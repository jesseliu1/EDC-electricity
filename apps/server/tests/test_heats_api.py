"""炉次 API 测试。"""

import asyncio
import json
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
from src.time_utils import from_timestamp_ms, plant_date_of, to_timestamp_ms, utc_now

FORMAL_PRIMARY_BASELINE_ID = "def-001:001"
FORMAL_SECONDARY_BASELINE_ID = "def-002:001"


def _build_runtime_metric_series_entry(
    *,
    heat_id: str,
    item: str,
    metric_key: str,
    metric_name: str,
    unit: str,
    color: str,
    source_channel_id: str,
    source_channel_name: str,
    source_channel_label: str,
    points: list[CurvePoint],
    sort_order: int,
) -> dict[str, object]:
    return {
        "owner_key": heat_id,
        "item": item,
        "owner_type": "heat",
        "metric_key": metric_key,
        "metric_name": metric_name,
        "unit": unit,
        "color": color,
        "sort_order": sort_order,
        "source_channel_id": source_channel_id,
        "source_channel_name": source_channel_name,
        "source_channel_label": source_channel_label,
        "series_json": {"points": [point.model_dump() for point in points]},
        "stat_json": {},
    }


def _build_runtime_definition_metric_snapshots(
    *,
    definition_id: str,
) -> list[dict[str, object]]:
    if definition_id == "def-002":
        return [
            {
                "item": "001",
                "metric_key": "power",
                "metric_name": "A相有功功率",
                "unit": "kW",
                "color": "#f97316",
                "sort_order": 1,
                "edc_channel_id": "2349-142",
                "source_channel_name": "A相有功功率",
                "source_channel_label": "测试设备 / A相有功功率 / kW",
                "enabled": True,
            },
            {
                "item": "002",
                "metric_key": "voltage",
                "metric_name": "B相电压",
                "unit": "V",
                "color": "#ef4444",
                "sort_order": 2,
                "edc_channel_id": "2349-130",
                "source_channel_name": "B相电压",
                "source_channel_label": "测试设备 / B相电压 / V",
                "enabled": True,
            },
        ]
    return [
        {
            "item": "001",
            "metric_key": "power",
            "metric_name": "总有功功率",
            "unit": "kW",
            "color": "#1152d4",
            "sort_order": 1,
            "edc_channel_id": "2349-199",
            "source_channel_name": "总有功功率",
            "source_channel_label": "测试设备 / 总有功功率 / kW",
            "enabled": True,
        },
        {
            "item": "002",
            "metric_key": "voltage",
            "metric_name": "A相电压",
            "unit": "V",
            "color": "#67C23A",
            "sort_order": 2,
            "edc_channel_id": "2349-128",
            "source_channel_name": "A相电压",
            "source_channel_label": "测试设备 / A相电压 / V",
            "enabled": True,
        },
    ]


def _build_runtime_baseline_curve_snapshots(
    *,
    baseline_id: str,
    start_time: datetime,
) -> list[dict[str, object]]:
    definition_id = str(baseline_id).split(":", 1)[0]
    definitions = _build_runtime_definition_metric_snapshots(definition_id=definition_id)
    snapshots: list[dict[str, object]] = []
    for snapshot in definitions:
        metric_key = str(snapshot["metric_key"])
        base_value = 410.0 if metric_key == "power" else 220.0
        snapshots.append(
            {
                "baseline_id": baseline_id,
                "metric_key": metric_key,
                "curve_source": "baseline_metric_series",
                "points": [
                    {
                        "timestamp": int(start_time.timestamp() * 1000),
                        "value": base_value,
                    },
                    {
                        "timestamp": int((start_time + timedelta(minutes=30)).timestamp() * 1000),
                        "value": base_value + (12.0 if metric_key == "power" else 4.0),
                    },
                ],
            }
        )
    return snapshots


def _build_runtime_metric_series(
    *,
    heat_id: str,
    baseline_id: str,
    start_time: datetime,
) -> list[dict[str, object]]:
    definition_id = str(baseline_id).split(":", 1)[0]
    power_points = [
        CurvePoint(
            timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
            value=430.0 + index,
        )
        for index in range(4)
    ]
    if definition_id == "def-002":
        voltage_metric_name = "B相电压"
        voltage_channel_id = "2349-130"
        voltage_channel_name = "B相电压"
        voltage_channel_label = "测试设备 / B相电压 / V"
    else:
        voltage_metric_name = "A相电压"
        voltage_channel_id = "2349-128"
        voltage_channel_name = "A相电压"
        voltage_channel_label = "测试设备 / A相电压 / V"
    voltage_points = [
        CurvePoint(
            timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
            value=221.0 + index,
        )
        for index in range(4)
    ]
    return [
        _build_runtime_metric_series_entry(
            heat_id=heat_id,
            item="001",
            metric_key="power",
            metric_name="总有功功率" if definition_id == "def-001" else "A相有功功率",
            unit="kW",
            color="#1152d4" if definition_id == "def-001" else "#f97316",
            source_channel_id="2349-199" if definition_id == "def-001" else "2349-142",
            source_channel_name="总有功功率" if definition_id == "def-001" else "A相有功功率",
            source_channel_label="测试设备 / 总有功功率 / kW"
            if definition_id == "def-001"
            else "测试设备 / A相有功功率 / kW",
            points=power_points,
            sort_order=1,
        ),
        _build_runtime_metric_series_entry(
            heat_id=heat_id,
            item="002",
            metric_key="voltage",
            metric_name=voltage_metric_name,
            unit="V",
            color="#67C23A" if definition_id == "def-001" else "#ef4444",
            source_channel_id=voltage_channel_id,
            source_channel_name=voltage_channel_name,
            source_channel_label=voltage_channel_label,
            points=voltage_points,
            sort_order=2,
        ),
    ]


@pytest.fixture(autouse=True)
def _patch_runtime_metric_curve_loader(monkeypatch):
    async def fake_load_runtime_metric_curves(
        metrics: list[dict[str, object]],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, list[CurvePoint]]:
        curves: dict[str, list[CurvePoint]] = {}
        for metric in metrics:
            metric_id = str(metric.get("id") or "")
            metric_key = str(metric.get("metric_key") or "")
            if metric_key == "power":
                curves[metric_id] = [
                    CurvePoint(timestamp=int(start_time.timestamp() * 1000), value=430.0),
                    CurvePoint(timestamp=int(end_time.timestamp() * 1000), value=438.0),
                ]
            elif metric_key == "voltage":
                curves[metric_id] = [
                    CurvePoint(timestamp=int(start_time.timestamp() * 1000), value=221.0),
                    CurvePoint(timestamp=int(end_time.timestamp() * 1000), value=226.0),
                ]
        return curves

    monkeypatch.setattr(
        "src.api.heats._load_runtime_metric_curves", fake_load_runtime_metric_curves
    )


def _build_live_power_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = int((start + timedelta(minutes=offset_minutes + index)).timestamp() * 1000)
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


