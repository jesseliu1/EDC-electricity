"""炉次切割策略服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from ..schemas import CurvePoint

CuttingMode = Literal["signal_inference", "fixed_interval"]

_LIVE_HEAT_GAP_MINUTES = 3
_FIXED_INTERVAL_MINIMUM_ACTIVE_MINUTES = 5
_AUTO_ACTIVITY_THRESHOLD = object()


@dataclass(frozen=True)
class HeatCuttingConfig:
    """炉次切割配置。"""

    time_tolerance_percent: float
    major_issue_duration_minutes: int
    plant_timezone: str
    work_start_time: str
    work_end_time: str
    break_periods: tuple[str, ...]
    cutting_mode: CuttingMode = "signal_inference"
    fixed_interval_minutes: int | None = None

    def cache_token(self) -> str:
        fixed_interval = (
            str(self.fixed_interval_minutes) if self.fixed_interval_minutes is not None else ""
        )
        return "|".join(
            [
                self.cutting_mode,
                fixed_interval,
                f"{self.time_tolerance_percent}",
                f"{self.major_issue_duration_minutes}",
                self.plant_timezone,
                self.work_start_time,
                self.work_end_time,
                ",".join(self.break_periods),
            ]
        )


@dataclass(frozen=True)
class HeatCuttingContext:
    """切割运行上下文。"""

    expected_duration_minutes: int


class HeatCuttingStrategy(Protocol):
    """炉次切割策略接口。"""

    mode: CuttingMode

    def infer_segments(
        self,
        points: list[CurvePoint],
        *,
        context: HeatCuttingContext,
        config: HeatCuttingConfig,
        activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
    ) -> list[list[CurvePoint]]:
        """根据策略返回切割后的炉次片段。"""


_CUTTING_STRATEGIES: dict[CuttingMode, HeatCuttingStrategy] = {}


def normalize_cutting_mode(raw_value: str | None) -> CuttingMode:
    """归一化切割模式。"""

    return "fixed_interval" if str(raw_value or "").strip() == "fixed_interval" else "signal_inference"


def build_live_heat_cache_key(
    *,
    channel_key: str,
    expected_duration_minutes: int,
    config: HeatCuttingConfig,
) -> str:
    """构造 live 炉次推断缓存键。"""

    return "|".join(
        [
            channel_key,
            str(expected_duration_minutes),
            config.cache_token(),
        ]
    )


def register_heat_cutting_strategy(strategy: HeatCuttingStrategy) -> None:
    """注册切割策略。"""

    _CUTTING_STRATEGIES[strategy.mode] = strategy


def available_heat_cutting_modes() -> tuple[CuttingMode, ...]:
    """返回当前已注册的切割模式。"""

    return tuple(_CUTTING_STRATEGIES.keys())


def infer_live_heat_segments(
    points: list[CurvePoint],
    *,
    context: HeatCuttingContext,
    config: HeatCuttingConfig,
    activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
) -> list[list[CurvePoint]]:
    """按当前配置执行 live 炉次切割。"""

    strategy = _CUTTING_STRATEGIES.get(config.cutting_mode)
    if strategy is None:
        raise ValueError(f"unsupported_cutting_mode:{config.cutting_mode}")
    return strategy.infer_segments(
        points,
        context=context,
        config=config,
        activity_threshold=activity_threshold,
    )


def infer_live_activity_threshold(points: list[CurvePoint]) -> float | None:
    """对外暴露当前活跃阈值推断，便于调试与回归。"""

    return _infer_live_activity_threshold(points)


def _percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    index = min(max(int((len(ordered) - 1) * ratio), 0), len(ordered) - 1)
    return float(ordered[index])


def _infer_live_activity_threshold(points: list[CurvePoint]) -> float | None:
    if len(points) < 10:
        return None

    values = [float(point.value) for point in points]
    if not values:
        return None
    non_zero_values = [value for value in values if abs(value) > 1e-6]
    if not non_zero_values:
        return None
    if max(non_zero_values) - min(non_zero_values) <= 1e-6:
        return None

    median = _percentile(values, 0.5)
    p75 = _percentile(values, 0.75)
    p90 = _percentile(values, 0.9)
    threshold = max(median + (p90 - median) * 0.35, p75 * 0.95)
    return round(threshold, 3)


def _infer_fixed_interval_activity_threshold(
    points: list[CurvePoint],
    *,
    fallback_threshold: float | None,
) -> float | None:
    non_zero_values = sorted(float(point.value) for point in points if abs(float(point.value)) > 1e-6)
    if not non_zero_values:
        return fallback_threshold

    low_band = _percentile(non_zero_values, 0.25)
    high_band = _percentile(non_zero_values, 0.85)
    if high_band - low_band <= 1e-6:
        return fallback_threshold if fallback_threshold is not None else round(high_band, 3)

    relaxed_midpoint = low_band + (high_band - low_band) * 0.5
    if fallback_threshold is None:
        return round(relaxed_midpoint, 3)

    # fixed_interval 需要先识别一个更宽的“活跃窗口”，否则高功率平台会被误拆成两档。
    return round(min(float(fallback_threshold), relaxed_midpoint), 3)


def _group_active_segments(
    points: list[CurvePoint],
    *,
    threshold: float,
    gap_minutes: int,
) -> list[list[CurvePoint]]:
    gap_ms = gap_minutes * 60_000
    grouped_segments: list[list[CurvePoint]] = []
    current_segment: list[CurvePoint] = []
    last_active_timestamp: int | None = None

    for point in points:
        is_active = float(point.value) >= threshold
        point_timestamp = int(point.timestamp)
        if is_active:
            if (
                current_segment
                and last_active_timestamp is not None
                and point_timestamp - last_active_timestamp > gap_ms
            ):
                grouped_segments.append(current_segment)
                current_segment = []
            current_segment.append(point)
            last_active_timestamp = point_timestamp
            continue

        if (
            current_segment
            and last_active_timestamp is not None
            and point_timestamp - last_active_timestamp <= gap_ms
        ):
            current_segment.append(point)
            continue

        if current_segment:
            grouped_segments.append(current_segment)
            current_segment = []
            last_active_timestamp = None

    if current_segment:
        grouped_segments.append(current_segment)

    return grouped_segments


def _slice_curve_points(
    points: list[CurvePoint],
    start_ts: int,
    end_ts: int,
) -> list[CurvePoint]:
    return [point for point in points if start_ts <= point.timestamp <= end_ts]


def _segment_covered_minutes(points: list[CurvePoint]) -> float:
    if not points:
        return 0.0
    start_ts = int(points[0].timestamp)
    end_ts = int(points[-1].timestamp)
    return ((end_ts - start_ts) / 60000) + 1


def _trim_segment_to_active_core(
    points: list[CurvePoint],
    *,
    threshold: float,
) -> list[CurvePoint]:
    first_active_index: int | None = None
    last_active_index: int | None = None

    for index, point in enumerate(points):
        if float(point.value) >= threshold:
            first_active_index = index
            break

    for reverse_index, point in enumerate(reversed(points)):
        if float(point.value) >= threshold:
            last_active_index = len(points) - reverse_index - 1
            break

    if first_active_index is None or last_active_index is None:
        return []
    return points[first_active_index : last_active_index + 1]


def _split_segment_by_expected_duration(
    points: list[CurvePoint],
    *,
    expected_duration_minutes: int,
    min_duration_minutes: int,
) -> list[list[CurvePoint]]:
    if not points:
        return []

    start_ts = int(points[0].timestamp)
    end_ts = int(points[-1].timestamp)
    duration_minutes = (end_ts - start_ts) / 60000
    if duration_minutes <= expected_duration_minutes * 1.6:
        return [points]

    split_count = max(int(round(duration_minutes / expected_duration_minutes)), 1)
    if split_count <= 1:
        return [points]

    total_span = max(end_ts - start_ts, 1)
    slices: list[list[CurvePoint]] = []
    for index in range(split_count):
        window_start = start_ts + int(total_span * index / split_count)
        window_end = (
            end_ts
            if index == split_count - 1
            else start_ts + int(total_span * (index + 1) / split_count)
        )
        window_points = _slice_curve_points(points, window_start, window_end)
        if not window_points:
            continue
        window_duration = (window_points[-1].timestamp - window_points[0].timestamp) / 60000
        if window_duration >= min_duration_minutes:
            slices.append(window_points)

    return slices or [points]


def _split_segment_by_fixed_interval(
    points: list[CurvePoint],
    *,
    interval_minutes: int,
) -> list[list[CurvePoint]]:
    if not points:
        return []

    if _segment_covered_minutes(points) < _FIXED_INTERVAL_MINIMUM_ACTIVE_MINUTES:
        return []

    start_ts = int(points[0].timestamp)
    interval_ms = max(interval_minutes, 1) * 60_000
    segments: list[list[CurvePoint]] = []
    current_segment: list[CurvePoint] = []
    current_boundary = start_ts + interval_ms

    for point in points:
        point_timestamp = int(point.timestamp)
        if current_segment and point_timestamp >= current_boundary:
            segments.append(current_segment)
            current_segment = []
            while point_timestamp >= current_boundary:
                current_boundary += interval_ms
        current_segment.append(point)

    if current_segment:
        segments.append(current_segment)

    return [
        segment
        for segment in segments
        if _segment_covered_minutes(segment) >= _FIXED_INTERVAL_MINIMUM_ACTIVE_MINUTES
    ]


class SignalInferenceCuttingStrategy:
    """当前默认的信号推断切割策略。"""

    mode: CuttingMode = "signal_inference"

    def infer_segments(
        self,
        points: list[CurvePoint],
        *,
        context: HeatCuttingContext,
        config: HeatCuttingConfig,
        activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
    ) -> list[list[CurvePoint]]:
        del config
        threshold = (
            _infer_live_activity_threshold(points)
            if activity_threshold is _AUTO_ACTIVITY_THRESHOLD
            else activity_threshold
        )
        if threshold is None:
            return []

        min_duration_minutes = max(int(round(context.expected_duration_minutes * 0.45)), 15)
        grouped_segments = _group_active_segments(
            points,
            threshold=threshold,
            gap_minutes=_LIVE_HEAT_GAP_MINUTES,
        )

        inferred: list[list[CurvePoint]] = []
        for segment in grouped_segments:
            duration_minutes = (segment[-1].timestamp - segment[0].timestamp) / 60000
            if duration_minutes < min_duration_minutes:
                continue
            inferred.extend(
                _split_segment_by_expected_duration(
                    segment,
                    expected_duration_minutes=context.expected_duration_minutes,
                    min_duration_minutes=min_duration_minutes,
                )
            )
        return inferred


class FixedIntervalCuttingStrategy:
    """按固定分钟数硬切割。"""

    mode: CuttingMode = "fixed_interval"

    def infer_segments(
        self,
        points: list[CurvePoint],
        *,
        context: HeatCuttingContext,
        config: HeatCuttingConfig,
        activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
    ) -> list[list[CurvePoint]]:
        del context
        if config.fixed_interval_minutes is None:
            raise ValueError("fixed_interval_minutes_required")

        threshold = (
            _infer_live_activity_threshold(points)
            if activity_threshold is _AUTO_ACTIVITY_THRESHOLD
            else activity_threshold
        )
        threshold = _infer_fixed_interval_activity_threshold(
            points,
            fallback_threshold=threshold,
        )
        if threshold is None:
            return []

        grouped_segments = _group_active_segments(
            points,
            threshold=threshold,
            gap_minutes=_LIVE_HEAT_GAP_MINUTES,
        )

        inferred: list[list[CurvePoint]] = []
        for segment in grouped_segments:
            active_segment = _trim_segment_to_active_core(segment, threshold=threshold)
            if not active_segment:
                continue
            inferred.extend(
                _split_segment_by_fixed_interval(
                    active_segment,
                    interval_minutes=config.fixed_interval_minutes,
                )
            )
        return inferred


register_heat_cutting_strategy(SignalInferenceCuttingStrategy())
register_heat_cutting_strategy(FixedIntervalCuttingStrategy())
