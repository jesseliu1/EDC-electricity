from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

_LIVE_HANDOFF_STATE = "live"
_REPLAY_ACTIVE_HANDOFF_STATE = "replay_active"
_REPLAY_SEED_APPLYING_HANDOFF_STATE = "replay_seed_applying"
_AWAITING_LIVE_CONTINUATION_HANDOFF_STATE = "awaiting_live_continuation"

_HANDOFF_STATES = {
    _LIVE_HANDOFF_STATE,
    _REPLAY_ACTIVE_HANDOFF_STATE,
    _REPLAY_SEED_APPLYING_HANDOFF_STATE,
    _AWAITING_LIVE_CONTINUATION_HANDOFF_STATE,
}


@dataclass(frozen=True)
class RuntimeAggregateLease:
    observed_generation: int
    observed_handoff_state: str
    observed_channel_key: str | None


@dataclass(frozen=True)
class RuntimeAggregateCommitResult:
    accepted: bool
    current_generation: int
    current_handoff_state: str
    reject_reason: str | None = None
    transitioned_to_live: bool = False


RuntimeCommitCallback = Callable[[], Awaitable[Any]]


def ensure_runtime_handoff_meta(meta: dict[str, Any]) -> dict[str, Any]:
    try:
        generation = max(int(meta.get("runtime_generation") or 0), 0)
    except (TypeError, ValueError):
        generation = 0
    handoff_state = str(meta.get("handoff_state") or _LIVE_HANDOFF_STATE).strip().lower()
    if handoff_state not in _HANDOFF_STATES:
        handoff_state = _LIVE_HANDOFF_STATE
    channel_key = meta.get("handoff_channel_key")
    replay_job_id = meta.get("last_replay_job_id")
    meta.setdefault("runtime_generation", generation)
    meta["runtime_generation"] = generation
    meta.setdefault("handoff_state", handoff_state)
    meta["handoff_state"] = handoff_state
    meta.setdefault("handoff_channel_key", str(channel_key) if channel_key else None)
    meta["handoff_channel_key"] = str(channel_key) if channel_key else None
    meta.setdefault("last_replay_job_id", str(replay_job_id) if replay_job_id else None)
    meta["last_replay_job_id"] = str(replay_job_id) if replay_job_id else None
    meta.setdefault("last_handoff_at", None)
    return meta


class HeatRuntimeAggregateCoordinator:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    def snapshot(self, meta: dict[str, Any]) -> RuntimeAggregateLease:
        normalized = ensure_runtime_handoff_meta(meta)
        return RuntimeAggregateLease(
            observed_generation=int(normalized["runtime_generation"]),
            observed_handoff_state=str(normalized["handoff_state"]),
            observed_channel_key=(
                str(normalized["handoff_channel_key"])
                if normalized.get("handoff_channel_key")
                else None
            ),
        )

    async def enter_replay(
        self,
        meta: dict[str, Any],
        *,
        channel_key: str,
        replay_job_id: str,
        now: datetime,
    ) -> RuntimeAggregateLease:
        async with self._lock:
            normalized = ensure_runtime_handoff_meta(meta)
            normalized["handoff_state"] = _REPLAY_ACTIVE_HANDOFF_STATE
            normalized["handoff_channel_key"] = str(channel_key)
            normalized["last_replay_job_id"] = str(replay_job_id)
            normalized["last_handoff_at"] = now
            return self.snapshot(normalized)

    async def finish_replay(
        self,
        meta: dict[str, Any],
        *,
        channel_key: str,
        replay_job_id: str,
        now: datetime,
    ) -> RuntimeAggregateLease:
        async with self._lock:
            normalized = ensure_runtime_handoff_meta(meta)
            current_job_id = str(normalized.get("last_replay_job_id") or "")
            current_state = str(normalized.get("handoff_state") or _LIVE_HANDOFF_STATE)
            if (
                current_job_id == str(replay_job_id)
                and current_state == _REPLAY_ACTIVE_HANDOFF_STATE
                and str(normalized.get("handoff_channel_key") or "") == str(channel_key)
            ):
                normalized["handoff_state"] = _LIVE_HANDOFF_STATE
                normalized["handoff_channel_key"] = None
                normalized["last_handoff_at"] = now
            return self.snapshot(normalized)

    async def commit_replay_seed(
        self,
        meta: dict[str, Any],
        *,
        channel_key: str,
        replay_job_id: str,
        now: datetime,
        callback: RuntimeCommitCallback,
    ) -> RuntimeAggregateCommitResult:
        async with self._lock:
            normalized = ensure_runtime_handoff_meta(meta)
            normalized["handoff_state"] = _REPLAY_SEED_APPLYING_HANDOFF_STATE
            normalized["handoff_channel_key"] = str(channel_key)
            normalized["last_replay_job_id"] = str(replay_job_id)
            normalized["last_handoff_at"] = now
            await callback()
            normalized["runtime_generation"] = int(normalized["runtime_generation"]) + 1
            normalized["handoff_state"] = _AWAITING_LIVE_CONTINUATION_HANDOFF_STATE
            normalized["handoff_channel_key"] = str(channel_key)
            normalized["last_replay_job_id"] = str(replay_job_id)
            normalized["last_handoff_at"] = now
            return RuntimeAggregateCommitResult(
                accepted=True,
                current_generation=int(normalized["runtime_generation"]),
                current_handoff_state=str(normalized["handoff_state"]),
            )

    async def commit_live_refresh(
        self,
        meta: dict[str, Any],
        *,
        lease: RuntimeAggregateLease,
        channel_key: str,
        now: datetime,
        callback: RuntimeCommitCallback,
    ) -> RuntimeAggregateCommitResult:
        async with self._lock:
            normalized = ensure_runtime_handoff_meta(meta)
            current_generation = int(normalized["runtime_generation"])
            current_state = str(normalized["handoff_state"])
            current_channel = (
                str(normalized["handoff_channel_key"])
                if normalized.get("handoff_channel_key")
                else None
            )
            if lease.observed_generation != current_generation:
                return RuntimeAggregateCommitResult(
                    accepted=False,
                    current_generation=current_generation,
                    current_handoff_state=current_state,
                    reject_reason="runtime_generation_changed",
                )
            if current_state in {
                _REPLAY_ACTIVE_HANDOFF_STATE,
                _REPLAY_SEED_APPLYING_HANDOFF_STATE,
            }:
                return RuntimeAggregateCommitResult(
                    accepted=False,
                    current_generation=current_generation,
                    current_handoff_state=current_state,
                    reject_reason="runtime_handoff_blocked",
                )
            if (
                current_channel
                and current_channel != str(channel_key)
                and current_state != _LIVE_HANDOFF_STATE
            ):
                return RuntimeAggregateCommitResult(
                    accepted=False,
                    current_generation=current_generation,
                    current_handoff_state=current_state,
                    reject_reason="runtime_channel_mismatch",
                )
            await callback()
            normalized["runtime_generation"] = current_generation + 1
            transitioned_to_live = current_state == _AWAITING_LIVE_CONTINUATION_HANDOFF_STATE
            normalized["handoff_state"] = _LIVE_HANDOFF_STATE
            normalized["handoff_channel_key"] = None
            normalized["last_handoff_at"] = now if transitioned_to_live else normalized.get(
                "last_handoff_at"
            )
            return RuntimeAggregateCommitResult(
                accepted=True,
                current_generation=int(normalized["runtime_generation"]),
                current_handoff_state=str(normalized["handoff_state"]),
                transitioned_to_live=transitioned_to_live,
            )
