"""当前炉次 runtime 聚合对象类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..schemas.common import CurvePoint


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
    deviation_percent: float | None
    avg_deviation_percent: float | None
    time_offset_percent: float | None
    mismatch_duration_minutes: float | None

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
            "deviation_percent": self.deviation_percent,
            "avg_deviation_percent": self.avg_deviation_percent,
            "time_offset_percent": self.time_offset_percent,
            "mismatch_duration_minutes": self.mismatch_duration_minutes,
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
    bindings: list[RuntimeHeatBinding] = field(default_factory=list)
    metric_series: list[RuntimeMetricSeries] = field(default_factory=list)
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
        item["deviation_percent"] = (
            primary_binding.deviation_percent if primary_binding else None
        )
        item["avg_deviation_percent"] = (
            primary_binding.avg_deviation_percent if primary_binding else None
        )
        item["time_offset_percent"] = (
            primary_binding.time_offset_percent if primary_binding else None
        )
        item["mismatch_duration_minutes"] = (
            primary_binding.mismatch_duration_minutes if primary_binding else None
        )
        item["runtime_metric_series"] = [series.to_dict() for series in self.metric_series]
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
