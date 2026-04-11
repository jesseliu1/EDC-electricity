"""炉次 replay batch 服务。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from ..database import async_session_maker
from ..models import HeatReplayJob
from ..observability import log_event
from ..schemas.common import CurvePoint
from ..services.heat_cutting_service import HeatCuttingConfig
from ..time_utils import utc_now
from .formal_heat_service import MetricCurveLoader, compile_runtime_candidates, replace_heat_range
from .heat_stream_processor import HeatProcessorResult, HeatStreamProcessor

_REPLAY_TASKS: dict[str, asyncio.Task[None]] = {}
_REPLAY_ACTIVE_CHANNELS: set[str] = set()
_REPLAY_JOB_SNAPSHOTS: dict[str, dict[str, Any]] = {}
_REPLAY_CHUNK_HOURS = 6
_SQLITE_LOCK_RETRY_COUNT = 20
_SQLITE_LOCK_RETRY_DELAY_SECONDS = 0.05

LoadPointWindow = Callable[[dict[str, str], datetime, datetime], Awaitable[list[CurvePoint]]]
BuildReplayItems = Callable[[list[list[CurvePoint]]], list[dict[str, Any]]]
ThresholdResolver = Callable[[list[CurvePoint]], float | None]


@dataclass(slots=True)
class ReplayRuntimeSeed:
    previous_segment_points: list[CurvePoint] | None
    active_segment_points: list[CurvePoint] | None
    all_segment_count: int
    history_segment_count: int


AfterReplaceCallback = Callable[[datetime, datetime, str, ReplayRuntimeSeed], Awaitable[None]]


@dataclass(slots=True)
class ReplayContext:
    channel: dict[str, str]
    channel_key: str
    context_hash: str
    cache_key: str
    cutting_config_snapshot: dict[str, Any]
    baseline_id: str | None
    baseline_ids: list[str]
    selected_baselines: list[dict[str, Any]]
    definition_id: str | None
    expected_duration_minutes: int


def _build_replay_runtime_seed(result: HeatProcessorResult) -> ReplayRuntimeSeed:
    all_segments = list(result.all_segments)
    previous_segment_points = (
        list(result.previous_segment.points) if result.previous_segment is not None else None
    )
    active_segment_points = list(result.active_segment.points) if result.active_segment is not None else None
    runtime_seed_count = int(previous_segment_points is not None) + int(active_segment_points is not None)
    return ReplayRuntimeSeed(
        previous_segment_points=previous_segment_points,
        active_segment_points=active_segment_points,
        all_segment_count=len(all_segments),
        history_segment_count=max(len(all_segments) - runtime_seed_count, 0),
    )


def is_replay_active_for_channel(channel_key: str) -> bool:
    return channel_key in _REPLAY_ACTIVE_CHANNELS


def _job_id() -> str:
    return f"heat-replay-{utc_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"


def _cutting_config_snapshot(config: HeatCuttingConfig) -> str:
    return json.dumps(asdict(config), ensure_ascii=False, separators=(",", ":"))


def _is_sqlite_locked_error(exc: OperationalError) -> bool:
    return "database is locked" in str(exc).lower()


def _job_to_snapshot(job: HeatReplayJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_kind": job.job_kind,
        "status": job.status,
        "anchor_time": job.anchor_time,
        "end_time": job.end_time,
        "channel_key": job.channel_key,
        "force_replace": job.force_replace,
        "progress_cursor": job.progress_cursor,
        "processed_chunk_count": job.processed_chunk_count,
        "generated_heat_count": job.generated_heat_count,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "updated_at": job.updated_at,
    }


def _get_job_snapshot(job_id: str) -> dict[str, Any] | None:
    snapshot = _REPLAY_JOB_SNAPSHOTS.get(job_id)
    if snapshot is None:
        return None
    return dict(snapshot)


def _merge_job_snapshot(job_id: str, **fields: Any) -> dict[str, Any] | None:
    snapshot = _REPLAY_JOB_SNAPSHOTS.get(job_id)
    if snapshot is None:
        return None
    merged = dict(snapshot)
    merged.update(fields)
    _REPLAY_JOB_SNAPSHOTS[job_id] = merged
    return dict(merged)


def _job_field(job: HeatReplayJob | dict[str, Any], field_name: str) -> Any:
    if isinstance(job, dict):
        return job.get(field_name)
    return getattr(job, field_name)


async def _update_job(job_id: str, **fields: Any) -> HeatReplayJob | dict[str, Any] | None:
    updated_at = utc_now()
    snapshot = _merge_job_snapshot(job_id, **fields, updated_at=updated_at)
    last_error: OperationalError | None = None
    for attempt in range(_SQLITE_LOCK_RETRY_COUNT):
        try:
            async with async_session_maker() as session:
                job = await session.get(HeatReplayJob, job_id)
                if job is None:
                    return snapshot
                for field_name, value in fields.items():
                    setattr(job, field_name, value)
                job.updated_at = updated_at
                await session.commit()
                await session.refresh(job)
                persisted_snapshot = _job_to_snapshot(job)
                _REPLAY_JOB_SNAPSHOTS[job_id] = persisted_snapshot
                return job
        except OperationalError as exc:
            if not _is_sqlite_locked_error(exc) or attempt == _SQLITE_LOCK_RETRY_COUNT - 1:
                raise
            last_error = exc
            await asyncio.sleep(_SQLITE_LOCK_RETRY_DELAY_SECONDS)
    if last_error is not None:
        raise last_error
    return snapshot


async def list_heat_replay_jobs() -> list[HeatReplayJob | dict[str, Any]]:
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(HeatReplayJob).order_by(HeatReplayJob.created_at.desc())
                )
            ).scalars()
        )
    snapshots = {job_id: dict(snapshot) for job_id, snapshot in _REPLAY_JOB_SNAPSHOTS.items()}
    items: list[HeatReplayJob | dict[str, Any]] = []
    seen_job_ids: set[str] = set()
    for row in rows:
        seen_job_ids.add(row.id)
        items.append(snapshots.get(row.id) or row)
    for job_id, snapshot in snapshots.items():
        if job_id not in seen_job_ids:
            items.append(snapshot)
    return items


async def get_heat_replay_job(job_id: str) -> HeatReplayJob | dict[str, Any] | None:
    snapshot = _get_job_snapshot(job_id)
    if snapshot is not None:
        return snapshot
    async with async_session_maker() as session:
        job = await session.get(HeatReplayJob, job_id)
        if job is None:
            return None
        persisted_snapshot = _job_to_snapshot(job)
        _REPLAY_JOB_SNAPSHOTS[job_id] = persisted_snapshot
        return job


async def mark_interrupted_heat_replay_jobs() -> None:
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(HeatReplayJob).where(HeatReplayJob.status == "running")
                )
            ).scalars()
        )
        if not rows:
            return
        now = utc_now()
        for job in rows:
            job.status = "failed"
            job.error_message = "job_interrupted_by_process_restart"
            job.completed_at = now
            job.updated_at = now
        await session.commit()


async def create_heat_replay_job(
    *,
    job_kind: str,
    anchor_time: datetime,
    end_time: datetime,
    channel_key: str,
    cutting_config: HeatCuttingConfig,
    force_replace: bool,
) -> HeatReplayJob:
    if is_replay_active_for_channel(channel_key):
        raise ValueError("replay_job_already_running")
    now = utc_now()
    job = HeatReplayJob(
        id=_job_id(),
        job_kind=job_kind,
        status="queued",
        anchor_time=anchor_time,
        end_time=end_time,
        channel_key=channel_key,
        force_replace=force_replace,
        cutting_config_snapshot_json=_cutting_config_snapshot(cutting_config),
        progress_cursor=None,
        processed_chunk_count=0,
        generated_heat_count=0,
        error_message=None,
        created_at=now,
        started_at=None,
        completed_at=None,
        updated_at=now,
    )
    async with async_session_maker() as session:
        session.add(job)
        await session.commit()
        await session.refresh(job)
    _REPLAY_JOB_SNAPSHOTS[job.id] = _job_to_snapshot(job)
    return job


async def cancel_heat_replay_job(job_id: str) -> HeatReplayJob | None:
    task = _REPLAY_TASKS.get(job_id)
    if task is not None and not task.done():
        task.cancel()
        return await get_heat_replay_job(job_id)

    job = await get_heat_replay_job(job_id)
    if job is None:
        return None
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    updated = await _update_job(
        job_id,
        status="cancelled",
        completed_at=utc_now(),
        error_message="job_cancelled_by_user",
    )
    return updated


def launch_heat_replay_job(
    *,
    job_id: str,
    replay_context: ReplayContext,
    cutting_config: HeatCuttingConfig,
    point_loader: LoadPointWindow,
    build_items_from_segments: BuildReplayItems,
    metric_curve_loader: MetricCurveLoader | None = None,
    threshold_resolver: ThresholdResolver | None = None,
    after_replace: AfterReplaceCallback | None = None,
) -> asyncio.Task[None]:
    if replay_context.channel_key in _REPLAY_ACTIVE_CHANNELS:
        raise ValueError("replay_job_already_running")
    if job_id in _REPLAY_TASKS and not _REPLAY_TASKS[job_id].done():
        return _REPLAY_TASKS[job_id]

    async def _runner() -> None:
        _REPLAY_ACTIVE_CHANNELS.add(replay_context.channel_key)
        try:
            job = await get_heat_replay_job(job_id)
            if job is None:
                raise ValueError("replay_job_not_found")
            await _update_job(
                job_id,
                status="running",
                started_at=utc_now(),
                error_message=None,
            )
            generated_heat_count = 0
            processed_chunk_count = 0
            chunk_start = _job_field(job, "anchor_time")
            end_time = _job_field(job, "end_time")
            processor = HeatStreamProcessor(
                cache_key=replay_context.cache_key,
                channel_key=replay_context.channel_key,
                context_hash=replay_context.context_hash,
                baseline_id=replay_context.baseline_id,
                expected_duration_minutes=replay_context.expected_duration_minutes,
                cutting_config=cutting_config,
                processing_mode="replay_batch",
                threshold_resolver=threshold_resolver,
            )
            generated_candidate_map: dict[str, dict[str, Any]] = {}

            def _merge_generated_candidates(candidates: list[dict[str, Any]]) -> None:
                nonlocal generated_heat_count

                for candidate in candidates:
                    candidate_id = str(candidate.get("id") or "").strip()
                    if not candidate_id:
                        continue
                    generated_candidate_map[candidate_id] = candidate
                generated_heat_count = len(generated_candidate_map)

            while chunk_start < end_time:
                chunk_end = min(chunk_start + timedelta(hours=_REPLAY_CHUNK_HOURS), end_time)
                try:
                    points = await point_loader(replay_context.channel, chunk_start, chunk_end)
                except TypeError:
                    points = await point_loader(replay_context.channel)
                result = processor.feed_points(
                    points,
                    allow_sealing=True,
                    retain_tail_count=2,
                )
                chunk_candidates = build_items_from_segments(
                    [segment.points for segment in result.sealed_segments]
                )
                _merge_generated_candidates(chunk_candidates)
                processed_chunk_count += 1
                chunk_start = chunk_end
                await _update_job(
                    job_id,
                    progress_cursor=chunk_end,
                    processed_chunk_count=processed_chunk_count,
                    generated_heat_count=generated_heat_count,
                )

            final_result = processor.finalize_until(end_time, retain_tail_count=2)
            final_runtime_seed = _build_replay_runtime_seed(final_result)
            final_history_segment_points = [
                list(segment.points)
                for segment in final_result.all_segments[: final_runtime_seed.history_segment_count]
            ]
            final_candidates = build_items_from_segments(final_history_segment_points)
            _merge_generated_candidates(final_candidates)

            compiled_candidates = await compile_runtime_candidates(
                list(generated_candidate_map.values()),
                processing_mode="replay_batch",
                trigger_source=f"replay_job:{job_id}",
                cutting_config=cutting_config,
                explicit_baselines=replay_context.selected_baselines,
                explicit_primary_baseline_id=replay_context.baseline_id,
                metric_curve_loader=metric_curve_loader,
            )
            await replace_heat_range(
                anchor_time=_job_field(job, "anchor_time"),
                end_time=end_time,
                candidates=compiled_candidates,
            )
            if after_replace is not None:
                try:
                    await after_replace(
                        _job_field(job, "anchor_time"),
                        end_time,
                        replay_context.channel_key,
                        final_runtime_seed,
                    )
                except Exception as exc:  # pragma: no cover - 运维补偿失败不影响正式落库
                    log_event(
                        "heat_replay_after_replace_error",
                        job_id=job_id,
                        channel_key=replay_context.channel_key,
                        error=str(exc),
                    )
            await _update_job(
                job_id,
                status="completed",
                progress_cursor=end_time,
                processed_chunk_count=processed_chunk_count,
                generated_heat_count=generated_heat_count,
                completed_at=utc_now(),
                error_message=None,
            )
        except asyncio.CancelledError:
            await _update_job(
                job_id,
                status="cancelled",
                completed_at=utc_now(),
                error_message="job_cancelled_by_user",
            )
            raise
        except Exception as exc:
            await _update_job(
                job_id,
                status="failed",
                completed_at=utc_now(),
                error_message=str(exc),
            )
            raise
        finally:
            _REPLAY_ACTIVE_CHANNELS.discard(replay_context.channel_key)
            _REPLAY_TASKS.pop(job_id, None)

    task = asyncio.create_task(_runner())
    _REPLAY_TASKS[job_id] = task
    return task
