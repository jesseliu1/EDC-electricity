"""测试配置"""
# ruff: noqa: E402

import asyncio
import copy
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete


def _resolve_sqlite_db_path(database_url: str) -> Path | None:
    """把 sqlite URL 解析成文件路径，便于保护联调库。"""
    sqlite_prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return None
    raw_path = database_url.removeprefix(sqlite_prefix)
    if raw_path.startswith("/") and len(raw_path) >= 3 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return Path(raw_path).resolve()


_SERVER_ROOT = Path(__file__).resolve().parents[1]
_SHARED_DB_PATH = (_SERVER_ROOT / "data" / "asns.db").resolve()
_AUTO_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="asns-pytest-db-"))
_CONFIGURED_TEST_DB_PATH = Path(
    os.environ.get("ASNS_TEST_DB_PATH") or (_AUTO_TEST_DB_DIR / "asns-test.db")
).resolve()
_CONFIGURED_TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if _CONFIGURED_TEST_DB_PATH.exists():
    _CONFIGURED_TEST_DB_PATH.unlink()

os.environ.setdefault(
    "ASNS_DATABASE_URL",
    f"sqlite+aiosqlite:///{_CONFIGURED_TEST_DB_PATH.as_posix()}",
)

_RESOLVED_TEST_DB_PATH = _resolve_sqlite_db_path(os.environ["ASNS_DATABASE_URL"])
if _RESOLVED_TEST_DB_PATH == _SHARED_DB_PATH:
    raise RuntimeError(
        "pytest 已被阻止：当前测试数据库仍指向 apps/server/data/asns.db。"
        " 请改用独立测试库，或仅设置 ASNS_TEST_DB_PATH。"
    )

from src.api.baseline_definitions import (
    _DEFINITION_STORE,
    _PREVIEW_JOB_STORE,
    _reload_definition_store,
)
from src.api.baselines import _BASELINE_STORE, _reload_baseline_store
from src.api.heats import (
    _ACTIVE_HEAT_RUNTIME,
    _COMPARE_BASELINE_CACHE,
    _COMPARE_CHANNEL_CURVE_CACHE,
    _HEAT_COMPARE_CACHE,
    _HEAT_ID_ALIAS_STORE,
    _HEAT_RUNTIME_REFRESH_META,
    _HEAT_STORE,
    _HEAT_STREAM_PROCESSOR_STATE,
    _LIVE_HEAT_CACHE,
    _MOCK_HEAT_STREAM_STORE,
    _NEXT_MOCK_HEAT_INDEX,
    _PREVIOUS_HEAT_RUNTIME,
    _reset_heat_runtime_refresh_meta,
    _seed_heats,
)
from src.api.settings import (
    _CHANNEL_ROLE_BINDING_STORE,
    _HOST_CHANNEL_CATALOG_CACHE,
    _HOST_CHANNEL_LAST_SYNC_AT,
    _HOST_CHANNEL_STORE,
    _HOST_CONNECTIVITY_STATUS,
    _HOST_SOURCE_REVISION,
    _SETTINGS_STORE,
    _reconcile_channel_role_binding_store,
)
from src.api.tasks import _SHOWTIME_TASK_STORE, _TASK_STORE
from src.config import settings
from src.database import Base, async_session_maker, engine
from src.main import app
from src.models import (
    Baseline,
    BaselineDefinition,
    BaselineDefinitionMetric,
    Heat,
    HeatBaselineBinding,
    MetricSeries,
    Setting,
)
from src.runtime_state import _SECTION_TO_KEY, load_runtime_state
from src.services import close_shared_edc_clients, encode_baseline_id

FORMAL_PRIMARY_BASELINE_ID = encode_baseline_id("def-001", "001")
FORMAL_SECONDARY_BASELINE_ID = encode_baseline_id("def-002", "001")


@pytest.fixture(scope="session", autouse=True)
def cleanup_auto_test_db() -> None:
    """清理 pytest 自动生成的独立测试库目录。"""
    yield
    if "ASNS_TEST_DB_PATH" in os.environ:
        return
    shutil.rmtree(_AUTO_TEST_DB_DIR, ignore_errors=True)


