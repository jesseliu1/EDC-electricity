"""任务/报表/设置 API 测试。"""

import datetime as dt
from unittest.mock import AsyncMock

import pytest

from src.api import settings as settings_api
from src.api.heats import _COMPARE_BASELINE_CACHE, _COMPARE_CHANNEL_CURVE_CACHE, _HEAT_COMPARE_CACHE
from src.runtime_state import load_runtime_state, persist_runtime_state
from src.services import EDCClient

HOST_SYNC_HEADERS = {"X-ASNS-Host-Sync": "true"}


def _seed_compare_caches() -> None:
    _HEAT_COMPARE_CACHE["entries"] = {"heat-001": {"heat_id": "heat-001"}}
    _COMPARE_BASELINE_CACHE["entries"] = {"baseline-001": {"payload": {"id": "baseline-001"}}}
    _COMPARE_CHANNEL_CURVE_CACHE["entries"] = {
        "curve-001": {"payload": {"2349:199": []}}
    }


@pytest.mark.asyncio
async def test_request_id_header_is_echoed_and_generated(client) -> None:
    custom_request_id = "req-observe-001"
    custom_resp = await client.get("/health", headers={"X-Request-ID": custom_request_id})
    assert custom_resp.status_code == 200
    assert custom_resp.headers["X-Request-ID"] == custom_request_id

    generated_resp = await client.get("/health")
    assert generated_resp.status_code == 200
    assert generated_resp.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_tasks_crud_and_pdf(client) -> None:
    list_resp = await client.get("/api/tasks", params={"page_size": 5})
    assert list_resp.status_code == 200
    assert list_resp.json()["items"] == []

    showtime_list_resp = await client.get(
        "/api/tasks",
        params={"page_size": 5, "showtime": "true"},
    )
    assert showtime_list_resp.status_code == 200
    first_id = showtime_list_resp.json()["items"][0]["id"]

    detail_resp = await client.get(f"/api/tasks/{first_id}", params={"showtime": "true"})
    assert detail_resp.status_code == 200

    heat_resp = await client.get("/api/heats/heat-001")
    assert heat_resp.status_code == 200

    create_resp = await client.post("/api/tasks", json={"heat_id": "heat-001"})
    assert create_resp.status_code == 201
    created_id = create_resp.json()["id"]
    assert create_resp.json()["heat_id"] == "heat-001"
    assert create_resp.json()["deviation_percent"] == heat_resp.json()["deviation_percent"]

    created_detail_resp = await client.get(f"/api/tasks/{created_id}")
    assert created_detail_resp.status_code == 200
    assert created_detail_resp.json()["heat_no"] == heat_resp.json()["heat_no"]
    assert created_detail_resp.json()["deviation_snapshot"]["max_deviation"] == heat_resp.json()["deviation_percent"]

    update_resp = await client.patch(
        f"/api/tasks/{created_id}",
        json={"cause_analysis": "原因", "improvement": "改善", "prevention": "预防"},
    )
    assert update_resp.status_code == 200

    complete_resp = await client.post(
        f"/api/tasks/{created_id}/complete",
        json={"cause_analysis": "原因", "improvement": "改善", "prevention": "预防"},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    pdf_resp = await client.get(f"/api/tasks/{created_id}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_task_create_uses_frontend_snapshot_to_skip_live_heat_lookup(client, monkeypatch) -> None:
    get_heat_or_404 = AsyncMock(side_effect=AssertionError("should not refetch heat when snapshot is provided"))
    monkeypatch.setattr("src.api.heats._get_or_404", get_heat_or_404)

    create_resp = await client.post(
        "/api/tasks",
        json={
            "heat_id": "live-heat-fast-001",
            "heat_no": "H20260328-FAST",
            "deviation_percent": 18.5,
            "avg_deviation_percent": 9.2,
            "time_offset_percent": 4.8,
            "mismatch_duration_minutes": 4,
        },
    )
    assert create_resp.status_code == 201
    payload = create_resp.json()
    assert payload["heat_id"] == "live-heat-fast-001"
    assert payload["deviation_percent"] == 18.5
    get_heat_or_404.assert_not_awaited()

    created_detail_resp = await client.get(f"/api/tasks/{payload['id']}")
    assert created_detail_resp.status_code == 200
    assert created_detail_resp.json()["heat_no"] == "H20260328-FAST"
    assert created_detail_resp.json()["deviation_snapshot"]["avg_deviation"] == 9.2
    assert created_detail_resp.json()["deviation_snapshot"]["time_offset_percent"] == 4.8


@pytest.mark.asyncio
async def test_reports_list_detail_generate_pdf(client) -> None:
    list_resp = await client.get("/api/reports/daily", params={"page_size": 5})
    assert list_resp.status_code == 200
    first_date = list_resp.json()["items"][0]["date"]

    detail_resp = await client.get(f"/api/reports/daily/{first_date}")
    assert detail_resp.status_code == 200

    gen_resp = await client.post(f"/api/reports/daily/{first_date}/generate")
    assert gen_resp.status_code == 200

    pdf_resp = await client.get(f"/api/reports/daily/{first_date}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")

    future = (dt.date.today() + dt.timedelta(days=10)).isoformat()
    not_found_resp = await client.get(f"/api/reports/daily/{future}")
    assert not_found_resp.status_code == 404


@pytest.mark.asyncio
async def test_settings_get_and_update(client, monkeypatch) -> None:
    async def _fake_login(self: EDCClient) -> None:
        return None

    monkeypatch.setattr(EDCClient, "login", _fake_login)

    get_resp = await client.get("/api/settings")
    assert get_resp.status_code == 200

    host_status_resp = await client.get("/api/settings/host-connectivity-status")
    assert host_status_resp.status_code == 200
    assert host_status_resp.json()["is_connected"] is False

    runtime_resp = await client.get("/api/settings/runtime-status")
    assert runtime_resp.status_code == 200
    assert runtime_resp.json()["overall_code"] == "host_disconnected"
    assert runtime_resp.json()["pipelines"]["dashboard"]["code"] == "host_disconnected"
    assert runtime_resp.json()["pipelines"]["inbox"]["code"] == "host_disconnected"
    assert runtime_resp.json()["pipelines"]["tasks"]["code"] == "host_disconnected"
    assert runtime_resp.json()["pipelines"]["reports"]["code"] == "host_disconnected"
    assert runtime_resp.json()["pipelines"]["baselines"]["code"] == "host_disconnected"
    assert runtime_resp.json()["pipelines"]["settings"]["code"] == "host_disconnected"

    patch_resp = await client.patch(
        "/api/settings", json={"settings": {"report_generation_hour": "3"}}
    )
    assert patch_resp.status_code == 200

    tol_resp = await client.put("/api/settings/tolerance", json={"tolerance_percent": 12.5})
    assert tol_resp.status_code == 200

    forbidden_edc_resp = await client.put(
        "/api/settings/edc-connection",
        json={
            "base_url": "http://localhost:8080",
            "username": "tester",
            "password": "secret",
            "api_key": "abc",
        },
    )
    assert forbidden_edc_resp.status_code == 403

    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json={
            "base_url": "http://localhost:8080",
            "username": "tester",
            "password": "secret",
            "api_key": "abc",
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert edc_resp.status_code == 200

    update_host_status_resp = await client.put(
        "/api/settings/host-connectivity-status",
        json={
            "is_connected": True,
            "machine_name": "EDC Test Gateway",
            "last_sync_label": "2026-03-20 15:30:00",
            "meta": {
                "source": "http://60.251.229.32",
                "sensor_count": 26,
                "channel_count": 2286,
                "enabled_channel_count": 6,
            },
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert update_host_status_resp.status_code == 200
    assert update_host_status_resp.json()["machine_name"] == "EDC Test Gateway"

    host_status_resp = await client.get("/api/settings/host-connectivity-status")
    assert host_status_resp.status_code == 200
    assert host_status_resp.json()["meta"]["enabled_channel_count"] == 6

    pre_channel_runtime_resp = await client.get("/api/settings/runtime-status")
    assert pre_channel_runtime_resp.status_code == 200
    assert pre_channel_runtime_resp.json()["overall_code"] == "no_enabled_channels"

    host_channels_resp = await client.put(
        "/api/settings/host-channels",
        json={
            "items": [
                {
                    "id": "sensor-9-128",
                    "device_name": "测试设备 · 三相智能电表",
                    "device_type": "三相智能电表",
                    "area": "测试区域",
                    "suid": "sensor-9",
                    "cuid": "128",
                    "channel_name": "总有功功率",
                    "unit": "kW",
                    "last_value": "226.8",
                    "status": "online",
                }
            ]
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert host_channels_resp.status_code == 200

    runtime_resp = await client.get("/api/settings/runtime-status")
    assert runtime_resp.status_code == 200
    assert runtime_resp.json()["overall_code"] == "ready"
    assert runtime_resp.json()["runtime"]["showtime_enabled"] is False
    assert runtime_resp.json()["pipelines"]["heats"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["inbox"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["tasks"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["reports"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["baselines"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["settings"]["code"] == "ready"
    assert runtime_resp.json()["active_baseline"]["id"] == "baseline-001"

    runtime_showtime_resp = await client.get("/api/settings/runtime-status", params={"showtime": "true"})
    assert runtime_showtime_resp.status_code == 200
    assert runtime_showtime_resp.json()["overall_code"] == "showtime"
    assert runtime_showtime_resp.json()["pipelines"]["dashboard"]["code"] == "showtime"
    assert runtime_showtime_resp.json()["pipelines"]["settings"]["code"] == "showtime"

    test_resp = await client.post("/api/settings/edc-connection/test")
    assert test_resp.status_code == 200

    report_resp = await client.put("/api/settings/report", json={"generation_hour": 6})
    assert report_resp.status_code == 200


@pytest.mark.asyncio
async def test_runtime_status_uses_selected_business_channels_for_ready(client) -> None:
    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json={
            "base_url": "http://localhost:8080",
            "username": "tester",
            "password": "secret",
            "api_key": "abc",
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert edc_resp.status_code == 200

    host_channels_resp = await client.put(
        "/api/settings/host-channels",
        json={
            "items": [
                {
                    "id": "sensor-9-128",
                    "device_name": "测试设备 · 三相智能电表",
                    "device_type": "三相智能电表",
                    "area": "测试区域",
                    "suid": "sensor-9",
                    "cuid": "128",
                    "channel_name": "B相电压",
                    "unit": "V",
                    "last_value": "226.8",
                    "status": "online",
                }
            ]
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert host_channels_resp.status_code == 200

    host_status_resp = await client.put(
        "/api/settings/host-connectivity-status",
        json={
            "is_connected": True,
            "machine_name": "EDC Test Gateway",
            "last_sync_label": "2026-03-22 10:00:00",
            "meta": {
                "source": "http://60.251.229.32",
                "sensor_count": 26,
                "channel_count": 2286,
                "enabled_channel_count": 2127,
            },
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert host_status_resp.status_code == 200

    runtime_resp = await client.get("/api/settings/runtime-status")
    assert runtime_resp.status_code == 200
    payload = runtime_resp.json()
    assert payload["overall_code"] == "no_enabled_channels"
    assert payload["host"]["meta"]["enabled_channel_count"] == 2127
    assert payload["edc"]["host_channel_total"] == 1
    assert payload["pipelines"]["dashboard"]["code"] == "no_enabled_channels"
    assert payload["pipelines"]["heats"]["code"] == "no_enabled_channels"
    assert payload["pipelines"]["baselines"]["code"] == "no_enabled_channels"
    assert payload["pipelines"]["settings"]["code"] == "ready"


@pytest.mark.asyncio
async def test_settings_connection_and_host_channels_invalidate_compare_caches(client) -> None:
    _seed_compare_caches()

    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json={
            "base_url": "http://localhost:8080",
            "username": "tester",
            "password": "secret",
            "api_key": "abc",
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert edc_resp.status_code == 200
    assert _HEAT_COMPARE_CACHE["entries"] == {}
    assert _COMPARE_BASELINE_CACHE["entries"] == {}
    assert _COMPARE_CHANNEL_CURVE_CACHE["entries"] == {}

    _seed_compare_caches()

    host_channels_resp = await client.put(
        "/api/settings/host-channels",
        json={
            "items": [
                {
                    "id": "sensor-9-128",
                    "device_name": "测试设备 · 三相智能电表",
                    "device_type": "三相智能电表",
                    "area": "测试区域",
                    "suid": "sensor-9",
                    "cuid": "128",
                    "channel_name": "B相电压",
                    "unit": "V",
                    "last_value": "226.8",
                    "status": "online",
                }
            ]
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert host_channels_resp.status_code == 200
    assert _HEAT_COMPARE_CACHE["entries"] == {}
    assert _COMPARE_BASELINE_CACHE["entries"] == {}
    assert _COMPARE_CHANNEL_CURVE_CACHE["entries"] == {}


@pytest.mark.asyncio
async def test_edc_connection_change_resets_host_sync_state(client) -> None:
    host_channels_resp = await client.put(
        "/api/settings/host-channels",
        json={
            "items": [
                {
                    "id": "sensor-9-128",
                    "device_name": "测试设备 · 三相智能电表",
                    "device_type": "三相智能电表",
                    "area": "测试区域",
                    "suid": "sensor-9",
                    "cuid": "128",
                    "channel_name": "B相电压",
                    "unit": "V",
                    "last_value": "226.8",
                    "status": "online",
                }
            ]
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert host_channels_resp.status_code == 200

    host_status_resp = await client.put(
        "/api/settings/host-connectivity-status",
        json={
            "is_connected": True,
            "machine_name": "EDC Test Gateway",
            "last_sync_label": "2026-03-22 10:00:00",
            "meta": {
                "source": "http://old-edc-host",
                "sensor_count": 26,
                "channel_count": 2286,
                "enabled_channel_count": 2127,
            },
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert host_status_resp.status_code == 200

    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json={
            "base_url": "http://new-edc-host",
            "username": "tester",
            "password": "secret",
            "api_key": "abc",
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert edc_resp.status_code == 200

    runtime_resp = await client.get("/api/settings/runtime-status")
    assert runtime_resp.status_code == 200
    payload = runtime_resp.json()
    assert payload["host"]["is_connected"] is False
    assert payload["host"]["meta"]["source"] == "http://new-edc-host"
    assert payload["edc"]["base_url"] == "http://new-edc-host"
    assert payload["edc"]["host_channel_total"] == 0


@pytest.mark.asyncio
async def test_runtime_state_prefers_explicit_app_edc_config_and_clears_old_host_sync(
    client, monkeypatch
) -> None:
    settings_api._SETTINGS_STORE["edc_base_url"]["value"] = "http://old-edc-host"
    settings_api._SETTINGS_STORE["edc_username"]["value"] = "old-user"
    settings_api._SETTINGS_STORE["edc_password"]["value"] = "old-secret"
    settings_api._SETTINGS_STORE["edc_api_key"]["value"] = "old-api-key"
    settings_api._HOST_CHANNEL_STORE[:] = [
        {
            "id": "sensor-9-128",
            "device_name": "旧设备 · 三相智能电表",
            "device_type": "三相智能电表",
            "area": "旧区域",
            "suid": "sensor-9",
            "cuid": "128",
            "channel_name": "总有功功率",
            "unit": "kW",
            "last_value": "226.8",
            "status": "online",
        }
    ]
    settings_api._HOST_CONNECTIVITY_STATUS.clear()
    settings_api._HOST_CONNECTIVITY_STATUS.update(
        {
            "is_connected": True,
            "machine_name": "Old Gateway",
            "last_sync_label": "2026-03-28 12:00:00",
            "meta": {
                "source": "http://old-edc-host",
                "sensor_count": 26,
                "channel_count": 2286,
                "enabled_channel_count": 2127,
            },
        }
    )
    await persist_runtime_state(
        "settings_store",
        "host_channels",
        "host_connectivity_status",
    )

    monkeypatch.setattr(settings_api.app_settings, "edc_base_url", "http://env-edc-host")
    monkeypatch.setattr(settings_api.app_settings, "edc_username", "env-user")
    monkeypatch.setattr(settings_api.app_settings, "edc_password", "env-secret")
    monkeypatch.setattr(settings_api.app_settings, "edc_api_key", "env-api-key")

    await load_runtime_state()

    runtime_resp = await client.get("/api/settings/runtime-status")
    assert runtime_resp.status_code == 200
    payload = runtime_resp.json()
    assert payload["edc"]["base_url"] == "http://env-edc-host"
    assert payload["host"]["is_connected"] is False
    assert payload["host"]["meta"]["source"] == "http://env-edc-host"
    assert payload["edc"]["host_channel_total"] == 0
