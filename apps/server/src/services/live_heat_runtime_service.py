"""实时炉次 runtime 刷新服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from ..schemas.common import CurvePoint
from ..services.heat_cutting_service import HeatCuttingConfig
from ..time_utils import from_timestamp_ms, utc_now
from .heat_stream_processor import (
    HeatProcessorState,
    HeatProcessorResult,
    HeatStreamProcessor,
)

_BOOTSTRAP_WINDOW_MINUTES = 180
_FETCH_OVERLAP_SECONDS = 60

LoadPointWindow = Callable[
    [dict[str, str], datetime, datetime],
    Awaitable[list[CurvePoint]],
]
ThresholdResolver = Callable[[list[CurvePoint]], float | None]


@dataclass(slots=True)
class LiveHeatRefreshResult:
    processor_state: dict[str, Any]
    processor_result: HeatProcessorResult
    fetch_start_time: datetime
    fetch_end_time: datetime
    used_bootstrap_window: bool


def _bootstrap_window_minutes(expected_duration_minutes: int) -> int:
    return max(_BOOTSTRAP_WINDOW_MINUTES, expected_duration_minutes * 4)


def _compute_fetch_window(
    *,
    processor_state: HeatProcessorState | None,
    expected_duration_minutes: int,
    current_time: datetime,
) -> tuple[datetime, datetime, bool]:
    if processor_state is None or processor_state.last_point_timestamp is None:
        return (
            current_time - timedelta(minutes=_bootstrap_window_minutes(expected_duration_minutes)),
            current_time,
            True,
        )

    overlap_start = from_timestamp_ms(processor_state.last_point_timestamp) - timedelta(
        seconds=_FETCH_OVERLAP_SECONDS
    )
    return (overlap_start, current_time, False)


async def refresh_live_heat_segments(
    *,
    context: dict[str, Any],
    cutting_config: HeatCuttingConfig,
    point_loader: LoadPointWindow,
    processor_snapshot: dict[str, Any] | None,
    processing_mode: str = "live_incremental",
    current_time: datetime | None = None,
    threshold_resolver: ThresholdResolver | None = None,
) -> LiveHeatRefreshResult:
    now = current_time or utc_now()
    restored_state = HeatProcessorState.from_snapshot(processor_snapshot)
    fetch_start_time, fetch_end_time, used_bootstrap_window = _compute_fetch_window(
        processor_state=restored_state,
        expected_duration_minutes=int(context["expected_duration_minutes"]),
        current_time=now,
    )
    processor = HeatStreamProcessor(
        cache_key=str(context["cache_key"]),
        channel_key=str(context["channel_key"]),
        context_hash=str(context["context_hash"]),
        baseline_id=context.get("baseline_id"),
        expected_duration_minutes=int(context["expected_duration_minutes"]),
        cutting_config=cutting_config,
        processing_mode=processing_mode,
        state=restored_state,
        threshold_resolver=threshold_resolver,
    )
    try:
        points = await point_loader(context["channel"], fetch_start_time, fetch_end_time)
    except TypeError:
        points = await point_loader(context["channel"])
    allow_sealing = processor.state.bootstrapped and not used_bootstrap_window
    processor_result = processor.feed_points(
        points,
        allow_sealing=allow_sealing,
        retain_tail_count=2,
    )
    return LiveHeatRefreshResult(
        processor_state=processor.snapshot_state(),
        processor_result=processor_result,
        fetch_start_time=fetch_start_time,
        fetch_end_time=fetch_end_time,
        used_bootstrap_window=used_bootstrap_window,
    )