def _build_live_power_points_with_heat_lengths(
    start: datetime,
    heat_lengths: list[int],
) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    cursor = 0
    for heat_length in heat_lengths:
        for offset in range(8):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=42.0))
        cursor += 8
        for offset in range(heat_length):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=128.0))
        cursor += heat_length
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
    definition_id = str(baseline_id).split(":", 1)[0]
    runtime_metric_series = _build_runtime_metric_series(
        heat_id=heat_id,
        baseline_id=baseline_id,
        start_time=runtime_start,
    )
    item = {
        "id": heat_id,
        "heat_no": f"H{runtime_start.strftime('%Y%m%d-%H%M')}",
        "description": "运行态炉次",
        "start_time": runtime_start,
        "end_time": runtime_start + timedelta(minutes=30),
        "completion_status": "in_progress" if record_source == "active_runtime" else "completed",
        "last_point_at": runtime_start + timedelta(minutes=30),
        "baseline_id": baseline_id,
        "baseline_version_id": baseline_id,
        "baseline_effective_from": _formal_baseline_effective_from(baseline_id),
        "baseline_ids": [baseline_id],
        "deviation_score": None,
        "avg_deviation_score": None,
        "abnormal_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": record_source,
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "normal" if record_source != "active_runtime" else "pending",
        "temperature": None,
        "record_source": record_source,
        "current_curve_source": "live_edc",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": runtime_start,
        "power_curve": [
            CurvePoint(**point) for point in runtime_metric_series[0]["series_json"]["points"]
        ],
        "voltage_curve": [
            CurvePoint(**point) for point in runtime_metric_series[1]["series_json"]["points"]
        ],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": runtime_metric_series,
        "definition_metric_snapshots": _build_runtime_definition_metric_snapshots(
            definition_id=definition_id
        ),
        "baseline_curve_snapshots": _build_runtime_baseline_curve_snapshots(
            baseline_id=baseline_id,
            start_time=runtime_start,
        ),
        "baseline_bindings": [
            {
                "heat_id": heat_id,
                "baseline_id": baseline_id,
                "baseline_definition_id": definition_id,
                "baseline_item": "001",
                "is_primary": True,
                "baseline_effective_from": _formal_baseline_effective_from(baseline_id),
                "tolerance_percent": 15.0,
                "analysis_status": "ready",
                "deviation_score": 1.2,
                "avg_deviation_score": 0.8,
                "analysis_details_json": '{"abnormal_ranges":[]}',
                "abnormal_duration_minutes": 0.0,
            }
        ],
    }

    if record_source == "previous_runtime":
        heats_module._PREVIOUS_HEAT_RUNTIME[heat_id] = item
    else:
        heats_module._ACTIVE_HEAT_RUNTIME[heat_id] = item
    return heat_id


def test_build_current_heat_runtime_reads_birth_context_snapshots() -> None:
    import src.api.heats as heats_module

    start_time = datetime(2026, 3, 19, 8, 0)
    end_time = start_time + timedelta(minutes=30)
    binding_payload = {
        "heat_id": "runtime-heat-ctx",
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_definition_id": "def-001",
        "baseline_item": "001",
        "is_primary": True,
        "baseline_effective_from": start_time,
        "tolerance_percent": 5.0,
        "analysis_status": "ready",
        "deviation_score": 1.2,
        "avg_deviation_score": 0.8,
        "analysis_details_json": None,
        "abnormal_duration_minutes": 0.0,
    }
    item = {
        "id": "runtime-heat-ctx",
        "heat_no": "H20260319-0800",
        "start_time": start_time,
        "end_time": end_time,
        "created_at": start_time,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "runtime_snapshot",
        "baseline_bindings": [binding_payload],
        "runtime_metric_series": _build_runtime_metric_series(
            heat_id="runtime-heat-ctx",
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            start_time=start_time,
        ),
        "power_curve": [
            CurvePoint(timestamp=int(start_time.timestamp() * 1000), value=420.0),
            CurvePoint(
                timestamp=int((start_time + timedelta(minutes=1)).timestamp() * 1000), value=421.0
            ),
        ],
        "birth_context": {
            "heat_id": "runtime-heat-ctx",
            "channel_key": "2349:199",
            "cutting_mode": "signal_inference",
            "expected_duration_minutes": 30,
            "plant_timezone": "Asia/Shanghai",
            "cutting_config_snapshot": {
                "time_tolerance_percent": 10.0,
                "major_issue_duration_minutes": 6,
                "plant_timezone": "Asia/Shanghai",
                "work_start_time": "08:00",
                "work_end_time": "20:00",
                "break_periods": ["12:00-13:00"],
                "cutting_mode": "signal_inference",
                "fixed_interval_minutes": None,
            },
            "primary_baseline_id": FORMAL_PRIMARY_BASELINE_ID,
            "baseline_bindings_snapshot": [binding_payload],
            "definition_metric_snapshots": [
                {
                    "item": "001",
                    "metric_key": "power",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#ff6600",
                    "sort_order": 0,
                    "edc_channel_id": "2349-199",
                    "source_channel_name": "功率",
                    "source_channel_label": "功率曲线",
                    "enabled": True,
                }
            ],
            "baseline_curve_snapshots": [
                {
                    "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
                    "metric_key": "power",
                    "curve_source": "baseline_metric_series",
                    "points": [
                        {"timestamp": int(start_time.timestamp() * 1000), "value": 410.0},
                        {
                            "timestamp": int(
                                (start_time + timedelta(minutes=1)).timestamp() * 1000
                            ),
                            "value": 411.0,
                        },
                    ],
                }
            ],
        },
    }

    runtime = heats_module._build_current_heat_runtime(item, trigger_source="test")

    assert runtime.birth_context is not None
    assert runtime.birth_context.primary_baseline_id == FORMAL_PRIMARY_BASELINE_ID
    assert runtime.birth_context.channel_key == "2349:199"
    assert runtime.birth_context.cutting_config_snapshot is not None
    assert runtime.birth_context.cutting_config_snapshot.plant_timezone == "Asia/Shanghai"
    assert len(runtime.definition_metric_snapshots) == 1
    assert runtime.definition_metric_snapshots[0].metric_key == "power"
    assert len(runtime.baseline_curve_snapshots) == 1
    assert runtime.baseline_curve_snapshots[0].curve_source == "baseline_metric_series"

    runtime_item = runtime.to_runtime_item()
    assert runtime_item["birth_context"]["primary_baseline_id"] == FORMAL_PRIMARY_BASELINE_ID
    assert runtime_item["birth_context"]["cutting_config_snapshot"]["work_start_time"] == "08:00"
    assert runtime_item["definition_metric_snapshots"][0]["metric_key"] == "power"
    assert runtime_item["baseline_curve_snapshots"][0]["curve_source"] == "baseline_metric_series"


def test_transition_service_active_runtime_only_uses_previous_start_for_n_minus_1() -> None:
    from src.services.heat_runtime_transition_service import HeatRuntimeTransitionService

    service = HeatRuntimeTransitionService()
    previous_start = datetime(2026, 3, 19, 8, 0)
    previous_end = previous_start + timedelta(minutes=30)
    active_start = previous_end + timedelta(minutes=8)
    active_end = active_start + timedelta(minutes=30)

    previous_candidate = {
        "id": "heat-prev",
        "start_time": previous_start,
        "end_time": previous_end,
        "context_start_time": previous_start - timedelta(minutes=30),
        "context_end_time": active_end,
    }
    active_candidate = {
        "id": "heat-active",
        "start_time": active_start,
        "end_time": active_end,
    }

    prepared = service.prepare_active_candidate(
        active_candidate,
        previous_candidate=previous_candidate,
        existing_previous_item=None,
    )

    assert prepared is not None
    assert prepared["context_start_time"] == previous_start
    assert prepared["context_end_time"] == active_end


