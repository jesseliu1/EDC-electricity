"""HeatStreamProcessor 单测。"""

from datetime import datetime, timedelta

from src.schemas.common import CurvePoint
from src.services.heat_cutting_service import HeatCuttingConfig
from src.services.heat_stream_processor import HeatStreamProcessor


def _build_cutting_config(*, cutting_mode: str = "signal_inference", fixed_interval: int | None = None):
    return HeatCuttingConfig(
        time_tolerance_percent=10.0,
        major_issue_duration_minutes=8,
        plant_timezone="Asia/Shanghai",
        work_start_time="08:00",
        work_end_time="18:00",
        break_periods=("12:00-13:00",),
        cutting_mode="fixed_interval" if cutting_mode == "fixed_interval" else "signal_inference",
        fixed_interval_minutes=fixed_interval,
    )


def _build_live_power_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = int(
                (start + timedelta(minutes=offset_minutes + index)).timestamp() * 1000
            )
            points.append(CurvePoint(timestamp=timestamp, value=value))

    append_block(0, 10, 42.0)
    append_block(10, 30, 124.0)
    append_block(40, 12, 46.0)
    append_block(52, 28, 129.0)
    append_block(80, 10, 38.0)
    return points


def _build_live_power_points_with_heat_count(start: datetime, heat_count: int) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    cursor = 0
    for _index in range(heat_count):
        for offset in range(8):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=42.0))
        cursor += 8
        for offset in range(28):
            timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
            points.append(CurvePoint(timestamp=timestamp, value=128.0))
        cursor += 28
    for offset in range(8):
        timestamp = int((start + timedelta(minutes=cursor + offset)).timestamp() * 1000)
        points.append(CurvePoint(timestamp=timestamp, value=41.0))
    return points


def _shift_curve_points(points: list[CurvePoint], *, seconds: int) -> list[CurvePoint]:
    delta_ms = seconds * 1000
    return [
        CurvePoint(timestamp=int(point.timestamp) + delta_ms, value=float(point.value))
        for point in points
    ]


def test_processor_bootstrap_keeps_last_two_segments_only() -> None:
    processor = HeatStreamProcessor(
        cache_key="test-cache",
        channel_key="2349:199",
        context_hash="ctx",
        baseline_id="def-001:001",
        expected_duration_minutes=30,
        cutting_config=_build_cutting_config(),
        processing_mode="live_incremental",
        threshold_resolver=lambda _points: 100.0,
    )

    result = processor.feed_points(
        _build_live_power_points(datetime(2026, 3, 19, 8, 0)),
        allow_sealing=False,
        retain_tail_count=2,
    )

    assert result.previous_segment is not None
    assert result.active_segment is not None
    assert result.sealed_segments == []
    assert result.previous_segment.start_time < result.active_segment.start_time
    assert processor.state.bootstrapped is True


def test_processor_incremental_rollover_seals_older_segment() -> None:
    processor = HeatStreamProcessor(
        cache_key="test-cache",
        channel_key="2349:199",
        context_hash="ctx",
        baseline_id="def-001:001",
        expected_duration_minutes=30,
        cutting_config=_build_cutting_config(),
        processing_mode="live_incremental",
        threshold_resolver=lambda _points: 100.0,
    )

    processor.feed_points(
        _build_live_power_points_with_heat_count(datetime(2026, 3, 19, 8, 0), 3),
        allow_sealing=False,
        retain_tail_count=2,
    )
    result = processor.feed_points(
        _shift_curve_points(
            _build_live_power_points_with_heat_count(datetime(2026, 3, 19, 8, 0), 4),
            seconds=240,
        ),
        allow_sealing=True,
        retain_tail_count=2,
    )

    assert len(result.sealed_segments) >= 1
    assert result.previous_segment is not None
    assert result.active_segment is not None
    assert result.sealed_segments[0].start_time < result.previous_segment.start_time


def test_processor_finalize_until_seals_remaining_closed_tail() -> None:
    processor = HeatStreamProcessor(
        cache_key="test-cache",
        channel_key="2349:199",
        context_hash="ctx",
        baseline_id="def-001:001",
        expected_duration_minutes=30,
        cutting_config=_build_cutting_config(),
        processing_mode="replay_batch",
        threshold_resolver=lambda _points: 100.0,
    )

    bootstrap = processor.feed_points(
        _build_live_power_points(datetime(2026, 3, 19, 8, 0)),
        allow_sealing=False,
        retain_tail_count=2,
    )
    assert bootstrap.active_segment is not None

    result = processor.finalize_until(
        bootstrap.active_segment.end_time + timedelta(minutes=10),
        retain_tail_count=0,
    )

    assert result.active_segment is None
    assert result.previous_segment is None
    assert len(result.sealed_segments) == len(result.all_segments)
