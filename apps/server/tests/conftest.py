"""测试配置"""

import copy
from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from src.api.baseline_definitions import _DEFINITION_STORE
from src.api.baselines import _BASELINE_STORE
from src.api.heats import (
    _COMPARE_BASELINE_CACHE,
    _COMPARE_CHANNEL_CURVE_CACHE,
    _HEAT_COMPARE_CACHE,
    _HEAT_STORE,
    _LIVE_HEAT_CACHE,
    _MOCK_HEAT_STREAM_STORE,
    _NEXT_MOCK_HEAT_INDEX,
    _get_live_heat_cache_entry,
    _resolve_live_heat_inference_context,
    _seed_heats,
)
from src.api.settings import (
    _CHANNEL_ROLE_BINDING_STORE,
    _HOST_CHANNEL_CATALOG_CACHE,
    _HOST_CHANNEL_LAST_SYNC_AT,
    _HOST_SOURCE_REVISION,
    _HOST_CHANNEL_STORE,
    _HOST_CONNECTIVITY_STATUS,
    _SETTINGS_STORE,
    _reconcile_channel_role_binding_store,
)
from src.api.tasks import _SHOWTIME_TASK_STORE, _TASK_STORE
from src.config import settings
from src.database import async_session_maker, init_db
from src.models import Setting
from src.main import app
from src.runtime_state import _SECTION_TO_KEY, load_runtime_state
from src.services import close_shared_edc_clients


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


@pytest.fixture
async def client(reset_in_memory_stores):
    """创建测试客户端"""
    await close_shared_edc_clients()
    await init_db()
    async with async_session_maker() as session:
        await session.execute(delete(Setting).where(Setting.key.in_(_SECTION_TO_KEY.values())))
        await session.commit()
    await load_runtime_state()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_shared_edc_clients()


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """隔离 API 模块内的全局内存状态，避免测试互相污染。"""
    baseline_snapshot = copy.deepcopy(_BASELINE_STORE)
    definition_snapshot = copy.deepcopy(_DEFINITION_STORE)
    heat_snapshot = copy.deepcopy(_HEAT_STORE)
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
    _HEAT_STORE.clear()
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(copy.deepcopy(_build_test_host_channels()))
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend(copy.deepcopy(_HOST_CHANNEL_STORE))
    _bind_test_definition_channels()
    _reconcile_channel_role_binding_store()
    _LIVE_HEAT_CACHE.clear()
    _LIVE_HEAT_CACHE["contexts"] = {}
    default_context = _resolve_live_heat_inference_context()
    if default_context:
        cache_entry = _get_live_heat_cache_entry(default_context)
        cache_entry["expires_at"] = datetime.now() + timedelta(hours=1)
        cache_entry["items"] = _build_test_reference_heats()
    _HEAT_COMPARE_CACHE["entries"] = {}
    _COMPARE_BASELINE_CACHE["entries"] = {}
    _COMPARE_CHANNEL_CURVE_CACHE["entries"] = {}
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"

    yield

    _BASELINE_STORE.clear()
    _BASELINE_STORE.update(copy.deepcopy(baseline_snapshot))

    _DEFINITION_STORE.clear()
    _DEFINITION_STORE.update(copy.deepcopy(definition_snapshot))

    _HEAT_STORE.clear()
    _HEAT_STORE.update(copy.deepcopy(heat_snapshot))

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
    settings.enable_mock_dataset = enable_mock_dataset_snapshot
