"""炉次 replay API 测试。"""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import update

from src.api.heats import (
    _ACTIVE_HEAT_RUNTIME,
    _PREVIOUS_HEAT_RUNTIME,
    refresh_heat_runtime_state,
)
from src.api.settings import _SETTINGS_STORE
from src.database import async_session_maker
from src.models import Baseline
from src.schemas.common import CurvePoint
from src.services import decode_baseline_id
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
async def test_replay_job_rejects_cross_definition_selected_baselines(client) -> None:
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
    assert create_response.json()["detail"] == "replay_selected_baselines_cross_definition"