def test_seal_service_prefers_existing_previous_runtime_as_formal_source() -> None:
    from src.services.heat_runtime_seal_service import HeatRuntimeSealService

    service = HeatRuntimeSealService()
    start_time = datetime(2026, 3, 19, 8, 0)
    end_time = start_time + timedelta(minutes=30)
    context_start_time = start_time - timedelta(minutes=20)
    context_end_time = end_time + timedelta(minutes=28)
    binding_payload = {
        "heat_id": "runtime-previous-001",
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_definition_id": "def-001",
        "baseline_item": "001",
        "is_primary": True,
        "baseline_effective_from": start_time,
        "tolerance_percent": 5.0,
        "analysis_status": "ready",
        "deviation_score": 1.8,
        "avg_deviation_score": 0.9,
        "analysis_details_json": '{"status":"ready"}',
        "abnormal_duration_minutes": 2.0,
    }
    definition_metric_snapshots = _build_runtime_definition_metric_snapshots(
        definition_id="def-001"
    )
    baseline_curve_snapshots = _build_runtime_baseline_curve_snapshots(
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        start_time=start_time,
    )
    existing_previous_item = {
        "id": "runtime-previous-001",
        "heat_no": "H20260319-0800",
        "start_time": start_time,
        "end_time": end_time,
        "context_start_time": context_start_time,
        "context_end_time": context_end_time,
        "created_at": start_time,
        "record_source": "previous_runtime",
        "current_curve_source": "runtime_metric_series",
        "baseline_curve_source": "runtime_snapshot",
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
        "baseline_bindings": [binding_payload],
        "deviation_score": 1.8,
        "avg_deviation_score": 0.9,
        "abnormal_duration_minutes": 2.0,
        "runtime_metric_series": _build_runtime_metric_series(
            heat_id="runtime-previous-001",
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            start_time=start_time,
        ),
        "definition_metric_snapshots": definition_metric_snapshots,
        "baseline_curve_snapshots": baseline_curve_snapshots,
        "birth_context": {
            "heat_id": "runtime-previous-001",
            "channel_key": "2349:199",
            "cutting_mode": "signal_inference",
            "expected_duration_minutes": 30,
            "plant_timezone": "Asia/Shanghai",
            "cutting_config_snapshot": {
                "time_tolerance_percent": 10.0,
                "major_issue_duration_minutes": 6,
                "plant_timezone": "Asia/Shanghai",
                "work_start_time": "08:00",
                "work_end_time": "20:00",
                "break_periods": [],
                "cutting_mode": "signal_inference",
                "fixed_interval_minutes": None,
            },
            "primary_baseline_id": FORMAL_PRIMARY_BASELINE_ID,
            "baseline_bindings_snapshot": [binding_payload],
            "definition_metric_snapshots": definition_metric_snapshots,
            "baseline_curve_snapshots": baseline_curve_snapshots,
        },
    }
    sealed_candidate = {
        "id": "sealed-raw-001",
        "start_time": start_time,
        "end_time": end_time,
    }

    resolved = service.resolve_seal_sources(
        sealed_candidates=[sealed_candidate],
        existing_previous_item=existing_previous_item,
        existing_active_item=None,
        trigger_source="test_refresh",
    )

    assert len(resolved) == 1
    resolved_item = resolved[0]
    assert resolved_item["id"] == "runtime-previous-001"
    assert resolved_item["context_end_time"] == context_end_time
    assert (
        resolved_item["preseal_payload"]["heat_payload"]["context_end_time"] == context_end_time
    )
    assert (
        resolved_item["preseal_payload"]["binding_payloads"][0]["deviation_score"]
        == pytest.approx(1.8)
    )


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
    runtime_metric_series = _build_runtime_metric_series(
        heat_id=active_id,
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        start_time=start_time,
    )
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
        "deviation_score": None,
        "avg_deviation_score": None,
        "abnormal_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": start_time,
        "power_curve": [
            CurvePoint(**point) for point in runtime_metric_series[0]["series_json"]["points"]
        ],
        "voltage_curve": [
            CurvePoint(**point) for point in runtime_metric_series[1]["series_json"]["points"]
        ],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": runtime_metric_series,
        "definition_metric_snapshots": _build_runtime_definition_metric_snapshots(
            definition_id="def-001"
        ),
        "baseline_curve_snapshots": _build_runtime_baseline_curve_snapshots(
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            start_time=start_time,
        ),
    }
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = start_time + timedelta(
        minutes=5
    )
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
async def test_list_heats_keeps_active_previous_and_history_sorted_without_cross_source_merging(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()

    history_start = datetime(2026, 4, 17, 12, 5, 0)
    previous_start = datetime(2026, 4, 17, 13, 5, 0)
    active_start = datetime(2026, 4, 17, 13, 35, 0)

    _seed_runtime_heat(
        heat_id="live-heat-active-001",
        record_source="active_runtime",
        start_time=active_start,
    )
    _seed_runtime_heat(
        heat_id="live-heat-previous-001",
        record_source="previous_runtime",
        start_time=previous_start,
    )

    history_metric_series = _build_runtime_metric_series(
        heat_id="heat-history-001",
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        start_time=history_start,
    )
    history_item = {
        "id": "heat-history-001",
        "heat_no": "H20260417-1205",
        "description": "已固化历史炉次",
        "start_time": history_start,
        "end_time": history_start + timedelta(minutes=30),
        "completion_status": "completed",
        "last_point_at": history_start + timedelta(minutes=30),
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_effective_from": _formal_baseline_effective_from(),
        "deviation_score": 12.3,
        "avg_deviation_score": 11.1,
        "abnormal_duration_minutes": 0.0,
        "schedule_tag": "work",
        "cut_reason": "sealed_history",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "normal",
        "temperature": None,
        "record_source": "sealed_history",
        "current_curve_source": "formal_db",
        "baseline_curve_source": "baseline_metric_series",
        "created_at": history_start,
        "power_curve": [
            CurvePoint(**point) for point in history_metric_series[0]["series_json"]["points"]
        ],
        "voltage_curve": [
            CurvePoint(**point) for point in history_metric_series[1]["series_json"]["points"]
        ],
    }

    async def fake_list_formal_heat_records(**_kwargs):
        return [history_item]

    monkeypatch.setattr("src.api.heats.list_formal_heat_records", fake_list_formal_heat_records)

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()

    visible_items = payload["items"][:3]
    assert [item["id"] for item in visible_items] == [
        "live-heat-active-001",
        "live-heat-previous-001",
        "heat-history-001",
    ]
    assert [item["record_source"] for item in visible_items] == [
        "active_runtime",
        "previous_runtime",
        "sealed_history",
    ]


@pytest.mark.asyncio
async def test_list_heats_marks_active_runtime_as_stale_when_watermark_is_old(client) -> None:
    import src.api.heats as heats_module

    start_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=20)
    active_id = "active-heat-stale"
    runtime_metric_series = _build_runtime_metric_series(
        heat_id=active_id,
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        start_time=start_time,
    )
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
        "deviation_score": None,
        "avg_deviation_score": None,
        "abnormal_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": start_time,
        "power_curve": [
            CurvePoint(**point) for point in runtime_metric_series[0]["series_json"]["points"]
        ],
        "voltage_curve": [
            CurvePoint(**point) for point in runtime_metric_series[1]["series_json"]["points"]
        ],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": runtime_metric_series,
        "definition_metric_snapshots": _build_runtime_definition_metric_snapshots(
            definition_id="def-001"
        ),
        "baseline_curve_snapshots": _build_runtime_baseline_curve_snapshots(
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            start_time=start_time,
        ),
    }
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = utc_now() - timedelta(
        minutes=10
    )
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
    runtime_metric_series = _build_runtime_metric_series(
        heat_id=active_id,
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        start_time=start_time,
    )
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
        "deviation_score": None,
        "avg_deviation_score": None,
        "abnormal_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": start_time,
        "power_curve": [
            CurvePoint(**point) for point in runtime_metric_series[0]["series_json"]["points"]
        ],
        "voltage_curve": [
            CurvePoint(**point) for point in runtime_metric_series[1]["series_json"]["points"]
        ],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": runtime_metric_series,
        "definition_metric_snapshots": _build_runtime_definition_metric_snapshots(
            definition_id="def-001"
        ),
        "baseline_curve_snapshots": _build_runtime_baseline_curve_snapshots(
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            start_time=start_time,
        ),
    }
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = utc_now() - timedelta(
        seconds=30
    )
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
    active_runtime_metric_series = _build_runtime_metric_series(
        heat_id="active-heat-restore",
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        start_time=start_time,
    )
    previous_runtime_metric_series = _build_runtime_metric_series(
        heat_id="previous-heat-restore",
        baseline_id=FORMAL_PRIMARY_BASELINE_ID,
        start_time=start_time - timedelta(minutes=38),
    )
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
        "deviation_score": None,
        "avg_deviation_score": None,
        "abnormal_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "active_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "pending",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": start_time,
        "power_curve": [
            CurvePoint(**point)
            for point in active_runtime_metric_series[0]["series_json"]["points"]
        ],
        "voltage_curve": [
            CurvePoint(**point)
            for point in active_runtime_metric_series[1]["series_json"]["points"]
        ],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": active_runtime_metric_series,
        "definition_metric_snapshots": _build_runtime_definition_metric_snapshots(
            definition_id="def-001"
        ),
        "baseline_curve_snapshots": _build_runtime_baseline_curve_snapshots(
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            start_time=start_time,
        ),
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
        "deviation_score": None,
        "avg_deviation_score": None,
        "abnormal_duration_minutes": None,
        "schedule_tag": "work",
        "cut_reason": "previous_runtime",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "normal",
        "temperature": None,
        "record_source": "previous_runtime",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": start_time - timedelta(minutes=38),
        "power_curve": [
            CurvePoint(**point)
            for point in previous_runtime_metric_series[0]["series_json"]["points"]
        ],
        "voltage_curve": [
            CurvePoint(**point)
            for point in previous_runtime_metric_series[1]["series_json"]["points"]
        ],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": previous_runtime_metric_series,
        "definition_metric_snapshots": _build_runtime_definition_metric_snapshots(
            definition_id="def-001"
        ),
        "baseline_curve_snapshots": _build_runtime_baseline_curve_snapshots(
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            start_time=start_time - timedelta(minutes=38),
        ),
    }
    heats_module._HEAT_ID_ALIAS_STORE["legacy-previous-heat"] = "previous-heat-restore"
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_status"] = "ready"
    heats_module._HEAT_RUNTIME_REFRESH_META["refresh_status"] = "idle"
    heats_module._HEAT_RUNTIME_REFRESH_META["snapshot_watermark"] = start_time + timedelta(
        minutes=7
    )

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
    assert heat_item["deviation_score"] is not None

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
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heat_id = _seed_runtime_heat()

    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare 不应在请求期回源 EDC 当前曲线")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window", fail_runtime_compare_fetch
    )
    monkeypatch.setattr(
        "src.api.heats._load_metric_current_curves_from_edc", fail_runtime_compare_fetch
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["heat"]["current_curve_source"] == "runtime_metric_series"
    first_baseline = payload["baselines"][0]
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 430.0
    assert first_baseline["metric_curves"][1]["current_curve"][1]["value"] == 222.0


@pytest.mark.asyncio
async def test_heat_compare_exposes_context_window_and_prefers_runtime_context_for_display_curves(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heat_id = _seed_runtime_heat()
    runtime_item = heats_module._ACTIVE_HEAT_RUNTIME[heat_id]
    runtime_item["context_start_time"] = runtime_item["start_time"] - timedelta(minutes=40)
    runtime_item["context_end_time"] = runtime_item["end_time"] + timedelta(minutes=25)
    runtime_item["runtime_metric_series"][0]["series_json"]["points"] = [
        {
            "timestamp": to_timestamp_ms(
                runtime_item["context_start_time"] + timedelta(minutes=index * 10)
            ),
            "value": 500.0 + index,
        }
        for index in range(5)
    ]
    runtime_item["runtime_metric_series"][1]["series_json"]["points"] = [
        {
            "timestamp": to_timestamp_ms(
                runtime_item["context_start_time"] + timedelta(minutes=index * 10)
            ),
            "value": 350.0 + index,
        }
        for index in range(5)
    ]

    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare 不应按展示窗口再请求当前曲线")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window", fail_runtime_compare_fetch
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["heat"]["context_start_time"] == to_timestamp_ms(
        runtime_item["context_start_time"]
    )
    assert payload["heat"]["context_end_time"] == to_timestamp_ms(runtime_item["context_end_time"])
    first_baseline = payload["baselines"][0]
    assert len(first_baseline["metric_curves"][0]["current_curve"]) == 5
    assert first_baseline["metric_curves"][0]["current_curve"][0]["timestamp"] == to_timestamp_ms(
        runtime_item["context_start_time"]
    )


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
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heat_id = _seed_runtime_heat()
    runtime_item = heats_module._ACTIVE_HEAT_RUNTIME[heat_id]
    runtime_item["runtime_metric_series"] = [
        entry
        for entry in runtime_item["runtime_metric_series"]
        if str(entry.get("metric_key") or "") != "voltage"
    ]

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc", fake_load_channel_curves_from_edc
    )
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc", fake_load_channel_curves_from_edc
    )
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window", fake_load_channel_curves_from_edc
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 409
    assert compare_resp.json()["detail"] == "runtime_current_metric_curve_missing:voltage"


