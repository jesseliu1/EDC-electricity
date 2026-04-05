"""API 错误分支与边界场景测试。"""

from datetime import datetime

import pytest

PRIMARY_BASELINE_ID = "def-001:001"
SECONDARY_BASELINE_ID = "def-002:001"
BASELINE_SELECTION_START = int(datetime(2026, 3, 12, 10, 0, 0).timestamp() * 1000)
BASELINE_SELECTION_END = int(datetime(2026, 3, 12, 10, 45, 0).timestamp() * 1000)


@pytest.mark.asyncio
async def test_dashboard_invalid_duration_returns_422(client) -> None:
    response = await client.get("/api/dashboard/realtime", params={"duration": "2h"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_baseline_definition_invalid_state_transitions_and_missing_metric(client) -> None:
    enable_active_resp = await client.post("/api/baseline-definitions/def-001/enable")
    assert enable_active_resp.status_code == 400

    disable_resp = await client.post("/api/baseline-definitions/def-001/disable")
    assert disable_resp.status_code == 200

    disable_again_resp = await client.post("/api/baseline-definitions/def-001/disable")
    assert disable_again_resp.status_code == 400

    missing_metric_update = await client.patch(
        "/api/baseline-definitions/def-001/metrics/not-exists",
        json={"name": "不存在"},
    )
    assert missing_metric_update.status_code == 404

    missing_metric_delete = await client.delete(
        "/api/baseline-definitions/def-001/metrics/not-exists"
    )
    assert missing_metric_delete.status_code == 404


@pytest.mark.asyncio
async def test_baseline_invalid_state_transitions_and_validation(client) -> None:
    publish_published_resp = await client.post(f"/api/baselines/{PRIMARY_BASELINE_ID}/publish")
    assert publish_published_resp.status_code == 400

    disable_draft_resp = await client.post(f"/api/baselines/{SECONDARY_BASELINE_ID}/disable")
    assert disable_draft_resp.status_code == 400

    invalid_definition_resp = await client.post(
        "/api/baselines",
        json={
            "name": "bad definition",
            "definition_id": "def-not-exists",
            "source_heat_id": "heat-001",
            "selected_start_time": BASELINE_SELECTION_START,
            "selected_end_time": BASELINE_SELECTION_END,
            "tolerance_percent": 10,
        },
    )
    assert invalid_definition_resp.status_code == 400

    invalid_tolerance_resp = await client.post(
        "/api/baselines",
        json={
            "name": "bad tolerance",
            "definition_id": "def-001",
            "source_heat_id": "heat-001",
            "selected_start_time": BASELINE_SELECTION_START,
            "selected_end_time": BASELINE_SELECTION_END,
            "tolerance_percent": 120,
        },
    )
    assert invalid_tolerance_resp.status_code == 422


@pytest.mark.asyncio
async def test_task_invalid_state_transitions_and_validation(client) -> None:
    complete_cancelled_resp = await client.post(
        "/api/tasks/task-004/complete",
        params={"showtime": "true"},
        json={
            "cause_analysis": "原因",
            "improvement": "改善",
            "prevention": "预防",
        },
    )
    assert complete_cancelled_resp.status_code == 400

    cancel_completed_resp = await client.post(
        "/api/tasks/task-003/cancel",
        params={"showtime": "true"},
    )
    assert cancel_completed_resp.status_code == 400

    update_completed_resp = await client.patch(
        "/api/tasks/task-003",
        params={"showtime": "true"},
        json={"cause_analysis": "不应更新"},
    )
    assert update_completed_resp.status_code == 400

    complete_empty_text_resp = await client.post(
        "/api/tasks/task-001/complete",
        params={"showtime": "true"},
        json={"cause_analysis": "", "improvement": "改善", "prevention": "预防"},
    )
    assert complete_empty_text_resp.status_code == 422


@pytest.mark.asyncio
async def test_settings_invalid_payloads(client) -> None:
    invalid_tolerance_resp = await client.put(
        "/api/settings/tolerance",
        json={"tolerance_percent": -1},
    )
    assert invalid_tolerance_resp.status_code == 422

    invalid_report_hour_resp = await client.put(
        "/api/settings/report",
        json={"generation_hour": 25},
    )
    assert invalid_report_hour_resp.status_code == 422

    invalid_cutting_resp = await client.put(
        "/api/settings/cutting",
        json={
            "time_tolerance_percent": 10,
            "major_issue_duration_minutes": 0,
            "work_start_time": "08:00",
            "work_end_time": "18:00",
            "break_periods": [],
        },
    )
    assert invalid_cutting_resp.status_code == 422

    invalid_scope_resp = await client.put(
        "/api/settings/baseline-length-scope",
        json={"scope_mode": "invalid"},
    )
    assert invalid_scope_resp.status_code == 200
    assert invalid_scope_resp.json()["success"] is False


@pytest.mark.asyncio
async def test_heat_missing_and_invalid_resume_paths(client) -> None:
    missing_timeline_resp = await client.get("/api/heats/not-exists/cutting-timeline")
    assert missing_timeline_resp.status_code == 404

    invalid_status_resp = await client.get("/api/heats", params={"status": "bad-status"})
    assert invalid_status_resp.status_code == 422
