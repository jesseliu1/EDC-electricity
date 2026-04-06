"""基线、基线定义与仪表盘 API 测试。"""

import asyncio
from datetime import datetime

import pytest

from src.api import settings as settings_api
from src.api.baseline_definitions import _DEFINITION_STORE
from src.api.baselines import _BASELINE_STORE
from src.api.heats import _COMPARE_BASELINE_CACHE, _COMPARE_CHANNEL_CURVE_CACHE, _HEAT_COMPARE_CACHE
from src.api.settings import _CHANNEL_ROLE_BINDING_STORE, _HOST_CHANNEL_STORE, _SETTINGS_STORE
from src.config import settings
from src.schemas.common import CurvePoint
from src.services import EDCClientError

HOST_SYNC_HEADERS = {"X-ASNS-Host-Sync": "true"}
SHOWTIME_HEADERS = {"X-Showtime": "true"}
PRIMARY_BASELINE_ID = "def-001:001"
SECONDARY_BASELINE_ID = "def-002:001"


def _seed_compare_caches() -> None:
    _HEAT_COMPARE_CACHE["entries"] = {"heat-001": {"heat_id": "heat-001"}}
    _COMPARE_BASELINE_CACHE["entries"] = {PRIMARY_BASELINE_ID: {"payload": {"id": PRIMARY_BASELINE_ID}}}
    _COMPARE_CHANNEL_CURVE_CACHE["entries"] = {"curve-001": {"payload": {"2349:199": []}}}