async def _stop_runtime_background_tasks() -> None:
    import src.api.heats as heats_module
    from src.services import heat_replay_batch_service

    await heats_module.stop_heat_runtime_refresh_loop()
    inflight = heats_module._HEAT_RUNTIME_REFRESH_INFLIGHT
    if inflight is not None and not inflight.done():
        inflight.cancel()
        try:
            await inflight
        except asyncio.CancelledError:
            pass
    heats_module._HEAT_RUNTIME_REFRESH_INFLIGHT = None
    for task in list(heat_replay_batch_service._REPLAY_TASKS.values()):
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    heat_replay_batch_service._REPLAY_TASKS.clear()
    heat_replay_batch_service._REPLAY_ACTIVE_CHANNELS.clear()
    heat_replay_batch_service._REPLAY_JOB_SNAPSHOTS.clear()


async def _reset_test_database() -> None:
    await close_shared_edc_clients()
    await _stop_runtime_background_tasks()
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def _build_test_reference_heats() -> dict[str, dict]:
    """测试专用：构造一组可作为真实推断缓存的参考炉次。"""
    seeded = copy.deepcopy(_seed_heats())
    for item in seeded.values():
        item["record_source"] = "live_inferred"
        item["current_curve_source"] = "live_edc"
        item["baseline_curve_source"] = "none"
    return seeded


def _build_test_host_channels() -> list[dict[str, str]]:
    return [
        {
            "id": "2349-199",
            "device_name": "测试电表 · 三相智能电表",
            "device_type": "三相智能电表",
            "area": "测试电力",
            "suid": "2349",
            "cuid": "199",
            "channel_name": "总有功功率",
            "unit": "kW",
            "last_value": "--",
            "status": "online",
        },
        {
            "id": "2349-142",
            "device_name": "测试电表 · 三相智能电表",
            "device_type": "三相智能电表",
            "area": "测试电力",
            "suid": "2349",
            "cuid": "142",
            "channel_name": "A相有功功率",
            "unit": "kW",
            "last_value": "--",
            "status": "online",
        },
        {
            "id": "2349-128",
            "device_name": "测试电表 · 三相智能电表",
            "device_type": "三相智能电表",
            "area": "测试电力",
            "suid": "2349",
            "cuid": "128",
            "channel_name": "A相电压",
            "unit": "V",
            "last_value": "--",
            "status": "online",
        },
        {
            "id": "2349-130",
            "device_name": "测试电表 · 三相智能电表",
            "device_type": "三相智能电表",
            "area": "测试电力",
            "suid": "2349",
            "cuid": "130",
            "channel_name": "B相电压",
            "unit": "V",
            "last_value": "--",
            "status": "online",
        },
        {
            "id": "2054-128",
            "device_name": "测试温度 A · 热电偶温度采集器",
            "device_type": "热电偶温度采集器",
            "area": "测试温度 A",
            "suid": "2054",
            "cuid": "128",
            "channel_name": "热电偶温度采集通道",
            "unit": "℃",
            "last_value": "--",
            "status": "online",
        },
        {
            "id": "2066-128",
            "device_name": "测试温度 B · 热电偶温度采集器",
            "device_type": "热电偶温度采集器",
            "area": "测试温度 B",
            "suid": "2066",
            "cuid": "128",
            "channel_name": "热电偶温度采集通道",
            "unit": "℃",
            "last_value": "--",
            "status": "online",
        },
        {
            "id": "769-128",
            "device_name": "测试压力 · 电流信号转换器",
            "device_type": "General 4-20 mA to CAN Converter",
            "area": "测试压力",
            "suid": "769",
            "cuid": "128",
            "channel_name": "AD_CH1",
            "unit": "MPa",
            "last_value": "--",
            "status": "online",
        },
        {
            "id": "769-129",
            "device_name": "测试压力 · 电流信号转换器",
            "device_type": "General 4-20 mA to CAN Converter",
            "area": "测试压力",
            "suid": "769",
            "cuid": "129",
            "channel_name": "AD_CH2",
            "unit": "MPa",
            "last_value": "--",
            "status": "online",
        },
    ]


