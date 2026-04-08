"""炉次 API 测试。"""

import asyncio
from datetime import datetime, timedelta

import pytest

from src.api.baseline_definitions import _resolve_preview_window
from src.api.baselines import _BASELINE_STORE, _resolve_baseline_time_window
from src.api.settings import (
    _CHANNEL_ROLE_BINDING_STORE,
    _SETTINGS_STORE,
    get_plant_timezone,
)
from src.runtime_state import load_runtime_state, persist_runtime_state
from src.schemas.common import CurvePoint
from src.time_utils import from_timestamp_ms, plant_date_of

FORMAL_PRIMARY_BASELINE_ID = "def-001:001"
FORMAL_SECONDARY_BASELINE_ID = "def-002:001"


def _build_live_power_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = int(
                (start + timedelta(minutes=offset_minutes + index)).timestamp() * 1000
            )
            points.append(CurvePoint(timestamp=timestamp, value=value))

    append_block(0, 10, 42.0)
    append_block(10, 30, 124.0)
    append_block(40, 12, 46.0)
    append_block(52, 28, 129.0)
    append_block(80, 10, 38.0)
    return points


def _build_live_power_points_with_heat_count(start: datetime, heat_count: int) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    cursor = 0
    for _index in range(heat_count):
        for offset in range(8):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=42.0))
        cursor += 8
        for offset in range(28):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=128.0))
        cursor += 28
    for offset in range(8):
        timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
        points.append(CurvePoint(timestamp=timestamp, value=41.0))
    return points


def _shift_curve_points(points: list[CurvePoint], *, seconds: int) -> list[CurvePoint]:
    delta_ms = seconds * 1000
    return [
        CurvePoint(timestamp=int(point.timestamp) + delta_ms, value=float(point.value))
        for point in points
    ]


def _build_legacy_live_heat_id(*, start_time: str, end_time: str) -> str:
    start_timestamp = int(datetime.fromisoformat(start_time).timestamp() * 1000)
    end_timestamp = int(datetime.fromisoformat(end_time).timestamp() * 1000)
    return f"live-heat-{start_timestamp}-{end_timestamp}"


def _build_test_live_context(
    *,
    baseline_id: str | None = FORMAL_PRIMARY_BASELINE_ID,
    suid: str = "2349",
    cuid: str = "199",
    channel_id: str = "2349-199",
    expected_duration_minutes: int = 30,
) -> dict[str, object]:
    import src.api.heats as heats_module

    return heats_module._build_live_heat_context(
        channel={
            "id": channel_id,
            "suid": suid,
            "cuid": cuid,
            "device_name": "测试设备",
            "channel_name": "功率",
            "unit": "kW",
        },
        baseline_id=baseline_id,
        expected_duration_minutes=expected_duration_minutes,
    )


def _formal_baseline_effective_from(
    baseline_id: str = FORMAL_PRIMARY_BASELINE_ID,
) -> datetime | None:
    baseline = _BASELINE_STORE.get(baseline_id)
    return baseline.get("effective_from") if baseline else None


def _seed_runtime_heat(
    *,
    heat_id: str = "runtime-heat-001",
    baseline_id: str = FORMAL_PRIMARY_BASELINE_ID,
    record_source: str = "active_runtime",
    start_time: datetime | None = None,
) -> str:
    import src.api.heats as heats_module

    runtime_start = start_time or datetime(2026, 3, 19, 8, 0, 0)
    item = {
        "id": heat_id,
        "heat_no": f"H{runtime_start.strftime('%Y%m%d-%H%M')}",
        "description": "运行态炉次",
        "start_time": runtime_start,
        "end_time": runtime_start + timedelta(minutes=30),
        "completion_status": "in_progress"
        if record_source == "active_runtime"
        else "completed",
        "last_point_at": runtime_start + timedelta(minutes=30),
        "baseline_id": baseline_id,
        "baseline_version_id": baseline_id,
        "baseline_effective_from": _formal_baseline_effective_from(baseline_id),
        "baseline_ids": [baseline_id],
        "deviation_percent": None,
        "avg_deviation_percent": None,
        "time_offset_percent": None,
        "mismatch_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": record_source,
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "normal" if record_source != "active_runtime" else "pending",
        "temperature": None,
        "record_source": record_source,
        "current_curve_source": "live_edc",
        "baseline_curve_source": "none",
        "created_at": runtime_start,
        "power_curve": [
            CurvePoint(
                timestamp=int((runtime_start + timedelta(minutes=index)).timestamp() * 1000),
                value=430.0 + index,
            )
            for index in range(4)
        ],
        "voltage_curve": [
            CurvePoint(
                timestamp=int((runtime_start + timedelta(minutes=index)).timestamp() * 1000),
                value=221.0 + index,
            )
            for index in range(4)
        ],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
    }

    if record_source == "previous_runtime":
        heats_module._PREVIOUS_HEAT_RUNTIME[heat_id] = item
    else:
        heats_module._ACTIVE_HEAT_RUNTIME[heat_id] = item
    return heat_id


async def _pick_heat_id(client, *, require_baseline: bool = True) -> str:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    assert list_resp.status_code == 200
    return next(
        item["id"]
        for item in list_resp.json()["items"]
        if not require_baseline or item.get("baseline_id") is not None
    )


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
async def test_list_heats_with_pagination(client) -> None:
    response = await client.get("/api/heats", params={"page": 1, "page_size": 10})
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["items"]) <= 10
    assert data["total"] >= len(data["items"])


@pytest.mark.asyncio
async def test_list_heats_filter_by_status(client) -> None:
    response = await client.get("/api/heats", params={"status": "abnormal", "page_size": 20})
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "abnormal" for item in data["items"])


@pytest.mark.asyncio
async def test_list_heats_includes_active_runtime_item(client) -> None:
    import src.api.heats as heats_module

    start_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=5)
    active_id = "active-heat-001"
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._ACTIVE_HEAT_RUNTIME[active_id] = {
        "id": active_id,
        "heat_no": "H20260402-2145",
        "description": "进行中炉次",
        "start_time": start_time,
        "end_time": start_time + timedelta(minutes=5),
        "completion_status": "in_progress",
        "last_point_at": start_time + timedelta(minutes=5),
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_effective_from": _formal_baseline_effective_from(),
        "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
        "deviation_percent": None,
        "avg_deviation_percent": None,
        "time_offset_percent": None,
        "mismatch_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "live_edc",
        "created_at": start_time,
        "power_curve": [
            CurvePoint(timestamp=int((start_time + timedelta(minutes=index)).timestamp() * 1000), value=410.0 + index)
            for index in range(6)
        ],
        "voltage_curve": [],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
    }
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = start_time + timedelta(minutes=5)
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_failure_count"] = 0
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_status"] = "idle"

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    active_item = next(item for item in payload["items"] if item["id"] == active_id)
    assert active_item["completion_status"] == "in_progress"
    assert active_item["record_source"] == "active_runtime"
    assert active_item["baseline_version_id"] == FORMAL_PRIMARY_BASELINE_ID
    assert payload["snapshot_status"] == "ready"
    assert active_item["runtime_snapshot_status"] == "ready"
    assert active_item["realtime_current"] is True


