"""炉次 replay API 测试。"""

import asyncio
from datetime import datetime

import pytest

from src.api.heats import (
    _ACTIVE_HEAT_RUNTIME,
    _PREVIOUS_HEAT_RUNTIME,
    refresh_heat_runtime_state,
)
from src.api.settings import _SETTINGS_STORE
from src.schemas.common import CurvePoint


def _build_live_power_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = int(
                (start.replace(second=0, microsecond=0)).timestamp() * 1000
            ) + (offset_minutes + index) * 60_000
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
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "anchor_time": int(datetime(2026, 3, 19, 8, 0).timestamp() * 1000),
            "end_time": int(datetime(2026, 3, 19, 9, 40).timestamp() * 1000),
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
    live_history_items = [
        item
        for item in list_response.json()["items"]
        if item["record_source"] == "sealed_history" and item["id"].startswith("live-heat-")
    ]
    assert len(live_history_items) >= 2


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
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    create_response = await client.post(
        "/api/heats/replay-jobs",
        json={
            "job_kind": "replay_batch",
            "anchor_time": int(datetime(2026, 3, 19, 8, 0).timestamp() * 1000),
            "end_time": int(datetime(2026, 3, 19, 20, 0).timestamp() * 1000),
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
async def test_replay_job_rebuilds_head_runtime_from_previous_anchor(client, monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    fake_now = datetime(2026, 3, 19, 9, 20)
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel, start_time=None, end_time=None):
        if start_time is None or end_time is None:
            return live_points
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
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
            "anchor_time": int(datetime(2026, 3, 19, 8, 0).timestamp() * 1000),
            "end_time": int(datetime(2026, 3, 19, 9, 20).timestamp() * 1000),
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

    assert history_items
    assert len(runtime_items) == 1
    assert runtime_items[0]["record_source"] == "active_runtime"
