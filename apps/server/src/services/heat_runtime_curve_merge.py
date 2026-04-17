"""运行态指标曲线合并与覆盖范围计算。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..schemas.common import CurvePoint
from ..time_utils import from_timestamp_ms, to_timestamp_ms


def normalize_curve_points(points: list[Any] | None) -> list[CurvePoint]:
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


def merge_curve_points(
    base_points: list[CurvePoint] | None,
    incoming_points: list[CurvePoint] | None,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[CurvePoint]:
    start_ts = to_timestamp_ms(window_start) if window_start is not None else None
    end_ts = to_timestamp_ms(window_end) if window_end is not None else None
    merged_by_ts: dict[int, CurvePoint] = {}
    for point in [*(base_points or []), *(incoming_points or [])]:
        timestamp = int(point.timestamp)
        if start_ts is not None and timestamp < start_ts:
            continue
        if end_ts is not None and timestamp > end_ts:
            continue
        merged_by_ts[timestamp] = CurvePoint(timestamp=timestamp, value=float(point.value))
    return [merged_by_ts[timestamp] for timestamp in sorted(merged_by_ts)]


def merge_metric_curves(
    base_curves: dict[str, list[CurvePoint]],
    incoming_curves: dict[str, list[CurvePoint]],
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, list[CurvePoint]]:
    metric_keys = {*base_curves.keys(), *incoming_curves.keys()}
    merged: dict[str, list[CurvePoint]] = {}
    for metric_key in metric_keys:
        merged_points = merge_curve_points(
            base_curves.get(metric_key),
            incoming_curves.get(metric_key),
            window_start=window_start,
            window_end=window_end,
        )
        if merged_points:
            merged[metric_key] = merged_points
    return merged


def actual_context_bounds_from_metric_curves(
    curves_by_metric: dict[str, list[CurvePoint]],
) -> tuple[datetime | None, datetime | None]:
    timestamps = [
        int(point.timestamp)
        for points in curves_by_metric.values()
        for point in points
    ]
    if not timestamps:
        return None, None
    return from_timestamp_ms(min(timestamps)), from_timestamp_ms(max(timestamps))


def actual_context_bounds_from_runtime_series(
    runtime_series: list[dict[str, Any]] | None,
) -> tuple[datetime | None, datetime | None]:
    curves_by_metric: dict[str, list[CurvePoint]] = {}
    for entry in runtime_series or []:
        if not isinstance(entry, dict):
            continue
        metric_key = str(entry.get("metric_key") or "").strip().lower()
        if not metric_key:
            continue
        series_json = entry.get("series_json")
        if isinstance(series_json, dict):
            curves_by_metric[metric_key] = normalize_curve_points(series_json.get("points"))
    return actual_context_bounds_from_metric_curves(curves_by_metric)


def missing_metric_keys_in_window(
    *,
    curves_by_metric: dict[str, list[CurvePoint]],
    required_metric_keys: list[str],
    window_start: datetime,
    window_end: datetime,
) -> list[str]:
    start_ts = to_timestamp_ms(window_start)
    end_ts = to_timestamp_ms(window_end)
    missing: list[str] = []
    for metric_key in required_metric_keys:
        points = curves_by_metric.get(str(metric_key).strip().lower()) or []
        if not any(start_ts <= int(point.timestamp) <= end_ts for point in points):
            missing.append(str(metric_key).strip().lower())
    return missing
