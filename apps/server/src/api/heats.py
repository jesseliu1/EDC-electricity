"""炉次 API 路由。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ..channel_roles import (
    format_host_channel_label,
    resolve_channel_role,
)
from ..mock_dataset import ensure_mock_dataset_enabled, is_mock_dataset_enabled
from ..observability import log_event
from ..runtime_state import persist_runtime_state
from ..schemas import (
    BaselineCompareItem,
    CurvePoint,
    CuttingTimelineEvent,
    CuttingTimelineResponse,
    DeviationRange,
    HeatCompareResponse,
    HeatListResponse,
    HeatReplayJobCreateRequest,
    HeatReplayJobListResponse,
    HeatReplayJobResponse,
    HeatResponse,
    HeatResumeCuttingRequest,
    HeatUpdate,
    HeatWithCurve,
    MetricCompareSeries,
    OptionalTimestampMs,
)
from ..schemas.heat import BaselineWithCurveSimple
from ..services import (
    EDCClient,
    EDCClientError,
    append_sealed_heats,
    compile_runtime_candidates,
    encode_baseline_id,
    get_formal_heat_record,
    list_formal_heat_records,
    resume_formal_heat_cutting,
    update_formal_heat_record,
)
from ..services.heat_cutting_service import (
    HeatCuttingConfig,
    HeatCuttingContext,
    build_live_heat_cache_key,
    infer_live_activity_threshold,
    infer_live_heat_segments_with_metadata,
    normalize_cutting_mode,
    resolve_live_cutting_anchor_time,
)
from ..services.heat_list_read_model_service import build_heat_list_items
from ..services.heat_replay_batch_service import (
    ReplayContext,
    ReplayRuntimeSeed,
    is_replay_active_for_channel,
    launch_heat_replay_job,
)
from ..services.heat_replay_batch_service import (
    cancel_heat_replay_job as cancel_heat_replay_job_record,
)
from ..services.heat_replay_batch_service import (
    create_heat_replay_job as create_heat_replay_job_record,
)
from ..services.heat_replay_batch_service import (
    get_heat_replay_job as get_heat_replay_job_record,
)
from ..services.heat_replay_batch_service import (
    list_heat_replay_jobs as list_heat_replay_job_records,
)
from ..services.heat_runtime_curve_merge import actual_context_bounds_from_runtime_series
from ..services.heat_runtime_factory import HeatRuntimeFactory
from ..services.heat_runtime_seal_service import HeatRuntimeSealService
from ..services.heat_runtime_transition_service import HeatRuntimeTransitionService
from ..services.heat_runtime_types import (
    CurrentHeatRuntime,
    HeatBirthContext,
    RuntimeBaselineCurveSnapshot,
    RuntimeBaselineView,
    RuntimeCuttingConfigSnapshot,
    RuntimeDefinitionMetricSnapshot,
    RuntimeHeatBinding,
    RuntimeHeatFacts,
    RuntimeMetricSeries,
    RuntimePresealPayload,
    RuntimeProcessingMeta,
)
from ..services.heat_runtime_updater import HeatRuntimeUpdater
from ..services.heat_stream_processor import HeatSegment
from ..services.live_heat_runtime_service import refresh_live_heat_segments
from ..services.replay_baseline_selection_service import (
    ReplayBaselineSelection,
    ReplayBaselineSelectionService,
)
from ..time_utils import (
    from_timestamp_ms,
    minutes_since_midnight,
    normalize_utc_datetime,
    to_plant_datetime,
    to_timestamp_ms,
    utc_now,
)
from .baseline_definitions import _DEFINITION_STORE, _reload_definition_store
from .baselines import _BASELINE_STORE, _reload_baseline_store, _resolve_active_baseline_item
from .settings import (
    _CHANNEL_ROLE_BINDING_STORE,
    _HOST_CHANNEL_STORE,
    _SETTINGS_STORE,
    get_cutting_config,
    get_edc_connection_config,
    get_plant_timezone,
)

router = APIRouter(prefix="/heats", tags=["Heats"])

_LIVE_HEAT_CACHE_TTL_SECONDS = 30
_LIVE_HEAT_GAP_MINUTES = 3
_LIVE_HEAT_ID_BUCKET_MINUTES = 5
_HEAT_COMPARE_CONTEXT_PADDING_MINUTES = 60
_HEAT_COMPARE_CACHE_TTL_SECONDS = 20
_COMPARE_BASELINE_CACHE_TTL_SECONDS = 20
_COMPARE_CHANNEL_CURVE_CACHE_TTL_SECONDS = 20
_HEAT_RUNTIME_REFRESH_ACTIVE_INTERVAL_SECONDS = 30
_HEAT_RUNTIME_REFRESH_IDLE_INTERVAL_SECONDS = 60
_HEAT_RUNTIME_STALE_THRESHOLD_SECONDS = 180
_HEAT_RUNTIME_ERROR_FAILURE_THRESHOLD = 3
_LIVE_HEAT_CACHE: dict[str, Any] = {
    "contexts": {},
}
_HEAT_COMPARE_CACHE: dict[str, Any] = {
    "entries": {},
}
_COMPARE_BASELINE_CACHE: dict[str, Any] = {
    "entries": {},
}
_COMPARE_CHANNEL_CURVE_CACHE: dict[str, Any] = {
    "entries": {},
}

_LIVE_HEAT_LEGACY_ID_PATTERN = re.compile(r"^live-heat-(\d+)-(\d+)$")
_LIVE_HEAT_CANONICAL_ID_PATTERN = re.compile(r"^live-heat-([0-9a-f]{8})-(\d+)-(\d+)$")


async def _ensure_formal_baseline_mirrors_loaded(
    *,
    definition_id: str | None = None,
    baseline_id: str | None = None,
) -> None:
    """按需把正式表里的基线定义/版本回填到过渡镜像。"""
    if not _DEFINITION_STORE or (definition_id and definition_id not in _DEFINITION_STORE):
        await _reload_definition_store()
    if not _BASELINE_STORE or (baseline_id and baseline_id not in _BASELINE_STORE):
        await _reload_baseline_store()


def _as_cache_token(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _normalize_filter_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return normalize_utc_datetime(value)


def _build_heat_compare_cache_key(item: dict[str, Any], baseline_ids: list[str]) -> str:
    baseline_tokens: list[str] = []
    for baseline_id in baseline_ids:
        baseline_item = _BASELINE_STORE.get(baseline_id) or {}
        baseline_tokens.append(
            ":".join(
                [
                    baseline_id,
                    _as_cache_token(baseline_item.get("definition_id")),
                ]
            )
        )
    binding_tokens: list[str] = []
    baseline_bindings = item.get("baseline_bindings")
    if isinstance(baseline_bindings, list):
        for binding in baseline_bindings:
            if not isinstance(binding, dict):
                continue
            binding_tokens.append(
                ":".join(
                    [
                        _as_cache_token(binding.get("baseline_id")),
                        _as_cache_token(binding.get("analysis_status")),
                        _as_cache_token(binding.get("deviation_score")),
                        _as_cache_token(binding.get("avg_deviation_score")),
                        _as_cache_token(binding.get("analysis_details_json")),
                    ]
                )
            )
        binding_tokens.sort()

    return "|".join(
        [
            _as_cache_token(item.get("id")),
            _as_cache_token(item.get("start_time")),
            _as_cache_token(item.get("end_time")),
            _as_cache_token(item.get("status")),
            _as_cache_token(item.get("cut_status")),
            _as_cache_token(item.get("baseline_id")),
            ",".join(baseline_tokens),
            ",".join(binding_tokens),
        ]
    )


def _get_cached_heat_compare(cache_key: str) -> HeatCompareResponse | None:
    entries = _HEAT_COMPARE_CACHE.get("entries")
    if not isinstance(entries, dict):
        return None

    entry = entries.get(cache_key)
    if not isinstance(entry, dict):
        return None

    expires_at = entry.get("expires_at")
    response = entry.get("response")
    if (
        not isinstance(expires_at, datetime)
        or expires_at <= utc_now()
        or not isinstance(response, HeatCompareResponse)
    ):
        entries.pop(cache_key, None)
        return None

    return deepcopy(response)


def _set_cached_heat_compare(
    *,
    cache_key: str,
    heat_id: str,
    response: HeatCompareResponse,
) -> None:
    entries = _HEAT_COMPARE_CACHE.setdefault("entries", {})
    if not isinstance(entries, dict):
        return

    entries[cache_key] = {
        "heat_id": heat_id,
        "expires_at": utc_now() + timedelta(seconds=_HEAT_COMPARE_CACHE_TTL_SECONDS),
        "response": deepcopy(response),
    }


def _invalidate_heat_compare_cache(*heat_ids: str) -> None:
    entries = _HEAT_COMPARE_CACHE.get("entries")
    if not isinstance(entries, dict):
        return

    if not heat_ids:
        entries.clear()
        return

    invalid_ids = set(heat_ids)
    cache_keys = [
        cache_key
        for cache_key, entry in entries.items()
        if isinstance(entry, dict) and str(entry.get("heat_id") or "") in invalid_ids
    ]
    for cache_key in cache_keys:
        entries.pop(cache_key, None)


def _clear_compare_shared_caches() -> None:
    baseline_entries = _COMPARE_BASELINE_CACHE.get("entries")
    if isinstance(baseline_entries, dict):
        baseline_entries.clear()

    channel_entries = _COMPARE_CHANNEL_CURVE_CACHE.get("entries")
    if isinstance(channel_entries, dict):
        channel_entries.clear()


def invalidate_compare_runtime_caches(*heat_ids: str, include_shared: bool = False) -> None:
    if include_shared:
        _invalidate_heat_compare_cache()
        _clear_compare_shared_caches()
        return

    _invalidate_heat_compare_cache(*heat_ids)


def invalidate_live_heat_runtime_cache() -> None:
    contexts = _LIVE_HEAT_CACHE.get("contexts")
    if isinstance(contexts, dict):
        contexts.clear()
        return
    _LIVE_HEAT_CACHE["contexts"] = {}


def _get_compare_baseline_cache_entry(cache_key: str) -> dict[str, Any]:
    entries = _COMPARE_BASELINE_CACHE.setdefault("entries", {})
    if not isinstance(entries, dict):
        entries = {}
        _COMPARE_BASELINE_CACHE["entries"] = entries

    entry = entries.get(cache_key)
    if not isinstance(entry, dict):
        entry = {"expires_at": None, "payload": None, "inflight": None}
        entries[cache_key] = entry
    return entry


def _get_cached_compare_baseline(cache_key: str) -> dict[str, Any] | None:
    entry = _get_compare_baseline_cache_entry(cache_key)
    expires_at = entry.get("expires_at")
    payload = entry.get("payload")
    if (
        not isinstance(expires_at, datetime)
        or expires_at <= utc_now()
        or not isinstance(payload, dict)
    ):
        entry["payload"] = None
        return None

    return deepcopy(payload)


def _build_compare_baseline_cache_key(item: dict[str, Any]) -> str:
    definition_id = str(item.get("definition_id") or "")
    definition = _DEFINITION_STORE.get(definition_id)
    metrics = list(definition.get("metrics", [])) if definition else []
    metric_tokens: list[str] = []
    for metric in metrics:
        channel = _resolve_metric_channel(metric)
        metric_tokens.append(
            ":".join(
                [
                    _as_cache_token(metric.get("id")),
                    _as_cache_token(metric.get("edc_channel_id")),
                    _as_cache_token(_channel_curve_cache_key(channel)),
                ]
            )
        )

    return "|".join(
        [
            _as_cache_token(item.get("id")),
            definition_id,
            _as_cache_token(item.get("source_heat_id")),
            _as_cache_token(item.get("selected_start_time")),
            _as_cache_token(item.get("selected_end_time")),
            _as_cache_token(item.get("updated_at")),
            str(is_mock_dataset_enabled()).lower(),
            ",".join(metric_tokens),
        ]
    )


def _get_compare_channel_curve_cache_entry(cache_key: str) -> dict[str, Any]:
    entries = _COMPARE_CHANNEL_CURVE_CACHE.setdefault("entries", {})
    if not isinstance(entries, dict):
        entries = {}
        _COMPARE_CHANNEL_CURVE_CACHE["entries"] = entries

    entry = entries.get(cache_key)
    if not isinstance(entry, dict):
        entry = {"expires_at": None, "payload": None, "inflight": None}
        entries[cache_key] = entry
    return entry


def _get_cached_compare_channel_curves(
    cache_key: str,
) -> dict[str, list[CurvePoint]] | None:
    entry = _get_compare_channel_curve_cache_entry(cache_key)
    expires_at = entry.get("expires_at")
    payload = entry.get("payload")
    if (
        not isinstance(expires_at, datetime)
        or expires_at <= utc_now()
        or not isinstance(payload, dict)
    ):
        entry["payload"] = None
        return None

    return deepcopy(payload)


def _build_compare_channel_curve_cache_key(
    channel_keys: list[str],
    *,
    start_time: datetime,
    end_time: datetime,
) -> str:
    ordered_channel_keys = sorted({key for key in channel_keys if key})
    return "|".join(
        [
            _as_cache_token(start_time),
            _as_cache_token(end_time),
            ",".join(ordered_channel_keys),
        ]
    )


def _is_live_heat_inference_enabled() -> bool:
    raw_value = _SETTINGS_STORE.get("live_heat_inference_enabled", {}).get("value")
    if raw_value is None:
        return True
    return str(raw_value).strip().lower() not in {"0", "false", "off", "no"}


def _to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _schedule_tag_of(start_time: datetime, config: Any) -> str:
    """根据时间判断班次标签。"""
    current = minutes_since_midnight(start_time, get_plant_timezone())
    work_start = _to_minutes(config.work_start_time)
    work_end = _to_minutes(config.work_end_time)
    if current < work_start or current > work_end:
        return "off_shift"

    for period in config.break_periods:
        try:
            start_str, end_str = period.split("-", 1)
            if _to_minutes(start_str) <= current <= _to_minutes(end_str):
                return "break"
        except ValueError:
            continue
    return "work"


def _curve_points(
    start: datetime, minutes: int, base: float, amp: float, phase: float
) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    for idx in range(minutes):
        ts = to_timestamp_ms(start + timedelta(minutes=idx))
        value = base + amp * ((idx + int(phase)) % 10) / 10
        points.append(CurvePoint(timestamp=ts, value=round(value, 3)))
    return points


def _coerce_curve_points(
    points: list[CurvePoint] | list[dict[str, Any]] | None,
) -> list[CurvePoint]:
    """将存储结构统一转换为 CurvePoint 列表。"""
    if not points:
        return []

    normalized: list[CurvePoint] = []
    for point in points:
        if isinstance(point, CurvePoint):
            normalized.append(point)
            continue

        if isinstance(point, dict):
            timestamp = point.get("timestamp")
            value = point.get("value")
            if timestamp is None or value is None:
                continue
            normalized.append(CurvePoint(timestamp=int(timestamp), value=float(value)))
    return normalized


def _curve_points_to_pairs(
    points: list[CurvePoint] | list[dict[str, Any]] | None,
) -> list[tuple[float, float]]:
    """将曲线点统一转换为偏差计算所需的二元组结构。"""
    return [(float(point.timestamp), float(point.value)) for point in _coerce_curve_points(points)]


def _curve_window_ms(start_time: datetime, end_time: datetime) -> tuple[int, int]:
    return to_timestamp_ms(start_time), to_timestamp_ms(end_time)


def _resolve_compare_display_window(
    start_time: datetime,
    end_time: datetime,
    *,
    context_start_time: datetime | None = None,
    context_end_time: datetime | None = None,
) -> tuple[datetime, datetime]:
    if (
        context_start_time is not None
        and context_end_time is not None
        and context_start_time <= context_end_time
    ):
        return min(context_start_time, start_time), max(context_end_time, end_time)
    padding = timedelta(minutes=_HEAT_COMPARE_CONTEXT_PADDING_MINUTES)
    return start_time - padding, end_time + padding


def _rebase_curve_points_to_window(
    points: list[CurvePoint] | list[dict[str, Any]] | None,
    *,
    target_start_time: datetime,
    target_end_time: datetime,
) -> list[CurvePoint]:
    normalized = _coerce_curve_points(points)
    if not normalized:
        return []

    target_start_ms, target_end_ms = _curve_window_ms(target_start_time, target_end_time)
    if len(normalized) == 1:
        point = normalized[0]
        midpoint = target_start_ms + max(target_end_ms - target_start_ms, 0) // 2
        return [CurvePoint(timestamp=midpoint, value=float(point.value))]

    source_start_ms = int(normalized[0].timestamp)
    source_end_ms = int(normalized[-1].timestamp)
    if source_end_ms <= source_start_ms or target_end_ms <= target_start_ms:
        return [
            CurvePoint(timestamp=target_start_ms, value=float(point.value)) for point in normalized
        ]

    source_span = source_end_ms - source_start_ms
    target_span = target_end_ms - target_start_ms
    rebased: list[CurvePoint] = []
    for point in normalized:
        ratio = (int(point.timestamp) - source_start_ms) / source_span
        rebased_timestamp = target_start_ms + int(round(target_span * ratio))
        rebased.append(CurvePoint(timestamp=rebased_timestamp, value=float(point.value)))
    return rebased


def _resolve_host_channel(channel_id: str | None) -> dict[str, str] | None:
    if not channel_id:
        return None
    return next((item for item in _HOST_CHANNEL_STORE if item["id"] == channel_id), None)


def _live_heat_bucket_ms() -> int:
    return _LIVE_HEAT_ID_BUCKET_MINUTES * 60_000


def _round_timestamp_to_live_bucket(timestamp: int) -> int:
    bucket_ms = _live_heat_bucket_ms()
    return int(((timestamp + bucket_ms / 2) // bucket_ms) * bucket_ms)


def _round_duration_to_live_bucket_minutes(duration_minutes: float) -> int:
    bucket_minutes = _LIVE_HEAT_ID_BUCKET_MINUTES
    rounded = int(((duration_minutes + bucket_minutes / 2) // bucket_minutes) * bucket_minutes)
    return max(rounded, bucket_minutes)


def _live_heat_channel_key(channel: dict[str, str]) -> str:
    return f"{channel['suid']}:{channel['cuid']}"


def _live_heat_context_hash(channel_key: str) -> str:
    return hashlib.sha1(channel_key.encode("utf-8")).hexdigest()[:8]


def _build_live_heat_context(
    *,
    channel: dict[str, str],
    baseline_id: str | None,
    expected_duration_minutes: int,
    cutting_config: HeatCuttingConfig | None = None,
) -> dict[str, Any]:
    channel_key = _live_heat_channel_key(channel)
    effective_cutting_config = cutting_config or get_cutting_config()
    return {
        "channel": channel,
        "channel_key": channel_key,
        "context_hash": _live_heat_context_hash(channel_key),
        "cache_key": build_live_heat_cache_key(
            channel_key=channel_key,
            expected_duration_minutes=expected_duration_minutes,
            config=effective_cutting_config,
        ),
        "baseline_id": baseline_id,
        "expected_duration_minutes": expected_duration_minutes,
        "cutting_config_snapshot": _HEAT_RUNTIME_FACTORY.serialize_cutting_config(
            effective_cutting_config
        ),
    }


def _parse_live_heat_id(heat_id: str) -> dict[str, Any] | None:
    canonical_match = _LIVE_HEAT_CANONICAL_ID_PATTERN.fullmatch(heat_id)
    if canonical_match:
        context_hash, anchor_ms, duration_bucket = canonical_match.groups()
        return {
            "format": "canonical",
            "context_hash": context_hash,
            "anchor_ms": int(anchor_ms),
            "duration_bucket_minutes": int(duration_bucket),
        }

    legacy_match = _LIVE_HEAT_LEGACY_ID_PATTERN.fullmatch(heat_id)
    if legacy_match:
        start_ts, end_ts = legacy_match.groups()
        start_timestamp = int(start_ts)
        end_timestamp = int(end_ts)
        midpoint = start_timestamp + (end_timestamp - start_timestamp) // 2
        return {
            "format": "legacy",
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "anchor_ms": midpoint,
            "duration_bucket_minutes": _round_duration_to_live_bucket_minutes(
                max((end_timestamp - start_timestamp) / 60000, 1)
            ),
        }

    return None


def _build_live_heat_canonical_id(
    *, context_hash: str, anchor_ms: int, duration_bucket_minutes: int
) -> str:
    return f"live-heat-{context_hash}-{anchor_ms}-{duration_bucket_minutes}"


def _clone_live_heat_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel": dict(context["channel"]),
        "channel_key": str(context["channel_key"]),
        "context_hash": str(context["context_hash"]),
        "cache_key": str(context["cache_key"]),
        "baseline_id": str(context["baseline_id"]) if context.get("baseline_id") else None,
        "expected_duration_minutes": int(context["expected_duration_minutes"]),
        "cutting_config_snapshot": deepcopy(context.get("cutting_config_snapshot") or {}),
    }


def _resolve_live_heat_channel_by_key(channel_key: str | None) -> dict[str, str] | None:
    if not channel_key:
        return None
    suid, sep, cuid = str(channel_key).partition(":")
    if not suid or not cuid or sep != ":":
        return None
    return next(
        (
            item
            for item in _HOST_CHANNEL_STORE
            if str(item.get("suid") or "") == suid and str(item.get("cuid") or "") == cuid
        ),
        None,
    )


def _build_live_refresh_context_from_runtime_item(
    item: dict[str, Any],
) -> dict[str, Any] | None:
    birth_context = item.get("birth_context")
    if not isinstance(birth_context, dict):
        return None

    channel_key = str(
        birth_context.get("channel_key")
        or item.get("_live_context_key")
        or item.get("furnace_id")
        or ""
    ).strip()
    expected_duration_minutes = birth_context.get("expected_duration_minutes")
    if not channel_key or expected_duration_minutes is None:
        return None

    channel = _resolve_live_heat_channel_by_key(channel_key)
    if channel is None:
        return None
    cutting_config = _HEAT_RUNTIME_FACTORY.resolve_frozen_cutting_config(
        item,
        fallback_config=get_cutting_config(),
    )
    if cutting_config is None:
        return None

    return _build_live_heat_context(
        channel=channel,
        baseline_id=(
            str(birth_context.get("primary_baseline_id") or item.get("baseline_id") or "")
            if (
                birth_context.get("primary_baseline_id") is not None
                or item.get("baseline_id") is not None
            )
            else None
        ),
        expected_duration_minutes=int(expected_duration_minutes),
        cutting_config=cutting_config,
    )


def _resolve_live_context_cutting_config(context: dict[str, Any] | None) -> HeatCuttingConfig:
    if not isinstance(context, dict):
        return get_cutting_config()

    raw_snapshot = context.get("cutting_config_snapshot")
    if not isinstance(raw_snapshot, dict):
        return get_cutting_config()

    try:
        fixed_interval_minutes = raw_snapshot.get("fixed_interval_minutes")
        cutting_mode = normalize_cutting_mode(raw_snapshot.get("cutting_mode"))
        return HeatCuttingConfig(
            time_tolerance_percent=float(raw_snapshot.get("time_tolerance_percent") or 0.0),
            major_issue_duration_minutes=int(raw_snapshot.get("major_issue_duration_minutes") or 0),
            plant_timezone=str(raw_snapshot.get("plant_timezone") or ""),
            work_start_time=str(raw_snapshot.get("work_start_time") or ""),
            work_end_time=str(raw_snapshot.get("work_end_time") or ""),
            break_periods=tuple(
                str(period) for period in (raw_snapshot.get("break_periods") or [])
            ),
            cutting_mode=cutting_mode,
            fixed_interval_minutes=(
                int(fixed_interval_minutes)
                if fixed_interval_minutes is not None
                else (30 if cutting_mode == "fixed_interval" else None)
            ),
        )
    except (TypeError, ValueError):
        return get_cutting_config()


def _resolve_live_runtime_refresh_context() -> dict[str, Any] | None:
    existing_active_item = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
    if isinstance(existing_active_item, dict):
        runtime_context = _build_live_refresh_context_from_runtime_item(existing_active_item)
        if runtime_context is not None:
            return runtime_context
    return _resolve_live_heat_inference_context()


def _hydrate_candidate_from_existing_runtime(
    candidate: dict[str, Any] | None,
    *,
    existing_item: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if candidate is None or not isinstance(existing_item, dict):
        return candidate
    candidate_id = str(candidate.get("id") or "").strip()
    existing_id = str(existing_item.get("id") or "").strip()
    if not candidate_id or candidate_id != existing_id:
        return candidate

    hydrated = dict(candidate)
    hydrated["birth_context"] = deepcopy(existing_item.get("birth_context"))
    hydrated["definition_metric_snapshots"] = deepcopy(
        existing_item.get("definition_metric_snapshots") or []
    )
    hydrated["baseline_curve_snapshots"] = deepcopy(
        existing_item.get("baseline_curve_snapshots") or []
    )
    hydrated["baseline_bindings"] = deepcopy(existing_item.get("baseline_bindings") or [])
    hydrated["baseline_id"] = existing_item.get("baseline_id")
    hydrated["baseline_version_id"] = existing_item.get("baseline_version_id")
    hydrated["baseline_ids"] = deepcopy(existing_item.get("baseline_ids") or [])
    hydrated["baseline_effective_from"] = existing_item.get("baseline_effective_from")
    hydrated["runtime_metric_series"] = deepcopy(existing_item.get("runtime_metric_series") or [])
    hydrated["power_curve"] = deepcopy(existing_item.get("power_curve") or [])
    hydrated["voltage_curve"] = deepcopy(existing_item.get("voltage_curve") or [])
    hydrated["actual_context_start_time"] = existing_item.get("actual_context_start_time")
    hydrated["actual_context_end_time"] = existing_item.get("actual_context_end_time")
    return hydrated


def _seed_candidate_context_curves_from_runtime(
    candidate: dict[str, Any] | None,
    *,
    existing_item: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if candidate is None or not isinstance(existing_item, dict):
        return candidate
    runtime_metric_series = existing_item.get("runtime_metric_series")
    if not isinstance(runtime_metric_series, list) or not runtime_metric_series:
        return candidate
    seeded = dict(candidate)
    seeded["runtime_metric_series"] = deepcopy(runtime_metric_series)
    seeded["power_curve"] = deepcopy(existing_item.get("power_curve") or [])
    seeded["voltage_curve"] = deepcopy(existing_item.get("voltage_curve") or [])
    seeded["actual_context_start_time"] = existing_item.get("actual_context_start_time")
    seeded["actual_context_end_time"] = existing_item.get("actual_context_end_time")
    return seeded


def _same_runtime_candidate(
    candidate: dict[str, Any] | None,
    existing_item: dict[str, Any] | None,
) -> bool:
    if candidate is None or not isinstance(existing_item, dict):
        return False
    return str(candidate.get("id") or "").strip() == str(existing_item.get("id") or "").strip()


def _candidate_end_time(item: dict[str, Any] | None) -> datetime | None:
    if not isinstance(item, dict):
        return None
    end_time = item.get("end_time")
    return end_time if isinstance(end_time, datetime) else None


def _infer_metric_key(metric: dict[str, Any], index: int) -> str:
    metric_key = str(metric.get("metric_key") or "").strip().lower()
    if metric_key:
        return metric_key
    raise ValueError(f"definition_metric_key_missing:{index}")


def _resolve_primary_baseline_id(item: dict[str, Any]) -> str | None:
    baseline_bindings = item.get("baseline_bindings")
    if isinstance(baseline_bindings, list):
        primary_binding = next(
            (
                binding
                for binding in baseline_bindings
                if isinstance(binding, dict) and bool(binding.get("is_primary"))
            ),
            None,
        )
        if isinstance(primary_binding, dict):
            binding_baseline_id = primary_binding.get("baseline_id")
            if isinstance(binding_baseline_id, str) and binding_baseline_id:
                return binding_baseline_id

    baseline_version_id = item.get("baseline_version_id")
    if isinstance(baseline_version_id, str) and baseline_version_id:
        return baseline_version_id

    baseline_id = item.get("baseline_id")
    if isinstance(baseline_id, str) and baseline_id:
        return baseline_id

    baseline_ids = item.get("baseline_ids")
    if isinstance(baseline_ids, list) and baseline_ids:
        first = baseline_ids[0]
        if isinstance(first, str) and first:
            return first
    return None


def _slice_curve_points(points: list[CurvePoint], start_ts: int, end_ts: int) -> list[CurvePoint]:
    return [point for point in points if start_ts <= point.timestamp <= end_ts]


def _resolve_actual_context_bounds(item: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    actual_start_time = item.get("actual_context_start_time")
    actual_end_time = item.get("actual_context_end_time")
    if isinstance(actual_start_time, datetime) or isinstance(actual_end_time, datetime):
        return (
            actual_start_time if isinstance(actual_start_time, datetime) else None,
            actual_end_time if isinstance(actual_end_time, datetime) else None,
        )
    runtime_metric_series = item.get("runtime_metric_series")
    if isinstance(runtime_metric_series, list):
        return actual_context_bounds_from_runtime_series(runtime_metric_series)
    return None, None


def _infer_live_activity_threshold(points: list[CurvePoint]) -> float | None:
    """保留本地包装，兼容调试与既有测试入口。"""

    return infer_live_activity_threshold(points)


def _clip_curves_to_time_window(
    curves_by_metric: dict[str, list[CurvePoint]],
    *,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]]:
    start_ts, end_ts = _curve_window_ms(start_time, end_time)
    clipped: dict[str, list[CurvePoint]] = {}
    for metric_key, points in curves_by_metric.items():
        clipped[metric_key] = _slice_curve_points(points, start_ts, end_ts)
    return clipped


def _build_live_heat_item(
    *,
    index: int,
    context: dict[str, Any],
    baseline_id: str | None,
    power_curve: list[CurvePoint],
    expected_duration_minutes: int,
    cutting_config: HeatCuttingConfig,
    segment_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start_time = from_timestamp_ms(power_curve[0].timestamp)
    end_time = from_timestamp_ms(power_curve[-1].timestamp)
    duration_minutes = max((end_time - start_time).total_seconds() / 60, 1)
    schedule_tag = _schedule_tag_of(start_time, cutting_config)
    duration_ratio = duration_minutes / max(expected_duration_minutes, 1)
    status = "abnormal" if duration_ratio < 0.6 or duration_ratio > 1.5 else "normal"
    original_start_ts = int(power_curve[0].timestamp)
    original_end_ts = int(power_curve[-1].timestamp)
    anchor_ms = _round_timestamp_to_live_bucket(
        original_start_ts + (original_end_ts - original_start_ts) // 2
    )
    duration_bucket_minutes = (
        int(cutting_config.fixed_interval_minutes)
        if cutting_config.cutting_mode == "fixed_interval"
        and cutting_config.fixed_interval_minutes is not None
        else _round_duration_to_live_bucket_minutes(duration_minutes)
    )
    heat_id = _build_live_heat_canonical_id(
        context_hash=str(context["context_hash"]),
        anchor_ms=anchor_ms,
        duration_bucket_minutes=duration_bucket_minutes,
    )
    metadata = dict(segment_metadata or {})
    anchor_timestamp_ms = metadata.get("anchor_timestamp_ms")
    request_anchor_time = (
        from_timestamp_ms(int(anchor_timestamp_ms))
        if anchor_timestamp_ms is not None
        else start_time
    )
    processing_meta = {
        "processing_mode": f"{cutting_config.cutting_mode}_cutting",
        "trigger_source": f"{cutting_config.cutting_mode}_cutting",
        "request_anchor_time": request_anchor_time,
        "batch_cursor": None,
        "last_processed_heat_id": heat_id,
    }
    if metadata:
        processing_meta.update(
            {
                "fixed_cutting_anchor_timestamp_ms": anchor_timestamp_ms,
                "fixed_cutting_ideal_start_boundary_ts": metadata.get(
                    "ideal_start_boundary_ts"
                ),
                "fixed_cutting_actual_start_boundary_ts": metadata.get(
                    "actual_start_boundary_ts"
                ),
                "fixed_cutting_ideal_end_boundary_ts": metadata.get(
                    "ideal_end_boundary_ts"
                ),
                "fixed_cutting_actual_end_boundary_ts": metadata.get(
                    "actual_end_boundary_ts"
                ),
                "fixed_cutting_end_boundary_snapped": metadata.get("end_boundary_snapped"),
            }
        )

    plant_start_time = to_plant_datetime(start_time, cutting_config.plant_timezone)
    return {
        "id": heat_id,
        "heat_no": f"H{plant_start_time.strftime('%Y%m%d')}-{plant_start_time.strftime('%H%M')}",
        "description": None,
        "start_time": start_time,
        "end_time": end_time,
        "baseline_id": baseline_id,
        "baseline_version_id": baseline_id,
        "baseline_effective_from": _baseline_effective_from(_BASELINE_STORE.get(baseline_id))
        if baseline_id
        else None,
        "baseline_ids": [baseline_id] if baseline_id else [],
        "completion_status": "completed",
        "last_point_at": end_time,
        "deviation_score": None,
        "avg_deviation_score": None,
        "abnormal_duration_minutes": None,
        "schedule_tag": schedule_tag,
        "cut_reason": "live_inferred",
        "cut_status": "normal",
        "major_issue": False,
        "blocked_by_issue": False,
        "status": status,
        "temperature": None,
        "record_source": "live_inferred",
        "current_curve_source": "live_edc",
        "baseline_curve_source": "none",
        "created_at": start_time,
        "power_curve": power_curve,
        "voltage_curve": [],
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
        "inference_rank": index,
        "processing_meta": processing_meta,
        "_live_context_key": str(context["channel_key"]),
        "_live_context_hash": str(context["context_hash"]),
        "_live_anchor_ms": anchor_ms,
        "_live_duration_bucket_minutes": duration_bucket_minutes,
        "_live_original_start_ts": original_start_ts,
        "_live_original_end_ts": original_end_ts,
        "_live_expected_duration_minutes": int(expected_duration_minutes),
        "_live_cutting_mode": str(cutting_config.cutting_mode),
        "_live_plant_timezone": str(cutting_config.plant_timezone),
        "_live_cutting_anchor_ts": anchor_timestamp_ms,
        "_live_ideal_start_boundary_ts": metadata.get("ideal_start_boundary_ts"),
        "_live_actual_start_boundary_ts": metadata.get("actual_start_boundary_ts"),
        "_live_start_boundary_snapped": metadata.get("start_boundary_snapped"),
        "_live_ideal_end_boundary_ts": metadata.get("ideal_end_boundary_ts"),
        "_live_actual_end_boundary_ts": metadata.get("actual_end_boundary_ts"),
        "_live_end_boundary_snapped": metadata.get("end_boundary_snapped"),
    }


def _infer_live_heat_items(
    *,
    context: dict[str, Any],
    points: list[CurvePoint],
    baseline_id: str | None,
    expected_duration_minutes: int,
    cutting_config: HeatCuttingConfig | None = None,
) -> dict[str, dict[str, Any]]:
    effective_cutting_config = cutting_config or _resolve_live_context_cutting_config(context)
    activity_threshold = _infer_live_activity_threshold(points)
    if activity_threshold is None:
        return {}

    anchor_time = resolve_live_cutting_anchor_time(
        reference_time=from_timestamp_ms(points[-1].timestamp),
        config=effective_cutting_config,
    )
    split_segments = infer_live_heat_segments_with_metadata(
        points,
        context=HeatCuttingContext(
            expected_duration_minutes=expected_duration_minutes,
            anchor_time=anchor_time,
        ),
        config=effective_cutting_config,
        activity_threshold=activity_threshold,
    )

    inferred: list[dict[str, Any]] = []
    for split_segment in split_segments:
        if not split_segment.points:
            continue
        inferred.append(
            _build_live_heat_item(
                index=len(inferred) + 1,
                context=context,
                baseline_id=baseline_id,
                power_curve=split_segment.points,
                expected_duration_minutes=expected_duration_minutes,
                cutting_config=effective_cutting_config,
                segment_metadata=_segment_cutting_metadata(split_segment),
            )
        )

    inferred.sort(key=lambda item: item["start_time"], reverse=True)
    return {str(item["id"]): item for item in inferred}


def _build_live_heat_items_from_segments(
    *,
    context: dict[str, Any],
    segments: list[HeatSegment] | list[list[CurvePoint]],
    baseline_id: str | None,
    expected_duration_minutes: int,
    cutting_config: HeatCuttingConfig | None = None,
) -> list[dict[str, Any]]:
    effective_cutting_config = cutting_config or _resolve_live_context_cutting_config(context)
    built: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        power_curve = _segment_points(segment)
        if not power_curve:
            continue
        built.append(
            _build_live_heat_item(
                index=index,
                context=context,
                baseline_id=baseline_id,
                power_curve=power_curve,
                expected_duration_minutes=expected_duration_minutes,
                cutting_config=effective_cutting_config,
                segment_metadata=_segment_cutting_metadata(segment),
            )
        )
    return built


def _segment_points(segment: HeatSegment | list[CurvePoint]) -> list[CurvePoint]:
    if isinstance(segment, list):
        return segment
    return list(segment.points)


def _segment_cutting_metadata(segment: HeatSegment | list[CurvePoint]) -> dict[str, Any]:
    if isinstance(segment, HeatSegment):
        return dict(segment.metadata)
    return {}


def _resolve_compare_baseline_ids(item: dict[str, Any]) -> list[str]:
    explicit_ids = item.get("baseline_ids")
    if isinstance(explicit_ids, list):
        normalized_ids = [
            baseline_id
            for baseline_id in explicit_ids
            if isinstance(baseline_id, str) and baseline_id
        ]
        if normalized_ids:
            return normalized_ids

    ordered_ids: list[str] = []
    primary_baseline_id = _resolve_primary_baseline_id(item)
    if primary_baseline_id:
        ordered_ids.append(primary_baseline_id)
    return ordered_ids


def _resolve_definition_metrics(item: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    baseline_id = _resolve_primary_baseline_id(item)
    baseline_item = _BASELINE_STORE.get(baseline_id) if baseline_id else None
    definition = (
        _DEFINITION_STORE.get(str(baseline_item.get("definition_id")))
        if baseline_item and baseline_item.get("definition_id")
        else None
    )
    return baseline_id, list(definition.get("metrics", [])) if definition else []


def _iter_live_heat_inference_contexts() -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    seen_cache_keys: set[str] = set()
    candidates: list[tuple[str | None, dict[str, Any]]] = []
    inference_channel = resolve_channel_role(
        "live_heat_inference",
        _CHANNEL_ROLE_BINDING_STORE,
        _HOST_CHANNEL_STORE,
    )
    if not inference_channel:
        return contexts

    active_baseline = _resolve_active_baseline_item()
    if active_baseline:
        candidates.append((str(active_baseline["id"]), active_baseline))

    candidates.extend(
        (str(item["id"]), item)
        for item in _BASELINE_STORE.values()
        if item["status"] == "published" and item is not active_baseline
    )

    for baseline_id, baseline_item in candidates:
        definition = _DEFINITION_STORE.get(str(baseline_item.get("definition_id")))
        if not definition:
            continue
        expected_duration = int(definition.get("expected_duration_minutes") or 45)
        context = _build_live_heat_context(
            channel=inference_channel,
            baseline_id=baseline_id,
            expected_duration_minutes=expected_duration,
        )
        if context["cache_key"] in seen_cache_keys:
            continue
        seen_cache_keys.add(context["cache_key"])
        contexts.append(context)

    return contexts


def _resolve_live_heat_inference_context() -> dict[str, Any] | None:
    contexts = _iter_live_heat_inference_contexts()
    if not contexts:
        return None
    return _clone_live_heat_context(contexts[0])


def _build_replay_context(
    context: dict[str, Any],
    *,
    baseline_ids: list[str] | None = None,
    selected_baselines: list[dict[str, Any]] | None = None,
) -> ReplayContext:
    return ReplayContext(
        channel=dict(context["channel"]),
        channel_key=str(context["channel_key"]),
        context_hash=str(context["context_hash"]),
        cache_key=str(context["cache_key"]),
        cutting_config_snapshot=deepcopy(context.get("cutting_config_snapshot") or {}),
        baseline_id=context.get("baseline_id"),
        baseline_ids=list(
            baseline_ids or ([str(context["baseline_id"])] if context.get("baseline_id") else [])
        ),
        selected_baselines=[dict(item) for item in (selected_baselines or [])],
        expected_duration_minutes=int(context["expected_duration_minutes"]),
    )


def _resolve_replay_inference_channel() -> dict[str, str] | None:
    return resolve_channel_role(
        "live_heat_inference",
        _CHANNEL_ROLE_BINDING_STORE,
        _HOST_CHANNEL_STORE,
    )


def _build_replay_context_from_selection(
    selection: ReplayBaselineSelection,
    *,
    cutting_config: HeatCuttingConfig,
) -> ReplayContext:
    inference_channel = _resolve_replay_inference_channel()
    if inference_channel is None:
        raise ValueError("live_heat_inference_channel_missing")

    live_context = _build_live_heat_context(
        channel=inference_channel,
        baseline_id=str(selection.primary_baseline.get("id") or ""),
        expected_duration_minutes=selection.expected_duration_minutes,
        cutting_config=cutting_config,
    )
    return _build_replay_context(
        live_context,
        baseline_ids=[str(item.get("id") or "") for item in selection.selected_baselines],
        selected_baselines=selection.selected_baselines,
    )


def build_live_heat_lookup_context(
    *,
    definition_id: str | None,
    baseline_id: str | None = None,
) -> dict[str, Any] | None:
    if not definition_id:
        return None

    definition = _DEFINITION_STORE.get(str(definition_id))
    if not definition:
        return None

    inference_channel = resolve_channel_role(
        "live_heat_inference",
        _CHANNEL_ROLE_BINDING_STORE,
        _HOST_CHANNEL_STORE,
    )
    if not inference_channel:
        return None

    return _build_live_heat_context(
        channel=inference_channel,
        baseline_id=baseline_id,
        expected_duration_minutes=int(definition.get("expected_duration_minutes") or 45),
    )


async def _load_live_heat_inference_power_points(
    channel: dict[str, str],
    start_time: datetime,
    end_time: datetime,
) -> list[CurvePoint]:
    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return []

    try:
        async with EDCClient(**config) as client:
            return await client.get_local_datas(
                suid=channel["suid"],
                cuid=channel["cuid"],
                start_time=start_time,
                end_time=end_time,
            )
    except Exception:
        return []


def _get_live_heat_cache_entry(context: dict[str, Any]) -> dict[str, Any]:
    contexts = _LIVE_HEAT_CACHE.setdefault("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
        _LIVE_HEAT_CACHE["contexts"] = contexts
    entry = contexts.get(context["cache_key"])
    if not isinstance(entry, dict):
        entry = {"expires_at": None, "items": {}, "inflight": None}
        contexts[context["cache_key"]] = entry
    return entry


async def _get_live_inferred_heat_store(
    preferred_context: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    if not _is_live_heat_inference_enabled():
        return {}

    context = _clone_live_heat_context(preferred_context) if preferred_context else None
    if context is None:
        context = _resolve_live_heat_inference_context()
    if not context:
        return {}

    cache_entry = _get_live_heat_cache_entry(context)
    expires_at = cache_entry.get("expires_at")
    cached_items = cache_entry.get("items")
    if (
        isinstance(expires_at, datetime)
        and expires_at > utc_now()
        and isinstance(cached_items, dict)
    ):
        return cached_items

    inflight = cache_entry.get("inflight")
    if isinstance(inflight, asyncio.Task):
        return await inflight

    async def _refresh_live_items() -> dict[str, dict[str, Any]]:
        window_end = utc_now()
        window_start = window_end - timedelta(
            minutes=max(int(context["expected_duration_minutes"]) * 4, 180)
        )
        try:
            points = await _load_live_heat_inference_power_points(
                context["channel"],
                window_start,
                window_end,
            )
        except TypeError:
            points = await _load_live_heat_inference_power_points(context["channel"])
        inferred_items = _infer_live_heat_items(
            context=context,
            points=points,
            baseline_id=context["baseline_id"],
            expected_duration_minutes=int(context["expected_duration_minutes"]),
            cutting_config=_resolve_live_context_cutting_config(context),
        )
        cache_entry["items"] = inferred_items
        cache_entry["expires_at"] = utc_now() + timedelta(seconds=_LIVE_HEAT_CACHE_TTL_SECONDS)
        return inferred_items

    inflight_task = asyncio.create_task(_refresh_live_items())
    cache_entry["inflight"] = inflight_task
    try:
        return await inflight_task
    finally:
        if cache_entry.get("inflight") is inflight_task:
            cache_entry["inflight"] = None


def _live_heat_match_sort_key(
    *, candidate: dict[str, Any], target_anchor_ms: int, target_duration_bucket_minutes: int
) -> tuple[int, int, int]:
    start_ts = int(candidate.get("_live_original_start_ts") or 0)
    end_ts = int(candidate.get("_live_original_end_ts") or 0)
    overlap_penalty = 0 if start_ts <= target_anchor_ms <= end_ts else 1
    anchor_delta = abs(int(candidate.get("_live_anchor_ms") or 0) - target_anchor_ms)
    duration_delta = abs(
        int(candidate.get("_live_duration_bucket_minutes") or 0) - target_duration_bucket_minutes
    )
    return overlap_penalty, anchor_delta, duration_delta


def _resolve_live_heat_candidate(
    heat_id: str, live_items: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    if heat_id in live_items:
        return live_items[heat_id]

    parsed = _parse_live_heat_id(heat_id)
    if not parsed:
        return None

    if parsed["format"] == "canonical":
        matching_context_items = [
            item
            for item in live_items.values()
            if str(item.get("_live_context_hash") or "") == parsed["context_hash"]
        ]
        if not matching_context_items:
            return None
        return min(
            matching_context_items,
            key=lambda item: _live_heat_match_sort_key(
                candidate=item,
                target_anchor_ms=int(parsed["anchor_ms"]),
                target_duration_bucket_minutes=int(parsed["duration_bucket_minutes"]),
            ),
        )

    legacy_candidates: list[dict[str, Any]] = []
    for item in live_items.values():
        start_ts = int(item.get("_live_original_start_ts") or 0)
        end_ts = int(item.get("_live_original_end_ts") or 0)
        if start_ts <= int(parsed["end_timestamp"]) and int(parsed["start_timestamp"]) <= end_ts:
            legacy_candidates.append(item)
    if legacy_candidates:
        return min(
            legacy_candidates,
            key=lambda item: _live_heat_match_sort_key(
                candidate=item,
                target_anchor_ms=int(parsed["anchor_ms"]),
                target_duration_bucket_minutes=int(parsed["duration_bucket_minutes"]),
            ),
        )

    if not live_items:
        return None
    return min(
        live_items.values(),
        key=lambda item: _live_heat_match_sort_key(
            candidate=item,
            target_anchor_ms=int(parsed["anchor_ms"]),
            target_duration_bucket_minutes=int(parsed["duration_bucket_minutes"]),
        ),
    )


def _merge_live_heat_with_persisted_state(
    live_item: dict[str, Any], persisted_item: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(live_item)
    merged.update(persisted_item)
    merged["id"] = live_item["id"]
    for key in (
        "_live_context_key",
        "_live_context_hash",
        "_live_anchor_ms",
        "_live_duration_bucket_minutes",
        "_live_original_start_ts",
        "_live_original_end_ts",
    ):
        merged[key] = live_item.get(key)
    return merged


def _resolve_item_time_window_ms(item: dict[str, Any]) -> tuple[int, int] | None:
    start_ts = item.get("_live_original_start_ts")
    end_ts = item.get("_live_original_end_ts")
    if start_ts is not None and end_ts is not None:
        return int(start_ts), int(end_ts)

    start_time = item.get("start_time")
    end_time = item.get("end_time")
    if isinstance(start_time, datetime) and isinstance(end_time, datetime):
        return to_timestamp_ms(start_time), to_timestamp_ms(end_time)
    return None


def _has_overlapping_time_window(left_item: dict[str, Any], right_item: dict[str, Any]) -> bool:
    left_window = _resolve_item_time_window_ms(left_item)
    right_window = _resolve_item_time_window_ms(right_item)
    if not left_window or not right_window:
        return False

    tolerance_ms = _live_heat_bucket_ms()
    left_start, left_end = left_window
    right_start, right_end = right_window
    return left_start <= right_end + tolerance_ms and right_start <= left_end + tolerance_ms


def _find_persisted_live_heat_alias(live_item: dict[str, Any]) -> dict[str, Any] | None:
    canonical_heat_id = str(live_item["id"])
    exact_item = _HEAT_STORE.get(canonical_heat_id)
    if exact_item and _is_real_heat_record(exact_item):
        return exact_item

    candidate_store = {canonical_heat_id: live_item}
    for heat_id, stored_item in _HEAT_STORE.items():
        if not _is_real_heat_record(stored_item):
            continue
        if heat_id == canonical_heat_id:
            return stored_item
        if not _has_overlapping_time_window(live_item, stored_item):
            continue
        if _resolve_live_heat_candidate(heat_id, candidate_store):
            return stored_item
    return None


def _collect_live_heat_lookup_contexts(
    *, heat_id: str, preferred_context: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    ordered_contexts: list[dict[str, Any]] = []
    seen_cache_keys: set[str] = set()
    parsed = _parse_live_heat_id(heat_id)
    target_context_hash = parsed.get("context_hash") if parsed else None

    def push(context: dict[str, Any] | None) -> None:
        if not context:
            return
        cloned = _clone_live_heat_context(context)
        if target_context_hash and cloned["context_hash"] != target_context_hash:
            return
        if cloned["cache_key"] in seen_cache_keys:
            return
        seen_cache_keys.add(cloned["cache_key"])
        ordered_contexts.append(cloned)

    push(preferred_context)
    push(_resolve_live_heat_inference_context())
    if not parsed:
        return ordered_contexts
    for context in _iter_live_heat_inference_contexts():
        push(context)
    return ordered_contexts


async def resolve_heat_record(
    heat_id: str,
    *,
    preferred_live_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    del preferred_live_context
    if is_mock_dataset_enabled():
        return _MOCK_HEAT_STREAM_STORE.get(heat_id)

    resolved_heat_id = _resolve_heat_alias_id(heat_id)

    active_item = _ACTIVE_HEAT_RUNTIME.get(heat_id)
    if active_item and _is_real_heat_record(active_item):
        return active_item
    active_item = _ACTIVE_HEAT_RUNTIME.get(resolved_heat_id)
    if active_item and _is_real_heat_record(active_item):
        return active_item

    previous_item = _PREVIOUS_HEAT_RUNTIME.get(heat_id)
    if previous_item and _is_real_heat_record(previous_item):
        return previous_item
    previous_item = _PREVIOUS_HEAT_RUNTIME.get(resolved_heat_id)
    if previous_item and _is_real_heat_record(previous_item):
        return previous_item

    formal_item = await get_formal_heat_record(heat_id)
    if formal_item and _is_real_heat_record(formal_item):
        return formal_item
    if resolved_heat_id != heat_id:
        formal_item = await get_formal_heat_record(resolved_heat_id)
        if formal_item and _is_real_heat_record(formal_item):
            return formal_item

    stored_item = _HEAT_STORE.get(heat_id)
    if stored_item and _is_real_heat_record(stored_item):
        return stored_item
    stored_item = _HEAT_STORE.get(resolved_heat_id)
    if stored_item and _is_real_heat_record(stored_item):
        return stored_item
    return None


async def resolve_heat_time_window(
    heat_id: str,
    *,
    preferred_live_context: dict[str, Any] | None = None,
) -> tuple[datetime, datetime] | None:
    item = await resolve_heat_record(heat_id, preferred_live_context=preferred_live_context)
    if not item:
        return None
    return item["start_time"], item["end_time"]


def _runtime_window_probe(*, start_time: datetime, end_time: datetime) -> dict[str, Any]:
    return {
        "id": f"window-{to_timestamp_ms(start_time)}-{to_timestamp_ms(end_time)}",
        "start_time": start_time,
        "end_time": end_time,
    }


def _filter_runtime_items_covered_by_formal_history(
    runtime_items: dict[str, dict[str, Any]],
    *,
    formal_items: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    filtered: dict[str, dict[str, Any]] = {}
    for heat_id, item in runtime_items.items():
        covered = _find_overlapping_heat_record(item, formal_items)
        if covered is not None:
            _link_heat_alias(heat_id, str(covered.get("id") or ""))
            continue
        filtered[heat_id] = item
    return filtered


def _is_replay_runtime_debug_enabled() -> bool:
    raw_value = _SETTINGS_STORE.get("replay_runtime_debug_enabled", {}).get("value")
    return str(raw_value or "false").strip().lower() in {"1", "true", "yes", "on"}


def _log_replay_runtime_debug(event: str, **fields: Any) -> None:
    if not _is_replay_runtime_debug_enabled():
        return
    log_event(event, **fields)


def _summarize_replay_seed_segment(
    *,
    prefix: str,
    points: list[CurvePoint] | None,
    plant_timezone: str,
) -> dict[str, Any]:
    if not points:
        return {f"{prefix}_exists": False}

    start_time = from_timestamp_ms(points[0].timestamp)
    end_time = from_timestamp_ms(points[-1].timestamp)
    return {
        f"{prefix}_exists": True,
        f"{prefix}_point_count": len(points),
        f"{prefix}_start_time_utc": start_time,
        f"{prefix}_end_time_utc": end_time,
        f"{prefix}_start_time_plant": to_plant_datetime(start_time, plant_timezone),
        f"{prefix}_end_time_plant": to_plant_datetime(end_time, plant_timezone),
    }


def _clone_replay_processor_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    return deepcopy(snapshot) if isinstance(snapshot, dict) else None


def _build_live_processor_snapshot_from_replay_seed(
    *,
    snapshot: dict[str, Any] | None,
    live_context: dict[str, Any],
    cutting_config: HeatCuttingConfig,
) -> dict[str, Any] | None:
    state = _replay_processor_snapshot_state(snapshot)
    if not isinstance(state, dict):
        return None
    return {
        "config": {
            "cache_key": str(live_context["cache_key"]),
            "channel_key": str(live_context["channel_key"]),
            "context_hash": str(live_context["context_hash"]),
            "expected_duration_minutes": int(live_context["expected_duration_minutes"]),
            "cutting_config_token": cutting_config.cache_token(),
            "processing_mode": "live_incremental",
        },
        "state": deepcopy(state),
    }


def _replay_processor_snapshot_state(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    state = snapshot.get("state")
    if isinstance(state, dict):
        return state
    return snapshot


def _replay_processor_last_point_time(snapshot: dict[str, Any] | None) -> datetime | None:
    state = _replay_processor_snapshot_state(snapshot)
    if not isinstance(state, dict):
        return None
    raw_timestamp = state.get("last_point_timestamp")
    try:
        if raw_timestamp is None:
            return None
        return from_timestamp_ms(int(raw_timestamp))
    except (TypeError, ValueError):
        return None


async def _apply_replay_runtime_seed_with_context(
    *,
    anchor_time: datetime,
    end_time: datetime,
    replay_context: ReplayContext,
    runtime_seed: ReplayRuntimeSeed,
    reason: str = "replay_head_rebuild",
) -> dict[str, Any]:
    started_at = utc_now()
    _HEAT_RUNTIME_REFRESH_META.update(
        {
            "refresh_status": "running",
            "refresh_reason": reason,
            "refresh_error": None,
            "last_refresh_started_at": started_at,
        }
    )
    _sync_heat_runtime_refresh_meta_status(now=started_at)

    cutting_config = _resolve_live_context_cutting_config(
        {"cutting_config_snapshot": replay_context.cutting_config_snapshot}
    )
    plant_timezone = str(cutting_config.plant_timezone)
    previous_points = (
        list(runtime_seed.previous_segment_points)
        if runtime_seed.previous_segment_points is not None
        else None
    )
    active_points = (
        list(runtime_seed.active_segment_points)
        if runtime_seed.active_segment_points is not None
        else None
    )
    raw_processor_snapshot = _clone_replay_processor_snapshot(runtime_seed.processor_snapshot)
    processor_state = _replay_processor_snapshot_state(raw_processor_snapshot)
    _log_replay_runtime_debug(
        "replay_runtime_seed_summary",
        channel_key=replay_context.channel_key,
        anchor_time_utc=anchor_time,
        end_time_utc=end_time,
        anchor_time_plant=to_plant_datetime(anchor_time, plant_timezone),
        end_time_plant=to_plant_datetime(end_time, plant_timezone),
        all_segment_count=runtime_seed.all_segment_count,
        history_segment_count=runtime_seed.history_segment_count,
        **_summarize_replay_seed_segment(
            prefix="previous",
            points=previous_points,
            plant_timezone=plant_timezone,
        ),
        **_summarize_replay_seed_segment(
            prefix="active",
            points=active_points,
            plant_timezone=plant_timezone,
        ),
        processor_bootstrapped=(
            bool(processor_state.get("bootstrapped")) if isinstance(processor_state, dict) else None
        ),
        processor_phase=(
            str(processor_state.get("processor_phase") or "")
            if isinstance(processor_state, dict)
            else None
        ),
        processor_last_point_at=_replay_processor_last_point_time(raw_processor_snapshot),
    )

    if raw_processor_snapshot is None:
        _HEAT_STREAM_PROCESSOR_STATE.clear()
        _mark_heat_runtime_refresh_failure(error="replay_runtime_processor_snapshot_missing")
        await persist_runtime_state(*_runtime_heat_sections())
        _log_replay_runtime_debug(
            "replay_runtime_processor_snapshot_missing",
            channel_key=replay_context.channel_key,
            all_segment_count=runtime_seed.all_segment_count,
            history_segment_count=runtime_seed.history_segment_count,
        )
        return _build_heat_runtime_refresh_meta_snapshot()

    replay_live_context = _build_live_heat_context(
        channel=dict(replay_context.channel),
        baseline_id=replay_context.baseline_id,
        expected_duration_minutes=replay_context.expected_duration_minutes,
        cutting_config=cutting_config,
    )
    processor_snapshot = _build_live_processor_snapshot_from_replay_seed(
        snapshot=raw_processor_snapshot,
        live_context=replay_live_context,
        cutting_config=cutting_config,
    )
    if processor_snapshot is None:
        _HEAT_STREAM_PROCESSOR_STATE.clear()
        _mark_heat_runtime_refresh_failure(error="replay_runtime_processor_snapshot_invalid")
        await persist_runtime_state(*_runtime_heat_sections())
        _log_replay_runtime_debug(
            "replay_runtime_processor_snapshot_invalid",
            channel_key=replay_context.channel_key,
        )
        return _build_heat_runtime_refresh_meta_snapshot()
    runtime_seed_segments: list[list[CurvePoint]] = []
    if previous_points is not None:
        runtime_seed_segments.append(previous_points)
    if active_points is not None:
        runtime_seed_segments.append(active_points)
    runtime_seed_candidates = (
        _build_live_heat_items_from_segments(
            context=replay_live_context,
            segments=runtime_seed_segments,
            baseline_id=replay_context.baseline_id,
            expected_duration_minutes=int(replay_context.expected_duration_minutes),
            cutting_config=cutting_config,
        )
        if runtime_seed_segments
        else []
    )
    prepared_runtime_candidates = (
        await compile_runtime_candidates(
            runtime_seed_candidates,
            processing_mode="live_incremental",
            trigger_source=reason,
            cutting_config=cutting_config,
            metric_curve_loader=_load_runtime_metric_curves,
            explicit_baselines=replay_context.selected_baselines,
            explicit_primary_baseline_id=replay_context.baseline_id,
        )
        if runtime_seed_candidates
        else []
    )
    prepared_runtime_candidate_map = {
        str(candidate["id"]): candidate for candidate in prepared_runtime_candidates
    }

    prepared_previous_candidate: dict[str, Any] | None = None
    prepared_active_candidate: dict[str, Any] | None = None
    if previous_points is not None and runtime_seed_candidates:
        prepared_previous_candidate = prepared_runtime_candidate_map.get(
            str(runtime_seed_candidates[0]["id"])
        )
    if active_points is not None and runtime_seed_candidates:
        prepared_active_candidate = prepared_runtime_candidate_map.get(
            str(runtime_seed_candidates[-1]["id"])
        )

    if (previous_points is not None and prepared_previous_candidate is None) or (
        active_points is not None and prepared_active_candidate is None
    ):
        _HEAT_STREAM_PROCESSOR_STATE.clear()
        _mark_heat_runtime_refresh_failure(error="replay_runtime_seed_compile_failed")
        await persist_runtime_state(*_runtime_heat_sections())
        _log_replay_runtime_debug(
            "replay_runtime_seed_compile_failed",
            channel_key=replay_context.channel_key,
            seed_candidate_ids=[
                str(candidate.get("id") or "") for candidate in runtime_seed_candidates
            ],
            prepared_candidate_ids=list(prepared_runtime_candidate_map.keys()),
        )
        return _build_heat_runtime_refresh_meta_snapshot()

    previous_runtime_items = [
        *list(_ACTIVE_HEAT_RUNTIME.values()),
        *list(_PREVIOUS_HEAT_RUNTIME.values()),
    ]
    next_previous_runtime: dict[str, dict[str, Any]] = {}
    next_active_runtime: dict[str, dict[str, Any]] = {}
    if prepared_previous_candidate is not None:
        previous_runtime = _build_current_heat_runtime(
            prepared_previous_candidate,
            trigger_source=reason,
            processing_mode="live_incremental",
        )
        previous_item = _mark_previous_runtime(previous_runtime.to_runtime_item())
        next_previous_runtime[str(previous_item["id"])] = previous_item
    if prepared_active_candidate is not None:
        active_runtime = _build_current_heat_runtime(
            prepared_active_candidate,
            trigger_source=reason,
            processing_mode="live_incremental",
        )
        active_item = _mark_active_runtime(active_runtime.to_runtime_item())
        next_active_runtime[str(active_item["id"])] = active_item

    formal_items = {str(item["id"]): item for item in await list_formal_heat_records()}
    next_runtime_lookup = dict(formal_items)
    next_runtime_lookup.update(next_previous_runtime)
    next_runtime_lookup.update(next_active_runtime)
    _register_runtime_aliases(previous_runtime_items, next_runtime_lookup)

    _HEAT_STORE.clear()
    _HEAT_STREAM_PROCESSOR_STATE.clear()
    _HEAT_STREAM_PROCESSOR_STATE.update(processor_snapshot)
    _PREVIOUS_HEAT_RUNTIME.clear()
    _PREVIOUS_HEAT_RUNTIME.update(next_previous_runtime)
    _ACTIVE_HEAT_RUNTIME.clear()
    _ACTIVE_HEAT_RUNTIME.update(next_active_runtime)

    watermark_candidates: list[datetime] = [end_time]
    processor_last_point_time = _replay_processor_last_point_time(processor_snapshot)
    if processor_last_point_time is not None:
        watermark_candidates.append(processor_last_point_time)
    for runtime_item in [*next_previous_runtime.values(), *next_active_runtime.values()]:
        watermark = runtime_item.get("last_point_at") or runtime_item.get("end_time")
        if isinstance(watermark, datetime):
            watermark_candidates.append(watermark)

    _mark_heat_runtime_refresh_success(
        reason=reason,
        refresh_outcome="replay_runtime_seed_applied",
        snapshot_watermark=max(watermark_candidates) if watermark_candidates else None,
    )
    await persist_runtime_state(*_runtime_heat_sections())
    _log_replay_runtime_debug(
        "replay_runtime_seed_applied",
        channel_key=replay_context.channel_key,
        replaced_previous=bool(previous_runtime_items),
        next_previous_id=next(iter(next_previous_runtime.keys()), None),
        next_active_id=next(iter(next_active_runtime.keys()), None),
        processor_bootstrapped=(
            bool(processor_state.get("bootstrapped")) if isinstance(processor_state, dict) else None
        ),
        processor_phase=(
            str(processor_state.get("processor_phase") or "")
            if isinstance(processor_state, dict)
            else None
        ),
        snapshot_watermark=max(watermark_candidates) if watermark_candidates else None,
    )
    return _build_heat_runtime_refresh_meta_snapshot()


async def _refresh_heat_runtime_state_from_context(
    *,
    reason: str,
    context: dict[str, Any],
    force_anchor_time: datetime | None = None,
    force_reset_processor: bool = False,
    explicit_baselines: list[dict[str, Any]] | None = None,
    explicit_primary_baseline_id: str | None = None,
) -> dict[str, Any]:
    started_at = utc_now()
    _HEAT_RUNTIME_REFRESH_META.update(
        {
            "refresh_status": "running",
            "refresh_reason": reason,
            "refresh_error": None,
            "last_refresh_started_at": started_at,
        }
    )
    _sync_heat_runtime_refresh_meta_status(now=started_at)

    existing_active_item = next(iter(_ACTIVE_HEAT_RUNTIME.values()), None)
    existing_previous_item = next(iter(_PREVIOUS_HEAT_RUNTIME.values()), None)
    cutting_config = _resolve_live_context_cutting_config(context)

    refresh_result = await refresh_live_heat_segments(
        context=context,
        cutting_config=cutting_config,
        point_loader=_load_live_heat_inference_power_points,
        processor_snapshot=(
            None
            if force_reset_processor
            else (dict(_HEAT_STREAM_PROCESSOR_STATE) if _HEAT_STREAM_PROCESSOR_STATE else None)
        ),
        processing_mode="live_incremental",
        threshold_resolver=_infer_live_activity_threshold,
        force_start_time=force_anchor_time,
    )
    _HEAT_STREAM_PROCESSOR_STATE.clear()
    _HEAT_STREAM_PROCESSOR_STATE.update(refresh_result.processor_state)

    segment_items = _build_live_heat_items_from_segments(
        context=context,
        segments=list(refresh_result.processor_result.all_segments),
        baseline_id=context["baseline_id"],
        expected_duration_minutes=int(context["expected_duration_minutes"]),
        cutting_config=cutting_config,
    )
    segment_item_lookup = {
        (
            int(item.get("_live_original_start_ts") or 0),
            int(item.get("_live_original_end_ts") or 0),
        ): item
        for item in segment_items
    }

    def _segment_item(segment) -> dict[str, Any] | None:
        if segment is None:
            return None
        return segment_item_lookup.get(segment.key())

    active_candidate = _segment_item(refresh_result.processor_result.active_segment)
    previous_candidate = _segment_item(refresh_result.processor_result.previous_segment)
    sealed_candidates = [
        item
        for segment in refresh_result.processor_result.sealed_segments
        if (item := _segment_item(segment)) is not None
    ]
    active_candidate = _hydrate_candidate_from_existing_runtime(
        active_candidate,
        existing_item=existing_active_item if isinstance(existing_active_item, dict) else None,
    )
    previous_candidate = _hydrate_candidate_from_existing_runtime(
        previous_candidate,
        existing_item=existing_previous_item if isinstance(existing_previous_item, dict) else None,
    )
    if (
        previous_candidate is not None
        and isinstance(existing_active_item, dict)
        and str(previous_candidate.get("id") or "") == str(existing_active_item.get("id") or "")
    ):
        previous_candidate = _hydrate_candidate_from_existing_runtime(
            previous_candidate,
            existing_item=existing_active_item,
        )
    previous_candidate = _HEAT_RUNTIME_TRANSITION_SERVICE.prepare_previous_candidate(
        previous_candidate,
        active_candidate=active_candidate,
        existing_previous_item=(
            existing_previous_item if isinstance(existing_previous_item, dict) else None
        ),
        existing_active_item=(
            existing_active_item if isinstance(existing_active_item, dict) else None
        ),
    )
    active_candidate = _HEAT_RUNTIME_TRANSITION_SERVICE.prepare_active_candidate(
        active_candidate,
        previous_candidate=previous_candidate,
        existing_previous_item=(
            existing_previous_item if isinstance(existing_previous_item, dict) else None
        ),
    )
    if active_candidate is not None and not _same_runtime_candidate(
        active_candidate,
        existing_active_item,
    ):
        active_seed_source: dict[str, Any] | None = None
        if (
            isinstance(previous_candidate, dict)
            and str(previous_candidate.get("id") or "").strip()
            != str(active_candidate.get("id") or "").strip()
        ):
            active_seed_source = previous_candidate
        elif isinstance(existing_previous_item, dict):
            active_seed_source = existing_previous_item
        if active_seed_source is not None:
            active_candidate = _seed_candidate_context_curves_from_runtime(
                active_candidate,
                existing_item=active_seed_source,
            )

    if not active_candidate and not previous_candidate and not sealed_candidates:
        _mark_heat_runtime_refresh_failure(error="no_runtime_heats_inferred")
        await persist_runtime_state(*_runtime_heat_sections())
        return _build_heat_runtime_refresh_meta_snapshot()

    active_reuses_existing = _same_runtime_candidate(active_candidate, existing_active_item)
    previous_reuses_existing = _same_runtime_candidate(previous_candidate, existing_previous_item)
    previous_reuses_existing_active = _same_runtime_candidate(
        previous_candidate,
        existing_active_item,
    )
    compile_candidates: list[dict[str, Any]] = []
    if active_candidate is not None and not active_reuses_existing:
        compile_candidates.append(active_candidate)
    if (
        previous_candidate is not None
        and not previous_reuses_existing
        and not previous_reuses_existing_active
    ):
        compile_candidates.append(previous_candidate)

    prepared_runtime_candidates = (
        await compile_runtime_candidates(
            compile_candidates,
            processing_mode="live_incremental",
            trigger_source=reason,
            cutting_config=cutting_config,
            metric_curve_loader=_load_runtime_metric_curves,
            explicit_baselines=explicit_baselines,
            explicit_primary_baseline_id=explicit_primary_baseline_id,
        )
        if compile_candidates
        else []
    )
    prepared_runtime_candidate_map = {
        str(candidate["id"]): candidate for candidate in prepared_runtime_candidates
    }
    prepared_active_candidate: dict[str, Any] | None = None
    if active_candidate is not None:
        if active_reuses_existing and isinstance(existing_active_item, dict):
            prepared_active_candidate = await _HEAT_RUNTIME_UPDATER.update_existing_runtime(
                existing_item=existing_active_item,
                candidate=active_candidate,
                trigger_source=reason,
                processing_mode="live_incremental",
                request_anchor_time=force_anchor_time or active_candidate.get("start_time"),
                metric_curve_loader=_load_runtime_metric_curves,
            )
        else:
            prepared_active_candidate = prepared_runtime_candidate_map.get(
                str(active_candidate["id"])
            )

    prepared_previous_candidate: dict[str, Any] | None = None
    if previous_candidate is not None:
        if previous_reuses_existing_active and isinstance(existing_active_item, dict):
            prepared_previous_candidate = await _HEAT_RUNTIME_UPDATER.update_existing_runtime(
                existing_item=existing_active_item,
                candidate=previous_candidate,
                trigger_source=reason,
                processing_mode="live_incremental",
                request_anchor_time=force_anchor_time or previous_candidate.get("start_time"),
                metric_curve_loader=_load_runtime_metric_curves,
                preserve_binding_analysis=True,
            )
        elif previous_reuses_existing and isinstance(existing_previous_item, dict):
            prepared_previous_candidate = await _HEAT_RUNTIME_UPDATER.update_existing_runtime(
                existing_item=existing_previous_item,
                candidate=previous_candidate,
                trigger_source=reason,
                processing_mode="live_incremental",
                request_anchor_time=force_anchor_time or previous_candidate.get("start_time"),
                metric_curve_loader=_load_runtime_metric_curves,
                preserve_binding_analysis=True,
            )
        else:
            prepared_previous_candidate = prepared_runtime_candidate_map.get(
                str(previous_candidate["id"])
            )

    next_active_runtime: dict[str, dict[str, Any]] = {}
    next_previous_runtime: dict[str, dict[str, Any]] = {}
    if prepared_active_candidate is not None:
        active_runtime = _build_current_heat_runtime(
            prepared_active_candidate,
            trigger_source=reason,
            processing_mode="live_incremental",
        )
        active_item = _mark_active_runtime(active_runtime.to_runtime_item())
        next_active_runtime[str(active_item["id"])] = active_item
    previous_item = _choose_next_previous_runtime(
        existing_active_item=existing_active_item
        if isinstance(existing_active_item, dict)
        else None,
        existing_previous_item=(
            existing_previous_item if isinstance(existing_previous_item, dict) else None
        ),
        next_active_candidate_id=(
            str(prepared_active_candidate["id"]) if prepared_active_candidate is not None else None
        ),
        prepared_previous_candidate=prepared_previous_candidate,
        reason=reason,
    )
    if previous_item is not None:
        next_previous_runtime[str(previous_item["id"])] = previous_item

    next_history_items: dict[str, dict[str, Any]] = {}
    if not is_replay_active_for_channel(str(context["channel_key"])):
        try:
            seal_sources = _HEAT_RUNTIME_SEAL_SERVICE.resolve_seal_sources(
                sealed_candidates=[dict(candidate) for candidate in sealed_candidates],
                existing_previous_item=(
                    existing_previous_item if isinstance(existing_previous_item, dict) else None
                ),
                existing_active_item=(
                    existing_active_item if isinstance(existing_active_item, dict) else None
                ),
                trigger_source=reason,
            )
        except ValueError as exc:
            _mark_heat_runtime_refresh_failure(error=str(exc))
            await persist_runtime_state(*_runtime_heat_sections())
            raise
        next_history_items = await append_sealed_heats(seal_sources)

    previous_runtime_items = [
        *list(_ACTIVE_HEAT_RUNTIME.values()),
        *list(_PREVIOUS_HEAT_RUNTIME.values()),
    ]
    next_runtime_lookup = dict(next_history_items)
    next_runtime_lookup.update(next_previous_runtime)
    next_runtime_lookup.update(next_active_runtime)
    _register_runtime_aliases(previous_runtime_items, next_runtime_lookup)

    _HEAT_STORE.clear()
    _PREVIOUS_HEAT_RUNTIME.clear()
    _PREVIOUS_HEAT_RUNTIME.update(next_previous_runtime)
    _ACTIVE_HEAT_RUNTIME.clear()
    _ACTIVE_HEAT_RUNTIME.update(next_active_runtime)

    watermark_candidates = [
        item.get("last_point_at") or item.get("end_time")
        for item in next_history_items.values()
        if isinstance(item.get("last_point_at") or item.get("end_time"), datetime)
    ]
    for runtime_store in (_PREVIOUS_HEAT_RUNTIME, _ACTIVE_HEAT_RUNTIME):
        runtime_item = next(iter(runtime_store.values()), None)
        if runtime_item and isinstance(runtime_item.get("last_point_at"), datetime):
            watermark_candidates.append(runtime_item["last_point_at"])
    if refresh_result.processor_result.last_point_timestamp is not None:
        watermark_candidates.append(
            from_timestamp_ms(refresh_result.processor_result.last_point_timestamp)
        )

    existing_active_id = (
        str(existing_active_item.get("id") or "") if isinstance(existing_active_item, dict) else ""
    )
    next_active_id = (
        str(prepared_active_candidate.get("id") or "")
        if isinstance(prepared_active_candidate, dict)
        else ""
    )
    existing_active_end = _candidate_end_time(existing_active_item)
    next_active_end = _candidate_end_time(prepared_active_candidate)

    if not prepared_active_candidate:
        refresh_outcome = "no_new_heat_born"
    elif existing_active_id and next_active_id == existing_active_id:
        refresh_outcome = (
            "active_heat_continues"
            if (
                existing_active_end is not None
                and next_active_end is not None
                and next_active_end > existing_active_end
            )
            else "no_new_heat_born"
        )
    else:
        refresh_outcome = "new_heat_born"

    _mark_heat_runtime_refresh_success(
        reason=reason,
        refresh_outcome=refresh_outcome,
        snapshot_watermark=max(watermark_candidates) if watermark_candidates else None,
    )
    await persist_runtime_state(*_runtime_heat_sections())
    return _build_heat_runtime_refresh_meta_snapshot()


async def _rebuild_head_runtime_after_replay_with_context(
    anchor_time: datetime,
    end_time: datetime,
    replay_context: ReplayContext,
    runtime_seed: ReplayRuntimeSeed,
) -> None:
    inflight = _HEAT_RUNTIME_REFRESH_INFLIGHT
    if inflight is not None and not inflight.done():
        try:
            await inflight
        except Exception:
            pass

    invalidate_compare_runtime_caches(include_shared=True)
    invalidate_live_heat_runtime_cache()
    await _apply_replay_runtime_seed_with_context(
        anchor_time=anchor_time,
        end_time=end_time,
        replay_context=replay_context,
        runtime_seed=runtime_seed,
        reason="replay_head_rebuild",
    )


async def _list_heat_store() -> list[dict[str, Any]]:
    if is_mock_dataset_enabled():
        return list(_MOCK_HEAT_STREAM_STORE.values())

    return build_heat_list_items(
        formal_items=await list_formal_heat_records(),
        previous_runtime_items=_PREVIOUS_HEAT_RUNTIME,
        active_runtime_items=_ACTIVE_HEAT_RUNTIME,
    )


async def refresh_heat_runtime_state(
    *,
    reason: str,
    force_anchor_time: datetime | None = None,
    force_reset_processor: bool = False,
) -> dict[str, Any]:
    if is_mock_dataset_enabled():
        _HEAT_RUNTIME_REFRESH_META.update(
            {
                "refresh_status": "idle",
                "refresh_reason": reason,
                "refresh_error": None,
                "refresh_failure_count": 0,
            }
        )
        _sync_heat_runtime_refresh_meta_status()
        return _build_heat_runtime_refresh_meta_snapshot()

    await _ensure_formal_baseline_mirrors_loaded()
    context = _resolve_live_runtime_refresh_context()
    if not _is_live_heat_inference_enabled() or not context:
        _mark_heat_runtime_refresh_failure(error="live_heat_inference_unavailable")
        await persist_runtime_state(*_runtime_heat_sections())
        return _build_heat_runtime_refresh_meta_snapshot()
    return await _refresh_heat_runtime_state_from_context(
        reason=reason,
        context=context,
        force_anchor_time=force_anchor_time,
        force_reset_processor=force_reset_processor,
    )


def schedule_heat_runtime_refresh(*, reason: str) -> asyncio.Task[dict[str, Any]] | None:
    global _HEAT_RUNTIME_REFRESH_INFLIGHT
    if is_mock_dataset_enabled():
        return None
    if _HEAT_RUNTIME_REFRESH_INFLIGHT and not _HEAT_RUNTIME_REFRESH_INFLIGHT.done():
        return _HEAT_RUNTIME_REFRESH_INFLIGHT

    async def _runner() -> dict[str, Any]:
        global _HEAT_RUNTIME_REFRESH_INFLIGHT
        try:
            return await refresh_heat_runtime_state(reason=reason)
        except Exception as exc:
            _mark_heat_runtime_refresh_failure(error=str(exc))
            await persist_runtime_state(*_runtime_heat_sections())
            raise
        finally:
            _HEAT_RUNTIME_REFRESH_INFLIGHT = None

    _HEAT_RUNTIME_REFRESH_INFLIGHT = asyncio.create_task(_runner())
    return _HEAT_RUNTIME_REFRESH_INFLIGHT


def _heat_runtime_refresh_interval_seconds() -> int:
    return (
        _HEAT_RUNTIME_REFRESH_ACTIVE_INTERVAL_SECONDS
        if _ACTIVE_HEAT_RUNTIME
        else _HEAT_RUNTIME_REFRESH_IDLE_INTERVAL_SECONDS
    )


async def _heat_runtime_refresh_loop() -> None:
    while True:
        task = schedule_heat_runtime_refresh(reason="background")
        if task is not None:
            try:
                await task
            except Exception as exc:  # pragma: no cover - 记录并继续后台循环
                log_event("heat_runtime_refresh_loop_error", error=str(exc))
        await asyncio.sleep(_heat_runtime_refresh_interval_seconds())


def start_heat_runtime_refresh_loop() -> asyncio.Task[None] | None:
    global _HEAT_RUNTIME_REFRESH_LOOP_TASK
    if is_mock_dataset_enabled():
        return None
    if _HEAT_RUNTIME_REFRESH_LOOP_TASK and not _HEAT_RUNTIME_REFRESH_LOOP_TASK.done():
        return _HEAT_RUNTIME_REFRESH_LOOP_TASK
    _HEAT_RUNTIME_REFRESH_LOOP_TASK = asyncio.create_task(_heat_runtime_refresh_loop())
    return _HEAT_RUNTIME_REFRESH_LOOP_TASK


async def stop_heat_runtime_refresh_loop() -> None:
    global _HEAT_RUNTIME_REFRESH_LOOP_TASK
    if not _HEAT_RUNTIME_REFRESH_LOOP_TASK:
        return
    _HEAT_RUNTIME_REFRESH_LOOP_TASK.cancel()
    try:
        await _HEAT_RUNTIME_REFRESH_LOOP_TASK
    except asyncio.CancelledError:
        pass
    finally:
        _HEAT_RUNTIME_REFRESH_LOOP_TASK = None


async def _load_heat_curves_from_edc_window(
    item: dict[str, Any],
    *,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]] | None:
    """按指定时间窗读取炉次主基线绑定的真实功率/电压曲线。"""
    _baseline_id, metrics = _resolve_definition_metrics(item)
    if not metrics:
        return None

    power_metric = next(
        (
            metric
            for index, metric in enumerate(metrics)
            if _infer_metric_key(metric, index) == "power"
        ),
        None,
    )
    voltage_metric = next(
        (
            metric
            for index, metric in enumerate(metrics)
            if _infer_metric_key(metric, index) == "voltage"
        ),
        None,
    )
    power_channel = (
        _resolve_host_channel(power_metric.get("edc_channel_id")) if power_metric else None
    )
    voltage_channel = (
        _resolve_host_channel(voltage_metric.get("edc_channel_id")) if voltage_metric else None
    )
    if not power_channel and not voltage_channel:
        return None

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return None

    try:
        async with EDCClient(**config) as client:
            tasks: dict[str, asyncio.Task[list[CurvePoint]]] = {}
            if power_channel:
                tasks["power"] = asyncio.create_task(
                    client.get_local_datas(
                        suid=power_channel["suid"],
                        cuid=power_channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
            if voltage_channel:
                tasks["voltage"] = asyncio.create_task(
                    client.get_local_datas(
                        suid=voltage_channel["suid"],
                        cuid=voltage_channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    except EDCClientError:
        return None

    curves: dict[str, list[CurvePoint]] = {}
    for metric_key, result in zip(tasks.keys(), results, strict=False):
        if isinstance(result, Exception) or not result:
            continue
        curves[metric_key] = result

    return curves or None


async def _load_heat_curves_from_edc(item: dict[str, Any]) -> dict[str, list[CurvePoint]] | None:
    """按炉次主基线绑定读取真实功率/电压曲线。"""
    return await _load_heat_curves_from_edc_window(
        item,
        start_time=item["start_time"],
        end_time=item["end_time"],
    )


async def _hydrate_heat_item(item: dict[str, Any]) -> dict[str, Any]:
    """优先为炉次自身曲线补齐真实 EDC 数据。"""
    live_curves = await _load_heat_curves_from_edc(item)
    if live_curves:
        if live_curves.get("power"):
            item["power_curve"] = live_curves["power"]
        if live_curves.get("voltage"):
            item["voltage_curve"] = live_curves["voltage"]
        item["current_curve_source"] = "live_edc"

    baseline_id = _resolve_primary_baseline_id(item)
    baseline_item = _BASELINE_STORE.get(baseline_id) if baseline_id else None
    if baseline_item:
        from .baselines import _hydrate_baseline_item

        hydrated_baseline = await _hydrate_baseline_item(baseline_item)
        baseline_power_curve = _coerce_curve_points(hydrated_baseline.get("power_curve"))
        baseline_voltage_curve = _coerce_curve_points(hydrated_baseline.get("voltage_curve"))
        if baseline_power_curve:
            item["baseline_power_curve"] = baseline_power_curve
        if baseline_voltage_curve:
            item["baseline_voltage_curve"] = baseline_voltage_curve
        item["baseline_curve_source"] = str(hydrated_baseline.get("curve_source") or "none")

    return item


def _build_heat_list_view(
    item: dict[str, Any],
    *,
    hydrated_baseline_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """轻量视图只透传已存好的业务结果，不再在请求阶段现场补算偏离度。"""
    response_item = dict(item)
    baseline_id = _resolve_primary_baseline_id(item)
    response_item["baseline_id"] = baseline_id

    baseline_item = hydrated_baseline_item or (
        _BASELINE_STORE.get(baseline_id) if baseline_id else None
    )
    if baseline_item:
        response_item["baseline_curve_source"] = str(
            baseline_item.get("curve_source") or item.get("baseline_curve_source") or "none"
        )
    return response_item


async def _build_heat_list_views(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline_ids = sorted(
        {
            baseline_id
            for item in items
            if (baseline_id := _resolve_primary_baseline_id(item)) is not None
        }
    )
    hydrated_baselines = await _hydrate_compare_baselines(baseline_ids)
    return [
        _build_heat_list_view(
            item,
            hydrated_baseline_item=hydrated_baselines.get(_resolve_primary_baseline_id(item) or ""),
        )
        for item in items
    ]


async def _build_heat_response_view(item: dict[str, Any]) -> dict[str, Any]:
    """按默认黄金基线整理炉次响应视图，不在详情请求里重算业务偏离结果。"""
    response_item = dict(item)
    baseline_id = _resolve_primary_baseline_id(item)
    response_item["baseline_id"] = baseline_id
    response_item["baseline_ids"] = _resolve_compare_baseline_ids(item)
    response_item["baseline_curve_source"] = str(item.get("baseline_curve_source") or "none")

    if not baseline_id:
        return response_item

    baseline_item = _BASELINE_STORE.get(baseline_id)
    if not baseline_item:
        return response_item

    from .baselines import _hydrate_baseline_item

    hydrated_baseline = await _hydrate_baseline_item(baseline_item)

    baseline_power_curve = _coerce_curve_points(hydrated_baseline.get("power_curve"))
    baseline_voltage_curve = _coerce_curve_points(hydrated_baseline.get("voltage_curve"))

    if baseline_power_curve:
        response_item["baseline_power_curve"] = baseline_power_curve
    if baseline_voltage_curve:
        response_item["baseline_voltage_curve"] = baseline_voltage_curve
    response_item["baseline_curve_source"] = str(hydrated_baseline.get("curve_source") or "none")
    return response_item


def _build_heat_compare_view(item: dict[str, Any]) -> dict[str, Any]:
    """compare 路径复用已 hydrate 的主基线，不再现场重算偏离结果。"""
    response_item = dict(item)
    baseline_id = _resolve_primary_baseline_id(item)
    response_item["baseline_id"] = baseline_id
    response_item["baseline_ids"] = _resolve_compare_baseline_ids(item)
    response_item["baseline_curve_source"] = str(item.get("baseline_curve_source") or "none")

    if not baseline_id:
        return response_item

    baseline_item = _BASELINE_STORE.get(baseline_id)
    if not baseline_item:
        return response_item

    baseline_power_curve = _coerce_curve_points(
        response_item.get("baseline_power_curve") or baseline_item.get("power_curve")
    )
    baseline_voltage_curve = _coerce_curve_points(
        response_item.get("baseline_voltage_curve") or baseline_item.get("voltage_curve")
    )

    if baseline_power_curve:
        response_item["baseline_power_curve"] = baseline_power_curve
    if baseline_voltage_curve:
        response_item["baseline_voltage_curve"] = baseline_voltage_curve
    response_item["baseline_curve_source"] = str(
        item.get("baseline_curve_source") or baseline_item.get("curve_source") or "none"
    )
    return response_item


def _resolve_baseline_metric_curve(
    baseline_id: str,
    metric_id: str,
    baseline_item: dict[str, Any] | None = None,
) -> list[CurvePoint]:
    resolved_baseline_item = baseline_item or _BASELINE_STORE.get(baseline_id)
    if not resolved_baseline_item:
        return []

    curves_data = resolved_baseline_item.get("curves_data")
    if not isinstance(curves_data, list):
        return []

    matched = next(
        (
            curve
            for curve in curves_data
            if isinstance(curve, dict) and str(curve.get("metric_id") or "") == metric_id
        ),
        None,
    )
    if not matched:
        return []
    return _coerce_curve_points(matched.get("points"))


def _resolve_metric_channel(metric: dict[str, Any]) -> dict[str, str] | None:
    return _resolve_host_channel(metric.get("edc_channel_id"))


def _channel_curve_cache_key(channel: dict[str, str] | None) -> str | None:
    if not channel:
        return None
    suid = str(channel.get("suid") or "")
    cuid = str(channel.get("cuid") or "")
    if not suid or not cuid:
        return None
    return f"{suid}:{cuid}"


async def _load_metric_current_curves_from_edc(
    *,
    metrics: list[dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]]:
    """按指标绑定尝试批量读取真实当前曲线。"""
    bound_metrics: list[tuple[str, dict[str, str]]] = []
    for metric in metrics:
        channel = _resolve_host_channel(metric.get("edc_channel_id"))
        metric_id = str(metric.get("id") or "")
        if channel and metric_id:
            bound_metrics.append((metric_id, channel))

    if not bound_metrics:
        return {}

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return {}

    try:
        async with EDCClient(**config) as client:
            tasks = {
                metric_id: asyncio.create_task(
                    client.get_local_datas(
                        suid=channel["suid"],
                        cuid=channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
                for metric_id, channel in bound_metrics
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    except EDCClientError:
        return {}

    curves: dict[str, list[CurvePoint]] = {}
    for metric_id, result in zip(tasks.keys(), results, strict=False):
        if isinstance(result, Exception) or not result:
            continue
        curves[metric_id] = result
    return curves


async def _load_runtime_metric_curves(
    metrics: list[dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]]:
    """适配 runtime hydrate 所需的位置参数签名。"""

    return await _load_metric_current_curves_from_edc(
        metrics=metrics,
        start_time=start_time,
        end_time=end_time,
    )


async def _load_channel_curves_from_edc(
    *,
    channels: list[dict[str, str]],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]]:
    """按唯一通道批量读取当前曲线，供 compare 路径多个基线共享。"""
    started_at = perf_counter()
    unique_channels: dict[str, dict[str, str]] = {}
    for channel in channels:
        cache_key = _channel_curve_cache_key(channel)
        if cache_key:
            unique_channels[cache_key] = channel

    if not unique_channels:
        log_event(
            "compare_shared_curves",
            unique_channel_count=0,
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            cache_hit=False,
        )
        return {}

    cache_key = _build_compare_channel_curve_cache_key(
        list(unique_channels.keys()),
        start_time=start_time,
        end_time=end_time,
    )
    cached_curves = _get_cached_compare_channel_curves(cache_key)
    if cached_curves is not None:
        log_event(
            "compare_shared_curves",
            unique_channel_count=len(unique_channels),
            curve_group_count=len(cached_curves),
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            cache_hit=True,
        )
        return cached_curves

    cache_entry = _get_compare_channel_curve_cache_entry(cache_key)
    inflight = cache_entry.get("inflight")
    if isinstance(inflight, asyncio.Task):
        curves = deepcopy(await inflight)
        log_event(
            "compare_shared_curves",
            unique_channel_count=len(unique_channels),
            curve_group_count=len(curves),
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            cache_hit=True,
            inflight_reused=True,
        )
        return curves

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        log_event(
            "compare_shared_curves",
            unique_channel_count=len(unique_channels),
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            cache_hit=False,
            edc_available=False,
        )
        return {}

    async def _refresh_shared_curves() -> dict[str, list[CurvePoint]]:
        try:
            async with EDCClient(**config) as client:
                tasks = {
                    channel_key: asyncio.create_task(
                        client.get_local_datas(
                            suid=channel["suid"],
                            cuid=channel["cuid"],
                            start_time=start_time,
                            end_time=end_time,
                        )
                    )
                    for channel_key, channel in unique_channels.items()
                }
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        except EDCClientError:
            return {}

        curves: dict[str, list[CurvePoint]] = {}
        for channel_key, result in zip(tasks.keys(), results, strict=False):
            if isinstance(result, Exception) or not result:
                continue
            curves[channel_key] = result

        cache_entry["payload"] = deepcopy(curves)
        cache_entry["expires_at"] = utc_now() + timedelta(
            seconds=_COMPARE_CHANNEL_CURVE_CACHE_TTL_SECONDS
        )
        return curves

    inflight_task = asyncio.create_task(_refresh_shared_curves())
    cache_entry["inflight"] = inflight_task
    try:
        curves = deepcopy(await inflight_task)
        log_event(
            "compare_shared_curves",
            unique_channel_count=len(unique_channels),
            curve_group_count=len(curves),
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            cache_hit=False,
        )
        return curves
    finally:
        if cache_entry.get("inflight") is inflight_task:
            cache_entry["inflight"] = None


def _resolve_heat_curves_from_shared_channels(
    item: dict[str, Any],
    current_curves_by_channel: dict[str, list[CurvePoint]],
) -> dict[str, list[CurvePoint]]:
    """优先从 compare 已批量读取的通道曲线中回填功率/电压主曲线。"""
    _baseline_id, metrics = _resolve_definition_metrics(item)
    if not metrics:
        return {}

    resolved: dict[str, list[CurvePoint]] = {}
    for index, metric in enumerate(metrics):
        metric_key = _infer_metric_key(metric, index)
        if metric_key not in {"power", "voltage"}:
            continue
        channel = _resolve_metric_channel(metric)
        cache_key = _channel_curve_cache_key(channel)
        if not cache_key:
            continue
        points = current_curves_by_channel.get(cache_key)
        if points:
            resolved[metric_key] = points
    return resolved


def _is_runtime_compare_source(item: dict[str, Any]) -> bool:
    if str(item.get("record_source") or "") not in {"active_runtime", "previous_runtime"}:
        return False
    return (
        bool(_runtime_metric_series_entries(item))
        and bool(
            _runtime_baseline_view_entries(item) or _build_runtime_definition_metric_snapshots(item)
        )
        and bool(_build_runtime_baseline_curve_snapshots(item))
    )


def _runtime_metric_series_entries(item: dict[str, Any]) -> list[dict[str, Any]]:
    raw_series = item.get("runtime_metric_series")
    if not isinstance(raw_series, list):
        return []
    return [series for series in raw_series if isinstance(series, dict)]


def _runtime_series_payload(series: dict[str, Any]) -> dict[str, Any]:
    raw_payload = series.get("series_json")
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str):
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _resolve_runtime_current_curves(
    item: dict[str, Any],
) -> dict[str, list[CurvePoint]]:
    curves: dict[str, list[CurvePoint]] = {}
    for series in _runtime_metric_series_entries(item):
        metric_key = str(series.get("metric_key") or "").strip()
        if not metric_key:
            continue
        points = _coerce_curve_points(_runtime_series_payload(series).get("points"))
        if points:
            curves[metric_key] = points
    return {metric_key: points for metric_key, points in curves.items() if points}


def _metric_series_compare_keys(
    *,
    metric_key: str,
    source_channel_id: str | None,
) -> list[str]:
    keys: list[str] = []
    normalized_metric_key = str(metric_key or "").strip()
    if normalized_metric_key:
        keys.append(normalized_metric_key)
    normalized_channel_id = str(source_channel_id or "").strip()
    if normalized_channel_id and "-" in normalized_channel_id:
        suid, cuid = normalized_channel_id.split("-", 1)
        if suid and cuid:
            keys.append(f"{suid}:{cuid}")
    return keys


def _resolve_formal_current_curves(
    item: dict[str, Any],
) -> dict[str, list[CurvePoint]]:
    curves: dict[str, list[CurvePoint]] = {}
    raw_metric_series = item.get("runtime_metric_series")
    if not isinstance(raw_metric_series, list):
        raw_metric_series = item.get("metric_series")
    if not isinstance(raw_metric_series, list):
        return curves
    for series in raw_metric_series:
        if not isinstance(series, dict):
            continue
        metric_key = str(series.get("metric_key") or "").strip()
        points = _coerce_curve_points(_runtime_series_payload(series).get("points"))
        if not metric_key or not points:
            continue
        for cache_key in _metric_series_compare_keys(
            metric_key=metric_key,
            source_channel_id=(
                str(series.get("source_channel_id"))
                if series.get("source_channel_id") is not None
                else None
            ),
        ):
            curves[cache_key] = points
    return curves


def _resolve_runtime_baseline_curve_snapshots(
    item: dict[str, Any],
) -> dict[tuple[str, str], RuntimeBaselineCurveSnapshot]:
    return {
        (snapshot.baseline_id, snapshot.metric_key): snapshot
        for snapshot in _build_runtime_baseline_curve_snapshots(item)
    }


def _resolve_runtime_definition_metric_snapshots(
    item: dict[str, Any],
) -> list[RuntimeDefinitionMetricSnapshot]:
    return _build_runtime_definition_metric_snapshots(item)


def _runtime_baseline_view_entries(item: dict[str, Any]) -> list[dict[str, Any]]:
    raw_views = item.get("baseline_views")
    if not isinstance(raw_views, list):
        return []
    return [view for view in raw_views if isinstance(view, dict)]


def _resolve_runtime_baseline_view(
    item: dict[str, Any],
    baseline_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            view
            for view in _runtime_baseline_view_entries(item)
            if str(view.get("baseline_id") or "").strip() == baseline_id
        ),
        None,
    )


def _resolve_runtime_baseline_view_current_curves(
    baseline_view: dict[str, Any],
) -> dict[str, list[CurvePoint]]:
    curves: dict[str, list[CurvePoint]] = {}
    raw_series = baseline_view.get("current_metric_series")
    if not isinstance(raw_series, list):
        return curves
    for entry in raw_series:
        if not isinstance(entry, dict):
            continue
        metric_key = str(entry.get("metric_key") or "").strip()
        if not metric_key:
            continue
        points = _coerce_curve_points(_runtime_series_payload(entry).get("points"))
        if points:
            curves[metric_key] = points
    return curves


def _build_runtime_metric_curve_series(
    *,
    item: dict[str, Any],
    baseline_id: str,
) -> list[MetricCompareSeries]:
    baseline_view = _resolve_runtime_baseline_view(item, baseline_id)
    if baseline_view is not None:
        current_curves = _resolve_runtime_baseline_view_current_curves(baseline_view)
        baseline_snapshots = _resolve_runtime_baseline_curve_snapshots(item)
        raw_series = baseline_view.get("current_metric_series")
        if not isinstance(raw_series, list) or not raw_series:
            raise ValueError("runtime_baseline_view_current_metric_series_missing")

        series: list[MetricCompareSeries] = []
        for entry in sorted(
            (series for series in raw_series if isinstance(series, dict)),
            key=lambda value: (int(value.get("sort_order") or 0), str(value.get("item") or "")),
        ):
            metric_key = str(entry.get("metric_key") or "").strip()
            metric_name = str(entry.get("metric_name") or "").strip()
            color = str(entry.get("color") or "").strip()
            if not metric_key or not metric_name or not color:
                continue
            current_curve = current_curves.get(metric_key)
            if not current_curve:
                raise ValueError(f"runtime_current_metric_curve_missing:{metric_key}")
            baseline_snapshot = baseline_snapshots.get((baseline_id, metric_key))
            if baseline_snapshot is None or not baseline_snapshot.points:
                raise ValueError(f"runtime_baseline_metric_curve_missing:{metric_key}")
            baseline_curve = _rebase_curve_points_to_window(
                baseline_snapshot.points,
                target_start_time=item["start_time"],
                target_end_time=item["end_time"],
            )
            series.append(
                MetricCompareSeries(
                    metric_key=metric_key,
                    metric_name=metric_name,
                    unit=str(entry.get("unit") or "--"),
                    color=color,
                    edc_channel_id=(
                        str(entry.get("source_channel_id"))
                        if entry.get("source_channel_id") is not None
                        else None
                    ),
                    source_channel_name=(
                        str(entry.get("source_channel_name"))
                        if entry.get("source_channel_name") is not None
                        else None
                    ),
                    source_channel_label=(
                        str(entry.get("source_channel_label"))
                        if entry.get("source_channel_label") is not None
                        else None
                    ),
                    baseline_curve=baseline_curve,
                    current_curve=current_curve,
                )
            )
        return series

    metric_snapshots = _resolve_runtime_definition_metric_snapshots(item)
    if not metric_snapshots:
        raise ValueError("runtime_definition_metric_snapshots_missing")
    current_curves = _resolve_runtime_current_curves(item)
    baseline_snapshots = _resolve_runtime_baseline_curve_snapshots(item)

    series: list[MetricCompareSeries] = []
    for snapshot in metric_snapshots:
        current_curve = current_curves.get(snapshot.metric_key)
        if not current_curve:
            raise ValueError(f"runtime_current_metric_curve_missing:{snapshot.metric_key}")
        baseline_snapshot = baseline_snapshots.get((baseline_id, snapshot.metric_key))
        if baseline_snapshot is None or not baseline_snapshot.points:
            raise ValueError(f"runtime_baseline_metric_curve_missing:{snapshot.metric_key}")
        baseline_curve = _rebase_curve_points_to_window(
            baseline_snapshot.points,
            target_start_time=item["start_time"],
            target_end_time=item["end_time"],
        )
        series.append(
            MetricCompareSeries(
                metric_key=snapshot.metric_key,
                metric_name=snapshot.metric_name,
                unit=snapshot.unit or "--",
                color=snapshot.color,
                edc_channel_id=snapshot.edc_channel_id,
                source_channel_name=snapshot.source_channel_name,
                source_channel_label=snapshot.source_channel_label,
                baseline_curve=baseline_curve,
                current_curve=current_curve,
            )
        )

    return series


async def _build_metric_curve_series(
    *,
    start_time: datetime,
    end_time: datetime,
    minutes: int,
    baseline_id: str,
    power_curve: list[CurvePoint],
    voltage_curve: list[CurvePoint],
    current_curves_by_channel: dict[str, list[CurvePoint]] | None = None,
    hydrated_baseline_item: dict[str, Any] | None = None,
    hydrate_baseline: bool = True,
) -> list[MetricCompareSeries]:
    """按基线定义动态构造炉次详情多指标对比曲线。"""
    baseline_item = hydrated_baseline_item or _BASELINE_STORE.get(baseline_id)
    if not baseline_item:
        raise ValueError("compare_baseline_not_found")
    definition = _DEFINITION_STORE.get(str(baseline_item.get("definition_id")))
    if not definition:
        raise ValueError("compare_definition_not_found")
    metrics = list(definition.get("metrics", []))
    if not metrics:
        raise ValueError("compare_definition_metrics_missing")

    real_current_curves = (
        {}
        if current_curves_by_channel is not None
        else await _load_metric_current_curves_from_edc(
            metrics=metrics,
            start_time=start_time,
            end_time=end_time,
        )
    )
    if baseline_item and hydrate_baseline:
        from .baselines import _hydrate_baseline_item

        baseline_item = await _hydrate_baseline_item(baseline_item)

    series: list[MetricCompareSeries] = []
    for index, metric in enumerate(metrics):
        metric_key = _infer_metric_key(metric, index)
        host_channel = _resolve_metric_channel(metric)
        metric_id = str(metric.get("id") or "")
        if not metric_id:
            raise ValueError(f"compare_metric_id_missing:{metric_key}")
        baseline_curve = _resolve_baseline_metric_curve(
            baseline_id,
            metric_id,
            baseline_item=baseline_item,
        )
        if not baseline_curve:
            raise ValueError(f"compare_baseline_metric_curve_missing:{metric_key}")
        baseline_curve = _rebase_curve_points_to_window(
            baseline_curve,
            target_start_time=start_time,
            target_end_time=end_time,
        )
        current_metric_curve = (
            (
                current_curves_by_channel.get(_channel_curve_cache_key(host_channel) or "", [])
                or current_curves_by_channel.get(metric_key, [])
            )
            if current_curves_by_channel is not None
            else real_current_curves.get(metric_id)
        )
        if not current_metric_curve:
            raise ValueError(f"compare_current_metric_curve_missing:{metric_key}")
        series.append(
            MetricCompareSeries(
                metric_key=metric_key,
                metric_name=str(metric.get("name") or f"指标{index + 1}"),
                unit=str(metric.get("unit") or "--"),
                color=str(metric.get("color") or "#94a3b8"),
                edc_channel_id=metric.get("edc_channel_id"),
                source_channel_name=host_channel["channel_name"] if host_channel else None,
                source_channel_label=format_host_channel_label(host_channel),
                baseline_curve=baseline_curve,
                current_curve=current_metric_curve,
            )
        )

    return series


def _collect_compare_metric_channels(baseline_ids: list[str]) -> list[dict[str, str]]:
    channels: list[dict[str, str]] = []
    for baseline_id in baseline_ids:
        baseline_item = _BASELINE_STORE.get(baseline_id)
        definition = (
            _DEFINITION_STORE.get(str(baseline_item.get("definition_id")))
            if baseline_item
            else None
        )
        metrics = list(definition.get("metrics", [])) if definition else []
        for metric in metrics:
            channel = _resolve_metric_channel(metric)
            if channel:
                channels.append(channel)
    return channels


async def _hydrate_compare_baselines(
    baseline_ids: list[str],
) -> dict[str, dict[str, Any]]:
    from .baselines import _hydrate_baseline_item

    started_at = perf_counter()

    async def _hydrate_with_shared_cache(baseline_item: dict[str, Any]) -> dict[str, Any]:
        cache_key = _build_compare_baseline_cache_key(baseline_item)
        cached_payload = _get_cached_compare_baseline(cache_key)
        if cached_payload is not None:
            return cached_payload

        cache_entry = _get_compare_baseline_cache_entry(cache_key)
        inflight = cache_entry.get("inflight")
        if isinstance(inflight, asyncio.Task):
            return deepcopy(await inflight)

        async def _refresh_baseline() -> dict[str, Any]:
            hydrated = await _hydrate_baseline_item(dict(baseline_item))
            cache_entry["payload"] = deepcopy(hydrated)
            cache_entry["expires_at"] = utc_now() + timedelta(
                seconds=_COMPARE_BASELINE_CACHE_TTL_SECONDS
            )
            return hydrated

        inflight_task = asyncio.create_task(_refresh_baseline())
        cache_entry["inflight"] = inflight_task
        try:
            return deepcopy(await inflight_task)
        finally:
            if cache_entry.get("inflight") is inflight_task:
                cache_entry["inflight"] = None

    tasks = {
        baseline_id: _hydrate_with_shared_cache(baseline_item)
        for baseline_id in baseline_ids
        if (baseline_item := _BASELINE_STORE.get(baseline_id)) is not None
    }
    if not tasks:
        log_event(
            "compare_hydrate_baselines",
            baseline_count=0,
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
        )
        return {}

    results = await asyncio.gather(*tasks.values())
    hydrated = dict(zip(tasks.keys(), results, strict=False))
    log_event(
        "compare_hydrate_baselines",
        baseline_count=len(tasks),
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
    )
    return hydrated


def _binding_by_baseline_id(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bindings = item.get("baseline_bindings")
    if not isinstance(bindings, list):
        return {}
    return {
        str(binding["baseline_id"]): binding
        for binding in bindings
        if isinstance(binding, dict) and isinstance(binding.get("baseline_id"), str)
    }


def _binding_deviation_ranges(binding: dict[str, Any]) -> list[DeviationRange]:
    raw_payload = binding.get("analysis_details_json")
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        return []
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return []
    ranges = payload.get("abnormal_ranges")
    if not isinstance(ranges, list):
        return []
    normalized: list[DeviationRange] = []
    for item in ranges:
        if not isinstance(item, dict):
            continue
        start = item.get("start")
        end = item.get("end")
        score = item.get("score")
        if start is None or end is None or score is None:
            continue
        normalized.append(
            DeviationRange(
                start=int(start),
                end=int(end),
                score=float(score),
            )
        )
    return normalized


def _select_metric_curve(
    metric_curves: list[MetricCompareSeries], metric_key: str
) -> list[CurvePoint]:
    matched = next((item for item in metric_curves if item.metric_key == metric_key), None)
    return matched.baseline_curve if matched else []


def _seed_heats() -> dict[str, dict[str, Any]]:
    now = utc_now().replace(second=0, microsecond=0)
    config = get_cutting_config()
    seeded: dict[str, dict[str, Any]] = {}
    major_issue_triggered = False
    for idx in range(60):
        start_time = now - timedelta(hours=idx + 1)
        end_time = start_time + timedelta(minutes=45)
        status: str = "normal"

        # Demo 两组数据:
        # 组1(前30条): 时间偏移都在容忍值内，但部分数值偏差异常
        # 组2(后30条): 连续不一致超过阈值触发重大事故，后续阻断
        group = 1 if idx < 30 else 2

        schedule_tag = _schedule_tag_of(start_time, config)
        mismatch_minutes = 3 + (idx % 6)
        time_window_offset_percent = round((idx % 7) * 1.6, 2)
        cut_reason: str | None = None
        cut_status = "normal"
        major_issue = False
        blocked_by_issue = False

        if group == 1:
            status = "abnormal" if idx % 6 == 0 else "normal"
            mismatch_minutes = 4 + (idx % 4)
            time_window_offset_percent = round((idx % 5) * 1.4, 2)
        else:
            mismatch_minutes = 6 + (idx % 7)
            if idx == 34:
                mismatch_minutes = max(config.major_issue_duration_minutes + 2, mismatch_minutes)

        if schedule_tag in {"break", "off_shift"}:
            cut_status = "blocked"
            blocked_by_issue = True
            status = "pending"
            cut_reason = "schedule_window"
            time_window_offset_percent = None
        elif major_issue_triggered:
            cut_status = "blocked"
            blocked_by_issue = True
            status = "pending"
            cut_reason = "major_issue_lock"
            time_window_offset_percent = None
        elif mismatch_minutes >= config.major_issue_duration_minutes:
            cut_status = "major_issue"
            major_issue = True
            status = "abnormal"
            cut_reason = "continuous_mismatch"
            major_issue_triggered = True
        elif time_window_offset_percent > config.time_tolerance_percent:
            status = "abnormal"
            cut_reason = "time_offset_exceed"
        else:
            cut_reason = "within_tolerance"

        power_curve = _curve_points(start_time, 46, 430 + (idx % 7), 35, phase=float(idx))
        voltage_curve = _curve_points(start_time, 46, 378 + (idx % 5), 8, phase=float(idx + 3))
        baseline_power_curve = _curve_points(start_time, 46, 435, 24, phase=2.0)
        baseline_voltage_curve = _curve_points(start_time, 46, 380, 5, phase=1.0)

        max_dev = None if status == "pending" else round(4.2 + (idx % 9) * 1.8, 3)
        avg_dev = None if status == "pending" else round(2.1 + (idx % 7) * 1.1, 3)

        heat_id = f"heat-{idx + 1:03d}"
        plant_start_time = to_plant_datetime(start_time, get_plant_timezone())
        seeded[heat_id] = {
            "id": heat_id,
            "heat_no": f"H{plant_start_time.strftime('%Y%m%d')}-{idx + 1:03d}",
            "description": None,
            "start_time": start_time,
            "end_time": end_time,
            "completion_status": "completed",
            "last_point_at": end_time,
            "baseline_id": "baseline-001" if status != "pending" else None,
            "baseline_version_id": "baseline-001" if status != "pending" else None,
            "baseline_effective_from": None,
            "baseline_ids": ["baseline-001", "baseline-002"] if status != "pending" else [],
            "deviation_score": max_dev,
            "avg_deviation_score": avg_dev,
            "abnormal_duration_minutes": mismatch_minutes,
            "schedule_tag": schedule_tag,
            "cut_reason": cut_reason,
            "cut_status": cut_status,
            "major_issue": major_issue,
            "blocked_by_issue": blocked_by_issue,
            "status": status,
            "temperature": round(1450 + (idx % 6) * 5.5, 2),
            "record_source": "demo_seed",
            "current_curve_source": "demo_curve",
            "baseline_curve_source": "demo_curve",
            "created_at": start_time,
            "power_curve": power_curve,
            "voltage_curve": voltage_curve,
            "baseline_power_curve": baseline_power_curve,
            "baseline_voltage_curve": baseline_voltage_curve,
        }
    return seeded


def _seed_mock_stream_heats() -> dict[str, dict[str, Any]]:
    """为显式 mock 流入口构造独立种子数据。"""
    seeded = _seed_heats()
    for item in seeded.values():
        item["record_source"] = "mock_stream"
        item["current_curve_source"] = "mock_curve"
        item["baseline_curve_source"] = "mock_curve"
    return seeded


def _is_mock_heat_record(item: dict[str, Any]) -> bool:
    return str(item.get("record_source") or "").strip().lower() in {"demo_seed", "mock_stream"}


def _is_real_heat_record(item: dict[str, Any]) -> bool:
    return str(item.get("record_source") or "").strip().lower() in {
        "live_inferred",
        "live_edc",
        "active_runtime",
        "previous_runtime",
        "sealed_history",
    }


_HEAT_STORE: dict[str, dict[str, Any]] = {}
_ACTIVE_HEAT_RUNTIME: dict[str, dict[str, Any]] = {}
_PREVIOUS_HEAT_RUNTIME: dict[str, dict[str, Any]] = {}
_HEAT_ID_ALIAS_STORE: dict[str, str] = {}
_HEAT_STREAM_PROCESSOR_STATE: dict[str, Any] = {}
_MOCK_HEAT_STREAM_STORE: dict[str, dict[str, Any]] = _seed_mock_stream_heats()
_NEXT_MOCK_HEAT_INDEX = len(_MOCK_HEAT_STREAM_STORE) + 1
_HEAT_RUNTIME_REFRESH_META: dict[str, Any] = {}
_HEAT_RUNTIME_REFRESH_INFLIGHT: asyncio.Task[dict[str, Any]] | None = None
_HEAT_RUNTIME_REFRESH_LOOP_TASK: asyncio.Task[None] | None = None
_HEAT_RUNTIME_FACTORY = HeatRuntimeFactory()
_HEAT_RUNTIME_UPDATER = HeatRuntimeUpdater()
_HEAT_RUNTIME_TRANSITION_SERVICE = HeatRuntimeTransitionService()
_HEAT_RUNTIME_SEAL_SERVICE = HeatRuntimeSealService()
_REPLAY_BASELINE_SELECTION_SERVICE = ReplayBaselineSelectionService()


def _default_heat_runtime_refresh_meta() -> dict[str, Any]:
    return {
        "snapshot_status": "warming",
        "refresh_status": "idle",
        "refresh_reason": None,
        "refresh_outcome": None,
        "refresh_error": None,
        "refresh_failure_count": 0,
        "snapshot_watermark": None,
        "last_refresh_started_at": None,
        "last_refresh_completed_at": None,
    }


def _reset_heat_runtime_refresh_meta() -> None:
    _HEAT_RUNTIME_REFRESH_META.clear()
    _HEAT_RUNTIME_REFRESH_META.update(_default_heat_runtime_refresh_meta())


_reset_heat_runtime_refresh_meta()


def _baseline_effective_from(item: dict[str, Any] | None) -> datetime | None:
    if not item:
        return None
    effective_from = item.get("effective_from")
    if isinstance(effective_from, datetime):
        return effective_from
    published_at = item.get("published_at")
    if isinstance(published_at, datetime):
        return published_at
    updated_at = item.get("updated_at")
    if isinstance(updated_at, datetime):
        return updated_at
    created_at = item.get("created_at")
    if isinstance(created_at, datetime):
        return created_at
    return None


def _resolve_baseline_version_for_time(at_time: datetime) -> dict[str, Any] | None:
    published = [
        item
        for item in _BASELINE_STORE.values()
        if item.get("status") == "published" and _baseline_effective_from(item) is not None
    ]
    if published:
        eligible = [item for item in published if _baseline_effective_from(item) <= at_time]
        if eligible:
            eligible.sort(
                key=lambda item: (
                    bool(item.get("is_default")),
                    _baseline_effective_from(item),
                ),
                reverse=True,
            )
            return eligible[0]
        return None
    return None


def _list_applicable_runtime_baselines(at_time: datetime) -> list[dict[str, Any]]:
    published = [
        item
        for item in _BASELINE_STORE.values()
        if item.get("status") == "published" and _baseline_effective_from(item) is not None
    ]
    eligible = [item for item in published if _baseline_effective_from(item) <= at_time]
    eligible.sort(
        key=lambda item: (
            bool(item.get("is_default")),
            _baseline_effective_from(item),
            item.get("published_at")
            if isinstance(item.get("published_at"), datetime)
            else datetime.min,
            item.get("updated_at")
            if isinstance(item.get("updated_at"), datetime)
            else datetime.min,
        ),
        reverse=True,
    )
    return eligible


def _build_runtime_metric_series_from_dict(
    *,
    owner_key: str,
    entry: dict[str, Any],
) -> RuntimeMetricSeries | None:
    metric_key = str(entry.get("metric_key") or "").strip()
    metric_name = str(entry.get("metric_name") or "").strip()
    item = str(entry.get("item") or "").strip()
    color = str(entry.get("color") or "").strip()
    if not metric_key or not metric_name or not item or not color:
        return None
    normalized = _coerce_curve_points(_runtime_series_payload(entry).get("points"))
    if not normalized:
        return None
    raw_stat_json = entry.get("stat_json")
    stat_json = raw_stat_json if isinstance(raw_stat_json, dict) else {}
    if not stat_json:
        stat_json = {
            "heat_min": min(float(point.value) for point in normalized),
            "heat_max": max(float(point.value) for point in normalized),
            "heat_avg": round(
                sum(float(point.value) for point in normalized) / max(len(normalized), 1),
                4,
            ),
        }
    return RuntimeMetricSeries(
        owner_key=owner_key,
        item=item,
        owner_type="heat",
        metric_key=metric_key,
        metric_name=metric_name,
        unit=str(entry.get("unit")) if entry.get("unit") is not None else None,
        color=color,
        sort_order=int(entry.get("sort_order") or 0),
        series_json=_runtime_series_payload(entry),
        stat_json=stat_json,
    )


def _build_runtime_bindings(item: dict[str, Any]) -> list[RuntimeHeatBinding]:
    existing_bindings = item.get("baseline_bindings")
    if isinstance(existing_bindings, list) and existing_bindings:
        normalized: list[RuntimeHeatBinding] = []
        for binding in existing_bindings:
            if not isinstance(binding, dict):
                continue
            baseline_definition_id = str(binding.get("baseline_definition_id") or "")
            baseline_item = str(binding.get("baseline_item") or "")
            baseline_id = str(binding.get("baseline_id") or "")
            if not baseline_definition_id or not baseline_item or not baseline_id:
                continue
            normalized.append(
                RuntimeHeatBinding(
                    heat_id=str(item["id"]),
                    baseline_id=baseline_id,
                    baseline_definition_id=baseline_definition_id,
                    baseline_item=baseline_item,
                    is_primary=bool(binding.get("is_primary")),
                    baseline_effective_from=binding.get("baseline_effective_from"),
                    tolerance_percent=(
                        float(binding.get("tolerance_percent"))
                        if binding.get("tolerance_percent") is not None
                        else None
                    ),
                    analysis_status=str(binding.get("analysis_status") or "waiting"),
                    analysis_reason=(
                        str(binding.get("analysis_reason"))
                        if binding.get("analysis_reason") is not None
                        else None
                    ),
                    analysis_message=(
                        str(binding.get("analysis_message"))
                        if binding.get("analysis_message") is not None
                        else None
                    ),
                    deviation_score=(
                        float(binding.get("deviation_score"))
                        if binding.get("deviation_score") is not None
                        else None
                    ),
                    avg_deviation_score=(
                        float(binding.get("avg_deviation_score"))
                        if binding.get("avg_deviation_score") is not None
                        else None
                    ),
                    analysis_details_json=(
                        str(binding.get("analysis_details_json"))
                        if binding.get("analysis_details_json") is not None
                        else None
                    ),
                    abnormal_duration_minutes=(
                        float(binding.get("abnormal_duration_minutes"))
                        if binding.get("abnormal_duration_minutes") is not None
                        else None
                    ),
                )
            )
        if normalized:
            return normalized

    applicable = _list_applicable_runtime_baselines(item["start_time"])
    if not applicable:
        return []
    primary = applicable[0]
    candidate_baseline_id = (
        str(item.get("baseline_id")).strip() if item.get("baseline_id") else None
    )
    bindings: list[RuntimeHeatBinding] = []
    primary_baseline_id = str(primary.get("id") or "")
    for baseline_item in applicable:
        baseline_definition_id = str(baseline_item.get("definition_id") or "")
        baseline_version_item = str(baseline_item.get("item") or "")
        baseline_id = str(
            baseline_item.get("id")
            or encode_baseline_id(baseline_definition_id, baseline_version_item)
        )
        should_seed = False
        if candidate_baseline_id and candidate_baseline_id == baseline_id:
            should_seed = True
        elif candidate_baseline_id is None and primary_baseline_id == baseline_id:
            should_seed = True
        analysis_ready = should_seed and item.get("deviation_score") is not None
        bindings.append(
            RuntimeHeatBinding(
                heat_id=str(item["id"]),
                baseline_id=baseline_id,
                baseline_definition_id=baseline_definition_id,
                baseline_item=baseline_version_item,
                is_primary=baseline_id == primary_baseline_id,
                baseline_effective_from=_baseline_effective_from(baseline_item),
                tolerance_percent=(
                    float(baseline_item.get("tolerance_percent"))
                    if baseline_item.get("tolerance_percent") is not None
                    else None
                ),
                analysis_status="ready" if analysis_ready else "waiting",
                analysis_reason=None if analysis_ready else "metric_inputs_missing",
                analysis_message=(
                    None if analysis_ready else "当前数据尚未准备完成，暂无法计算偏离度"
                ),
                deviation_score=item.get("deviation_score") if should_seed else None,
                avg_deviation_score=item.get("avg_deviation_score") if should_seed else None,
                analysis_details_json=None,
                abnormal_duration_minutes=(
                    item.get("abnormal_duration_minutes") if should_seed else None
                ),
            )
        )
    return bindings


def _build_runtime_definition_metric_snapshots(
    item: dict[str, Any],
) -> list[RuntimeDefinitionMetricSnapshot]:
    raw_birth_context = item.get("birth_context")
    if isinstance(raw_birth_context, dict):
        raw_snapshots = raw_birth_context.get("definition_metric_snapshots")
    else:
        raw_snapshots = item.get("definition_metric_snapshots")
    if not isinstance(raw_snapshots, list):
        return []

    snapshots: list[RuntimeDefinitionMetricSnapshot] = []
    for snapshot in raw_snapshots:
        if not isinstance(snapshot, dict):
            continue
        metric_key = str(snapshot.get("metric_key") or "").strip()
        metric_name = str(snapshot.get("metric_name") or "").strip()
        item_no = str(snapshot.get("item") or "").strip()
        color = str(snapshot.get("color") or "").strip()
        if not metric_key or not metric_name or not item_no or not color:
            continue
        snapshots.append(
            RuntimeDefinitionMetricSnapshot(
                item=item_no,
                metric_key=metric_key,
                metric_name=metric_name,
                unit=str(snapshot.get("unit")) if snapshot.get("unit") is not None else None,
                color=color,
                sort_order=int(snapshot.get("sort_order") or 0),
                edc_channel_id=(
                    str(snapshot.get("edc_channel_id"))
                    if snapshot.get("edc_channel_id") is not None
                    else None
                ),
                source_channel_name=(
                    str(snapshot.get("source_channel_name"))
                    if snapshot.get("source_channel_name") is not None
                    else None
                ),
                source_channel_label=(
                    str(snapshot.get("source_channel_label"))
                    if snapshot.get("source_channel_label") is not None
                    else None
                ),
                enabled=bool(snapshot.get("enabled", True)),
            )
        )
    return snapshots


def _build_runtime_baseline_curve_snapshots(
    item: dict[str, Any],
) -> list[RuntimeBaselineCurveSnapshot]:
    raw_birth_context = item.get("birth_context")
    if isinstance(raw_birth_context, dict):
        raw_snapshots = raw_birth_context.get("baseline_curve_snapshots")
    else:
        raw_snapshots = item.get("baseline_curve_snapshots")
    if not isinstance(raw_snapshots, list):
        return []

    snapshots: list[RuntimeBaselineCurveSnapshot] = []
    for snapshot in raw_snapshots:
        if not isinstance(snapshot, dict):
            continue
        baseline_id = str(snapshot.get("baseline_id") or "").strip()
        metric_key = str(snapshot.get("metric_key") or "").strip()
        if not baseline_id or not metric_key:
            continue
        snapshots.append(
            RuntimeBaselineCurveSnapshot(
                baseline_id=baseline_id,
                metric_key=metric_key,
                curve_source=str(snapshot.get("curve_source") or "none"),
                points=_coerce_curve_points(snapshot.get("points")),
            )
        )
    return snapshots


def _build_runtime_baseline_view_objects(
    item: dict[str, Any],
) -> list[RuntimeBaselineView]:
    raw_views = item.get("baseline_views")
    if not isinstance(raw_views, list):
        return []

    views: list[RuntimeBaselineView] = []
    for raw_view in raw_views:
        if not isinstance(raw_view, dict):
            continue
        baseline_id = str(raw_view.get("baseline_id") or "").strip()
        baseline_definition_id = str(raw_view.get("baseline_definition_id") or "").strip()
        baseline_item = str(raw_view.get("baseline_item") or "").strip()
        if not baseline_id or not baseline_definition_id or not baseline_item:
            continue
        metric_series: list[RuntimeMetricSeries] = []
        raw_metric_series = raw_view.get("current_metric_series")
        if isinstance(raw_metric_series, list):
            for entry in raw_metric_series:
                if not isinstance(entry, dict):
                    continue
                payload = _build_runtime_metric_series_from_dict(
                    owner_key=str(item.get("id") or ""),
                    entry=entry,
                )
                if payload is not None:
                    metric_series.append(payload)
        views.append(
            RuntimeBaselineView(
                heat_id=str(raw_view.get("heat_id") or item.get("id") or ""),
                baseline_id=baseline_id,
                baseline_definition_id=baseline_definition_id,
                baseline_item=baseline_item,
                is_primary=bool(raw_view.get("is_primary")),
                baseline_effective_from=raw_view.get("baseline_effective_from"),
                tolerance_percent=(
                    float(raw_view.get("tolerance_percent"))
                    if raw_view.get("tolerance_percent") is not None
                    else None
                ),
                required_metric_keys=[
                    str(metric_key)
                    for metric_key in (raw_view.get("required_metric_keys") or [])
                    if isinstance(metric_key, str) and metric_key.strip()
                ],
                current_metric_series=metric_series,
                analysis_status=str(raw_view.get("analysis_status") or "waiting"),
                analysis_reason=(
                    str(raw_view.get("analysis_reason"))
                    if raw_view.get("analysis_reason") is not None
                    else None
                ),
                analysis_message=(
                    str(raw_view.get("analysis_message"))
                    if raw_view.get("analysis_message") is not None
                    else None
                ),
                deviation_score=(
                    float(raw_view.get("deviation_score"))
                    if raw_view.get("deviation_score") is not None
                    else None
                ),
                avg_deviation_score=(
                    float(raw_view.get("avg_deviation_score"))
                    if raw_view.get("avg_deviation_score") is not None
                    else None
                ),
                analysis_details_json=(
                    str(raw_view.get("analysis_details_json"))
                    if raw_view.get("analysis_details_json") is not None
                    else None
                ),
                abnormal_duration_minutes=(
                    float(raw_view.get("abnormal_duration_minutes"))
                    if raw_view.get("abnormal_duration_minutes") is not None
                    else None
                ),
            )
        )
    return views


def _build_runtime_cutting_config_snapshot(
    item: dict[str, Any],
) -> RuntimeCuttingConfigSnapshot | None:
    raw_birth_context = item.get("birth_context")
    if not isinstance(raw_birth_context, dict):
        return None

    raw_snapshot = raw_birth_context.get("cutting_config_snapshot")
    if not isinstance(raw_snapshot, dict):
        return None

    try:
        fixed_interval_minutes = raw_snapshot.get("fixed_interval_minutes")
        cutting_mode = normalize_cutting_mode(raw_snapshot.get("cutting_mode"))
        return RuntimeCuttingConfigSnapshot(
            time_tolerance_percent=float(raw_snapshot.get("time_tolerance_percent") or 0.0),
            major_issue_duration_minutes=int(raw_snapshot.get("major_issue_duration_minutes") or 0),
            plant_timezone=str(raw_snapshot.get("plant_timezone") or ""),
            work_start_time=str(raw_snapshot.get("work_start_time") or ""),
            work_end_time=str(raw_snapshot.get("work_end_time") or ""),
            break_periods=tuple(
                str(period) for period in (raw_snapshot.get("break_periods") or [])
            ),
            cutting_mode=cutting_mode,
            fixed_interval_minutes=(
                int(fixed_interval_minutes)
                if fixed_interval_minutes is not None
                else (30 if cutting_mode == "fixed_interval" else None)
            ),
        )
    except (TypeError, ValueError):
        return None


def _build_heat_birth_context(
    item: dict[str, Any],
    *,
    bindings: list[RuntimeHeatBinding],
    definition_metric_snapshots: list[RuntimeDefinitionMetricSnapshot],
    baseline_curve_snapshots: list[RuntimeBaselineCurveSnapshot],
) -> HeatBirthContext | None:
    raw_birth_context = item.get("birth_context")
    if not isinstance(raw_birth_context, dict):
        return None

    heat_id = str(raw_birth_context.get("heat_id") or item.get("id") or "").strip()
    if not heat_id:
        return None

    raw_bindings_snapshot = raw_birth_context.get("baseline_bindings_snapshot")
    baseline_bindings_snapshot = (
        [dict(binding) for binding in raw_bindings_snapshot if isinstance(binding, dict)]
        if isinstance(raw_bindings_snapshot, list)
        else [binding.to_dict() for binding in bindings]
    )
    return HeatBirthContext(
        heat_id=heat_id,
        channel_key=(
            str(raw_birth_context.get("channel_key"))
            if raw_birth_context.get("channel_key") is not None
            else None
        ),
        cutting_mode=(
            str(raw_birth_context.get("cutting_mode"))
            if raw_birth_context.get("cutting_mode") is not None
            else None
        ),
        expected_duration_minutes=(
            int(raw_birth_context.get("expected_duration_minutes"))
            if raw_birth_context.get("expected_duration_minutes") is not None
            else None
        ),
        plant_timezone=(
            str(raw_birth_context.get("plant_timezone"))
            if raw_birth_context.get("plant_timezone") is not None
            else None
        ),
        cutting_config_snapshot=_build_runtime_cutting_config_snapshot(item),
        primary_baseline_id=(
            str(raw_birth_context.get("primary_baseline_id"))
            if raw_birth_context.get("primary_baseline_id") is not None
            else None
        ),
        baseline_bindings_snapshot=baseline_bindings_snapshot,
        definition_metric_snapshots=definition_metric_snapshots,
        baseline_curve_snapshots=baseline_curve_snapshots,
    )


def _build_current_heat_runtime(
    item: dict[str, Any],
    *,
    trigger_source: str,
    processing_mode: str = "live_incremental",
) -> CurrentHeatRuntime:
    start_time = item["start_time"]
    end_time = item["end_time"]
    context_start_time = item.get("context_start_time") or start_time
    context_end_time = item.get("context_end_time") or end_time
    actual_context_start_time, actual_context_end_time = _resolve_actual_context_bounds(item)
    facts = RuntimeHeatFacts(
        heat_id=str(item["id"]),
        heat_no=str(item["heat_no"]),
        description=item.get("description"),
        furnace_id=str(item.get("furnace_id") or item.get("_live_context_key") or "") or None,
        start_time=start_time,
        end_time=end_time,
        context_start_time=context_start_time,
        context_end_time=context_end_time,
        actual_context_start_time=actual_context_start_time,
        actual_context_end_time=actual_context_end_time,
        is_manually_adjusted=bool(item.get("is_manually_adjusted") or False),
        completion_status=str(item.get("completion_status") or "completed"),
        last_point_at=item.get("last_point_at") or context_end_time or end_time,
        schedule_tag=str(item.get("schedule_tag") or "work"),
        cut_reason=item.get("cut_reason"),
        cut_status=str(item.get("cut_status") or "normal"),
        major_issue=bool(item.get("major_issue") or False),
        blocked_by_issue=bool(item.get("blocked_by_issue") or False),
        status=str(item.get("status") or "normal"),
        temperature=item.get("temperature"),
        record_source=str(item.get("record_source") or "live_inferred"),
        current_curve_source=str(item.get("current_curve_source") or "live_edc"),
        baseline_curve_source=str(item.get("baseline_curve_source") or "none"),
        created_at=item.get("created_at") or utc_now(),
        sealed_at=item.get("sealed_at"),
    )
    metric_series: list[RuntimeMetricSeries] = []
    raw_runtime_metric_series = item.get("runtime_metric_series")
    if isinstance(raw_runtime_metric_series, list) and raw_runtime_metric_series:
        for entry in raw_runtime_metric_series:
            if not isinstance(entry, dict):
                continue
            payload = _build_runtime_metric_series_from_dict(owner_key=facts.heat_id, entry=entry)
            if payload is not None:
                metric_series.append(payload)
    if not metric_series:
        raise ValueError("runtime_metric_series_missing")
    bindings = _build_runtime_bindings(item)
    baseline_views = _build_runtime_baseline_view_objects(item)
    definition_metric_snapshots = _build_runtime_definition_metric_snapshots(item)
    baseline_curve_snapshots = _build_runtime_baseline_curve_snapshots(item)
    birth_context = _build_heat_birth_context(
        item,
        bindings=bindings,
        definition_metric_snapshots=definition_metric_snapshots,
        baseline_curve_snapshots=baseline_curve_snapshots,
    )
    raw_processing_meta = item.get("processing_meta")
    if isinstance(raw_processing_meta, dict):
        processing_meta = RuntimeProcessingMeta(
            processing_mode=str(raw_processing_meta.get("processing_mode") or processing_mode),
            trigger_source=str(raw_processing_meta.get("trigger_source") or trigger_source),
            request_anchor_time=raw_processing_meta.get("request_anchor_time") or start_time,
            batch_cursor=(
                str(raw_processing_meta.get("batch_cursor"))
                if raw_processing_meta.get("batch_cursor") is not None
                else None
            ),
            last_processed_heat_id=(
                str(raw_processing_meta.get("last_processed_heat_id"))
                if raw_processing_meta.get("last_processed_heat_id") is not None
                else facts.heat_id
            ),
        )
    else:
        processing_meta = RuntimeProcessingMeta(
            processing_mode=processing_mode,
            trigger_source=trigger_source,
            request_anchor_time=start_time,
            batch_cursor=None,
            last_processed_heat_id=facts.heat_id,
        )
    raw_preseal_payload = item.get("preseal_payload")
    preseal_payload = (
        RuntimePresealPayload(
            heat_payload=dict(raw_preseal_payload.get("heat_payload") or {}),
            binding_payloads=[
                dict(binding_payload)
                for binding_payload in (raw_preseal_payload.get("binding_payloads") or [])
                if isinstance(binding_payload, dict)
            ],
            metric_series_payloads=[
                dict(metric_payload)
                for metric_payload in (raw_preseal_payload.get("metric_series_payloads") or [])
                if isinstance(metric_payload, dict)
            ],
        )
        if isinstance(raw_preseal_payload, dict)
        else None
    )
    return CurrentHeatRuntime(
        facts=facts,
        birth_context=birth_context,
        bindings=bindings,
        metric_series=metric_series,
        baseline_views=baseline_views,
        definition_metric_snapshots=definition_metric_snapshots,
        baseline_curve_snapshots=baseline_curve_snapshots,
        preseal_payload=preseal_payload,
        processing_meta=processing_meta,
        refresh_meta={},
        power_curve=_coerce_curve_points(item.get("power_curve")),
        voltage_curve=_coerce_curve_points(item.get("voltage_curve")),
        baseline_power_curve=_coerce_curve_points(item.get("baseline_power_curve")),
        baseline_voltage_curve=_coerce_curve_points(item.get("baseline_voltage_curve")),
    )


def _mark_active_runtime(item: dict[str, Any]) -> dict[str, Any]:
    active_item = dict(item)
    active_item["completion_status"] = "in_progress"
    active_item["last_point_at"] = (
        active_item.get("last_point_at")
        or active_item.get("actual_context_end_time")
        or active_item.get("context_end_time")
        or active_item.get("end_time")
    )
    active_item["status"] = "pending"
    active_item["record_source"] = "active_runtime"
    return active_item


def _mark_previous_runtime(item: dict[str, Any]) -> dict[str, Any]:
    previous_item = dict(item)
    previous_item["completion_status"] = "completed"
    previous_item["last_point_at"] = (
        previous_item.get("last_point_at")
        or previous_item.get("actual_context_end_time")
        or previous_item.get("context_end_time")
        or previous_item.get("end_time")
    )
    previous_item["record_source"] = "previous_runtime"
    previous_item["sealed_at"] = None
    return previous_item


def _mark_history_runtime(item: dict[str, Any]) -> dict[str, Any]:
    history_item = dict(item)
    history_item["completion_status"] = "completed"
    history_item["last_point_at"] = (
        history_item.get("last_point_at")
        or history_item.get("actual_context_end_time")
        or history_item.get("context_end_time")
        or history_item.get("end_time")
    )
    history_item["record_source"] = "sealed_history"
    history_item["sealed_at"] = utc_now()
    return history_item


def _choose_next_previous_runtime(
    *,
    existing_active_item: dict[str, Any] | None,
    existing_previous_item: dict[str, Any] | None,
    next_active_candidate_id: str | None,
    prepared_previous_candidate: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any] | None:
    existing_active_id = (
        str(existing_active_item.get("id") or "")
        if isinstance(existing_active_item, dict)
        else None
    )
    active_rollover = bool(existing_active_id) and existing_active_id != (
        next_active_candidate_id or ""
    )

    if active_rollover:
        if prepared_previous_candidate is not None:
            previous_runtime = _build_current_heat_runtime(
                prepared_previous_candidate,
                trigger_source=reason,
                processing_mode="live_incremental",
            )
            return _mark_previous_runtime(previous_runtime.to_runtime_item())
        if isinstance(existing_active_item, dict):
            return _mark_previous_runtime(dict(existing_active_item))
        return None

    if prepared_previous_candidate is not None:
        previous_runtime = _build_current_heat_runtime(
            prepared_previous_candidate,
            trigger_source=reason,
            processing_mode="live_incremental",
        )
        return _mark_previous_runtime(previous_runtime.to_runtime_item())

    if isinstance(existing_previous_item, dict):
        return dict(existing_previous_item)

    return None


def _build_runtime_lookup_store() -> dict[str, dict[str, Any]]:
    lookup = dict(_HEAT_STORE)
    lookup.update(_PREVIOUS_HEAT_RUNTIME)
    lookup.update(_ACTIVE_HEAT_RUNTIME)
    return lookup


def _resolve_heat_alias_id(heat_id: str) -> str:
    current_id = heat_id
    visited = {current_id}
    while True:
        target_id = _HEAT_ID_ALIAS_STORE.get(current_id)
        if not target_id or target_id in visited:
            return current_id
        visited.add(target_id)
        current_id = target_id


def _link_heat_alias(source_id: str | None, target_id: str | None) -> None:
    if not source_id or not target_id or source_id == target_id:
        return
    _HEAT_ID_ALIAS_STORE[str(source_id)] = str(target_id)


def _find_overlapping_heat_record(
    item: dict[str, Any], candidates: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    overlapping = [
        candidate
        for candidate in candidates.values()
        if _has_overlapping_time_window(item, candidate)
    ]
    if not overlapping:
        return None

    item_window = _resolve_item_time_window_ms(item)
    if not item_window:
        return overlapping[0]
    item_start, item_end = item_window
    return min(
        overlapping,
        key=lambda candidate: (
            abs((_resolve_item_time_window_ms(candidate) or (0, 0))[0] - item_start),
            abs((_resolve_item_time_window_ms(candidate) or (0, 0))[1] - item_end),
        ),
    )


def _seal_runtime_candidates(
    candidates: list[dict[str, Any]],
    *,
    existing_history: dict[str, dict[str, Any]],
    runtime_items: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    runtime_lookup = {
        str(item.get("id") or ""): item for item in (runtime_items or []) if item.get("id")
    }
    sealed_history: dict[str, dict[str, Any]] = {}
    for heat_id, existing_item in existing_history.items():
        runtime_target = _find_overlapping_heat_record(existing_item, runtime_lookup)
        if runtime_target:
            _link_heat_alias(
                str(existing_item.get("id") or ""),
                str(runtime_target.get("id") or ""),
            )
            continue
        normalized = dict(existing_item)
        normalized["completion_status"] = "completed"
        normalized["record_source"] = "sealed_history"
        normalized["last_point_at"] = normalized.get("last_point_at") or normalized.get("end_time")
        normalized["sealed_at"] = normalized.get("sealed_at") or utc_now()
        sealed_history[heat_id] = normalized
    for candidate in candidates:
        existing = _find_overlapping_heat_record(candidate, sealed_history)
        if existing:
            _link_heat_alias(str(candidate.get("id") or ""), str(existing.get("id") or ""))
            continue
        sealed_item = _mark_history_runtime(candidate)
        sealed_history[str(sealed_item["id"])] = sealed_item
    return sealed_history


def _register_runtime_aliases(
    previous_runtime_items: list[dict[str, Any]],
    next_runtime_lookup: dict[str, dict[str, Any]],
) -> None:
    for previous_item in previous_runtime_items:
        previous_id = str(previous_item.get("id") or "")
        if not previous_id:
            continue
        if previous_id in next_runtime_lookup:
            continue
        target = _find_overlapping_heat_record(previous_item, next_runtime_lookup)
        if target:
            _link_heat_alias(previous_id, str(target.get("id") or ""))


def _is_active_runtime_candidate(item: dict[str, Any], *, now: datetime) -> bool:
    end_time = item.get("end_time")
    if not isinstance(end_time, datetime):
        return False
    return (now - end_time) <= timedelta(minutes=_LIVE_HEAT_GAP_MINUTES)


def _refresh_failure_count() -> int:
    try:
        return max(int(_HEAT_RUNTIME_REFRESH_META.get("refresh_failure_count") or 0), 0)
    except (TypeError, ValueError):
        return 0


def _runtime_snapshot_watermark() -> datetime | None:
    watermark = _HEAT_RUNTIME_REFRESH_META.get("snapshot_watermark")
    return watermark if isinstance(watermark, datetime) else None


def _has_runtime_snapshot_data() -> bool:
    return bool(
        _HEAT_STORE
        or _PREVIOUS_HEAT_RUNTIME
        or _ACTIVE_HEAT_RUNTIME
        or _runtime_snapshot_watermark()
    )


def _is_runtime_snapshot_fresh(*, now: datetime | None = None) -> bool:
    watermark = _runtime_snapshot_watermark()
    if watermark is None:
        return False
    current_time = now or utc_now()
    return (current_time - watermark) <= timedelta(seconds=_HEAT_RUNTIME_STALE_THRESHOLD_SECONDS)


def _runtime_snapshot_status(*, now: datetime | None = None) -> str:
    current_time = now or utc_now()
    refresh_status = str(_HEAT_RUNTIME_REFRESH_META.get("refresh_status") or "idle")
    has_snapshot_data = _has_runtime_snapshot_data()
    if refresh_status == "running":
        return "warming" if not has_snapshot_data else "refreshing_history"
    if _refresh_failure_count() >= _HEAT_RUNTIME_ERROR_FAILURE_THRESHOLD:
        return "error"
    if not has_snapshot_data:
        return "warming"
    if not _is_runtime_snapshot_fresh(now=current_time):
        return "stale"
    return "ready"


def _sync_heat_runtime_refresh_meta_status(*, now: datetime | None = None) -> None:
    _HEAT_RUNTIME_REFRESH_META["snapshot_status"] = _runtime_snapshot_status(now=now)


def _build_heat_runtime_refresh_meta_snapshot(*, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or utc_now()
    snapshot = dict(_HEAT_RUNTIME_REFRESH_META)
    snapshot["refresh_failure_count"] = _refresh_failure_count()
    snapshot["snapshot_is_fresh"] = _is_runtime_snapshot_fresh(now=current_time)
    snapshot["snapshot_status"] = _runtime_snapshot_status(now=current_time)
    return snapshot


def _mark_heat_runtime_refresh_failure(*, error: str, completed_at: datetime | None = None) -> None:
    finished_at = completed_at or utc_now()
    _HEAT_RUNTIME_REFRESH_META.update(
        {
            "refresh_status": "idle",
            "refresh_outcome": "runtime_refresh_failed",
            "refresh_error": error,
            "refresh_failure_count": _refresh_failure_count() + 1,
            "last_refresh_completed_at": finished_at,
        }
    )
    _sync_heat_runtime_refresh_meta_status(now=finished_at)


def _mark_heat_runtime_refresh_success(
    *,
    reason: str,
    refresh_outcome: str | None,
    snapshot_watermark: datetime | None,
    completed_at: datetime | None = None,
) -> None:
    finished_at = completed_at or utc_now()
    _HEAT_RUNTIME_REFRESH_META.update(
        {
            "refresh_reason": reason,
            "refresh_status": "idle",
            "refresh_outcome": refresh_outcome,
            "refresh_error": None,
            "refresh_failure_count": 0,
            "snapshot_watermark": snapshot_watermark,
            "last_refresh_completed_at": finished_at,
        }
    )
    _sync_heat_runtime_refresh_meta_status(now=finished_at)


def _is_realtime_current_heat(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    current_time = now or utc_now()
    return (
        str(item.get("record_source") or "") == "active_runtime"
        and str(item.get("completion_status") or "") == "in_progress"
        and _runtime_snapshot_status(now=current_time) in {"ready", "refreshing_history"}
        and _is_runtime_snapshot_fresh(now=current_time)
    )


def _to_heat_response(item: dict[str, Any]) -> HeatResponse:
    current_time = utc_now()
    context_start_time = item.get("context_start_time") or item["start_time"]
    context_end_time = item.get("context_end_time") or item["end_time"]
    actual_context_start_time, actual_context_end_time = _resolve_actual_context_bounds(item)
    return HeatResponse(
        id=item["id"],
        heat_no=item["heat_no"],
        description=item.get("description"),
        start_time=item["start_time"],
        end_time=item["end_time"],
        context_start_time=context_start_time,
        context_end_time=context_end_time,
        actual_context_start_time=actual_context_start_time,
        actual_context_end_time=actual_context_end_time,
        is_manually_adjusted=bool(item.get("is_manually_adjusted") or False),
        completion_status=str(item.get("completion_status") or "completed"),
        last_point_at=item.get("last_point_at"),
        runtime_snapshot_status=_runtime_snapshot_status(now=current_time),
        realtime_current=_is_realtime_current_heat(item, now=current_time),
        baseline_id=item["baseline_id"],
        baseline_version_id=item.get("baseline_version_id"),
        baseline_effective_from=item.get("baseline_effective_from"),
        analysis_status=(
            str(item.get("analysis_status")) if item.get("analysis_status") is not None else None
        ),
        analysis_reason=(
            str(item.get("analysis_reason")) if item.get("analysis_reason") is not None else None
        ),
        analysis_message=(
            str(item.get("analysis_message"))
            if item.get("analysis_message") is not None
            else None
        ),
        deviation_score=item["deviation_score"],
        avg_deviation_score=item["avg_deviation_score"],
        abnormal_duration_minutes=item.get("abnormal_duration_minutes"),
        schedule_tag=item.get("schedule_tag", "work"),
        cut_reason=item.get("cut_reason"),
        cut_status=item.get("cut_status", "normal"),
        major_issue=item.get("major_issue", False),
        blocked_by_issue=item.get("blocked_by_issue", False),
        status=item["status"],
        temperature=item["temperature"],
        record_source=str(item.get("record_source") or "none"),
        current_curve_source=str(item.get("current_curve_source") or "none"),
        baseline_curve_source=str(item.get("baseline_curve_source") or "none"),
        created_at=item["created_at"],
    )


def _to_heat_with_curve(item: dict[str, Any]) -> HeatWithCurve:
    return HeatWithCurve(
        **_to_heat_response(item).model_dump(),
        power_curve=item["power_curve"],
        voltage_curve=item["voltage_curve"],
    )


def _to_heat_replay_job_response(job) -> HeatReplayJobResponse:
    return HeatReplayJobResponse.model_validate(job)


def _ensure_persisted_heat(item: dict[str, Any]) -> dict[str, Any]:
    heat_id = str(item["id"])
    target_store = _MOCK_HEAT_STREAM_STORE if is_mock_dataset_enabled() else _HEAT_STORE
    stored_item = target_store.get(heat_id)
    if stored_item:
        return stored_item

    persisted_item = dict(item)
    target_store[heat_id] = persisted_item
    return persisted_item


def _mutable_heat_store() -> dict[str, dict[str, Any]]:
    return _MOCK_HEAT_STREAM_STORE if is_mock_dataset_enabled() else _HEAT_STORE


def _runtime_heat_sections() -> tuple[str, ...]:
    if is_mock_dataset_enabled():
        return ("mock_heats", "next_heat_index")
    return (
        "heats",
        "active_heat_runtime",
        "previous_heat_runtime",
        "heat_id_aliases",
        "heat_stream_processor_state",
        "heat_runtime_refresh_meta",
    )


async def _get_or_404(heat_id: str) -> dict[str, Any]:
    item = await resolve_heat_record(heat_id)
    if not item:
        raise HTTPException(status_code=404, detail="炉次不存在")
    return item


def _latest_heat() -> dict[str, Any] | None:
    if not _MOCK_HEAT_STREAM_STORE:
        return None
    return max(_MOCK_HEAT_STREAM_STORE.values(), key=lambda x: x["start_time"])


def _build_ingested_heat() -> dict[str, Any]:
    """构造一条实时流入的模拟炉次。"""
    global _NEXT_MOCK_HEAT_INDEX

    config = get_cutting_config()
    latest = _latest_heat()
    start_time = (
        latest["start_time"] + timedelta(minutes=50)
        if latest
        else utc_now().replace(second=0, microsecond=0)
    )
    end_time = start_time + timedelta(minutes=45)

    schedule_tag = _schedule_tag_of(start_time, config)
    mismatch_minutes = 3 + (_NEXT_MOCK_HEAT_INDEX % 9)
    time_window_offset_percent = round((_NEXT_MOCK_HEAT_INDEX % 8) * 1.7, 2)

    has_major_issue_lock = any(
        item.get("cut_status") == "major_issue" or item.get("cut_reason") == "major_issue_lock"
        for item in _MOCK_HEAT_STREAM_STORE.values()
    )

    cut_status = "normal"
    status = "normal"
    major_issue = False
    blocked_by_issue = False
    cut_reason = "within_tolerance"

    if schedule_tag in {"break", "off_shift"}:
        cut_status = "blocked"
        status = "pending"
        blocked_by_issue = True
        cut_reason = "schedule_window"
        time_window_offset_percent = None
    elif has_major_issue_lock:
        cut_status = "blocked"
        status = "pending"
        blocked_by_issue = True
        cut_reason = "major_issue_lock"
        time_window_offset_percent = None
    elif mismatch_minutes >= config.major_issue_duration_minutes:
        cut_status = "major_issue"
        status = "abnormal"
        major_issue = True
        cut_reason = "continuous_mismatch"
    elif time_window_offset_percent > config.time_tolerance_percent:
        status = "abnormal"
        cut_reason = "time_offset_exceed"

    power_curve = _curve_points(
        start_time,
        46,
        430 + (_NEXT_MOCK_HEAT_INDEX % 7),
        35,
        phase=float(_NEXT_MOCK_HEAT_INDEX),
    )
    voltage_curve = _curve_points(
        start_time,
        46,
        378 + (_NEXT_MOCK_HEAT_INDEX % 5),
        8,
        phase=float(_NEXT_MOCK_HEAT_INDEX + 3),
    )
    baseline_power_curve = _curve_points(start_time, 46, 435, 24, phase=2.0)
    baseline_voltage_curve = _curve_points(start_time, 46, 380, 5, phase=1.0)

    max_dev = None if status == "pending" else round(4.2 + (_NEXT_MOCK_HEAT_INDEX % 9) * 1.8, 3)
    avg_dev = None if status == "pending" else round(2.1 + (_NEXT_MOCK_HEAT_INDEX % 7) * 1.1, 3)

    heat_id = f"mock-heat-{_NEXT_MOCK_HEAT_INDEX:03d}"
    plant_start_time = to_plant_datetime(start_time, get_plant_timezone())
    heat = {
        "id": heat_id,
        "heat_no": f"M{plant_start_time.strftime('%Y%m%d')}-{_NEXT_MOCK_HEAT_INDEX:03d}",
        "description": None,
        "start_time": start_time,
        "end_time": end_time,
        "completion_status": "completed",
        "last_point_at": end_time,
        "baseline_id": "baseline-001" if status != "pending" else None,
        "baseline_version_id": "baseline-001" if status != "pending" else None,
        "baseline_effective_from": None,
        "baseline_ids": ["baseline-001", "baseline-002"] if status != "pending" else [],
        "deviation_score": max_dev,
        "avg_deviation_score": avg_dev,
        "abnormal_duration_minutes": mismatch_minutes,
        "schedule_tag": schedule_tag,
        "cut_reason": cut_reason,
        "cut_status": cut_status,
        "major_issue": major_issue,
        "blocked_by_issue": blocked_by_issue,
        "status": status,
        "temperature": round(1450 + (_NEXT_MOCK_HEAT_INDEX % 6) * 5.5, 2),
        "record_source": "mock_stream",
        "current_curve_source": "mock_curve",
        "baseline_curve_source": "mock_curve",
        "created_at": start_time,
        "power_curve": power_curve,
        "voltage_curve": voltage_curve,
        "baseline_power_curve": baseline_power_curve,
        "baseline_voltage_curve": baseline_voltage_curve,
    }
    _NEXT_MOCK_HEAT_INDEX += 1
    return heat


@router.get("/stream/mock", response_model=HeatListResponse)
async def get_mock_stream(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> HeatListResponse:
    """模拟实时流入炉次（按最近开始时间返回）。"""
    ensure_mock_dataset_enabled("mock 数据集未开启，禁止访问模拟流入接口")
    items = list(_MOCK_HEAT_STREAM_STORE.values())
    items.sort(key=lambda x: x["start_time"], reverse=True)
    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged = items[start_idx:end_idx]
    return HeatListResponse(
        items=[_to_heat_response(item) for item in paged],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/stream/mock/ingest", response_model=HeatResponse)
async def ingest_mock_stream_heat() -> HeatResponse:
    """模拟实时流入一条新炉次并返回。"""
    ensure_mock_dataset_enabled("mock 数据集未开启，禁止访问模拟流入接口")
    heat = _build_ingested_heat()
    _MOCK_HEAT_STREAM_STORE[heat["id"]] = heat
    await persist_runtime_state("mock_heats", "next_heat_index")
    return _to_heat_response(heat)


@router.get("", response_model=HeatListResponse)
async def list_heats(
    status: Literal["normal", "abnormal", "pending"] | None = Query(
        default=None, description="状态筛选"
    ),  # noqa: B008
    start_date: OptionalTimestampMs = Query(default=None, description="开始日期"),  # noqa: B008
    end_date: OptionalTimestampMs = Query(default=None, description="结束日期"),  # noqa: B008
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> HeatListResponse:
    """获取炉次列表（支持状态和日期范围筛选）。"""
    await _ensure_formal_baseline_mirrors_loaded()
    started_at = perf_counter()
    current_time = utc_now()
    normalized_start_date = _normalize_filter_datetime(start_date)
    normalized_end_date = _normalize_filter_datetime(end_date)
    items = await _list_heat_store()
    if isinstance(items, dict):
        items = list(items.values())
    items.sort(key=lambda x: x["start_time"], reverse=True)
    prepared_items = [dict(item) for item in items]

    if status:
        prepared_items = [item for item in prepared_items if item["status"] == status]
    if normalized_start_date:
        prepared_items = [
            item for item in prepared_items if item["start_time"] >= normalized_start_date
        ]
    if normalized_end_date:
        prepared_items = [
            item for item in prepared_items if item["start_time"] <= normalized_end_date
        ]

    total = len(prepared_items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged = prepared_items[start_idx:end_idx]
    refresh_meta = _build_heat_runtime_refresh_meta_snapshot(now=current_time)

    response = HeatListResponse(
        items=[_to_heat_response(item) for item in paged],
        total=total,
        page=page,
        page_size=page_size,
        snapshot_status=str(refresh_meta["snapshot_status"]),
        snapshot_watermark=refresh_meta.get("snapshot_watermark"),
        last_refresh_started_at=refresh_meta.get("last_refresh_started_at"),
        last_refresh_completed_at=refresh_meta.get("last_refresh_completed_at"),
        refresh_error=refresh_meta.get("refresh_error"),
        refresh_failure_count=int(refresh_meta.get("refresh_failure_count") or 0),
    )
    log_event(
        "api_heats_list",
        status=status,
        start_date=normalized_start_date,
        end_date=normalized_end_date,
        total=total,
        page=page,
        page_size=page_size,
        returned_count=len(response.items),
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
    )
    return response


@router.post("/runtime/refresh")
async def refresh_heat_runtime() -> dict[str, Any]:
    """异步刷新历史炉次运行态。"""
    task = schedule_heat_runtime_refresh(reason="manual")
    return {
        "success": True,
        "refresh_status": "running" if task else "idle",
        "snapshot_status": _runtime_snapshot_status(),
    }


@router.get("/replay-jobs", response_model=HeatReplayJobListResponse)
async def list_replay_jobs() -> HeatReplayJobListResponse:
    jobs = await list_heat_replay_job_records()
    return HeatReplayJobListResponse(items=[_to_heat_replay_job_response(job) for job in jobs])


@router.post("/replay-jobs", response_model=HeatReplayJobResponse, status_code=201)
async def create_replay_job(data: HeatReplayJobCreateRequest) -> HeatReplayJobResponse:
    end_time = data.end_time or utc_now().replace(microsecond=0)
    if data.start_time > end_time:
        raise HTTPException(status_code=400, detail="anchor_time_after_end_time")

    cutting_config = get_cutting_config()
    try:
        selection = await _REPLAY_BASELINE_SELECTION_SERVICE.resolve_selection(
            primary_baseline_id=data.primary_baseline_id,
            baseline_ids=data.baseline_ids,
        )
        replay_context = _build_replay_context_from_selection(
            selection,
            cutting_config=cutting_config,
        )
        job = await create_heat_replay_job_record(
            job_kind=data.job_kind,
            anchor_time=data.start_time,
            end_time=end_time,
            channel_key=str(replay_context.channel_key),
            cutting_config=cutting_config,
            force_replace=bool(data.force_replace),
        )

        def _build_replay_items_from_segments(
            segments: list[HeatSegment],
        ) -> list[dict[str, Any]]:
            return _build_live_heat_items_from_segments(
                context={
                    "channel": dict(replay_context.channel),
                    "channel_key": replay_context.channel_key,
                    "context_hash": replay_context.context_hash,
                    "cache_key": replay_context.cache_key,
                    "baseline_id": replay_context.baseline_id,
                    "expected_duration_minutes": replay_context.expected_duration_minutes,
                    "cutting_config_snapshot": deepcopy(replay_context.cutting_config_snapshot),
                },
                segments=segments,
                baseline_id=replay_context.baseline_id,
                expected_duration_minutes=int(replay_context.expected_duration_minutes),
                cutting_config=cutting_config,
            )

        async def _after_replace_with_explicit_baselines(
            anchor_time: datetime,
            replay_end_time: datetime,
            _channel_key: str,
            runtime_seed: ReplayRuntimeSeed,
        ) -> None:
            await _rebuild_head_runtime_after_replay_with_context(
                anchor_time,
                replay_end_time,
                replay_context,
                runtime_seed,
            )

        launch_heat_replay_job(
            job_id=job.id,
            replay_context=replay_context,
            cutting_config=cutting_config,
            point_loader=_load_live_heat_inference_power_points,
            metric_curve_loader=_load_runtime_metric_curves,
            build_items_from_segments=_build_replay_items_from_segments,
            threshold_resolver=_infer_live_activity_threshold,
            after_replace=_after_replace_with_explicit_baselines,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    refreshed = await get_heat_replay_job_record(job.id)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="replay_job_launch_failed")
    return _to_heat_replay_job_response(refreshed)


@router.get("/replay-jobs/{job_id}", response_model=HeatReplayJobResponse)
async def get_replay_job(job_id: str) -> HeatReplayJobResponse:
    job = await get_heat_replay_job_record(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="replay_job_not_found")
    return _to_heat_replay_job_response(job)


@router.post("/replay-jobs/{job_id}/cancel", response_model=HeatReplayJobResponse)
async def cancel_replay_job(job_id: str) -> HeatReplayJobResponse:
    job = await cancel_heat_replay_job_record(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="replay_job_not_found")
    return _to_heat_replay_job_response(job)


@router.get("/{heat_id}", response_model=HeatResponse)
async def get_heat(heat_id: str) -> HeatResponse:
    """获取炉次详情。"""
    await _ensure_formal_baseline_mirrors_loaded()
    item = await _get_or_404(heat_id)
    return _to_heat_response(item)


@router.patch("/{heat_id}", response_model=HeatResponse)
async def update_heat(heat_id: str, data: HeatUpdate) -> HeatResponse:
    """更新炉次信息（描述、起止时间）。"""
    item = await _get_or_404(heat_id)
    if str(item.get("record_source") or "") == "sealed_history":
        if data.adjust_subsequent:
            raise HTTPException(
                status_code=400,
                detail="正式历史炉次的联动批量调整尚未实现，请先关闭联动调整。",
            )
        try:
            updated_item = await update_formal_heat_record(
                str(item["id"]),
                description=data.description,
                start_time=data.start_time,
                end_time=data.end_time,
            )
        except ValueError as exc:
            detail = "更新失败"
            if str(exc) == "start_time_after_end_time":
                detail = "开始时间不能晚于结束时间。"
            elif str(exc) == "outside_context_window":
                detail = "调整后的时间超出当前炉次已保存的上下文窗口，需走批量修订流程。"
            raise HTTPException(status_code=400, detail=detail) from exc
        if updated_item is None:
            raise HTTPException(status_code=404, detail="炉次不存在")
        invalidate_compare_runtime_caches(str(item["id"]))
        return _to_heat_response(updated_item)

    item = _ensure_persisted_heat(item)
    canonical_heat_id = str(item["id"])
    original_start = item["start_time"]

    if data.description is not None:
        item["description"] = data.description
    if data.start_time is not None:
        item["start_time"] = data.start_time
    if data.end_time is not None:
        item["end_time"] = data.end_time

    if data.adjust_subsequent and data.start_time is not None:
        delta = data.start_time - original_start
        # 以开始时间顺序调整后续炉次
        current_start = item["start_time"]
        for other in _mutable_heat_store().values():
            if other["id"] == canonical_heat_id:
                continue
            if other["start_time"] > current_start:
                other["start_time"] = other["start_time"] + delta
                other["end_time"] = other["end_time"] + delta

    await persist_runtime_state(*_runtime_heat_sections())
    invalidate_compare_runtime_caches(canonical_heat_id)
    return _to_heat_response(item)


@router.post("/{heat_id}/resume-cutting", response_model=HeatResponse)
async def resume_cutting(heat_id: str, data: HeatResumeCuttingRequest) -> HeatResponse:
    """恢复重大事故后的炉次切割。"""
    item = await _get_or_404(heat_id)
    if str(item.get("record_source") or "") == "sealed_history":
        if data.adjust_subsequent:
            raise HTTPException(
                status_code=400,
                detail="正式历史炉次的联动恢复尚未实现，请先关闭联动恢复。",
            )
        updated_item = await resume_formal_heat_cutting(
            str(item["id"]),
            note=data.note,
        )
        if updated_item is None:
            raise HTTPException(status_code=404, detail="炉次不存在")
        invalidate_compare_runtime_caches(str(item["id"]))
        return _to_heat_response(updated_item)

    item = _ensure_persisted_heat(item)
    canonical_heat_id = str(item["id"])

    item["cut_status"] = "normal"
    item["major_issue"] = False
    item["blocked_by_issue"] = False
    item["cut_reason"] = "manual_resume"
    item["schedule_tag"] = "work"
    item["abnormal_duration_minutes"] = min(item.get("abnormal_duration_minutes") or 0, 4)
    if item["status"] == "pending":
        item["status"] = "normal"

    if data.adjust_subsequent:
        current_start = item["start_time"]
        for other in _mutable_heat_store().values():
            if other["id"] == canonical_heat_id:
                continue
            if other["start_time"] > current_start and other.get("cut_status") == "blocked":
                other["cut_status"] = "normal"
                other["blocked_by_issue"] = False
                other["major_issue"] = False
                other["cut_reason"] = "manual_resume_followup"
                other["schedule_tag"] = "work"
                other["abnormal_duration_minutes"] = 4
                if other["status"] == "pending":
                    other["status"] = "normal"

    await persist_runtime_state(*_runtime_heat_sections())
    invalidate_compare_runtime_caches(canonical_heat_id)
    return _to_heat_response(item)


@router.get("/{heat_id}/cutting-timeline", response_model=CuttingTimelineResponse)
async def get_cutting_timeline(heat_id: str) -> CuttingTimelineResponse:
    """获取炉次切割判定时间轴。"""
    item = await _get_or_404(heat_id)
    canonical_heat_id = str(item["id"])
    config = get_cutting_config()

    start_time: datetime = item["start_time"]
    events: list[CuttingTimelineEvent] = [
        CuttingTimelineEvent(
            timestamp=start_time,
            event_type="stream_in",
            title="实时流入",
            detail="炉次进入切割判定队列",
        ),
        CuttingTimelineEvent(
            timestamp=start_time + timedelta(minutes=1),
            event_type="window_check",
            title="窗口判定",
            detail=(
                f"连续不一致 {item.get('abnormal_duration_minutes') or 0} 分钟，"
                f"阈值 {config.major_issue_duration_minutes} 分钟"
            ),
        ),
        CuttingTimelineEvent(
            timestamp=start_time + timedelta(minutes=2),
            event_type="schedule_check",
            title="班次窗口检查",
            detail=f"当前窗口：{item.get('schedule_tag', 'work')}",
        ),
    ]

    cut_status = item.get("cut_status", "normal")
    if cut_status == "major_issue":
        events.append(
            CuttingTimelineEvent(
                timestamp=start_time + timedelta(minutes=3),
                event_type="major_issue",
                title="触发重大事故",
                detail="连续不一致超过阈值，后续炉次阻断",
            )
        )
    elif cut_status == "blocked":
        events.append(
            CuttingTimelineEvent(
                timestamp=start_time + timedelta(minutes=3),
                event_type="blocked",
                title="切割阻断",
                detail=f"阻断原因：{item.get('cut_reason') or 'unknown'}",
            )
        )
    elif item.get("status") == "abnormal":
        events.append(
            CuttingTimelineEvent(
                timestamp=start_time + timedelta(minutes=3),
                event_type="abnormal",
                title="判定异常",
                detail=f"异常原因：{item.get('cut_reason') or 'unknown'}",
            )
        )
    else:
        events.append(
            CuttingTimelineEvent(
                timestamp=start_time + timedelta(minutes=3),
                event_type="normal",
                title="判定正常",
                detail="切割继续执行",
            )
        )

    return CuttingTimelineResponse(heat_id=canonical_heat_id, events=events)


@router.get("/{heat_id}/curve", response_model=HeatWithCurve)
async def get_heat_curve(heat_id: str) -> HeatWithCurve:
    """获取炉次曲线数据。"""
    await _ensure_formal_baseline_mirrors_loaded()
    item = await _get_or_404(heat_id)
    await _ensure_formal_baseline_mirrors_loaded(
        definition_id=str(item.get("baseline_definition_id") or "") or None,
        baseline_id=_resolve_primary_baseline_id(item),
    )
    if str(item.get("record_source") or "") == "sealed_history":
        return _to_heat_with_curve(item)
    await _hydrate_heat_item(item)
    prepared_item = await _build_heat_response_view(item)
    return _to_heat_with_curve(prepared_item)


@router.get("/{heat_id}/compare", response_model=HeatCompareResponse)
async def get_heat_compare(heat_id: str) -> HeatCompareResponse:
    """获取炉次与基线对比数据。"""
    await _ensure_formal_baseline_mirrors_loaded()
    started_at = perf_counter()
    item = await _get_or_404(heat_id)
    await _ensure_formal_baseline_mirrors_loaded(
        definition_id=str(item.get("baseline_definition_id") or "") or None,
        baseline_id=_resolve_primary_baseline_id(item),
    )
    canonical_heat_id = str(item["id"])
    baseline_id = _resolve_primary_baseline_id(item)
    baseline_ids = _resolve_compare_baseline_ids(item)
    if not baseline_ids:
        log_event(
            "heat_compare_source_error",
            heat_id=canonical_heat_id,
            error="compare_baseline_ids_missing",
        )
        raise HTTPException(status_code=409, detail="compare_baseline_ids_missing")
    cache_key = _build_heat_compare_cache_key(item, baseline_ids)
    cached_response = _get_cached_heat_compare(cache_key)
    if cached_response is not None:
        log_event(
            "api_heat_compare",
            heat_id=canonical_heat_id,
            baseline_count=len(baseline_ids),
            cache_hit=True,
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
        )
        return cached_response

    compare_display_start, compare_display_end = _resolve_compare_display_window(
        item["start_time"],
        item["end_time"],
        context_start_time=item.get("context_start_time"),
        context_end_time=item.get("context_end_time"),
    )
    compare_channels = _collect_compare_metric_channels(baseline_ids)
    is_sealed_history = str(item.get("record_source") or "") == "sealed_history"
    is_runtime_compare = _is_runtime_compare_source(item)
    if is_runtime_compare:
        hydrated_baselines = {
            baseline_id: dict(baseline_item)
            for baseline_id in baseline_ids
            if (baseline_item := _BASELINE_STORE.get(baseline_id)) is not None
        }
        runtime_current_curves = _resolve_runtime_current_curves(item)
        shared_current_curves = {}
        display_current_curves = {}
        live_curves = _clip_curves_to_time_window(
            runtime_current_curves,
            start_time=item["start_time"],
            end_time=item["end_time"],
        )
        display_live_curves = dict(runtime_current_curves)
        runtime_baseline_snapshots = _resolve_runtime_baseline_curve_snapshots(item)
        if baseline_id:
            baseline_power_snapshot = runtime_baseline_snapshots.get((baseline_id, "power"))
            baseline_voltage_snapshot = runtime_baseline_snapshots.get((baseline_id, "voltage"))
            if baseline_power_snapshot is not None:
                item["baseline_power_curve"] = _rebase_curve_points_to_window(
                    baseline_power_snapshot.points,
                    target_start_time=item["start_time"],
                    target_end_time=item["end_time"],
                )
                item["baseline_curve_source"] = baseline_power_snapshot.curve_source
            if baseline_voltage_snapshot is not None:
                item["baseline_voltage_curve"] = _rebase_curve_points_to_window(
                    baseline_voltage_snapshot.points,
                    target_start_time=item["start_time"],
                    target_end_time=item["end_time"],
                )
                if not item.get("baseline_curve_source"):
                    item["baseline_curve_source"] = baseline_voltage_snapshot.curve_source
    elif is_sealed_history:
        hydrated_baselines = await _hydrate_compare_baselines(baseline_ids)
        shared_current_curves = _resolve_formal_current_curves(item)
        display_current_curves = dict(shared_current_curves)
        historical_context_curves = {
            "power": _coerce_curve_points(item.get("power_curve")),
            "voltage": _coerce_curve_points(item.get("voltage_curve")),
        }
        live_curves = _clip_curves_to_time_window(
            historical_context_curves,
            start_time=item["start_time"],
            end_time=item["end_time"],
        )
        display_live_curves = dict(historical_context_curves)
    else:
        hydrated_baselines, shared_current_curves, display_current_curves = await asyncio.gather(
            _hydrate_compare_baselines(baseline_ids),
            _load_channel_curves_from_edc(
                channels=compare_channels,
                start_time=item["start_time"],
                end_time=item["end_time"],
            ),
            _load_channel_curves_from_edc(
                channels=compare_channels,
                start_time=compare_display_start,
                end_time=compare_display_end,
            ),
        )
        live_curves = _resolve_heat_curves_from_shared_channels(item, shared_current_curves)
        display_live_curves = _resolve_heat_curves_from_shared_channels(
            item, display_current_curves
        )

    if live_curves.get("power"):
        item["power_curve"] = _coerce_curve_points(live_curves["power"])
    if live_curves.get("voltage"):
        item["voltage_curve"] = _coerce_curve_points(live_curves["voltage"])
    if live_curves:
        if is_runtime_compare:
            item["current_curve_source"] = "runtime_metric_series"
        elif is_sealed_history:
            item["current_curve_source"] = str(item.get("current_curve_source") or "formal_db")
        else:
            item["current_curve_source"] = "live_edc"

    if baseline_id:
        baseline_item = hydrated_baselines.get(baseline_id) or _BASELINE_STORE.get(baseline_id)
        if baseline_item and not is_runtime_compare:
            baseline_power_curve = _coerce_curve_points(baseline_item.get("power_curve"))
            baseline_voltage_curve = _coerce_curve_points(baseline_item.get("voltage_curve"))
            if baseline_power_curve:
                item["baseline_power_curve"] = baseline_power_curve
            if baseline_voltage_curve:
                item["baseline_voltage_curve"] = baseline_voltage_curve
            item["baseline_curve_source"] = str(baseline_item.get("curve_source") or "none")

    response_item = _build_heat_compare_view(item)
    heat = _to_heat_with_curve(response_item)
    binding_map = _binding_by_baseline_id(item)
    baseline_compares: list[BaselineCompareItem] = []
    try:
        for baseline_id in baseline_ids:
            if is_runtime_compare:
                metric_curves = _build_runtime_metric_curve_series(
                    item=item,
                    baseline_id=baseline_id,
                )
            else:
                metric_curves = await _build_metric_curve_series(
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                    minutes=46,
                    baseline_id=baseline_id,
                    power_curve=display_live_curves.get("power")
                    or _coerce_curve_points(response_item.get("power_curve")),
                    voltage_curve=display_live_curves.get("voltage")
                    or _coerce_curve_points(response_item.get("voltage_curve")),
                    current_curves_by_channel=display_current_curves,
                    hydrated_baseline_item=hydrated_baselines.get(baseline_id),
                    hydrate_baseline=False,
                )
            binding_summary = binding_map.get(baseline_id)
            baseline_item = hydrated_baselines.get(baseline_id) or _BASELINE_STORE.get(baseline_id)
            baseline_name = (
                str(baseline_item.get("name"))
                if baseline_item and baseline_item.get("name")
                else baseline_id
            )
            baseline_curve_points = _select_metric_curve(metric_curves, "power")
            baseline_voltage_curve_points = _select_metric_curve(metric_curves, "voltage")

            tolerance = float(
                (binding_summary or {}).get("tolerance_percent")
                or (baseline_item or {}).get("tolerance_percent")
                or 15.0
            )
            if (
                binding_summary is not None
                and str(binding_summary.get("analysis_status") or "") == "ready"
            ):
                deviation_ranges = _binding_deviation_ranges(binding_summary)
                deviation_score = binding_summary.get("deviation_score")
                avg_deviation_score = binding_summary.get("avg_deviation_score")
            else:
                deviation_ranges = []
                deviation_score = None
                avg_deviation_score = None

            baseline_compares.append(
                BaselineCompareItem(
                    baseline=BaselineWithCurveSimple(
                        id=baseline_id,
                        name=baseline_name,
                        power_curve=baseline_curve_points,
                        voltage_curve=baseline_voltage_curve_points,
                        tolerance_percent=tolerance,
                    ),
                    metric_curves=metric_curves,
                    analysis_status=(
                        str(binding_summary.get("analysis_status"))
                        if binding_summary is not None
                        and binding_summary.get("analysis_status") is not None
                        else None
                    ),
                    analysis_reason=(
                        str(binding_summary.get("analysis_reason"))
                        if binding_summary is not None
                        and binding_summary.get("analysis_reason") is not None
                        else None
                    ),
                    analysis_message=(
                        str(binding_summary.get("analysis_message"))
                        if binding_summary is not None
                        and binding_summary.get("analysis_message") is not None
                        else None
                    ),
                    deviation_ranges=deviation_ranges,
                    deviation_score=deviation_score,
                    avg_deviation_score=avg_deviation_score,
                )
            )
    except ValueError as exc:
        log_event(
            "heat_compare_source_error",
            heat_id=canonical_heat_id,
            error=str(exc),
            baseline_ids=baseline_ids,
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    baseline = baseline_compares[0].baseline if baseline_compares else None
    deviation_ranges = baseline_compares[0].deviation_ranges if baseline_compares else []
    deviation_score = baseline_compares[0].deviation_score if baseline_compares else None
    avg_deviation_score = baseline_compares[0].avg_deviation_score if baseline_compares else None

    response = HeatCompareResponse(
        heat=heat,
        baseline=baseline,
        baselines=baseline_compares,
        analysis_status=baseline_compares[0].analysis_status if baseline_compares else None,
        analysis_reason=baseline_compares[0].analysis_reason if baseline_compares else None,
        analysis_message=baseline_compares[0].analysis_message if baseline_compares else None,
        deviation_ranges=deviation_ranges,
        deviation_score=deviation_score,
        avg_deviation_score=avg_deviation_score,
    )
    _set_cached_heat_compare(cache_key=cache_key, heat_id=canonical_heat_id, response=response)
    log_event(
        "api_heat_compare",
        heat_id=canonical_heat_id,
        baseline_count=len(baseline_ids),
        current_curve_points=len(response.heat.power_curve),
        cache_hit=False,
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
    )
    return response
