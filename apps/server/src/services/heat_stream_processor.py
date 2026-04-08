"""炉次点流增量处理器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from ..schemas.common import CurvePoint
from ..services.heat_cutting_service import (
    HeatCuttingConfig,
    HeatCuttingContext,
    infer_live_activity_threshold,
    infer_live_heat_segments,
)
from ..time_utils import from_timestamp_ms, to_timestamp_ms

_DEFAULT_GAP_MINUTES = 3


def _normalize_points(points: list[CurvePoint] | list[dict[str, Any]] | None) -> list[CurvePoint]:
    normalized: dict[int, CurvePoint] = {}
    for point in points or []:
        if isinstance(point, CurvePoint):
            normalized[int(point.timestamp)] = point
            continue
        if isinstance(point, dict):
            timestamp = point.get("timestamp")
            value = point.get("value")
            if timestamp is None or value is None:
                continue
            normalized[int(timestamp)] = CurvePoint(timestamp=int(timestamp), value=float(value))
    return [normalized[key] for key in sorted(normalized)]


@dataclass(slots=True)
class HeatSegment:
    points: list[CurvePoint]

    @property
    def start_timestamp(self) -> int:
        return int(self.points[0].timestamp)

    @property
    def end_timestamp(self) -> int:
        return int(self.points[-1].timestamp)

    @property
    def start_time(self) -> datetime:
        return from_timestamp_ms(self.start_timestamp)

    @property
    def end_time(self) -> datetime:
        return from_timestamp_ms(self.end_timestamp)

    def key(self) -> tuple[int, int]:
        return (self.start_timestamp, self.end_timestamp)


@dataclass(slots=True)
class HeatProcessorConfig:
    cache_key: str
    channel_key: str
    context_hash: str
    expected_duration_minutes: int
    cutting_config_token: str
    processing_mode: str

    def is_compatible(
        self,
        *,
        cache_key: str,
        channel_key: str,
        context_hash: str,
        expected_duration_minutes: int,
        cutting_config: HeatCuttingConfig,
        processing_mode: str,
    ) -> bool:
        return (
            self.cache_key == cache_key
            and self.channel_key == channel_key
            and self.context_hash == context_hash
            and self.expected_duration_minutes == expected_duration_minutes
            and self.cutting_config_token == cutting_config.cache_token()
            and self.processing_mode == processing_mode
        )

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "cache_key": self.cache_key,
            "channel_key": self.channel_key,
            "context_hash": self.context_hash,
            "expected_duration_minutes": self.expected_duration_minutes,
            "cutting_config_token": self.cutting_config_token,
            "processing_mode": self.processing_mode,
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any] | None) -> HeatProcessorConfig | None:
        if not isinstance(snapshot, dict):
            return None
        source = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else snapshot
        cache_key = str(source.get("cache_key") or "").strip()
        channel_key = str(source.get("channel_key") or "").strip()
        context_hash = str(source.get("context_hash") or "").strip()
        processing_mode = str(source.get("processing_mode") or "").strip()
        if not cache_key or not channel_key or not context_hash or not processing_mode:
            return None
        try:
            expected_duration_minutes = int(source.get("expected_duration_minutes") or 0)
        except (TypeError, ValueError):
            return None
        if expected_duration_minutes <= 0:
            return None
        return cls(
            cache_key=cache_key,
            channel_key=channel_key,
            context_hash=context_hash,
            expected_duration_minutes=expected_duration_minutes,
            cutting_config_token=str(source.get("cutting_config_token") or ""),
            processing_mode=processing_mode,
        )


@dataclass(slots=True)
class HeatProcessorState:
    bootstrapped: bool = False
    processor_phase: str = "cold_start"
    activity_threshold: float | None = None
    last_point_timestamp: int | None = None
    current_heat_id: str | None = None
    pending_seal_heat_id: str | None = None
    points_buffer: list[CurvePoint] = field(default_factory=list)

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "bootstrapped": self.bootstrapped,
            "processor_phase": self.processor_phase,
            "activity_threshold": self.activity_threshold,
            "last_point_timestamp": self.last_point_timestamp,
            "current_heat_id": self.current_heat_id,
            "pending_seal_heat_id": self.pending_seal_heat_id,
            "points_buffer": list(self.points_buffer),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any] | None) -> HeatProcessorState | None:
        if not isinstance(snapshot, dict):
            return None
        source = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else snapshot
        threshold_raw = snapshot.get("activity_threshold")
        if isinstance(source, dict):
            threshold_raw = source.get("activity_threshold")
        threshold = float(threshold_raw) if threshold_raw is not None else None
        last_point_raw = source.get("last_point_timestamp")
        last_point_timestamp = int(last_point_raw) if last_point_raw is not None else None
        return cls(
            bootstrapped=bool(source.get("bootstrapped") or False),
            processor_phase=str(source.get("processor_phase") or "cold_start"),
            activity_threshold=threshold,
            last_point_timestamp=last_point_timestamp,
            current_heat_id=(
                str(source.get("current_heat_id"))
                if source.get("current_heat_id") is not None
                else None
            ),
            pending_seal_heat_id=(
                str(source.get("pending_seal_heat_id"))
                if source.get("pending_seal_heat_id") is not None
                else None
            ),
            points_buffer=_normalize_points(source.get("points_buffer")),
        )


@dataclass(slots=True)
class HeatProcessorResult:
    active_segment: HeatSegment | None
    previous_segment: HeatSegment | None
    sealed_segments: list[HeatSegment]
    all_segments: list[HeatSegment]
    bootstrapped: bool
    last_point_timestamp: int | None
    activity_threshold: float | None


class HeatStreamProcessor:
    """滚动 buffer 的炉次状态机。"""

    def __init__(
        self,
        *,
        cache_key: str,
        channel_key: str,
        context_hash: str,
        baseline_id: str | None,
        expected_duration_minutes: int,
        cutting_config: HeatCuttingConfig,
        processing_mode: str,
        snapshot_config: HeatProcessorConfig | None = None,
        state: HeatProcessorState | None = None,
        gap_minutes: int = _DEFAULT_GAP_MINUTES,
        threshold_resolver: Callable[[list[CurvePoint]], float | None] | None = None,
    ) -> None:
        del baseline_id
        self._config = HeatProcessorConfig(
            cache_key=cache_key,
            channel_key=channel_key,
            context_hash=context_hash,
            expected_duration_minutes=expected_duration_minutes,
            cutting_config_token=cutting_config.cache_token(),
            processing_mode=processing_mode,
        )
        self._cutting_config = cutting_config
        self._cutting_context = HeatCuttingContext(
            expected_duration_minutes=expected_duration_minutes
        )
        self._processing_mode = processing_mode
        self._gap_minutes = gap_minutes
        self._threshold_resolver = threshold_resolver or infer_live_activity_threshold
        if state is not None and snapshot_config is not None and snapshot_config.is_compatible(
            cache_key=cache_key,
            channel_key=channel_key,
            context_hash=context_hash,
            expected_duration_minutes=expected_duration_minutes,
            cutting_config=cutting_config,
            processing_mode=processing_mode,
        ):
            self._state = state
        else:
            self._state = HeatProcessorState()

    @property
    def state(self) -> HeatProcessorState:
        return self._state

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "config": self._config.to_snapshot(),
            "state": self._state.to_snapshot(),
        }

    def feed_points(
        self,
        points: list[CurvePoint] | list[dict[str, Any]] | None,
        *,
        allow_sealing: bool,
        retain_tail_count: int = 2,
    ) -> HeatProcessorResult:
        merged_points = self._merge_points(points)
        return self._recompute(
            merged_points,
            allow_sealing=allow_sealing,
            retain_tail_count=retain_tail_count,
        )

    def finalize_until(
        self,
        anchor_time: datetime,
        *,
        force_close_last: bool = False,
        retain_tail_count: int = 0,
    ) -> HeatProcessorResult:
        merged_points = list(self._state.points_buffer)
        segments = self._infer_segments(merged_points)
        if not segments:
            return self._recompute(
                merged_points,
                allow_sealing=False,
                retain_tail_count=retain_tail_count,
            )

        gap_closed = (
            to_timestamp_ms(anchor_time) - segments[-1].end_timestamp
            >= self._gap_minutes * 60_000
        )
        effective_retain_count = 0 if (force_close_last or gap_closed) else max(retain_tail_count, 1)
        return self._recompute(
            merged_points,
            allow_sealing=True,
            retain_tail_count=effective_retain_count,
        )

    def _merge_points(
        self, incoming_points: list[CurvePoint] | list[dict[str, Any]] | None
    ) -> list[CurvePoint]:
        merged_by_timestamp: dict[int, CurvePoint] = {
            int(point.timestamp): point for point in self._state.points_buffer
        }
        for point in _normalize_points(incoming_points):
            merged_by_timestamp[int(point.timestamp)] = point
        merged = [merged_by_timestamp[key] for key in sorted(merged_by_timestamp)]
        if merged:
            self._state.last_point_timestamp = int(merged[-1].timestamp)
        return merged

    def _infer_segments(self, points: list[CurvePoint]) -> list[HeatSegment]:
        if not points:
            return []

        if self._state.activity_threshold is None:
            inferred_threshold = self._threshold_resolver(points)
            if inferred_threshold is not None:
                self._state.activity_threshold = inferred_threshold

        if self._state.activity_threshold is None:
            raw_segments = infer_live_heat_segments(
                points,
                context=self._cutting_context,
                config=self._cutting_config,
            )
        else:
            raw_segments = infer_live_heat_segments(
                points,
                context=self._cutting_context,
                config=self._cutting_config,
                activity_threshold=self._state.activity_threshold,
            )

        return [HeatSegment(points=segment) for segment in raw_segments if segment]

    def _recompute(
        self,
        points: list[CurvePoint],
        *,
        allow_sealing: bool,
        retain_tail_count: int,
    ) -> HeatProcessorResult:
        segments = self._infer_segments(points)
        if not segments:
            self._state.processor_phase = "buffering"
            self._state.points_buffer = self._trim_idle_buffer(points)
            return HeatProcessorResult(
                active_segment=None,
                previous_segment=None,
                sealed_segments=[],
                all_segments=[],
                bootstrapped=self._state.bootstrapped,
                last_point_timestamp=self._state.last_point_timestamp,
                activity_threshold=self._state.activity_threshold,
            )

        retain_count = max(min(retain_tail_count, len(segments)), 0)
        sealed_segments = list(segments[:-retain_count]) if allow_sealing and retain_count else (
            list(segments) if allow_sealing and retain_count == 0 else []
        )
        retained_segments = list(segments[-retain_count:]) if retain_count else []
        if not allow_sealing:
            retained_segments = list(segments[-max(retain_tail_count, 0) :]) if retain_tail_count else []
            sealed_segments = []

        if retained_segments:
            self._state.processor_phase = "tracking_active_heat"
            self._state.current_heat_id = None
            self._state.pending_seal_heat_id = None
            earliest_retained_start = retained_segments[0].start_timestamp
            self._state.points_buffer = [
                point for point in points if int(point.timestamp) >= earliest_retained_start
            ]
        else:
            self._state.processor_phase = "awaiting_seal" if sealed_segments else "buffering"
            self._state.current_heat_id = None
            self._state.pending_seal_heat_id = None
            self._state.points_buffer = self._trim_idle_buffer(points)

        if segments:
            self._state.bootstrapped = True

        active_segment = retained_segments[-1] if retained_segments else None
        previous_segment = retained_segments[-2] if len(retained_segments) >= 2 else None
        return HeatProcessorResult(
            active_segment=active_segment,
            previous_segment=previous_segment,
            sealed_segments=sealed_segments,
            all_segments=list(segments),
            bootstrapped=self._state.bootstrapped,
            last_point_timestamp=self._state.last_point_timestamp,
            activity_threshold=self._state.activity_threshold,
        )

    def _trim_idle_buffer(self, points: list[CurvePoint]) -> list[CurvePoint]:
        if not points:
            return []
        idle_window_minutes = max(
            self._config.expected_duration_minutes,
            self._gap_minutes * 4,
            15,
        )
        cutoff = int(points[-1].timestamp) - idle_window_minutes * 60_000
        return [point for point in points if int(point.timestamp) >= cutoff]
