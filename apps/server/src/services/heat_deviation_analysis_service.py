"""炉次偏离度分析服务。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..schemas.common import CurvePoint
from .deviation_service import DeviationService
from .formal_baseline_service import encode_baseline_id, load_baseline_metric_series


def _baseline_field(baseline: Any, field_name: str) -> Any:
    if isinstance(baseline, dict):
        return baseline.get(field_name)
    return getattr(baseline, field_name)


def _coerce_curve_points(points: list[CurvePoint] | list[dict[str, Any]] | None) -> list[CurvePoint]:
    normalized: list[CurvePoint] = []
    for point in points or []:
        if isinstance(point, CurvePoint):
            normalized.append(point)
            continue
        if not isinstance(point, dict):
            continue
        timestamp = point.get("timestamp")
        value = point.get("value")
        if timestamp is None or value is None:
            continue
        normalized.append(CurvePoint(timestamp=int(timestamp), value=float(value)))
    return normalized


def _curve_points_to_pairs(
    points: list[CurvePoint] | list[dict[str, Any]] | None,
) -> list[tuple[float, float]]:
    return [
        (float(point.timestamp), float(point.value))
        for point in _coerce_curve_points(points)
    ]


def _rebase_curve_points_to_window(
    points: list[CurvePoint] | list[dict[str, Any]] | None,
    *,
    target_start_time: datetime,
    target_end_time: datetime,
) -> list[CurvePoint]:
    normalized = _coerce_curve_points(points)
    if not normalized:
        return []

    target_start_ms = int(target_start_time.timestamp() * 1000)
    target_end_ms = int(target_end_time.timestamp() * 1000)
    if len(normalized) == 1:
        midpoint = target_start_ms + max(target_end_ms - target_start_ms, 0) // 2
        return [CurvePoint(timestamp=midpoint, value=float(normalized[0].value))]

    source_start_ms = int(normalized[0].timestamp)
    source_end_ms = int(normalized[-1].timestamp)
    if source_end_ms <= source_start_ms or target_end_ms <= target_start_ms:
        return [
            CurvePoint(timestamp=target_start_ms, value=float(point.value)) for point in normalized
        ]

    source_span = source_end_ms - source_start_ms
    target_span = target_end_ms - target_start_ms
    rebased: list[CurvePoint] = []
    for point in normalized:
        ratio = (int(point.timestamp) - source_start_ms) / source_span
        rebased_timestamp = target_start_ms + int(round(target_span * ratio))
        rebased.append(CurvePoint(timestamp=rebased_timestamp, value=float(point.value)))
    return rebased


def _serialize_abnormal_ranges(abnormal_ranges: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"abnormal_ranges": abnormal_ranges},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _max_abnormal_range_minutes(abnormal_ranges: Iterable[dict[str, Any]]) -> int | None:
    max_minutes = 0.0
    found = False
    for item in abnormal_ranges:
        if not isinstance(item, dict):
            continue
        start = item.get("start")
        end = item.get("end")
        if start is None or end is None:
            continue
        duration_ms = max(float(end) - float(start), 0.0)
        max_minutes = max(max_minutes, duration_ms / 60_000)
        found = True
    if not found:
        return 0
    return int(round(max_minutes))


def _merge_heat_status(existing_status: Any, analyzed_status: str | None) -> str | None:
    current_status = str(existing_status or "").strip().lower()
    if current_status == "pending":
        return existing_status if existing_status is not None else "pending"
    if analyzed_status is None:
        return existing_status if existing_status is not None else None
    if current_status == "abnormal" or analyzed_status == "abnormal":
        return "abnormal"
    if current_status == "normal" or analyzed_status == "normal":
        return "normal"
    return existing_status if existing_status is not None else analyzed_status


@dataclass(slots=True)
class BaselineCurvePayload:
    curves_by_metric: dict[str, list[CurvePoint]]
    curve_source: str

    @property
    def power_curve(self) -> list[CurvePoint]:
        return list(self.curves_by_metric.get("power") or [])

    @property
    def voltage_curve(self) -> list[CurvePoint]:
        return list(self.curves_by_metric.get("voltage") or [])


@dataclass(slots=True)
class HeatBindingAnalysis:
    baseline_id: str
    baseline_definition_id: str
    baseline_item: str
    is_primary: bool
    baseline_effective_from: datetime | None
    tolerance_percent: float | None
    analysis_status: str
    deviation_percent: float | None
    avg_deviation_percent: float | None
    deviation_details_json: str | None
    time_offset_percent: float | None
    mismatch_duration_minutes: float | None
    derived_status: str | None

    def to_runtime_binding(self) -> dict[str, Any]:
        return {
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
            "deviation_details_json": self.deviation_details_json,
            "time_offset_percent": self.time_offset_percent,
            "mismatch_duration_minutes": self.mismatch_duration_minutes,
        }


class HeatDeviationAnalysisService:
    """负责把炉次与适用黄金基线的偏离度计算收敛为统一后端服务。"""

    def __init__(self) -> None:
        self._deviation_service = DeviationService()

    async def load_baseline_curve_payloads(
        self,
        baselines: Iterable[Any],
    ) -> dict[str, BaselineCurvePayload]:
        payloads: dict[str, BaselineCurvePayload] = {}
        for baseline in baselines:
            definition_id = str(_baseline_field(baseline, "definition_id") or "")
            item = str(_baseline_field(baseline, "item") or "")
            if not definition_id or not item:
                continue
            baseline_id = encode_baseline_id(definition_id, item)
            if baseline_id in payloads:
                continue
            series_payload = await load_baseline_metric_series(definition_id, item)
            curves_by_metric: dict[str, list[CurvePoint]] = {}
            for curve in series_payload.get("curves_data") or []:
                if not isinstance(curve, dict):
                    continue
                metric_key = str(curve.get("metric_key") or "").strip().lower()
                if not metric_key:
                    continue
                points = _coerce_curve_points(curve.get("points"))
                if points:
                    curves_by_metric[metric_key] = points
            payloads[baseline_id] = BaselineCurvePayload(
                curves_by_metric=curves_by_metric,
                curve_source=str(series_payload.get("curve_source") or "none"),
            )
        return payloads

    def analyze_candidate_bindings(
        self,
        *,
        candidate: dict[str, Any],
        applicable_baselines: list[Any],
        baseline_curve_payloads: dict[str, BaselineCurvePayload],
    ) -> list[HeatBindingAnalysis]:
        current_power_curve = _coerce_curve_points(candidate.get("power_curve"))
        current_start_time = candidate["start_time"]
        current_end_time = candidate["end_time"]
        primary_baseline_id = self._resolve_primary_baseline_id(applicable_baselines)

        analyses: list[HeatBindingAnalysis] = []
        for baseline in applicable_baselines:
            baseline_definition_id = str(_baseline_field(baseline, "definition_id") or "")
            baseline_item = str(_baseline_field(baseline, "item") or "")
            if not baseline_definition_id or not baseline_item:
                continue

            baseline_id = encode_baseline_id(baseline_definition_id, baseline_item)
            tolerance_percent = _baseline_field(baseline, "tolerance_percent")
            tolerance = float(tolerance_percent) if tolerance_percent is not None else 15.0
            rebased_power_curve = _rebase_curve_points_to_window(
                baseline_curve_payloads.get(
                    baseline_id,
                    BaselineCurvePayload(curves_by_metric={}, curve_source="none"),
                ).power_curve,
                target_start_time=current_start_time,
                target_end_time=current_end_time,
            )
            analysis_status = "pending"
            deviation_percent = None
            avg_deviation_percent = None
            deviation_details_json = None
            time_offset_percent = None
            mismatch_duration_minutes = None
            derived_status = None
            if rebased_power_curve and current_power_curve:
                result = self._deviation_service.calculate_deviation(
                    baseline_curve=_curve_points_to_pairs(rebased_power_curve),
                    current_curve=_curve_points_to_pairs(current_power_curve),
                    tolerance=tolerance,
                )
                analysis_status = "ready"
                deviation_percent = result["max_deviation"]
                avg_deviation_percent = result["avg_deviation"]
                deviation_details_json = _serialize_abnormal_ranges(result["abnormal_ranges"])
                mismatch_duration_minutes = _max_abnormal_range_minutes(result["abnormal_ranges"])
                derived_status = str(result["status"])

            analyses.append(
                HeatBindingAnalysis(
                    baseline_id=baseline_id,
                    baseline_definition_id=baseline_definition_id,
                    baseline_item=baseline_item,
                    is_primary=baseline_id == primary_baseline_id,
                    baseline_effective_from=_baseline_field(baseline, "effective_from"),
                    tolerance_percent=(
                        float(tolerance_percent) if tolerance_percent is not None else None
                    ),
                    analysis_status=analysis_status,
                    deviation_percent=deviation_percent,
                    avg_deviation_percent=avg_deviation_percent,
                    deviation_details_json=deviation_details_json,
                    time_offset_percent=time_offset_percent,
                    mismatch_duration_minutes=mismatch_duration_minutes,
                    derived_status=derived_status,
                )
            )
        return analyses

    def apply_binding_analysis_to_candidate(
        self,
        *,
        candidate: dict[str, Any],
        binding_analyses: list[HeatBindingAnalysis],
    ) -> dict[str, Any]:
        prepared = dict(candidate)
        prepared["baseline_bindings"] = [
            binding.to_runtime_binding() for binding in binding_analyses
        ]
        prepared["baseline_ids"] = [binding.baseline_id for binding in binding_analyses]

        primary_binding = next((binding for binding in binding_analyses if binding.is_primary), None)
        if primary_binding is None and binding_analyses:
            primary_binding = binding_analyses[0]

        if primary_binding is not None:
            prepared["baseline_id"] = primary_binding.baseline_id
            prepared["baseline_version_id"] = primary_binding.baseline_id
            prepared["baseline_definition_id"] = primary_binding.baseline_definition_id
            prepared["baseline_item"] = primary_binding.baseline_item
            prepared["baseline_effective_from"] = primary_binding.baseline_effective_from
            prepared["deviation_percent"] = primary_binding.deviation_percent
            prepared["avg_deviation_percent"] = primary_binding.avg_deviation_percent
            prepared["time_offset_percent"] = primary_binding.time_offset_percent
            prepared["mismatch_duration_minutes"] = primary_binding.mismatch_duration_minutes
            prepared["status"] = _merge_heat_status(
                prepared.get("status"),
                primary_binding.derived_status,
            )
        else:
            prepared["baseline_id"] = None
            prepared["baseline_version_id"] = None
            prepared["baseline_definition_id"] = None
            prepared["baseline_item"] = None
            prepared["baseline_effective_from"] = None
            prepared["deviation_percent"] = None
            prepared["avg_deviation_percent"] = None
            prepared["time_offset_percent"] = None
            prepared["mismatch_duration_minutes"] = None

        return prepared

    def _resolve_primary_baseline_id(self, baselines: list[Any]) -> str | None:
        if not baselines:
            return None
        default_baseline = next(
            (baseline for baseline in baselines if bool(_baseline_field(baseline, "is_default"))),
            None,
        )
        resolved = default_baseline or baselines[0]
        definition_id = str(_baseline_field(resolved, "definition_id") or "")
        item = str(_baseline_field(resolved, "item") or "")
        if not definition_id or not item:
            return None
        return encode_baseline_id(definition_id, item)