@pytest.mark.asyncio
async def test_heat_compare_accepts_dict_live_curves_without_500(client, monkeypatch) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heat_id = _seed_runtime_heat()
    runtime_item = heats_module._ACTIVE_HEAT_RUNTIME[heat_id]
    runtime_item["baseline_curve_snapshots"] = [
        snapshot
        for snapshot in runtime_item["baseline_curve_snapshots"]
        if str(snapshot.get("metric_key") or "") != "voltage"
    ]

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
        "src.api.heats._load_channel_curves_from_edc", fake_load_heat_curves_from_edc
    )
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 409
    assert compare_resp.json()["detail"] == "runtime_baseline_metric_curve_missing:voltage"


@pytest.mark.asyncio
async def test_heat_compare_prefers_hydrated_baseline_metric_curves(client, monkeypatch) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heat_id = _seed_runtime_heat()

    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare 不应再 hydrate baseline 或回源曲线")

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._hydrate_compare_baselines", fail_runtime_compare_fetch)

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert payload["baseline"]["power_curve"][0]["value"] == 410.0
    assert first_baseline["metric_curves"][0]["baseline_curve"][0]["value"] == 410.0
    assert first_baseline["metric_curves"][1]["baseline_curve"][1]["value"] == 224.0


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
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heat_id = _seed_runtime_heat()
    runtime_item = heats_module._ACTIVE_HEAT_RUNTIME[heat_id]
    runtime_item["context_start_time"] = runtime_item["start_time"] - timedelta(minutes=20)
    runtime_item["context_end_time"] = runtime_item["end_time"] + timedelta(minutes=20)
    runtime_item["runtime_metric_series"][0]["series_json"]["points"] = [
        {
            "timestamp": to_timestamp_ms(
                runtime_item["context_start_time"] + timedelta(minutes=index * 10)
            ),
            "value": 401.0 + index,
        }
        for index in range(8)
    ]
    runtime_item["runtime_metric_series"][1]["series_json"]["points"] = [
        {
            "timestamp": to_timestamp_ms(
                runtime_item["context_start_time"] + timedelta(minutes=index * 10)
            ),
            "value": 301.0 + index,
        }
        for index in range(8)
    ]

    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare 不应按 +/-60 分钟展示窗口再请求当前曲线")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert len(payload["heat"]["power_curve"]) == 4
    assert len(first_baseline["metric_curves"][0]["current_curve"]) == 8
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 401.0


