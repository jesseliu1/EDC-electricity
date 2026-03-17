"""基线、基线定义与仪表盘 API 测试。"""

import pytest


@pytest.mark.asyncio
async def test_dashboard_endpoints(client) -> None:
    stats_resp = await client.get("/api/dashboard/stats")
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert stats_data["today_heats"] >= 0
    assert 0 <= stats_data["normal_rate"] <= 100

    realtime_resp = await client.get("/api/dashboard/realtime", params={"duration": "1h"})
    assert realtime_resp.status_code == 200
    realtime_data = realtime_resp.json()
    assert len(realtime_data["power"]) == len(realtime_data["baseline_power"])
    assert len(realtime_data["voltage"]) == len(realtime_data["baseline_voltage"])
    assert realtime_data["baseline_name"] == "标准基线 v2.1"
    assert "总有功功率" in realtime_data["power_source_label"]
    assert "A相电压" in realtime_data["voltage_source_label"]

    recent_resp = await client.get("/api/dashboard/recent-heats", params={"limit": 5})
    assert recent_resp.status_code == 200
    recent_data = recent_resp.json()
    assert len(recent_data["items"]) == 5


@pytest.mark.asyncio
async def test_settings_host_channels_endpoint(client) -> None:
    host_channels_resp = await client.get("/api/settings/host-channels")
    assert host_channels_resp.status_code == 200
    payload = host_channels_resp.json()
    assert payload["total"] >= 6
    assert any(item["channel_name"] == "总有功功率" for item in payload["items"])
    assert any(item["channel_name"] == "热电偶温度采集通道" for item in payload["items"])


@pytest.mark.asyncio
async def test_baseline_definition_crud_and_metric_workflow(client) -> None:
    list_resp = await client.get("/api/baseline-definitions")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 2

    create_resp = await client.post(
        "/api/baseline-definitions",
        json={
            "definition_name": "测试定义",
            "description": "自动化回归定义",
            "expected_duration_minutes": 40,
            "metrics": [
                {"name": "氧含量", "unit": "%", "color": "#7c3aed", "sort_order": 1}
            ],
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    definition_id = created["id"]
    assert created["definition_name"] == "测试定义"
    assert len(created["metrics"]) == 1

    update_resp = await client.patch(
        f"/api/baseline-definitions/{definition_id}",
        json={"description": "已更新描述", "expected_duration_minutes": 55},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["description"] == "已更新描述"
    assert updated["expected_duration_minutes"] == 55

    metric_add_resp = await client.post(
        f"/api/baseline-definitions/{definition_id}/metrics",
        json={
            "name": "压力",
            "unit": "MPa",
            "color": "#f56c6c",
            "edc_channel_id": "769-128",
        },
    )
    assert metric_add_resp.status_code == 201
    metric_added = metric_add_resp.json()
    assert any(metric["name"] == "压力" for metric in metric_added["metrics"])

    added_metric = next(metric for metric in metric_added["metrics"] if metric["name"] == "压力")
    assert added_metric["edc_channel_id"] == "769-128"
    metric_update_resp = await client.patch(
        f"/api/baseline-definitions/{definition_id}/metrics/{added_metric['id']}",
        json={"name": "炉压", "color": "#ef4444", "edc_channel_id": "769-129"},
    )
    assert metric_update_resp.status_code == 200
    metric_updated = metric_update_resp.json()
    updated_metric = next(metric for metric in metric_updated["metrics"] if metric["id"] == added_metric["id"])
    assert updated_metric["name"] == "炉压"
    assert updated_metric["edc_channel_id"] == "769-129"

    metric_delete_resp = await client.delete(
        f"/api/baseline-definitions/{definition_id}/metrics/{added_metric['id']}"
    )
    assert metric_delete_resp.status_code == 200
    metric_deleted = metric_delete_resp.json()
    assert all(metric["id"] != added_metric["id"] for metric in metric_deleted["metrics"])

    disable_resp = await client.post(f"/api/baseline-definitions/{definition_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"

    enable_resp = await client.post(f"/api/baseline-definitions/{definition_id}/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["status"] == "active"

    delete_resp = await client.delete(f"/api/baseline-definitions/{definition_id}")
    assert delete_resp.status_code == 200

    detail_after_delete = await client.get(f"/api/baseline-definitions/{definition_id}")
    assert detail_after_delete.status_code == 404


@pytest.mark.asyncio
async def test_baseline_crud_publish_disable_and_delete(client) -> None:
    list_resp = await client.get("/api/baselines", params={"page_size": 10})
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 2

    active_resp = await client.get("/api/baselines/active")
    assert active_resp.status_code == 200
    assert active_resp.json()["status"] == "published"

    create_resp = await client.post(
        "/api/baselines",
        json={
            "name": "自动化测试基线",
            "description": "用于验证发布流程",
            "definition_id": "def-001",
            "source_heat_id": "heat-001",
            "selected_start_time": "2026-03-12T10:00:00Z",
            "selected_end_time": "2026-03-12T10:45:00Z",
            "tolerance_percent": 9.5,
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    baseline_id = created["id"]
    assert created["status"] == "draft"

    detail_resp = await client.get(f"/api/baselines/{baseline_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["definition_id"] == "def-001"
    assert len(detail_data["curves_data"]) > 0
    assert all("edc_channel_id" in curve for curve in detail_data["curves_data"])
    assert all("source_channel_label" in curve for curve in detail_data["curves_data"])

    update_resp = await client.patch(
        f"/api/baselines/{baseline_id}",
        json={"name": "自动化测试基线 v2", "tolerance_percent": 11.0},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["name"] == "自动化测试基线 v2"
    assert updated["tolerance_percent"] == 11.0

    publish_resp = await client.post(f"/api/baselines/{baseline_id}/publish")
    assert publish_resp.status_code == 200
    published = publish_resp.json()
    assert published["status"] == "published"
    assert published["published_at"] is not None

    update_published_resp = await client.patch(
        f"/api/baselines/{baseline_id}",
        json={"description": "不应该成功"},
    )
    assert update_published_resp.status_code == 400

    disable_resp = await client.post(f"/api/baselines/{baseline_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"

    delete_disabled_resp = await client.delete(f"/api/baselines/{baseline_id}")
    assert delete_disabled_resp.status_code == 400


@pytest.mark.asyncio
async def test_baseline_delete_draft_and_reject_disabled_definition(client) -> None:
    disable_definition_resp = await client.post("/api/baseline-definitions/def-001/disable")
    assert disable_definition_resp.status_code == 200

    create_with_disabled_definition = await client.post(
        "/api/baselines",
        json={
            "name": "无效基线",
            "definition_id": "def-001",
            "source_heat_id": "heat-001",
            "tolerance_percent": 10,
        },
    )
    assert create_with_disabled_definition.status_code == 400

    await client.post("/api/baseline-definitions/def-001/enable")

    create_resp = await client.post(
        "/api/baselines",
        json={
            "name": "草稿基线",
            "definition_id": "def-001",
            "source_heat_id": "heat-001",
            "tolerance_percent": 10,
        },
    )
    assert create_resp.status_code == 201
    baseline_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/baselines/{baseline_id}")
    assert delete_resp.status_code == 200

    get_deleted = await client.get(f"/api/baselines/{baseline_id}")
    assert get_deleted.status_code == 404
