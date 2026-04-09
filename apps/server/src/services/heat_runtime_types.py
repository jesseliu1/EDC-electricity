"""当前炉次 runtime 聚合对象类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..schemas.common import CurvePoint


@dataclass(slots=True)
class RuntimeDefinitionMetricSnapshot:
    item: str
    metric_key: str
    metric_name: str
    unit: str | None
    color: str
    sort_order: int
    edc_channel_id: str | None = None
    source_channel_name: str | None = None
    source_channel_label: str | None = None
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "item": self.item,
            "metric_key": self.metric_key,
            "metric_name": self.metric_name,
            "unit": self.unit,
            "color": self.color,
            "sort_order": self.sort_order,
            "edc_channel_id": self.edc_channel_id,
            "source_channel_name": self.source_channel_name,
            "source_channel_label": self.source_channel_label,
            "enabled": self.enabled,
        }


@dataclass(slots=True)
class RuntimeBaselineCurveSnapshot:
    baseline_id: str
    metric_key: str
    curve_source: str
    points: list[CurvePoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "metric_key": self.metric_key,
            "curve_source": self.curve_source,
            "points": list(self.points),
        }


@dataclass(slots=True)
class RuntimeCuttingConfigSnapshot:
    time_tolerance_percent: float
    major_issue_duration_minutes: int
    plant_timezone: str
    work_start_time: str
    work_end_time: str
    break_periods: tuple[str, ...] = ()
    cutting_mode: str = "signal_inference"
    fixed_interval_minutes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_tolerance_percent": self.time_tolerance_percent,
            "major_issue_duration_minutes": self.major_issue_duration_minutes,
            "plant_timezone": self.plant_timezone,
            "work_start_time": self.work_start_time,
            "work_end_time": self.work_end_time,
            "break_periods": list(self.break_periods),
            "cutting_mode": self.cutting_mode,
            "fixed_interval_minutes": self.fixed_interval_minutes,
        }


@dataclass(slots=True)
class HeatBirthContext:
    heat_id: str
    channel_key: str | None = None
    cutting_mode: str | None = None
    expected_duration_minutes: int | None = None
    plant_timezone: str | None = None
    cutting_config_snapshot: RuntimeCuttingConfigSnapshot | None = None
    primary_baseline_id: str | None = None
    baseline_bindings_snapshot: list[dict[str, Any]] = field(default_factory=list)
    definition_metric_snapshots: list[RuntimeDefinitionMetricSnapshot] = field(default_factory=list)
    baseline_curve_snapshots: list[RuntimeBaselineCurveSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "heat_id": self.heat_id,
            "channel_key": self.channel_key,
            "cutting_mode": self.cutting_mode,
            "expected_duration_minutes": self.expected_duration_minutes,
            "plant_timezone": self.plant_timezone,
            "cutting_config_snapshot": (
                self.cutting_config_snapshot.to_dict()
                if self.cutting_config_snapshot is not None
                else None
            ),
            "primary_baseline_id": self.primary_baseline_id,
            "baseline_bindings_snapshot": list(self.baseline_bindings_snapshot),
            "definition_metric_snapshots": [
                snapshot.to_dict() for snapshot in self.definition_metric_snapshots
            ],
            "baseline_curve_snapshots": [
                snapshot.to_dict() for snapshot in self.baseline_curve_snapshots
            ],
        }


@dataclass(slots=True)
class RuntimeHeatFacts:
    heat_id: str
    heat_no: str
    description: str | None
    furnace_id: str | None
    start_time: datetime
    end_time: datetime
    context_start_time: datetime
    context_end_time: datetime
    is_manually_adjusted: bool
    completion_status: str
    last_point_at: datetime | None
    schedule_tag: str
    cut_reason: str | None
    cut_status: str
    major_issue: bool
    blocked_by_issue: bool
    status: str
    temperature: float | None
    record_source: str
    current_curve_source: str
    baseline_curve_source: str
    created_at: datetime
    sealed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.heat_id,
            "heat_no": self.heat_no,
            "description": self.description,
            "furnace_id": self.furnace_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "context_start_time": self.context_start_time,
            "context_end_time": self.context_end_time,
            "is_manually_adjusted": self.is_manually_adjusted,
            "completion_status": self.completion_status,
            "last_point_at": self.last_point_at,
            "schedule_tag": self.schedule_tag,
            "cut_reason": self.cut_reason,
            "cut_status": self.cut_status,
            "major_issue": self.major_issue,
            "blocked_by_issue": self.blocked_by_issue,
            "status": self.status,
            "temperature": self.temperature,
            "record_source": self.record_source,
            "current_curve_source": self.current_curve_source,
            "baseline_curve_source": self.baseline_curve_source,
            "created_at": self.created_at,
            "sealed_at": self.sealed_at,
        }


@dataclass(slots=True)
class RuntimeHeatBinding:
    heat_id: str
    baseline_id: str
    baseline_definition_id: str
    baseline_item: str
    is_primary: bool
    baseline_effective_from: datetime | None
    tolerance_percent: float | None
    analysis_status: str
    deviation_score: float | None
    avg_deviation_score: float | None
    analysis_details_json: str | None
    abnormal_duration_minutes: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "heat_id": self.heat_id,
            "baseline_id": self.baseline_id,
            "baseline_version_id": self.baseline_id,
            "baseline_definition_id": self.baseline_definition_id,
            "baseline_item": self.baseline_item,
            "is_primary": self.is_primary,
            "baseline_effective_from": self.baseline_effective_from,
            "tolerance_percent": self.tolerance_percent,
            "analysis_status": self.analysis_status,
            "deviation_score": self.deviation_score,
            "avg_deviation_score": self.avg_deviation_score,
            "analysis_details_json": self.analysis_details_json,
            "abnormal_duration_minutes": self.abnormal_duration_minutes,
        }


@dataclass(slots=True)
class RuntimeMetricSeries:
    owner_key: str
    item: str
    owner_type: str
    metric_key: str
    metric_name: str
    unit: str | None
    color: str
    sort_order: int
    series_json: dict[str, Any]
    stat_json: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_key": self.owner_key,
            "item": self.item,
            "owner_type": self.owner_type,
            "metric_key": self.metric_key,
            "metric_name": self.metric_name,
            "unit": self.unit,
            "color": self.color,
            "sort_order": self.sort_order,
            "series_json": self.series_json,
            "stat_json": self.stat_json,
        }


@dataclass(slots=True)
class RuntimePresealPayload:
    heat_payload: dict[str, Any]
    binding_payloads: list[dict[str, Any]]
    metric_series_payloads: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "heat_payload": self.heat_payload,
            "binding_payloads": self.binding_payloads,
            "metric_series_payloads": self.metric_series_payloads,
        }


@dataclass(slots=True)
class RuntimeProcessingMeta:
    processing_mode: str
    trigger_source: str
    request_anchor_time: datetime | None = None
    batch_cursor: str | None = None
    last_processed_heat_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "processing_mode": self.processing_mode,
            "trigger_source": self.trigger_source,
            "request_anchor_time": self.request_anchor_time,
            "batch_cursor": self.batch_cursor,
            "last_processed_heat_id": self.last_processed_heat_id,
        }


@dataclass(slots=True)
class CurrentHeatRuntime:
    facts: RuntimeHeatFacts
    birth_context: HeatBirthContext | None = None
    bindings: list[RuntimeHeatBinding] = field(default_factory=list)
    metric_series: list[RuntimeMetricSeries] = field(default_factory=list)
    definition_metric_snapshots: list[RuntimeDefinitionMetricSnapshot] = field(default_factory=list)
    baseline_curve_snapshots: list[RuntimeBaselineCurveSnapshot] = field(default_factory=list)
    preseal_payload: RuntimePresealPayload | None = None
    processing_meta: RuntimeProcessingMeta | None = None
    refresh_meta: dict[str, Any] = field(default_factory=dict)
    power_curve: list[CurvePoint] = field(default_factory=list)
    voltage_curve: list[CurvePoint] = field(default_factory=list)
    baseline_power_curve: list[CurvePoint] = field(default_factory=list)
    baseline_voltage_curve: list[CurvePoint] = field(default_factory=list)

    def primary_binding(self) -> RuntimeHeatBinding | None:
        for binding in self.bindings:
            if binding.is_primary:
                return binding
        return self.bindings[0] if self.bindings else None

    def to_runtime_item(self) -> dict[str, Any]:
        item = self.facts.to_dict()
        primary_binding = self.primary_binding()
        item["baseline_id"] = primary_binding.baseline_id if primary_binding else None
        item["baseline_version_id"] = primary_binding.baseline_id if primary_binding else None
        item["baseline_effective_from"] = (
            primary_binding.baseline_effective_from if primary_binding else None
        )
        item["baseline_ids"] = [binding.baseline_id for binding in self.bindings]
        item["baseline_bindings"] = [binding.to_dict() for binding in self.bindings]
        item["deviation_score"] = (
            primary_binding.deviation_score if primary_binding else None
        )
        item["avg_deviation_score"] = (
            primary_binding.avg_deviation_score if primary_binding else None
        )
        item["abnormal_duration_minutes"] = (
            primary_binding.abnormal_duration_minutes if primary_binding else None
        )
        item["runtime_metric_series"] = [series.to_dict() for series in self.metric_series]
        item["birth_context"] = (
            self.birth_context.to_dict() if self.birth_context is not None else None
        )
        item["definition_metric_snapshots"] = [
            snapshot.to_dict() for snapshot in self.definition_metric_snapshots
        ]
        item["baseline_curve_snapshots"] = [
            snapshot.to_dict() for snapshot in self.baseline_curve_snapshots
        ]
        item["processing_meta"] = (
            self.processing_meta.to_dict() if self.processing_meta is not None else None
        )
        item["preseal_payload"] = (
            self.preseal_payload.to_dict() if self.preseal_payload is not None else None
        )
        item["refresh_meta"] = dict(self.refresh_meta)
        item["power_curve"] = list(self.power_curve)
        item["voltage_curve"] = list(self.voltage_curve)
        item["baseline_power_curve"] = list(self.baseline_power_curve)
        item["baseline_voltage_curve"] = list(self.baseline_voltage_curve)
        return item