@pytest.mark.asyncio
async def test_heat_compare_display_metric_curves_fall_back_to_display_window_live_curves(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heat_id = _seed_runtime_heat()
    runtime_item = heats_module._ACTIVE_HEAT_RUNTIME[heat_id]
    runtime_item["runtime_metric_series"][0]["series_json"]["points"] = [
        {
            "timestamp": to_timestamp_ms(
                runtime_item["start_time"] + timedelta(minutes=index * 10)
            ),
            "value": 611.0 + index,
        }
        for index in range(4)
    ]
    runtime_item["runtime_metric_series"][1]["series_json"]["points"] = [
        {
            "timestamp": to_timestamp_ms(
                runtime_item["start_time"] + timedelta(minutes=index * 10)
            ),
            "value": 351.0 + index,
        }
        for index in range(4)
    ]

    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare 不应回退到展示窗口 live curves")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window", fail_runtime_compare_fetch
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert len(payload["heat"]["power_curve"]) == 4
    assert payload["heat"]["power_curve"][0]["value"] == 611.0
    assert len(first_baseline["metric_curves"][0]["current_curve"]) == 4
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 611.0
    assert first_baseline["metric_curves"][1]["current_curve"][1]["value"] == 352.0


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
        item
        for item in payload["items"]
        if item["record_source"] in {"active_runtime", "previous_runtime"}
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
    assert all(item["current_curve_source"] == "runtime_metric_series" for item in runtime_items)
    assert runtime_items[0]["id"].startswith("live-heat-")
    assert any(item["id"] == "heat-001" for item in payload["items"])
    assert payload["snapshot_status"] == "stale"
    active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    assert active_runtime["processing_meta"]["processing_mode"] == "live_incremental"
    assert active_runtime["processing_meta"]["trigger_source"] == "test"
    assert active_runtime["baseline_bindings"]
    assert active_runtime["runtime_metric_series"]


@pytest.mark.asyncio
async def test_refresh_heat_runtime_bootstrap_hydrates_all_definition_metrics_into_runtime(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        return live_points

    async def fake_load_metric_current_curves_from_edc(*, metrics, start_time, end_time):
        curves: dict[str, list[CurvePoint]] = {}
        for metric in metrics:
            metric_id = str(metric.get("id") or "")
            metric_key = str(metric.get("metric_key") or "")
            if metric_key == "power":
                curves[metric_id] = [
                    CurvePoint(timestamp=int(start_time.timestamp() * 1000), value=420.0),
                    CurvePoint(timestamp=int(end_time.timestamp() * 1000), value=435.0),
                ]
            elif metric_key == "voltage":
                curves[metric_id] = [
                    CurvePoint(timestamp=int(start_time.timestamp() * 1000), value=221.0),
                    CurvePoint(timestamp=int(end_time.timestamp() * 1000), value=226.0),
                ]
            elif metric_key == "temperature":
                curves[metric_id] = [
                    CurvePoint(timestamp=int(start_time.timestamp() * 1000), value=1548.0),
                    CurvePoint(timestamp=int(end_time.timestamp() * 1000), value=1562.0),
                ]
        return curves

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._load_metric_current_curves_from_edc",
        fake_load_metric_current_curves_from_edc,
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

    await heats_module.refresh_heat_runtime_state(reason="test")

    active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    metric_keys = {
        str(entry.get("metric_key") or "")
        for entry in active_runtime["runtime_metric_series"]
        if isinstance(entry, dict)
    }
    assert {"power", "voltage"} <= metric_keys
    assert active_runtime["current_curve_source"] == "runtime_metric_series"
    assert active_runtime["current_curve_source"] == "runtime_metric_series"

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    runtime_item = next(
        item for item in payload["items"] if item["record_source"] == "active_runtime"
    )
    assert runtime_item["current_curve_source"] == "runtime_metric_series"


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
    live_history_items = [item for item in live_items if item["record_source"] == "sealed_history"]

    assert len(live_items) == 2
    assert live_history_items == []
    assert all(item["id"].endswith("-15") for item in live_items)


@pytest.mark.asyncio
async def test_refresh_heat_runtime_rejects_flat_zero_power_signal(client, monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    zero_points = [
        CurvePoint(
            timestamp=int(
                (datetime(2026, 3, 19, 8, 0) + timedelta(minutes=index)).timestamp() * 1000
            ),
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
async def test_refresh_heat_runtime_reuses_active_birth_context_after_first_birth(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))
    resolver_state = {"allow_global_context": True}

    async def fake_load_live_heat_inference_power_points(_channel):
        return live_points

    def fake_resolve_live_heat_inference_context():
        if not resolver_state["allow_global_context"]:
            raise AssertionError("active runtime should stop depending on global inference context")
        return _build_test_live_context(
            baseline_id=FORMAL_PRIMARY_BASELINE_ID,
            expected_duration_minutes=30,
        )

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        fake_resolve_live_heat_inference_context,
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_STREAM_PROCESSOR_STATE.clear()

    first_refresh_meta = await heats_module.refresh_heat_runtime_state(reason="test")

    active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    assert active_runtime["birth_context"]["primary_baseline_id"] == FORMAL_PRIMARY_BASELINE_ID
    assert heats_module._HEAT_STREAM_PROCESSOR_STATE["config"]["expected_duration_minutes"] == 30
    assert first_refresh_meta["refresh_outcome"] == "new_heat_born"

    resolver_state["allow_global_context"] = False
    second_refresh_meta = await heats_module.refresh_heat_runtime_state(reason="test")

    refreshed_active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    assert (
        refreshed_active_runtime["birth_context"]["primary_baseline_id"]
        == FORMAL_PRIMARY_BASELINE_ID
    )
    assert heats_module._HEAT_STREAM_PROCESSOR_STATE["config"]["expected_duration_minutes"] == 30
    assert second_refresh_meta["refresh_outcome"] == "no_new_heat_born"


@pytest.mark.asyncio
async def test_refresh_heat_runtime_reuses_frozen_cutting_config_after_first_birth(
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
    heats_module._HEAT_STREAM_PROCESSOR_STATE.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")

    first_active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    first_cutting_token = heats_module._HEAT_STREAM_PROCESSOR_STATE["config"][
        "cutting_config_token"
    ]
    assert (
        first_active_runtime["birth_context"]["cutting_config_snapshot"]["fixed_interval_minutes"]
        == 15
    )
    assert (
        first_active_runtime["birth_context"]["cutting_config_snapshot"]["cutting_mode"]
        == "fixed_interval"
    )

    _SETTINGS_STORE["cutting_mode"]["value"] = "signal_inference"
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = ""
    second_refresh_meta = await heats_module.refresh_heat_runtime_state(reason="test")

    second_active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    assert second_active_runtime["id"] == first_active_runtime["id"]
    assert (
        second_active_runtime["birth_context"]["cutting_config_snapshot"]["fixed_interval_minutes"]
        == 15
    )
    assert (
        heats_module._HEAT_STREAM_PROCESSOR_STATE["config"]["cutting_config_token"]
        == first_cutting_token
    )
    assert second_refresh_meta["refresh_outcome"] in {"no_new_heat_born", "active_heat_continues"}


@pytest.mark.asyncio
async def test_refresh_heat_runtime_updates_existing_active_without_recompiling_same_heat(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    full_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))
    current_points = full_points[:-9]

    async def fake_load_live_heat_inference_power_points(_channel):
        return current_points

    async def fail_compile(*_args, **_kwargs):
        raise AssertionError(
            "same active heat refresh should not re-enter compile_runtime_candidates"
        )

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
    heats_module._HEAT_STREAM_PROCESSOR_STATE.clear()

    first_refresh_meta = await heats_module.refresh_heat_runtime_state(reason="test")
    first_active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    first_end_time = first_active_runtime["end_time"]
    assert first_refresh_meta["refresh_outcome"] == "new_heat_born"

    current_points = full_points
    monkeypatch.setattr("src.api.heats.compile_runtime_candidates", fail_compile)
    second_refresh_meta = await heats_module.refresh_heat_runtime_state(reason="test")

    second_active_runtime = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    assert second_active_runtime["id"] == first_active_runtime["id"]
    assert second_active_runtime["end_time"] > first_end_time
    assert second_refresh_meta["refresh_outcome"] == "active_heat_continues"


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
        "deviation_score": 697.4947,
        "avg_deviation_score": 697.4947,
    }

    await heats_module.refresh_heat_runtime_state(reason="test")

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    runtime_items = [
        item
        for item in payload["items"]
        if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    history_items = [item for item in payload["items"] if item["record_source"] == "sealed_history"]
    assert len(runtime_items) == 2
    assert all(
        from_timestamp_ms(item["start_time"]).date() == datetime(2026, 3, 23).date()
        for item in runtime_items
    )
    assert history_items
    assert all(item["deviation_score"] is not None for item in runtime_items)
    assert all(item["avg_deviation_score"] is not None for item in runtime_items)
    assert all(item["deviation_score"] != 697.4947 for item in runtime_items)
    assert all(item["avg_deviation_score"] != 697.4947 for item in runtime_items)


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
        item
        for item in payload["items"]
        if item["record_source"] in {"active_runtime", "previous_runtime"}
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
    active_item = next(
        item for item in list_response.json()["items"] if item["completion_status"] == "in_progress"
    )

    detail_response = await client.get(f"/api/heats/{active_item['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == active_item["id"]

    compare_response = await client.get(f"/api/heats/{active_item['id']}/compare")
    assert compare_response.status_code == 200
    assert compare_response.json()["heat"]["id"] == active_item["id"]
    assert compare_response.json()["deviation_score"] == pytest.approx(
        active_item["deviation_score"]
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
        item
        for item in payload["items"]
        if item["record_source"] in {"active_runtime", "previous_runtime"}
    ]
    history_items = [item for item in payload["items"] if item["record_source"] == "sealed_history"]
    live_history_items = [item for item in history_items if item["id"].startswith("live-heat-")]
    assert len(runtime_items) == 2
    assert runtime_items[0]["record_source"] == "active_runtime"
    assert runtime_items[1]["record_source"] == "previous_runtime"
    assert live_history_items == []
    assert any(item["id"] == "heat-001" for item in history_items)


@pytest.mark.asyncio
async def test_previous_runtime_id_stays_resolvable_after_rollover(client, monkeypatch) -> None:
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
    assert first_previous_item["deviation_score"] is not None

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
    assert second_previous_item["deviation_score"] == pytest.approx(
        first_previous_item["deviation_score"]
    )


@pytest.mark.asyncio
async def test_previous_runtime_extends_n_plus_1_context_without_recomputing_analysis(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    initial_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 28],
    )
    current_points = list(initial_points)

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
    first_previous_item = next(iter(heats_module._PREVIOUS_HEAT_RUNTIME.values()))
    first_active_item = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))
    first_previous_context_end = first_previous_item["context_end_time"]
    first_previous_deviation = first_previous_item["deviation_score"]

    assert first_previous_item["context_end_time"] == first_active_item["end_time"]
    assert first_previous_item["last_point_at"] == first_active_item["end_time"]

    current_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 30],
    )
    await heats_module.refresh_heat_runtime_state(reason="test")

    second_previous_item = next(iter(heats_module._PREVIOUS_HEAT_RUNTIME.values()))
    second_active_item = next(iter(heats_module._ACTIVE_HEAT_RUNTIME.values()))

    assert second_previous_item["id"] == first_previous_item["id"]
    assert second_active_item["id"] == first_active_item["id"]
    assert second_previous_item["context_end_time"] == second_active_item["end_time"]
    assert second_previous_item["context_end_time"] > first_previous_context_end
    assert second_previous_item["last_point_at"] == second_active_item["end_time"]
    assert second_previous_item["deviation_score"] == pytest.approx(first_previous_deviation)

    expected_last_timestamp = int(second_active_item["end_time"].timestamp() * 1000)
    power_points = second_previous_item["runtime_metric_series"][0]["series_json"]["points"]
    assert power_points[-1]["timestamp"] == expected_last_timestamp
    baseline_view_points = (
        second_previous_item["baseline_views"][0]["current_metric_series"][0]["series_json"]["points"]
    )
    assert baseline_view_points[-1]["timestamp"] == expected_last_timestamp


