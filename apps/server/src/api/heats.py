"""炉次 API 路由。"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ..mock_dataset import ensure_mock_dataset_enabled, is_mock_dataset_enabled
from ..runtime_state import persist_runtime_state
from ..schemas import (
    BaselineCompareItem,
    CurvePoint,
    CuttingTimelineEvent,
    CuttingTimelineResponse,
    DeviationRange,
    HeatAnalyzeRequest,
    HeatAnalyzeResponse,
    HeatCompareResponse,
    HeatListResponse,
    HeatResponse,
    HeatResumeCuttingRequest,
    HeatUpdate,
    HeatWithCurve,
    MetricCompareSeries,
)
from ..schemas.heat import BaselineWithCurveSimple
from ..services import DeviationService, EDCClient, EDCClientError
from .baseline_definitions import _DEFINITION_STORE
from .baselines import _BASELINE_STORE, _resolve_active_baseline_item
from .settings import _HOST_CHANNEL_STORE, _SETTINGS_STORE, get_edc_connection_config

router = APIRouter(prefix="/heats", tags=["Heats"])
deviation_service = DeviationService()

_LIVE_HEAT_LOOKBACK_HOURS = 72
_LIVE_HEAT_CACHE_TTL_SECONDS = 30
_LIVE_HEAT_GAP_MINUTES = 3
_HEAT_COMPARE_CACHE_TTL_SECONDS = 20
_LIVE_HEAT_CACHE: dict[str, Any] = {
    "expires_at": None,
    "items": {},
}
_HEAT_COMPARE_CACHE: dict[str, Any] = {
    "entries": {},
}


def _as_cache_token(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


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

    return "|".join(
        [
            _as_cache_token(item.get("id")),
            _as_cache_token(item.get("start_time")),
            _as_cache_token(item.get("end_time")),
            _as_cache_token(item.get("status")),
            _as_cache_token(item.get("cut_status")),
            _as_cache_token(item.get("baseline_id")),
            ",".join(baseline_tokens),
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
        or expires_at <= datetime.now()
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
        "expires_at": datetime.now() + timedelta(seconds=_HEAT_COMPARE_CACHE_TTL_SECONDS),
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


def _get_cutting_config() -> dict[str, Any]:
    """读取切割配置。"""
    tolerance = float(_SETTINGS_STORE.get("time_tolerance_percent", {}).get("value") or 10.0)
    major_issue_minutes = int(
        _SETTINGS_STORE.get("major_issue_duration_minutes", {}).get("value") or 8
    )
    work_start = str(_SETTINGS_STORE.get("work_start_time", {}).get("value") or "08:00")
    work_end = str(_SETTINGS_STORE.get("work_end_time", {}).get("value") or "18:00")
    break_raw = str(_SETTINGS_STORE.get("break_periods", {}).get("value") or "12:00-13:00")
    break_periods = [item.strip() for item in break_raw.split(",") if item.strip()]
    return {
        "tolerance": tolerance,
        "major_issue_minutes": major_issue_minutes,
        "work_start": work_start,
        "work_end": work_end,
        "break_periods": break_periods,
    }


def _is_live_heat_inference_enabled() -> bool:
    raw_value = _SETTINGS_STORE.get("live_heat_inference_enabled", {}).get("value")
    if raw_value is None:
        return True
    return str(raw_value).strip().lower() not in {"0", "false", "off", "no"}


def _to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _schedule_tag_of(start_time: datetime, config: dict[str, Any]) -> str:
    """根据时间判断班次标签。"""
    current = start_time.hour * 60 + start_time.minute
    work_start = _to_minutes(config["work_start"])
    work_end = _to_minutes(config["work_end"])
    if current < work_start or current > work_end:
        return "off_shift"

    for period in config["break_periods"]:
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
        ts = int((start + timedelta(minutes=idx)).timestamp() * 1000)
        value = base + amp * ((idx + int(phase)) % 10) / 10
        points.append(CurvePoint(timestamp=ts, value=round(value, 3)))
    return points


def _coerce_curve_points(points: list[CurvePoint] | list[dict[str, Any]] | None) -> list[CurvePoint]:
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


def _resolve_host_channel(channel_id: str | None) -> dict[str, str] | None:
    if not channel_id:
        return None
    return next((item for item in _HOST_CHANNEL_STORE if item["id"] == channel_id), None)


def _format_host_channel_label(channel: dict[str, str] | None) -> str | None:
    if not channel:
        return None
    return f'{channel["device_name"]} / {channel["channel_name"]} / {channel["unit"] or "--"}'


def _infer_metric_key(metric: dict[str, Any], index: int) -> str:
    name = str(metric.get("name") or "").lower()
    unit = str(metric.get("unit") or "")
    if "功率" in name or "power" in name or unit == "kW":
        return "power"
    if "电压" in name or "電壓" in name or "voltage" in name or unit == "V":
        return "voltage"
    if "温" in name or "溫" in name or "temperature" in name or unit in {"°C", "℃"}:
        return "temperature"
    if "压" in name or "壓" in name or "pressure" in name or unit == "MPa":
        return "pressure"
    return f"metric_{index + 1}"


def _build_generated_curve(
    *,
    start_time: datetime,
    minutes: int,
    metric_key: str,
    baseline_index: int,
    variant: Literal["baseline", "current"],
    offset: float = 0.0,
) -> list[CurvePoint]:
    if metric_key == "power":
        base = 435 + baseline_index * 5 + offset
        amp = 24 + baseline_index * 3
        phase = 2.0 + baseline_index
    elif metric_key == "voltage":
        base = 380 + baseline_index * 2 + offset
        amp = 5 + baseline_index
        phase = 1.0 + baseline_index
    elif metric_key == "temperature":
        base = (1460 if variant == "baseline" else 1452) + baseline_index * 10 + offset
        amp = 18 + baseline_index * 2 if variant == "baseline" else 22 + baseline_index * 3
        phase = 2.5 + baseline_index if variant == "baseline" else 2.1 + baseline_index
    elif metric_key == "pressure":
        base = (0.82 if variant == "baseline" else 0.79) + offset
        amp = 0.12 if variant == "baseline" else 0.18
        phase = 1.6 if variant == "baseline" else 1.2
    else:
        base = (120 if variant == "baseline" else 112) + baseline_index * 7 + offset
        amp = 14 + baseline_index * 2
        phase = 1.0 + baseline_index
    return _curve_points(start_time, minutes, base, amp, phase)


def _resolve_primary_baseline_id(item: dict[str, Any]) -> str | None:
    active_baseline = _resolve_active_baseline_item()
    if active_baseline and active_baseline.get("id"):
        return str(active_baseline["id"])

    baseline_id = item.get("baseline_id")
    if isinstance(baseline_id, str) and baseline_id:
        return baseline_id

    baseline_ids = item.get("baseline_ids")
    if isinstance(baseline_ids, list) and baseline_ids:
        first = baseline_ids[0]
        if isinstance(first, str) and first:
            return first
    return None


def _percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    index = min(max(int((len(ordered) - 1) * ratio), 0), len(ordered) - 1)
    return float(ordered[index])


def _infer_live_activity_threshold(points: list[CurvePoint]) -> float | None:
    if len(points) < 10:
        return None

    values = [float(point.value) for point in points]
    median = _percentile(values, 0.5)
    p75 = _percentile(values, 0.75)
    p90 = _percentile(values, 0.9)
    threshold = max(median + (p90 - median) * 0.35, p75 * 0.95)
    return round(threshold, 3)


def _slice_curve_points(
    points: list[CurvePoint], start_ts: int, end_ts: int
) -> list[CurvePoint]:
    return [point for point in points if start_ts <= point.timestamp <= end_ts]


def _split_live_segment(
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
        window_end = end_ts if index == split_count - 1 else start_ts + int(
            total_span * (index + 1) / split_count
        )
        window_points = _slice_curve_points(points, window_start, window_end)
        if not window_points:
            continue
        window_duration = (window_points[-1].timestamp - window_points[0].timestamp) / 60000
        if window_duration >= min_duration_minutes:
            slices.append(window_points)

    return slices or [points]


def _build_live_heat_item(
    *,
    index: int,
    baseline_id: str | None,
    power_curve: list[CurvePoint],
    expected_duration_minutes: int,
) -> dict[str, Any]:
    start_time = datetime.fromtimestamp(power_curve[0].timestamp / 1000)
    end_time = datetime.fromtimestamp(power_curve[-1].timestamp / 1000)
    duration_minutes = max((end_time - start_time).total_seconds() / 60, 1)
    schedule_tag = _schedule_tag_of(start_time, _get_cutting_config())
    duration_ratio = duration_minutes / max(expected_duration_minutes, 1)
    status = "abnormal" if duration_ratio < 0.6 or duration_ratio > 1.5 else "normal"
    heat_id = f"live-heat-{int(power_curve[0].timestamp)}-{int(power_curve[-1].timestamp)}"

    return {
        "id": heat_id,
        "heat_no": f"H{start_time.strftime('%Y%m%d')}-{start_time.strftime('%H%M')}",
        "description": None,
        "start_time": start_time,
        "end_time": end_time,
        "baseline_id": baseline_id,
        "baseline_ids": [baseline_id] if baseline_id else [],
        "deviation_percent": None,
        "avg_deviation_percent": None,
        "time_offset_percent": None,
        "mismatch_duration_minutes": None,
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
    }


def _infer_live_heat_items(
    *,
    points: list[CurvePoint],
    baseline_id: str | None,
    expected_duration_minutes: int,
) -> dict[str, dict[str, Any]]:
    threshold = _infer_live_activity_threshold(points)
    if threshold is None:
        return {}

    gap_ms = _LIVE_HEAT_GAP_MINUTES * 60_000
    min_duration_minutes = max(int(round(expected_duration_minutes * 0.45)), 15)
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

    inferred: list[dict[str, Any]] = []
    for segment in grouped_segments:
        duration_minutes = (segment[-1].timestamp - segment[0].timestamp) / 60000
        if duration_minutes < min_duration_minutes:
            continue
        for split_segment in _split_live_segment(
            segment,
            expected_duration_minutes=expected_duration_minutes,
            min_duration_minutes=min_duration_minutes,
        ):
            split_duration = (split_segment[-1].timestamp - split_segment[0].timestamp) / 60000
            if split_duration < min_duration_minutes:
                continue
            inferred.append(
                _build_live_heat_item(
                    index=len(inferred) + 1,
                    baseline_id=baseline_id,
                    power_curve=split_segment,
                    expected_duration_minutes=expected_duration_minutes,
                )
            )

    inferred.sort(key=lambda item: item["start_time"], reverse=True)
    return {str(item["id"]): item for item in inferred}


def _resolve_compare_baseline_ids(item: dict[str, Any]) -> list[str]:
    ordered_ids: list[str] = []
    primary_baseline_id = _resolve_primary_baseline_id(item)
    if primary_baseline_id:
        ordered_ids.append(primary_baseline_id)

    published = sorted(
        [
            baseline
            for baseline in _BASELINE_STORE.values()
            if baseline["status"] == "published" and baseline["id"] != primary_baseline_id
        ],
        key=lambda baseline: baseline["published_at"] or baseline["updated_at"],
        reverse=True,
    )
    drafts = sorted(
        [
            baseline
            for baseline in _BASELINE_STORE.values()
            if baseline["status"] == "draft" and baseline["id"] != primary_baseline_id
        ],
        key=lambda baseline: baseline["updated_at"],
        reverse=True,
    )

    ordered_ids.extend(str(baseline["id"]) for baseline in published)
    ordered_ids.extend(str(baseline["id"]) for baseline in drafts)
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


def _resolve_live_heat_inference_context() -> tuple[dict[str, str], str | None, int] | None:
    candidates: list[tuple[str | None, dict[str, Any]]] = []
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
        metrics = list(definition.get("metrics", []))
        power_metric = next(
            (
                metric
                for index, metric in enumerate(metrics)
                if _infer_metric_key(metric, index) == "power"
            ),
            None,
        )
        channel = _resolve_host_channel(power_metric.get("edc_channel_id")) if power_metric else None
        if not channel:
            continue
        expected_duration = int(definition.get("expected_duration_minutes") or 45)
        return channel, baseline_id, expected_duration

    fallback_channel = next((item for item in _HOST_CHANNEL_STORE if item.get("unit") == "kW"), None)
    if not fallback_channel:
        return None
    return fallback_channel, None, 45


async def _load_live_heat_inference_power_points(
    channel: dict[str, str],
) -> list[CurvePoint]:
    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return []

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=_LIVE_HEAT_LOOKBACK_HOURS)
    try:
        async with EDCClient(**config) as client:
            return await client.get_local_datas(
                suid=channel["suid"],
                cuid=channel["cuid"],
                start_time=start_time,
                end_time=end_time,
            )
    except EDCClientError:
        return []


async def _get_live_inferred_heat_store() -> dict[str, dict[str, Any]]:
    if not _is_live_heat_inference_enabled():
        return {}

    expires_at = _LIVE_HEAT_CACHE.get("expires_at")
    cached_items = _LIVE_HEAT_CACHE.get("items")
    if (
        isinstance(expires_at, datetime)
        and expires_at > datetime.now()
        and isinstance(cached_items, dict)
    ):
        return cached_items

    context = _resolve_live_heat_inference_context()
    if not context:
        _LIVE_HEAT_CACHE["items"] = {}
        _LIVE_HEAT_CACHE["expires_at"] = datetime.now() + timedelta(
            seconds=_LIVE_HEAT_CACHE_TTL_SECONDS
        )
        return {}

    channel, baseline_id, expected_duration_minutes = context
    points = await _load_live_heat_inference_power_points(channel)
    inferred_items = _infer_live_heat_items(
        points=points,
        baseline_id=baseline_id,
        expected_duration_minutes=expected_duration_minutes,
    )
    _LIVE_HEAT_CACHE["items"] = inferred_items
    _LIVE_HEAT_CACHE["expires_at"] = datetime.now() + timedelta(
        seconds=_LIVE_HEAT_CACHE_TTL_SECONDS
    )
    return inferred_items


async def resolve_heat_record(heat_id: str) -> dict[str, Any] | None:
    if is_mock_dataset_enabled():
        return _MOCK_HEAT_STREAM_STORE.get(heat_id)

    stored_item = _HEAT_STORE.get(heat_id)
    if stored_item and _is_real_heat_record(stored_item):
        return stored_item

    live_items = await _get_live_inferred_heat_store()
    return live_items.get(heat_id)


async def resolve_heat_time_window(heat_id: str) -> tuple[datetime, datetime] | None:
    item = await resolve_heat_record(heat_id)
    if not item:
        return None
    return item["start_time"], item["end_time"]


async def _list_heat_store() -> dict[str, dict[str, Any]]:
    if is_mock_dataset_enabled():
        return dict(_MOCK_HEAT_STREAM_STORE)

    live_items = await _get_live_inferred_heat_store()
    if not live_items:
        return {}

    merged = dict(live_items)
    for heat_id, item in _HEAT_STORE.items():
        if not _is_real_heat_record(item):
            continue
        if heat_id in merged:
            merged[heat_id] = item
    return merged


async def _load_heat_curves_from_edc(item: dict[str, Any]) -> dict[str, list[CurvePoint]] | None:
    """按炉次主基线绑定读取真实功率/电压曲线。"""
    _baseline_id, metrics = _resolve_definition_metrics(item)
    if not metrics:
        return None

    power_metric = next(
        (metric for index, metric in enumerate(metrics) if _infer_metric_key(metric, index) == "power"),
        None,
    )
    voltage_metric = next(
        (metric for index, metric in enumerate(metrics) if _infer_metric_key(metric, index) == "voltage"),
        None,
    )
    power_channel = _resolve_host_channel(power_metric.get("edc_channel_id")) if power_metric else None
    voltage_channel = _resolve_host_channel(voltage_metric.get("edc_channel_id")) if voltage_metric else None
    if not power_channel and not voltage_channel:
        return None

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return None

    start_time = item["start_time"]
    end_time = item["end_time"]

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

        await _hydrate_baseline_item(baseline_item)
        baseline_power_curve = _coerce_curve_points(baseline_item.get("power_curve"))
        baseline_voltage_curve = _coerce_curve_points(baseline_item.get("voltage_curve"))
        if baseline_power_curve:
            item["baseline_power_curve"] = baseline_power_curve
        if baseline_voltage_curve:
            item["baseline_voltage_curve"] = baseline_voltage_curve

    return item


def _build_heat_list_view(item: dict[str, Any]) -> dict[str, Any]:
    """列表接口只返回轻量字段，不在此处触发基线 hydrate 或实时取数。"""
    response_item = dict(item)
    baseline_id = _resolve_primary_baseline_id(item)
    response_item["baseline_id"] = baseline_id

    baseline_item = _BASELINE_STORE.get(baseline_id) if baseline_id else None
    if baseline_item:
        response_item["baseline_curve_source"] = str(
            baseline_item.get("curve_source") or item.get("baseline_curve_source") or "none"
        )

    if response_item.get("status") == "pending":
        return response_item

    baseline_power_curve = _coerce_curve_points(
        (baseline_item or {}).get("power_curve") or response_item.get("baseline_power_curve")
    )
    current_power_curve = _coerce_curve_points(response_item.get("power_curve"))
    if not baseline_power_curve or not current_power_curve:
        return response_item

    tolerance = float((baseline_item or {}).get("tolerance_percent") or 15.0)
    result = deviation_service.calculate_deviation(
        baseline_curve=[
            (float(point.timestamp), float(point.value)) for point in baseline_power_curve
        ],
        current_curve=[
            (float(point.timestamp), float(point.value)) for point in current_power_curve
        ],
        tolerance=tolerance,
    )
    response_item["deviation_percent"] = result["max_deviation"]
    response_item["avg_deviation_percent"] = result["avg_deviation"]
    return response_item


async def _build_heat_response_view(item: dict[str, Any]) -> dict[str, Any]:
    """按默认黄金基线整理炉次响应视图。"""
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

    await _hydrate_baseline_item(baseline_item)

    baseline_power_curve = _coerce_curve_points(baseline_item.get("power_curve"))
    baseline_voltage_curve = _coerce_curve_points(baseline_item.get("voltage_curve"))
    current_power_curve = _coerce_curve_points(response_item.get("power_curve"))

    if baseline_power_curve:
        response_item["baseline_power_curve"] = baseline_power_curve
    if baseline_voltage_curve:
        response_item["baseline_voltage_curve"] = baseline_voltage_curve
    response_item["baseline_curve_source"] = str(baseline_item.get("curve_source") or "none")

    if item.get("status") == "pending" or not baseline_power_curve or not current_power_curve:
        return response_item

    result = deviation_service.calculate_deviation(
        baseline_curve=[
            (float(point.timestamp), float(point.value)) for point in baseline_power_curve
        ],
        current_curve=[
            (float(point.timestamp), float(point.value)) for point in current_power_curve
        ],
        tolerance=float(baseline_item.get("tolerance_percent") or 15.0),
    )
    response_item["deviation_percent"] = result["max_deviation"]
    response_item["avg_deviation_percent"] = result["avg_deviation"]
    return response_item


def _build_heat_compare_view(item: dict[str, Any]) -> dict[str, Any]:
    """compare 路径复用已 hydrate 的主基线，不重复触发基线取数。"""
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

    baseline_power_curve = _coerce_curve_points(baseline_item.get("power_curve"))
    baseline_voltage_curve = _coerce_curve_points(baseline_item.get("voltage_curve"))
    current_power_curve = _coerce_curve_points(response_item.get("power_curve"))

    if baseline_power_curve:
        response_item["baseline_power_curve"] = baseline_power_curve
    if baseline_voltage_curve:
        response_item["baseline_voltage_curve"] = baseline_voltage_curve
    response_item["baseline_curve_source"] = str(baseline_item.get("curve_source") or "none")

    if item.get("status") == "pending" or not baseline_power_curve or not current_power_curve:
        return response_item

    result = deviation_service.calculate_deviation(
        baseline_curve=[
            (float(point.timestamp), float(point.value)) for point in baseline_power_curve
        ],
        current_curve=[
            (float(point.timestamp), float(point.value)) for point in current_power_curve
        ],
        tolerance=float(baseline_item.get("tolerance_percent") or 15.0),
    )
    response_item["deviation_percent"] = result["max_deviation"]
    response_item["avg_deviation_percent"] = result["avg_deviation"]
    return response_item


def _resolve_baseline_metric_curve(
    baseline_id: str,
    metric_id: str,
) -> list[CurvePoint]:
    baseline_item = _BASELINE_STORE.get(baseline_id)
    if not baseline_item:
        return []

    curves_data = baseline_item.get("curves_data")
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


def _build_current_curve_for_metric(
    *,
    start_time: datetime,
    minutes: int,
    metric_key: str,
    metric_index: int,
    baseline_index: int,
    power_curve: list[CurvePoint],
    voltage_curve: list[CurvePoint],
) -> list[CurvePoint]:
    if metric_key == "power":
        return power_curve
    if metric_key == "voltage":
        return voltage_curve
    return _build_generated_curve(
        start_time=start_time,
        minutes=minutes,
        metric_key=metric_key,
        baseline_index=baseline_index,
        variant="current",
        offset=metric_index * 1.5,
    )


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


async def _load_channel_curves_from_edc(
    *,
    channels: list[dict[str, str]],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]]:
    """按唯一通道批量读取当前曲线，供 compare 路径多个基线共享。"""
    unique_channels: dict[str, dict[str, str]] = {}
    for channel in channels:
        cache_key = _channel_curve_cache_key(channel)
        if cache_key:
            unique_channels[cache_key] = channel

    if not unique_channels:
        return {}

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return {}

    try:
        async with EDCClient(**config) as client:
            tasks = {
                cache_key: asyncio.create_task(
                    client.get_local_datas(
                        suid=channel["suid"],
                        cuid=channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
                for cache_key, channel in unique_channels.items()
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    except EDCClientError:
        return {}

    curves: dict[str, list[CurvePoint]] = {}
    for cache_key, result in zip(tasks.keys(), results, strict=False):
        if isinstance(result, Exception) or not result:
            continue
        curves[cache_key] = result
    return curves


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


async def _build_metric_curve_series(
    *,
    start_time: datetime,
    end_time: datetime,
    minutes: int,
    baseline_id: str,
    power_curve: list[CurvePoint],
    voltage_curve: list[CurvePoint],
    current_curves_by_channel: dict[str, list[CurvePoint]] | None = None,
    hydrate_baseline: bool = True,
) -> list[MetricCompareSeries]:
    """按基线定义动态构造炉次详情多指标对比曲线。"""
    baseline_item = _BASELINE_STORE.get(baseline_id)
    definition = (
        _DEFINITION_STORE.get(str(baseline_item.get("definition_id")))
        if baseline_item
        else None
    )
    metrics = list(definition.get("metrics", [])) if definition else []

    if not metrics:
        metrics = [
            {"id": "metric-power", "name": "功率", "unit": "kW", "color": "#409EFF"},
            {"id": "metric-voltage", "name": "电压", "unit": "V", "color": "#67C23A"},
            {"id": "metric-temperature", "name": "炉温", "unit": "°C", "color": "#E6A23C"},
        ]
        if baseline_id == "baseline-002":
            metrics.append(
                {"id": "metric-pressure", "name": "炉压", "unit": "MPa", "color": "#F56C6C"}
            )

    real_current_curves = (
        {}
        if current_curves_by_channel is not None
        else await _load_metric_current_curves_from_edc(
            metrics=metrics,
            start_time=start_time,
            end_time=end_time,
        )
    )
    baseline_item = _BASELINE_STORE.get(baseline_id)
    if baseline_item and hydrate_baseline:
        from .baselines import _hydrate_baseline_item

        await _hydrate_baseline_item(baseline_item)

    series: list[MetricCompareSeries] = []
    for index, metric in enumerate(metrics):
        metric_key = _infer_metric_key(metric, index)
        host_channel = _resolve_metric_channel(metric)
        metric_id = str(metric.get("id") or "")
        baseline_curve = _resolve_baseline_metric_curve(baseline_id, metric_id)
        current_metric_curve = (
            current_curves_by_channel.get(_channel_curve_cache_key(host_channel) or "", [])
            if current_curves_by_channel is not None
            else real_current_curves.get(metric_id)
        )
        if current_metric_curve is None:
            current_metric_curve = []
        series.append(
            MetricCompareSeries(
                metric_key=metric_key,
                metric_name=str(metric.get("name") or f"指标{index + 1}"),
                unit=str(metric.get("unit") or "--"),
                color=str(metric.get("color") or "#94a3b8"),
                edc_channel_id=metric.get("edc_channel_id"),
                source_channel_name=host_channel["channel_name"] if host_channel else None,
                source_channel_label=_format_host_channel_label(host_channel),
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


async def _hydrate_compare_baselines(baseline_ids: list[str]) -> None:
    from .baselines import _hydrate_baseline_item

    await asyncio.gather(
        *(
            _hydrate_baseline_item(baseline_item)
            for baseline_id in baseline_ids
            if (baseline_item := _BASELINE_STORE.get(baseline_id)) is not None
        )
    )


def _ensure_deviation_ranges(
    item: dict[str, Any], deviation_ranges: list[DeviationRange]
) -> list[DeviationRange]:
    """异常炉次至少返回一段可展示的异常区间。"""
    if deviation_ranges or item.get("status") != "abnormal":
        return deviation_ranges

    power_curve = item["power_curve"]
    mid_index = max(len(power_curve) // 2, 1)
    start_point = power_curve[max(mid_index - 5, 0)]
    end_point = power_curve[min(mid_index + 4, len(power_curve) - 1)]
    return [
        DeviationRange(
            start=int(start_point.timestamp),
            end=int(end_point.timestamp),
            deviation=round(float(item.get("deviation_percent") or 12.0), 2),
        )
    ]


def _select_metric_curve(
    metric_curves: list[MetricCompareSeries], metric_key: str
) -> list[CurvePoint]:
    matched = next((item for item in metric_curves if item.metric_key == metric_key), None)
    if matched:
        return matched.baseline_curve
    fallback = metric_curves[0] if metric_curves else None
    return fallback.baseline_curve if fallback else []


def _seed_heats() -> dict[str, dict[str, Any]]:
    now = datetime.now().replace(second=0, microsecond=0)
    config = _get_cutting_config()
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
        time_offset_percent = round((idx % 7) * 1.6, 2)
        cut_reason: str | None = None
        cut_status = "normal"
        major_issue = False
        blocked_by_issue = False

        if group == 1:
            status = "abnormal" if idx % 6 == 0 else "normal"
            mismatch_minutes = 4 + (idx % 4)
            time_offset_percent = round((idx % 5) * 1.4, 2)
        else:
            mismatch_minutes = 6 + (idx % 7)
            if idx == 34:
                mismatch_minutes = max(config["major_issue_minutes"] + 2, mismatch_minutes)

        if schedule_tag in {"break", "off_shift"}:
            cut_status = "blocked"
            blocked_by_issue = True
            status = "pending"
            cut_reason = "schedule_window"
            time_offset_percent = None
        elif major_issue_triggered:
            cut_status = "blocked"
            blocked_by_issue = True
            status = "pending"
            cut_reason = "major_issue_lock"
            time_offset_percent = None
        elif mismatch_minutes >= config["major_issue_minutes"]:
            cut_status = "major_issue"
            major_issue = True
            status = "abnormal"
            cut_reason = "continuous_mismatch"
            major_issue_triggered = True
        elif time_offset_percent > config["tolerance"]:
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
        seeded[heat_id] = {
            "id": heat_id,
            "heat_no": f"H{now.strftime('%Y%m%d')}-{idx + 1:03d}",
            "description": None,
            "start_time": start_time,
            "end_time": end_time,
            "baseline_id": "baseline-001" if status != "pending" else None,
            "baseline_ids": ["baseline-001", "baseline-002"] if status != "pending" else [],
            "deviation_percent": max_dev,
            "avg_deviation_percent": avg_dev,
            "time_offset_percent": time_offset_percent,
            "mismatch_duration_minutes": mismatch_minutes,
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
    return str(item.get("record_source") or "").strip().lower() in {"live_inferred", "live_edc"}


_HEAT_STORE: dict[str, dict[str, Any]] = {}
_MOCK_HEAT_STREAM_STORE: dict[str, dict[str, Any]] = _seed_mock_stream_heats()
_NEXT_MOCK_HEAT_INDEX = len(_MOCK_HEAT_STREAM_STORE) + 1


def _to_heat_response(item: dict[str, Any]) -> HeatResponse:
    return HeatResponse(
        id=item["id"],
        heat_no=item["heat_no"],
        description=item.get("description"),
        start_time=item["start_time"],
        end_time=item["end_time"],
        baseline_id=item["baseline_id"],
        deviation_percent=item["deviation_percent"],
        avg_deviation_percent=item["avg_deviation_percent"],
        time_offset_percent=item.get("time_offset_percent"),
        mismatch_duration_minutes=item.get("mismatch_duration_minutes"),
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
    return ("heats",)


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

    config = _get_cutting_config()
    latest = _latest_heat()
    start_time = (
        latest["start_time"] + timedelta(minutes=50)
        if latest
        else datetime.now().replace(second=0, microsecond=0)
    )
    end_time = start_time + timedelta(minutes=45)

    schedule_tag = _schedule_tag_of(start_time, config)
    mismatch_minutes = 3 + (_NEXT_MOCK_HEAT_INDEX % 9)
    time_offset_percent = round((_NEXT_MOCK_HEAT_INDEX % 8) * 1.7, 2)

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
        time_offset_percent = None
    elif has_major_issue_lock:
        cut_status = "blocked"
        status = "pending"
        blocked_by_issue = True
        cut_reason = "major_issue_lock"
        time_offset_percent = None
    elif mismatch_minutes >= config["major_issue_minutes"]:
        cut_status = "major_issue"
        status = "abnormal"
        major_issue = True
        cut_reason = "continuous_mismatch"
    elif time_offset_percent > config["tolerance"]:
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
    heat = {
        "id": heat_id,
        "heat_no": f"M{start_time.strftime('%Y%m%d')}-{_NEXT_MOCK_HEAT_INDEX:03d}",
        "description": None,
        "start_time": start_time,
        "end_time": end_time,
        "baseline_id": "baseline-001" if status != "pending" else None,
        "baseline_ids": ["baseline-001", "baseline-002"] if status != "pending" else [],
        "deviation_percent": max_dev,
        "avg_deviation_percent": avg_dev,
        "time_offset_percent": time_offset_percent,
        "mismatch_duration_minutes": mismatch_minutes,
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
    ),
    start_date: datetime | None = Query(default=None, description="开始日期"),  # noqa: B008
    end_date: datetime | None = Query(default=None, description="结束日期"),  # noqa: B008
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> HeatListResponse:
    """获取炉次列表（支持状态和日期范围筛选）。"""
    items = list((await _list_heat_store()).values())
    items.sort(key=lambda x: x["start_time"], reverse=True)

    if status:
        items = [item for item in items if item["status"] == status]
    if start_date:
        items = [item for item in items if item["start_time"] >= start_date]
    if end_date:
        items = [item for item in items if item["start_time"] <= end_date]

    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged = items[start_idx:end_idx]

    return HeatListResponse(
        items=[_to_heat_response(_build_heat_list_view(item)) for item in paged],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{heat_id}", response_model=HeatResponse)
async def get_heat(heat_id: str) -> HeatResponse:
    """获取炉次详情。"""
    item = await _get_or_404(heat_id)
    return _to_heat_response(_build_heat_list_view(item))


@router.patch("/{heat_id}", response_model=HeatResponse)
async def update_heat(heat_id: str, data: HeatUpdate) -> HeatResponse:
    """更新炉次信息（描述、起止时间）。"""
    item = _ensure_persisted_heat(await _get_or_404(heat_id))
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
            if other["id"] == heat_id:
                continue
            if other["start_time"] > current_start:
                other["start_time"] = other["start_time"] + delta
                other["end_time"] = other["end_time"] + delta

    await persist_runtime_state(*_runtime_heat_sections())
    _invalidate_heat_compare_cache(heat_id)
    return _to_heat_response(item)


@router.post("/{heat_id}/resume-cutting", response_model=HeatResponse)
async def resume_cutting(heat_id: str, data: HeatResumeCuttingRequest) -> HeatResponse:
    """恢复重大事故后的炉次切割。"""
    item = _ensure_persisted_heat(await _get_or_404(heat_id))

    item["cut_status"] = "normal"
    item["major_issue"] = False
    item["blocked_by_issue"] = False
    item["cut_reason"] = "manual_resume"
    item["schedule_tag"] = "work"
    item["mismatch_duration_minutes"] = min(item.get("mismatch_duration_minutes") or 0, 4)
    if item["status"] == "pending":
        item["status"] = "normal"
    item["time_offset_percent"] = min(item.get("time_offset_percent") or 0.0, 8.0)

    if data.adjust_subsequent:
        current_start = item["start_time"]
        for other in _mutable_heat_store().values():
            if other["id"] == heat_id:
                continue
            if other["start_time"] > current_start and other.get("cut_status") == "blocked":
                other["cut_status"] = "normal"
                other["blocked_by_issue"] = False
                other["major_issue"] = False
                other["cut_reason"] = "manual_resume_followup"
                other["schedule_tag"] = "work"
                other["mismatch_duration_minutes"] = 4
                if other["status"] == "pending":
                    other["status"] = "normal"
                other["time_offset_percent"] = 6.0

    await persist_runtime_state(*_runtime_heat_sections())
    _invalidate_heat_compare_cache(heat_id)
    return _to_heat_response(item)


@router.get("/{heat_id}/cutting-timeline", response_model=CuttingTimelineResponse)
async def get_cutting_timeline(heat_id: str) -> CuttingTimelineResponse:
    """获取炉次切割判定时间轴。"""
    item = await _get_or_404(heat_id)
    config = _get_cutting_config()

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
                f"连续不一致 {item.get('mismatch_duration_minutes') or 0} 分钟，"
                f"阈值 {config['major_issue_minutes']} 分钟"
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

    return CuttingTimelineResponse(heat_id=heat_id, events=events)


@router.get("/{heat_id}/curve", response_model=HeatWithCurve)
async def get_heat_curve(heat_id: str) -> HeatWithCurve:
    """获取炉次曲线数据。"""
    item = await _get_or_404(heat_id)
    await _hydrate_heat_item(item)
    prepared_item = await _build_heat_response_view(item)
    return _to_heat_with_curve(prepared_item)


@router.get("/{heat_id}/compare", response_model=HeatCompareResponse)
async def get_heat_compare(heat_id: str) -> HeatCompareResponse:
    """获取炉次与基线对比数据。"""
    item = await _get_or_404(heat_id)
    baseline_id = _resolve_primary_baseline_id(item)
    baseline_ids = _resolve_compare_baseline_ids(item)
    cache_key = _build_heat_compare_cache_key(item, baseline_ids)
    cached_response = _get_cached_heat_compare(cache_key)
    if cached_response is not None:
        return cached_response

    _, shared_current_curves = await asyncio.gather(
        _hydrate_compare_baselines(baseline_ids),
        _load_channel_curves_from_edc(
            channels=_collect_compare_metric_channels(baseline_ids),
            start_time=item["start_time"],
            end_time=item["end_time"],
        ),
    )
    live_curves = _resolve_heat_curves_from_shared_channels(item, shared_current_curves)
    if not live_curves.get("power") and not live_curves.get("voltage"):
        live_curves = await _load_heat_curves_from_edc(item) or {}

    if live_curves:
        if live_curves.get("power"):
            item["power_curve"] = live_curves["power"]
        if live_curves.get("voltage"):
            item["voltage_curve"] = live_curves["voltage"]
        item["current_curve_source"] = "live_edc"

    if baseline_id:
        baseline_item = _BASELINE_STORE.get(baseline_id)
        if baseline_item:
            baseline_power_curve = _coerce_curve_points(baseline_item.get("power_curve"))
            baseline_voltage_curve = _coerce_curve_points(baseline_item.get("voltage_curve"))
            if baseline_power_curve:
                item["baseline_power_curve"] = baseline_power_curve
            if baseline_voltage_curve:
                item["baseline_voltage_curve"] = baseline_voltage_curve
            item["baseline_curve_source"] = str(baseline_item.get("curve_source") or "none")

    response_item = _build_heat_compare_view(item)
    heat = _to_heat_with_curve(response_item)
    baseline_compares: list[BaselineCompareItem] = []
    for idx, baseline_id in enumerate(baseline_ids):
        metric_curves = await _build_metric_curve_series(
            start_time=item["start_time"],
            end_time=item["end_time"],
            minutes=46,
            baseline_id=baseline_id,
            power_curve=response_item["power_curve"],
            voltage_curve=response_item["voltage_curve"],
            current_curves_by_channel=shared_current_curves,
            hydrate_baseline=False,
        )
        baseline_item = _BASELINE_STORE.get(baseline_id)
        baseline_name = (
            str(baseline_item.get("name"))
            if baseline_item and baseline_item.get("name")
            else ("标准基线 v2.1" if idx == 0 else "高功率基线")
        )
        baseline_curve_points = _select_metric_curve(metric_curves, "power")
        baseline_voltage_curve_points = _select_metric_curve(metric_curves, "voltage")

        baseline_curve = [
            (float(point.timestamp), float(point.value)) for point in baseline_curve_points
        ]
        current_curve = [
            (float(point.timestamp), float(point.value)) for point in response_item["power_curve"]
        ]
        result = deviation_service.calculate_deviation(
            baseline_curve=baseline_curve,
            current_curve=current_curve,
            tolerance=15.0,
        )

        deviation_ranges = [
            DeviationRange(
                start=int(item_range["start"]),
                end=int(item_range["end"]),
                deviation=float(item_range["deviation"]),
            )
            for item_range in result["abnormal_ranges"]
        ]
        deviation_ranges = _ensure_deviation_ranges(response_item, deviation_ranges)

        baseline_compares.append(
            BaselineCompareItem(
                baseline=BaselineWithCurveSimple(
                    id=baseline_id,
                    name=baseline_name,
                    power_curve=baseline_curve_points,
                    voltage_curve=baseline_voltage_curve_points,
                    tolerance_percent=15.0,
                ),
                metric_curves=metric_curves,
                deviation_ranges=deviation_ranges,
                max_deviation=result["max_deviation"],
                avg_deviation=result["avg_deviation"],
            )
        )

    baseline = baseline_compares[0].baseline if baseline_compares else None
    deviation_ranges = baseline_compares[0].deviation_ranges if baseline_compares else []
    max_deviation = baseline_compares[0].max_deviation if baseline_compares else None
    avg_deviation = baseline_compares[0].avg_deviation if baseline_compares else None

    response = HeatCompareResponse(
        heat=heat,
        baseline=baseline,
        baselines=baseline_compares,
        deviation_ranges=deviation_ranges,
        max_deviation=max_deviation,
        avg_deviation=avg_deviation,
    )
    _set_cached_heat_compare(cache_key=cache_key, heat_id=heat_id, response=response)
    return response


@router.post("/{heat_id}/analyze", response_model=HeatAnalyzeResponse)
async def analyze_heat(heat_id: str, data: HeatAnalyzeRequest) -> HeatAnalyzeResponse:
    """触发炉次偏差分析。"""
    item = _ensure_persisted_heat(await _get_or_404(heat_id))
    await _hydrate_heat_item(item)
    baseline_id = data.baseline_id or _resolve_primary_baseline_id(item) or "baseline-001"

    baseline_curve = [
        (float(point.timestamp), float(point.value)) for point in item["baseline_power_curve"]
    ]
    current_curve = [(float(point.timestamp), float(point.value)) for point in item["power_curve"]]
    result = deviation_service.calculate_deviation(
        baseline_curve=baseline_curve,
        current_curve=current_curve,
        tolerance=15.0,
    )

    item["baseline_id"] = baseline_id
    item["deviation_percent"] = result["max_deviation"]
    item["avg_deviation_percent"] = result["avg_deviation"]
    item["status"] = result["status"]
    await persist_runtime_state(*_runtime_heat_sections())
    _invalidate_heat_compare_cache(heat_id)

    return HeatAnalyzeResponse(
        heat_id=heat_id,
        baseline_id=baseline_id,
        max_deviation=result["max_deviation"],
        avg_deviation=result["avg_deviation"],
        status=result["status"],
        deviation_ranges=[
            DeviationRange(
                start=int(item_range["start"]),
                end=int(item_range["end"]),
                deviation=float(item_range["deviation"]),
            )
            for item_range in result["abnormal_ranges"]
        ],
    )
