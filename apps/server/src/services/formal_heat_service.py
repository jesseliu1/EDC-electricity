"""正式历史炉次服务。"""

from __future__ import annotations

import json
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
from ..schemas.common import CurvePoint
from ..time_utils import from_timestamp_ms, to_timestamp_ms, utc_now
from .formal_baseline_service import decode_baseline_id, encode_baseline_id
from .heat_runtime_types import RuntimePresealPayload

DEFAULT_METRIC_SPECS: dict[str, dict[str, Any]] = {
    "power": {
        "item": "001",
        "metric_key": "power",
        "metric_name": "总有功功率",
        "unit": "kW",
        "color": "#409EFF",
        "sort_order": 1,
    },
    "voltage": {
        "item": "002",
        "metric_key": "voltage",
        "metric_name": "A相电压",
        "unit": "V",
        "color": "#67C23A",
        "sort_order": 2,
    },
}


def encode_heat_owner_key(heat_id: str) -> str:
    """生成 heat 指标值 owner_key。"""

    return heat_id


def _normalize_curve_points(points: list[Any] | None) -> list[CurvePoint]:
    normalized: list[CurvePoint] = []
    for point in points or []:
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


def _metric_kind_for_series(series: MetricSeries) -> str:
    if series.metric_key:
        lowered = series.metric_key.lower()
        if lowered in {"power", "voltage", "temperature", "pressure"}:
            return lowered
    return infer_metric_kind(series.metric_name, series.unit or "")


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
        "deviation_percent": binding.deviation_percent,
        "avg_deviation_percent": binding.avg_deviation_percent,
        "deviation_details_json": binding.deviation_details_json,
        "time_offset_percent": binding.time_offset_percent,
        "mismatch_duration_minutes": binding.mismatch_duration_minutes,
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

    power_curve = _metric_series_points(series_by_kind["power"]) if "power" in series_by_kind else []
    voltage_curve = (
        _metric_series_points(series_by_kind["voltage"]) if "voltage" in series_by_kind else []
    )
    context_start_time, context_end_time = _context_boundaries_from_series(series_rows)
    ordered_bindings = sorted(bindings, key=_binding_sort_key, reverse=True)
    primary_binding = _select_primary_binding(ordered_bindings)
    primary_baseline_id = (
        encode_baseline_id(primary_binding.baseline_definition_id, primary_binding.baseline_item)
        if primary_binding is not None
        else None
    )
    binding_views = [_binding_to_dict(binding) for binding in ordered_bindings]

    return {
        "id": heat.id,
        "heat_no": heat.heat_no,
        "description": heat.description,
        "furnace_id": heat.furnace_id,
        "start_time": heat.start_time,
        "end_time": heat.end_time,
        "context_start_time": context_start_time or heat.context_start_time,
        "context_end_time": context_end_time or heat.context_end_time,
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
        "deviation_percent": (
            primary_binding.deviation_percent if primary_binding is not None else None
        ),
        "avg_deviation_percent": (
            primary_binding.avg_deviation_percent if primary_binding is not None else None
        ),
        "time_offset_percent": (
            primary_binding.time_offset_percent if primary_binding is not None else None
        ),
        "mismatch_duration_minutes": (
            primary_binding.mismatch_duration_minutes if primary_binding is not None else None
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


def _serialize_deviation_details(abnormal_ranges: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"abnormal_ranges": abnormal_ranges},
        ensure_ascii=False,
        separators=(",", ":"),
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
            primary_binding.mismatch_duration_minutes = min(
                primary_binding.mismatch_duration_minutes or 0,
                4,
            )
            primary_binding.time_offset_percent = min(
                primary_binding.time_offset_percent or 0.0,
                8.0,
            )
            primary_binding.updated_at = utc_now()

        await session.commit()

    return await get_formal_heat_record(heat_id)


async def save_formal_heat_analysis(
    heat_id: str,
    *,
    baseline_id: str,
    max_deviation: float,
    avg_deviation: float,
    status: str,
    abnormal_ranges: list[dict[str, Any]],
    updated_by: str = "system",
) -> dict[str, Any] | None:
    baseline_definition_id, baseline_item = decode_baseline_id(baseline_id)
    async with async_session_maker() as session:
        heat = await session.get(Heat, heat_id)
        if heat is None:
            return None

        binding = await session.get(
            HeatBaselineBinding,
            {
                "heat_id": heat_id,
                "baseline_definition_id": baseline_definition_id,
                "baseline_item": baseline_item,
            },
        )
        if binding is None:
            return None

        binding.analysis_status = "ready"
        binding.deviation_percent = max_deviation
        binding.avg_deviation_percent = avg_deviation
        binding.deviation_details_json = _serialize_deviation_details(abnormal_ranges)
        binding.updated_at = utc_now()

        if binding.is_primary:
            heat.status = status
            heat.updated_by = updated_by
            heat.updated_at = utc_now()

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


def _pick_metric_template(
    templates: list[BaselineDefinitionMetric],
    *,
    metric_kind: str,
) -> BaselineDefinitionMetric | None:
    exact = next(
        (row for row in templates if str(row.metric_key).strip().lower() == metric_kind),
        None,
    )
    if exact is not None:
        return exact
    inferred = [
        row for row in templates if infer_metric_kind(row.metric_name, row.unit or "") == metric_kind
    ]
    return inferred[0] if inferred else None


def _default_metric_spec(metric_kind: str) -> dict[str, Any]:
    spec = DEFAULT_METRIC_SPECS.get(metric_kind)
    if spec is None:
        return {
            "item": "999",
            "metric_key": metric_kind,
            "metric_name": metric_kind,
            "unit": None,
            "color": "#909399",
            "sort_order": 99,
        }
    return dict(spec)


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
    baselines: list[Baseline],
) -> Baseline | None:
    if not baselines:
        return None
    default_baseline = next((baseline for baseline in baselines if baseline.is_default), None)
    if default_baseline is not None:
        return default_baseline
    return baselines[0]


def _seed_binding_analysis(
    *,
    baseline: Baseline,
    primary_baseline: Baseline | None,
    candidate_baseline_id: str | None,
    candidate_deviation_percent: float | None,
    candidate_avg_deviation_percent: float | None,
    candidate_time_offset_percent: float | None,
    candidate_mismatch_duration_minutes: float | None,
) -> dict[str, Any]:
    baseline_id = encode_baseline_id(baseline.definition_id, baseline.item)
    primary_baseline_id = (
        encode_baseline_id(primary_baseline.definition_id, primary_baseline.item)
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
            "analysis_status": "pending",
            "deviation_percent": None,
            "avg_deviation_percent": None,
            "time_offset_percent": None,
            "mismatch_duration_minutes": None,
        }

    analysis_status = "ready" if candidate_deviation_percent is not None else "pending"
    return {
        "analysis_status": analysis_status,
        "deviation_percent": candidate_deviation_percent,
        "avg_deviation_percent": candidate_avg_deviation_percent,
        "time_offset_percent": candidate_time_offset_percent,
        "mismatch_duration_minutes": candidate_mismatch_duration_minutes,
    }


def _build_binding_payloads(
    *,
    heat_id: str,
    applicable_baselines: list[Baseline],
    candidate: dict[str, Any],
    created_at: datetime,
    updated_at: datetime,
) -> tuple[list[dict[str, Any]], str | None]:
    primary_baseline = _resolve_primary_baseline(applicable_baselines)
    primary_definition_id = primary_baseline.definition_id if primary_baseline is not None else None
    candidate_baseline_id = (
        str(candidate.get("baseline_id")).strip() if candidate.get("baseline_id") else None
    )
    payloads: list[dict[str, Any]] = []
    for baseline in applicable_baselines:
        seeded = _seed_binding_analysis(
            baseline=baseline,
            primary_baseline=primary_baseline,
            candidate_baseline_id=candidate_baseline_id,
            candidate_deviation_percent=candidate.get("deviation_percent"),
            candidate_avg_deviation_percent=candidate.get("avg_deviation_percent"),
            candidate_time_offset_percent=candidate.get("time_offset_percent"),
            candidate_mismatch_duration_minutes=candidate.get("mismatch_duration_minutes"),
        )
        payloads.append(
            {
                "heat_id": heat_id,
                "baseline_definition_id": baseline.definition_id,
                "baseline_item": baseline.item,
                "is_primary": (
                    primary_baseline is not None
                    and baseline.definition_id == primary_baseline.definition_id
                    and baseline.item == primary_baseline.item
                ),
                "effective_from_snapshot": baseline.effective_from,
                "tolerance_percent_snapshot": baseline.tolerance_percent,
                "analysis_status": str(seeded["analysis_status"]),
                "deviation_percent": seeded["deviation_percent"],
                "avg_deviation_percent": seeded["avg_deviation_percent"],
                "deviation_details_json": None,
                "time_offset_percent": seeded["time_offset_percent"],
                "mismatch_duration_minutes": seeded["mismatch_duration_minutes"],
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
    return payloads, primary_definition_id


def _build_metric_series_payloads(
    *,
    heat_payload: dict[str, Any],
    candidate: dict[str, Any],
    primary_definition_id: str | None,
    template_map: dict[str, list[BaselineDefinitionMetric]],
) -> list[dict[str, Any]]:
    templates = template_map.get(primary_definition_id or "", [])
    metric_payloads: list[dict[str, Any]] = []
    for metric_kind, curve_field in (("power", "power_curve"), ("voltage", "voltage_curve")):
        points = _normalize_curve_points(candidate.get(curve_field))
        if not points:
            continue
        template = _pick_metric_template(templates, metric_kind=metric_kind)
        if template is not None:
            spec = {
                "item": template.item,
                "metric_key": template.metric_key,
                "metric_name": template.metric_name,
                "unit": template.unit,
                "color": template.color,
                "sort_order": template.sort_order,
            }
        else:
            spec = _default_metric_spec(metric_kind)
        metric_payloads.append(
            {
                "owner_key": encode_heat_owner_key(str(heat_payload["id"])),
                "item": str(spec["item"]),
                "owner_type": "heat",
                "definition_id": primary_definition_id,
                "item_kind": "metric_item",
                "metric_key": str(spec["metric_key"]),
                "metric_name": str(spec["metric_name"]),
                "unit": spec.get("unit"),
                "color": str(spec["color"]),
                "sort_order": int(spec["sort_order"]),
                "source_channel_id": None,
                "source_channel_name": None,
                "source_channel_label": None,
                "series_json": _build_series_payload(
                    context_start_time=heat_payload["context_start_time"],
                    heat_start_time=heat_payload["start_time"],
                    heat_end_time=heat_payload["end_time"],
                    context_end_time=heat_payload["context_end_time"],
                    points=points,
                ),
                "stat_json": _json_compact(
                    {
                        "metric_kind": metric_kind,
                        "heat_min": min(float(point.value) for point in points),
                        "heat_max": max(float(point.value) for point in points),
                        "heat_avg": round(
                            sum(float(point.value) for point in points) / max(len(points), 1),
                            4,
                        ),
                    }
                ),
                "created_at": heat_payload["created_at"],
                "updated_at": heat_payload["updated_at"],
            }
        )
    return metric_payloads


def _build_preseal_payload_for_candidate(
    candidate: dict[str, Any],
    *,
    applicable_baselines: list[Baseline],
    template_map: dict[str, list[BaselineDefinitionMetric]],
    trigger_source: str,
) -> RuntimePresealPayload:
    furnace_id = str(candidate.get("furnace_id") or candidate.get("_live_context_key") or "") or None
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
    )
    return RuntimePresealPayload(
        heat_payload=heat_payload,
        binding_payloads=binding_payloads,
        metric_series_payloads=metric_series_payloads,
    )


async def compile_runtime_candidates(
    candidates: list[dict[str, Any]],
    *,
    processing_mode: str = "live_incremental",
    trigger_source: str = "background_refresh",
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    published_baselines = await _list_all_published_baselines()
    definition_ids: set[str] = set()
    applicable_by_candidate: dict[str, list[Baseline]] = {}
    for candidate in candidates:
        candidate_id = str(candidate["id"])
        applicable = _eligible_published_baselines(
            published_baselines,
            start_time=candidate["start_time"],
        )
        applicable_by_candidate[candidate_id] = applicable
        primary_baseline = _resolve_primary_baseline(applicable)
        if primary_baseline is not None:
            definition_ids.add(primary_baseline.definition_id)
    template_map = await _load_definition_metric_templates(sorted(definition_ids))

    prepared: list[dict[str, Any]] = []
    for candidate in candidates:
        prepared_candidate = dict(candidate)
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
            applicable_baselines=applicable_by_candidate[str(candidate["id"])],
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
            (
                await session.execute(select(Heat.id).where(Heat.id.in_(candidate_ids)))
            ).scalars()
        )
    async with async_session_maker() as session:
        seen_new_ids: set[str] = set()
        for candidate in prepared_candidates:
            candidate_id = str(candidate["id"])
            if candidate_id in existing_ids or candidate_id in seen_new_ids:
                continue
            payload = candidate.get("preseal_payload") or {}
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
                delete(HeatBaselineBinding).where(HeatBaselineBinding.heat_id.in_(affected_heat_ids))
            )
            await session.execute(delete(Heat).where(Heat.id.in_(affected_heat_ids)))

        for candidate in insertable_candidates:
            payload = candidate.get("preseal_payload") or {}
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
