"""炉次 replay API 测试。"""

import asyncio
import json
from datetime import datetime

import pytest
from sqlalchemy import select, update

from src.api.heats import (
    _ACTIVE_HEAT_RUNTIME,
    _HEAT_STREAM_PROCESSOR_STATE,
    _PREVIOUS_HEAT_RUNTIME,
    refresh_heat_runtime_state,
)
from src.api.settings import _SETTINGS_STORE
from src.database import async_session_maker
from src.models import (
    Baseline,
    BaselineDefinition,
    BaselineDefinitionMetric,
    HeatBaselineBinding,
    MetricSeries,
)
from src.schemas.common import CurvePoint
from src.services import decode_baseline_id, encode_baseline_id
from src.time_utils import to_timestamp_ms


def _build_live_power_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    normalized_start = start.replace(second=0, microsecond=0)

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = to_timestamp_ms(normalized_start) + (offset_minutes + index) * 60_000
            points.append(CurvePoint(timestamp=timestamp, value=value))

    append_block(0, 10, 42.0)
    append_block(10, 30, 124.0)
    append_block(40, 12, 46.0)
    append_block(52, 28, 129.0)
    append_block(80, 10, 38.0)
    return points


def _build_continuing_live_power_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    normalized_start = start.replace(second=0, microsecond=0)

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = to_timestamp_ms(normalized_start) + (offset_minutes + index) * 60_000
            points.append(CurvePoint(timestamp=timestamp, value=value))

    append_block(0, 8, 42.0)
    append_block(8, 24, 124.0)
    append_block(32, 10, 46.0)
    append_block(42, 44, 129.0)
    append_block(86, 8, 38.0)
    return points


def _build_fixed_interval_regression_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    normalized_start = start.replace(second=0, microsecond=0)

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = to_timestamp_ms(normalized_start) + (offset_minutes + index) * 60_000
            points.append(CurvePoint(timestamp=timestamp, value=value))

    append_block(0, 33, 124.0)
    append_block(33, 4, 18.0)
    append_block(37, 26, 127.0)
    append_block(63, 4, 18.0)
    append_block(67, 25, 126.0)
    append_block(92, 4, 18.0)
    append_block(96, 27, 129.0)
    append_block(123, 3, 18.0)
    return points


def _build_test_live_context() -> dict[str, object]:
    import src.api.heats as heats_module

    return heats_module._build_live_heat_context(
        channel={
            "id": "2349-199",
            "suid": "2349",
            "cuid": "199",
            "device_name": "测试设备",
            "channel_name": "功率",
            "unit": "kW",
        },
        baseline_id="def-001:001",
        expected_duration_minutes=30,
    )


async def _fake_runtime_metric_curves(metrics, start_time, end_time):
    payload = {}
    for metric in metrics:
        metric_id = str(metric.get("id") or "")
        metric_key = str(metric.get("metric_key") or "")
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        if metric_key == "power":
            payload[metric_id] = [
                CurvePoint(timestamp=start_ms, value=420.0),
                CurvePoint(timestamp=end_ms, value=438.0),
            ]
        elif metric_key == "voltage":
            payload[metric_id] = [
                CurvePoint(timestamp=start_ms, value=220.0),
                CurvePoint(timestamp=end_ms, value=226.0),
            ]
        elif metric_key == "temperature":
            payload[metric_id] = [
                CurvePoint(timestamp=start_ms, value=1540.0),
                CurvePoint(timestamp=end_ms, value=1566.0),
            ]
    return payload


async def _wait_for_job(client, job_id: str, *, terminal_statuses: set[str]) -> dict:
    last_payload: dict | None = None
    for _ in range(50):
        response = await client.get(f"/api/heats/replay-jobs/{job_id}")
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] in terminal_statuses:
            return last_payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"job {job_id} did not reach terminal status, last={last_payload}")


