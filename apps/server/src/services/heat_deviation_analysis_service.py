"""炉次统一分析服务。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..observability import log_event
from ..schemas.common import CurvePoint
from .heat_analysis import (
    HeatAnalysisMetricDefinition,
    HeatAnalysisMetricInput,
    HeatAnalysisRequest,
    NormalizedMultiMetricStrategy,
)
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


def _compact_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


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
    deviation_score: float | None
    avg_deviation_score: float | None
    analysis_details_json: str | None
    abnormal_duration_minutes: float | None
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
            "deviation_score": self.deviation_score,
            "avg_deviation_score": self.avg_deviation_score,
            "analysis_details_json": self.analysis_details_json,
            "abnormal_duration_minutes": self.abnormal_duration_minutes,
        }


class HeatDeviationAnalysisService:
    """负责把炉次与适用黄金基线的偏离度计算收敛为统一后端服务。"""

    def __init__(self) -> None:
        self._strategy = NormalizedMultiMetricStrategy()

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
        current_start_time = candidate["start_time"]
        current_end_time = candidate["end_time"]
        primary_baseline_id = self._resolve_primary_baseline_id(applicable_baselines)
        metric_inputs_by_key = self._candidate_metric_inputs(candidate)
        metric_definitions = self._definition_metric_definitions(candidate)

        analyses: list[HeatBindingAnalysis] = []
        for baseline in applicable_baselines:
            baseline_definition_id = str(_baseline_field(baseline, "definition_id") or "")
            baseline_item = str(_baseline_field(baseline, "item") or "")
            if not baseline_definition_id or not baseline_item:
                continue

            baseline_id = encode_baseline_id(baseline_definition_id, baseline_item)
            tolerance_percent = _baseline_field(baseline, "tolerance_percent")
            analysis_status = "pending"
            deviation_score = None
            avg_deviation_score = None
            analysis_details_json = None
            abnormal_duration_minutes = None
            derived_status = None
            baseline_payload = baseline_curve_payloads.get(
                baseline_id,
                BaselineCurvePayload(curves_by_metric={}, curve_source="none"),
            )
            strategy_metric_inputs = self._build_strategy_metric_inputs(
                baseline_id=baseline_id,
                metric_definitions=metric_definitions,
                current_metric_points=metric_inputs_by_key,
                baseline_payload=baseline_payload,
                current_start_time=current_start_time,
                current_end_time=current_end_time,
            )
            if strategy_metric_inputs:
                result = self._strategy.analyze(
                    request=self._build_strategy_request(
                        baseline_id=baseline_id,
                        metric_inputs=strategy_metric_inputs,
                    )
                )
                if result.analysis_status != "ready":
                    log_event(
                        "heat_binding_analysis_pending",
                        heat_id=str(candidate.get("id") or ""),
                        baseline_id=baseline_id,
                        reason=str(result.analysis_details.get("reason") or "analysis_pending"),
                    )
                analysis_status = result.analysis_status
                deviation_score = result.deviation_score
                avg_deviation_score = result.avg_deviation_score
                abnormal_duration_minutes = result.abnormal_duration_minutes
                derived_status = result.derived_status
                analysis_details_json = _compact_json(result.analysis_details)
            else:
                log_event(
                    "heat_binding_analysis_pending",
                    heat_id=str(candidate.get("id") or ""),
                    baseline_id=baseline_id,
                    reason="metric_inputs_missing",
                )
                analysis_details_json = _compact_json(
                    {
                        "version": "v1",
                        "summary_method": self._strategy.strategy_key,
                        "status": "pending",
                        "reason": "metric_inputs_missing",
                    }
                )

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
                    deviation_score=deviation_score,
                    avg_deviation_score=avg_deviation_score,
                    analysis_details_json=analysis_details_json,
                    abnormal_duration_minutes=abnormal_duration_minutes,
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
            prepared["deviation_score"] = primary_binding.deviation_score
            prepared["avg_deviation_score"] = primary_binding.avg_deviation_score
            prepared["abnormal_duration_minutes"] = primary_binding.abnormal_duration_minutes
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
            prepared["deviation_score"] = None
            prepared["avg_deviation_score"] = None
            prepared["abnormal_duration_minutes"] = None

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

    def _candidate_metric_inputs(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, list[CurvePoint]]:
        curves_by_metric: dict[str, list[CurvePoint]] = {}
        runtime_series = candidate.get("runtime_metric_series")
        if isinstance(runtime_series, list):
            for entry in runtime_series:
                if not isinstance(entry, dict):
                    continue
                metric_key = str(entry.get("metric_key") or "").strip().lower()
                if not metric_key:
                    continue
                series_payload = entry.get("series_json")
                if isinstance(series_payload, dict):
                    curves_by_metric[metric_key] = _coerce_curve_points(series_payload.get("points"))
        return {metric_key: points for metric_key, points in curves_by_metric.items() if points}

    def _definition_metric_definitions(
        self,
        candidate: dict[str, Any],
    ) -> list[HeatAnalysisMetricDefinition]:
        definitions: list[HeatAnalysisMetricDefinition] = []
        raw_snapshots = candidate.get("definition_metric_snapshots")
        if not isinstance(raw_snapshots, list):
            return []
        for snapshot in raw_snapshots:
            if not isinstance(snapshot, dict):
                continue
            if snapshot.get("enabled") is False:
                continue
            metric_item = str(snapshot.get("item") or "").strip()
            metric_key = str(snapshot.get("metric_key") or "").strip().lower()
            metric_name = str(snapshot.get("metric_name") or "").strip()
            color = str(snapshot.get("color") or "").strip()
            if not metric_item or not metric_key or not metric_name or not color:
                continue
            definitions.append(
                HeatAnalysisMetricDefinition(
                    item=metric_item,
                    metric_key=metric_key,
                    metric_name=metric_name,
                    unit=(
                        str(snapshot.get("unit"))
                        if snapshot.get("unit") is not None
                        else None
                    ),
                    color=color,
                    sort_order=int(snapshot.get("sort_order") or 0),
                )
            )
        return sorted(definitions, key=lambda item: (item.sort_order, item.item))

    def _build_strategy_metric_inputs(
        self,
        *,
        baseline_id: str,
        metric_definitions: list[HeatAnalysisMetricDefinition],
        current_metric_points: dict[str, list[CurvePoint]],
        baseline_payload: BaselineCurvePayload,
        current_start_time: datetime,
        current_end_time: datetime,
    ) -> list[HeatAnalysisMetricInput]:
        inputs: list[HeatAnalysisMetricInput] = []
        for definition in metric_definitions:
            current_points = current_metric_points.get(definition.metric_key)
            baseline_points = baseline_payload.curves_by_metric.get(definition.metric_key)
            if not current_points or not baseline_points:
                log_event(
                    "heat_binding_analysis_metric_missing",
                    baseline_id=baseline_id,
                    metric_key=definition.metric_key,
                    missing_current=not bool(current_points),
                    missing_baseline=not bool(baseline_points),
                )
                continue
            rebased_baseline_points = _rebase_curve_points_to_window(
                baseline_points,
                target_start_time=current_start_time,
                target_end_time=current_end_time,
            )
            if not rebased_baseline_points:
                continue
            inputs.append(
                HeatAnalysisMetricInput(
                    definition=definition,
                    baseline_points=rebased_baseline_points,
                    current_points=list(current_points),
                )
            )
        return inputs

    def _build_strategy_request(
        self,
        *,
        baseline_id: str,
        metric_inputs: list[HeatAnalysisMetricInput],
    ) -> HeatAnalysisRequest:
        return HeatAnalysisRequest(
            baseline_id=baseline_id,
            metric_inputs=metric_inputs,
        )
