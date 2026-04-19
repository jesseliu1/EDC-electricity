"""正式历史炉次服务。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from ..channel_roles import infer_metric_kind
from ..database import async_session_maker
from ..models import (
    Baseline,
    BaselineDefinitionMetric,
    Heat,
    HeatBaselineBinding,
    MetricSeries,
)
from ..observability import log_event
from ..schemas.common import CurvePoint
from ..time_utils import from_timestamp_ms, to_timestamp_ms, utc_now
from .edc_client import EDCClient, EDCClientError
from .formal_baseline_service import decode_baseline_id, encode_baseline_id
from .heat_cutting_service import HeatCuttingConfig
from .heat_deviation_analysis_service import HeatDeviationAnalysisService
from .heat_runtime_curve_merge import (
    actual_context_bounds_from_metric_curves,
    merge_metric_curves,
    missing_metric_keys_in_window,
    normalize_curve_points,
)
from .heat_runtime_factory import HeatRuntimeFactory
from .heat_runtime_frozen_input_resolver import (
    resolve_runtime_baseline_metric_specs_from_frozen_inputs,
    resolve_runtime_hydrate_specs_from_frozen_inputs,
)
from .heat_runtime_types import RuntimePresealPayload

MetricCurveLoader = Callable[
    [list[dict[str, Any]], datetime, datetime],
    Awaitable[dict[str, list[CurvePoint]]],
]

_heat_deviation_analysis_service = HeatDeviationAnalysisService()
_heat_runtime_factory = HeatRuntimeFactory()


def _is_runtime_debug_enabled() -> bool:
    try:
        from ..api.settings import _SETTINGS_STORE
    except ImportError:
        return False
    raw_value = _SETTINGS_STORE.get("replay_runtime_debug_enabled", {}).get("value")
    return str(raw_value or "false").strip().lower() in {"1", "true", "yes", "on"}


def _log_runtime_debug(event: str, **fields: Any) -> None:
    if not _is_runtime_debug_enabled():
        return
    log_event(event, **fields)


def _summarize_curve_points(points: list[CurvePoint] | None) -> dict[str, Any]:
    normalized_points = list(points or [])
    if not normalized_points:
        return {
            "point_count": 0,
            "first_point_at": None,
            "last_point_at": None,
        }
    return {
        "point_count": len(normalized_points),
        "first_point_at": from_timestamp_ms(normalized_points[0].timestamp),
        "last_point_at": from_timestamp_ms(normalized_points[-1].timestamp),
    }


def _summarize_curves_by_metric(
    curves_by_metric: dict[str, list[CurvePoint]],
    *,
    sample_limit: int = 4,
) -> dict[str, Any]:
    metric_keys = sorted(str(metric_key) for metric_key in curves_by_metric.keys())
    sampled_metrics: list[dict[str, Any]] = []
    overall_first_point_at: datetime | None = None
    overall_last_point_at: datetime | None = None
    for index, metric_key in enumerate(metric_keys):
        summary = _summarize_curve_points(curves_by_metric.get(metric_key))
        first_point_at = summary.get("first_point_at")
        last_point_at = summary.get("last_point_at")
        if isinstance(first_point_at, datetime):
            if overall_first_point_at is None or first_point_at < overall_first_point_at:
                overall_first_point_at = first_point_at
        if isinstance(last_point_at, datetime):
            if overall_last_point_at is None or last_point_at > overall_last_point_at:
                overall_last_point_at = last_point_at
        if index < sample_limit:
            sampled_metrics.append({"metric_key": metric_key, **summary})
    return {
        "metric_count": len(metric_keys),
        "sampled_metrics": sampled_metrics,
        "overall_first_point_at": overall_first_point_at,
        "overall_last_point_at": overall_last_point_at,
    }


def _summarize_candidate_windows(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    return {
        "id": str(candidate.get("id") or ""),
        "start_time": candidate.get("start_time"),
        "end_time": candidate.get("end_time"),
        "context_start_time": candidate.get("context_start_time"),
        "context_end_time": candidate.get("context_end_time"),
        "actual_context_start_time": candidate.get("actual_context_start_time"),
        "actual_context_end_time": candidate.get("actual_context_end_time"),
        "last_point_at": candidate.get("last_point_at"),
    }


def encode_heat_owner_key(heat_id: str) -> str:
    """生成 heat 指标值 owner_key。"""

    return heat_id


def _normalize_curve_points(points: list[Any] | None) -> list[CurvePoint]:
    return normalize_curve_points(points)


def _build_series_payload(
    *,
    context_start_time: datetime,
    heat_start_time: datetime,
    heat_end_time: datetime,
    context_end_time: datetime,
    points: list[CurvePoint],
) -> str:
    payload = {
        "context_start_time": to_timestamp_ms(context_start_time),
        "heat_start_time": to_timestamp_ms(heat_start_time),
        "heat_end_time": to_timestamp_ms(heat_end_time),
        "context_end_time": to_timestamp_ms(context_end_time),
        "points": [
            {"timestamp": int(point.timestamp), "value": float(point.value)} for point in points
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_series_payload(series_json: str | None) -> dict[str, Any]:
    if not series_json:
        return {}
    try:
        payload = json.loads(series_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _rewrite_heat_series_payload_window(
    series_json: str | None,
    *,
    heat_start_time: datetime,
    heat_end_time: datetime,
) -> str | None:
    payload = _parse_series_payload(series_json)
    if not payload:
        return series_json
    payload["heat_start_time"] = to_timestamp_ms(heat_start_time)
    payload["heat_end_time"] = to_timestamp_ms(heat_end_time)
    return _json_compact(payload)


def _metric_series_points(series: MetricSeries) -> list[CurvePoint]:
    payload = _parse_series_payload(series.series_json)
    raw_points = payload.get("points")
    if isinstance(raw_points, list):
        return _normalize_curve_points(raw_points)
    return []


def _series_payload_points(raw_payload: Any) -> list[CurvePoint]:
    if isinstance(raw_payload, dict):
        raw_points = raw_payload.get("points")
        return _normalize_curve_points(raw_points if isinstance(raw_points, list) else None)
    if isinstance(raw_payload, str):
        payload = _parse_series_payload(raw_payload)
        raw_points = payload.get("points")
        return _normalize_curve_points(raw_points if isinstance(raw_points, list) else None)
    return []


def _context_boundaries_from_series(
    series_rows: list[MetricSeries],
) -> tuple[datetime | None, datetime | None]:
    for row in series_rows:
        payload = _parse_series_payload(row.series_json)
        start_raw = payload.get("context_start_time")
        end_raw = payload.get("context_end_time")
        if isinstance(start_raw, (int, float)) and isinstance(end_raw, (int, float)):
            try:
                return from_timestamp_ms(start_raw), from_timestamp_ms(end_raw)
            except (TypeError, ValueError):
                continue
    return None, None


def _actual_context_boundaries_from_series(
    series_rows: list[MetricSeries],
) -> tuple[datetime | None, datetime | None]:
    curves_by_metric: dict[str, list[CurvePoint]] = {}
    for row in series_rows:
        metric_key = str(row.metric_key or "").strip().lower()
        if not metric_key:
            continue
        points = _metric_series_points(row)
        if points:
            curves_by_metric[metric_key] = points
    return actual_context_bounds_from_metric_curves(curves_by_metric)


def _metric_kind_for_series(series: MetricSeries) -> str:
    if series.metric_key:
        lowered = series.metric_key.lower()
        if lowered in {"power", "voltage", "temperature", "pressure"}:
            return lowered
    return infer_metric_kind(series.metric_name, series.unit or "")


def _candidate_metric_curve_map(candidate: dict[str, Any]) -> dict[str, list[CurvePoint]]:
    curves: dict[str, list[CurvePoint]] = {}
    runtime_series = candidate.get("runtime_metric_series")
    if isinstance(runtime_series, list):
        for entry in runtime_series:
            if not isinstance(entry, dict):
                continue
            metric_key = str(entry.get("metric_key") or "").strip().lower()
            if not metric_key:
                continue
            points = _series_payload_points(entry.get("series_json"))
            if points:
                curves[metric_key] = points
    power_curve = _normalize_curve_points(candidate.get("power_curve"))
    if power_curve:
        curves.setdefault("power", power_curve)
    voltage_curve = _normalize_curve_points(candidate.get("voltage_curve"))
    if voltage_curve:
        curves.setdefault("voltage", voltage_curve)
    return curves


def _binding_sort_key(binding: HeatBaselineBinding) -> tuple[int, float, float, str]:
    effective_ts = (
        float(to_timestamp_ms(binding.effective_from_snapshot))
        if binding.effective_from_snapshot is not None
        else 0.0
    )
    updated_ts = float(to_timestamp_ms(binding.updated_at))
    baseline_id = encode_baseline_id(binding.baseline_definition_id, binding.baseline_item)
    return (1 if binding.is_primary else 0, effective_ts, updated_ts, baseline_id)


def _binding_to_dict(binding: HeatBaselineBinding) -> dict[str, Any]:
    baseline_id = encode_baseline_id(binding.baseline_definition_id, binding.baseline_item)
    return {
        "heat_id": binding.heat_id,
        "baseline_id": baseline_id,
        "baseline_version_id": baseline_id,
        "baseline_definition_id": binding.baseline_definition_id,
        "baseline_item": binding.baseline_item,
        "is_primary": bool(binding.is_primary),
        "baseline_effective_from": binding.effective_from_snapshot,
        "tolerance_percent": binding.tolerance_percent_snapshot,
        "analysis_status": binding.analysis_status,
        "analysis_reason": binding.analysis_reason,
        "analysis_message": binding.analysis_message,
        "deviation_score": binding.deviation_score,
        "avg_deviation_score": binding.avg_deviation_score,
        "analysis_details_json": binding.analysis_details_json,
        "abnormal_duration_minutes": binding.abnormal_duration_minutes,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }


def _select_primary_binding(bindings: list[HeatBaselineBinding]) -> HeatBaselineBinding | None:
    if not bindings:
        return None
    ordered = sorted(bindings, key=_binding_sort_key, reverse=True)
    return ordered[0] if ordered else None


def _heat_model_to_dict(
    heat: Heat,
    series_rows: list[MetricSeries],
    bindings: list[HeatBaselineBinding],
) -> dict[str, Any]:
    series_by_kind: dict[str, MetricSeries] = {}
    for row in sorted(series_rows, key=lambda item: (item.sort_order, item.item)):
        kind = _metric_kind_for_series(row)
        if kind not in series_by_kind:
            series_by_kind[kind] = row

    power_curve = (
        _metric_series_points(series_by_kind["power"]) if "power" in series_by_kind else []
    )
    voltage_curve = (
        _metric_series_points(series_by_kind["voltage"]) if "voltage" in series_by_kind else []
    )
    context_start_time, context_end_time = _context_boundaries_from_series(series_rows)
    actual_context_start_time, actual_context_end_time = _actual_context_boundaries_from_series(
        series_rows
    )
    ordered_bindings = sorted(bindings, key=_binding_sort_key, reverse=True)
    primary_binding = _select_primary_binding(ordered_bindings)
    primary_baseline_id = (
        encode_baseline_id(primary_binding.baseline_definition_id, primary_binding.baseline_item)
        if primary_binding is not None
        else None
    )
    binding_views = [_binding_to_dict(binding) for binding in ordered_bindings]
    runtime_metric_series = [
        {
            "owner_key": row.owner_key,
            "item": row.item,
            "owner_type": row.owner_type,
            "metric_key": row.metric_key,
            "metric_name": row.metric_name,
            "unit": row.unit,
            "color": row.color,
            "sort_order": row.sort_order,
            "source_channel_id": row.source_channel_id,
            "source_channel_name": row.source_channel_name,
            "source_channel_label": row.source_channel_label,
            "series_json": _parse_series_payload(row.series_json),
            "stat_json": _parse_series_payload(row.stat_json),
        }
        for row in sorted(series_rows, key=lambda item: (item.sort_order, item.item))
    ]

    return {
        "id": heat.id,
        "heat_no": heat.heat_no,
        "description": heat.description,
        "furnace_id": heat.furnace_id,
        "start_time": heat.start_time,
        "end_time": heat.end_time,
        "context_start_time": context_start_time or heat.context_start_time,
        "context_end_time": context_end_time or heat.context_end_time,
        "actual_context_start_time": actual_context_start_time,
        "actual_context_end_time": actual_context_end_time,
        "is_manually_adjusted": bool(heat.is_manually_adjusted),
        "completion_status": "completed",
        "last_point_at": heat.end_time,
        "baseline_id": primary_baseline_id,
        "baseline_version_id": primary_baseline_id,
        "baseline_definition_id": (
            primary_binding.baseline_definition_id if primary_binding is not None else None
        ),
        "baseline_item": primary_binding.baseline_item if primary_binding is not None else None,
        "baseline_effective_from": (
            primary_binding.effective_from_snapshot if primary_binding is not None else None
        ),
        "baseline_ids": [binding["baseline_id"] for binding in binding_views],
        "baseline_bindings": binding_views,
        "analysis_status": primary_binding.analysis_status if primary_binding is not None else None,
        "analysis_reason": primary_binding.analysis_reason if primary_binding is not None else None,
        "analysis_message": (
            primary_binding.analysis_message if primary_binding is not None else None
        ),
        "deviation_score": (
            primary_binding.deviation_score if primary_binding is not None else None
        ),
        "avg_deviation_score": (
            primary_binding.avg_deviation_score if primary_binding is not None else None
        ),
        "abnormal_duration_minutes": (
            primary_binding.abnormal_duration_minutes if primary_binding is not None else None
        ),
        "schedule_tag": "work",
        "cut_reason": heat.cut_reason,
        "cut_status": heat.cut_status,
        "major_issue": heat.cut_status == "major_issue",
        "blocked_by_issue": heat.cut_status == "blocked",
        "status": heat.status,
        "temperature": None,
        "record_source": "sealed_history",
        "current_curve_source": "formal_db",
        "baseline_curve_source": "none",
        "created_at": heat.created_at,
        "sealed_at": heat.sealed_at,
        "runtime_metric_series": runtime_metric_series,
        "power_curve": power_curve,
        "voltage_curve": voltage_curve,
        "baseline_power_curve": [],
        "baseline_voltage_curve": [],
    }


async def _load_metric_series_for_owner_keys(
    owner_keys: list[str],
) -> dict[str, list[MetricSeries]]:
    if not owner_keys:
        return {}
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(MetricSeries)
                    .where(MetricSeries.owner_key.in_(owner_keys))
                    .order_by(MetricSeries.owner_key, MetricSeries.sort_order, MetricSeries.item)
                )
            ).scalars()
        )

    grouped: dict[str, list[MetricSeries]] = {}
    for row in rows:
        grouped.setdefault(row.owner_key, []).append(row)
    return grouped


async def _load_bindings_for_heat_ids(
    heat_ids: list[str],
) -> dict[str, list[HeatBaselineBinding]]:
    if not heat_ids:
        return {}
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(HeatBaselineBinding)
                    .where(HeatBaselineBinding.heat_id.in_(heat_ids))
                    .order_by(
                        HeatBaselineBinding.heat_id,
                        HeatBaselineBinding.is_primary.desc(),
                        HeatBaselineBinding.effective_from_snapshot.desc(),
                        HeatBaselineBinding.updated_at.desc(),
                    )
                )
            ).scalars()
        )

    grouped: dict[str, list[HeatBaselineBinding]] = {}
    for row in rows:
        grouped.setdefault(row.heat_id, []).append(row)
    return grouped


async def list_formal_heat_binding_records(heat_id: str) -> list[dict[str, Any]]:
    binding_map = await _load_bindings_for_heat_ids([heat_id])
    return [_binding_to_dict(binding) for binding in binding_map.get(heat_id, [])]


async def list_formal_heat_records(
    *,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    async with async_session_maker() as session:
        query = select(Heat)
        if status:
            query = query.where(Heat.status == status)
        if start_date is not None:
            query = query.where(Heat.start_time >= start_date)
        if end_date is not None:
            query = query.where(Heat.start_time <= end_date)
        heats = list((await session.execute(query.order_by(Heat.start_time.desc()))).scalars())

    owner_keys = [encode_heat_owner_key(heat.id) for heat in heats]
    metric_series_by_owner, bindings_by_heat = await _gather_heat_read_context(
        owner_keys=owner_keys,
        heat_ids=[heat.id for heat in heats],
    )
    return [
        _heat_model_to_dict(
            heat,
            metric_series_by_owner.get(encode_heat_owner_key(heat.id), []),
            bindings_by_heat.get(heat.id, []),
        )
        for heat in heats
    ]


async def _gather_heat_read_context(
    *,
    owner_keys: list[str],
    heat_ids: list[str],
) -> tuple[dict[str, list[MetricSeries]], dict[str, list[HeatBaselineBinding]]]:
    metric_series_by_owner = await _load_metric_series_for_owner_keys(owner_keys)
    bindings_by_heat = await _load_bindings_for_heat_ids(heat_ids)
    return metric_series_by_owner, bindings_by_heat


async def get_formal_heat_record(heat_id: str) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        heat = await session.get(Heat, heat_id)
    if heat is None:
        return None

    metric_series_by_owner, bindings_by_heat = await _gather_heat_read_context(
        owner_keys=[encode_heat_owner_key(heat_id)],
        heat_ids=[heat_id],
    )
    return _heat_model_to_dict(
        heat,
        metric_series_by_owner.get(encode_heat_owner_key(heat_id), []),
        bindings_by_heat.get(heat_id, []),
    )


async def update_formal_heat_record(
    heat_id: str,
    *,
    description: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    updated_by: str = "system",
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        heat = await session.get(Heat, heat_id)
        if heat is None:
            return None

        if description is not None:
            heat.description = description

        new_start = start_time or heat.start_time
        new_end = end_time or heat.end_time
        if new_start > new_end:
            raise ValueError("start_time_after_end_time")
        if new_start < heat.context_start_time or new_end > heat.context_end_time:
            raise ValueError("outside_context_window")

        time_changed = new_start != heat.start_time or new_end != heat.end_time
        heat.start_time = new_start
        heat.end_time = new_end
        if time_changed:
            heat.is_manually_adjusted = True
        heat.updated_by = updated_by
        heat.updated_at = utc_now()

        if time_changed:
            series_rows = list(
                (
                    await session.execute(
                        select(MetricSeries)
                        .where(MetricSeries.owner_key == heat_id)
                        .where(MetricSeries.owner_type == "heat")
                        .order_by(MetricSeries.sort_order, MetricSeries.item)
                    )
                ).scalars()
            )
            for row in series_rows:
                row.series_json = _rewrite_heat_series_payload_window(
                    row.series_json,
                    heat_start_time=new_start,
                    heat_end_time=new_end,
                )
                row.updated_at = heat.updated_at
        await session.commit()

    return await get_formal_heat_record(heat_id)


async def resume_formal_heat_cutting(
    heat_id: str,
    *,
    note: str | None = None,
    updated_by: str = "system",
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        heat = await session.get(Heat, heat_id)
        if heat is None:
            return None

        primary_binding = (
            await session.execute(
                select(HeatBaselineBinding)
                .where(HeatBaselineBinding.heat_id == heat_id)
                .where(HeatBaselineBinding.is_primary.is_(True))
                .limit(1)
            )
        ).scalar_one_or_none()

        heat.cut_status = "normal"
        heat.cut_reason = note or "manual_resume"
        if heat.status == "pending":
            heat.status = "normal"
        heat.updated_by = updated_by
        heat.updated_at = utc_now()

        if primary_binding is not None:
            primary_binding.abnormal_duration_minutes = min(
                primary_binding.abnormal_duration_minutes or 0,
                4,
            )
            primary_binding.updated_at = utc_now()

        await session.commit()

    return await get_formal_heat_record(heat_id)


async def _load_definition_metric_templates(
    definition_ids: list[str],
) -> dict[str, list[BaselineDefinitionMetric]]:
    if not definition_ids:
        return {}
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(BaselineDefinitionMetric)
                    .where(BaselineDefinitionMetric.definition_id.in_(definition_ids))
                    .where(BaselineDefinitionMetric.enabled.is_(True))
                    .order_by(
                        BaselineDefinitionMetric.definition_id,
                        BaselineDefinitionMetric.sort_order,
                        BaselineDefinitionMetric.item,
                    )
                )
            ).scalars()
        )

    grouped: dict[str, list[BaselineDefinitionMetric]] = {}
    for row in rows:
        grouped.setdefault(row.definition_id, []).append(row)
    return grouped


def _template_field(template: Any, field_name: str) -> Any:
    if isinstance(template, dict):
        return template.get(field_name)
    return getattr(template, field_name)


def _baseline_field(baseline: Any, field_name: str) -> Any:
    if isinstance(baseline, dict):
        return baseline.get(field_name)
    return getattr(baseline, field_name)


def _pick_metric_template(
    templates: list[Any],
    *,
    metric_kind: str,
) -> Any | None:
    exact = next(
        (
            row
            for row in templates
            if str(_template_field(row, "metric_key") or "").strip().lower() == metric_kind
        ),
        None,
    )
    if exact is not None:
        return exact
    inferred = [
        row
        for row in templates
        if infer_metric_kind(
            str(_template_field(row, "metric_name") or ""),
            str(_template_field(row, "unit") or ""),
        )
        == metric_kind
    ]
    return inferred[0] if inferred else None


def _template_series_spec(template: Any) -> dict[str, Any] | None:
    item = str(_template_field(template, "item") or "").strip()
    metric_key = str(_template_field(template, "metric_key") or "").strip().lower()
    metric_name = str(_template_field(template, "metric_name") or "").strip()
    color = str(_template_field(template, "color") or "").strip()
    if not item or not metric_key or not metric_name or not color:
        return None
    return {
        "item": item,
        "metric_key": metric_key,
        "metric_name": metric_name,
        "unit": _template_field(template, "unit"),
        "color": color,
        "sort_order": int(_template_field(template, "sort_order") or 0),
        "edc_channel_id": _template_field(template, "edc_channel_id")
        or _template_field(template, "source_channel_id"),
        "source_channel_id": _template_field(template, "edc_channel_id")
        or _template_field(template, "source_channel_id"),
        "source_channel_name": _template_field(template, "source_channel_name"),
        "source_channel_label": _template_field(template, "source_channel_label"),
    }


def _build_baseline_metric_spec_map(
    *,
    applicable_baselines: list[Any],
    template_map: dict[str, list[BaselineDefinitionMetric]],
) -> dict[str, list[dict[str, Any]]]:
    baseline_specs: dict[str, list[dict[str, Any]]] = {}
    for baseline in applicable_baselines:
        definition_id = str(_baseline_field(baseline, "definition_id") or "").strip()
        baseline_item = str(_baseline_field(baseline, "item") or "").strip()
        if not definition_id or not baseline_item:
            continue
        baseline_id = encode_baseline_id(definition_id, baseline_item)
        specs = [
            spec
            for template in template_map.get(definition_id, [])
            if (spec := _template_series_spec(template)) is not None
        ]
        if specs:
            baseline_specs[baseline_id] = specs
    return baseline_specs


def _build_runtime_metric_union_specs(
    baseline_metric_specs_by_id: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    union_specs: dict[str, dict[str, Any]] = {}
    for specs in baseline_metric_specs_by_id.values():
        for spec in specs:
            metric_key = str(spec.get("metric_key") or "").strip().lower()
            if not metric_key or metric_key in union_specs:
                continue
            union_specs[metric_key] = dict(spec)
    return list(union_specs.values())


def _metric_spec_from_runtime_series_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    metric_key = str(entry.get("metric_key") or "").strip().lower()
    metric_name = str(entry.get("metric_name") or "").strip()
    color = str(entry.get("color") or "").strip()
    if not metric_key or not metric_name or not color:
        return None
    return {
        "item": str(entry.get("item") or "").strip() or "001",
        "metric_key": metric_key,
        "metric_name": metric_name,
        "unit": entry.get("unit"),
        "color": color,
        "sort_order": int(entry.get("sort_order") or 0),
        "edc_channel_id": entry.get("edc_channel_id") or entry.get("source_channel_id"),
        "source_channel_id": entry.get("source_channel_id"),
        "source_channel_name": entry.get("source_channel_name"),
        "source_channel_label": entry.get("source_channel_label"),
    }


def _baseline_metric_spec_map_from_runtime_views(
    baseline_views: list[dict[str, Any]] | None,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(baseline_views, list):
        return {}

    baseline_specs: dict[str, list[dict[str, Any]]] = {}
    for raw_view in baseline_views:
        if not isinstance(raw_view, dict):
            continue
        baseline_id = str(raw_view.get("baseline_id") or "").strip()
        if not baseline_id:
            continue
        raw_series = raw_view.get("current_metric_series")
        if not isinstance(raw_series, list):
            continue
        specs = [
            spec
            for entry in raw_series
            if isinstance(entry, dict)
            and (spec := _metric_spec_from_runtime_series_entry(entry)) is not None
        ]
        if specs:
            baseline_specs[baseline_id] = specs
    return baseline_specs


def _runtime_series_window(
    candidate: dict[str, Any],
) -> tuple[datetime, datetime, datetime, datetime]:
    start_time = candidate["start_time"]
    end_time = candidate["end_time"]
    context_start_time = candidate.get("context_start_time") or start_time
    context_end_time = candidate.get("context_end_time") or end_time
    return context_start_time, start_time, end_time, context_end_time


def _build_runtime_metric_series_entries(
    *,
    candidate: dict[str, Any],
    metric_specs: list[Any],
    curves_by_metric: dict[str, list[CurvePoint]],
) -> list[dict[str, Any]]:
    context_start_time, start_time, end_time, context_end_time = _runtime_series_window(candidate)
    series_entries: list[dict[str, Any]] = []
    for index, template in enumerate(metric_specs, start=1):
        spec = _template_series_spec(template)
        if spec is None:
            continue
        points = curves_by_metric.get(str(spec["metric_key"]))
        if not points:
            continue
        series_entries.append(
            {
                "owner_key": encode_heat_owner_key(str(candidate["id"])),
                "item": f"{index:03d}",
                "owner_type": "heat",
                "metric_key": str(spec["metric_key"]),
                "metric_name": str(spec["metric_name"]),
                "unit": spec.get("unit"),
                "color": str(spec["color"]),
                "sort_order": int(spec["sort_order"]),
                "source_channel_id": spec.get("source_channel_id") or spec.get("edc_channel_id"),
                "source_channel_name": spec.get("source_channel_name"),
                "source_channel_label": spec.get("source_channel_label"),
                "series_json": {
                    "context_start_time": to_timestamp_ms(context_start_time),
                    "heat_start_time": to_timestamp_ms(start_time),
                    "heat_end_time": to_timestamp_ms(end_time),
                    "context_end_time": to_timestamp_ms(context_end_time),
                    "points": [
                        {"timestamp": int(point.timestamp), "value": float(point.value)}
                        for point in points
                    ],
                },
                "stat_json": {
                    "heat_min": min(float(point.value) for point in points),
                    "heat_max": max(float(point.value) for point in points),
                    "heat_avg": round(
                        sum(float(point.value) for point in points) / max(len(points), 1),
                        4,
                    ),
                },
            }
        )
    return series_entries


async def _default_metric_curve_loader(
    metrics: list[dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]]:
    from ..api.settings import _HOST_CHANNEL_STORE, get_edc_connection_config

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return {}

    host_channels = {
        str(channel.get("id") or ""): channel
        for channel in _HOST_CHANNEL_STORE
        if isinstance(channel, dict) and str(channel.get("id") or "")
    }
    bound_metrics: list[tuple[str, dict[str, str]]] = []
    for metric in metrics:
        metric_id = str(metric.get("id") or "").strip()
        channel_id = str(metric.get("edc_channel_id") or "").strip()
        channel = host_channels.get(channel_id)
        if metric_id and channel:
            bound_metrics.append((metric_id, channel))
    if not bound_metrics:
        return {}

    try:
        async with EDCClient(**config) as client:
            tasks = {
                metric_id: asyncio.create_task(
                    client.get_local_datas(
                        suid=str(channel["suid"]),
                        cuid=str(channel["cuid"]),
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


async def hydrate_candidate_runtime_metric_series(
    candidate: dict[str, Any],
    *,
    metric_specs: list[Any],
    metric_curve_loader: MetricCurveLoader | None = None,
) -> dict[str, Any]:
    hydrated = dict(candidate)
    if not metric_specs:
        log_event(
            "runtime_metric_series_hydrate_error",
            heat_id=str(candidate.get("id") or ""),
            error="definition_metric_templates_missing",
        )
        raise ValueError("definition_metric_templates_missing")

    base_curves_by_metric = _candidate_metric_curve_map(hydrated)
    context_start_time, _start_time, _end_time, context_end_time = _runtime_series_window(hydrated)
    loader = metric_curve_loader or _default_metric_curve_loader
    metric_views = [
        {
            "id": str(spec["metric_key"]),
            "metric_key": str(spec["metric_key"]),
            "name": str(spec["metric_name"]),
            "unit": spec.get("unit"),
            "color": str(spec["color"]),
            "edc_channel_id": spec.get("edc_channel_id") or spec.get("source_channel_id"),
        }
        for template in metric_specs
        if (spec := _template_series_spec(template)) is not None
    ]
    _log_runtime_debug(
        "runtime_metric_series_hydrate_started",
        candidate=_summarize_candidate_windows(hydrated),
        request_window_start_time=context_start_time,
        request_window_end_time=context_end_time,
        requested_metric_keys=[str(metric.get("metric_key") or "") for metric in metric_views],
        base_curves=_summarize_curves_by_metric(base_curves_by_metric),
    )
    loaded_curves = await loader(metric_views, context_start_time, context_end_time)
    metric_key_by_item = {
        str(metric["id"]): str(metric["metric_key"]) for metric in metric_views if metric.get("id")
    }
    incoming_curves_by_metric: dict[str, list[CurvePoint]] = {}
    for metric_item, points in loaded_curves.items():
        metric_key = metric_key_by_item.get(str(metric_item))
        if metric_key and points:
            incoming_curves_by_metric[metric_key] = list(points)
    curves_by_metric = merge_metric_curves(
        base_curves_by_metric,
        incoming_curves_by_metric,
        window_start=context_start_time,
        window_end=context_end_time,
    )

    required_metric_keys = [
        str(spec["metric_key"])
        for template in metric_specs
        if (spec := _template_series_spec(template)) is not None
    ]
    missing_metric_keys = [
        metric_key for metric_key in required_metric_keys if not curves_by_metric.get(metric_key)
    ]
    if missing_metric_keys:
        log_event(
            "runtime_metric_series_hydrate_error",
            heat_id=str(candidate.get("id") or ""),
            error="runtime_metric_curves_incomplete",
            missing_metric_keys=missing_metric_keys,
        )
        raise ValueError("runtime_metric_curves_incomplete")

    runtime_metric_series = _build_runtime_metric_series_entries(
        candidate=hydrated,
        metric_specs=metric_specs,
        curves_by_metric=curves_by_metric,
    )
    hydrated["runtime_metric_series"] = runtime_metric_series
    if curves_by_metric.get("power"):
        hydrated["power_curve"] = list(curves_by_metric["power"])
    if curves_by_metric.get("voltage"):
        hydrated["voltage_curve"] = list(curves_by_metric["voltage"])
    actual_context_start_time, actual_context_end_time = actual_context_bounds_from_metric_curves(
        curves_by_metric
    )
    _log_runtime_debug(
        "runtime_metric_series_hydrate_result",
        candidate=_summarize_candidate_windows(hydrated),
        request_window_start_time=context_start_time,
        request_window_end_time=context_end_time,
        loaded_curves=_summarize_curves_by_metric(incoming_curves_by_metric),
        merged_curves=_summarize_curves_by_metric(curves_by_metric),
        actual_context_start_time=actual_context_start_time,
        actual_context_end_time=actual_context_end_time,
        missing_metric_keys=missing_metric_keys,
    )
    if runtime_metric_series:
        hydrated["current_curve_source"] = "runtime_metric_series"
        hydrated["context_start_time"] = context_start_time
        hydrated["context_end_time"] = context_end_time
        hydrated["actual_context_start_time"] = actual_context_start_time
        hydrated["actual_context_end_time"] = actual_context_end_time
        hydrated["last_point_at"] = actual_context_end_time or context_end_time
        _log_runtime_debug(
            "runtime_metric_series_hydrate_applied",
            candidate=_summarize_candidate_windows(hydrated),
            runtime_metric_series=_summarize_curves_by_metric(curves_by_metric),
        )
    return hydrated


def _build_runtime_baseline_views(
    *,
    candidate: dict[str, Any],
    applicable_baselines: list[Any],
    baseline_metric_specs_by_id: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    curves_by_metric = _candidate_metric_curve_map(candidate)
    binding_map = {
        str(binding.get("baseline_id") or ""): binding
        for binding in (candidate.get("baseline_bindings") or [])
        if isinstance(binding, dict)
    }
    views: list[dict[str, Any]] = []
    for baseline in applicable_baselines:
        baseline_definition_id = str(_baseline_field(baseline, "definition_id") or "").strip()
        baseline_item = str(_baseline_field(baseline, "item") or "").strip()
        if not baseline_definition_id or not baseline_item:
            continue
        baseline_id = encode_baseline_id(baseline_definition_id, baseline_item)
        metric_specs = baseline_metric_specs_by_id.get(baseline_id, [])
        current_metric_series = _build_runtime_metric_series_entries(
            candidate=candidate,
            metric_specs=metric_specs,
            curves_by_metric=curves_by_metric,
        )
        binding = binding_map.get(baseline_id) or {}
        required_metric_keys = [
            str(spec.get("metric_key") or "").strip().lower()
            for spec in metric_specs
            if str(spec.get("metric_key") or "").strip()
        ]
        views.append(
            {
                "heat_id": str(candidate.get("id") or ""),
                "baseline_id": baseline_id,
                "baseline_definition_id": baseline_definition_id,
                "baseline_item": baseline_item,
                "is_primary": bool(
                    binding.get("is_primary")
                    if isinstance(binding, dict)
                    else baseline_id == candidate.get("baseline_id")
                ),
                "baseline_effective_from": (
                    binding.get("baseline_effective_from")
                    if isinstance(binding, dict)
                    else _baseline_field(baseline, "effective_from")
                ),
                "tolerance_percent": (
                    binding.get("tolerance_percent")
                    if isinstance(binding, dict)
                    else _baseline_field(baseline, "tolerance_percent")
                ),
                "required_metric_keys": required_metric_keys,
                "current_metric_series": current_metric_series,
                "analysis_status": str(binding.get("analysis_status") or "waiting"),
                "analysis_reason": (
                    str(binding.get("analysis_reason"))
                    if binding.get("analysis_reason") is not None
                    else None
                ),
                "analysis_message": (
                    str(binding.get("analysis_message"))
                    if binding.get("analysis_message") is not None
                    else None
                ),
                "deviation_score": binding.get("deviation_score"),
                "avg_deviation_score": binding.get("avg_deviation_score"),
                "analysis_details_json": binding.get("analysis_details_json"),
                "abnormal_duration_minutes": binding.get("abnormal_duration_minutes"),
            }
        )
    return views


def _decode_baseline_binding(baseline_id: str | None) -> tuple[str | None, str | None]:
    if not baseline_id:
        return None, None
    try:
        return decode_baseline_id(baseline_id)
    except ValueError:
        return None, None


async def _list_applicable_published_baselines(start_time: datetime) -> list[Baseline]:
    async with async_session_maker() as session:
        baselines = list(
            (
                await session.execute(
                    select(Baseline)
                    .where(Baseline.status == "published")
                    .where(Baseline.effective_from <= start_time)
                    .order_by(
                        Baseline.is_default.desc(),
                        Baseline.effective_from.desc(),
                        Baseline.published_at.desc(),
                        Baseline.updated_at.desc(),
                    )
                )
            ).scalars()
        )
    return baselines


async def _list_all_published_baselines() -> list[Baseline]:
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(Baseline)
                    .where(Baseline.status == "published")
                    .order_by(
                        Baseline.is_default.desc(),
                        Baseline.effective_from.desc(),
                        Baseline.published_at.desc(),
                        Baseline.updated_at.desc(),
                    )
                )
            ).scalars()
        )
    return rows


def _eligible_published_baselines(
    published_baselines: list[Baseline],
    *,
    start_time: datetime,
) -> list[Baseline]:
    return [baseline for baseline in published_baselines if baseline.effective_from <= start_time]


def _resolve_primary_baseline(
    baselines: list[Any],
    *,
    preferred_baseline_id: str | None = None,
) -> Any | None:
    if not baselines:
        return None
    if preferred_baseline_id:
        preferred = next(
            (
                baseline
                for baseline in baselines
                if encode_baseline_id(
                    str(_baseline_field(baseline, "definition_id") or ""),
                    str(_baseline_field(baseline, "item") or ""),
                )
                == preferred_baseline_id
            ),
            None,
        )
        if preferred is not None:
            return preferred
    default_baseline = next(
        (baseline for baseline in baselines if bool(_baseline_field(baseline, "is_default"))),
        None,
    )
    if default_baseline is not None:
        return default_baseline
    return baselines[0]


def _seed_binding_analysis(
    *,
    baseline: Any,
    primary_baseline: Any | None,
    candidate_baseline_id: str | None,
    candidate_deviation_score: float | None,
    candidate_avg_deviation_score: float | None,
    candidate_abnormal_duration_minutes: float | None,
    candidate_analysis_details_json: str | None,
    candidate_analysis_status: str | None,
    candidate_analysis_reason: str | None,
    candidate_analysis_message: str | None,
) -> dict[str, Any]:
    baseline_id = encode_baseline_id(
        str(_baseline_field(baseline, "definition_id") or ""),
        str(_baseline_field(baseline, "item") or ""),
    )
    primary_baseline_id = (
        encode_baseline_id(
            str(_baseline_field(primary_baseline, "definition_id") or ""),
            str(_baseline_field(primary_baseline, "item") or ""),
        )
        if primary_baseline is not None
        else None
    )
    should_seed = False
    if candidate_baseline_id and candidate_baseline_id == baseline_id:
        should_seed = True
    elif candidate_baseline_id is None and primary_baseline_id == baseline_id:
        should_seed = True

    if not should_seed:
        return {
            "analysis_status": "waiting",
            "analysis_reason": "metric_inputs_missing",
            "analysis_message": "当前数据尚未准备完成，暂无法计算偏离度",
            "deviation_score": None,
            "avg_deviation_score": None,
            "abnormal_duration_minutes": None,
            "analysis_details_json": None,
        }

    analysis_status = (
        str(candidate_analysis_status)
        if candidate_analysis_status is not None
        else ("ready" if candidate_deviation_score is not None else "waiting")
    )
    analysis_reason = candidate_analysis_reason
    analysis_message = candidate_analysis_message
    if analysis_status != "ready" and not analysis_reason:
        analysis_reason = "metric_inputs_missing"
    if analysis_status != "ready" and not analysis_message:
        analysis_message = "当前数据尚未准备完成，暂无法计算偏离度"
    return {
        "analysis_status": analysis_status,
        "analysis_reason": analysis_reason,
        "analysis_message": analysis_message,
        "deviation_score": candidate_deviation_score,
        "avg_deviation_score": candidate_avg_deviation_score,
        "abnormal_duration_minutes": candidate_abnormal_duration_minutes,
        "analysis_details_json": candidate_analysis_details_json,
    }


def _build_binding_payloads(
    *,
    heat_id: str,
    applicable_baselines: list[Any],
    candidate: dict[str, Any],
    created_at: datetime,
    updated_at: datetime,
) -> tuple[list[dict[str, Any]], str | None]:
    existing_bindings = candidate.get("baseline_bindings")
    if isinstance(existing_bindings, list) and existing_bindings:
        payloads: list[dict[str, Any]] = []
        primary_definition_id: str | None = None
        for binding in existing_bindings:
            if not isinstance(binding, dict):
                continue
            baseline_definition_id = str(binding.get("baseline_definition_id") or "")
            baseline_item = str(binding.get("baseline_item") or "")
            if not baseline_definition_id or not baseline_item:
                continue
            if bool(binding.get("is_primary")):
                primary_definition_id = baseline_definition_id
            payloads.append(
                {
                    "heat_id": heat_id,
                    "baseline_definition_id": baseline_definition_id,
                    "baseline_item": baseline_item,
                    "is_primary": bool(binding.get("is_primary")),
                    "effective_from_snapshot": binding.get("baseline_effective_from"),
                    "tolerance_percent_snapshot": binding.get("tolerance_percent"),
                    "analysis_status": str(binding.get("analysis_status") or "waiting"),
                    "analysis_reason": (
                        str(binding.get("analysis_reason"))
                        if binding.get("analysis_reason") is not None
                        else None
                    ),
                    "analysis_message": (
                        str(binding.get("analysis_message"))
                        if binding.get("analysis_message") is not None
                        else None
                    ),
                    "deviation_score": binding.get("deviation_score"),
                    "avg_deviation_score": binding.get("avg_deviation_score"),
                    "analysis_details_json": binding.get("analysis_details_json"),
                    "abnormal_duration_minutes": binding.get("abnormal_duration_minutes"),
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
        if payloads:
            return payloads, primary_definition_id

    primary_baseline = _resolve_primary_baseline(applicable_baselines)
    primary_definition_id = (
        str(_baseline_field(primary_baseline, "definition_id") or "")
        if primary_baseline is not None
        else None
    )
    candidate_baseline_id = (
        str(candidate.get("baseline_id")).strip() if candidate.get("baseline_id") else None
    )
    payloads: list[dict[str, Any]] = []
    for baseline in applicable_baselines:
        seeded = _seed_binding_analysis(
            baseline=baseline,
            primary_baseline=primary_baseline,
            candidate_baseline_id=candidate_baseline_id,
            candidate_deviation_score=candidate.get("deviation_score"),
            candidate_avg_deviation_score=candidate.get("avg_deviation_score"),
            candidate_abnormal_duration_minutes=candidate.get("abnormal_duration_minutes"),
            candidate_analysis_details_json=candidate.get("analysis_details_json"),
            candidate_analysis_status=(
                str(candidate.get("analysis_status"))
                if candidate.get("analysis_status") is not None
                else None
            ),
            candidate_analysis_reason=(
                str(candidate.get("analysis_reason"))
                if candidate.get("analysis_reason") is not None
                else None
            ),
            candidate_analysis_message=(
                str(candidate.get("analysis_message"))
                if candidate.get("analysis_message") is not None
                else None
            ),
        )
        payloads.append(
            {
                "heat_id": heat_id,
                "baseline_definition_id": str(_baseline_field(baseline, "definition_id") or ""),
                "baseline_item": str(_baseline_field(baseline, "item") or ""),
                "is_primary": (
                    primary_baseline is not None
                    and str(_baseline_field(baseline, "definition_id") or "")
                    == str(_baseline_field(primary_baseline, "definition_id") or "")
                    and str(_baseline_field(baseline, "item") or "")
                    == str(_baseline_field(primary_baseline, "item") or "")
                ),
                "effective_from_snapshot": _baseline_field(baseline, "effective_from"),
                "tolerance_percent_snapshot": _baseline_field(baseline, "tolerance_percent"),
                "analysis_status": str(seeded["analysis_status"]),
                "analysis_reason": seeded["analysis_reason"],
                "analysis_message": seeded["analysis_message"],
                "deviation_score": seeded["deviation_score"],
                "avg_deviation_score": seeded["avg_deviation_score"],
                "analysis_details_json": seeded["analysis_details_json"],
                "abnormal_duration_minutes": seeded["abnormal_duration_minutes"],
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
    return payloads, primary_definition_id


def _candidate_definition_metric_templates(
    candidate: dict[str, Any],
    *,
    primary_definition_id: str | None,
    template_map: dict[str, list[BaselineDefinitionMetric]],
) -> list[Any]:
    raw_snapshots = candidate.get("definition_metric_snapshots")
    raw_birth_context = candidate.get("birth_context")
    if isinstance(raw_birth_context, dict) and isinstance(
        raw_birth_context.get("definition_metric_snapshots"),
        list,
    ):
        raw_snapshots = raw_birth_context.get("definition_metric_snapshots")
    if isinstance(raw_snapshots, list) and raw_snapshots:
        return [snapshot for snapshot in raw_snapshots if isinstance(snapshot, dict)]
    return template_map.get(primary_definition_id or "", [])


def _build_metric_series_payloads(
    *,
    heat_payload: dict[str, Any],
    candidate: dict[str, Any],
    primary_definition_id: str | None,
    template_map: dict[str, list[BaselineDefinitionMetric]],
    require_heat_window_coverage: bool = False,
) -> list[dict[str, Any]]:
    templates = _candidate_definition_metric_templates(
        candidate,
        primary_definition_id=primary_definition_id,
        template_map=template_map,
    )
    runtime_series = candidate.get("runtime_metric_series")
    if not isinstance(runtime_series, list) or not runtime_series:
        log_event(
            "runtime_metric_series_persist_error",
            heat_id=str(candidate.get("id") or ""),
            error="runtime_metric_series_missing",
        )
        raise ValueError("runtime_metric_series_missing")

    template_by_metric_key = {
        str(spec["metric_key"]): spec
        for template in templates
        if (spec := _template_series_spec(template)) is not None
    }
    if not template_by_metric_key:
        log_event(
            "runtime_metric_series_persist_error",
            heat_id=str(candidate.get("id") or ""),
            error="definition_metric_templates_missing",
        )
        raise ValueError("definition_metric_templates_missing")

    if require_heat_window_coverage:
        missing_heat_window_metric_keys = missing_metric_keys_in_window(
            curves_by_metric=_candidate_metric_curve_map(candidate),
            required_metric_keys=list(template_by_metric_key),
            window_start=heat_payload["start_time"],
            window_end=heat_payload["end_time"],
        )
        if missing_heat_window_metric_keys:
            log_event(
                "runtime_metric_series_persist_error",
                heat_id=str(candidate.get("id") or ""),
                error="runtime_metric_series_missing_heat_window",
                missing_metric_keys=missing_heat_window_metric_keys,
            )
            raise ValueError("runtime_metric_series_missing_heat_window")

    metric_payloads: list[dict[str, Any]] = []
    persisted_metric_keys: list[str] = []
    for entry in runtime_series:
        if not isinstance(entry, dict):
            continue
        metric_key = str(entry.get("metric_key") or "").strip().lower()
        if not metric_key:
            continue
        spec = template_by_metric_key.get(metric_key)
        if spec is None:
            log_event(
                "runtime_metric_series_persist_error",
                heat_id=str(candidate.get("id") or ""),
                error="definition_metric_template_missing_for_runtime_metric",
                metric_key=metric_key,
            )
            raise ValueError("definition_metric_template_missing_for_runtime_metric")
        series_payload = entry.get("series_json")
        stat_payload = entry.get("stat_json")
        metric_payloads.append(
            {
                "owner_key": encode_heat_owner_key(str(heat_payload["id"])),
                "item": str(entry.get("item") or spec["item"]),
                "owner_type": "heat",
                "definition_id": primary_definition_id,
                "item_kind": "metric_item",
                "metric_key": metric_key,
                "metric_name": str(entry.get("metric_name") or spec["metric_name"]),
                "unit": entry.get("unit", spec.get("unit")),
                "color": str(entry.get("color") or spec["color"]),
                "sort_order": int(entry.get("sort_order") or spec["sort_order"]),
                "source_channel_id": entry.get("source_channel_id", spec.get("source_channel_id")),
                "source_channel_name": entry.get(
                    "source_channel_name",
                    spec.get("source_channel_name"),
                ),
                "source_channel_label": entry.get(
                    "source_channel_label",
                    spec.get("source_channel_label"),
                ),
                "series_json": (
                    _json_compact(series_payload)
                    if isinstance(series_payload, dict)
                    else str(series_payload or "")
                ),
                "stat_json": (
                    _json_compact(stat_payload)
                    if isinstance(stat_payload, dict)
                    else str(stat_payload or "")
                ),
                "created_at": heat_payload["created_at"],
                "updated_at": heat_payload["updated_at"],
            }
        )
        persisted_metric_keys.append(metric_key)

    missing_metric_keys = [
        metric_key
        for metric_key in template_by_metric_key
        if metric_key not in persisted_metric_keys
    ]
    if missing_metric_keys:
        log_event(
            "runtime_metric_series_persist_error",
            heat_id=str(candidate.get("id") or ""),
            error="runtime_metric_series_incomplete",
            missing_metric_keys=missing_metric_keys,
        )
        raise ValueError("runtime_metric_series_incomplete")
    return metric_payloads


def _build_preseal_payload_for_candidate(
    candidate: dict[str, Any],
    *,
    applicable_baselines: list[Any],
    template_map: dict[str, list[BaselineDefinitionMetric]],
    trigger_source: str,
    require_heat_window_coverage: bool = False,
) -> RuntimePresealPayload:
    furnace_id = (
        str(candidate.get("furnace_id") or candidate.get("_live_context_key") or "") or None
    )
    now = utc_now()
    heat_payload = {
        "id": str(candidate["id"]),
        "heat_no": str(candidate["heat_no"]),
        "description": candidate.get("description"),
        "furnace_id": furnace_id,
        "start_time": candidate["start_time"],
        "end_time": candidate["end_time"],
        "context_start_time": candidate.get("context_start_time") or candidate["start_time"],
        "context_end_time": candidate.get("context_end_time") or candidate["end_time"],
        "is_manually_adjusted": bool(candidate.get("is_manually_adjusted") or False),
        "sealed_at": now,
        "source_kind": str(candidate.get("record_source") or trigger_source),
        "cut_reason": candidate.get("cut_reason"),
        "cut_status": str(candidate.get("cut_status") or "normal"),
        "status": str(candidate.get("status") or "normal"),
        "created_by": "system",
        "updated_by": "system",
        "created_at": candidate.get("created_at") or now,
        "updated_at": now,
    }
    binding_payloads, primary_definition_id = _build_binding_payloads(
        heat_id=str(heat_payload["id"]),
        applicable_baselines=applicable_baselines,
        candidate=candidate,
        created_at=now,
        updated_at=now,
    )
    metric_series_payloads = _build_metric_series_payloads(
        heat_payload=heat_payload,
        candidate=candidate,
        primary_definition_id=primary_definition_id,
        template_map=template_map,
        require_heat_window_coverage=require_heat_window_coverage,
    )
    return RuntimePresealPayload(
        heat_payload=heat_payload,
        binding_payloads=binding_payloads,
        metric_series_payloads=metric_series_payloads,
    )


def build_runtime_preseal_payload(
    candidate: dict[str, Any],
    *,
    applicable_baselines: list[Any],
    trigger_source: str,
    require_heat_window_coverage: bool = False,
) -> RuntimePresealPayload:
    """基于当前 candidate 与已冻结 binding/template 快照生成待固化 payload。"""

    return _build_preseal_payload_for_candidate(
        candidate,
        applicable_baselines=applicable_baselines,
        template_map={},
        trigger_source=trigger_source,
        require_heat_window_coverage=require_heat_window_coverage,
    )


async def compile_runtime_candidates(
    candidates: list[dict[str, Any]],
    *,
    processing_mode: str = "live_incremental",
    trigger_source: str = "background_refresh",
    cutting_config: HeatCuttingConfig | None = None,
    metric_curve_loader: MetricCurveLoader | None = None,
    explicit_baselines: list[Any] | None = None,
    explicit_primary_baseline_id: str | None = None,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    published_baselines = (
        list(explicit_baselines)
        if explicit_baselines is not None
        else await _list_all_published_baselines()
    )
    definition_ids: set[str] = set()
    applicable_by_candidate: dict[str, list[Baseline]] = {}
    applicable_baselines: list[Baseline] = []
    for candidate in candidates:
        frozen_inputs = (
            _heat_runtime_factory.resolve_frozen_analysis_inputs(candidate)
            if _heat_runtime_factory.has_frozen_birth_context(candidate)
            else None
        )
        candidate_id = str(candidate["id"])
        applicable = (
            list(frozen_inputs.applicable_baselines)
            if frozen_inputs is not None
            else (
                list(published_baselines)
                if explicit_baselines is not None
                else _eligible_published_baselines(
                    published_baselines,
                    start_time=candidate["start_time"],
                )
            )
        )
        if not applicable:
            log_event(
                "runtime_candidate_compile_error",
                heat_id=candidate_id,
                error=(
                    "replay_explicit_baselines_missing"
                    if explicit_baselines is not None
                    else "published_baselines_missing"
                ),
            )
            raise ValueError(
                "replay_explicit_baselines_missing"
                if explicit_baselines is not None
                else "published_baselines_missing"
            )
        applicable_by_candidate[candidate_id] = applicable
        applicable_baselines.extend(applicable)
        for baseline in applicable:
            definition_id = str(_baseline_field(baseline, "definition_id") or "").strip()
            if definition_id:
                definition_ids.add(definition_id)
    template_map = await _load_definition_metric_templates(sorted(definition_ids))
    baseline_curve_payloads = await _heat_deviation_analysis_service.load_baseline_curve_payloads(
        applicable_baselines
    )

    prepared: list[dict[str, Any]] = []
    for candidate in candidates:
        prepared_candidate = dict(candidate)
        frozen_inputs = _heat_runtime_factory.resolve_frozen_analysis_inputs(prepared_candidate)
        candidate_applicable_baselines: list[Any]
        candidate_curve_payloads: dict[str, Any]
        baseline_metric_specs_by_id: dict[str, list[dict[str, Any]]]
        metric_union_specs: list[dict[str, Any]]
        if frozen_inputs is not None:
            candidate_applicable_baselines = frozen_inputs.applicable_baselines
            candidate_curve_payloads = frozen_inputs.baseline_curve_payloads
            metric_union_specs = resolve_runtime_hydrate_specs_from_frozen_inputs(
                prepared_candidate
            )
            baseline_metric_specs_by_id = resolve_runtime_baseline_metric_specs_from_frozen_inputs(
                prepared_candidate,
                applicable_baselines=candidate_applicable_baselines,
            )
            if not metric_union_specs or not baseline_metric_specs_by_id:
                log_event(
                    "runtime_candidate_compile_error",
                    heat_id=str(candidate.get("id") or ""),
                    error="runtime_birth_context_missing",
                )
                raise ValueError("runtime_birth_context_missing")
            prepared_candidate["definition_metric_snapshots"] = list(metric_union_specs)
            prepared_candidate["baseline_curve_snapshots"] = list(
                frozen_inputs.baseline_curve_snapshots
            )
        else:
            candidate_applicable_baselines = applicable_by_candidate[str(candidate["id"])]
            candidate_curve_payloads = baseline_curve_payloads
            primary_baseline = _resolve_primary_baseline(
                candidate_applicable_baselines,
                preferred_baseline_id=explicit_primary_baseline_id,
            )
            primary_definition_id = (
                str(_baseline_field(primary_baseline, "definition_id") or "")
                if primary_baseline is not None
                else str(prepared_candidate.get("baseline_definition_id") or "").strip()
            ) or None
            if primary_definition_id is not None:
                prepared_candidate["baseline_definition_id"] = primary_definition_id
            baseline_metric_specs_by_id = _build_baseline_metric_spec_map(
                applicable_baselines=candidate_applicable_baselines,
                template_map=template_map,
            )
            metric_union_specs = _build_runtime_metric_union_specs(baseline_metric_specs_by_id)
            if not metric_union_specs:
                log_event(
                    "runtime_candidate_compile_error",
                    heat_id=str(candidate.get("id") or ""),
                    error="definition_metric_templates_missing",
                    definition_id=primary_definition_id,
                )
                raise ValueError("definition_metric_templates_missing")
        prepared_candidate = await hydrate_candidate_runtime_metric_series(
            prepared_candidate,
            metric_specs=metric_union_specs,
            metric_curve_loader=metric_curve_loader,
        )
        prepared_candidate["definition_metric_snapshots"] = (
            _heat_runtime_factory._build_definition_metric_snapshots(metric_union_specs)
        )
        prepared_candidate["baseline_views"] = _build_runtime_baseline_views(
            candidate=prepared_candidate,
            applicable_baselines=candidate_applicable_baselines,
            baseline_metric_specs_by_id=baseline_metric_specs_by_id,
        )
        binding_analyses = _heat_deviation_analysis_service.analyze_candidate_bindings(
            candidate=prepared_candidate,
            applicable_baselines=candidate_applicable_baselines,
            baseline_curve_payloads=candidate_curve_payloads,
        )
        prepared_candidate = _heat_deviation_analysis_service.apply_binding_analysis_to_candidate(
            candidate=prepared_candidate,
            binding_analyses=binding_analyses,
        )
        prepared_candidate["baseline_views"] = _build_runtime_baseline_views(
            candidate=prepared_candidate,
            applicable_baselines=candidate_applicable_baselines,
            baseline_metric_specs_by_id=baseline_metric_specs_by_id,
        )
        if frozen_inputs is None:
            primary_definition_id = (
                str(prepared_candidate.get("baseline_definition_id") or "").strip() or None
            )
            birth_snapshot = _heat_runtime_factory.build_birth_snapshot(
                prepared_candidate,
                applicable_baselines=candidate_applicable_baselines,
                definition_templates=metric_union_specs,
                baseline_curve_payloads=baseline_curve_payloads,
                cutting_config=(
                    cutting_config
                    or _heat_runtime_factory.resolve_frozen_cutting_config(prepared_candidate)
                    or HeatCuttingConfig(
                        time_tolerance_percent=0.0,
                        major_issue_duration_minutes=0,
                        plant_timezone=str(prepared_candidate.get("_live_plant_timezone") or ""),
                        work_start_time="00:00",
                        work_end_time="23:59",
                        break_periods=(),
                        cutting_mode=str(
                            prepared_candidate.get("_live_cutting_mode") or "fixed_interval"
                        ),
                        fixed_interval_minutes=30,
                    )
                ),
            )
            prepared_candidate["birth_context"] = birth_snapshot.birth_context
            prepared_candidate["definition_metric_snapshots"] = list(
                birth_snapshot.definition_metric_snapshots
            )
            prepared_candidate["baseline_curve_snapshots"] = list(
                birth_snapshot.baseline_curve_snapshots
            )
        processing_meta = dict(prepared_candidate.get("processing_meta") or {})
        if not processing_meta:
            processing_meta = {
                "processing_mode": processing_mode,
                "trigger_source": trigger_source,
                "request_anchor_time": candidate.get("start_time"),
                "batch_cursor": None,
                "last_processed_heat_id": str(candidate["id"]),
            }
        prepared_candidate["processing_meta"] = processing_meta
        prepared_candidate["preseal_payload"] = _build_preseal_payload_for_candidate(
            prepared_candidate,
            applicable_baselines=candidate_applicable_baselines,
            template_map=template_map,
            trigger_source=trigger_source,
        ).to_dict()
        prepared.append(prepared_candidate)
    return prepared


async def append_sealed_heats(
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not candidates:
        return {}

    prepared_candidates = [
        dict(candidate)
        for candidate in (
            candidates
            if all(isinstance(candidate.get("preseal_payload"), dict) for candidate in candidates)
            else await compile_runtime_candidates(candidates)
        )
    ]
    persisted: dict[str, dict[str, Any]] = {}
    persisted_ids: list[str] = []
    candidate_ids = [str(candidate["id"]) for candidate in prepared_candidates]
    async with async_session_maker() as session:
        existing_ids = set(
            (await session.execute(select(Heat.id).where(Heat.id.in_(candidate_ids)))).scalars()
        )
    async with async_session_maker() as session:
        seen_new_ids: set[str] = set()
        for candidate in prepared_candidates:
            candidate_id = str(candidate["id"])
            if candidate_id in existing_ids or candidate_id in seen_new_ids:
                continue
            frozen_inputs = _heat_runtime_factory.resolve_frozen_analysis_inputs(candidate)
            payload = (
                build_runtime_preseal_payload(
                    candidate,
                    applicable_baselines=frozen_inputs.applicable_baselines,
                    trigger_source=str(candidate.get("record_source") or "sealed_history"),
                    require_heat_window_coverage=True,
                ).to_dict()
                if frozen_inputs is not None
                else (candidate.get("preseal_payload") or {})
            )
            heat_payload = dict(payload.get("heat_payload") or {})
            if not heat_payload:
                continue
            session.add(Heat(**heat_payload))
            for binding_payload in payload.get("binding_payloads") or []:
                session.add(HeatBaselineBinding(**binding_payload))
            for metric_payload in payload.get("metric_series_payloads") or []:
                session.add(MetricSeries(**metric_payload))
            persisted_ids.append(candidate_id)
            seen_new_ids.add(candidate_id)

        await session.commit()

    for heat_id in [*sorted(existing_ids), *persisted_ids]:
        persisted_dict = await get_formal_heat_record(heat_id)
        if persisted_dict is not None:
            persisted[heat_id] = persisted_dict

    return persisted


async def replace_heat_range(
    *,
    anchor_time: datetime,
    end_time: datetime,
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    prepared_candidates = [
        dict(candidate)
        for candidate in (
            candidates
            if all(isinstance(candidate.get("preseal_payload"), dict) for candidate in candidates)
            else await compile_runtime_candidates(
                candidates,
                processing_mode="replay_batch",
                trigger_source="replay_batch",
            )
        )
    ]
    insertable_candidates = [
        candidate
        for candidate in prepared_candidates
        if candidate.get("start_time") is not None
        and candidate.get("end_time") is not None
        and candidate["end_time"] >= anchor_time
        and candidate["start_time"] <= end_time
    ]

    async with async_session_maker() as session:
        affected_heat_ids = list(
            (
                await session.execute(
                    select(Heat.id)
                    .where(Heat.end_time >= anchor_time)
                    .where(Heat.start_time <= end_time)
                )
            ).scalars()
        )

        if affected_heat_ids:
            await session.execute(
                delete(MetricSeries)
                .where(MetricSeries.owner_type == "heat")
                .where(MetricSeries.owner_key.in_(affected_heat_ids))
            )
            await session.execute(
                delete(HeatBaselineBinding).where(
                    HeatBaselineBinding.heat_id.in_(affected_heat_ids)
                )
            )
            await session.execute(delete(Heat).where(Heat.id.in_(affected_heat_ids)))

        for candidate in insertable_candidates:
            frozen_inputs = _heat_runtime_factory.resolve_frozen_analysis_inputs(candidate)
            payload = (
                build_runtime_preseal_payload(
                    candidate,
                    applicable_baselines=frozen_inputs.applicable_baselines,
                    trigger_source=str(candidate.get("record_source") or "sealed_history"),
                    require_heat_window_coverage=True,
                ).to_dict()
                if frozen_inputs is not None
                else (candidate.get("preseal_payload") or {})
            )
            heat_payload = dict(payload.get("heat_payload") or {})
            if not heat_payload:
                continue
            session.add(Heat(**heat_payload))
            for binding_payload in payload.get("binding_payloads") or []:
                session.add(HeatBaselineBinding(**binding_payload))
            for metric_payload in payload.get("metric_series_payloads") or []:
                session.add(MetricSeries(**metric_payload))

        await session.commit()

    persisted: dict[str, dict[str, Any]] = {}
    for candidate in insertable_candidates:
        heat_id = str(candidate["id"])
        persisted_record = await get_formal_heat_record(heat_id)
        if persisted_record is not None:
            persisted[heat_id] = persisted_record
    return persisted


async def replace_heat_range_from_preseal_candidates(
    *,
    anchor_time: datetime,
    end_time: datetime,
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if any(not isinstance(candidate.get("preseal_payload"), dict) for candidate in candidates):
        raise ValueError("replay_preseal_payload_missing")
    return await replace_heat_range(
        anchor_time=anchor_time,
        end_time=end_time,
        candidates=candidates,
    )


async def prepare_runtime_candidates_for_persist(
    candidates: list[dict[str, Any]],
    *,
    processing_mode: str = "live_incremental",
    trigger_source: str = "background_refresh",
) -> list[dict[str, Any]]:
    """兼容旧调用名，语义等同于 compile_runtime_candidates。"""

    return await compile_runtime_candidates(
        candidates,
        processing_mode=processing_mode,
        trigger_source=trigger_source,
    )


async def persist_sealed_heat_candidates(
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """兼容旧调用名，语义等同于 append_sealed_heats。"""

    return await append_sealed_heats(candidates)
