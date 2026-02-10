"""偏差分析服务。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class DeviationPoint:
    """偏差点。"""

    timestamp: float
    deviation: float


class DeviationService:
    """提供曲线对齐、偏差计算与异常区间识别。"""

    def calculate_deviation(
        self,
        baseline_curve: list[tuple[float, float]],
        current_curve: list[tuple[float, float]],
        tolerance: float,
    ) -> dict:
        """计算偏差结果。"""
        aligned_baseline, aligned_current = self._align_curves(baseline_curve, current_curve)
        if not aligned_baseline:
            return {
                "max_deviation": 0.0,
                "avg_deviation": 0.0,
                "abnormal_ranges": [],
                "status": "normal",
            }

        deviations: list[DeviationPoint] = []
        for (timestamp, baseline_value), (_, current_value) in zip(
            aligned_baseline, aligned_current, strict=False
        ):
            deviation = self._calc_point_deviation(baseline_value, current_value)
            deviations.append(DeviationPoint(timestamp=timestamp, deviation=deviation))

        abnormal_ranges = self._find_abnormal_ranges(deviations, tolerance)
        max_deviation = max(item.deviation for item in deviations)
        avg_deviation = sum(item.deviation for item in deviations) / len(deviations)

        return {
            "max_deviation": round(max_deviation, 4),
            "avg_deviation": round(avg_deviation, 4),
            "abnormal_ranges": abnormal_ranges,
            "status": "abnormal" if max_deviation > tolerance else "normal",
        }

    def _align_curves(
        self,
        baseline_curve: list[tuple[float, float]],
        current_curve: list[tuple[float, float]],
    ) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """基于最短长度做时间对齐（MVP 简化实现）。"""
        if not baseline_curve or not current_curve:
            return [], []

        target_len = min(len(baseline_curve), len(current_curve))
        baseline_aligned = self._resample_curve(baseline_curve, target_len)
        current_aligned = self._resample_curve(current_curve, target_len)
        return baseline_aligned, current_aligned

    def _resample_curve(
        self, curve: list[tuple[float, float]], target_len: int
    ) -> list[tuple[float, float]]:
        """按索引线性重采样到指定长度。"""
        if target_len <= 0 or not curve:
            return []
        if len(curve) == target_len:
            return curve
        if len(curve) == 1:
            return [curve[0]] * target_len

        result: list[tuple[float, float]] = []
        source_last = len(curve) - 1
        target_last = target_len - 1

        for i in range(target_len):
            position = (i / target_last) * source_last if target_last > 0 else 0
            left = int(position)
            right = min(left + 1, source_last)
            ratio = position - left

            t_left, v_left = curve[left]
            t_right, v_right = curve[right]
            timestamp = t_left + (t_right - t_left) * ratio
            value = v_left + (v_right - v_left) * ratio
            result.append((timestamp, value))

        return result

    def _calc_point_deviation(self, baseline_value: float, current_value: float) -> float:
        """计算单点偏差百分比。"""
        if baseline_value == 0:
            return 0.0 if current_value == 0 else 100.0
        return abs(current_value - baseline_value) / abs(baseline_value) * 100.0

    def _find_abnormal_ranges(
        self, deviations: Iterable[DeviationPoint], tolerance: float
    ) -> list[dict]:
        """识别连续超阈值区间。"""
        ranges: list[dict] = []
        current_start: float | None = None
        current_peak = 0.0
        last_timestamp: float | None = None

        for point in deviations:
            if point.deviation > tolerance:
                if current_start is None:
                    current_start = point.timestamp
                    current_peak = point.deviation
                else:
                    current_peak = max(current_peak, point.deviation)
                last_timestamp = point.timestamp
            elif current_start is not None and last_timestamp is not None:
                ranges.append(
                    {
                        "start": current_start,
                        "end": last_timestamp,
                        "deviation": round(current_peak, 4),
                    }
                )
                current_start = None
                current_peak = 0.0
                last_timestamp = None

        if current_start is not None and last_timestamp is not None:
            ranges.append(
                {
                    "start": current_start,
                    "end": last_timestamp,
                    "deviation": round(current_peak, 4),
                }
            )

        return ranges
