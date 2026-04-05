"""黄金基线定义 API 路由"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from ..runtime_state import persist_runtime_state
from ..schemas import BaselinePreviewJobResponse, BaselinePreviewResponse, CurveData
from ..schemas.baseline_definition import (
    BaselineDefinitionCreate,
    BaselineDefinitionListResponse,
    BaselineDefinitionResponse,
    BaselineDefinitionUpdate,
    MetricDefinitionCreate,
    MetricDefinitionResponse,
    MetricDefinitionUpdate,
)
from ..schemas.common import MessageResponse
from ..services import (
    EDCClientError,
    create_definition_record,
    delete_definition_record,
    get_definition_record,
    get_shared_edc_client,
    list_baseline_records,
    list_definition_records,
    load_definition_store,
    set_definition_status,
    update_definition_record,
)
from ..services import (
    add_definition_metric as add_definition_metric_record,
)
from ..services import (
    delete_definition_metric as delete_definition_metric_record,
)
from ..services import (
    update_definition_metric as update_definition_metric_record,
)
from ..time_utils import parse_timestamp_ms, plant_date_of, plant_day_bounds_datetime, utc_now
from .settings import _HOST_CHANNEL_STORE, get_edc_connection_config, get_plant_timezone

router = APIRouter(prefix="/baseline-definitions", tags=["BaselineDefinitions"])

_PREVIEW_TASK_TIMEOUT_SECONDS = 600.0
_PREVIEW_JOB_TTL = timedelta(hours=6)
_PREVIEW_JOB_STORE: dict[str, dict[str, Any]] = {}
_PREVIEW_JOB_LOCK = asyncio.Lock()


def _now() -> datetime:
    return utc_now()


_DEFINITION_STORE: dict[str, dict[str, Any]] = {}


async def _reload_definition_store() -> None:
    store = await load_definition_store()
    _DEFINITION_STORE.clear()
    _DEFINITION_STORE.update(store)


def _to_response(
    item: dict[str, Any],
    *,
    instance_count_map: dict[str, int] | None = None,
) -> BaselineDefinitionResponse:
    counts = instance_count_map or {}
    metrics = [
        MetricDefinitionResponse(
            id=m["id"],
            name=m["name"],
            unit=m["unit"],
            color=m["color"],
            sort_order=m["sort_order"],
            edc_channel_id=m.get("edc_channel_id"),
        )
        for m in item.get("metrics", [])
    ]
    return BaselineDefinitionResponse(
        id=item["id"],
        definition_name=item["definition_name"],
        description=item.get("description"),
        expected_duration_minutes=item["expected_duration_minutes"],
        status=item["status"],
        metrics=metrics,
        instance_count=counts.get(str(item["id"]), 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


async def _get_or_404(definition_id: str) -> dict[str, Any]:
    item = await get_definition_record(definition_id)
    if not item:
        raise HTTPException(status_code=404, detail="黄金基线定义不存在")
    return item


def _resolve_host_channel(channel_id: str | None) -> dict[str, str] | None:
    if not channel_id:
        return None
    return next((item for item in _HOST_CHANNEL_STORE if item["id"] == channel_id), None)


def _format_host_channel_label(channel: dict[str, str] | None) -> str | None:
    if not channel:
        return None
    return (
        f'{channel["device_name"]} / '
        f'{channel["channel_name"]} / '
        f'{channel["unit"] or "--"}'
    )


async def _resolve_preview_window(
    heat_id: str | None = None,
    *,
    definition_id: str | None = None,
    range_start: datetime | int | float | None = None,
    range_end: datetime | int | float | None = None,
) -> tuple[datetime, datetime]:
    if range_start is not None and range_end is not None:
        normalized_start = parse_timestamp_ms(range_start)
        normalized_end = parse_timestamp_ms(range_end)
        if normalized_start >= normalized_end:
            raise HTTPException(status_code=400, detail="预览时间范围无效")
        return normalized_start, normalized_end

    if not heat_id:
        raise HTTPException(status_code=400, detail="缺少预览日期范围")

    from .heats import build_live_heat_lookup_context, resolve_heat_record

    preferred_live_context = build_live_heat_lookup_context(definition_id=definition_id)
    heat = await resolve_heat_record(heat_id, preferred_live_context=preferred_live_context)
    if not heat:
        raise HTTPException(status_code=404, detail="来源炉次不存在")

    heat_start: datetime = heat["start_time"]
    return plant_day_bounds_datetime(heat_start, get_plant_timezone())


async def _build_preview_curves(
    *,
    definition: dict[str, Any],
    range_start: datetime,
    range_end: datetime,
) -> list[CurveData]:
    metrics = list(definition.get("metrics", []))
    points_by_metric: dict[str, list[dict[str, float | int]]] = {}
    config = get_edc_connection_config()
    bound_metrics: list[tuple[dict[str, Any], dict[str, str]]] = []
    for metric in metrics:
        channel = _resolve_host_channel(metric.get("edc_channel_id"))
        if channel:
            bound_metrics.append((metric, channel))

    if bound_metrics and config["base_url"] and config["username"] and config["password"]:
        try:
            client = await get_shared_edc_client(**config, timeout=_PREVIEW_TASK_TIMEOUT_SECONDS)
            await client.login()
            tasks = {
                str(metric["id"]): asyncio.create_task(
                    client.get_local_datas(
                        suid=channel["suid"],
                        cuid=channel["cuid"],
                        start_time=range_start,
                        end_time=range_end,
                    )
                )
                for metric, channel in bound_metrics
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        except EDCClientError:
            results = []
            tasks = {}

        for metric_id, result in zip(tasks.keys(), results, strict=False):
            if isinstance(result, Exception) or not result:
                continue
            points_by_metric[metric_id] = [point.model_dump() for point in result]

    curves: list[CurveData] = []
    for metric in metrics:
        metric_id = str(metric["id"])
        host_channel = _resolve_host_channel(metric.get("edc_channel_id"))
        points = points_by_metric.get(metric_id)
        if points is None:
            points = []
        curves.append(
            CurveData(
                metric_id=metric_id,
                metric_name=str(metric["name"]),
                unit=str(metric["unit"]),
                color=str(metric["color"]),
                edc_channel_id=metric.get("edc_channel_id"),
                source_channel_name=host_channel["channel_name"] if host_channel else None,
                source_channel_label=_format_host_channel_label(host_channel),
                points=points,
            )
        )
    return curves


def _preview_job_key(*, definition_id: str, range_start: datetime) -> str:
    plant_date = plant_date_of(range_start, get_plant_timezone())
    return f"{definition_id}:{plant_date.isoformat()}"


def _preview_job_has_points(entry: dict[str, Any]) -> bool:
    return _preview_curves_have_points(entry.get("curves_data") or [])


def _preview_curves_have_points(curves: list[Any]) -> bool:
    return any(
        curve.points if hasattr(curve, "points") else curve.get("points", [])
        for curve in curves
    )


def _serialize_preview_job(
    entry: dict[str, Any],
    *,
    source_heat_id: str | None,
) -> BaselinePreviewJobResponse:
    return BaselinePreviewJobResponse(
        job_key=str(entry["job_key"]),
        definition_id=str(entry["definition_id"]),
        source_heat_id=source_heat_id,
        status=str(entry["status"]),
        range_start=entry["range_start"],
        range_end=entry["range_end"],
        curves_data=list(entry.get("curves_data") or []),
        last_error=entry.get("last_error"),
        created_at=entry.get("created_at"),
        started_at=entry.get("started_at"),
        updated_at=entry.get("updated_at"),
        completed_at=entry.get("completed_at"),
    )


def _prune_preview_jobs(now: datetime) -> None:
    expired_keys = [
        job_key
        for job_key, entry in _PREVIEW_JOB_STORE.items()
        if entry.get("status") in {"succeeded", "failed"}
        and isinstance(entry.get("updated_at"), datetime)
        and now - entry["updated_at"] >= _PREVIEW_JOB_TTL
    ]
    for job_key in expired_keys:
        _PREVIEW_JOB_STORE.pop(job_key, None)


async def _run_preview_job(job_key: str) -> None:
    async with _PREVIEW_JOB_LOCK:
        entry = _PREVIEW_JOB_STORE.get(job_key)
        if not entry:
            return
        entry["status"] = "running"
        entry["started_at"] = _now()
        entry["updated_at"] = entry["started_at"]
        definition_id = str(entry["definition_id"])
        range_start = entry["range_start"]
        range_end = entry["range_end"]

    try:
        definition = await _get_or_404(definition_id)
        curves = await _build_preview_curves(
            definition=definition,
            range_start=range_start,
            range_end=range_end,
        )
        if not any(
            curve.points if hasattr(curve, "points") else curve.get("points", [])
            for curve in curves
        ):
            raise HTTPException(
                status_code=503,
                detail="未获取到真实预览数据，请检查宿主连接和通道绑定",
            )

        completed_at = _now()
        async with _PREVIEW_JOB_LOCK:
            latest = _PREVIEW_JOB_STORE.get(job_key)
            if not latest:
                return
            latest["status"] = "succeeded"
            latest["curves_data"] = curves
            latest["last_error"] = None
            latest["updated_at"] = completed_at
            latest["completed_at"] = completed_at
            latest["task"] = None
    except HTTPException as exc:
        failed_at = _now()
        async with _PREVIEW_JOB_LOCK:
            latest = _PREVIEW_JOB_STORE.get(job_key)
            if not latest:
                return
            latest["status"] = "failed"
            latest["last_error"] = str(exc.detail)
            latest["updated_at"] = failed_at
            latest["completed_at"] = failed_at
            latest["task"] = None
    except Exception as exc:
        failed_at = _now()
        async with _PREVIEW_JOB_LOCK:
            latest = _PREVIEW_JOB_STORE.get(job_key)
            if not latest:
                return
            latest["status"] = "failed"
            latest["last_error"] = str(exc)
            latest["updated_at"] = failed_at
            latest["completed_at"] = failed_at
            latest["task"] = None


async def _ensure_preview_job(
    *,
    definition_id: str,
    heat_id: str | None = None,
    range_start: datetime | int | float | None = None,
    range_end: datetime | int | float | None = None,
) -> BaselinePreviewJobResponse:
    range_start, range_end = await _resolve_preview_window(
        heat_id,
        definition_id=definition_id,
        range_start=range_start,
        range_end=range_end,
    )
    job_key = _preview_job_key(definition_id=definition_id, range_start=range_start)
    now = _now()

    async with _PREVIEW_JOB_LOCK:
        _prune_preview_jobs(now)
        entry = _PREVIEW_JOB_STORE.get(job_key)
        if entry is None:
            entry = {
                "job_key": job_key,
                "definition_id": definition_id,
                "range_start": range_start,
                "range_end": range_end,
                "status": "idle",
                "curves_data": [],
                "last_error": None,
                "created_at": now,
                "started_at": None,
                "updated_at": now,
                "completed_at": None,
                "task": None,
            }
            _PREVIEW_JOB_STORE[job_key] = entry

        task = entry.get("task")
        if isinstance(task, asyncio.Task) and not task.done():
            return _serialize_preview_job(entry, source_heat_id=heat_id)

        if entry.get("status") == "succeeded" and _preview_job_has_points(entry):
            return _serialize_preview_job(entry, source_heat_id=heat_id)

        entry["status"] = "running"
        entry["last_error"] = None
        entry["started_at"] = now
        entry["updated_at"] = now
        entry["completed_at"] = None
        entry["task"] = asyncio.create_task(_run_preview_job(job_key))
        return _serialize_preview_job(entry, source_heat_id=heat_id)


async def _get_preview_job(
    *,
    definition_id: str,
    heat_id: str | None = None,
    range_start: datetime | int | float | None = None,
    range_end: datetime | int | float | None = None,
) -> BaselinePreviewJobResponse:
    range_start, _range_end = await _resolve_preview_window(
        heat_id,
        definition_id=definition_id,
        range_start=range_start,
        range_end=range_end,
    )
    job_key = _preview_job_key(definition_id=definition_id, range_start=range_start)
    async with _PREVIEW_JOB_LOCK:
        entry = _PREVIEW_JOB_STORE.get(job_key)
        if not entry:
            raise HTTPException(status_code=404, detail="预览任务不存在")
        return _serialize_preview_job(entry, source_heat_id=heat_id)


@router.get("", response_model=BaselineDefinitionListResponse)
async def list_definitions(
    status: str | None = Query(default=None, description="状态筛选: active/disabled"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> BaselineDefinitionListResponse:
    """获取黄金基线定义列表。"""
    items, total, instance_count_map = await list_definition_records(
        status=status,
        page=page,
        page_size=page_size,
    )
    await _reload_definition_store()
    return BaselineDefinitionListResponse(items=[_to_response(x, instance_count_map=instance_count_map) for x in items], total=total)


@router.get("/{definition_id}", response_model=BaselineDefinitionResponse)
async def get_definition(definition_id: str) -> BaselineDefinitionResponse:
    """获取黄金基线定义详情。"""
    item = await _get_or_404(definition_id)
    _, total = await list_baseline_records(status=None, definition_id=definition_id, page=1, page_size=1)
    return _to_response(item, instance_count_map={definition_id: total})


@router.get("/{definition_id}/preview-curves", response_model=BaselinePreviewResponse)
async def get_definition_preview_curves(
    definition_id: str,
    heat_id: str | None = Query(default=None, description="来源炉次ID，可选"),
    range_start: int | None = Query(default=None, description="预览开始时间戳(ms)"),
    range_end: int | None = Query(default=None, description="预览结束时间戳(ms)"),
) -> BaselinePreviewResponse:
    """按定义与炉次返回基线向导候选曲线预览。"""
    definition = await _get_or_404(definition_id)
    range_start, range_end = await _resolve_preview_window(
        heat_id,
        definition_id=definition_id,
        range_start=range_start,
        range_end=range_end,
    )
    curves = await _build_preview_curves(
        definition=definition,
        range_start=range_start,
        range_end=range_end,
    )
    if not _preview_curves_have_points(curves):
        raise HTTPException(
            status_code=503,
            detail="未获取到真实预览数据，请检查宿主连接和通道绑定",
        )
    return BaselinePreviewResponse(
        definition_id=definition_id,
        source_heat_id=heat_id,
        range_start=range_start,
        range_end=range_end,
        curves_data=curves,
    )


@router.post("/{definition_id}/preview-jobs", response_model=BaselinePreviewJobResponse)
async def start_definition_preview_job(
    definition_id: str,
    heat_id: str | None = Query(default=None, description="来源炉次ID，可选"),
    range_start: int | None = Query(default=None, description="预览开始时间戳(ms)"),
    range_end: int | None = Query(default=None, description="预览结束时间戳(ms)"),
) -> BaselinePreviewJobResponse:
    """启动或复用整天预览任务。"""
    await _get_or_404(definition_id)
    return await _ensure_preview_job(
        definition_id=definition_id,
        heat_id=heat_id,
        range_start=range_start,
        range_end=range_end,
    )


@router.get("/{definition_id}/preview-jobs", response_model=BaselinePreviewJobResponse)
async def get_definition_preview_job(
    definition_id: str,
    heat_id: str | None = Query(default=None, description="来源炉次ID，可选"),
    range_start: int | None = Query(default=None, description="预览开始时间戳(ms)"),
    range_end: int | None = Query(default=None, description="预览结束时间戳(ms)"),
) -> BaselinePreviewJobResponse:
    """查询整天预览任务状态。"""
    await _get_or_404(definition_id)
    return await _get_preview_job(
        definition_id=definition_id,
        heat_id=heat_id,
        range_start=range_start,
        range_end=range_end,
    )


@router.post("", response_model=BaselineDefinitionResponse, status_code=201)
async def create_definition(data: BaselineDefinitionCreate) -> BaselineDefinitionResponse:
    """创建黄金基线定义。"""
    definition_id = f"def-{uuid4()}"

    metrics = []
    for idx, metric in enumerate(data.metrics, start=1):
        channel = _resolve_host_channel(metric.edc_channel_id)
        metrics.append(
            {
                "metric_key": f"metric_{idx:03d}",
                "name": metric.name,
                "unit": metric.unit,
                "color": metric.color,
                "sort_order": metric.sort_order if metric.sort_order else idx,
                "edc_channel_id": metric.edc_channel_id,
                "source_channel_name": channel["channel_name"] if channel else None,
                "source_channel_label": _format_host_channel_label(channel),
                "enabled": True,
            }
        )

    item = await create_definition_record(
        definition_id=definition_id,
        definition_name=data.definition_name,
        description=data.description,
        expected_duration_minutes=data.expected_duration_minutes,
        metrics=metrics,
        actor="system",
    )
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return _to_response(item)


@router.patch("/{definition_id}", response_model=BaselineDefinitionResponse)
async def update_definition(
    definition_id: str, data: BaselineDefinitionUpdate
) -> BaselineDefinitionResponse:
    """更新黄金基线定义。"""
    item = await update_definition_record(
        definition_id=definition_id,
        definition_name=data.definition_name,
        description=data.description,
        expected_duration_minutes=data.expected_duration_minutes,
        actor="system",
    )
    if not item:
        raise HTTPException(status_code=404, detail="黄金基线定义不存在")
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return _to_response(item)


@router.delete("/{definition_id}", response_model=MessageResponse)
async def delete_definition(definition_id: str) -> MessageResponse:
    """删除黄金基线定义（无关联实例时）。"""
    deleted = await delete_definition_record(definition_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="黄金基线定义不存在")
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return MessageResponse(message="黄金基线定义已删除", success=True)


@router.post("/{definition_id}/disable", response_model=BaselineDefinitionResponse)
async def disable_definition(definition_id: str) -> BaselineDefinitionResponse:
    """停用黄金基线定义。"""
    item = await _get_or_404(definition_id)
    if item["status"] != "active":
        raise HTTPException(status_code=400, detail="仅激活状态可停用")
    item = await set_definition_status(definition_id=definition_id, status="disabled", actor="system")
    if not item:
        raise HTTPException(status_code=404, detail="黄金基线定义不存在")
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return _to_response(item)


@router.post("/{definition_id}/enable", response_model=BaselineDefinitionResponse)
async def enable_definition(definition_id: str) -> BaselineDefinitionResponse:
    """启用黄金基线定义。"""
    item = await _get_or_404(definition_id)
    if item["status"] != "disabled":
        raise HTTPException(status_code=400, detail="仅停用状态可启用")
    item = await set_definition_status(definition_id=definition_id, status="active", actor="system")
    if not item:
        raise HTTPException(status_code=404, detail="黄金基线定义不存在")
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return _to_response(item)


# ---- 指标通道子路由 ----


@router.post(
    "/{definition_id}/metrics",
    response_model=BaselineDefinitionResponse,
    status_code=201,
)
async def add_metric(
    definition_id: str, data: MetricDefinitionCreate
) -> BaselineDefinitionResponse:
    """向定义添加指标通道。"""
    item = await add_definition_metric_record(
        definition_id=definition_id,
        metric_key=f"metric_{uuid4().hex[:8]}",
        name=data.name,
        unit=data.unit,
        color=data.color,
        sort_order=data.sort_order,
        edc_channel_id=data.edc_channel_id,
    )
    if not item:
        raise HTTPException(status_code=404, detail="黄金基线定义不存在")
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return _to_response(item)


@router.patch(
    "/{definition_id}/metrics/{metric_id}",
    response_model=BaselineDefinitionResponse,
)
async def update_metric(
    definition_id: str, metric_id: str, data: MetricDefinitionUpdate
) -> BaselineDefinitionResponse:
    """更新指标通道。"""
    item = await update_definition_metric_record(
        definition_id=definition_id,
        item=metric_id,
        name=data.name,
        unit=data.unit,
        color=data.color,
        sort_order=data.sort_order,
        edc_channel_id=data.edc_channel_id,
    )
    if not item:
        raise HTTPException(status_code=404, detail="指标通道不存在")
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return _to_response(item)


@router.delete(
    "/{definition_id}/metrics/{metric_id}",
    response_model=BaselineDefinitionResponse,
)
async def delete_metric(definition_id: str, metric_id: str) -> BaselineDefinitionResponse:
    """删除指标通道。"""
    item = await delete_definition_metric_record(definition_id, metric_id)
    if not item:
        raise HTTPException(status_code=404, detail="指标通道不存在")
    await _reload_definition_store()
    await persist_runtime_state("baseline_definitions")
    return _to_response(item)