@pytest.mark.asyncio
async def test_list_heats_marks_active_runtime_as_stale_when_watermark_is_old(client) -> None:
    import src.api.heats as heats_module

    start_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=20)
    active_id = "active-heat-stale"
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._ACTIVE_HEAT_RUNTIME[active_id] = {
        "id": active_id,
        "heat_no": "H20260402-2100",
        "description": "过期快照炉次",
        "start_time": start_time,
        "end_time": start_time + timedelta(minutes=8),
        "completion_status": "in_progress",
        "last_point_at": start_time + timedelta(minutes=8),
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_effective_from": _formal_baseline_effective_from(),
        "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
        "deviation_percent": None,
        "avg_deviation_percent": None,
        "time_offset_percent": None,
        "mismatch_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "live_edc",
        "created_at": start_time,
        "power_curve": [],
        "voltage_curve": [],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
    }
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = datetime.now() - timedelta(minutes=10)
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_failure_count"] = 0
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_status"] = "idle"

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    active_item = next(item for item in payload["items"] if item["id"] == active_id)
    assert payload["snapshot_status"] == "stale"
    assert active_item["runtime_snapshot_status"] == "stale"
    assert active_item["realtime_current"] is False


@pytest.mark.asyncio
async def test_list_heats_marks_active_runtime_as_untrusted_after_repeated_refresh_failures(
    client,
) -> None:
    import src.api.heats as heats_module

    start_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=2)
    active_id = "active-heat-error"
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._ACTIVE_HEAT_RUNTIME[active_id] = {
        "id": active_id,
        "heat_no": "H20260402-2140",
        "description": "错误态炉次",
        "start_time": start_time,
        "end_time": start_time + timedelta(minutes=2),
        "completion_status": "in_progress",
        "last_point_at": start_time + timedelta(minutes=2),
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_effective_from": _formal_baseline_effective_from(),
        "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
        "deviation_percent": None,
        "avg_deviation_percent": None,
        "time_offset_percent": None,
        "mismatch_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "live_edc",
        "created_at": start_time,
        "power_curve": [],
        "voltage_curve": [],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
    }
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = datetime.now() - timedelta(seconds=30)
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_failure_count"] = 3
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_status"] = "idle"
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_error"] = "upstream_timeout"

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    active_item = next(item for item in payload["items"] if item["id"] == active_id)
    assert payload["snapshot_status"] == "error"
    assert payload["refresh_failure_count"] == 3
    assert payload["refresh_error"] == "upstream_timeout"
    assert active_item["runtime_snapshot_status"] == "error"
    assert active_item["realtime_current"] is False


@pytest.mark.asyncio
async def test_active_runtime_state_persists_and_restores(client) -> None:
    import src.api.heats as heats_module

    start_time = datetime(2026, 4, 1, 10, 20, 0)
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_ID_ALIAS_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME["active-heat-restore"] = {
        "id": "active-heat-restore",
        "heat_no": "H20260401-1020",
        "description": None,
        "start_time": start_time,
        "end_time": start_time + timedelta(minutes=7),
        "completion_status": "in_progress",
        "last_point_at": start_time + timedelta(minutes=7),
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_effective_from": _formal_baseline_effective_from(),
        "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
        "deviation_percent": None,
        "avg_deviation_percent": None,
        "time_offset_percent": None,
        "mismatch_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "live_edc",
        "created_at": start_time,
        "power_curve": [],
        "voltage_curve": [],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
    }
    heats_module._PREVIOUS_HEAT_RUNTIME["previous-heat-restore"] = {
        "id": "previous-heat-restore",
        "heat_no": "H20260401-0942",
        "description": None,
        "start_time": start_time - timedelta(minutes=38),
        "end_time": start_time - timedelta(minutes=2),
        "completion_status": "completed",
        "last_point_at": start_time - timedelta(minutes=2),
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_effective_from": _formal_baseline_effective_from(),
        "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
        "deviation_percent": None,
        "avg_deviation_percent": None,
        "time_offset_percent": None,
        "mismatch_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "previous_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "normal",
        "temperature": None,
        "record_source": "previous_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "live_edc",
        "created_at": start_time - timedelta(minutes=38),
        "power_curve": [],
        "voltage_curve": [],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
    }
    heats_module._HEAT_ID_ALIAS_STORE["legacy-previous-heat"] = "previous-heat-restore"
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_status"] = "ready"
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_status"] = "idle"
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = start_time + timedelta(minutes=7)

    await persist_runtime_state(
        "active_heat_runtime",
        "previous_heat_runtime",
        "heat_id_aliases",
        "heat_runtime_refresh_meta",
    )

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_ID_ALIAS_STORE.clear()
    heats_module._HEAT_RUNTIME_REFRESH_META.clear()

    await load_runtime_state()

    restored = heats_module._ACTIVE_HEAT_RUNTIME["active-heat-restore"]
    assert restored["completion_status"] == "in_progress"
    assert restored["baseline_version_id"] == FORMAL_PRIMARY_BASELINE_ID
    restored_previous = heats_module._PREVIOUS_HEAT_RUNTIME["previous-heat-restore"]
    assert restored_previous["record_source"] == "previous_runtime"
    assert heats_module._HEAT_ID_ALIAS_STORE["legacy-previous-heat"] == "previous-heat-restore"
    assert heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_status"] == "ready"


@pytest.mark.asyncio
async def test_get_heat_not_found(client) -> None:
    response = await client.get("/api/heats/not-exists")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_heat_curve_and_compare(client) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    heat_id = next(
        item["id"] for item in list_resp.json()["items"] if item.get("baseline_id") is not None
    )

    curve_resp = await client.get(f"/api/heats/{heat_id}/curve")
    assert curve_resp.status_code == 200
    curve_data = curve_resp.json()
    assert len(curve_data["power_curve"]) > 0

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    compare_data = compare_resp.json()
    assert "deviation_ranges" in compare_data
    assert compare_data["heat"]["id"] == heat_id
    assert len(compare_data["baselines"]) > 0
    first_baseline = compare_data["baselines"][0]
    assert len(first_baseline["metric_curves"]) >= 2
    assert [item["metric_key"] for item in first_baseline["metric_curves"][:2]] == [
        "power",
        "voltage",
    ]
    assert compare_data["baseline"]["id"] == compare_data["baselines"][0]["baseline"]["id"]
    assert compare_data["heat"]["baseline_id"]
    assert all("source_channel_label" in item for item in first_baseline["metric_curves"])
    assert all("source_channel_name" in item for item in first_baseline["metric_curves"])