class _FakeSharedEDCClient:
    def __init__(
        self,
        *,
        point_map: dict[tuple[str, str], list[CurvePoint]] | None = None,
    ) -> None:
        self._token: str | None = None
        self.login_calls = 0
        self.requests: list[dict[str, object]] = []
        self.point_map = point_map or {}

    async def login(self) -> str:
        if self._token:
            return self._token
        self.login_calls += 1
        self._token = "fake-token"
        return self._token

    async def get_local_datas(
        self,
        *,
        suid: str,
        cuid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[CurvePoint]:
        self.requests.append(
            {
                "suid": str(suid),
                "cuid": str(cuid),
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        return list(self.point_map.get((str(suid), str(cuid)), []))


@pytest.mark.asyncio
async def test_dashboard_endpoints(client, monkeypatch) -> None:
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"

    fake_client = _FakeSharedEDCClient(
        point_map={
            ("2349", "199"): [
                CurvePoint(timestamp=1000, value=101.0),
                CurvePoint(timestamp=2000, value=102.0),
            ],
            ("2349", "128"): [
                CurvePoint(timestamp=1000, value=221.0),
                CurvePoint(timestamp=2000, value=222.0),
            ],
        }
    )

    class _FakeDashboardEDCClient:
        def __init__(self, **_kwargs) -> None:
            self._delegate = fake_client

        async def __aenter__(self):
            return self._delegate

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.api.dashboard.EDCClient", _FakeDashboardEDCClient)

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
    assert len(recent_data["items"]) >= 1
    assert recent_data["items"][0]["id"] == "heat-001"


@pytest.mark.asyncio
async def test_dashboard_realtime_prefers_edc_curves_when_available(client, monkeypatch) -> None:
    async def fake_load_realtime_curves_from_edc(**_kwargs):
        return {
            "power": [
                CurvePoint(timestamp=1000, value=101.0),
                CurvePoint(timestamp=2000, value=102.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=221.0),
                CurvePoint(timestamp=2000, value=222.0),
            ],
            "baseline_power": [
                CurvePoint(timestamp=1000, value=460.0),
                CurvePoint(timestamp=2000, value=460.0),
            ],
            "baseline_voltage": [
                CurvePoint(timestamp=1000, value=385.0),
                CurvePoint(timestamp=2000, value=385.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.dashboard._load_realtime_curves_from_edc",
        fake_load_realtime_curves_from_edc,
    )

    response = await client.get("/api/dashboard/realtime", params={"duration": "1h"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["power"][0]["value"] == 101.0
    assert payload["voltage"][1]["value"] == 222.0


@pytest.mark.asyncio
async def test_dashboard_realtime_rejects_empty_real_data_when_mock_disabled(
    client, monkeypatch
) -> None:
    settings.enable_mock_dataset = False

    async def fake_load_realtime_curves_from_edc(**_kwargs):
        return None

    monkeypatch.setattr(
        "src.api.dashboard._load_realtime_curves_from_edc",
        fake_load_realtime_curves_from_edc,
    )

    response = await client.get("/api/dashboard/realtime", params={"duration": "1h"})
    assert response.status_code == 503
    assert "未获取到真实实时数据" in response.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_realtime_does_not_fallback_when_mock_enabled(client, monkeypatch) -> None:
    settings.enable_mock_dataset = True

    async def fake_load_realtime_curves_from_edc(**_kwargs):
        return None

    monkeypatch.setattr(
        "src.api.dashboard._load_realtime_curves_from_edc",
        fake_load_realtime_curves_from_edc,
    )

    response = await client.get("/api/dashboard/realtime", params={"duration": "1h"})
    assert response.status_code == 503
    assert "未获取到真实实时数据" in response.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_realtime_surfaces_edc_transport_failure(client, monkeypatch) -> None:
    async def fake_load_realtime_curves_from_edc(**_kwargs):
        raise EDCClientError(
            "实时曲线拉取失败：EDC 登录超时（ConnectTimeout），请检查当前环境到上游 EDC 的网络连通性"
        )

    monkeypatch.setattr(
        "src.api.dashboard._load_realtime_curves_from_edc",
        fake_load_realtime_curves_from_edc,
    )

    response = await client.get("/api/dashboard/realtime", params={"duration": "1h"})
    assert response.status_code == 503
    assert "实时曲线拉取失败" in response.json()["detail"]
    assert "ConnectTimeout" in response.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_realtime_falls_back_to_bound_host_channels_after_source_switch_reset(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    _SETTINGS_STORE["active_baseline_id"]["value"] = ""
    for definition in _DEFINITION_STORE.values():
        for metric in definition["metrics"]:
            metric["edc_channel_id"] = None

    fake_client = _FakeSharedEDCClient(
        point_map={
            ("2349", "199"): [
                CurvePoint(timestamp=1000, value=88.0),
                CurvePoint(timestamp=2000, value=92.0),
            ],
            ("2349", "128"): [
                CurvePoint(timestamp=1000, value=221.5),
                CurvePoint(timestamp=2000, value=222.0),
            ],
        }
    )

    class _FakeDashboardEDCClient:
        def __init__(self, **_kwargs) -> None:
            self._delegate = fake_client

        async def __aenter__(self):
            return self._delegate

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.api.dashboard.EDCClient", _FakeDashboardEDCClient)

    response = await client.get("/api/dashboard/realtime", params={"duration": "1h"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline_id"] == PRIMARY_BASELINE_ID
    assert payload["baseline_name"] == "标准基线 v2.1"
    assert "总有功功率" in payload["power_source_label"]
    assert "A相电压" in payload["voltage_source_label"]
    assert payload["power"][0]["value"] == 88.0
    assert payload["voltage"][1]["value"] == 222.0
    assert fake_client.login_calls == 1
    assert [(item["suid"], item["cuid"]) for item in fake_client.requests] == [
        ("2349", "199"),
        ("2349", "128"),
    ]


@pytest.mark.asyncio
async def test_dashboard_realtime_allows_missing_secondary_role_when_primary_role_has_data(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    _CHANNEL_ROLE_BINDING_STORE["dashboard_primary"] = "2349-199"
    _CHANNEL_ROLE_BINDING_STORE["dashboard_secondary"] = None

    fake_client = _FakeSharedEDCClient(
        point_map={
            ("2349", "199"): [
                CurvePoint(timestamp=1000, value=88.0),
                CurvePoint(timestamp=2000, value=92.0),
            ],
        }
    )

    class _FakeDashboardEDCClient:
        def __init__(self, **_kwargs) -> None:
            self._delegate = fake_client

        async def __aenter__(self):
            return self._delegate

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.api.dashboard.EDCClient", _FakeDashboardEDCClient)

    response = await client.get("/api/dashboard/realtime", params={"duration": "1h"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["power"]) == 2
    assert payload["voltage"] == []
    assert payload["baseline_voltage"] == []
    assert payload["voltage_source_label"] is None
    assert [(item["suid"], item["cuid"]) for item in fake_client.requests] == [
        ("2349", "199"),
    ]


@pytest.mark.asyncio
async def test_settings_host_channels_endpoint(client, monkeypatch) -> None:
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(
        [
            {
                "id": "sensor-1-128",
                "device_name": "测试设备 · 三相智能电表",
                "device_type": "三相智能电表",
                "area": "测试区域",
                "suid": "sensor-1",
                "cuid": "128",
                "channel_name": "总有功功率",
                "unit": "kW",
                "last_value": "321.5",
                "status": "online",
            },
            {
                "id": "sensor-2-128",
                "device_name": "测试设备 · 热电偶温度采集器",
                "device_type": "热电偶温度采集器",
                "area": "测试区域",
                "suid": "sensor-2",
                "cuid": "128",
                "channel_name": "热电偶温度采集通道",
                "unit": "℃",
                "last_value": "1450.2",
                "status": "online",
            },
        ]
    )
    host_channels_resp = await client.get("/api/settings/host-channels")
    assert host_channels_resp.status_code == 200
    payload = host_channels_resp.json()
    assert payload["total"] == 2
    assert any(item["channel_name"] == "总有功功率" for item in payload["items"])
    assert any(item["channel_name"] == "热电偶温度采集通道" for item in payload["items"])


@pytest.mark.asyncio
async def test_settings_host_channels_can_be_saved(client) -> None:
    forbidden_response = await client.put(
        "/api/settings/host-channels",
        json={
            "source_revision": settings_api._current_source_revision(),
            "items": [],
        },
    )
    assert forbidden_response.status_code == 403

    response = await client.put(
        "/api/settings/host-channels",
        json={
            "source_revision": settings_api._current_source_revision(),
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
            ],
        },
        headers=HOST_SYNC_HEADERS,
    )
    assert response.status_code == 200

    fetch_resp = await client.get("/api/settings/host-channels")
    assert fetch_resp.status_code == 200
    payload = fetch_resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "sensor-9-128"


@pytest.mark.asyncio
async def test_definition_preview_curves_prefers_preview_builder(client, monkeypatch) -> None:
    async def fake_build_preview_curves(**_kwargs):
        return [
            {
                "metric_id": "metric-001",
                "metric_name": "功率",
                "unit": "kW",
                "color": "#409EFF",
                "edc_channel_id": "2349-199",
                "source_channel_name": "总有功功率",
                "source_channel_label": "SSTW / 总有功功率 / kW",
                "points": [
                    {"timestamp": 1000, "value": 401.0},
                    {"timestamp": 2000, "value": 402.0},
                ],
            }
        ]

    monkeypatch.setattr(
        "src.api.baseline_definitions._build_preview_curves",
        fake_build_preview_curves,
    )

    response = await client.get(
        "/api/baseline-definitions/def-001/preview-curves",
        params={"heat_id": "heat-001"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["definition_id"] == "def-001"
    assert payload["source_heat_id"] == "heat-001"
    assert payload["curves_data"][0]["points"][0]["value"] == 401.0


@pytest.mark.asyncio
async def test_baseline_detail_fetches_curves_via_shared_client_and_source_heat_window(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    baseline_item = _BASELINE_STORE[PRIMARY_BASELINE_ID]
    baseline_item["source_heat_id"] = "heat-001"
    baseline_item["selected_start_time"] = None
    baseline_item["selected_end_time"] = None

    fake_client = _FakeSharedEDCClient(
        point_map={
            ("2349", "199"): [
                CurvePoint(timestamp=1000, value=301.0),
                CurvePoint(timestamp=2000, value=302.0),
            ],
            ("2349", "128"): [
                CurvePoint(timestamp=1000, value=211.0),
                CurvePoint(timestamp=2000, value=212.0),
            ],
        }
    )

    async def fake_get_shared_edc_client(**_kwargs):
        return fake_client

    monkeypatch.setattr("src.api.baselines.get_shared_edc_client", fake_get_shared_edc_client)

    first_response = await client.get(f"/api/baselines/{PRIMARY_BASELINE_ID}")
    second_response = await client.get(f"/api/baselines/{PRIMARY_BASELINE_ID}")
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    payload = first_response.json()
    assert payload["curve_source"] == "formal_db"
    assert payload["power_curve"][0]["value"] == 410.0
    assert payload["voltage_curve"][1]["value"] == 222.0
    assert payload["curves_data"][0]["points"][1]["value"] == 420.0
    assert fake_client.login_calls == 0
    assert fake_client.requests == []


@pytest.mark.asyncio
async def test_definition_preview_curves_fetches_points_via_shared_client(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    fake_client = _FakeSharedEDCClient(
        point_map={
            ("2349", "199"): [
                CurvePoint(timestamp=1000, value=401.0),
                CurvePoint(timestamp=2000, value=402.0),
            ],
            ("2349", "128"): [
                CurvePoint(timestamp=1000, value=221.0),
                CurvePoint(timestamp=2000, value=222.0),
            ],
        }
    )

    async def fake_get_shared_edc_client(**_kwargs):
        return fake_client

    monkeypatch.setattr(
        "src.api.baseline_definitions.get_shared_edc_client",
        fake_get_shared_edc_client,
    )

    response = await client.get(
        "/api/baseline-definitions/def-001/preview-curves",
        params={"heat_id": "heat-001"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["curves_data"][0]["points"][0]["value"] == 401.0
    assert payload["curves_data"][1]["points"][1]["value"] == 222.0
    assert fake_client.login_calls == 1


@pytest.mark.asyncio
async def test_definition_preview_curves_rejects_empty_real_data_when_mock_disabled(
    client, monkeypatch
) -> None:
    settings.enable_mock_dataset = False
    fake_client = _FakeSharedEDCClient()

    async def fake_get_shared_edc_client(**_kwargs):
        return fake_client

    monkeypatch.setattr(
        "src.api.baseline_definitions.get_shared_edc_client",
        fake_get_shared_edc_client,
    )

    response = await client.get(
        "/api/baseline-definitions/def-001/preview-curves",
        params={"heat_id": "heat-001"},
    )
    assert response.status_code == 503
    assert "未获取到真实预览数据" in response.json()["detail"]


@pytest.mark.asyncio
async def test_definition_preview_curves_do_not_fallback_when_mock_enabled(
    client, monkeypatch
) -> None:
    settings.enable_mock_dataset = True
    fake_client = _FakeSharedEDCClient()

    async def fake_get_shared_edc_client(**_kwargs):
        return fake_client

    monkeypatch.setattr(
        "src.api.baseline_definitions.get_shared_edc_client",
        fake_get_shared_edc_client,
    )

    response = await client.get(
        "/api/baseline-definitions/def-001/preview-curves",
        params={"heat_id": "heat-001"},
    )
    assert response.status_code == 503
    assert "未获取到真实预览数据" in response.json()["detail"]


@pytest.mark.asyncio
async def test_definition_preview_job_runs_async_and_reuses_same_job_key(
    client, monkeypatch
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    build_calls = 0

    async def fake_build_preview_curves(**_kwargs):
        nonlocal build_calls
        build_calls += 1
        started.set()
        await release.wait()
        return [
            {
                "metric_id": "metric-001",
                "metric_name": "功率",
                "unit": "kW",
                "color": "#409EFF",
                "edc_channel_id": "2349-199",
                "source_channel_name": "总有功功率",
                "source_channel_label": "SSTW / 总有功功率 / kW",
                "points": [
                    {"timestamp": 1000, "value": 401.0},
                    {"timestamp": 2000, "value": 402.0},
                ],
            }
        ]

    monkeypatch.setattr(
        "src.api.baseline_definitions._build_preview_curves",
        fake_build_preview_curves,
    )

    first_response = await client.post(
        "/api/baseline-definitions/def-001/preview-jobs",
        params={"heat_id": "heat-001"},
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["status"] == "running"
    assert first_payload["curves_data"] == []

    await asyncio.wait_for(started.wait(), timeout=1)

    second_response = await client.post(
        "/api/baseline-definitions/def-001/preview-jobs",
        params={"heat_id": "heat-001"},
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["status"] == "running"
    assert second_payload["job_key"] == first_payload["job_key"]
    assert build_calls == 1

    running_status = await client.get(
        "/api/baseline-definitions/def-001/preview-jobs",
        params={"heat_id": "heat-001"},
    )
    assert running_status.status_code == 200
    assert running_status.json()["status"] == "running"

    release.set()

    preview_payload = None
    for _ in range(20):
        status_response = await client.get(
            "/api/baseline-definitions/def-001/preview-jobs",
            params={"heat_id": "heat-001"},
        )
        assert status_response.status_code == 200
        preview_payload = status_response.json()
        if preview_payload["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)

    assert preview_payload is not None
    assert preview_payload["status"] == "succeeded"
    assert preview_payload["job_key"] == first_payload["job_key"]
    assert preview_payload["curves_data"][0]["points"][0]["value"] == 401.0


@pytest.mark.asyncio
async def test_definition_preview_job_reports_failed_state(client, monkeypatch) -> None:
    async def fake_build_preview_curves(**_kwargs):
        return []

    monkeypatch.setattr(
        "src.api.baseline_definitions._build_preview_curves",
        fake_build_preview_curves,
    )

    start_response = await client.post(
        "/api/baseline-definitions/def-001/preview-jobs",
        params={"heat_id": "heat-001"},
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    failed_payload = None
    for _ in range(20):
        status_response = await client.get(
            "/api/baseline-definitions/def-001/preview-jobs",
            params={"heat_id": "heat-001"},
        )
        assert status_response.status_code == 200
        failed_payload = status_response.json()
        if failed_payload["status"] == "failed":
            break
        await asyncio.sleep(0.01)

    assert failed_payload is not None
    assert failed_payload["status"] == "failed"
    assert "未获取到真实预览数据" in failed_payload["last_error"]


@pytest.mark.asyncio
async def test_baseline_definition_crud_and_metric_workflow(client) -> None:
    list_resp = await client.get("/api/baseline-definitions")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 2
    instance_counts = {item["id"]: item["instance_count"] for item in list_resp.json()["items"]}
    assert instance_counts["def-001"] == 1
    assert instance_counts["def-002"] == 1

    create_resp = await client.post(
        "/api/baseline-definitions",
        json={
            "definition_name": "测试定义",
            "description": "自动化回归定义",
            "expected_duration_minutes": 40,
            "metrics": [{"name": "氧含量", "unit": "%", "color": "#7c3aed", "sort_order": 1}],
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    definition_id = created["id"]
    assert created["definition_name"] == "测试定义"
    assert created["instance_count"] == 0
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
    updated_metric = next(
        metric for metric in metric_updated["metrics"] if metric["id"] == added_metric["id"]
    )
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
async def test_baseline_crud_publish_disable_and_delete(client, monkeypatch) -> None:
    async def fake_load_preview_curves_for_selection(
        *, definition_id, selected_start_time, selected_end_time
    ):
        return [
            {
                "metric_id": "001",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#1152d4",
                "points": [
                    {"timestamp": int(selected_start_time.timestamp() * 1000), "value": 410.0},
                    {"timestamp": int(selected_end_time.timestamp() * 1000), "value": 420.0},
                ],
            },
            {
                "metric_id": "002",
                "metric_name": "A相电压",
                "unit": "V",
                "color": "#67C23A",
                "points": [
                    {"timestamp": int(selected_start_time.timestamp() * 1000), "value": 220.0},
                    {"timestamp": int(selected_end_time.timestamp() * 1000), "value": 222.0},
                ],
            },
        ]

    monkeypatch.setattr(
        "src.api.baselines._load_preview_curves_for_selection",
        fake_load_preview_curves_for_selection,
    )

    list_resp = await client.get("/api/baselines", params={"page_size": 10})
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 2

    active_resp = await client.get("/api/baselines/active")
    assert active_resp.status_code == 200
    assert active_resp.json()["status"] == "published"
    assert active_resp.json()["id"] == PRIMARY_BASELINE_ID

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

    definition_resp = await client.get("/api/baseline-definitions/def-001")
    assert definition_resp.status_code == 200
    assert definition_resp.json()["instance_count"] == 2

    detail_resp = await client.get(f"/api/baselines/{baseline_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["definition_id"] == "def-001"
    assert detail_data["curve_source"] == "formal_db"
    assert detail_data["curve_source"] != "demo_curve"
    assert len(detail_data["curves_data"]) >= 1

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

    activate_resp = await client.post(f"/api/baselines/{baseline_id}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["id"] == baseline_id

    active_after_activate = await client.get("/api/baselines/active")
    assert active_after_activate.status_code == 200
    assert active_after_activate.json()["id"] == baseline_id

    update_published_resp = await client.patch(
        f"/api/baselines/{baseline_id}",
        json={"description": "不应该成功"},
    )
    assert update_published_resp.status_code == 400

    disable_resp = await client.post(f"/api/baselines/{baseline_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"

    active_after_disable = await client.get("/api/baselines/active")
    assert active_after_disable.status_code == 200
    assert active_after_disable.json()["id"] != baseline_id

    delete_disabled_resp = await client.delete(f"/api/baselines/{baseline_id}")
    assert delete_disabled_resp.status_code == 400


@pytest.mark.asyncio
async def test_baseline_mutations_invalidate_compare_caches(client) -> None:
    _seed_compare_caches()

    update_resp = await client.patch(
        f"/api/baselines/{SECONDARY_BASELINE_ID}",
        json={"name": "高功率基线 v2"},
    )
    assert update_resp.status_code == 200
    assert _HEAT_COMPARE_CACHE["entries"] == {}
    assert _COMPARE_BASELINE_CACHE["entries"] == {}
    assert _COMPARE_CHANNEL_CURVE_CACHE["entries"] == {}

    _seed_compare_caches()

    publish_resp = await client.post(f"/api/baselines/{SECONDARY_BASELINE_ID}/publish")
    assert publish_resp.status_code == 200
    assert _HEAT_COMPARE_CACHE["entries"] == {}
    assert _COMPARE_BASELINE_CACHE["entries"] == {}
    assert _COMPARE_CHANNEL_CURVE_CACHE["entries"] == {}


@pytest.mark.asyncio
async def test_baseline_delete_draft_and_reject_disabled_definition(client, monkeypatch) -> None:
    async def fake_load_preview_curves_for_selection(
        *, definition_id, selected_start_time, selected_end_time
    ):
        return [
            {
                "metric_id": "001",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#1152d4",
                "points": [
                    {"timestamp": int(selected_start_time.timestamp() * 1000), "value": 410.0},
                    {"timestamp": int(selected_end_time.timestamp() * 1000), "value": 420.0},
                ],
            },
            {
                "metric_id": "002",
                "metric_name": "A相电压",
                "unit": "V",
                "color": "#67C23A",
                "points": [
                    {"timestamp": int(selected_start_time.timestamp() * 1000), "value": 220.0},
                    {"timestamp": int(selected_end_time.timestamp() * 1000), "value": 222.0},
                ],
            },
        ]

    monkeypatch.setattr(
        "src.api.baselines._load_preview_curves_for_selection",
        fake_load_preview_curves_for_selection,
    )

    disable_definition_resp = await client.post("/api/baseline-definitions/def-001/disable")
    assert disable_definition_resp.status_code == 200

    create_with_disabled_definition = await client.post(
        "/api/baselines",
        json={
            "name": "无效基线",
            "definition_id": "def-001",
            "source_heat_id": "heat-001",
            "selected_start_time": "2026-03-12T10:00:00Z",
            "selected_end_time": "2026-03-12T10:45:00Z",
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
            "selected_start_time": "2026-03-12T10:00:00Z",
            "selected_end_time": "2026-03-12T10:45:00Z",
            "tolerance_percent": 10,
        },
    )
    assert create_resp.status_code == 201
    baseline_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/baselines/{baseline_id}")
    assert delete_resp.status_code == 200

    get_deleted = await client.get(f"/api/baselines/{baseline_id}")
    assert get_deleted.status_code == 404


@pytest.mark.asyncio
async def test_baseline_detail_prefers_edc_curves_when_available(client, monkeypatch) -> None:
    async def fake_hydrate_baseline_item(item):
        curves_data = item.get("curves_data") or [
            {
                "metric_id": "metric-power",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#1152d4",
                "edc_channel_id": "2349-199",
                "source_channel_name": "总有功功率",
                "source_channel_label": "测试设备 / 总有功功率 / kW",
                "points": [],
            }
        ]
        curves_data[0]["points"] = [
            {"timestamp": 1000, "value": 301.0},
            {"timestamp": 2000, "value": 302.0},
        ]
        return {
            **item,
            "curve_source": "live_edc",
            "power_curve": [
                {"timestamp": 1000, "value": 301.0},
                {"timestamp": 2000, "value": 302.0},
            ],
            "voltage_curve": [
                {"timestamp": 1000, "value": 211.0},
                {"timestamp": 2000, "value": 212.0},
            ],
            "curves_data": curves_data,
        }

    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)

    response = await client.get(f"/api/baselines/{PRIMARY_BASELINE_ID}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["curve_source"] == "live_edc"
    assert payload["power_curve"][0]["value"] == 301.0
    assert payload["curves_data"][0]["points"][1]["value"] == 302.0


@pytest.mark.asyncio
async def test_baseline_detail_only_uses_demo_curves_in_showtime_mode(client, monkeypatch) -> None:
    async def fake_load_baseline_curves_from_edc(_item):
        return None

    monkeypatch.setattr(
        "src.api.baselines._load_baseline_curves_from_edc",
        fake_load_baseline_curves_from_edc,
    )

    default_response = await client.get(f"/api/baselines/{PRIMARY_BASELINE_ID}")
    assert default_response.status_code == 200
    default_payload = default_response.json()
    assert default_payload["curve_source"] == "formal_db"
    assert len(default_payload["curves_data"]) > 0
    assert len(default_payload["power_curve"]) > 0
    assert len(default_payload["voltage_curve"]) > 0

    showtime_response = await client.get(
        f"/api/baselines/{PRIMARY_BASELINE_ID}",
        headers=SHOWTIME_HEADERS,
    )
    assert showtime_response.status_code == 200
    showtime_payload = showtime_response.json()
    assert showtime_payload["curve_source"] == "formal_db"
    assert len(showtime_payload["curves_data"]) > 0
    assert len(showtime_payload["power_curve"]) > 0
    assert len(showtime_payload["voltage_curve"]) > 0

    default_again_response = await client.get(f"/api/baselines/{PRIMARY_BASELINE_ID}")
    assert default_again_response.status_code == 200
    default_again_payload = default_again_response.json()
    assert default_again_payload["curve_source"] == "formal_db"
    assert len(default_again_payload["curves_data"]) > 0
    assert len(default_again_payload["power_curve"]) > 0
    assert len(default_again_payload["voltage_curve"]) > 0
