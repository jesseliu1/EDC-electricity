"""HeatCuttingService 单测。"""

from datetime import datetime, timedelta

from src.schemas.common import CurvePoint
from src.services.heat_cutting_service import (
    HeatCuttingConfig,
    HeatCuttingContext,
    infer_live_heat_segments_with_metadata,
)
from src.time_utils import to_timestamp_ms


def _build_cutting_config(
    *,
    cutting_mode: str = "fixed_interval",
    fixed_interval_minutes: int | None = 30,
    time_tolerance_percent: float = 10.0,
) -> HeatCuttingConfig:
    return HeatCuttingConfig(
        time_tolerance_percent=time_tolerance_percent,
        major_issue_duration_minutes=8,
        plant_timezone="Asia/Shanghai",
        work_start_time="08:00",
        work_end_time="18:00",
        break_periods=("12:00-13:00",),
        cutting_mode="fixed_interval" if cutting_mode == "fixed_interval" else "signal_inference",
        fixed_interval_minutes=fixed_interval_minutes,
    )


def _append_block(
    points: list[CurvePoint],
    *,
    start: datetime,
    offset_minutes: int,
    length_minutes: int,
    value: float,
) -> None:
    for index in range(length_minutes):
        points.append(
            CurvePoint(
                timestamp=to_timestamp_ms(start + timedelta(minutes=offset_minutes + index)),
                value=value,
            )
        )


def test_fixed_interval_snaps_boundary_to_active_end_within_tolerance() -> None:
    start = datetime(2026, 4, 17, 12, 0)
    points: list[CurvePoint] = []
    _append_block(points, start=start, offset_minutes=0, length_minutes=33, value=120.0)
    _append_block(points, start=start, offset_minutes=33, length_minutes=4, value=20.0)
    _append_block(points, start=start, offset_minutes=37, length_minutes=26, value=125.0)
    _append_block(points, start=start, offset_minutes=63, length_minutes=3, value=18.0)

    segments = infer_live_heat_segments_with_metadata(
        points,
        context=HeatCuttingContext(expected_duration_minutes=30, anchor_time=start),
        config=_build_cutting_config(),
        activity_threshold=100.0,
    )

    assert len(segments) == 2
    first_segment = segments[0]
    second_segment = segments[1]

    assert first_segment.end_boundary is not None
    assert first_segment.end_boundary.ideal_timestamp == to_timestamp_ms(
        start + timedelta(minutes=30)
    )
    assert first_segment.end_boundary.actual_timestamp == to_timestamp_ms(
        start + timedelta(minutes=32)
    )
    assert first_segment.end_boundary.snapped_to_active_end is True

    assert second_segment.start_boundary is not None
    assert second_segment.start_boundary.actual_timestamp == to_timestamp_ms(
        start + timedelta(minutes=32)
    )
    assert second_segment.points[0].timestamp == to_timestamp_ms(start + timedelta(minutes=33))


def test_fixed_interval_falls_back_to_ideal_boundary_without_candidate() -> None:
    start = datetime(2026, 4, 17, 12, 0)
    points: list[CurvePoint] = []
    _append_block(points, start=start, offset_minutes=0, length_minutes=21, value=120.0)
    _append_block(points, start=start, offset_minutes=21, length_minutes=19, value=20.0)
    _append_block(points, start=start, offset_minutes=40, length_minutes=20, value=122.0)
    _append_block(points, start=start, offset_minutes=60, length_minutes=5, value=20.0)

    segments = infer_live_heat_segments_with_metadata(
        points,
        context=HeatCuttingContext(expected_duration_minutes=30, anchor_time=start),
        config=_build_cutting_config(),
        activity_threshold=100.0,
    )

    assert len(segments) == 2
    first_segment = segments[0]
    assert first_segment.end_boundary is not None
    assert first_segment.end_boundary.actual_timestamp == to_timestamp_ms(
        start + timedelta(minutes=30)
    )
    assert first_segment.end_boundary.snapped_to_active_end is False


def test_signal_inference_keeps_independent_active_segment_logic() -> None:
    start = datetime(2026, 4, 17, 12, 0)
    points: list[CurvePoint] = []
    _append_block(points, start=start, offset_minutes=0, length_minutes=10, value=25.0)
    _append_block(points, start=start, offset_minutes=10, length_minutes=30, value=120.0)
    _append_block(points, start=start, offset_minutes=40, length_minutes=12, value=20.0)
    _append_block(points, start=start, offset_minutes=52, length_minutes=28, value=123.0)
    _append_block(points, start=start, offset_minutes=80, length_minutes=10, value=18.0)

    segments = infer_live_heat_segments_with_metadata(
        points,
        context=HeatCuttingContext(expected_duration_minutes=30, anchor_time=start),
        config=_build_cutting_config(cutting_mode="signal_inference", fixed_interval_minutes=None),
        activity_threshold=100.0,
    )

    assert len(segments) == 2
    assert segments[0].start_boundary is None
    assert segments[1].start_boundary is None
    assert segments[0].points[0].timestamp == to_timestamp_ms(start + timedelta(minutes=10))