async def _seed_same_duration_replay_baseline() -> str:
    now = datetime(2026, 3, 19, 9, 0)
    baseline_id = encode_baseline_id("def-003", "001")
    async with async_session_maker() as session:
        session.add(
            BaselineDefinition(
                id="def-003",
                definition_name="同时长温度视角",
                description="用于 replay 多 definition 同时长回归",
                expected_duration_minutes=45,
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
                    definition_id="def-003",
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
                    definition_id="def-003",
                    item="002",
                    item_kind="metric_item",
                    metric_key="temperature",
                    metric_name="炉温",
                    unit="℃",
                    color="#ef4444",
                    sort_order=2,
                    edc_channel_id="2054-128",
                    source_channel_name="热电偶温度采集通道",
                    source_channel_label="测试温度 A / 热电偶温度采集通道 / ℃",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add(
            Baseline(
                definition_id="def-003",
                item="001",
                item_kind="baseline_version",
                name="同温度基线",
                description="replay 同时长多 definition 样本",
                status="published",
                is_default=False,
                source_heat_id="heat-001",
                selected_start_time=datetime(2026, 3, 19, 8, 0),
                selected_end_time=datetime(2026, 3, 19, 8, 45),
                effective_from=datetime(2026, 3, 19, 8, 50),
                tolerance_percent=10.0,
                created_by="tester",
                updated_by="tester",
                created_at=now,
                updated_at=now,
                published_at=now,
            )
        )
        session.add_all(
            [
                MetricSeries(
                    owner_key=baseline_id,
                    item="001",
                    owner_type="baseline",
                    definition_id="def-003",
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
                                {"timestamp": int(datetime(2026, 3, 19, 8, 0).timestamp() * 1000), "value": 408.0},
                                {"timestamp": int(datetime(2026, 3, 19, 8, 45).timestamp() * 1000), "value": 419.0},
                            ]
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    stat_json=json.dumps({"avg": 413.5}, ensure_ascii=False, separators=(",", ":")),
                    created_at=now,
                    updated_at=now,
                ),
                MetricSeries(
                    owner_key=baseline_id,
                    item="002",
                    owner_type="baseline",
                    definition_id="def-003",
                    item_kind="metric_item",
                    metric_key="temperature",
                    metric_name="炉温",
                    unit="℃",
                    color="#ef4444",
                    sort_order=2,
                    source_channel_id="2054-128",
                    source_channel_name="热电偶温度采集通道",
                    source_channel_label="测试温度 A / 热电偶温度采集通道 / ℃",
                    series_json=json.dumps(
                        {
                            "points": [
                                {"timestamp": int(datetime(2026, 3, 19, 8, 0).timestamp() * 1000), "value": 1542.0},
                                {"timestamp": int(datetime(2026, 3, 19, 8, 45).timestamp() * 1000), "value": 1568.0},
                            ]
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    stat_json=json.dumps({"avg": 1555.0}, ensure_ascii=False, separators=(",", ":")),
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()
    return baseline_id


@pytest.mark.asyncio
async def test_create_replay_job_runs_to_completion_and_replaces_range(client, monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        return live_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "end_time": to_timestamp_ms(datetime(2026, 3, 19, 9, 40)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    finished = await _wait_for_job(client, job_id, terminal_statuses={"completed"})
    assert finished["generated_heat_count"] >= 2
    assert finished["processed_chunk_count"] >= 1

    list_response = await client.get("/api/heats", params={"page_size": 50})
    assert list_response.status_code == 200
    assert list_response.json()["snapshot_status"] != "error"
    runtime_items = [
        item
        for item in list_response.json()["items"]
        if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    live_history_items = [
        item
        for item in list_response.json()["items"]
        if item["record_source"] == "sealed_history" and item["id"].startswith("live-heat-")
    ]
    assert len(live_history_items) >= 1
    assert not runtime_items
    assert _HEAT_STREAM_PROCESSOR_STATE.get("state", {}).get("bootstrapped") is True


@pytest.mark.asyncio
async def test_replay_job_fixed_interval_uses_anchor_timeline_boundaries(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    _SETTINGS_STORE["cutting_mode"]["value"] = "fixed_interval"
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = "30"
    _SETTINGS_STORE["time_tolerance_percent"]["value"] = "10.0"
    replay_points = _build_fixed_interval_regression_points(datetime(2026, 4, 17, 12, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return replay_points
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        return [point for point in replay_points if start_ms <= int(point.timestamp) <= end_ms]

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 4, 17, 12, 0)),
            "end_time": to_timestamp_ms(datetime(2026, 4, 17, 14, 5)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    finished = await _wait_for_job(client, job_id, terminal_statuses={"completed"})
    assert finished["generated_heat_count"] >= 4

    list_response = await client.get("/api/heats", params={"page_size": 50})
    assert list_response.status_code == 200
    payload = list_response.json()
    sealed_history_items = [
        item
        for item in payload["items"]
        if item["record_source"] == "sealed_history" and item["id"].startswith("live-heat-")
    ]
    sealed_history_items.sort(key=lambda item: item["start_time"])

    assert len(sealed_history_items) >= 2
    assert sealed_history_items[0]["start_time"] == to_timestamp_ms(datetime(2026, 4, 17, 12, 0))
    assert sealed_history_items[0]["end_time"] == to_timestamp_ms(datetime(2026, 4, 17, 12, 32))
    assert sealed_history_items[1]["start_time"] == to_timestamp_ms(datetime(2026, 4, 17, 12, 33))
    assert sealed_history_items[1]["end_time"] == to_timestamp_ms(datetime(2026, 4, 17, 13, 2))


@pytest.mark.asyncio
async def test_cancel_replay_job_marks_job_cancelled(client, monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        await asyncio.sleep(0.2)
        return live_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "end_time": to_timestamp_ms(datetime(2026, 3, 19, 20, 0)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    cancel_response = await client.post(f"/api/heats/replay-jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200

    finished = await _wait_for_job(client, job_id, terminal_statuses={"cancelled"})
    assert finished["status"] == "cancelled"


@pytest.mark.asyncio
async def test_replay_job_replaces_existing_runtime_with_replay_seed(client, monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    fake_now = datetime(2026, 3, 19, 9, 20)
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return live_points
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        return [
            point
            for point in live_points
            if start_ms <= int(point.timestamp) <= end_ms
        ]

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)
    monkeypatch.setattr("src.api.heats.utc_now", lambda: fake_now)
    monkeypatch.setattr("src.services.live_heat_runtime_service.utc_now", lambda: fake_now)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()

    await refresh_heat_runtime_state(reason="bootstrap")
    assert len(_ACTIVE_HEAT_RUNTIME) == 1
    assert len(_PREVIOUS_HEAT_RUNTIME) == 1

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "end_time": to_timestamp_ms(datetime(2026, 3, 19, 9, 20)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    finished = await _wait_for_job(client, job_id, terminal_statuses={"completed"})
    assert finished["status"] == "completed"

    rebuilt_active = None
    for _ in range(20):
        candidate = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
        if (
            candidate is not None
            and candidate.get("processing_meta", {}).get("trigger_source") == "replay_head_rebuild"
        ):
            rebuilt_active = candidate
            break
        await asyncio.sleep(0.05)

    assert rebuilt_active is not None
    assert rebuilt_active["processing_meta"]["trigger_source"] == "replay_head_rebuild"

    list_response = await client.get("/api/heats", params={"page_size": 50})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    runtime_items = [
        item
        for item in items
        if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    history_items = [
        item
        for item in items
        if item["record_source"] == "sealed_history" and item["id"].startswith("live-heat-")
    ]

    assert not history_items
    assert len(runtime_items) == 2
    assert {item["record_source"] for item in runtime_items} == {"active_runtime", "previous_runtime"}


@pytest.mark.asyncio
async def test_replay_job_builds_runtime_seed_without_existing_runtime_or_live_recut(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    fake_now = datetime(2026, 3, 19, 9, 20)
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return live_points
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        return [
            point
            for point in live_points
            if start_ms <= int(point.timestamp) <= end_ms
        ]

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr(
        "src.api.heats.refresh_live_heat_segments",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("replay should not recut live runtime after replace")
        ),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)
    monkeypatch.setattr("src.api.heats.utc_now", lambda: fake_now)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "end_time": to_timestamp_ms(datetime(2026, 3, 19, 9, 20)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    finished = await _wait_for_job(client, job_id, terminal_statuses={"completed"})
    assert finished["status"] == "completed"

    rebuilt_active = None
    rebuilt_previous = None
    for _ in range(20):
        rebuilt_active = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
        rebuilt_previous = next(iter(_PREVIOUS_HEAT_RUNTIME.values()), None)
        if (
            rebuilt_active is not None
            and rebuilt_previous is not None
            and rebuilt_active.get("processing_meta", {}).get("trigger_source")
            == "replay_head_rebuild"
        ):
            break
        await asyncio.sleep(0.05)

    assert rebuilt_active is not None
    assert rebuilt_previous is not None
    assert rebuilt_active["processing_meta"]["trigger_source"] == "replay_head_rebuild"
    assert rebuilt_previous["record_source"] == "previous_runtime"

    list_response = await client.get("/api/heats", params={"page_size": 50})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    runtime_items = [
        item
        for item in items
        if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    history_items = [
        item
        for item in items
        if item["record_source"] == "sealed_history" and item["id"].startswith("live-heat-")
    ]

    assert not history_items
    assert len(runtime_items) == 2
    assert {item["record_source"] for item in runtime_items} == {"active_runtime", "previous_runtime"}
    assert _HEAT_STREAM_PROCESSOR_STATE.get("state", {}).get("bootstrapped") is True


@pytest.mark.asyncio
async def test_replay_job_rebuilds_processor_snapshot_for_live_continuation(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    _SETTINGS_STORE["cutting_mode"]["value"] = "signal_inference"
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = ""
    replay_end_time = datetime(2026, 3, 19, 9, 5)
    refresh_now = datetime(2026, 3, 19, 9, 18)
    live_points = _build_continuing_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return live_points
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        return [point for point in live_points if start_ms <= int(point.timestamp) <= end_ms]

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_STREAM_PROCESSOR_STATE.clear()

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "end_time": to_timestamp_ms(replay_end_time),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    finished = await _wait_for_job(client, create_response.json()["id"], terminal_statuses={"completed"})
    assert finished["status"] == "completed"

    active_before_refresh = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
    assert active_before_refresh is not None
    assert _HEAT_STREAM_PROCESSOR_STATE.get("state", {}).get("bootstrapped") is True

    monkeypatch.setattr("src.api.heats.utc_now", lambda: refresh_now)
    monkeypatch.setattr("src.services.live_heat_runtime_service.utc_now", lambda: refresh_now)

    refresh_meta = await refresh_heat_runtime_state(reason="post_replay_continuation")
    assert refresh_meta["refresh_error"] is None
    assert refresh_meta["snapshot_status"] != "error"

    active_after_refresh = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
    assert active_after_refresh is not None
    assert active_after_refresh["start_time"] == active_before_refresh["start_time"]
    assert active_after_refresh["last_point_at"] > active_before_refresh["last_point_at"]
    assert _HEAT_STREAM_PROCESSOR_STATE.get("state", {}).get("bootstrapped") is True


@pytest.mark.asyncio
async def test_replay_job_rebuilds_fixed_interval_processor_snapshot_for_live_continuation(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    _SETTINGS_STORE["cutting_mode"]["value"] = "fixed_interval"
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = "30"
    _SETTINGS_STORE["time_tolerance_percent"]["value"] = "10.0"
    replay_end_time = datetime(2026, 4, 17, 13, 4)
    refresh_now = datetime(2026, 4, 17, 13, 18)
    live_points = _build_fixed_interval_regression_points(datetime(2026, 4, 17, 12, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return live_points
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        return [point for point in live_points if start_ms <= int(point.timestamp) <= end_ms]

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_STREAM_PROCESSOR_STATE.clear()

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 4, 17, 12, 0)),
            "end_time": to_timestamp_ms(replay_end_time),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    finished = await _wait_for_job(client, create_response.json()["id"], terminal_statuses={"completed"})
    assert finished["status"] == "completed"

    active_before_refresh = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
    assert active_before_refresh is not None
    assert _HEAT_STREAM_PROCESSOR_STATE.get("state", {}).get("bootstrapped") is True
    assert _HEAT_STREAM_PROCESSOR_STATE.get("config", {}).get("anchor_timestamp_ms") == to_timestamp_ms(
        datetime(2026, 4, 17, 12, 0)
    )

    monkeypatch.setattr("src.api.heats.utc_now", lambda: refresh_now)
    monkeypatch.setattr("src.services.live_heat_runtime_service.utc_now", lambda: refresh_now)

    refresh_meta = await refresh_heat_runtime_state(reason="post_replay_continuation")
    assert refresh_meta["refresh_error"] is None
    assert refresh_meta["snapshot_status"] != "error"

    active_after_refresh = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
    previous_after_refresh = next(iter(_PREVIOUS_HEAT_RUNTIME.values()), None)
    assert active_after_refresh is not None
    assert previous_after_refresh is not None
    assert previous_after_refresh["start_time"] == active_before_refresh["start_time"]
    assert active_after_refresh["start_time"] >= active_before_refresh["start_time"]
    assert active_after_refresh["last_point_at"] > active_before_refresh["last_point_at"]
    assert _HEAT_STREAM_PROCESSOR_STATE.get("state", {}).get("bootstrapped") is True
    assert _HEAT_STREAM_PROCESSOR_STATE.get("config", {}).get("anchor_timestamp_ms") == to_timestamp_ms(
        datetime(2026, 4, 17, 12, 0)
    )


@pytest.mark.asyncio
async def test_replay_job_ignores_effective_from_for_explicit_selected_baselines(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    fake_now = datetime(2026, 3, 19, 9, 40, 37)
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return live_points
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        return [point for point in live_points if start_ms <= int(point.timestamp) <= end_ms]

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)
    monkeypatch.setattr("src.api.heats.utc_now", lambda: fake_now)

    definition_id, item = decode_baseline_id("def-001:001")
    async with async_session_maker() as session:
        await session.execute(
            update(Baseline)
            .where(Baseline.definition_id == definition_id)
            .where(Baseline.item == item)
            .values(effective_from=datetime(2026, 3, 20, 8, 0))
        )
        await session.commit()

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["end_time"] == to_timestamp_ms(fake_now)

    finished = await _wait_for_job(client, create_response.json()["id"], terminal_statuses={"completed"})
    assert finished["status"] == "completed"


@pytest.mark.asyncio
async def test_replay_job_rejects_unpublished_selected_baseline(client) -> None:
    definition_id, item = decode_baseline_id("def-001:001")
    async with async_session_maker() as session:
        await session.execute(
            update(Baseline)
            .where(Baseline.definition_id == definition_id)
            .where(Baseline.item == item)
            .values(status="draft")
        )
        await session.commit()

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 409
    assert create_response.json()["detail"] == "replay_selected_baseline_not_published"


@pytest.mark.asyncio
async def test_replay_job_rejects_selected_baselines_with_duration_mismatch(client) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(Baseline)
            .where(Baseline.definition_id == "def-002")
            .where(Baseline.item == "001")
            .values(status="published", published_at=datetime(2026, 3, 12, 10, 45))
        )
        await session.commit()

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001", "def-002:001"],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 409
    assert create_response.json()["detail"] == "replay_selected_baselines_duration_mismatch"


@pytest.mark.asyncio
async def test_replay_job_accepts_multi_definition_selected_baselines_with_same_duration(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return live_points
        start_ms = to_timestamp_ms(start_time)
        end_ms = to_timestamp_ms(end_time)
        return [point for point in live_points if start_ms <= int(point.timestamp) <= end_ms]

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_replay_inference_channel",
        lambda: dict(_build_test_live_context()["channel"]),
    )
    monkeypatch.setattr("src.api.heats._load_runtime_metric_curves", _fake_runtime_metric_curves)
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    same_duration_baseline_id = await _seed_same_duration_replay_baseline()

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "start_time": to_timestamp_ms(datetime(2026, 3, 19, 8, 0)),
            "end_time": to_timestamp_ms(datetime(2026, 3, 19, 9, 40)),
            "primary_baseline_id": "def-001:001",
            "baseline_ids": ["def-001:001", same_duration_baseline_id],
            "force_replace": True,
        },
    )
    assert create_response.status_code == 201

    finished = await _wait_for_job(client, create_response.json()["id"], terminal_statuses={"completed"})
    assert finished["status"] == "completed"

    async with async_session_maker() as session:
        replay_binding_rows = list(
            (
                await session.execute(
                    select(HeatBaselineBinding).where(
                        HeatBaselineBinding.baseline_definition_id == "def-003"
                    )
                )
            ).scalars()
        )
        replay_heat_temperature_rows = list(
            (
                await session.execute(
                    select(MetricSeries).where(
                        MetricSeries.owner_type == "heat",
                        MetricSeries.metric_key == "temperature",
                        MetricSeries.owner_key != "heat-001",
                    )
                )
            ).scalars()
        )

    assert replay_binding_rows
    assert replay_heat_temperature_rows
