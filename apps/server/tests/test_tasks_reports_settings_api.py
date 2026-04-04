"""任务/报表/设置 API 测试。"""

import datetime as dt
from unittest.mock import AsyncMock

import pytest

from src.api import settings as settings_api
from src.api.baseline_definitions import _DEFINITION_STORE
from src.api.heats import _COMPARE_BASELINE_CACHE, _COMPARE_CHANNEL_CURVE_CACHE, _HEAT_COMPARE_CACHE
from src.api.tasks import _TASK_STORE
from src.api.settings import (
    _CHANNEL_ROLE_BINDING_STORE,
    _HOST_CHANNEL_CATALOG_CACHE,
    _HOST_CHANNEL_STORE,
    _SETTINGS_STORE,
)
from src.runtime_state import load_runtime_state, persist_runtime_state
from src.services import EDCClient

HOST_SYNC_HEADERS = {"X-ASNS-Host-Sync": "true"}
PRIMARY_BASELINE_ID = "def-001:001"


def _with_source_revision(
    payload: dict[str, object],
    source_revision: int | None = None,
) -> dict[str, object]:
    return {
        "source_revision": source_revision or settings_api._current_source_revision(),
        **payload,
    }


def _seed_compare_caches() -> None:
    _HEAT_COMPARE_CACHE["entries"] = {"heat-001": {"heat_id": "heat-001"}}
    _COMPARE_BASELINE_CACHE["entries"] = {PRIMARY_BASELINE_ID: {"payload": {"id": PRIMARY_BASELINE_ID}}}
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
    assert create_resp.json()["deviation_percent"] is not None

    created_detail_resp = await client.get(f"/api/tasks/{created_id}")
    assert created_detail_resp.status_code == 200
    assert created_detail_resp.json()["heat_no"] == heat_resp.json()["heat_no"]
    assert (
        created_detail_resp.json()["deviation_snapshot"]["max_deviation"]
        == create_resp.json()["deviation_percent"]
    )

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
async def test_tasks_persist_across_runtime_reload(client) -> None:
    create_resp = await client.post("/api/tasks", json={"heat_id": "heat-001"})
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    _TASK_STORE.clear()
    await load_runtime_state()

    restored_detail = await client.get(f"/api/tasks/{task_id}")
    assert restored_detail.status_code == 200
    assert restored_detail.json()["id"] == task_id


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
        json=_with_source_revision(
            {
                "base_url": "http://localhost:8080",
                "username": "tester",
                "password": "secret",
                "api_key": "abc",
            }
        ),
    )
    assert forbidden_edc_resp.status_code == 403

    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json=_with_source_revision(
            {
                "base_url": "http://localhost:8080",
                "username": "tester",
                "password": "secret",
                "api_key": "abc",
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert edc_resp.status_code == 200

    update_host_status_resp = await client.put(
        "/api/settings/host-connectivity-status",
        json=_with_source_revision(
            {
                "is_connected": True,
                "machine_name": "EDC Test Gateway",
                "last_sync_label": "2026-03-20 15:30:00",
                "meta": {
                    "source": "http://60.251.229.32",
                    "sensor_count": 26,
                    "channel_count": 2286,
                    "enabled_channel_count": 6,
                },
            }
        ),
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
        json=_with_source_revision(
            {
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
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert host_channels_resp.status_code == 200

    runtime_resp = await client.get("/api/settings/runtime-status")
    assert runtime_resp.status_code == 200
    assert runtime_resp.json()["overall_code"] == "ready"
    assert runtime_resp.json()["runtime"]["showtime_enabled"] is False
    assert runtime_resp.json()["channel_roles"]["configured_count"] >= 1
    assert runtime_resp.json()["channel_roles"]["missing_required_role_keys"] == []
    assert runtime_resp.json()["pipelines"]["dashboard"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["heats"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["inbox"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["tasks"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["reports"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["baselines"]["code"] == "ready"
    assert runtime_resp.json()["pipelines"]["settings"]["code"] == "ready"
    assert runtime_resp.json()["active_baseline"]["id"] is None

    runtime_showtime_resp = await client.get("/api/settings/runtime-status", params={"showtime": "true"})
    assert runtime_showtime_resp.status_code == 200
    assert runtime_showtime_resp.json()["overall_code"] == "showtime"
    assert runtime_showtime_resp.json()["pipelines"]["dashboard"]["code"] == "showtime"
    assert runtime_showtime_resp.json()["pipelines"]["settings"]["code"] == "showtime"

    test_resp = await client.post("/api/settings/edc-connection/test")
    assert test_resp.status_code == 200

    role_resp = await client.get("/api/settings/channel-role-bindings")
    assert role_resp.status_code == 200
    assert role_resp.json()["configured_count"] >= 1
    assert role_resp.json()["items"][0]["role_key"] == "dashboard_primary"


@pytest.mark.asyncio
async def test_host_bootstrap_and_runtime_sync_round_trip(client) -> None:
    bootstrap_resp = await client.get("/api/settings/host-bootstrap")
    assert bootstrap_resp.status_code == 200
    bootstrap_payload = bootstrap_resp.json()
    assert bootstrap_payload["source_revision"] >= 1
    assert bootstrap_payload["host_channels"]["total"] >= 1
    assert bootstrap_payload["host_channel_catalog"]["total"] >= 1

    sync_resp = await client.put(
        "/api/settings/host-runtime-sync",
        json={
            "source_revision": bootstrap_payload["source_revision"],
            "items": [
                {
                    "id": "2349-199",
                    "device_name": "测试电表 · 三相智能电表",
                    "device_type": "三相智能电表",
                    "area": "测试电力",
                    "suid": "2349",
                    "cuid": "199",
                    "channel_name": "总有功功率",
                    "unit": "kW",
                    "last_value": "226.8",
                    "status": "online",
                }
            ],
            "catalog_items": [
                {
                    "id": "2349-199",
                    "device_name": "测试电表 · 三相智能电表",
                    "device_type": "三相智能电表",
                    "area": "测试电力",
                    "suid": "2349",
                    "cuid": "199",
                    "channel_name": "总有功功率",
                    "unit": "kW",
                    "last_value": "226.8",
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
                    "last_value": "221.1",
                    "status": "online",
                },
            ],
            "connection": {
                "is_connected": True,
                "machine_name": "EDC Test Gateway",
                "last_sync_label": "2026-03-31 10:00:00",
                "meta": {
                    "source": "http://61.216.55.133",
                    "sensor_count": 2,
                    "channel_count": 2,
                    "enabled_channel_count": 2,
                },
            },
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert sync_resp.status_code == 200
    sync_payload = sync_resp.json()
    assert sync_payload["success"] is True
    assert sync_payload["source_revision"] == bootstrap_payload["source_revision"] + 1
    assert sync_payload["host_channels"]["total"] == 1
    assert sync_payload["host_channel_catalog"]["total"] == 2
    assert sync_payload["connectivity_status"]["is_connected"] is True

    refreshed_bootstrap_resp = await client.get("/api/settings/host-bootstrap")
    assert refreshed_bootstrap_resp.status_code == 200
    refreshed_bootstrap = refreshed_bootstrap_resp.json()
    assert refreshed_bootstrap["source_revision"] == sync_payload["source_revision"]
    assert refreshed_bootstrap["host_channels"]["total"] == 1
    assert refreshed_bootstrap["host_channel_catalog"]["total"] == 2
    assert refreshed_bootstrap["connectivity_status"]["machine_name"] == "EDC Test Gateway"


@pytest.mark.asyncio
async def test_host_runtime_sync_rejects_stale_source_revision(client) -> None:
    current_revision = settings_api._current_source_revision()
    first_sync_resp = await client.put(
        "/api/settings/host-runtime-sync",
        json={
            "source_revision": current_revision,
            "items": [],
            "catalog_items": [],
            "connection": {
                "is_connected": False,
                "machine_name": "--",
                "last_sync_label": "--",
                "meta": {
                    "source": "--",
                    "sensor_count": 0,
                    "channel_count": 0,
                    "enabled_channel_count": 0,
                },
            },
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert first_sync_resp.status_code == 200

    stale_sync_resp = await client.put(
        "/api/settings/host-runtime-sync",
        json={
            "source_revision": current_revision,
            "items": [],
            "catalog_items": [],
            "connection": {
                "is_connected": False,
                "machine_name": "--",
                "last_sync_label": "--",
                "meta": {
                    "source": "--",
                    "sensor_count": 0,
                    "channel_count": 0,
                    "enabled_channel_count": 0,
                },
            },
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert stale_sync_resp.status_code == 409
    assert stale_sync_resp.json()["detail"]["current_source_revision"] == current_revision + 1
    assert "刷新后重试" in stale_sync_resp.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_channel_role_bindings_can_be_updated_explicitly(client) -> None:
    response = await client.put(
        "/api/settings/channel-role-bindings",
        json={
            "bindings": {
                "dashboard_primary": "2349-142",
                "dashboard_secondary": "2349-130",
                "live_heat_inference": "2349-142",
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured_count"] == 3
    assert payload["missing_required_role_keys"] == []
    assert _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] == "2349-142"
    assert _CHANNEL_ROLE_BINDING_STORE["dashboard_secondary"] == "2349-130"
    assert _CHANNEL_ROLE_BINDING_STORE["live_heat_inference"] == "2349-142"

    report_resp = await client.put("/api/settings/report", json={"generation_hour": 6})
    assert report_resp.status_code == 200


@pytest.mark.asyncio
async def test_runtime_status_uses_selected_business_channels_for_ready(client) -> None:
    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json=_with_source_revision(
            {
                "base_url": "http://localhost:8080",
                "username": "tester",
                "password": "secret",
                "api_key": "abc",
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert edc_resp.status_code == 200

    host_channels_resp = await client.put(
        "/api/settings/host-channels",
        json=_with_source_revision(
            {
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
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert host_channels_resp.status_code == 200

    host_status_resp = await client.put(
        "/api/settings/host-connectivity-status",
        json=_with_source_revision(
            {
                "is_connected": True,
                "machine_name": "EDC Test Gateway",
                "last_sync_label": "2026-03-22 10:00:00",
                "meta": {
                    "source": "http://60.251.229.32",
                    "sensor_count": 26,
                    "channel_count": 2286,
                    "enabled_channel_count": 2127,
                },
            }
        ),
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
        json=_with_source_revision(
            {
                "base_url": "http://localhost:8080",
                "username": "tester",
                "password": "secret",
                "api_key": "abc",
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert edc_resp.status_code == 200
    assert _HEAT_COMPARE_CACHE["entries"] == {}
    assert _COMPARE_BASELINE_CACHE["entries"] == {}
    assert _COMPARE_CHANNEL_CURVE_CACHE["entries"] == {}

    _seed_compare_caches()

    host_channels_resp = await client.put(
        "/api/settings/host-channels",
        json=_with_source_revision(
            {
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
            }
        ),
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
        json=_with_source_revision(
            {
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
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert host_channels_resp.status_code == 200

    host_status_resp = await client.put(
        "/api/settings/host-connectivity-status",
        json=_with_source_revision(
            {
                "is_connected": True,
                "machine_name": "EDC Test Gateway",
                "last_sync_label": "2026-03-22 10:00:00",
                "meta": {
                    "source": "http://old-edc-host",
                    "sensor_count": 26,
                    "channel_count": 2286,
                    "enabled_channel_count": 2127,
                },
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert host_status_resp.status_code == 200

    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json=_with_source_revision(
            {
                "base_url": "http://new-edc-host",
                "username": "tester",
                "password": "secret",
                "api_key": "abc",
            }
        ),
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


@pytest.mark.asyncio
async def test_switching_edc_source_clears_source_bound_runtime_state(client) -> None:
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(
        [
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
    )
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend([item.copy() for item in _HOST_CHANNEL_STORE])
    _SETTINGS_STORE["active_baseline_id"]["value"] = PRIMARY_BASELINE_ID
    _DEFINITION_STORE["def-001"]["metrics"][0]["edc_channel_id"] = "sensor-9-128"

    response = await client.put(
        "/api/settings/edc-connection",
        json=_with_source_revision(
            {
                "base_url": "http://61.216.55.133",
                "username": "admin",
                "password": "admin",
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "EDC 来源已切换，旧来源相关配置已统一清空"
    assert _HOST_CHANNEL_STORE == []
    assert _HOST_CHANNEL_CATALOG_CACHE == []
    assert _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] is None
    assert _SETTINGS_STORE["active_baseline_id"]["value"] == ""
    assert _DEFINITION_STORE["def-001"]["metrics"][0]["edc_channel_id"] is None

    host_status_resp = await client.get("/api/settings/host-connectivity-status")
    assert host_status_resp.status_code == 200
    payload = host_status_resp.json()
    assert payload["is_connected"] is False
    assert payload["meta"]["source"] == "http://61.216.55.133"
    assert payload["meta"]["enabled_channel_count"] == 0


@pytest.mark.asyncio
async def test_updating_same_edc_source_keeps_existing_host_channels(client) -> None:
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(
        [
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
    )
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend([item.copy() for item in _HOST_CHANNEL_STORE])
    _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] = "sensor-9-128"
    _CHANNEL_ROLE_BINDING_STORE["live_heat_inference"] = "sensor-9-128"
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    _SETTINGS_STORE["active_baseline_id"]["value"] = PRIMARY_BASELINE_ID
    _DEFINITION_STORE["def-001"]["metrics"][0]["edc_channel_id"] = "sensor-9-128"

    response = await client.put(
        "/api/settings/edc-connection",
        json=_with_source_revision(
            {
                "base_url": "http://61.216.55.133",
                "username": "admin",
                "password": "admin",
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "EDC 连接配置未发生变化"
    assert len(_HOST_CHANNEL_STORE) == 1
    assert _HOST_CHANNEL_STORE[0]["id"] == "sensor-9-128"
    assert len(_HOST_CHANNEL_CATALOG_CACHE) == 1
    assert _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] == "sensor-9-128"
    assert _SETTINGS_STORE["active_baseline_id"]["value"] == PRIMARY_BASELINE_ID
    assert _DEFINITION_STORE["def-001"]["metrics"][0]["edc_channel_id"] == "sensor-9-128"


@pytest.mark.asyncio
async def test_password_only_change_resets_connection_state_without_clearing_source_bound_runtime(
    client,
) -> None:
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(
        [
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
    )
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend([item.copy() for item in _HOST_CHANNEL_STORE])
    _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] = "sensor-9-128"
    _CHANNEL_ROLE_BINDING_STORE["live_heat_inference"] = "sensor-9-128"
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "old-secret"
    _SETTINGS_STORE["active_baseline_id"]["value"] = PRIMARY_BASELINE_ID
    _DEFINITION_STORE["def-001"]["metrics"][0]["edc_channel_id"] = "sensor-9-128"
    settings_api._HOST_CONNECTIVITY_STATUS.clear()
    settings_api._HOST_CONNECTIVITY_STATUS.update(
        {
            "is_connected": True,
            "machine_name": "EDC Test Gateway",
            "last_sync_label": "2026-03-30 09:00:00",
            "meta": {
                "source": "http://61.216.55.133",
                "sensor_count": 3,
                "channel_count": 788,
                "enabled_channel_count": 1,
            },
        }
    )

    response = await client.post(
        "/api/settings/source-switch",
        json=_with_source_revision(
            {
                "base_url": "http://61.216.55.133",
                "username": "admin",
                "password": "new-secret",
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_identity_changed"] is False
    assert payload["connection_material_changed"] is True
    assert payload["cleared_host_channel_count"] == 0
    assert payload["cleared_definition_binding_count"] == 0
    assert payload["message"] == "EDC 连接材料已更新，连线状态已重置，等待重新验证"

    assert len(_HOST_CHANNEL_STORE) == 1
    assert _HOST_CHANNEL_STORE[0]["id"] == "sensor-9-128"
    assert _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] == "sensor-9-128"
    assert _SETTINGS_STORE["active_baseline_id"]["value"] == PRIMARY_BASELINE_ID
    assert _DEFINITION_STORE["def-001"]["metrics"][0]["edc_channel_id"] == "sensor-9-128"

    host_status_resp = await client.get("/api/settings/host-connectivity-status")
    assert host_status_resp.status_code == 200
    host_payload = host_status_resp.json()
    assert host_payload["is_connected"] is False
    assert host_payload["meta"]["source"] == "http://61.216.55.133"


@pytest.mark.asyncio
async def test_source_switch_endpoint_returns_detailed_reset_summary(client) -> None:
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(
        [
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
    )
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend([item.copy() for item in _HOST_CHANNEL_STORE])
    _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] = "sensor-9-128"
    _CHANNEL_ROLE_BINDING_STORE["live_heat_inference"] = "sensor-9-128"
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://60.251.229.32"
    _SETTINGS_STORE["edc_username"]["value"] = "volapu"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    _SETTINGS_STORE["active_baseline_id"]["value"] = PRIMARY_BASELINE_ID
    _DEFINITION_STORE["def-001"]["metrics"][0]["edc_channel_id"] = "sensor-9-128"

    response = await client.post(
        "/api/settings/source-switch",
        json=_with_source_revision(
            {
                "base_url": "http://61.216.55.133",
                "username": "admin",
                "password": "admin",
            }
        ),
        headers=HOST_SYNC_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_identity_changed"] is True
    assert payload["connection_material_changed"] is True
    assert payload["cleared_host_channel_count"] == 1
    assert payload["cleared_host_channel_catalog_count"] == 1
    assert payload["cleared_channel_role_binding_count"] >= 1
    assert payload["cleared_definition_binding_count"] >= 1
    assert payload["cleared_active_baseline_id"] == PRIMARY_BASELINE_ID
    assert payload["next_source"] == "http://61.216.55.133"
