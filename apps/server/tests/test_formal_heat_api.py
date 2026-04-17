"""正式历史炉次 API 测试。"""

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, select

from src.api.heats import (
    _ACTIVE_HEAT_RUNTIME,
    _HEAT_STORE,
    _PREVIOUS_HEAT_RUNTIME,
    _build_live_heat_context,
    _resolve_baseline_version_for_time,
    refresh_heat_runtime_state,
)
from src.database import async_session_maker
from src.models import (
    Baseline,
    BaselineDefinition,
    BaselineDefinitionMetric,
    Heat,
    HeatBaselineBinding,
    MetricSeries,
)
from src.schemas.common import CurvePoint
from src.services import (
    compile_runtime_candidates,
    get_formal_heat_record,
    persist_sealed_heat_candidates,
    prepare_runtime_candidates_for_persist,
)
from src.time_utils import from_timestamp_ms, to_timestamp_ms


@pytest.fixture(autouse=True)
def _patch_runtime_metric_curve_loader(monkeypatch):
    async def fake_load_runtime_metric_curves(
        metrics: list[dict[str, object]],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, list[CurvePoint]]:
        curves: dict[str, list[CurvePoint]] = {}
        for metric in metrics:
            metric_id = str(metric.get("id") or "")
            metric_key = str(metric.get("metric_key") or "")
            if metric_key == "power":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(start_time), value=430.0),
                    CurvePoint(timestamp=to_timestamp_ms(end_time), value=438.0),
                ]
            elif metric_key == "voltage":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(start_time), value=221.0),
                    CurvePoint(timestamp=to_timestamp_ms(end_time), value=226.0),
                ]
        return curves

    monkeypatch.setattr(
        "src.api.heats._load_runtime_metric_curves", fake_load_runtime_metric_curves
    )


