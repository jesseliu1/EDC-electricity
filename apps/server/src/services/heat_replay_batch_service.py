"""炉次 replay batch 服务。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable
from uuid import uuid4

from sqlalchemy import select

from ..database import async_session_maker
from ..models import HeatReplayJob
from ..schemas.common import CurvePoint
from ..services.heat_cutting_service import HeatCuttingConfig
from ..time_utils import utc_now
from .formal_heat_service import compile_runtime_candidates, replace_heat_range
from .heat_stream_processor import HeatStreamProcessor

_REPLAY_TASKS: dict[str, asyncio.Task[None]] = {}
_REPLAY_ACTIVE_CHANNELS: set[str] = set()
_REPLAY_CHUNK_HOURS = 6

LoadPointWindow = Callable[[dict[str, str], datetime, datetime], Awaitable[list[CurvePoint]]]
BuildReplayItems = Callable[[list[list[CurvePoint]]], list[dict[str, Any]]]
ThresholdResolver = Callable[[list[CurvePoint]], float | None]


@dataclass(slots=True)
class ReplayContext:
    channel: dict[str, str]
    channel_key: str
    context_hash: str
    cache_key: str
    baseline_id: str | None
    expected_duration_minutes: int


def is_replay_active_for_channel(channel_key: str) -> bool:
    return channel_key in _REPLAY_ACTIVE_CHANNELS


def _job_id() -> str:
    return f"heat-replay-{utc_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"


def _cutting_config_snapshot(config: HeatCuttingConfig) -> str:
    return json.dumps(asdict(config), ensure_ascii=False, separators=(",", ":"))


async def _update_job(job_id: str, **fields: Any) -> HeatReplayJob | None:
    async with async_session_maker() as session:
        job = await session.get(HeatReplayJob, job_id)
        if job is None:
            return None
        for field_name, value in fields.items():
            setattr(job, field_name, value)
        job.updated_at = utc_now()
        await session.commit()
        await session.refresh(job)
        return job


async def list_heat_replay_jobs() -> list[HeatReplayJob]:
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(HeatReplayJob).order_by(HeatReplayJob.created_at.desc())
                )
            ).scalars()
        )
    return rows


async def get_heat_replay_job(job_id: str) -> HeatReplayJob | None:
    async with async_session_maker() as session:
        return await session.get(HeatReplayJob, job_id)


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
    threshold_resolver: ThresholdResolver | None = None,
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
            chunk_start = job.anchor_time
            end_time = job.end_time
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
            generated_candidates: list[dict[str, Any]] = []

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
                generated_candidates.extend(chunk_candidates)
                generated_heat_count += len(chunk_candidates)
                processed_chunk_count += 1
                chunk_start = chunk_end
                await _update_job(
                    job_id,
                    progress_cursor=chunk_end,
                    processed_chunk_count=processed_chunk_count,
                    generated_heat_count=generated_heat_count,
                )

            final_result = processor.finalize_until(end_time, retain_tail_count=0)
            final_candidates = build_items_from_segments(
                [segment.points for segment in final_result.sealed_segments]
            )
            generated_candidates.extend(final_candidates)
            generated_heat_count += len(final_candidates)

            compiled_candidates = await compile_runtime_candidates(
                generated_candidates,
                processing_mode="replay_batch",
                trigger_source=f"replay_job:{job_id}",
            )
            await replace_heat_range(
                anchor_time=job.anchor_time,
                end_time=end_time,
                candidates=compiled_candidates,
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
