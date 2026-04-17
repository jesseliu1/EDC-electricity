"""炉次切割策略服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from ..schemas import CurvePoint
from ..time_utils import normalize_utc_datetime, to_plant_datetime, to_timestamp_ms

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
    cutting_mode: CuttingMode = "fixed_interval"
    fixed_interval_minutes: int | None = 30

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
    anchor_time: datetime | None = None


@dataclass(frozen=True)
class HeatCutBoundary:
    """单个切割边界。"""

    ideal_timestamp: int
    actual_timestamp: int
    snapped_to_active_end: bool


@dataclass(frozen=True)
class HeatCuttingSegment:
    """切割结果与边界元数据。"""

    points: list[CurvePoint]
    start_boundary: HeatCutBoundary | None = None
    end_boundary: HeatCutBoundary | None = None


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
    ) -> list[HeatCuttingSegment]:
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


def infer_live_heat_segments_with_metadata(
    points: list[CurvePoint],
    *,
    context: HeatCuttingContext,
    config: HeatCuttingConfig,
    activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
) -> list[HeatCuttingSegment]:
    """按当前配置执行炉次切割，并保留边界元数据。"""

    strategy = _CUTTING_STRATEGIES.get(config.cutting_mode)
    if strategy is None:
        raise ValueError(f"unsupported_cutting_mode:{config.cutting_mode}")
    return strategy.infer_segments(
        points,
        context=context,
        config=config,
        activity_threshold=activity_threshold,
    )


def infer_live_heat_segments(
    points: list[CurvePoint],
    *,
    context: HeatCuttingContext,
    config: HeatCuttingConfig,
    activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
) -> list[list[CurvePoint]]:
    """兼容旧调用口径，仅返回点列表。"""

    return [
        segment.points
        for segment in infer_live_heat_segments_with_metadata(
            points,
            context=context,
            config=config,
            activity_threshold=activity_threshold,
        )
    ]


def infer_live_activity_threshold(points: list[CurvePoint]) -> float | None:
    """对外暴露当前活跃阈值推断，便于调试与回归。"""

    return _infer_live_activity_threshold(points)


def resolve_live_cutting_anchor_time(
    *,
    reference_time: datetime,
    config: HeatCuttingConfig,
) -> datetime | None:
    """解析 live fixed_interval 的业务锚点。"""

    if config.cutting_mode != "fixed_interval":
        return None

    anchor_hour, anchor_minute = _parse_clock_time(config.work_start_time)
    plant_reference = to_plant_datetime(reference_time, config.plant_timezone)
    plant_anchor = plant_reference.replace(
        hour=anchor_hour,
        minute=anchor_minute,
        second=0,
        microsecond=0,
    )
    return normalize_utc_datetime(plant_anchor.astimezone(UTC))


def _parse_clock_time(raw_value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = str(raw_value or "").strip().split(":", maxsplit=1)
        hour = min(max(int(hour_text), 0), 23)
        minute = min(max(int(minute_text), 0), 59)
    except (TypeError, ValueError):
        return (0, 0)
    return (hour, minute)


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

    # fixed_interval 仍需要识别更宽的活跃窗口，但边界不再由活跃段首点驱动。
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


def _slice_between_boundaries(
    points: list[CurvePoint],
    *,
    start_ts: int,
    end_ts: int,
    include_start: bool,
) -> list[CurvePoint]:
    if include_start:
        return [point for point in points if start_ts <= point.timestamp <= end_ts]
    return [point for point in points if start_ts < point.timestamp <= end_ts]


def _segment_covered_minutes(points: list[CurvePoint]) -> float:
    if not points:
        return 0.0
    start_ts = int(points[0].timestamp)
    end_ts = int(points[-1].timestamp)
    return ((end_ts - start_ts) / 60000) + 1


def _segment_active_covered_minutes(points: list[CurvePoint], *, threshold: float) -> float:
    active_points = [point for point in points if float(point.value) >= threshold]
    if not active_points:
        return 0.0
    return _segment_covered_minutes(active_points)


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


def _collect_active_end_timestamps(
    points: list[CurvePoint],
    *,
    threshold: float,
) -> list[int]:
    active_end_timestamps: list[int] = []
    last_active_timestamp: int | None = None
    in_active_window = False

    for point in points:
        point_timestamp = int(point.timestamp)
        is_active = float(point.value) >= threshold
        if is_active:
            in_active_window = True
            last_active_timestamp = point_timestamp
            continue
        if in_active_window and last_active_timestamp is not None:
            active_end_timestamps.append(last_active_timestamp)
            in_active_window = False
            last_active_timestamp = None

    if in_active_window and last_active_timestamp is not None:
        active_end_timestamps.append(last_active_timestamp)

    return active_end_timestamps


def _resolve_fixed_interval_boundary(
    *,
    ideal_timestamp: int,
    previous_actual_timestamp: int,
    active_end_timestamps: list[int],
    tolerance_ms: int,
) -> HeatCutBoundary:
    candidate_timestamps = [
        timestamp
        for timestamp in active_end_timestamps
        if previous_actual_timestamp < timestamp <= ideal_timestamp + tolerance_ms
        and timestamp >= ideal_timestamp - tolerance_ms
    ]
    if candidate_timestamps:
        actual_timestamp = min(
            candidate_timestamps,
            key=lambda timestamp: (abs(timestamp - ideal_timestamp), timestamp),
        )
        return HeatCutBoundary(
            ideal_timestamp=ideal_timestamp,
            actual_timestamp=actual_timestamp,
            snapped_to_active_end=True,
        )

    return HeatCutBoundary(
        ideal_timestamp=ideal_timestamp,
        actual_timestamp=ideal_timestamp,
        snapped_to_active_end=False,
    )


def _build_fixed_interval_boundaries(
    *,
    points: list[CurvePoint],
    anchor_timestamp: int,
    interval_minutes: int,
    time_tolerance_percent: float,
    threshold: float,
) -> list[HeatCutBoundary]:
    interval_ms = max(interval_minutes, 1) * 60_000
    tolerance_ms = int(round(interval_ms * max(time_tolerance_percent, 0.0) / 100))
    active_end_timestamps = _collect_active_end_timestamps(points, threshold=threshold)
    boundaries: list[HeatCutBoundary] = [
        HeatCutBoundary(
            ideal_timestamp=anchor_timestamp,
            actual_timestamp=anchor_timestamp,
            snapped_to_active_end=False,
        )
    ]

    last_point_timestamp = int(points[-1].timestamp)
    next_ideal_timestamp = anchor_timestamp + interval_ms
    while next_ideal_timestamp < last_point_timestamp:
        previous_actual_timestamp = boundaries[-1].actual_timestamp
        if next_ideal_timestamp <= previous_actual_timestamp:
            next_ideal_timestamp += interval_ms
            continue
        boundaries.append(
            _resolve_fixed_interval_boundary(
                ideal_timestamp=next_ideal_timestamp,
                previous_actual_timestamp=previous_actual_timestamp,
                active_end_timestamps=active_end_timestamps,
                tolerance_ms=tolerance_ms,
            )
        )
        next_ideal_timestamp += interval_ms

    boundaries.append(
        HeatCutBoundary(
            ideal_timestamp=last_point_timestamp,
            actual_timestamp=last_point_timestamp,
            snapped_to_active_end=False,
        )
    )
    return boundaries


class SignalInferenceCuttingStrategy:
    """按信号活跃段和预期时长推断炉次。"""

    mode: CuttingMode = "signal_inference"

    def infer_segments(
        self,
        points: list[CurvePoint],
        *,
        context: HeatCuttingContext,
        config: HeatCuttingConfig,
        activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
    ) -> list[HeatCuttingSegment]:
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

        inferred: list[HeatCuttingSegment] = []
        for segment in grouped_segments:
            duration_minutes = (segment[-1].timestamp - segment[0].timestamp) / 60000
            if duration_minutes < min_duration_minutes:
                continue
            inferred.extend(
                HeatCuttingSegment(points=item)
                for item in _split_segment_by_expected_duration(
                    segment,
                    expected_duration_minutes=context.expected_duration_minutes,
                    min_duration_minutes=min_duration_minutes,
                )
                if item
            )
        return inferred


class AnchoredFixedIntervalCuttingStrategy:
    """按锚点时间轴硬切，再吸附到活跃结束点。"""

    mode: CuttingMode = "fixed_interval"

    def infer_segments(
        self,
        points: list[CurvePoint],
        *,
        context: HeatCuttingContext,
        config: HeatCuttingConfig,
        activity_threshold: float | None | object = _AUTO_ACTIVITY_THRESHOLD,
    ) -> list[HeatCuttingSegment]:
        if config.fixed_interval_minutes is None:
            raise ValueError("fixed_interval_minutes_required")
        if context.anchor_time is None:
            raise ValueError("fixed_interval_anchor_time_required")
        if not points:
            return []

        anchor_timestamp = to_timestamp_ms(context.anchor_time)
        eligible_points = [point for point in points if int(point.timestamp) >= anchor_timestamp]
        if not eligible_points:
            return []

        threshold = (
            _infer_live_activity_threshold(eligible_points)
            if activity_threshold is _AUTO_ACTIVITY_THRESHOLD
            else activity_threshold
        )
        threshold = _infer_fixed_interval_activity_threshold(
            eligible_points,
            fallback_threshold=threshold,
        )
        if threshold is None:
            return []

        boundaries = _build_fixed_interval_boundaries(
            points=eligible_points,
            anchor_timestamp=anchor_timestamp,
            interval_minutes=config.fixed_interval_minutes,
            time_tolerance_percent=config.time_tolerance_percent,
            threshold=threshold,
        )
        inferred: list[HeatCuttingSegment] = []
        for index in range(len(boundaries) - 1):
            start_boundary = boundaries[index]
            end_boundary = boundaries[index + 1]
            segment_points = _slice_between_boundaries(
                eligible_points,
                start_ts=start_boundary.actual_timestamp,
                end_ts=end_boundary.actual_timestamp,
                include_start=index == 0,
            )
            if not segment_points:
                continue
            if (
                _segment_active_covered_minutes(segment_points, threshold=threshold)
                < _FIXED_INTERVAL_MINIMUM_ACTIVE_MINUTES
            ):
                continue
            inferred.append(
                HeatCuttingSegment(
                    points=segment_points,
                    start_boundary=start_boundary,
                    end_boundary=end_boundary,
                )
            )
        return inferred


register_heat_cutting_strategy(SignalInferenceCuttingStrategy())
register_heat_cutting_strategy(AnchoredFixedIntervalCuttingStrategy())