@pytest.mark.asyncio
async def test_sealed_history_persists_previous_runtime_context_window_from_runtime_source(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    current_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 28],
    )

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
    from src.database import async_session_maker
    from src.models import Heat, MetricSeries

    heats_module._HEAT_STORE.clear()
    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_ID_ALIAS_STORE.clear()

    await heats_module.refresh_heat_runtime_state(reason="test")
    first_previous_item = next(iter(heats_module._PREVIOUS_HEAT_RUNTIME.values()))
    expected_context_end = first_previous_item["context_end_time"]

    current_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 28, 28],
    )
    await heats_module.refresh_heat_runtime_state(reason="test")

    detail_response = await client.get(f"/api/heats/{first_previous_item['id']}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["id"] == first_previous_item["id"]
    assert detail_payload["record_source"] == "sealed_history"
    assert detail_payload["context_end_time"] == to_timestamp_ms(expected_context_end)

    async with async_session_maker() as session:
        heat_row = await session.get(Heat, first_previous_item["id"])
        metric_row = await session.get(
            MetricSeries,
            (first_previous_item["id"], "001"),
        )

    assert heat_row is not None
    assert heat_row.context_end_time == expected_context_end
    assert metric_row is not None
    metric_series_payload = json.loads(metric_row.series_json)
    assert metric_series_payload["context_end_time"] == to_timestamp_ms(expected_context_end)


@pytest.mark.asyncio
async def test_live_refresh_does_not_compile_raw_sealed_candidates_when_previous_runtime_exists(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    current_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 28],
    )

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
    first_previous_item = next(iter(heats_module._PREVIOUS_HEAT_RUNTIME.values()))

    real_compile_runtime_candidates = heats_module.compile_runtime_candidates
    compiled_candidate_batches: list[list[str]] = []

    async def recording_compile_runtime_candidates(candidates, **kwargs):
        compiled_candidate_batches.append([str(candidate.get("id") or "") for candidate in candidates])
        return await real_compile_runtime_candidates(candidates, **kwargs)

    monkeypatch.setattr(
        "src.api.heats.compile_runtime_candidates",
        recording_compile_runtime_candidates,
    )

    current_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 28, 28],
    )
    await heats_module.refresh_heat_runtime_state(reason="test")

    compiled_candidate_ids = {
        candidate_id
        for batch in compiled_candidate_batches
        for candidate_id in batch
    }
    assert first_previous_item["id"] not in compiled_candidate_ids