def _bind_test_definition_channels() -> None:
    bindings = {
        "def-001": ["2349-199", "2349-128", "2054-128"],
        "def-002": ["2349-142", "2349-130", "2066-128", "769-128"],
    }
    for definition_id, channel_ids in bindings.items():
        definition = _DEFINITION_STORE.get(definition_id)
        if not definition:
            continue
        metrics = definition.get("metrics", [])
        if not isinstance(metrics, list):
            continue
        for metric, channel_id in zip(metrics, channel_ids, strict=False):
            if isinstance(metric, dict):
                metric["edc_channel_id"] = channel_id


async def _seed_formal_reference_records() -> None:
    now = datetime(2026, 3, 12, 10, 45, 0)
    heat_start = datetime(2026, 3, 12, 10, 0, 0)
    heat_end = datetime(2026, 3, 12, 10, 45, 0)
    context_start = heat_start - timedelta(minutes=30)
    context_end = heat_end + timedelta(minutes=30)

    def _series_payload(*, values: list[tuple[datetime, float]]) -> str:
        return json.dumps(
            {
                "context_start_time": context_start.isoformat(),
                "heat_start_time": heat_start.isoformat(),
                "heat_end_time": heat_end.isoformat(),
                "context_end_time": context_end.isoformat(),
                "points": [
                    {"timestamp": int(point_time.timestamp() * 1000), "value": value}
                    for point_time, value in values
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    async with async_session_maker() as session:
        session.add_all(
            [
                BaselineDefinition(
                    id="def-001",
                    definition_name="标准熔炼基线定义",
                    description="测试正式定义一",
                    expected_duration_minutes=45,
                    status="active",
                    created_by="tester",
                    updated_by="tester",
                    created_at=now,
                    updated_at=now,
                ),
                BaselineDefinition(
                    id="def-002",
                    definition_name="高功率熔炼基线定义",
                    description="测试正式定义二",
                    expected_duration_minutes=35,
                    status="active",
                    created_by="tester",
                    updated_by="tester",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add_all(
            [
                BaselineDefinitionMetric(
                    definition_id="def-001",
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#1152d4",
                    sort_order=1,
                    edc_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
                BaselineDefinitionMetric(
                    definition_id="def-001",
                    item="002",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    edc_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="测试设备 / A相电压 / V",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
                BaselineDefinitionMetric(
                    definition_id="def-002",
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="A相有功功率",
                    unit="kW",
                    color="#f97316",
                    sort_order=1,
                    edc_channel_id="2349-142",
                    source_channel_name="A相有功功率",
                    source_channel_label="测试设备 / A相有功功率 / kW",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
                BaselineDefinitionMetric(
                    definition_id="def-002",
                    item="002",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="B相电压",
                    unit="V",
                    color="#ef4444",
                    sort_order=2,
                    edc_channel_id="2349-130",
                    source_channel_name="B相电压",
                    source_channel_label="测试设备 / B相电压 / V",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add_all(
            [
                Baseline(
                    definition_id="def-001",
                    item="001",
                    item_kind="baseline_version",
                    name="标准基线 v2.1",
                    description="标准基线正式样本",
                    status="published",
                    is_default=True,
                    source_heat_id="heat-001",
                    selected_start_time=heat_start,
                    selected_end_time=heat_end,
                    effective_from=datetime(2026, 3, 12, 11, 0, 0),
                    tolerance_percent=15.0,
                    created_by="tester",
                    updated_by="tester",
                    created_at=now,
                    updated_at=now,
                    published_at=now,
                ),
                Baseline(
                    definition_id="def-002",
                    item="001",
                    item_kind="baseline_version",
                    name="高功率基线",
                    description="高功率草稿样本",
                    status="draft",
                    is_default=False,
                    source_heat_id="heat-001",
                    selected_start_time=heat_start,
                    selected_end_time=heat_end,
                    effective_from=datetime(2026, 3, 13, 8, 0, 0),
                    tolerance_percent=12.0,
                    created_by="tester",
                    updated_by="tester",
                    created_at=now,
                    updated_at=now,
                    published_at=None,
                ),
            ]
        )
        session.add(
            Heat(
                id="heat-001",
                heat_no="H20260312-1000",
                description="正式历史炉次样本",
                furnace_id="Furnace-A01",
                start_time=heat_start,
                end_time=heat_end,
                context_start_time=context_start,
                context_end_time=context_end,
                is_manually_adjusted=False,
                sealed_at=now,
                source_kind="live_inferred",
                cut_reason="live_inferred",
                cut_status="normal",
                status="normal",
                created_by="tester",
                updated_by="tester",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            HeatBaselineBinding(
                heat_id="heat-001",
                baseline_definition_id="def-001",
                baseline_item="001",
                is_primary=True,
                effective_from_snapshot=datetime(2026, 3, 12, 11, 0, 0),
                tolerance_percent_snapshot=15.0,
                analysis_status="ready",
                deviation_score=18.5,
                avg_deviation_score=9.2,
                analysis_details_json=json.dumps(
                    {
                        "abnormal_ranges": [
                            {
                                "start": int((heat_start + timedelta(minutes=18)).timestamp() * 1000),
                                "end": int((heat_start + timedelta(minutes=23)).timestamp() * 1000),
                                "score": 18.5,
                            }
                        ]
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                abnormal_duration_minutes=4.0,
                created_at=now,
                updated_at=now,
            )
        )
        session.add_all(
            [
                MetricSeries(
                    owner_key=FORMAL_PRIMARY_BASELINE_ID,
                    item="001",
                    owner_type="baseline",
                    definition_id="def-001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#1152d4",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    series_json=json.dumps(
                        {
                            "points": [
                                {"timestamp": int(heat_start.timestamp() * 1000), "value": 410.0},
                                {"timestamp": int(heat_end.timestamp() * 1000), "value": 420.0},
                            ]
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    stat_json=json.dumps({"avg": 415.0}, ensure_ascii=False, separators=(",", ":")),
                    created_at=now,
                    updated_at=now,
                ),
                MetricSeries(
                    owner_key=FORMAL_PRIMARY_BASELINE_ID,
                    item="002",
                    owner_type="baseline",
                    definition_id="def-001",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    source_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="测试设备 / A相电压 / V",
                    series_json=json.dumps(
                        {
                            "points": [
                                {"timestamp": int(heat_start.timestamp() * 1000), "value": 220.0},
                                {"timestamp": int(heat_end.timestamp() * 1000), "value": 222.0},
                            ]
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    stat_json=json.dumps({"avg": 221.0}, ensure_ascii=False, separators=(",", ":")),
                    created_at=now,
                    updated_at=now,
                ),
                MetricSeries(
                    owner_key="heat-001",
                    item="001",
                    owner_type="heat",
                    definition_id="def-001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#1152d4",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    series_json=_series_payload(
                        values=[
                            (context_start, 32.5),
                            (heat_start, 430.0),
                            (heat_end, 436.0),
                            (context_end, 28.0),
                        ]
                    ),
                    stat_json=json.dumps(
                        {"context_min": 28.0, "context_max": 436.0, "heat_avg": 433.0},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    created_at=now,
                    updated_at=now,
                ),
                MetricSeries(
                    owner_key="heat-001",
                    item="002",
                    owner_type="heat",
                    definition_id="def-001",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    source_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="测试设备 / A相电压 / V",
                    series_json=_series_payload(
                        values=[
                            (context_start, 198.0),
                            (heat_start, 221.0),
                            (heat_end, 222.0),
                            (context_end, 201.0),
                        ]
                    ),
                    stat_json=json.dumps(
                        {"context_min": 198.0, "context_max": 222.0, "heat_avg": 221.5},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()


@pytest_asyncio.fixture
async def client(reset_in_memory_stores):
    """创建测试客户端"""
    await _reset_test_database()
    await _seed_formal_reference_records()
    async with async_session_maker() as session:
        await session.execute(delete(Setting).where(Setting.key.in_(_SECTION_TO_KEY.values())))
        await session.commit()
    await load_runtime_state()
    await _reload_definition_store()
    await _reload_baseline_store()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await _stop_runtime_background_tasks()
    await close_shared_edc_clients()


@pytest_asyncio.fixture
async def reset_test_database(reset_in_memory_stores):
    """为不走 HTTP client 的用例提供独立测试库。"""
    await _reset_test_database()
    yield
    await _stop_runtime_background_tasks()
    await close_shared_edc_clients()


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """隔离 API 模块内的全局内存状态，避免测试互相污染。"""
    baseline_snapshot = copy.deepcopy(_BASELINE_STORE)
    definition_snapshot = copy.deepcopy(_DEFINITION_STORE)
    heat_snapshot = copy.deepcopy(_HEAT_STORE)
    active_heat_snapshot = copy.deepcopy(_ACTIVE_HEAT_RUNTIME)
    previous_heat_snapshot = copy.deepcopy(_PREVIOUS_HEAT_RUNTIME)
    heat_id_alias_snapshot = copy.deepcopy(_HEAT_ID_ALIAS_STORE)
    heat_stream_processor_snapshot = copy.deepcopy(_HEAT_STREAM_PROCESSOR_STATE)
    heat_runtime_refresh_meta_snapshot = copy.deepcopy(_HEAT_RUNTIME_REFRESH_META)
    live_heat_cache_snapshot = copy.deepcopy(_LIVE_HEAT_CACHE)
    heat_compare_cache_snapshot = copy.deepcopy(_HEAT_COMPARE_CACHE)
    compare_baseline_cache_snapshot = copy.deepcopy(_COMPARE_BASELINE_CACHE)
    compare_channel_curve_cache_snapshot = copy.deepcopy(_COMPARE_CHANNEL_CURVE_CACHE)
    mock_heat_snapshot = copy.deepcopy(_MOCK_HEAT_STREAM_STORE)
    task_snapshot = copy.deepcopy(_TASK_STORE)
    showtime_task_snapshot = copy.deepcopy(_SHOWTIME_TASK_STORE)
    settings_snapshot = copy.deepcopy(_SETTINGS_STORE)
    host_channel_snapshot = copy.deepcopy(_HOST_CHANNEL_STORE)
    host_channel_catalog_snapshot = copy.deepcopy(_HOST_CHANNEL_CATALOG_CACHE)
    channel_role_binding_snapshot = copy.deepcopy(_CHANNEL_ROLE_BINDING_STORE)
    host_channel_last_sync_snapshot = _HOST_CHANNEL_LAST_SYNC_AT
    host_source_revision_snapshot = _HOST_SOURCE_REVISION
    host_connectivity_status_snapshot = copy.deepcopy(_HOST_CONNECTIVITY_STATUS)
    next_heat_index_snapshot = _NEXT_MOCK_HEAT_INDEX
    enable_mock_dataset_snapshot = settings.enable_mock_dataset
    for entry in list(_PREVIEW_JOB_STORE.values()):
        task = entry.get("task")
        if task is not None and hasattr(task, "cancel") and not task.done():
            task.cancel()
    _PREVIEW_JOB_STORE.clear()
    _HEAT_STORE.clear()
    _HEAT_STORE.update(copy.deepcopy(_build_test_reference_heats()))
    _ACTIVE_HEAT_RUNTIME.clear()
    _PREVIOUS_HEAT_RUNTIME.clear()
    _HEAT_ID_ALIAS_STORE.clear()
    _HEAT_STREAM_PROCESSOR_STATE.clear()
    _reset_heat_runtime_refresh_meta()
    _HEAT_RUNTIME_REFRESH_META["snapshot_status"] = "ready"
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(copy.deepcopy(_build_test_host_channels()))
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend(copy.deepcopy(_HOST_CHANNEL_STORE))
    _bind_test_definition_channels()
    _reconcile_channel_role_binding_store()
    _LIVE_HEAT_CACHE.clear()
    _LIVE_HEAT_CACHE["contexts"] = {}
    _HEAT_COMPARE_CACHE["entries"] = {}
    _COMPARE_BASELINE_CACHE["entries"] = {}
    _COMPARE_CHANNEL_CURVE_CACHE["entries"] = {}
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    _SETTINGS_STORE["active_baseline_id"]["value"] = FORMAL_PRIMARY_BASELINE_ID

    yield

    _BASELINE_STORE.clear()
    _BASELINE_STORE.update(copy.deepcopy(baseline_snapshot))

    _DEFINITION_STORE.clear()
    _DEFINITION_STORE.update(copy.deepcopy(definition_snapshot))

    _HEAT_STORE.clear()
    _HEAT_STORE.update(copy.deepcopy(heat_snapshot))

    _ACTIVE_HEAT_RUNTIME.clear()
    _ACTIVE_HEAT_RUNTIME.update(copy.deepcopy(active_heat_snapshot))

    _PREVIOUS_HEAT_RUNTIME.clear()
    _PREVIOUS_HEAT_RUNTIME.update(copy.deepcopy(previous_heat_snapshot))

    _HEAT_ID_ALIAS_STORE.clear()
    _HEAT_ID_ALIAS_STORE.update(copy.deepcopy(heat_id_alias_snapshot))

    _HEAT_STREAM_PROCESSOR_STATE.clear()
    _HEAT_STREAM_PROCESSOR_STATE.update(copy.deepcopy(heat_stream_processor_snapshot))

    _HEAT_RUNTIME_REFRESH_META.clear()
    _HEAT_RUNTIME_REFRESH_META.update(copy.deepcopy(heat_runtime_refresh_meta_snapshot))

    _LIVE_HEAT_CACHE.clear()
    _LIVE_HEAT_CACHE.update(copy.deepcopy(live_heat_cache_snapshot))

    _HEAT_COMPARE_CACHE.clear()
    _HEAT_COMPARE_CACHE.update(copy.deepcopy(heat_compare_cache_snapshot))

    _COMPARE_BASELINE_CACHE.clear()
    _COMPARE_BASELINE_CACHE.update(copy.deepcopy(compare_baseline_cache_snapshot))

    _COMPARE_CHANNEL_CURVE_CACHE.clear()
    _COMPARE_CHANNEL_CURVE_CACHE.update(copy.deepcopy(compare_channel_curve_cache_snapshot))

    _MOCK_HEAT_STREAM_STORE.clear()
    _MOCK_HEAT_STREAM_STORE.update(copy.deepcopy(mock_heat_snapshot))

    _TASK_STORE.clear()
    _TASK_STORE.update(copy.deepcopy(task_snapshot))

    _SHOWTIME_TASK_STORE.clear()
    _SHOWTIME_TASK_STORE.update(copy.deepcopy(showtime_task_snapshot))

    _SETTINGS_STORE.clear()
    _SETTINGS_STORE.update(copy.deepcopy(settings_snapshot))

    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(copy.deepcopy(host_channel_snapshot))

    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend(copy.deepcopy(host_channel_catalog_snapshot))

    _CHANNEL_ROLE_BINDING_STORE.clear()
    _CHANNEL_ROLE_BINDING_STORE.update(copy.deepcopy(channel_role_binding_snapshot))

    _HOST_CONNECTIVITY_STATUS.clear()
    _HOST_CONNECTIVITY_STATUS.update(copy.deepcopy(host_connectivity_status_snapshot))

    import src.api.settings as settings_module

    settings_module._HOST_CHANNEL_LAST_SYNC_AT = host_channel_last_sync_snapshot
    settings_module._HOST_SOURCE_REVISION = host_source_revision_snapshot

    import src.api.heats as heats_module

    heats_module._NEXT_MOCK_HEAT_INDEX = next_heat_index_snapshot
    for entry in list(_PREVIEW_JOB_STORE.values()):
        task = entry.get("task")
        if task is not None and hasattr(task, "cancel") and not task.done():
            task.cancel()
    _PREVIEW_JOB_STORE.clear()
    settings.enable_mock_dataset = enable_mock_dataset_snapshot
