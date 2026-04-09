"""单 baseline 多指标统一分析策略。"""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from ...schemas.common import CurvePoint
from .strategy import (
    HeatAnalysisMetricInput,
    HeatAnalysisMetricResult,
    HeatAnalysisPointRange,
    HeatAnalysisRequest,
    HeatAnalysisResult,
    HeatAnalysisStrategy,
)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("values_empty")
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(float(value) for value in values)
    ratio = max(0.0, min(percentile, 100.0)) / 100.0
    position = ratio * (len(ordered) - 1)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return ordered[lower_index]
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    weight = position - lower_index
    return lower_value + (upper_value - lower_value) * weight


def _resample_curve(points: list[CurvePoint], target_len: int) -> list[CurvePoint]:
    if target_len <= 0 or not points:
        return []
    if len(points) == target_len:
        return list(points)
    if len(points) == 1:
        return [CurvePoint(timestamp=int(points[0].timestamp), value=float(points[0].value))] * target_len

    source_last = len(points) - 1
    target_last = target_len - 1
    resampled: list[CurvePoint] = []
    for index in range(target_len):
        position = (index / target_last) * source_last if target_last > 0 else 0.0
        left = int(math.floor(position))
        right = min(left + 1, source_last)
        ratio = position - left
        left_point = points[left]
        right_point = points[right]
        timestamp = int(
            round(float(left_point.timestamp) + (float(right_point.timestamp) - float(left_point.timestamp)) * ratio)
        )
        value = float(left_point.value) + (float(right_point.value) - float(left_point.value)) * ratio
        resampled.append(CurvePoint(timestamp=timestamp, value=value))
    return resampled


def _mad_scale(values: list[float]) -> float:
    center = median(values)
    deviations = [abs(value - center) for value in values]
    mad = median(deviations)
    return float(1.4826 * mad)


def _sum_abnormal_minutes(ranges: list[HeatAnalysisPointRange]) -> float:
    total_ms = 0.0
    for item in ranges:
        total_ms += max(float(item.end) - float(item.start), 0.0)
    return round(total_ms / 60_000, 4)


def _build_abnormal_ranges(
    timestamps: list[int],
    point_scores: list[float],
    *,
    threshold: float,
) -> list[HeatAnalysisPointRange]:
    ranges: list[HeatAnalysisPointRange] = []
    current_start: int | None = None
    current_end: int | None = None
    current_peak = 0.0
    for timestamp, score in zip(timestamps, point_scores, strict=False):
        if score >= threshold:
            if current_start is None:
                current_start = timestamp
            current_end = timestamp
            current_peak = max(current_peak, score)
            continue
        if current_start is None or current_end is None:
            continue
        ranges.append(
            HeatAnalysisPointRange(
                start=current_start,
                end=current_end,
                score=round(current_peak, 4),
            )
        )
        current_start = None
        current_end = None
        current_peak = 0.0

    if current_start is not None and current_end is not None:
        ranges.append(
            HeatAnalysisPointRange(
                start=current_start,
                end=current_end,
                score=round(current_peak, 4),
            )
        )
    return ranges


