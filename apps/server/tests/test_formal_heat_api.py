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
from src.services import prepare_runtime_candidates_for_persist, persist_sealed_heat_candidates
from src.time_utils import from_timestamp_ms, to_timestamp_ms


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
                deviation_percent=12.3,
                avg_deviation_percent=8.1,
                deviation_details_json=json.dumps(
                    {
                        "abnormal_ranges": [
                            {
                                "start": int((now - timedelta(minutes=12)).timestamp() * 1000),
                                "end": int((now - timedelta(minutes=9)).timestamp() * 1000),
                                "deviation": 12.3,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                time_offset_percent=4.2,
                mismatch_duration_minutes=3.0,
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
                {"timestamp": int((now - timedelta(minutes=25)).timestamp() * 1000), "value": 420.0},
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
                                {"timestamp": int((now - timedelta(minutes=25)).timestamp() * 1000), "value": 410.0},
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
                                {"timestamp": int((now - timedelta(minutes=25)).timestamp() * 1000), "value": 220.0},
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
    assert item["deviation_percent"] == pytest.approx(12.3)


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
    assert len(payload["heat"]["power_curve"]) == 2
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
    assert response.status_code == 200
    payload = response.json()
    assert payload["heat"]["current_curve_source"] == "formal_db"
    assert payload["heat"]["voltage_curve"] == []
    voltage_metric = next(
        item
        for item in payload["baselines"][0]["metric_curves"]
        if item["metric_key"] == "voltage"
    )
    assert voltage_metric["current_curve"] == []


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
        binding.time_offset_percent = 16.0
        binding.mismatch_duration_minutes = 9.0
        await session.commit()

    response = await client.post(
        f"/api/heats/{heat_id}/resume-cutting",
        json={"adjust_subsequent": False, "note": "人工确认恢复"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["cut_status"] == "normal"
    assert payload["status"] == "normal"
    assert payload["time_offset_percent"] == pytest.approx(8.0)


@pytest.mark.asyncio
async def test_analyze_history_heat_uses_formal_tables_only(client, monkeypatch) -> None:
    heat_id = await _insert_formal_heat_fixture()

    async def fail_channel_curves(**_kwargs):
        raise AssertionError("历史 analyze 不应请求实时通道曲线")

    async def fail_heat_curves(_item):
        raise AssertionError("历史 analyze 不应请求实时炉次曲线")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_channel_curves)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_heat_curves)

    response = await client.post(f"/api/heats/{heat_id}/analyze", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline_id"] == "def-history-001:001"
    assert payload["max_deviation"] >= 0

    detail = await client.get(f"/api/heats/{heat_id}")
    assert detail.status_code == 200
    assert detail.json()["deviation_percent"] == pytest.approx(payload["max_deviation"])


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
    runtime_items = [item for item in items if item["record_source"] in {"active_runtime", "previous_runtime"}]
    history_items = [item for item in items if item["record_source"] == "sealed_history"]
    live_history_items = [item for item in history_items if item["id"].startswith("live-heat-")]
    assert len(runtime_items) == 2
    assert live_history_items == []
    assert any(item["id"] == "heat-001" for item in history_items)