@pytest.mark.asyncio
async def test_live_refresh_errors_when_sealed_segment_cannot_resolve_through_previous_only(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    current_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 28, 28],
    )

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

    current_points = _build_live_power_points_with_heat_lengths(
        datetime(2026, 3, 19, 8, 0),
        [28, 28, 28, 28],
    )
    with pytest.raises(ValueError, match="sealed_runtime_source_missing"):
        await heats_module.refresh_heat_runtime_state(reason="test")


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
    assert preview_window[0] < preview_window[1]
    assert baseline_window[0] < baseline_window[1]


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
        CurvePoint(timestamp=1_775_308_000_000 + index * 60_000, value=0.0) for index in range(30)
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
        CurvePoint(
            timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
            value=120.0,
        )
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
                "deviation_score": None,
                "avg_deviation_score": None,
                "abnormal_duration_minutes": 0,
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

    response = await client.get(
        "/api/heats", params={"status": "abnormal", "page": 1, "page_size": 10}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "heat-live-1"
    assert payload["items"][0]["status"] == "abnormal"
    assert payload["items"][0]["deviation_score"] is None


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
async def test_heat_compare_runtime_prefers_runtime_snapshots_without_request_time_fetch(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    start_time = datetime(2026, 3, 24, 8, 0)
    end_time = start_time + timedelta(minutes=30)
    context_start_time = start_time - timedelta(minutes=10)
    context_end_time = end_time + timedelta(minutes=10)
    binding_payload = {
        "heat_id": "runtime-compare-001",
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_definition_id": "def-001",
        "baseline_item": "001",
        "is_primary": True,
        "baseline_effective_from": start_time,
        "tolerance_percent": 5.0,
        "analysis_status": "ready",
        "deviation_score": 1.5,
        "avg_deviation_score": 0.7,
        "analysis_details_json": None,
        "abnormal_duration_minutes": 0.0,
    }
    runtime_power_curve = [
        CurvePoint(
            timestamp=int((context_start_time + timedelta(minutes=index)).timestamp() * 1000),
            value=500.0 + index,
        )
        for index in range(5)
    ]
    runtime_voltage_curve = [
        CurvePoint(
            timestamp=int((context_start_time + timedelta(minutes=index)).timestamp() * 1000),
            value=350.0 + index,
        )
        for index in range(5)
    ]
    baseline_power_curve = [
        CurvePoint(
            timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
            value=480.0 + index,
        )
        for index in range(4)
    ]
    baseline_voltage_curve = [
        CurvePoint(
            timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
            value=340.0 + index,
        )
        for index in range(4)
    ]

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heats_module._ACTIVE_HEAT_RUNTIME["runtime-compare-001"] = {
        "id": "runtime-compare-001",
        "heat_no": "H20260324-0800",
        "description": "运行态 compare",
        "start_time": start_time,
        "end_time": end_time,
        "context_start_time": context_start_time,
        "context_end_time": context_end_time,
        "completion_status": "in_progress",
        "last_point_at": end_time,
        "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_version_id": FORMAL_PRIMARY_BASELINE_ID,
        "baseline_effective_from": start_time,
        "baseline_ids": [FORMAL_PRIMARY_BASELINE_ID],
        "baseline_bindings": [binding_payload],
        "deviation_score": 1.5,
        "avg_deviation_score": 0.7,
        "abnormal_duration_minutes": 0.0,
        "schedule_tag": "work",
        "cut_reason": "live_inferred",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "normal",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "runtime_metric_series",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": start_time,
        "power_curve": runtime_power_curve[1:4],
        "voltage_curve": runtime_voltage_curve[1:4],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": [
            {
                "metric_key": "power",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#409EFF",
                "series_json": {
                    "context_start_time": context_start_time,
                    "heat_start_time": start_time,
                    "heat_end_time": end_time,
                    "context_end_time": context_end_time,
                    "points": [
                        {"timestamp": int(point.timestamp), "value": float(point.value)}
                        for point in runtime_power_curve
                    ],
                },
            },
            {
                "metric_key": "voltage",
                "metric_name": "A相电压",
                "unit": "V",
                "color": "#67C23A",
                "series_json": {
                    "context_start_time": context_start_time,
                    "heat_start_time": start_time,
                    "heat_end_time": end_time,
                    "context_end_time": context_end_time,
                    "points": [
                        {"timestamp": int(point.timestamp), "value": float(point.value)}
                        for point in runtime_voltage_curve
                    ],
                },
            },
        ],
        "birth_context": {
            "heat_id": "runtime-compare-001",
            "channel_key": "2349:199",
            "cutting_mode": "signal_inference",
            "expected_duration_minutes": 30,
            "plant_timezone": "Asia/Shanghai",
            "cutting_config_snapshot": {
                "time_tolerance_percent": 10.0,
                "major_issue_duration_minutes": 6,
                "plant_timezone": "Asia/Shanghai",
                "work_start_time": "08:00",
                "work_end_time": "20:00",
                "break_periods": [],
                "cutting_mode": "signal_inference",
                "fixed_interval_minutes": None,
            },
            "primary_baseline_id": FORMAL_PRIMARY_BASELINE_ID,
            "baseline_bindings_snapshot": [binding_payload],
            "definition_metric_snapshots": [
                {
                    "item": "001",
                    "metric_key": "power",
                    "metric_name": "总有功功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "sort_order": 1,
                    "edc_channel_id": "2349-199",
                    "source_channel_name": "总有功功率",
                    "source_channel_label": "测试设备 / 总有功功率 / kW",
                    "enabled": True,
                },
                {
                    "item": "002",
                    "metric_key": "voltage",
                    "metric_name": "A相电压",
                    "unit": "V",
                    "color": "#67C23A",
                    "sort_order": 2,
                    "edc_channel_id": "2349-128",
                    "source_channel_name": "A相电压",
                    "source_channel_label": "测试设备 / A相电压 / V",
                    "enabled": True,
                },
            ],
            "baseline_curve_snapshots": [
                {
                    "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
                    "metric_key": "power",
                    "curve_source": "runtime_snapshot",
                    "points": [
                        {"timestamp": int(point.timestamp), "value": float(point.value)}
                        for point in baseline_power_curve
                    ],
                },
                {
                    "baseline_id": FORMAL_PRIMARY_BASELINE_ID,
                    "metric_key": "voltage",
                    "curve_source": "runtime_snapshot",
                    "points": [
                        {"timestamp": int(point.timestamp), "value": float(point.value)}
                        for point in baseline_voltage_curve
                    ],
                },
            ],
        },
    }

    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare should not request-time fetch EDC curves")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window", fail_runtime_compare_fetch
    )
    monkeypatch.setattr(
        "src.api.heats._load_metric_current_curves_from_edc", fail_runtime_compare_fetch
    )
    monkeypatch.setattr("src.api.heats._hydrate_compare_baselines", fail_runtime_compare_fetch)

    compare_resp = await client.get("/api/heats/runtime-compare-001/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["heat"]["current_curve_source"] == "runtime_metric_series"
    assert payload["baselines"][0]["baseline"]["id"] == FORMAL_PRIMARY_BASELINE_ID

    power_metric = next(
        item for item in payload["baselines"][0]["metric_curves"] if item["metric_key"] == "power"
    )
    assert len(power_metric["current_curve"]) == len(runtime_power_curve)
    assert len(power_metric["baseline_curve"]) == len(baseline_power_curve)
    assert power_metric["current_curve"][0]["value"] == 500.0
    assert power_metric["baseline_curve"][0]["value"] == 480.0


@pytest.mark.asyncio
async def test_heat_compare_runtime_uses_each_baseline_view_metric_subset(
    client, monkeypatch
) -> None:
    import src.api.heats as heats_module

    start_time = datetime(2026, 3, 24, 9, 0)
    end_time = start_time + timedelta(minutes=30)
    context_start_time = start_time - timedelta(minutes=10)
    context_end_time = end_time + timedelta(minutes=10)
    baseline_a_id = "runtime-view-a:001"
    baseline_b_id = "runtime-view-b:001"

    union_series = [
        _build_runtime_metric_series_entry(
            heat_id="runtime-compare-multi-001",
            item="001",
            metric_key="power",
            metric_name="总有功功率",
            unit="kW",
            color="#409EFF",
            source_channel_id="2349-199",
            source_channel_name="总有功功率",
            source_channel_label="测试设备 / 总有功功率 / kW",
            points=[
                CurvePoint(
                    timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
                    value=500.0 + index,
                )
                for index in range(4)
            ],
            sort_order=1,
        ),
        _build_runtime_metric_series_entry(
            heat_id="runtime-compare-multi-001",
            item="002",
            metric_key="voltage",
            metric_name="A相电压",
            unit="V",
            color="#67C23A",
            source_channel_id="2349-128",
            source_channel_name="A相电压",
            source_channel_label="测试设备 / A相电压 / V",
            points=[
                CurvePoint(
                    timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
                    value=350.0 + index,
                )
                for index in range(4)
            ],
            sort_order=2,
        ),
        _build_runtime_metric_series_entry(
            heat_id="runtime-compare-multi-001",
            item="003",
            metric_key="temperature",
            metric_name="熔炼温度",
            unit="℃",
            color="#E6A23C",
            source_channel_id="2054-128",
            source_channel_name="热电偶温度采集通道",
            source_channel_label="测试设备 / 熔炼温度 / ℃",
            points=[
                CurvePoint(
                    timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
                    value=1550.0 + index * 3,
                )
                for index in range(4)
            ],
            sort_order=3,
        ),
    ]

    baseline_curve_snapshots = [
        {
            "baseline_id": baseline_a_id,
            "metric_key": "power",
            "curve_source": "runtime_snapshot",
            "points": [
                {
                    "timestamp": int(
                        (start_time + timedelta(minutes=index * 10)).timestamp() * 1000
                    ),
                    "value": 480.0 + index,
                }
                for index in range(4)
            ],
        },
        {
            "baseline_id": baseline_a_id,
            "metric_key": "voltage",
            "curve_source": "runtime_snapshot",
            "points": [
                {
                    "timestamp": int(
                        (start_time + timedelta(minutes=index * 10)).timestamp() * 1000
                    ),
                    "value": 340.0 + index,
                }
                for index in range(4)
            ],
        },
        {
            "baseline_id": baseline_b_id,
            "metric_key": "power",
            "curve_source": "runtime_snapshot",
            "points": [
                {
                    "timestamp": int(
                        (start_time + timedelta(minutes=index * 10)).timestamp() * 1000
                    ),
                    "value": 470.0 + index,
                }
                for index in range(4)
            ],
        },
        {
            "baseline_id": baseline_b_id,
            "metric_key": "temperature",
            "curve_source": "runtime_snapshot",
            "points": [
                {
                    "timestamp": int(
                        (start_time + timedelta(minutes=index * 10)).timestamp() * 1000
                    ),
                    "value": 1540.0 + index * 2,
                }
                for index in range(4)
            ],
        },
    ]

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heats_module._ACTIVE_HEAT_RUNTIME["runtime-compare-multi-001"] = {
        "id": "runtime-compare-multi-001",
        "heat_no": "H20260324-0900",
        "description": "运行态多基线 compare",
        "start_time": start_time,
        "end_time": end_time,
        "context_start_time": context_start_time,
        "context_end_time": context_end_time,
        "completion_status": "in_progress",
        "last_point_at": end_time,
        "baseline_id": baseline_a_id,
        "baseline_version_id": baseline_a_id,
        "baseline_effective_from": start_time,
        "baseline_ids": [baseline_a_id, baseline_b_id],
        "baseline_bindings": [
            {
                "heat_id": "runtime-compare-multi-001",
                "baseline_id": baseline_a_id,
                "baseline_definition_id": "runtime-view-a",
                "baseline_item": "001",
                "is_primary": True,
                "baseline_effective_from": start_time,
                "tolerance_percent": 10.0,
                "analysis_status": "ready",
                "deviation_score": 1.5,
                "avg_deviation_score": 0.7,
                "analysis_details_json": '{"abnormal_ranges":[]}',
                "abnormal_duration_minutes": 0.0,
            },
            {
                "heat_id": "runtime-compare-multi-001",
                "baseline_id": baseline_b_id,
                "baseline_definition_id": "runtime-view-b",
                "baseline_item": "001",
                "is_primary": False,
                "baseline_effective_from": start_time,
                "tolerance_percent": 12.0,
                "analysis_status": "ready",
                "deviation_score": 2.1,
                "avg_deviation_score": 1.1,
                "analysis_details_json": '{"abnormal_ranges":[]}',
                "abnormal_duration_minutes": 0.0,
            },
        ],
        "deviation_score": 1.5,
        "avg_deviation_score": 0.7,
        "abnormal_duration_minutes": 0.0,
        "schedule_tag": "work",
        "cut_reason": "live_inferred",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": "normal",
        "temperature": None,
        "record_source": "active_runtime",
        "current_curve_source": "runtime_metric_series",
        "baseline_curve_source": "runtime_snapshot",
        "created_at": start_time,
        "power_curve": [],
        "voltage_curve": [],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "runtime_metric_series": union_series,
        "baseline_views": [
            {
                "heat_id": "runtime-compare-multi-001",
                "baseline_id": baseline_a_id,
                "baseline_definition_id": "runtime-view-a",
                "baseline_item": "001",
                "is_primary": True,
                "baseline_effective_from": start_time,
                "tolerance_percent": 10.0,
                "required_metric_keys": ["power", "voltage"],
                "current_metric_series": union_series[:2],
                "analysis_status": "ready",
                "deviation_score": 1.5,
                "avg_deviation_score": 0.7,
                "analysis_details_json": '{"abnormal_ranges":[]}',
                "abnormal_duration_minutes": 0.0,
            },
            {
                "heat_id": "runtime-compare-multi-001",
                "baseline_id": baseline_b_id,
                "baseline_definition_id": "runtime-view-b",
                "baseline_item": "001",
                "is_primary": False,
                "baseline_effective_from": start_time,
                "tolerance_percent": 12.0,
                "required_metric_keys": ["power", "temperature"],
                "current_metric_series": [union_series[0], union_series[2]],
                "analysis_status": "ready",
                "deviation_score": 2.1,
                "avg_deviation_score": 1.1,
                "analysis_details_json": '{"abnormal_ranges":[]}',
                "abnormal_duration_minutes": 0.0,
            },
        ],
        "definition_metric_snapshots": [],
        "birth_context": {
            "heat_id": "runtime-compare-multi-001",
            "channel_key": "2349:199",
            "cutting_mode": "signal_inference",
            "expected_duration_minutes": 30,
            "plant_timezone": "Asia/Shanghai",
            "cutting_config_snapshot": {
                "time_tolerance_percent": 10.0,
                "major_issue_duration_minutes": 6,
                "plant_timezone": "Asia/Shanghai",
                "work_start_time": "08:00",
                "work_end_time": "20:00",
                "break_periods": [],
                "cutting_mode": "signal_inference",
                "fixed_interval_minutes": None,
            },
            "primary_baseline_id": baseline_a_id,
            "baseline_bindings_snapshot": [],
            "definition_metric_snapshots": [],
            "baseline_curve_snapshots": baseline_curve_snapshots,
        },
        "baseline_curve_snapshots": baseline_curve_snapshots,
    }

    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare should not request-time fetch EDC curves")

    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr(
        "src.api.heats._load_heat_curves_from_edc_window", fail_runtime_compare_fetch
    )
    monkeypatch.setattr(
        "src.api.heats._load_metric_current_curves_from_edc", fail_runtime_compare_fetch
    )
    monkeypatch.setattr("src.api.heats._hydrate_compare_baselines", fail_runtime_compare_fetch)

    compare_resp = await client.get("/api/heats/runtime-compare-multi-001/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    baseline_payloads = {item["baseline"]["id"]: item for item in payload["baselines"]}
    assert {
        metric["metric_key"] for metric in baseline_payloads[baseline_a_id]["metric_curves"]
    } == {"power", "voltage"}
    assert {
        metric["metric_key"] for metric in baseline_payloads[baseline_b_id]["metric_curves"]
    } == {"power", "temperature"}


@pytest.mark.asyncio
async def test_heat_compare_reuses_short_ttl_cache(client, monkeypatch) -> None:
    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare cache 命中前后都不应 request-time hydrate/fetch")

    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fail_runtime_compare_fetch)

    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
    heat_id = _seed_runtime_heat()
    first_resp = await client.get(f"/api/heats/{heat_id}/compare")
    second_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert first_resp.json() == second_resp.json()
    assert first_resp.json()["heat"]["current_curve_source"] == "runtime_metric_series"


@pytest.mark.asyncio
async def test_heat_compare_reuses_shared_baseline_cache_across_different_heats(
    client,
    monkeypatch,
) -> None:
    async def fail_runtime_compare_fetch(*_args, **_kwargs):
        raise AssertionError("runtime compare 不应走 shared baseline hydrate/cache 回源")

    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fail_runtime_compare_fetch)
    monkeypatch.setattr("src.api.heats._load_channel_curves_from_edc", fail_runtime_compare_fetch)
    import src.api.heats as heats_module

    heats_module._ACTIVE_HEAT_RUNTIME.clear()
    heats_module._PREVIOUS_HEAT_RUNTIME.clear()
    heats_module._HEAT_COMPARE_CACHE["entries"].clear()
    heats_module._COMPARE_BASELINE_CACHE["entries"].clear()
    heats_module._COMPARE_CHANNEL_CURVE_CACHE["entries"].clear()
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
    assert first_resp.json()["heat"]["current_curve_source"] == "runtime_metric_series"
    assert second_resp.json()["heat"]["current_curve_source"] == "runtime_metric_series"


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