class NormalizedMultiMetricStrategy(HeatAnalysisStrategy):
    """基于单 baseline 多指标残差标准化的统一分析策略。"""

    strategy_key = "normalized_multi_metric_v1"

    def __init__(
        self,
        *,
        point_score_threshold: float = 3.0,
        heat_score_percentile: float = 95.0,
    ) -> None:
        self._point_score_threshold = float(point_score_threshold)
        self._heat_score_percentile = float(heat_score_percentile)

    def analyze(self, request: HeatAnalysisRequest) -> HeatAnalysisResult:
        if not request.metric_inputs:
            return self._pending_result("metric_inputs_missing")

        common_len = min(
            min(len(metric.baseline_points), len(metric.current_points))
            for metric in request.metric_inputs
        )
        if common_len < 2:
            return self._pending_result("metric_points_insufficient")

        metric_z_scores: list[list[float]] = []
        metric_residuals: list[list[float]] = []
        metric_timestamps: list[list[int]] = []
        metric_results_seed: list[dict[str, Any]] = []
        metric_point_energies: list[list[float]] = []
        point_timestamps: list[int] | None = None

        for metric_input in request.metric_inputs:
            aligned_baseline = _resample_curve(metric_input.baseline_points, common_len)
            aligned_current = _resample_curve(metric_input.current_points, common_len)
            baseline_values = [float(point.value) for point in aligned_baseline]
            current_values = [float(point.value) for point in aligned_current]
            scale_value = _mad_scale(baseline_values)
            if scale_value <= 0.0:
                return self._pending_result(
                    "metric_scale_invalid",
                    metric_key=metric_input.definition.metric_key,
                )
            residuals = [
                float(current_value) - float(baseline_value)
                for baseline_value, current_value in zip(baseline_values, current_values, strict=False)
            ]
            z_scores = [residual / scale_value for residual in residuals]
            point_energies = [z_score * z_score for z_score in z_scores]
            timestamps = [int(point.timestamp) for point in aligned_current]
            point_timestamps = point_timestamps or timestamps
            metric_z_scores.append(z_scores)
            metric_residuals.append(residuals)
            metric_timestamps.append(timestamps)
            metric_point_energies.append(point_energies)
            max_index = max(range(len(residuals)), key=lambda index: abs(residuals[index]))
            metric_results_seed.append(
                {
                    "metric_item": metric_input.definition.item,
                    "metric_key": metric_input.definition.metric_key,
                    "metric_name": metric_input.definition.metric_name,
                    "unit": metric_input.definition.unit,
                    "point_count": common_len,
                    "scale_method": "mad",
                    "scale_value": round(scale_value, 6),
                    "mean_abs_residual": round(
                        sum(abs(value) for value in residuals) / len(residuals),
                        6,
                    ),
                    "max_abs_residual": round(max(abs(value) for value in residuals), 6),
                    "peak_residual_at": timestamps[max_index] if timestamps else None,
                }
            )

        if point_timestamps is None:
            return self._pending_result("point_timestamps_missing")

        metric_count = len(metric_z_scores)
        point_scores = [
            math.sqrt(
                sum(metric_z_scores[metric_index][point_index] ** 2 for metric_index in range(metric_count))
                / metric_count
            )
            for point_index in range(common_len)
        ]
        deviation_score = round(_percentile(point_scores, self._heat_score_percentile), 4)
        avg_deviation_score = round(sum(point_scores) / len(point_scores), 4)
        abnormal_ranges = _build_abnormal_ranges(
            point_timestamps,
            point_scores,
            threshold=self._point_score_threshold,
        )
        abnormal_duration_minutes = _sum_abnormal_minutes(abnormal_ranges)
        contribution_totals = [
            sum(point_energies)
            for point_energies in metric_point_energies
        ]
        total_contribution = sum(contribution_totals)
        total_point_energies = [
            sum(metric_point_energies[metric_index][point_index] for metric_index in range(metric_count))
            for point_index in range(common_len)
        ]
        total_point_energy_p95 = _percentile(total_point_energies, self._heat_score_percentile)
        metric_results: list[HeatAnalysisMetricResult] = []
        for index, seed in enumerate(metric_results_seed):
            point_energies = metric_point_energies[index]
            contribution_mean = (
                contribution_totals[index] / total_contribution if total_contribution > 0 else 0.0
            )
            contribution_p95 = (
                _percentile(point_energies, self._heat_score_percentile) / total_point_energy_p95
                if total_point_energy_p95 > 0
                else 0.0
            )
            metric_results.append(
                HeatAnalysisMetricResult(
                    metric_item=str(seed["metric_item"]),
                    metric_key=str(seed["metric_key"]),
                    metric_name=str(seed["metric_name"]),
                    unit=str(seed["unit"]) if seed["unit"] is not None else None,
                    point_count=int(seed["point_count"]),
                    scale_method=str(seed["scale_method"]),
                    scale_value=float(seed["scale_value"]),
                    mean_abs_residual=float(seed["mean_abs_residual"]),
                    max_abs_residual=float(seed["max_abs_residual"]),
                    contribution_mean=round(contribution_mean, 6),
                    contribution_p95=round(contribution_p95, 6),
                    peak_residual_at=(
                        int(seed["peak_residual_at"]) if seed["peak_residual_at"] is not None else None
                    ),
                )
            )

        analysis_details = {
            "version": "v1",
            "summary_method": self.strategy_key,
            "alignment_method": "resample_common_length",
            "scale_method": "mad",
            "score_aggregation": {
                "point_score": "root_mean_square_z",
                "heat_score": f"p{int(self._heat_score_percentile)}",
                "avg_score": "mean",
                "point_score_threshold": self._point_score_threshold,
            },
            "summary": {
                "deviation_score": deviation_score,
                "avg_deviation_score": avg_deviation_score,
                "abnormal_duration_minutes": abnormal_duration_minutes,
                "point_score_threshold": self._point_score_threshold,
            },
            "metric_results": [metric_result.to_dict() for metric_result in metric_results],
            "abnormal_ranges": [item.to_dict() for item in abnormal_ranges],
            "inputs": {
                "baseline_id": request.baseline_id,
                "metric_count": metric_count,
                "common_point_count": common_len,
            },
        }
        return HeatAnalysisResult(
            analysis_status="ready",
            deviation_score=deviation_score,
            avg_deviation_score=avg_deviation_score,
            abnormal_duration_minutes=abnormal_duration_minutes,
            derived_status="abnormal" if abnormal_ranges else "normal",
            analysis_details=analysis_details,
        )

    def _pending_result(self, reason: str, **extra: Any) -> HeatAnalysisResult:
        analysis_details = {
            "version": "v1",
            "summary_method": self.strategy_key,
            "status": "pending",
            "reason": reason,
        }
        analysis_details.update(extra)
        return HeatAnalysisResult(
            analysis_status="pending",
            deviation_score=None,
            avg_deviation_score=None,
            abnormal_duration_minutes=None,
            derived_status=None,
            analysis_details=analysis_details,
        )