async def _insert_formal_heat_fixture() -> str:
    now = datetime.now().replace(microsecond=0)
    heat_id = "heat-history-001"
    definition_id = "def-history-001"
    async with async_session_maker() as session:
        session.add(
            BaselineDefinition(
                id=definition_id,
                definition_name="正式炉次定义",
                description="测试",
                expected_duration_minutes=30,
                status="active",
                created_by="tester",
                updated_by="tester",
                created_at=now,
                updated_at=now,
            )
        )
        session.add_all(
            [
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    edc_channel_id="2349-199",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="002",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    edc_channel_id="2349-128",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add(
            Baseline(
                definition_id=definition_id,
                item="001",
                item_kind="baseline_version",
                name="正式基线 V1",
                description="已发布基线",
                status="published",
                is_default=True,
                source_heat_id=heat_id,
                selected_start_time=now - timedelta(minutes=25),
                selected_end_time=now,
                effective_from=now - timedelta(minutes=10),
                tolerance_percent=15.0,
                created_by="tester",
                updated_by="tester",
                created_at=now,
                updated_at=now,
                published_at=now,
            )
        )
        session.add(
            Heat(
                id=heat_id,
                heat_no="H20260404-1800",
                description="正式历史炉次",
                furnace_id="Furnace-A01",
                start_time=now - timedelta(minutes=25),
                end_time=now,
                context_start_time=now - timedelta(minutes=55),
                context_end_time=now + timedelta(minutes=30),
                is_manually_adjusted=False,
                sealed_at=now + timedelta(minutes=1),
                source_kind="live_inferred",
                cut_reason="live_inferred",
                cut_status="normal",
                status="normal",
                created_by="system",
                updated_by="system",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            HeatBaselineBinding(
                heat_id=heat_id,
                baseline_definition_id=definition_id,
                baseline_item="001",
                is_primary=True,
                effective_from_snapshot=now - timedelta(minutes=10),
                tolerance_percent_snapshot=15.0,
                analysis_status="ready",
                deviation_score=12.3,
                avg_deviation_score=8.1,
                analysis_details_json=json.dumps(
                    {
                        "abnormal_ranges": [
                            {
                                "start": int((now - timedelta(minutes=12)).timestamp() * 1000),
                                "end": int((now - timedelta(minutes=9)).timestamp() * 1000),
                                "score": 12.3,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                abnormal_duration_minutes=3.0,
                created_at=now,
                updated_at=now,
            )
        )
        series_payload = {
            "context_start_time": (now - timedelta(minutes=55)).isoformat(),
            "heat_start_time": (now - timedelta(minutes=25)).isoformat(),
            "heat_end_time": now.isoformat(),
            "context_end_time": (now + timedelta(minutes=30)).isoformat(),
            "points": [
                {"timestamp": int((now - timedelta(minutes=55)).timestamp() * 1000), "value": 18.5},
                {
                    "timestamp": int((now - timedelta(minutes=25)).timestamp() * 1000),
                    "value": 420.0,
                },
                {"timestamp": int(now.timestamp() * 1000), "value": 430.0},
            ],
        }
        session.add_all(
            [
                MetricSeries(
                    owner_key=f"{definition_id}:001",
                    item="001",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="A01 / 总有功功率 / kW",
                    series_json=json.dumps(
                        {
                            "points": [
                                {
                                    "timestamp": int(
                                        (now - timedelta(minutes=25)).timestamp() * 1000
                                    ),
                                    "value": 410.0,
                                },
                                {"timestamp": int(now.timestamp() * 1000), "value": 420.0},
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    stat_json=json.dumps({"avg": 415.0}, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                ),
                MetricSeries(
                    owner_key=f"{definition_id}:001",
                    item="002",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    source_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="A01 / A相电压 / V",
                    series_json=json.dumps(
                        {
                            "points": [
                                {
                                    "timestamp": int(
                                        (now - timedelta(minutes=25)).timestamp() * 1000
                                    ),
                                    "value": 220.0,
                                },
                                {"timestamp": int(now.timestamp() * 1000), "value": 225.0},
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    stat_json=json.dumps({"avg": 222.5}, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                ),
                MetricSeries(
                    owner_key=heat_id,
                    item="001",
                    owner_type="heat",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="A01 / 总有功功率 / kW",
                    series_json=json.dumps(series_payload, ensure_ascii=False),
                    stat_json=json.dumps({"heat_avg": 425.0}, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                ),
                MetricSeries(
                    owner_key=heat_id,
                    item="002",
                    owner_type="heat",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    source_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="A01 / A相电压 / V",
                    series_json=json.dumps(series_payload, ensure_ascii=False),
                    stat_json=json.dumps({"heat_avg": 225.0}, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()
    return heat_id


@pytest.mark.asyncio
async def test_list_heats_reads_history_from_formal_tables(client) -> None:
    heat_id = await _insert_formal_heat_fixture()

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    item = next(entry for entry in payload["items"] if entry["id"] == heat_id)
    assert item["record_source"] == "sealed_history"
    assert item["current_curve_source"] == "formal_db"
    assert item["baseline_id"] == "def-history-001:001"
    assert item["deviation_score"] == pytest.approx(12.3)


@pytest.mark.asyncio
async def test_list_heats_keeps_overlapping_previous_runtime_alongside_formal_history(client) -> None:
    heat_id = await _insert_formal_heat_fixture()
    formal_item = await get_formal_heat_record(heat_id)
    assert formal_item is not None

    _PREVIOUS_HEAT_RUNTIME.clear()
    _PREVIOUS_HEAT_RUNTIME["live-heat-overlap-001"] = {
        **formal_item,
        "id": "live-heat-overlap-001",
        "record_source": "previous_runtime",
        "completion_status": "completed",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "none",
        "sealed_at": None,
    }

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    items = response.json()["items"]

    assert any(
        item["id"] == heat_id and item["record_source"] == "sealed_history" for item in items
    )
    assert any(
        item["id"] == "live-heat-overlap-001" and item["record_source"] == "previous_runtime"
        for item in items
    )


@pytest.mark.asyncio
async def test_get_heat_curve_reads_formal_metric_series(client) -> None:
    heat_id = await _insert_formal_heat_fixture()

    _ACTIVE_HEAT_RUNTIME.clear()
    _PREVIOUS_HEAT_RUNTIME.clear()

    detail_resp = await client.get(f"/api/heats/{heat_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["record_source"] == "sealed_history"

    curve_resp = await client.get(f"/api/heats/{heat_id}/curve")
    assert curve_resp.status_code == 200
    payload = curve_resp.json()
    assert len(payload["power_curve"]) == 3
    assert len(payload["voltage_curve"]) == 3
    assert payload["current_curve_source"] == "formal_db"


@pytest.mark.asyncio
async def test_get_heat_compare_for_history_avoids_live_edc(client, monkeypatch) -> None:
    heat_id = await _insert_formal_heat_fixture()

    async def fail_channel_curves(**_kwargs):
        raise AssertionError("历史 compare 不应再请求实时通道曲线")

    async def fail_heat_curves(_item):
        raise AssertionError("历史 compare 不应再回退请求热炉实时曲线")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_channel_curves)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_heat_curves)

    response = await client.get(f"/api/heats/{heat_id}/compare")
    assert response.status_code == 200
    payload = response.json()
    assert payload["heat"]["current_curve_source"] == "formal_db"
    assert payload["heat"]["baseline_curve_source"] == "formal_db"
    assert len(payload["heat"]["power_curve"]) == 3
    assert len(payload["baselines"][0]["metric_curves"][0]["current_curve"]) == 3


@pytest.mark.asyncio
async def test_get_heat_compare_for_history_with_missing_metric_still_never_falls_back_to_edc(
    client, monkeypatch
) -> None:
    heat_id = await _insert_formal_heat_fixture()

    async with async_session_maker() as session:
        await session.execute(
            delete(MetricSeries).where(
                MetricSeries.owner_key == heat_id,
                MetricSeries.item == "002",
            )
        )
        await session.commit()

    async def fail_channel_curves(**_kwargs):
        raise AssertionError("历史 compare 缺指标时也不应请求实时通道曲线")

    async def fail_heat_curves(_item):
        raise AssertionError("历史 compare 缺指标时也不应回退请求热炉实时曲线")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_channel_curves)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_heat_curves)

    response = await client.get(f"/api/heats/{heat_id}/compare")
    assert response.status_code == 409
    assert response.json()["detail"] == "compare_current_metric_curve_missing:voltage"


@pytest.mark.asyncio
async def test_update_history_heat_writes_formal_tables(client) -> None:
    heat_id = await _insert_formal_heat_fixture()
    before = await client.get(f"/api/heats/{heat_id}")
    assert before.status_code == 200
    before_payload = before.json()
    original_start = from_timestamp_ms(before_payload["start_time"])
    original_end = from_timestamp_ms(before_payload["end_time"])
    new_start = (original_start - timedelta(minutes=2)).replace(microsecond=0)
    new_end = (original_end - timedelta(minutes=1)).replace(microsecond=0)

    response = await client.patch(
        f"/api/heats/{heat_id}",
        json={
            "description": "手工修订后的历史炉次",
            "start_time": to_timestamp_ms(new_start),
            "end_time": to_timestamp_ms(new_end),
            "adjust_subsequent": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["description"] == "手工修订后的历史炉次"
    assert payload["is_manually_adjusted"] is True
    updated_start = from_timestamp_ms(payload["start_time"])
    updated_end = from_timestamp_ms(payload["end_time"])
    assert updated_start == new_start
    assert updated_end == new_end

    detail = await client.get(f"/api/heats/{heat_id}")
    assert detail.status_code == 200
    assert detail.json()["description"] == "手工修订后的历史炉次"
    assert detail.json()["is_manually_adjusted"] is True
    detail_start = from_timestamp_ms(detail.json()["start_time"])
    assert detail_start == new_start

    async with async_session_maker() as session:
        series_rows = list(
            (
                await session.execute(
                    select(MetricSeries)
                    .where(MetricSeries.owner_key == heat_id)
                    .where(MetricSeries.owner_type == "heat")
                    .order_by(MetricSeries.sort_order, MetricSeries.item)
                )
            ).scalars()
        )
    assert series_rows
    for row in series_rows:
        payload = json.loads(row.series_json)
        assert payload["heat_start_time"] == to_timestamp_ms(new_start)
        assert payload["heat_end_time"] == to_timestamp_ms(new_end)


@pytest.mark.asyncio
async def test_update_history_heat_rejects_adjust_subsequent(client) -> None:
    heat_id = await _insert_formal_heat_fixture()
    before = await client.get(f"/api/heats/{heat_id}")
    assert before.status_code == 200
    original_start = from_timestamp_ms(before.json()["start_time"])

    response = await client.patch(
        f"/api/heats/{heat_id}",
        json={
            "start_time": to_timestamp_ms(
                (original_start - timedelta(minutes=1)).replace(microsecond=0)
            ),
            "adjust_subsequent": True,
        },
    )
    assert response.status_code == 400
    assert "联动批量调整尚未实现" in response.json()["detail"]


@pytest.mark.asyncio
async def test_persist_sealed_heat_candidates_allows_overlapping_windows(
    reset_test_database,
) -> None:
    await _insert_formal_heat_fixture()
    base_start = datetime.now().replace(microsecond=0, second=0)
    candidates = [
        {
            "id": "heat-overlap-001",
            "heat_no": "HOVERLAP-001",
            "description": "重叠炉次一",
            "start_time": base_start,
            "end_time": base_start + timedelta(minutes=30),
            "context_start_time": base_start - timedelta(minutes=30),
            "context_end_time": base_start + timedelta(minutes=60),
            "record_source": "live_inferred",
            "cut_reason": "test",
            "cut_status": "normal",
            "status": "normal",
            "created_at": base_start,
            "power_curve": [
                CurvePoint(timestamp=to_timestamp_ms(base_start), value=420.0),
                CurvePoint(
                    timestamp=to_timestamp_ms(base_start + timedelta(minutes=30)),
                    value=430.0,
                ),
            ],
            "voltage_curve": [
                CurvePoint(timestamp=to_timestamp_ms(base_start), value=220.0),
                CurvePoint(
                    timestamp=to_timestamp_ms(base_start + timedelta(minutes=30)),
                    value=225.0,
                ),
            ],
        },
        {
            "id": "heat-overlap-002",
            "heat_no": "HOVERLAP-002",
            "description": "重叠炉次二",
            "start_time": base_start + timedelta(minutes=20),
            "end_time": base_start + timedelta(minutes=50),
            "context_start_time": base_start - timedelta(minutes=10),
            "context_end_time": base_start + timedelta(minutes=80),
            "record_source": "live_inferred",
            "cut_reason": "test",
            "cut_status": "normal",
            "status": "normal",
            "created_at": base_start + timedelta(minutes=20),
            "power_curve": [
                CurvePoint(
                    timestamp=to_timestamp_ms(base_start + timedelta(minutes=20)),
                    value=421.0,
                ),
                CurvePoint(
                    timestamp=to_timestamp_ms(base_start + timedelta(minutes=50)),
                    value=431.0,
                ),
            ],
            "voltage_curve": [
                CurvePoint(
                    timestamp=to_timestamp_ms(base_start + timedelta(minutes=20)),
                    value=221.0,
                ),
                CurvePoint(
                    timestamp=to_timestamp_ms(base_start + timedelta(minutes=50)),
                    value=226.0,
                ),
            ],
        },
    ]

    prepared = await prepare_runtime_candidates_for_persist(candidates, trigger_source="test")
    persisted = await persist_sealed_heat_candidates(prepared)

    assert "heat-overlap-001" in persisted
    assert "heat-overlap-002" in persisted
    assert persisted["heat-overlap-001"]["start_time"] < persisted["heat-overlap-002"]["start_time"]
    assert persisted["heat-overlap-001"]["end_time"] > persisted["heat-overlap-002"]["start_time"]


@pytest.mark.asyncio
async def test_prepare_runtime_candidates_persists_ready_binding_analysis(
    reset_test_database,
) -> None:
    definition_id = "def-analysis-ready-001"
    baseline_id = f"{definition_id}:001"
    start_time = datetime.now().replace(microsecond=0, second=0)
    end_time = start_time + timedelta(minutes=30)
    context_start_time = start_time - timedelta(minutes=30)
    context_end_time = end_time + timedelta(minutes=30)
    baseline_series_payload = json.dumps(
        {
            "points": [
                {"timestamp": to_timestamp_ms(start_time), "value": 410.0},
                {"timestamp": to_timestamp_ms(end_time), "value": 425.0},
                {
                    "timestamp": to_timestamp_ms(end_time + timedelta(minutes=15)),
                    "value": 430.0,
                },
            ]
        },
        ensure_ascii=False,
    )
    async with async_session_maker() as session:
        session.add(
            BaselineDefinition(
                id=definition_id,
                definition_name="统一分析 ready 定义",
                description="验证 runtime 分析结果可落库",
                expected_duration_minutes=30,
                status="active",
                created_by="tester",
                updated_by="tester",
                created_at=start_time,
                updated_at=start_time,
            )
        )
        session.add_all(
            [
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    edc_channel_id="2349-199",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="002",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    edc_channel_id="2349-128",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        session.add(
            Baseline(
                definition_id=definition_id,
                item="001",
                item_kind="baseline_version",
                name="统一分析 ready 基线",
                description="测试",
                status="published",
                is_default=True,
                source_heat_id="heat-analysis-ready-seed",
                selected_start_time=start_time,
                selected_end_time=end_time,
                effective_from=start_time - timedelta(minutes=5),
                tolerance_percent=15.0,
                created_by="tester",
                updated_by="tester",
                created_at=start_time,
                updated_at=start_time,
                published_at=start_time,
            )
        )
        session.add_all(
            [
                MetricSeries(
                    owner_key=baseline_id,
                    item="001",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 421.5}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
                MetricSeries(
                    owner_key=baseline_id,
                    item="002",
                    owner_type="baseline",
                    definition_id=definition_id,
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
                                {"timestamp": to_timestamp_ms(start_time), "value": 220.0},
                                {"timestamp": to_timestamp_ms(end_time), "value": 224.0},
                                {
                                    "timestamp": to_timestamp_ms(end_time + timedelta(minutes=15)),
                                    "value": 226.0,
                                },
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    stat_json=json.dumps({"avg": 223.3}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        await session.commit()

    candidate = {
        "id": "heat-analysis-001",
        "heat_no": "HANALYSIS-001",
        "description": "偏离度正式固化样本",
        "start_time": start_time,
        "end_time": end_time,
        "context_start_time": context_start_time,
        "context_end_time": context_end_time,
        "record_source": "live_inferred",
        "cut_reason": "test",
        "cut_status": "normal",
        "status": "normal",
        "created_at": start_time,
        "power_curve": [
            CurvePoint(timestamp=to_timestamp_ms(start_time), value=470.0),
            CurvePoint(timestamp=to_timestamp_ms(start_time + timedelta(minutes=30)), value=495.0),
        ],
        "voltage_curve": [
            CurvePoint(timestamp=to_timestamp_ms(start_time), value=222.0),
            CurvePoint(timestamp=to_timestamp_ms(start_time + timedelta(minutes=30)), value=228.0),
        ],
    }

    async def fake_metric_curve_loader(
        metrics: list[dict[str, object]],
        loader_start_time: datetime,
        loader_end_time: datetime,
    ) -> dict[str, list[CurvePoint]]:
        curves: dict[str, list[CurvePoint]] = {}
        for metric in metrics:
            metric_id = str(metric.get("id") or "")
            metric_key = str(metric.get("metric_key") or "")
            if metric_key == "power":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=470.0),
                    CurvePoint(
                        timestamp=to_timestamp_ms(start_time + timedelta(minutes=15)), value=482.0
                    ),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=495.0),
                ]
            elif metric_key == "voltage":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=222.0),
                    CurvePoint(
                        timestamp=to_timestamp_ms(start_time + timedelta(minutes=15)), value=225.0
                    ),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=228.0),
                ]
        return curves

    candidate["baseline_id"] = baseline_id
    prepared = await compile_runtime_candidates(
        [candidate],
        trigger_source="test",
        metric_curve_loader=fake_metric_curve_loader,
    )
    binding = prepared[0]["baseline_bindings"][0]
    assert binding["analysis_status"] == "ready"
    assert binding["deviation_score"] is not None
    assert binding["avg_deviation_score"] is not None
    assert binding["analysis_details_json"]

    persisted = await persist_sealed_heat_candidates(prepared)
    persisted_binding = persisted["heat-analysis-001"]["baseline_bindings"][0]
    assert persisted_binding["analysis_status"] == "ready"
    assert persisted_binding["deviation_score"] == pytest.approx(binding["deviation_score"])
    assert persisted_binding["avg_deviation_score"] == pytest.approx(binding["avg_deviation_score"])


@pytest.mark.asyncio
async def test_persist_sealed_heat_candidates_writes_all_runtime_metrics_to_db(
    reset_test_database,
) -> None:
    definition_id = "def-runtime-metrics-001"
    baseline_id = f"{definition_id}:001"
    start_time = datetime.now().replace(microsecond=0, second=0)
    end_time = start_time + timedelta(minutes=30)
    context_start_time = start_time - timedelta(minutes=15)
    context_end_time = end_time + timedelta(minutes=15)
    baseline_series_payload = json.dumps(
        {
            "points": [
                {"timestamp": to_timestamp_ms(start_time), "value": 410.0},
                {"timestamp": to_timestamp_ms(end_time), "value": 425.0},
            ]
        },
        ensure_ascii=False,
    )

    async with async_session_maker() as session:
        session.add(
            BaselineDefinition(
                id=definition_id,
                definition_name="运行态多指标定义",
                description="验证 runtime metric_series 全量落库",
                expected_duration_minutes=30,
                status="active",
                created_by="tester",
                updated_by="tester",
                created_at=start_time,
                updated_at=start_time,
            )
        )
        session.add_all(
            [
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    edc_channel_id="2349-199",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="002",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    edc_channel_id="2349-128",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="003",
                    item_kind="metric_item",
                    metric_key="temperature",
                    metric_name="熔炼温度",
                    unit="℃",
                    color="#E6A23C",
                    sort_order=3,
                    edc_channel_id="2054-128",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        session.add(
            Baseline(
                definition_id=definition_id,
                item="001",
                item_kind="baseline_version",
                name="运行态多指标基线",
                description="测试",
                status="published",
                is_default=True,
                source_heat_id="heat-runtime-metrics-seed",
                selected_start_time=start_time - timedelta(minutes=30),
                selected_end_time=start_time,
                effective_from=start_time - timedelta(hours=1),
                tolerance_percent=15.0,
                created_by="tester",
                updated_by="tester",
                created_at=start_time,
                updated_at=start_time,
                published_at=start_time,
            )
        )
        session.add_all(
            [
                MetricSeries(
                    owner_key=baseline_id,
                    item="001",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 417.5}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
                MetricSeries(
                    owner_key=baseline_id,
                    item="002",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    source_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="测试设备 / A相电压 / V",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 223.0}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
                MetricSeries(
                    owner_key=baseline_id,
                    item="003",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="temperature",
                    metric_name="熔炼温度",
                    unit="℃",
                    color="#E6A23C",
                    sort_order=3,
                    source_channel_id="2054-128",
                    source_channel_name="热电偶温度采集通道",
                    source_channel_label="测试设备 / 熔炼温度 / ℃",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 1555.0}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        await session.commit()

    async def fake_metric_curve_loader(
        metrics: list[dict[str, object]],
        loader_start_time: datetime,
        loader_end_time: datetime,
    ) -> dict[str, list[CurvePoint]]:
        curves: dict[str, list[CurvePoint]] = {}
        for metric in metrics:
            metric_id = str(metric.get("id") or "")
            metric_key = str(metric.get("metric_key") or "")
            if metric_key == "power":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=430.0),
                    CurvePoint(timestamp=to_timestamp_ms(start_time + timedelta(minutes=15)), value=434.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=438.0),
                ]
            elif metric_key == "voltage":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=221.0),
                    CurvePoint(timestamp=to_timestamp_ms(start_time + timedelta(minutes=15)), value=224.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=226.0),
                ]
            elif metric_key == "temperature":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=1548.0),
                    CurvePoint(timestamp=to_timestamp_ms(start_time + timedelta(minutes=15)), value=1557.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=1566.0),
                ]
        return curves

    prepared = await compile_runtime_candidates(
        [
            {
                "id": "heat-runtime-metrics-001",
                "heat_no": "HRUNTIME-001",
                "description": "运行态多指标正式固化样本",
                "start_time": start_time,
                "end_time": end_time,
                "context_start_time": context_start_time,
                "context_end_time": context_end_time,
                "baseline_id": baseline_id,
                "record_source": "live_inferred",
                "cut_reason": "test",
                "cut_status": "normal",
                "status": "normal",
                "created_at": start_time,
                "power_curve": [
                    CurvePoint(timestamp=to_timestamp_ms(start_time), value=430.0),
                    CurvePoint(timestamp=to_timestamp_ms(end_time), value=438.0),
                ],
            }
        ],
        trigger_source="test",
        metric_curve_loader=fake_metric_curve_loader,
    )

    runtime_metric_keys = {
        str(entry.get("metric_key") or "")
        for entry in prepared[0]["runtime_metric_series"]
        if isinstance(entry, dict)
    }
    assert {"power", "voltage", "temperature"} <= runtime_metric_keys

    await persist_sealed_heat_candidates(prepared)

    async with async_session_maker() as session:
        series_rows = list(
            (
                await session.execute(
                    select(MetricSeries)
                    .where(MetricSeries.owner_key == "heat-runtime-metrics-001")
                    .where(MetricSeries.owner_type == "heat")
                    .order_by(MetricSeries.sort_order, MetricSeries.item)
                )
            ).scalars()
        )

    assert [row.metric_key for row in series_rows] == ["power", "voltage", "temperature"]
    for row in series_rows:
        payload = json.loads(row.series_json)
        assert payload["heat_start_time"] == to_timestamp_ms(start_time)
        assert payload["heat_end_time"] == to_timestamp_ms(end_time)
        assert payload["points"]


@pytest.mark.asyncio
async def test_persist_sealed_heat_candidates_rejects_previous_runtime_without_own_n_window(
    reset_test_database,
) -> None:
    definition_id = "def-runtime-window-001"
    baseline_id = f"{definition_id}:001"
    start_time = datetime.now().replace(microsecond=0, second=0)
    end_time = start_time + timedelta(minutes=30)
    context_start_time = start_time - timedelta(minutes=15)
    context_end_time = end_time + timedelta(minutes=15)
    baseline_series_payload = json.dumps(
        {
            "points": [
                {"timestamp": to_timestamp_ms(start_time), "value": 410.0},
                {"timestamp": to_timestamp_ms(end_time), "value": 425.0},
            ]
        },
        ensure_ascii=False,
    )

    async with async_session_maker() as session:
        session.add(
            BaselineDefinition(
                id=definition_id,
                definition_name="运行态完整度校验定义",
                description="验证 previous seal 前必须覆盖自己的 N",
                expected_duration_minutes=30,
                status="active",
                created_by="tester",
                updated_by="tester",
                created_at=start_time,
                updated_at=start_time,
            )
        )
        session.add_all(
            [
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    edc_channel_id="2349-199",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_id,
                    item="002",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    edc_channel_id="2349-128",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        session.add(
            Baseline(
                definition_id=definition_id,
                item="001",
                item_kind="baseline_version",
                name="运行态完整度校验基线",
                description="测试",
                status="published",
                is_default=True,
                source_heat_id="heat-runtime-window-seed",
                selected_start_time=start_time - timedelta(minutes=30),
                selected_end_time=start_time,
                effective_from=start_time - timedelta(hours=1),
                tolerance_percent=15.0,
                created_by="tester",
                updated_by="tester",
                created_at=start_time,
                updated_at=start_time,
                published_at=start_time,
            )
        )
        session.add_all(
            [
                MetricSeries(
                    owner_key=baseline_id,
                    item="001",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 417.5}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
                MetricSeries(
                    owner_key=baseline_id,
                    item="002",
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    source_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="测试设备 / A相电压 / V",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 223.0}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        await session.commit()

    async def fake_metric_curve_loader(
        metrics: list[dict[str, object]],
        loader_start_time: datetime,
        loader_end_time: datetime,
    ) -> dict[str, list[CurvePoint]]:
        curves: dict[str, list[CurvePoint]] = {}
        for metric in metrics:
            metric_id = str(metric.get("id") or "")
            metric_key = str(metric.get("metric_key") or "")
            if metric_key == "power":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=430.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=438.0),
                ]
            elif metric_key == "voltage":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=221.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=226.0),
                ]
        return curves

    prepared = await compile_runtime_candidates(
        [
            {
                "id": "heat-runtime-window-001",
                "heat_no": "HRUNTIME-WINDOW-001",
                "description": "缺少自己 N 的 previous runtime",
                "start_time": start_time,
                "end_time": end_time,
                "context_start_time": context_start_time,
                "context_end_time": context_end_time,
                "baseline_id": baseline_id,
                "record_source": "previous_runtime",
                "cut_reason": "test",
                "cut_status": "normal",
                "status": "normal",
                "created_at": start_time,
            }
        ],
        trigger_source="test",
        metric_curve_loader=fake_metric_curve_loader,
    )

    with pytest.raises(ValueError, match="runtime_metric_series_missing_heat_window"):
        await persist_sealed_heat_candidates(prepared)


@pytest.mark.asyncio
async def test_compile_runtime_candidates_builds_metric_union_and_baseline_views(
    reset_test_database,
) -> None:
    definition_a = "def-runtime-union-001"
    definition_b = "def-runtime-union-002"
    baseline_a_id = f"{definition_a}:001"
    baseline_b_id = f"{definition_b}:001"
    start_time = datetime.now().replace(microsecond=0, second=0)
    end_time = start_time + timedelta(minutes=30)
    context_start_time = start_time - timedelta(minutes=15)
    context_end_time = end_time + timedelta(minutes=15)

    baseline_series_payload = json.dumps(
        {
            "points": [
                {"timestamp": to_timestamp_ms(start_time), "value": 410.0},
                {"timestamp": to_timestamp_ms(end_time), "value": 425.0},
            ]
        },
        ensure_ascii=False,
    )

    async with async_session_maker() as session:
        session.add_all(
            [
                BaselineDefinition(
                    id=definition_a,
                    definition_name="运行态并集定义A",
                    description="power+voltage",
                    expected_duration_minutes=30,
                    status="active",
                    created_by="tester",
                    updated_by="tester",
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinition(
                    id=definition_b,
                    definition_name="运行态并集定义B",
                    description="power+temperature",
                    expected_duration_minutes=30,
                    status="active",
                    created_by="tester",
                    updated_by="tester",
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        session.add_all(
            [
                BaselineDefinitionMetric(
                    definition_id=definition_a,
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    edc_channel_id="2349-199",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_a,
                    item="002",
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    edc_channel_id="2349-128",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_b,
                    item="001",
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    edc_channel_id="2349-199",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
                BaselineDefinitionMetric(
                    definition_id=definition_b,
                    item="002",
                    item_kind="metric_item",
                    metric_key="temperature",
                    metric_name="熔炼温度",
                    unit="℃",
                    color="#E6A23C",
                    sort_order=2,
                    edc_channel_id="2054-128",
                    enabled=True,
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        session.add_all(
            [
                Baseline(
                    definition_id=definition_a,
                    item="001",
                    item_kind="baseline_version",
                    name="运行态并集基线A",
                    description="A",
                    status="published",
                    is_default=True,
                    source_heat_id="heat-runtime-union-seed-a",
                    selected_start_time=start_time - timedelta(minutes=30),
                    selected_end_time=start_time,
                    effective_from=start_time - timedelta(hours=2),
                    tolerance_percent=10.0,
                    created_by="tester",
                    updated_by="tester",
                    created_at=start_time,
                    updated_at=start_time,
                    published_at=start_time,
                ),
                Baseline(
                    definition_id=definition_b,
                    item="001",
                    item_kind="baseline_version",
                    name="运行态并集基线B",
                    description="B",
                    status="published",
                    is_default=False,
                    source_heat_id="heat-runtime-union-seed-b",
                    selected_start_time=start_time - timedelta(minutes=30),
                    selected_end_time=start_time,
                    effective_from=start_time - timedelta(hours=2),
                    tolerance_percent=12.0,
                    created_by="tester",
                    updated_by="tester",
                    created_at=start_time,
                    updated_at=start_time,
                    published_at=start_time,
                ),
            ]
        )
        session.add_all(
            [
                MetricSeries(
                    owner_key=baseline_a_id,
                    item="001",
                    owner_type="baseline",
                    definition_id=definition_a,
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 417.5}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
                MetricSeries(
                    owner_key=baseline_a_id,
                    item="002",
                    owner_type="baseline",
                    definition_id=definition_a,
                    item_kind="metric_item",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                    source_channel_id="2349-128",
                    source_channel_name="A相电压",
                    source_channel_label="测试设备 / A相电压 / V",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 223.0}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
                MetricSeries(
                    owner_key=baseline_b_id,
                    item="001",
                    owner_type="baseline",
                    definition_id=definition_b,
                    item_kind="metric_item",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                    source_channel_id="2349-199",
                    source_channel_name="总有功功率",
                    source_channel_label="测试设备 / 总有功功率 / kW",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 417.5}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
                MetricSeries(
                    owner_key=baseline_b_id,
                    item="002",
                    owner_type="baseline",
                    definition_id=definition_b,
                    item_kind="metric_item",
                    metric_key="temperature",
                    metric_name="熔炼温度",
                    unit="℃",
                    color="#E6A23C",
                    sort_order=2,
                    source_channel_id="2054-128",
                    source_channel_name="热电偶温度采集通道",
                    source_channel_label="测试设备 / 熔炼温度 / ℃",
                    series_json=baseline_series_payload,
                    stat_json=json.dumps({"avg": 1555.0}, ensure_ascii=False),
                    created_at=start_time,
                    updated_at=start_time,
                ),
            ]
        )
        await session.commit()

    explicit_baselines = [
        {
            "id": baseline_a_id,
            "definition_id": definition_a,
            "item": "001",
            "is_default": True,
            "effective_from": start_time - timedelta(hours=2),
            "tolerance_percent": 10.0,
        },
        {
            "id": baseline_b_id,
            "definition_id": definition_b,
            "item": "001",
            "is_default": False,
            "effective_from": start_time - timedelta(hours=2),
            "tolerance_percent": 12.0,
        },
    ]

    async def fake_metric_curve_loader(
        metrics: list[dict[str, object]],
        loader_start_time: datetime,
        loader_end_time: datetime,
    ) -> dict[str, list[CurvePoint]]:
        curves: dict[str, list[CurvePoint]] = {}
        for metric in metrics:
            metric_id = str(metric.get("id") or "")
            metric_key = str(metric.get("metric_key") or "")
            if metric_key == "power":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=430.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=438.0),
                ]
            elif metric_key == "voltage":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=221.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=226.0),
                ]
            elif metric_key == "temperature":
                curves[metric_id] = [
                    CurvePoint(timestamp=to_timestamp_ms(loader_start_time), value=1548.0),
                    CurvePoint(timestamp=to_timestamp_ms(loader_end_time), value=1566.0),
                ]
        return curves

    prepared = await compile_runtime_candidates(
        [
            {
                "id": "heat-runtime-union-001",
                "heat_no": "HRUNTIME-UNION-001",
                "description": "运行态并集视图样本",
                "start_time": start_time,
                "end_time": end_time,
                "context_start_time": context_start_time,
                "context_end_time": context_end_time,
                "record_source": "live_inferred",
                "cut_reason": "test",
                "cut_status": "normal",
                "status": "normal",
                "created_at": start_time,
            }
        ],
        trigger_source="test",
        metric_curve_loader=fake_metric_curve_loader,
        explicit_baselines=explicit_baselines,
        explicit_primary_baseline_id=baseline_a_id,
    )

    assert len(prepared) == 1
    runtime_metric_keys = {
        str(entry.get("metric_key") or "")
        for entry in prepared[0]["runtime_metric_series"]
        if isinstance(entry, dict)
    }
    assert runtime_metric_keys == {"power", "voltage", "temperature"}

    baseline_views = {
        str(view["baseline_id"]): view
        for view in prepared[0]["baseline_views"]
        if isinstance(view, dict)
    }
    assert set(baseline_views) == {baseline_a_id, baseline_b_id}
    assert {
        str(entry.get("metric_key") or "")
        for entry in baseline_views[baseline_a_id]["current_metric_series"]
    } == {"power", "voltage"}
    assert {
        str(entry.get("metric_key") or "")
        for entry in baseline_views[baseline_b_id]["current_metric_series"]
    } == {"power", "temperature"}

    persisted = await persist_sealed_heat_candidates(prepared)
    assert "heat-runtime-union-001" in persisted
    assert len(persisted["heat-runtime-union-001"]["baseline_bindings"]) == 2

    async with async_session_maker() as session:
        heat_metric_rows = list(
            (
                await session.execute(
                    select(MetricSeries)
                    .where(MetricSeries.owner_key == "heat-runtime-union-001")
                    .where(MetricSeries.owner_type == "heat")
                    .order_by(MetricSeries.sort_order, MetricSeries.item)
                )
            ).scalars()
        )
        binding_rows = list(
            (
                await session.execute(
                    select(HeatBaselineBinding)
                    .where(HeatBaselineBinding.heat_id == "heat-runtime-union-001")
                    .order_by(
                        HeatBaselineBinding.baseline_definition_id,
                        HeatBaselineBinding.baseline_item,
                    )
                )
            ).scalars()
        )

    assert [row.metric_key for row in heat_metric_rows] == ["power", "voltage", "temperature"]
    assert len(binding_rows) == 2


@pytest.mark.asyncio
async def test_resume_history_heat_writes_formal_tables(client) -> None:
    heat_id = await _insert_formal_heat_fixture()
    async with async_session_maker() as session:
        heat = await session.get(Heat, heat_id)
        assert heat is not None
        heat.cut_status = "blocked"
        heat.cut_reason = "major_issue_lock"
        heat.status = "pending"
        binding = await session.get(
            HeatBaselineBinding,
            {
                "heat_id": heat_id,
                "baseline_definition_id": "def-history-001",
                "baseline_item": "001",
            },
        )
        assert binding is not None
        binding.abnormal_duration_minutes = 9.0
        await session.commit()

    response = await client.post(
        f"/api/heats/{heat_id}/resume-cutting",
        json={"adjust_subsequent": False, "note": "人工确认恢复"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["cut_status"] == "normal"
    assert payload["status"] == "normal"


@pytest.mark.asyncio
async def test_history_compare_does_not_fallback_when_binding_analysis_not_ready(
    client, monkeypatch
) -> None:
    heat_id = await _insert_formal_heat_fixture()
    async with async_session_maker() as session:
        binding = await session.get(
            HeatBaselineBinding,
            {
                "heat_id": heat_id,
                "baseline_definition_id": "def-history-001",
                "baseline_item": "001",
            },
        )
        assert binding is not None
        binding.analysis_status = "unsupported"
        binding.analysis_reason = "metric_scale_invalid"
        binding.analysis_message = "该黄金基线包含当前模型不适用的低波动或离散台阶型指标，未计算偏离度"
        binding.deviation_score = None
        binding.avg_deviation_score = None
        binding.analysis_details_json = None
        await session.commit()

    async def fail_channel_curves(**_kwargs):
        raise AssertionError("历史 compare 不应请求实时通道曲线")

    async def fail_heat_curves(_item):
        raise AssertionError("历史 compare 不应请求实时炉次曲线")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_channel_curves)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_heat_curves)

    response = await client.get(f"/api/heats/{heat_id}/compare")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deviation_score"] is None
    assert payload["avg_deviation_score"] is None
    assert payload["deviation_ranges"] == []
    assert payload["analysis_status"] == "unsupported"
    assert payload["analysis_reason"] == "metric_scale_invalid"
    assert payload["analysis_message"] == "该黄金基线包含当前模型不适用的低波动或离散台阶型指标，未计算偏离度"
    assert payload["baselines"][0]["analysis_status"] == "unsupported"
    assert payload["baselines"][0]["analysis_reason"] == "metric_scale_invalid"
    assert payload["baselines"][0]["deviation_score"] is None


def test_future_published_baseline_does_not_fallback_to_past_heat() -> None:
    future_time = datetime.now() + timedelta(hours=1)
    baseline = {
        "id": "future-baseline",
        "status": "published",
        "effective_from": future_time,
    }

    from src.api.baselines import _BASELINE_STORE

    _BASELINE_STORE.clear()
    _BASELINE_STORE["future-baseline"] = baseline

    assert _resolve_baseline_version_for_time(datetime.now()) is None


def _build_runtime_live_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    cursor = 0
    for _ in range(4):
        for offset in range(8):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=40.0))
        cursor += 8
        for offset in range(28):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=128.0))
        cursor += 28
    return points


@pytest.mark.asyncio
async def test_refresh_runtime_only_keeps_n_minus_1_and_n_in_cache(client, monkeypatch) -> None:
    definition_id = "def-runtime-001"
    now = datetime.now().replace(second=0, microsecond=0)
    async with async_session_maker() as session:
        session.add(
            BaselineDefinition(
                id=definition_id,
                definition_name="运行态定义",
                description="运行态测试",
                expected_duration_minutes=30,
                status="active",
                created_by="tester",
                updated_by="tester",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            BaselineDefinitionMetric(
                definition_id=definition_id,
                item="001",
                item_kind="metric_item",
                metric_key="power",
                metric_name="总有功功率",
                unit="kW",
                color="#409EFF",
                sort_order=1,
                edc_channel_id="2349-199",
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Baseline(
                definition_id=definition_id,
                item="001",
                item_kind="baseline_version",
                name="运行态基线",
                description="测试",
                status="published",
                is_default=True,
                source_heat_id="heat-runtime-seed",
                selected_start_time=now - timedelta(minutes=30),
                selected_end_time=now,
                effective_from=now - timedelta(hours=3),
                tolerance_percent=15.0,
                created_by="tester",
                updated_by="tester",
                created_at=now,
                updated_at=now,
                published_at=now,
            )
        )
        await session.commit()

    live_points = _build_runtime_live_points(now - timedelta(minutes=144))
    context = _build_live_heat_context(
        channel={
            "id": "2349-199",
            "suid": "2349",
            "cuid": "199",
            "device_name": "测试设备",
            "channel_name": "总有功功率",
            "unit": "kW",
        },
        baseline_id=f"{definition_id}:001",
        expected_duration_minutes=30,
    )

    async def fake_load_live_heat_inference_power_points(_channel):
        return live_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr("src.api.heats._resolve_live_heat_inference_context", lambda: context)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    _HEAT_STORE.clear()
    _ACTIVE_HEAT_RUNTIME.clear()
    _PREVIOUS_HEAT_RUNTIME.clear()

    result = await refresh_heat_runtime_state(reason="test")
    assert result["snapshot_status"] in {"ready", "refreshing_history"}
    assert len(_ACTIVE_HEAT_RUNTIME) == 1
    assert len(_PREVIOUS_HEAT_RUNTIME) == 1
    assert _HEAT_STORE == {}

    list_resp = await client.get("/api/heats", params={"page_size": 20})
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    runtime_items = [
        item for item in items if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    history_items = [item for item in items if item["record_source"] == "sealed_history"]
    live_history_items = [item for item in history_items if item["id"].startswith("live-heat-")]
    assert len(runtime_items) == 2
    assert live_history_items == []
    assert any(item["id"] == "heat-001" for item in history_items)