@pytest.mark.asyncio
async def test_heat_list_and_compare_follow_active_default_baseline(client, monkeypatch) -> None:
    async def fake_load_preview_curves_for_selection(
        *, definition_id, selected_start_time, selected_end_time
    ):
        return [
            {
                "metric_id": "001",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#409EFF",
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

    source_heat_id = await _pick_heat_id(client)
    source_heat_resp = await client.get(f"/api/heats/{source_heat_id}")
    assert source_heat_resp.status_code == 200
    source_heat = source_heat_resp.json()

    create_resp = await client.post(
        "/api/baselines",
        json={
            "name": "默认黄金基线测试",
            "description": "用于验证炉次默认基线口径",
            "definition_id": "def-001",
            "source_heat_id": source_heat_id,
            "selected_start_time": source_heat["start_time"],
            "selected_end_time": source_heat["end_time"],
            "tolerance_percent": 9.5,
        },
    )
    assert create_resp.status_code == 201
    baseline_id = create_resp.json()["id"]

    publish_resp = await client.post(f"/api/baselines/{baseline_id}/publish")
    assert publish_resp.status_code == 200

    activate_resp = await client.post(f"/api/baselines/{baseline_id}/activate")
    assert activate_resp.status_code == 200

    list_resp = await client.get("/api/heats", params={"status": "normal", "page_size": 20})
    assert list_resp.status_code == 200
    heat_item = list_resp.json()["items"][0]
    assert heat_item["baseline_id"] != baseline_id
    assert heat_item["deviation_percent"] is not None

    compare_resp = await client.get(f"/api/heats/{heat_item['id']}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["baseline"]["id"] == payload["baselines"][0]["baseline"]["id"]
    assert all(item["baseline"]["id"] != baseline_id for item in payload["baselines"])


@pytest.mark.asyncio
async def test_mock_stream_endpoints_are_disabled_when_mock_dataset_is_off(client) -> None:
    list_response = await client.get("/api/heats/stream/mock")
    assert list_response.status_code == 503
    assert "mock 数据集未开启" in list_response.json()["detail"]

    ingest_response = await client.post("/api/heats/stream/mock/ingest")
    assert ingest_response.status_code == 503
    assert "mock 数据集未开启" in ingest_response.json()["detail"]


@pytest.mark.asyncio
async def test_heat_compare_prefers_edc_curves_when_available(client, monkeypatch) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 501.0
    assert first_baseline["metric_curves"][1]["current_curve"][1]["value"] == 332.0


@pytest.mark.asyncio
async def test_heat_compare_exposes_context_window_and_prefers_runtime_context_for_display_curves(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()
    runtime_item = heats_module._ACTIVE_HEAT_RUNTIME[heat_id]
    runtime_item["context_start_time"] = runtime_item["start_time"] - timedelta(minutes=40)
    runtime_item["context_end_time"] = runtime_item["end_time"] + timedelta(minutes=25)

    observed_windows: list[tuple[datetime, datetime]] = []

    async def fake_load_channel_curves_from_edc(*, start_time, end_time, **_kwargs):
        observed_windows.append((start_time, end_time))
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["heat"]["context_start_time"] == int(
        runtime_item["context_start_time"].timestamp() * 1000
    )
    assert payload["heat"]["context_end_time"] == int(
        runtime_item["context_end_time"].timestamp() * 1000
    )
    assert len(observed_windows) == 2
    assert observed_windows[1][0] == runtime_item["context_start_time"]
    assert observed_windows[1][1] == runtime_item["context_end_time"]


@pytest.mark.asyncio
async def test_get_heat_curve_prefers_live_heat_curves(client, monkeypatch) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()

    async def fake_load_heat_curves_from_edc(_item):
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)

    curve_resp = await client.get(f"/api/heats/{heat_id}/curve")
    assert curve_resp.status_code == 200
    payload = curve_resp.json()
    assert payload["power_curve"][0]["value"] == 611.0
    assert payload["voltage_curve"][1]["value"] == 352.0


@pytest.mark.asyncio
async def test_heat_compare_falls_back_to_direct_live_voltage_curve(client, monkeypatch) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ]
        }

    async def fake_load_heat_curves_from_edc(_item):
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    async def fake_load_heat_curves_from_edc_window(_item, *, start_time, end_time):
        return await fake_load_heat_curves_from_edc(_item)

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window",
        fake_load_heat_curves_from_edc_window,
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 501.0
    assert first_baseline["metric_curves"][1]["current_curve"][1]["value"] == 352.0


@pytest.mark.asyncio
async def test_heat_compare_accepts_dict_live_curves_without_500(client, monkeypatch) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {}

    async def fake_load_heat_curves_from_edc(_item):
        return {
            "power": [
                {"timestamp": 1000, "value": 611.0},
                {"timestamp": 2000, "value": 612.0},
            ],
            "voltage": [
                {"timestamp": 1000, "value": 351.0},
                {"timestamp": 2000, "value": 352.0},
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["heat"]["power_curve"][0]["value"] == 611.0
    assert payload["baselines"][0]["metric_curves"][0]["current_curve"][1]["value"] == 612.0


@pytest.mark.asyncio
async def test_heat_compare_prefers_hydrated_baseline_metric_curves(client, monkeypatch) -> None:
    async def fake_load_heat_curves_from_edc(_item):
        return None

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {}

    async def fake_hydrate_baseline_item(item):
        return {
            **item,
            "curve_source": "live_edc",
            "power_curve": [
                {"timestamp": 1000, "value": 701.0},
                {"timestamp": 2000, "value": 702.0},
            ],
            "voltage_curve": [
                {"timestamp": 1000, "value": 381.0},
                {"timestamp": 2000, "value": 382.0},
            ],
            "curves_data": [
                {
                    "metric_id": "001",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "points": [
                        {"timestamp": 1000, "value": 701.0},
                        {"timestamp": 2000, "value": 702.0},
                    ],
                },
                {
                    "metric_id": "002",
                    "metric_name": "电压",
                    "unit": "V",
                    "color": "#67C23A",
                    "points": [
                        {"timestamp": 1000, "value": 381.0},
                        {"timestamp": 2000, "value": 382.0},
                    ],
                },
            ],
        }

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()
    heats_module._COMPARE_BASELINE_CACHE["entries"] = {}

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert payload["baseline"]["power_curve"][0]["value"] == 701.0
    assert first_baseline["metric_curves"][0]["baseline_curve"][0]["value"] == 701.0
    assert first_baseline["metric_curves"][1]["baseline_curve"][1]["value"] == 382.0


@pytest.mark.asyncio
async def test_heat_compare_uses_formal_baseline_metric_series_without_shared_edc_client(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    heat_id = await _pick_heat_id(client)

    async def fail_get_shared_edc_client(**_kwargs):
        raise AssertionError("正式表 compare 不应再回源共享 EDC 基线曲线")

    async def fake_load_heat_curves_from_edc(_item):
        return None

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {}

    monkeypatch.setattr("src.api.baselines.get_shared_edc_client", fail_get_shared_edc_client)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )

    import src.api.heats as heats_module

    heats_module._COMPARE_BASELINE_CACHE["entries"] = {}

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["heat"]["id"] == heat_id
    assert payload["baselines"]


@pytest.mark.asyncio
async def test_heat_compare_rebases_baseline_curve_timestamps_into_current_heat_window(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat(start_time=datetime(2026, 3, 19, 8, 0, 0))

    async def fake_load_heat_curves_from_edc(_item):
        return None

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {}

    async def fake_hydrate_baseline_item(item):
        return {
            **item,
            "curve_source": "live_edc",
            "power_curve": [
                {"timestamp": 1773881543000, "value": 701.0},
                {"timestamp": 1773883343000, "value": 702.0},
            ],
            "voltage_curve": [
                {"timestamp": 1773881543000, "value": 381.0},
                {"timestamp": 1773883343000, "value": 382.0},
            ],
            "curves_data": [
                {
                    "metric_id": "001",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "points": [
                        {"timestamp": 1773881543000, "value": 701.0},
                        {"timestamp": 1773882443000, "value": 705.0},
                        {"timestamp": 1773883343000, "value": 702.0},
                    ],
                },
                {
                    "metric_id": "002",
                    "metric_name": "电压",
                    "unit": "V",
                    "color": "#67C23A",
                    "points": [
                        {"timestamp": 1773881543000, "value": 381.0},
                        {"timestamp": 1773882443000, "value": 383.0},
                        {"timestamp": 1773883343000, "value": 382.0},
                    ],
                },
            ],
        }

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)
    import src.api.heats as heats_module

    heats_module._COMPARE_BASELINE_CACHE["entries"] = {}

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    heat_start_ms = int(payload["heat"]["start_time"])
    heat_end_ms = int(payload["heat"]["end_time"])
    baseline_curve = payload["baselines"][0]["metric_curves"][0]["baseline_curve"]
    assert baseline_curve[0]["timestamp"] == heat_start_ms
    assert baseline_curve[-1]["timestamp"] == heat_end_ms


@pytest.mark.asyncio
async def test_heat_compare_extends_display_current_curves_with_plus_minus_60_minutes(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()

    async def fake_load_channel_curves_from_edc(*, start_time, end_time, **_kwargs):
        duration_minutes = (end_time - start_time).total_seconds() / 60
        if duration_minutes > 120:
            return {
                "2349:199": [
                    CurvePoint(timestamp=1000, value=401.0),
                    CurvePoint(timestamp=2000, value=402.0),
                    CurvePoint(timestamp=3000, value=403.0),
                    CurvePoint(timestamp=4000, value=404.0),
                ],
                "2349:128": [
                    CurvePoint(timestamp=1000, value=301.0),
                    CurvePoint(timestamp=2000, value=302.0),
                    CurvePoint(timestamp=3000, value=303.0),
                    CurvePoint(timestamp=4000, value=304.0),
                ],
            }
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert len(payload["heat"]["power_curve"]) == 2
    assert len(first_baseline["metric_curves"][0]["current_curve"]) == 4
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 401.0


@pytest.mark.asyncio
async def test_heat_compare_display_metric_curves_fall_back_to_display_window_live_curves(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()

    async def fake_load_channel_curves_from_edc(*, start_time, end_time, **_kwargs):
        duration_minutes = (end_time - start_time).total_seconds() / 60
        if duration_minutes > 120:
            return {}
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    async def fake_load_heat_curves_from_edc_window(_item, *, start_time, end_time):
        duration_minutes = (end_time - start_time).total_seconds() / 60
        if duration_minutes > 120:
            return {
                "power": [
                    CurvePoint(timestamp=1000, value=701.0),
                    CurvePoint(timestamp=2000, value=702.0),
                    CurvePoint(timestamp=3000, value=703.0),
                    CurvePoint(timestamp=4000, value=704.0),
                ],
                "voltage": [
                    CurvePoint(timestamp=1000, value=381.0),
                    CurvePoint(timestamp=2000, value=382.0),
                    CurvePoint(timestamp=3000, value=383.0),
                    CurvePoint(timestamp=4000, value=384.0),
                ],
            }
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window",
        fake_load_heat_curves_from_edc_window,
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert len(payload["heat"]["power_curve"]) == 2
    assert payload["heat"]["power_curve"][0]["value"] == 501.0
    assert len(first_baseline["metric_curves"][0]["current_curve"]) == 4
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 701.0
    assert first_baseline["metric_curves"][1]["current_curve"][1]["value"] == 382.0


@pytest.mark.asyncio
async def test_live_heat_inference_deduplicates_concurrent_cold_requests(monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))
    load_calls = 0

    async def fake_load_live_heat_inference_power_points(_channel):
        nonlocal load_calls
        load_calls += 1
        await asyncio.sleep(0.01)
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

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._LIVE_HEAT_CACHE["contexts"] = {}

    first_result, second_result = await asyncio.gather(
        heats_module._get_live_inferred_heat_store(),
        heats_module._get_live_inferred_heat_store(),
    )

    assert load_calls == 1
    assert list(first_result.keys()) == list(second_result.keys())


def test_build_live_heat_lookup_context_uses_explicit_role_binding_instead_of_definition_guessing(
    client,
) -> None:
    import src.api.heats as heats_module

    _CHANNEL_ROLE_BINDING_STORE["live_heat_inference"] = "2349-199"
    for definition in heats_module._DEFINITION_STORE.values():
        for metric in definition.get("metrics", []):
            if isinstance(metric, dict) and metric.get("unit") == "kW":
                metric["edc_channel_id"] = None

    context = heats_module.build_live_heat_lookup_context(
        definition_id="def-001",
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
    )

    assert context is not None
    assert context["channel"]["id"] == "2349-199"
    assert context["baseline_id"] == FORMAL_PRIMARY_BASELINE_ID


def test_live_heat_context_cache_key_changes_with_cutting_mode_and_fixed_interval() -> None:
    import src.api.heats as heats_module

    _SETTINGS_STORE["cutting_mode"]["value"] = "signal_inference"
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = ""
    signal_context = heats_module._build_live_heat_context(
        channel={
            "id": "2349-199",
            "suid": "2349",
            "cuid": "199",
            "device_name": "测试设备",
            "channel_name": "功率",
            "unit": "kW",
        },
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        expected_duration_minutes=30,
    )

    _SETTINGS_STORE["cutting_mode"]["value"] = "fixed_interval"
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = "20"
    fixed_context = heats_module._build_live_heat_context(
        channel={
            "id": "2349-199",
            "suid": "2349",
            "cuid": "199",
            "device_name": "测试设备",
            "channel_name": "功率",
            "unit": "kW",
        },
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        expected_duration_minutes=30,
    )

    assert signal_context["cache_key"] != fixed_context["cache_key"]
    assert "fixed_interval" in fixed_context["cache_key"]


@pytest.mark.asyncio
async def test_cutting_timeline_uses_abnormal_outcome_for_abnormal_heat(client) -> None:
    from src.database import async_session_maker
    from src.models import Heat

    async with async_session_maker() as session:
        heat = await session.get(Heat, "heat-001")
        assert heat is not None
        heat.status = "abnormal"
        await session.commit()

    timeline_resp = await client.get("/api/heats/heat-001/cutting-timeline")
    assert timeline_resp.status_code == 200
    events = timeline_resp.json()["events"]
    assert events[-1]["event_type"] in {"abnormal", "major_issue"}


@pytest.mark.asyncio
async def test_analyze_route_is_removed(client) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 1})
    heat_id = list_resp.json()["items"][0]["id"]

    analyze_resp = await client.post(f"/api/heats/{heat_id}/analyze", json={})
    assert analyze_resp.status_code == 404


@pytest.mark.asyncio
async def test_refresh_heat_runtime_bootstrap_keeps_live_segments_in_runtime_only(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        return live_points

    async def fake_hydrate_baseline_item(item):
        return item

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)
    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    runtime_items = [
        item for item in payload["items"] if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    live_history_items = [
        item
        for item in payload["items"]
        if item["record_source"] == "sealed_history" and item["id"].startswith("live-heat-")
    ]
    assert len(runtime_items) == 2
    assert runtime_items[0]["record_source"] == "active_runtime"
    assert runtime_items[0]["completion_status"] == "in_progress"
    assert runtime_items[1]["record_source"] == "previous_runtime"
    assert runtime_items[1]["completion_status"] == "completed"
    assert live_history_items == []
    assert all(item["current_curve_source"] == "live_edc" for item in runtime_items)
    assert runtime_items[0]["id"].startswith("live-heat-")
    assert any(item["id"] == "heat-001" for item in payload["items"])
    assert payload["snapshot_status"] == "stale"
    active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    assert active_runtime["processing_meta"]["processing_mode"] == "live_incremental"
    assert active_runtime["processing_meta"]["trigger_source"] == "test"
    assert active_runtime["baseline_bindings"]
    assert active_runtime["runtime_metric_series"]


@pytest.mark.asyncio
async def test_refresh_heat_runtime_supports_fixed_interval_cutting_mode_on_bootstrap(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    _SETTINGS_STORE["cutting_mode"]["value"] = "fixed_interval"
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = "15"
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

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    live_items = [item for item in payload["items"] if item["id"].startswith("live-heat-")]
    live_history_items = [
        item
        for item in live_items
        if item["record_source"] == "sealed_history"
    ]

    assert len(live_items) == 2
    assert live_history_items == []
    assert all(item["id"].endswith("-15") for item in live_items)


@pytest.mark.asyncio
async def test_refresh_heat_runtime_rejects_flat_zero_power_signal(client, monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    zero_points = [
        CurvePoint(
            timestamp=int((datetime(2026, 3, 19, 8, 0) + timedelta(minutes=index)).timestamp() * 1000),
            value=0.0,
        )
        for index in range(90)
    ]

    async def fake_load_live_heat_inference_power_points(_channel):
        return zero_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_failure_count"] = 0
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_error"] = None

    refresh_meta = await heats_module.refresh_heat_runtime_state(reason="test")

    assert refresh_meta["refresh_error"] == "no_runtime_heats_inferred"
    list_response = await client.get("/api/heats", params={"page_size": 20})
    assert list_response.status_code == 200
    payload = list_response.json()
    assert all(
        item["record_source"] not in {"active_runtime", "previous_runtime"}
        for item in payload["items"]
    )


@pytest.mark.asyncio
async def test_list_heats_does_not_alias_stale_live_record_into_all_current_rows(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    current_points = _build_live_power_points(datetime(2026, 3, 23, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        return current_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()

    stale_context = _build_test_live_context()
    stale_items = heats_module._infer_live_heat_items(
        context=stale_context,
        points=_build_live_power_points(datetime(2026, 3, 19, 8, 0)),
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        expected_duration_minutes=30,
    )
    stale_item = next(iter(stale_items.values()))
    heats_module._HEAT_STORE[stale_item["id"]] = {
        **stale_item,
        "deviation_percent": 697.4947,
        "avg_deviation_percent": 697.4947,
    }

    await heats_module.refresh_heat_runtime_state(reason="test")

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    runtime_items = [
        item for item in payload["items"] if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    history_items = [item for item in payload["items"] if item["record_source"] == "sealed_history"]
    assert len(runtime_items) == 2
    assert all(from_timestamp_ms(item["start_time"]).date() == datetime(2026, 3, 23).date() for item in runtime_items)
    assert history_items
    assert all(item["deviation_percent"] is not None for item in runtime_items)
    assert all(item["avg_deviation_percent"] is not None for item in runtime_items)
    assert all(item["deviation_percent"] != 697.4947 for item in runtime_items)
    assert all(item["avg_deviation_percent"] != 697.4947 for item in runtime_items)


@pytest.mark.asyncio
async def test_refresh_heat_runtime_does_not_duplicate_current_and_previous_from_legacy_history(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    current_points = _build_live_power_points(datetime(2026, 3, 23, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        return current_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()

    for item in heats_module._infer_live_heat_items(
        context=_build_test_live_context(),
        points=current_points,
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        expected_duration_minutes=30,
    ).values():
        heats_module._HEAT_STORE[item["id"]] = item

    await heats_module.refresh_heat_runtime_state(reason="test")

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    runtime_items = [
        item for item in payload["items"] if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    assert len(runtime_items) == 2
    assert runtime_items[0]["record_source"] == "active_runtime"
    assert runtime_items[1]["record_source"] == "previous_runtime"
    assert any(item["id"] == "heat-001" for item in payload["items"])


@pytest.mark.asyncio
async def test_runtime_heat_ids_can_resolve_preview_and_baseline_windows(
    client, monkeypatch
) -> None:
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

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    list_response = await client.get("/api/heats", params={"page_size": 20})
    heat_id = list_response.json()["items"][0]["id"]

    baseline_window = await _resolve_baseline_time_window({"source_heat_id": heat_id})
    preview_window = await _resolve_preview_window(heat_id, definition_id="def-001")
    assert (baseline_window[1] - baseline_window[0]).total_seconds() >= 20 * 60
    assert plant_date_of(preview_window[0], get_plant_timezone()) == plant_date_of(
        baseline_window[0],
        get_plant_timezone(),
    )


@pytest.mark.asyncio
async def test_live_inferred_canonical_id_stays_stable_across_small_boundary_changes(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points_v1 = _build_live_power_points(datetime(2026, 3, 19, 8, 0))
    live_points_v2 = _shift_curve_points(live_points_v1, seconds=20)
    current_points = live_points_v1

    async def fake_load_live_heat_inference_power_points(_channel):
        return current_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    first_response = await client.get("/api/heats", params={"page_size": 20})
    assert first_response.status_code == 200
    first_ids = [item["id"] for item in first_response.json()["items"]]

    current_points = live_points_v2
    await heats_module.refresh_heat_runtime_state(reason="test")

    second_response = await client.get("/api/heats", params={"page_size": 20})
    assert second_response.status_code == 200
    second_ids = [item["id"] for item in second_response.json()["items"]]

    assert first_ids
    assert second_ids == first_ids


@pytest.mark.asyncio
async def test_active_runtime_ids_remain_resolvable_across_detail_compare_and_timeline(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    start_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=50)
    current_points = _build_live_power_points(start_time)

    async def fake_load_live_heat_inference_power_points(_channel):
        return current_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    list_response = await client.get("/api/heats", params={"page_size": 20})
    assert list_response.status_code == 200
    active_item = next(item for item in list_response.json()["items"] if item["completion_status"] == "in_progress")

    detail_response = await client.get(f"/api/heats/{active_item['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == active_item["id"]

    compare_response = await client.get(f"/api/heats/{active_item['id']}/compare")
    assert compare_response.status_code == 200
    assert compare_response.json()["heat"]["id"] == active_item["id"]
    assert compare_response.json()["max_deviation"] == pytest.approx(
        active_item["deviation_percent"]
    )

    timeline_response = await client.get(f"/api/heats/{active_item['id']}/cutting-timeline")
    assert timeline_response.status_code == 200
    assert timeline_response.json()["heat_id"] == active_item["id"]


@pytest.mark.asyncio
async def test_refresh_heat_runtime_only_keeps_current_and_previous_as_runtime(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points_with_heat_count(datetime(2026, 3, 19, 8, 0), 4)

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

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_ID_ALIAS_STORE.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()

    runtime_items = [
        item for item in payload["items"] if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    history_items = [item for item in payload["items"] if item["record_source"] == "sealed_history"]
    live_history_items = [item for item in history_items if item["id"].startswith("live-heat-")]
    assert len(runtime_items) == 2
    assert runtime_items[0]["record_source"] == "active_runtime"
    assert runtime_items[1]["record_source"] == "previous_runtime"
    assert live_history_items == []
    assert any(item["id"] == "heat-001" for item in history_items)


@pytest.mark.asyncio
async def test_previous_runtime_id_stays_resolvable_after_rollover(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points_v1 = _build_live_power_points_with_heat_count(datetime(2026, 3, 19, 8, 0), 3)
    live_points_v2 = _shift_curve_points(
        _build_live_power_points_with_heat_count(datetime(2026, 3, 19, 8, 0), 4),
        seconds=240,
    )
    current_points = live_points_v1

    async def fake_load_live_heat_inference_power_points(_channel):
        return current_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_ID_ALIAS_STORE.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")
    first_list_response = await client.get("/api/heats", params={"page_size": 20})
    assert first_list_response.status_code == 200
    first_payload = first_list_response.json()
    previous_runtime_item = next(
        item for item in first_payload["items"] if item["record_source"] == "previous_runtime"
    )

    current_points = live_points_v2
    await heats_module.refresh_heat_runtime_state(reason="test")

    detail_response = await client.get(f"/api/heats/{previous_runtime_item['id']}")
    assert detail_response.status_code == 200

    compare_response = await client.get(f"/api/heats/{previous_runtime_item['id']}/compare")
    assert compare_response.status_code == 200

    timeline_response = await client.get(
        f"/api/heats/{previous_runtime_item['id']}/cutting-timeline"
    )
    assert timeline_response.status_code == 200


@pytest.mark.asyncio
async def test_previous_runtime_deviation_stays_frozen_while_active_id_is_unchanged(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    base_points = _build_live_power_points_with_heat_count(datetime(2026, 3, 19, 8, 0), 3)
    current_points = list(base_points)

    async def fake_load_live_heat_inference_power_points(_channel):
        return current_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: _build_test_live_context(),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_ID_ALIAS_STORE.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")
    first_payload = (await client.get("/api/heats", params={"page_size": 20})).json()
    first_active_item = next(
        item for item in first_payload["items"] if item["record_source"] == "active_runtime"
    )
    first_previous_item = next(
        item for item in first_payload["items"] if item["record_source"] == "previous_runtime"
    )
    assert first_previous_item["deviation_percent"] is not None

    current_points = [
        CurvePoint(timestamp=int(point.timestamp), value=float(point.value) + 20.0)
        for point in base_points
    ]
    await heats_module.refresh_heat_runtime_state(reason="test")

    second_payload = (await client.get("/api/heats", params={"page_size": 20})).json()
    second_active_item = next(
        item for item in second_payload["items"] if item["record_source"] == "active_runtime"
    )
    second_previous_item = next(
        item for item in second_payload["items"] if item["record_source"] == "previous_runtime"
    )

    assert second_active_item["id"] == first_active_item["id"]
    assert second_previous_item["id"] == first_previous_item["id"]
    assert second_previous_item["deviation_percent"] == pytest.approx(
        first_previous_item["deviation_percent"]
    )

@pytest.mark.asyncio
async def test_create_baseline_from_runtime_heat_id_keeps_same_source_heat_id(
    client, monkeypatch
) -> None:
    async def fake_load_preview_curves_for_selection(
        *, definition_id, selected_start_time, selected_end_time
    ):
        return [
            {
                "metric_id": "001",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#409EFF",
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

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    list_response = await client.get("/api/heats", params={"page_size": 20})
    assert list_response.status_code == 200
    runtime_item = list_response.json()["items"][0]

    create_response = await client.post(
        "/api/baselines",
        json={
            "name": "runtime source baseline",
            "description": "验证运行态炉次 ID 会直接落库",
            "definition_id": "def-001",
            "source_heat_id": runtime_item["id"],
            "selected_start_time": runtime_item["start_time"],
            "selected_end_time": runtime_item["end_time"],
            "tolerance_percent": 12.0,
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["source_heat_id"] == runtime_item["id"]


@pytest.mark.asyncio
async def test_preview_and_baseline_time_window_use_runtime_heat_id_even_after_active_baseline_changes(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    def1_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))
    def2_points = _build_live_power_points(datetime(2026, 3, 19, 11, 0))

    async def fake_load_live_heat_inference_power_points(channel):
        if channel["cuid"] == "199":
            return def1_points
        if channel["cuid"] == "142":
            return def2_points
        return []

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    list_response = await client.get("/api/heats", params={"page_size": 20})
    assert list_response.status_code == 200
    runtime_item = list_response.json()["items"][0]

    _SETTINGS_STORE["active_baseline_id"]["value"] = FORMAL_SECONDARY_BASELINE_ID

    preview_window = await _resolve_preview_window(runtime_item["id"], definition_id="def-001")
    baseline_window = await _resolve_baseline_time_window(
        {"definition_id": "def-001", "source_heat_id": runtime_item["id"]}
    )
    assert plant_date_of(preview_window[0], get_plant_timezone()) == plant_date_of(
        baseline_window[0],
        get_plant_timezone(),
    )
    assert baseline_window[0].hour == 8


@pytest.mark.asyncio
async def test_baseline_time_window_skips_live_lookup_for_non_live_missing_source(
    monkeypatch,
) -> None:
    calls: list[str] = []

    async def fake_resolve_heat_time_window(heat_id: str, **_kwargs):
        calls.append(heat_id)
        return None

    monkeypatch.setattr(
        "src.api.heats.resolve_heat_time_window",
        fake_resolve_heat_time_window,
    )

    window_start, window_end = await _resolve_baseline_time_window(
        {"definition_id": "def-001", "source_heat_id": "heat-ref-999"}
    )

    assert calls == ["heat-ref-999"]
    assert (window_end - window_start).total_seconds() == 3600


def test_infer_live_activity_threshold_returns_none_for_flat_zero_signal() -> None:
    import src.api.heats as heats_module

    zero_points = [
        CurvePoint(timestamp=1_775_308_000_000 + index * 60_000, value=0.0)
        for index in range(30)
    ]

    assert heats_module._infer_live_activity_threshold(zero_points) is None


@pytest.mark.asyncio
async def test_list_heats_does_not_surface_mock_stream_records(client) -> None:
    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["id"] == "heat-001" for item in payload["items"])
    assert all(item["record_source"] != "mock_stream" for item in payload["items"])


@pytest.mark.asyncio
async def test_mock_stream_endpoints_use_dedicated_store(client) -> None:
    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    list_response = await client.get("/api/heats")
    assert list_response.status_code == 200
    ordinary_before = list_response.json()
    assert ordinary_before["total"] >= 1
    assert any(item["id"] == "heat-001" for item in ordinary_before["items"])

    mock_list_response = await client.get(
        "/api/heats/stream/mock",
        params={"page_size": 5, "showtime": "true"},
    )
    assert mock_list_response.status_code == 200
    mock_payload = mock_list_response.json()
    assert mock_payload["total"] > 0
    assert all(item["record_source"] == "mock_stream" for item in mock_payload["items"])

    ingest_response = await client.post("/api/heats/stream/mock/ingest?showtime=true")
    assert ingest_response.status_code == 200
    assert ingest_response.json()["record_source"] == "mock_stream"

    ordinary_after_ingest = await client.get("/api/heats")
    assert ordinary_after_ingest.status_code == 200
    assert ordinary_after_ingest.json() == ordinary_before

    ordinary_showtime = await client.get("/api/heats", params={"showtime": "true"})
    assert ordinary_showtime.status_code == 200
    assert ordinary_showtime.json()["items"][0]["record_source"] == "mock_stream"


@pytest.mark.asyncio
async def test_list_heats_filters_by_stored_status_without_compare_recompute(
    client, monkeypatch
) -> None:
    start_time = datetime(2026, 3, 24, 8, 0, 0)
    end_time = start_time + timedelta(minutes=30)
    current_power_curve = [
        CurvePoint(timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000), value=120.0)
        for index in range(4)
    ]
    async def fake_list_heat_store():
        return {
            "heat-live-1": {
                "id": "heat-live-1",
                "heat_no": "H20260324-0800",
                "description": "Furnace-A01",
                "start_time": start_time,
                "end_time": end_time,
                "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
                "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
                "baseline_effective_from": _formal_baseline_effective_from(),
                "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
                "deviation_percent": None,
                "avg_deviation_percent": None,
                "time_offset_percent": 0.0,
                "mismatch_duration_minutes": 0,
                "schedule_tag": "work",
                "cut_reason": "within_tolerance",
                "cut_status": "normal",
                "major_issue": False,
                "blocked_by_issue": False,
                "status": "abnormal",
                "temperature": 1450.0,
                "record_source": "live_inferred",
                "current_curve_source": "live_edc",
                "baseline_curve_source": "none",
                "created_at": start_time,
                "power_curve": current_power_curve,
                "voltage_curve": [],
                "baseline_power_curve": [],
            }
        }

    async def fail_hydrate_compare_baselines(_baseline_ids):
        raise AssertionError("列表筛选不应在过滤前触发 compare hydrate")

    _SETTINGS_STORE["active_baseline_id"]["value"] = FORMAL_PRIMARY_BASELINE_ID
    monkeypatch.setattr("src.api.heats._list_heat_store", fake_list_heat_store)
    monkeypatch.setattr("src.api.heats._hydrate_compare_baselines", fail_hydrate_compare_baselines)

    response = await client.get("/api/heats", params={"status": "abnormal", "page": 1, "page_size": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "heat-live-1"
    assert payload["items"][0]["status"] == "abnormal"
    assert payload["items"][0]["deviation_percent"] is None


@pytest.mark.asyncio
async def test_heat_compare_hydrates_each_baseline_only_once(client, monkeypatch) -> None:
    hydrate_calls: list[str] = []

    async def fake_load_heat_curves_from_edc(_item):
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    async def fake_hydrate_baseline_item(item):
        hydrate_calls.append(str(item["id"]))
        if str(item["id"]) == FORMAL_PRIMARY_BASELINE_ID:
            item["curves_data"] = [
                {
                    "metric_id": "001",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "points": [
                        {"timestamp": 1000, "value": 701.0},
                        {"timestamp": 2000, "value": 702.0},
                    ],
                },
                {
                    "metric_id": "002",
                    "metric_name": "电压",
                    "unit": "V",
                    "color": "#67C23A",
                    "points": [
                        {"timestamp": 1000, "value": 381.0},
                        {"timestamp": 2000, "value": 382.0},
                    ],
                },
            ]
        else:
            item["curves_data"] = [
                {
                    "metric_id": "001",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "points": [
                        {"timestamp": 1000, "value": 801.0},
                        {"timestamp": 2000, "value": 802.0},
                    ],
                }
            ]
        item["power_curve"] = [
            CurvePoint(timestamp=1000, value=701.0),
            CurvePoint(timestamp=2000, value=702.0),
        ]
        item["voltage_curve"] = [
            CurvePoint(timestamp=1000, value=381.0),
            CurvePoint(timestamp=2000, value=382.0),
        ]
        item["curve_source"] = "live_edc"
        return item

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)
    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )

    heat_id = await _pick_heat_id(client)
    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    assert hydrate_calls.count(FORMAL_PRIMARY_BASELINE_ID) == 1
    assert FORMAL_SECONDARY_BASELINE_ID not in hydrate_calls


@pytest.mark.asyncio
async def test_heat_compare_reuses_short_ttl_cache(client, monkeypatch) -> None:
    hydrate_calls: list[str] = []
    channel_load_calls = 0
    heat_curve_calls = 0

    async def fake_hydrate_baseline_item(item):
        hydrate_calls.append(str(item["id"]))
        item["curves_data"] = [
            {
                "metric_id": "001",
                "metric_name": "功率",
                "unit": "kW",
                "color": "#409EFF",
                "points": [
                    {"timestamp": 1000, "value": 701.0},
                    {"timestamp": 2000, "value": 702.0},
                ],
            },
            {
                "metric_id": "002",
                "metric_name": "电压",
                "unit": "V",
                "color": "#67C23A",
                "points": [
                    {"timestamp": 1000, "value": 381.0},
                    {"timestamp": 2000, "value": 382.0},
                ],
            },
        ]
        item["power_curve"] = [
            CurvePoint(timestamp=1000, value=701.0),
            CurvePoint(timestamp=2000, value=702.0),
        ]
        item["voltage_curve"] = [
            CurvePoint(timestamp=1000, value=381.0),
            CurvePoint(timestamp=2000, value=382.0),
        ]
        item["curve_source"] = "live_edc"
        return item

    async def fake_load_channel_curves_from_edc(**_kwargs):
        nonlocal channel_load_calls
        channel_load_calls += 1
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    async def fake_load_heat_curves_from_edc(_item):
        nonlocal heat_curve_calls
        heat_curve_calls += 1
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)

    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()
    first_resp = await client.get(f"/api/heats/{heat_id}/compare")
    channel_load_calls_after_first = channel_load_calls
    second_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert first_resp.json() == second_resp.json()
    assert hydrate_calls.count(FORMAL_PRIMARY_BASELINE_ID) == 1
    assert FORMAL_SECONDARY_BASELINE_ID not in hydrate_calls
    assert channel_load_calls_after_first == 2
    assert channel_load_calls == channel_load_calls_after_first
    assert heat_curve_calls == 0


@pytest.mark.asyncio
async def test_heat_compare_reuses_shared_baseline_cache_across_different_heats(
    client,
    monkeypatch,
) -> None:
    hydrate_calls: list[str] = []

    async def fake_hydrate_baseline_item(item):
        hydrate_calls.append(str(item["id"]))
        return {
            **item,
            "curve_source": "live_edc",
            "power_curve": [
                {"timestamp": 1000, "value": 701.0},
                {"timestamp": 2000, "value": 702.0},
            ],
            "voltage_curve": [
                {"timestamp": 1000, "value": 381.0},
                {"timestamp": 2000, "value": 382.0},
            ],
            "curves_data": [
                {
                    "metric_id": "001",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "points": [
                        {"timestamp": 1000, "value": 701.0},
                        {"timestamp": 2000, "value": 702.0},
                    ],
                },
                {
                    "metric_id": "002",
                    "metric_name": "电压",
                    "unit": "V",
                    "color": "#67C23A",
                    "points": [
                        {"timestamp": 1000, "value": 381.0},
                        {"timestamp": 2000, "value": 382.0},
                    ],
                },
            ],
        }

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heat_ids = [
        _seed_runtime_heat(
            heat_id="runtime-heat-cache-001",
            record_source="active_runtime",
            start_time=datetime(2026, 3, 19, 8, 0, 0),
        ),
        _seed_runtime_heat(
            heat_id="runtime-heat-cache-002",
            record_source="previous_runtime",
            start_time=datetime(2026, 3, 19, 7, 0, 0),
        ),
    ]

    first_resp = await client.get(f"/api/heats/{heat_ids[0]}/compare")
    second_resp = await client.get(f"/api/heats/{heat_ids[1]}/compare")
    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert hydrate_calls.count(FORMAL_PRIMARY_BASELINE_ID) == 1
    assert FORMAL_SECONDARY_BASELINE_ID not in hydrate_calls


@pytest.mark.asyncio
async def test_startup_restore_keeps_formal_baseline_window(client) -> None:
    _SETTINGS_STORE["edc_base_url"]["value"] = "http://61.216.55.133"
    _SETTINGS_STORE["edc_username"]["value"] = "admin"
    _SETTINGS_STORE["edc_password"]["value"] = "admin"
    restored_start = datetime(2026, 3, 23, 8, 0)
    restored_end = datetime(2026, 3, 23, 8, 30)
    baseline_item = _BASELINE_STORE[FORMAL_PRIMARY_BASELINE_ID]
    baseline_item["source_heat_id"] = "heat-001"
    baseline_item["selected_start_time"] = restored_start
    baseline_item["selected_end_time"] = restored_end
    _SETTINGS_STORE["active_baseline_id"]["value"] = FORMAL_PRIMARY_BASELINE_ID

    await persist_runtime_state("baselines", "settings_store")

    baseline_item["selected_start_time"] = None
    baseline_item["selected_end_time"] = None
    _SETTINGS_STORE["active_baseline_id"]["value"] = ""
    await load_runtime_state()

    assert _BASELINE_STORE[FORMAL_PRIMARY_BASELINE_ID]["selected_start_time"] == restored_start
    assert _BASELINE_STORE[FORMAL_PRIMARY_BASELINE_ID]["selected_end_time"] == restored_end
    assert _SETTINGS_STORE["active_baseline_id"]["value"] == FORMAL_PRIMARY_BASELINE_ID

    window_start, window_end = await _resolve_baseline_time_window(
        _BASELINE_STORE[FORMAL_PRIMARY_BASELINE_ID]
    )
    assert (window_start, window_end) == (restored_start, restored_end)


@pytest.mark.asyncio
async def test_load_channel_curves_from_edc_reuses_shared_batch_cache(monkeypatch) -> None:
    calls = 0

    class FakeEDCClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def get_local_datas(self, **kwargs):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            cuid = str(kwargs["cuid"])
            base_value = 500.0 if cuid == "199" else 330.0
            return [
                CurvePoint(timestamp=1000, value=base_value),
                CurvePoint(timestamp=2000, value=base_value + 1.0),
            ]

    monkeypatch.setattr(
        "src.api.heats.get_edc_connection_config",
        lambda: {
            "base_url": "http://localhost:8080",
            "username": "tester",
            "password": "secret",
        },
    )
    monkeypatch.setattr("src.api.heats.EDCClient", FakeEDCClient)

    import src.api.heats as heats_module

    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"] = {}
    channels = [
        {"suid": "2349", "cuid": "199"},
        {"suid": "2349", "cuid": "128"},
    ]
    start_time = datetime(2026, 3, 22, 8, 0)
    end_time = datetime(2026, 3, 22, 8, 30)

    first_curves, second_curves = await asyncio.gather(
        heats_module._load_channel_curves_from_edc(
            channels=channels,
            start_time=start_time,
            end_time=end_time,
        ),
        heats_module._load_channel_curves_from_edc(
            channels=channels,
            start_time=start_time,
            end_time=end_time,
        ),
    )
    third_curves = await heats_module._load_channel_curves_from_edc(
        channels=channels,
        start_time=start_time,
        end_time=end_time,
    )

    assert calls == 2
    assert first_curves == second_curves
    assert second_curves == third_curves
