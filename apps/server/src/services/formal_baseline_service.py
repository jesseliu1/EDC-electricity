"""基线正式表服务。"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select

from ..channel_roles import infer_metric_kind
from ..database import async_session_maker
from ..models import (
    Baseline,
    BaselineDefinition,
    BaselineDefinitionMetric,
    MetricSeries,
)
from ..schemas.common import CurvePoint
from ..time_utils import to_timestamp_ms, utc_now

BASELINE_KEY_SEPARATOR = ":"


def encode_baseline_id(definition_id: str, item: str) -> str:
    """生成对前端兼容的基线复合键。"""
    return f"{definition_id}{BASELINE_KEY_SEPARATOR}{item}"


def decode_baseline_id(baseline_id: str) -> tuple[str, str]:
    """解析前端使用的基线复合键。"""
    definition_id, separator, item = baseline_id.rpartition(BASELINE_KEY_SEPARATOR)
    if not separator or not definition_id or not item:
        raise ValueError("invalid baseline id")
    return definition_id, item


def _metric_to_dict(metric: BaselineDefinitionMetric) -> dict[str, Any]:
    return {
        "id": metric.item,
        "item": metric.item,
        "metric_key": metric.metric_key,
        "name": metric.metric_name,
        "unit": metric.unit,
        "color": metric.color,
        "sort_order": metric.sort_order,
        "edc_channel_id": metric.edc_channel_id,
        "source_channel_name": metric.source_channel_name,
        "source_channel_label": metric.source_channel_label,
        "enabled": metric.enabled,
    }


def _definition_to_dict(
    definition: BaselineDefinition,
    metrics: list[BaselineDefinitionMetric],
) -> dict[str, Any]:
    return {
        "id": definition.id,
        "definition_name": definition.definition_name,
        "description": definition.description,
        "expected_duration_minutes": definition.expected_duration_minutes,
        "status": definition.status,
        "metrics": [_metric_to_dict(metric) for metric in metrics],
        "created_at": definition.created_at,
        "updated_at": definition.updated_at,
    }


def _baseline_to_dict(
    baseline: Baseline,
    *,
    definition_name: str = "",
) -> dict[str, Any]:
    return {
        "id": encode_baseline_id(baseline.definition_id, baseline.item),
        "definition_id": baseline.definition_id,
        "item": baseline.item,
        "name": baseline.name,
        "description": baseline.description,
        "status": baseline.status or "",
        "is_default": bool(baseline.is_default),
        "source_heat_id": baseline.source_heat_id,
        "selected_start_time": baseline.selected_start_time,
        "selected_end_time": baseline.selected_end_time,
        "effective_from": baseline.effective_from,
        "tolerance_percent": baseline.tolerance_percent,
        "version": int(baseline.item),
        "curve_seed": sum(ord(char) for char in encode_baseline_id(baseline.definition_id, baseline.item)) % 97 + 9,
        "created_at": baseline.created_at,
        "updated_at": baseline.updated_at,
        "published_at": baseline.published_at,
        "curve_source": "none",
        "curves_data": [],
        "power_curve": [],
        "voltage_curve": [],
        "temperature": None,
        "definition_name": definition_name,
    }


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


def _slice_curve_points(
    points: list[CurvePoint],
    *,
    start_time: datetime,
    end_time: datetime,
) -> list[CurvePoint]:
    start_ts = to_timestamp_ms(start_time)
    end_ts = to_timestamp_ms(end_time)
    return [point for point in points if start_ts <= int(point.timestamp) <= end_ts]


def _baseline_owner_key(definition_id: str, item: str) -> str:
    return encode_baseline_id(definition_id, item)


def _build_series_payload(points: list[CurvePoint]) -> str:
    return json.dumps(
        {
            "points": [
                {"timestamp": int(point.timestamp), "value": float(point.value)}
                for point in points
            ]
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _build_stat_payload(points: list[CurvePoint]) -> str | None:
    if not points:
        return None
    values = [float(point.value) for point in points]
    return json.dumps(
        {
            "min": min(values),
            "max": max(values),
            "avg": round(sum(values) / max(len(values), 1), 4),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _parse_series_payload(series_json: str | None) -> dict[str, Any]:
    if not series_json:
        return {}
    try:
        payload = json.loads(series_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _metric_points_from_series(row: MetricSeries) -> list[dict[str, float | int]]:
    payload = _parse_series_payload(row.series_json)
    raw_points = payload.get("points")
    if not isinstance(raw_points, list):
        return []
    points = _normalize_curve_points(raw_points)
    return [
        {"timestamp": int(point.timestamp), "value": float(point.value)}
        for point in points
    ]


async def load_baseline_metric_series(
    definition_id: str,
    item: str,
) -> dict[str, Any]:
    owner_key = _baseline_owner_key(definition_id, item)
    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(MetricSeries)
                    .where(MetricSeries.owner_key == owner_key)
                    .order_by(MetricSeries.sort_order, MetricSeries.item)
                )
            ).scalars()
        )

    if not rows:
        return {
            "curves_data": [],
            "power_curve": [],
            "voltage_curve": [],
            "curve_source": "none",
        }

    curves_data: list[dict[str, Any]] = []
    power_curve: list[dict[str, float | int]] = []
    voltage_curve: list[dict[str, float | int]] = []
    for row in rows:
        points = _metric_points_from_series(row)
        curves_data.append(
            {
                "metric_id": row.item,
                "metric_key": row.metric_key,
                "metric_name": row.metric_name,
                "unit": row.unit or "",
                "color": row.color,
                "edc_channel_id": row.source_channel_id,
                "source_channel_name": row.source_channel_name,
                "source_channel_label": row.source_channel_label,
                "points": points,
            }
        )
        metric_kind = infer_metric_kind(row.metric_name, row.unit or "")
        if metric_kind == "power" and points:
            power_curve = points
        if metric_kind == "voltage" and points:
            voltage_curve = points

    return {
        "curves_data": curves_data,
        "power_curve": power_curve,
        "voltage_curve": voltage_curve,
        "curve_source": "formal_db",
    }


async def list_definition_records(
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    async with async_session_maker() as session:
        query = select(BaselineDefinition)
        count_query = select(func.count()).select_from(BaselineDefinition)
        if status:
            query = query.where(BaselineDefinition.status == status)
            count_query = count_query.where(BaselineDefinition.status == status)
        total = int((await session.execute(count_query)).scalar_one())
        definitions = list(
            (
                await session.execute(
                    query
                    .order_by(BaselineDefinition.updated_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        definition_ids = [definition.id for definition in definitions]
        metrics = list(
            (
                await session.execute(
                    select(BaselineDefinitionMetric)
                    .where(BaselineDefinitionMetric.definition_id.in_(definition_ids))
                    .order_by(
                        BaselineDefinitionMetric.definition_id,
                        BaselineDefinitionMetric.sort_order,
                        BaselineDefinitionMetric.item,
                    )
                )
            ).scalars()
        ) if definition_ids else []
        counts_rows = await session.execute(
            select(Baseline.definition_id, func.count())
            .group_by(Baseline.definition_id)
        )

    metrics_by_definition: dict[str, list[BaselineDefinitionMetric]] = defaultdict(list)
    for metric in metrics:
        metrics_by_definition[metric.definition_id].append(metric)

    count_map = {str(definition_id): int(count) for definition_id, count in counts_rows.all()}
    items = [
        _definition_to_dict(definition, metrics_by_definition.get(definition.id, []))
        for definition in definitions
    ]
    return items, total, count_map


async def get_definition_record(definition_id: str) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        definition = await session.get(BaselineDefinition, definition_id)
        if definition is None:
            return None
        metrics = list(
            (
                await session.execute(
                    select(BaselineDefinitionMetric)
                    .where(BaselineDefinitionMetric.definition_id == definition_id)
                    .order_by(BaselineDefinitionMetric.sort_order, BaselineDefinitionMetric.item)
                )
            ).scalars()
        )
    return _definition_to_dict(definition, metrics)


async def create_definition_record(
    *,
    definition_id: str,
    definition_name: str,
    description: str | None,
    expected_duration_minutes: int,
    metrics: list[dict[str, Any]],
    actor: str,
) -> dict[str, Any]:
    now = utc_now()
    definition = BaselineDefinition(
        id=definition_id,
        definition_name=definition_name,
        description=description,
        expected_duration_minutes=expected_duration_minutes,
        status="active",
        created_by=actor,
        updated_by=actor,
        created_at=now,
        updated_at=now,
    )
    metric_rows = [
        BaselineDefinitionMetric(
            definition_id=definition_id,
            item=f"{index:03d}",
            item_kind="metric_item",
            metric_key=str(metric["metric_key"]),
            metric_name=str(metric["name"]),
            unit=metric.get("unit"),
            color=str(metric["color"]),
            sort_order=int(metric["sort_order"]),
            edc_channel_id=metric.get("edc_channel_id"),
            source_channel_name=metric.get("source_channel_name"),
            source_channel_label=metric.get("source_channel_label"),
            enabled=bool(metric.get("enabled", True)),
            created_at=now,
            updated_at=now,
        )
        for index, metric in enumerate(metrics, start=1)
    ]
    async with async_session_maker() as session:
        session.add(definition)
        session.add_all(metric_rows)
        await session.commit()
    return await get_definition_record(definition_id) or {}


async def update_definition_record(
    *,
    definition_id: str,
    definition_name: str | None,
    description: str | None,
    expected_duration_minutes: int | None,
    actor: str,
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        definition = await session.get(BaselineDefinition, definition_id)
        if definition is None:
            return None
        if definition_name is not None:
            definition.definition_name = definition_name
        if description is not None:
            definition.description = description
        if expected_duration_minutes is not None:
            definition.expected_duration_minutes = expected_duration_minutes
        definition.updated_by = actor
        definition.updated_at = utc_now()
        await session.commit()
    return await get_definition_record(definition_id)


async def set_definition_status(
    *,
    definition_id: str,
    status: str,
    actor: str,
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        definition = await session.get(BaselineDefinition, definition_id)
        if definition is None:
            return None
        definition.status = status
        definition.updated_by = actor
        definition.updated_at = utc_now()
        await session.commit()
    return await get_definition_record(definition_id)


async def delete_definition_record(definition_id: str) -> bool:
    async with async_session_maker() as session:
        definition = await session.get(BaselineDefinition, definition_id)
        if definition is None:
            return False
        await session.execute(
            delete(BaselineDefinitionMetric).where(
                BaselineDefinitionMetric.definition_id == definition_id
            )
        )
        await session.delete(definition)
        await session.commit()
    return True


async def add_definition_metric(
    *,
    definition_id: str,
    metric_key: str,
    name: str,
    unit: str | None,
    color: str,
    sort_order: int,
    edc_channel_id: str | None,
) -> dict[str, Any] | None:
    now = utc_now()
    async with async_session_maker() as session:
        definition = await session.get(BaselineDefinition, definition_id)
        if definition is None:
            return None
        next_item = (
            await session.execute(
                select(func.max(BaselineDefinitionMetric.item)).where(
                    BaselineDefinitionMetric.definition_id == definition_id
                )
            )
        ).scalar_one_or_none()
        next_index = int(next_item or "000") + 1
        session.add(
            BaselineDefinitionMetric(
                definition_id=definition_id,
                item=f"{next_index:03d}",
                item_kind="metric_item",
                metric_key=metric_key,
                metric_name=name,
                unit=unit,
                color=color,
                sort_order=sort_order,
                edc_channel_id=edc_channel_id,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        definition.updated_at = now
        await session.commit()
    return await get_definition_record(definition_id)


async def update_definition_metric(
    *,
    definition_id: str,
    item: str,
    name: str | None,
    unit: str | None,
    color: str | None,
    sort_order: int | None,
    edc_channel_id: str | None,
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        metric = await session.get(BaselineDefinitionMetric, {"definition_id": definition_id, "item": item})
        if metric is None:
            return None
        if name is not None:
            metric.metric_name = name
        if unit is not None:
            metric.unit = unit
        if color is not None:
            metric.color = color
        if sort_order is not None:
            metric.sort_order = sort_order
        if edc_channel_id is not None:
            metric.edc_channel_id = edc_channel_id
        metric.updated_at = utc_now()
        definition = await session.get(BaselineDefinition, definition_id)
        if definition is not None:
            definition.updated_at = utc_now()
        await session.commit()
    return await get_definition_record(definition_id)


async def delete_definition_metric(definition_id: str, item: str) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        metric = await session.get(BaselineDefinitionMetric, {"definition_id": definition_id, "item": item})
        if metric is None:
            return None
        await session.delete(metric)
        definition = await session.get(BaselineDefinition, definition_id)
        if definition is not None:
            definition.updated_at = utc_now()
        await session.commit()
    return await get_definition_record(definition_id)


async def list_baseline_records(
    *,
    status: str | None,
    definition_id: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    async with async_session_maker() as session:
        definitions = {
            row.id: row.definition_name
            for row in (
                await session.execute(select(BaselineDefinition))
            ).scalars()
        }
        query = select(Baseline)
        count_query = select(func.count()).select_from(Baseline)
        if status:
            query = query.where(Baseline.status == status)
            count_query = count_query.where(Baseline.status == status)
        if definition_id:
            query = query.where(Baseline.definition_id == definition_id)
            count_query = count_query.where(Baseline.definition_id == definition_id)
        total = int((await session.execute(count_query)).scalar_one())
        baselines = list(
            (
                await session.execute(
                    query.order_by(Baseline.updated_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
    return [
        _baseline_to_dict(baseline, definition_name=definitions.get(baseline.definition_id, ""))
        for baseline in baselines
    ], total


async def get_baseline_record(definition_id: str, item: str) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        baseline = await session.get(Baseline, {"definition_id": definition_id, "item": item})
        if baseline is None:
            return None
        definition = await session.get(BaselineDefinition, definition_id)
    return _baseline_to_dict(baseline, definition_name=definition.definition_name if definition else "")


async def create_baseline_record(
    *,
    definition_id: str,
    name: str,
    description: str | None,
    source_heat_id: str | None,
    selected_start_time: datetime,
    selected_end_time: datetime,
    effective_from: datetime | None,
    tolerance_percent: float,
    is_default: bool = False,
    actor: str,
) -> dict[str, Any]:
    now = utc_now()
    async with async_session_maker() as session:
        next_item = (
            await session.execute(
                select(func.max(Baseline.item)).where(Baseline.definition_id == definition_id)
            )
        ).scalar_one_or_none()
        item = f"{int(next_item or '000') + 1:03d}"
        baseline = Baseline(
            definition_id=definition_id,
            item=item,
            item_kind="baseline_version",
            name=name,
            description=description,
            status="draft",
            is_default=is_default,
            source_heat_id=source_heat_id or None,
            selected_start_time=selected_start_time,
            selected_end_time=selected_end_time,
            effective_from=effective_from or now,
            tolerance_percent=tolerance_percent,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
            published_at=None,
        )
        session.add(baseline)
        await session.commit()
    return await get_baseline_record(definition_id, item) or {}


async def replace_baseline_metric_series(
    *,
    definition_id: str,
    item: str,
    source_curves_data: list[dict[str, Any]],
    selected_start_time: datetime,
    selected_end_time: datetime,
) -> None:
    owner_key = _baseline_owner_key(definition_id, item)
    async with async_session_maker() as session:
        metrics = list(
            (
                await session.execute(
                    select(BaselineDefinitionMetric)
                    .where(BaselineDefinitionMetric.definition_id == definition_id)
                    .where(BaselineDefinitionMetric.enabled.is_(True))
                    .order_by(BaselineDefinitionMetric.sort_order, BaselineDefinitionMetric.item)
                )
            ).scalars()
        )
        await session.execute(delete(MetricSeries).where(MetricSeries.owner_key == owner_key))

        points_by_metric_id: dict[str, list[CurvePoint]] = {}
        points_by_metric_key: dict[str, list[CurvePoint]] = {}
        points_by_metric_kind: dict[str, list[CurvePoint]] = {}
        for curve in source_curves_data:
            metric_id = str(curve.get("metric_id") or curve.get("item") or "")
            metric_key = str(curve.get("metric_key") or "").strip().lower()
            metric_name = str(curve.get("metric_name") or "")
            unit = str(curve.get("unit") or "")
            points = _normalize_curve_points(curve.get("points"))
            if metric_id:
                points_by_metric_id[metric_id] = points
            if metric_key and metric_key not in points_by_metric_key:
                points_by_metric_key[metric_key] = points
            metric_kind = infer_metric_kind(metric_name, unit)
            if metric_kind and metric_kind not in points_by_metric_kind:
                points_by_metric_kind[metric_kind] = points

        now = utc_now()
        rows: list[MetricSeries] = []
        for metric in metrics:
            metric_kind = infer_metric_kind(metric.metric_name, metric.unit or "")
            metric_key = str(metric.metric_key or "").strip().lower()
            source_points = (
                points_by_metric_id.get(metric.item)
                or points_by_metric_key.get(metric_key)
                or points_by_metric_kind.get(metric_kind, [])
            )
            selected_points = _slice_curve_points(
                source_points,
                start_time=selected_start_time,
                end_time=selected_end_time,
            )
            rows.append(
                MetricSeries(
                    owner_key=owner_key,
                    item=metric.item,
                    owner_type="baseline",
                    definition_id=definition_id,
                    item_kind="metric_item",
                    metric_key=metric.metric_key,
                    metric_name=metric.metric_name,
                    unit=metric.unit,
                    color=metric.color,
                    sort_order=metric.sort_order,
                    source_channel_id=metric.edc_channel_id,
                    source_channel_name=metric.source_channel_name,
                    source_channel_label=metric.source_channel_label,
                    series_json=_build_series_payload(selected_points),
                    stat_json=_build_stat_payload(selected_points),
                    created_at=now,
                    updated_at=now,
                )
            )
        session.add_all(rows)
        await session.commit()


async def update_baseline_record(
    *,
    definition_id: str,
    item: str,
    name: str | None,
    description: str | None,
    selected_start_time: datetime | None,
    selected_end_time: datetime | None,
    effective_from: datetime | None,
    tolerance_percent: float | None,
    is_default: bool | None,
    actor: str,
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        baseline = await session.get(Baseline, {"definition_id": definition_id, "item": item})
        if baseline is None:
            return None
        if name is not None:
            baseline.name = name
        if description is not None:
            baseline.description = description
        if selected_start_time is not None:
            baseline.selected_start_time = selected_start_time
        if selected_end_time is not None:
            baseline.selected_end_time = selected_end_time
        if effective_from is not None:
            baseline.effective_from = effective_from
        if tolerance_percent is not None:
            baseline.tolerance_percent = tolerance_percent
        if is_default is not None:
            baseline.is_default = is_default
        baseline.updated_by = actor
        baseline.updated_at = utc_now()
        await session.commit()
    return await get_baseline_record(definition_id, item)


async def set_baseline_status(
    *,
    definition_id: str,
    item: str,
    status: str,
    actor: str,
    publish_time: datetime | None = None,
    effective_from: datetime | None = None,
    is_default: bool | None = None,
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        baseline = await session.get(Baseline, {"definition_id": definition_id, "item": item})
        if baseline is None:
            return None
        baseline.status = status
        if status != "published":
            baseline.is_default = False
        elif is_default is not None:
            baseline.is_default = is_default
        baseline.updated_by = actor
        baseline.updated_at = utc_now()
        if publish_time is not None:
            baseline.published_at = publish_time
        if effective_from is not None:
            baseline.effective_from = effective_from
        await session.commit()
    return await get_baseline_record(definition_id, item)


async def get_default_baseline_record() -> dict[str, Any] | None:
    async with async_session_maker() as session:
        baseline = (
            await session.execute(
                select(Baseline)
                .where(Baseline.is_default.is_(True))
                .where(Baseline.status == "published")
                .order_by(Baseline.updated_at.desc(), Baseline.published_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if baseline is None:
            return None
        definition = await session.get(BaselineDefinition, baseline.definition_id)
    return _baseline_to_dict(baseline, definition_name=definition.definition_name if definition else "")


async def set_default_baseline(
    *,
    definition_id: str,
    item: str,
    actor: str,
) -> dict[str, Any] | None:
    async with async_session_maker() as session:
        baseline = await session.get(Baseline, {"definition_id": definition_id, "item": item})
        if baseline is None:
            return None
        if baseline.status != "published":
            raise ValueError("default_baseline_must_be_published")

        now = utc_now()
        existing_defaults = list(
            (
                await session.execute(
                    select(Baseline)
                    .where(Baseline.is_default.is_(True))
                    .where(Baseline.status == "published")
                )
            ).scalars()
        )
        for candidate in existing_defaults:
            candidate.is_default = False
            candidate.updated_by = actor
            candidate.updated_at = now

        baseline.is_default = True
        baseline.updated_by = actor
        baseline.updated_at = now
        await session.commit()

    return await get_baseline_record(definition_id, item)


async def delete_baseline_record(definition_id: str, item: str) -> bool:
    async with async_session_maker() as session:
        baseline = await session.get(Baseline, {"definition_id": definition_id, "item": item})
        if baseline is None:
            return False
        await session.execute(
            delete(MetricSeries).where(
                MetricSeries.owner_key == _baseline_owner_key(definition_id, item)
            )
        )
        await session.delete(baseline)
        await session.commit()
    return True


async def get_definition_status(definition_id: str) -> str | None:
    async with async_session_maker() as session:
        definition = await session.get(BaselineDefinition, definition_id)
    return definition.status if definition else None


async def load_definition_store() -> dict[str, dict[str, Any]]:
    items, _, _ = await list_definition_records(status=None, page=1, page_size=1000)
    return {str(item["id"]): item for item in items}


async def load_baseline_store() -> dict[str, dict[str, Any]]:
    items, _ = await list_baseline_records(status=None, definition_id=None, page=1, page_size=1000)
    return {str(item["id"]): item for item in items}
