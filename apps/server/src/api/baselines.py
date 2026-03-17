"""基线 API 路由（黄金基线实例）"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    BaselineCreate,
    BaselineListResponse,
    BaselineResponse,
    BaselineSummary,
    BaselineUpdate,
    BaselineWithCurve,
    CurveData,
    MessageResponse,
)
from ..schemas.common import CurvePoint
from ..services import EDCClient, EDCClientError

# 引用 definition store 以做关联校验
from .baseline_definitions import _DEFINITION_STORE
from .settings import _HOST_CHANNEL_STORE, _SETTINGS_STORE, get_edc_connection_config

router = APIRouter(prefix="/baselines", tags=["Baselines"])


def _build_curve(seed: int, length: int = 100) -> list[dict[str, float]]:
    """生成稳定的模拟曲线数据。"""
    return [
        {"timestamp": 1000.0 * i, "value": float(430 + ((i + seed) % 12) * 3)}
        for i in range(length)
    ]


def _build_curves_data(definition_id: str, seed: int) -> list[dict[str, Any]]:
    """根据定义的指标生成动态曲线数据。"""
    definition = _DEFINITION_STORE.get(definition_id)
    if not definition:
        return []

    curves = []
    for idx, metric in enumerate(definition["metrics"]):
        points = _build_curve(seed + idx * 2)
        host_channel = _resolve_host_channel(metric.get("edc_channel_id"))
        curves.append(
            {
                "metric_id": metric["id"],
                "metric_name": metric["name"],
                "unit": metric["unit"],
                "color": metric["color"],
                "edc_channel_id": metric.get("edc_channel_id"),
                "source_channel_name": host_channel["channel_name"] if host_channel else None,
                "source_channel_label": _format_host_channel_label(host_channel),
                "points": points,
            }
        )
    return curves


def _curve_points_to_dicts(points: list[CurvePoint]) -> list[dict[str, float | int]]:
    """将 Pydantic 曲线点转回存储结构。"""
    return [point.model_dump() for point in points]


def _get_definition_name(definition_id: str) -> str:
    """获取定义名称。"""
    definition = _DEFINITION_STORE.get(definition_id)
    return definition["definition_name"] if definition else ""


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


def _now() -> datetime:
    return datetime.now()


_BASELINE_STORE: dict[str, dict[str, Any]] = {
    "baseline-001": {
        "id": "baseline-001",
        "name": "标准基线 v2.1",
        "description": "2024年优化后的标准生产基线",
        "definition_id": "def-001",
        "source_heat_id": "heat-ref-001",
        "selected_start_time": None,
        "selected_end_time": None,
        "tolerance_percent": 15.0,
        "status": "published",
        "version": 2,
        "created_at": _now(),
        "updated_at": _now(),
        "published_at": _now(),
        "power_curve": _build_curve(1),
        "voltage_curve": _build_curve(3),
        "temperature": 1450.0,
        "curves_data": _build_curves_data("def-001", 1),
    },
    "baseline-002": {
        "id": "baseline-002",
        "name": "高功率基线",
        "description": "高功率生产模式基线",
        "definition_id": "def-002",
        "source_heat_id": "heat-ref-002",
        "selected_start_time": None,
        "selected_end_time": None,
        "tolerance_percent": 12.0,
        "status": "draft",
        "version": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "published_at": None,
        "power_curve": _build_curve(5),
        "voltage_curve": _build_curve(7),
        "temperature": 1460.0,
        "curves_data": _build_curves_data("def-002", 5),
    },
}


def _to_baseline_response(item: dict[str, Any]) -> BaselineResponse:
    return BaselineResponse(
        id=item["id"],
        name=item["name"],
        description=item["description"],
        definition_id=item["definition_id"],
        definition_name=_get_definition_name(item["definition_id"]),
        source_heat_id=item["source_heat_id"],
        selected_start_time=item.get("selected_start_time"),
        selected_end_time=item.get("selected_end_time"),
        tolerance_percent=item["tolerance_percent"],
        status=item["status"],
        version=item["version"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        published_at=item["published_at"],
    )


def _to_baseline_with_curve(item: dict[str, Any]) -> BaselineWithCurve:
    curves_data = [
        CurveData(
            metric_id=curve["metric_id"],
            metric_name=curve["metric_name"],
            unit=curve["unit"],
            color=curve["color"],
            edc_channel_id=curve.get("edc_channel_id"),
            source_channel_name=curve.get("source_channel_name"),
            source_channel_label=curve.get("source_channel_label"),
            points=curve["points"],
        )
        for curve in item.get("curves_data", [])
    ]

    return BaselineWithCurve(
        id=item["id"],
        name=item["name"],
        description=item["description"],
        definition_id=item["definition_id"],
        definition_name=_get_definition_name(item["definition_id"]),
        source_heat_id=item["source_heat_id"],
        selected_start_time=item.get("selected_start_time"),
        selected_end_time=item.get("selected_end_time"),
        tolerance_percent=item["tolerance_percent"],
        status=item["status"],
        version=item["version"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        published_at=item["published_at"],
        curves_data=curves_data,
        power_curve=item.get("power_curve", []),
        voltage_curve=item.get("voltage_curve", []),
        temperature=item.get("temperature"),
    )


def _resolve_baseline_time_window(item: dict[str, Any]) -> tuple[datetime, datetime]:
    """优先按选区时间，其次按来源炉次时间，最后回退最近一小时。"""
    selected_start = item.get("selected_start_time")
    selected_end = item.get("selected_end_time")
    if isinstance(selected_start, datetime) and isinstance(selected_end, datetime):
        return selected_start, selected_end

    from .heats import _HEAT_STORE

    source_heat = _HEAT_STORE.get(str(item.get("source_heat_id")))
    if source_heat:
        return source_heat["start_time"], source_heat["end_time"]

    end_time = datetime.now()
    return end_time - timedelta(hours=1), end_time


async def _load_baseline_curves_from_edc(
    item: dict[str, Any],
) -> dict[str, list[dict[str, Any]]] | None:
    """按基线定义绑定通道尝试拉取真实基线曲线。"""
    definition = _DEFINITION_STORE.get(str(item.get("definition_id")))
    metrics = list(definition.get("metrics", [])) if definition else []
    if not metrics:
        return None

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return None

    start_time, end_time = _resolve_baseline_time_window(item)
    bound_metrics: list[tuple[dict[str, Any], dict[str, str]]] = []
    for metric in metrics:
        channel = _resolve_host_channel(metric.get("edc_channel_id"))
        if channel:
            bound_metrics.append((metric, channel))

    if not bound_metrics:
        return None

    try:
        async with EDCClient(**config) as client:
            tasks = {
                str(metric["id"]): asyncio.create_task(
                    client.get_local_datas(
                        suid=channel["suid"],
                        cuid=channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
                for metric, channel in bound_metrics
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    except EDCClientError:
        return None

    points_by_metric: dict[str, list[CurvePoint]] = {}
    for metric_id, result in zip(tasks.keys(), results, strict=False):
        if isinstance(result, Exception) or not result:
            continue
        points_by_metric[metric_id] = result

    if not points_by_metric:
        return None

    hydrated_curves: list[dict[str, Any]] = []
    power_curve: list[dict[str, float | int]] = []
    voltage_curve: list[dict[str, float | int]] = []

    for idx, metric in enumerate(metrics):
        metric_id = str(metric["id"])
        host_channel = _resolve_host_channel(metric.get("edc_channel_id"))
        points = points_by_metric.get(metric_id)
        if points:
            stored_points = _curve_points_to_dicts(points)
        else:
            stored_points = _build_curve(9 + idx * 2)

        metric_name = str(metric.get("name") or "")
        unit = str(metric.get("unit") or "")
        hydrated_curves.append(
            {
                "metric_id": metric_id,
                "metric_name": metric_name,
                "unit": unit,
                "color": metric["color"],
                "edc_channel_id": metric.get("edc_channel_id"),
                "source_channel_name": host_channel["channel_name"] if host_channel else None,
                "source_channel_label": _format_host_channel_label(host_channel),
                "points": stored_points,
            }
        )

        if ("功率" in metric_name or unit == "kW") and stored_points:
            power_curve = stored_points
        if ("电压" in metric_name or "電壓" in metric_name or unit == "V") and stored_points:
            voltage_curve = stored_points

    if not power_curve:
        power_curve = _build_curve(1)
    if not voltage_curve:
        voltage_curve = _build_curve(3)

    return {
        "curves_data": hydrated_curves,
        "power_curve": power_curve,
        "voltage_curve": voltage_curve,
    }


async def _hydrate_baseline_item(item: dict[str, Any]) -> dict[str, Any]:
    """为基线实例补齐真实曲线，失败时保留现有 mock。"""
    curves = await _load_baseline_curves_from_edc(item)
    if not curves:
        return item

    item["curves_data"] = curves["curves_data"]
    item["power_curve"] = curves["power_curve"]
    item["voltage_curve"] = curves["voltage_curve"]
    return item


def _get_or_404(baseline_id: str) -> dict[str, Any]:
    item = _BASELINE_STORE.get(baseline_id)
    if not item:
        raise HTTPException(status_code=404, detail="基线不存在")
    return item


def _validate_definition(definition_id: str) -> dict[str, Any]:
    """校验定义存在且为 active 状态。"""
    definition = _DEFINITION_STORE.get(definition_id)
    if not definition:
        raise HTTPException(status_code=400, detail="基线定义不存在")
    if definition["status"] != "active":
        raise HTTPException(status_code=400, detail="基线定义已停用，无法创建实例")
    return definition


def _validate_equal_length(definition_id: str, current_id: str | None = None) -> None:
    """按配置范围校验已发布实例曲线长度一致性。"""
    scope_mode = str(
        _SETTINGS_STORE.get("baseline_length_scope_mode", {}).get("value") or "definition"
    )

    def scope_key(item: dict[str, Any]) -> str:
        if scope_mode == "system":
            return "system"
        if scope_mode == "production_line":
            # 生产线字段预留：MVP 先不引生产线，缺省回落到定义维度
            production_line = item.get("production_line_id")
            if production_line:
                return f"production_line:{production_line}"
        return f"definition:{item['definition_id']}"

    current_item = _BASELINE_STORE.get(current_id) if current_id else None
    current_scope = scope_key(current_item) if current_item else f"definition:{definition_id}"

    published = [
        item
        for item in _BASELINE_STORE.values()
        if item["status"] == "published"
        and item["id"] != current_id
        and scope_key(item) == current_scope
    ]
    if len(published) < 2:
        return

    first = published[0].get("curves_data", [])
    if not first:
        return

    first_lengths = [len(c["points"]) for c in first]
    for item in published[1:]:
        curves = item.get("curves_data", [])
        lengths = [len(c["points"]) for c in curves]
        if lengths != first_lengths:
            raise HTTPException(status_code=400, detail="同一定义下黄金基线实例曲线长度不一致")


@router.get("", response_model=BaselineListResponse)
async def list_baselines(
    status: Literal["draft", "published", "disabled"] | None = Query(
        default=None, description="状态筛选"
    ),
    definition_id: str | None = Query(default=None, description="基线定义ID筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> BaselineListResponse:
    """获取基线列表，支持状态筛选与分页。"""
    items = list(_BASELINE_STORE.values())
    items.sort(key=lambda x: x["updated_at"], reverse=True)

    if status:
        items = [item for item in items if item["status"] == status]

    if definition_id:
        items = [item for item in items if item["definition_id"] == definition_id]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paged = items[start:end]

    return BaselineListResponse(items=[_to_baseline_response(x) for x in paged], total=total)


@router.get("/active", response_model=BaselineSummary | None)
async def get_active_baseline() -> BaselineSummary | None:
    """获取当前激活基线（最近发布的 published 基线）。"""
    published = [item for item in _BASELINE_STORE.values() if item["status"] == "published"]
    if not published:
        return None

    published.sort(key=lambda x: x["published_at"] or x["updated_at"], reverse=True)
    active = published[0]
    return BaselineSummary(
        id=active["id"],
        name=active["name"],
        status=active["status"],
        version=active["version"],
    )


@router.get("/{baseline_id}", response_model=BaselineWithCurve)
async def get_baseline(baseline_id: str) -> BaselineWithCurve:
    """获取基线详情（含曲线数据）。"""
    item = _get_or_404(baseline_id)
    await _hydrate_baseline_item(item)
    return _to_baseline_with_curve(item)


@router.post("", response_model=BaselineResponse, status_code=201)
async def create_baseline(data: BaselineCreate) -> BaselineResponse:
    """创建新基线实例，默认草稿状态。"""
    _validate_definition(data.definition_id)

    now = _now()
    baseline_id = f"baseline-{uuid4()}"
    item = {
        "id": baseline_id,
        "name": data.name,
        "description": data.description,
        "definition_id": data.definition_id,
        "source_heat_id": data.source_heat_id,
        "selected_start_time": data.selected_start_time,
        "selected_end_time": data.selected_end_time,
        "tolerance_percent": data.tolerance_percent,
        "status": "draft",
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "power_curve": _build_curve(9),
        "voltage_curve": _build_curve(11),
        "temperature": 1455.0,
        "curves_data": _build_curves_data(data.definition_id, 9),
    }
    await _hydrate_baseline_item(item)
    _BASELINE_STORE[baseline_id] = item
    return _to_baseline_response(item)


@router.patch("/{baseline_id}", response_model=BaselineResponse)
async def update_baseline(baseline_id: str, data: BaselineUpdate) -> BaselineResponse:
    """更新基线，仅草稿状态允许更新。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可编辑")

    if data.name is not None:
        item["name"] = data.name
    if data.description is not None:
        item["description"] = data.description
    if data.selected_start_time is not None:
        item["selected_start_time"] = data.selected_start_time
    if data.selected_end_time is not None:
        item["selected_end_time"] = data.selected_end_time
    if data.tolerance_percent is not None:
        item["tolerance_percent"] = data.tolerance_percent
    item["updated_at"] = _now()
    await _hydrate_baseline_item(item)

    return _to_baseline_response(item)


@router.post("/{baseline_id}/publish", response_model=BaselineResponse)
async def publish_baseline(baseline_id: str) -> BaselineResponse:
    """发布草稿基线。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可发布")

    _validate_equal_length(item["definition_id"], current_id=baseline_id)

    now = _now()
    item["status"] = "published"
    item["published_at"] = now
    item["updated_at"] = now

    return _to_baseline_response(item)


@router.post("/{baseline_id}/disable", response_model=BaselineResponse)
async def disable_baseline(baseline_id: str) -> BaselineResponse:
    """停用已发布基线。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "published":
        raise HTTPException(status_code=400, detail="仅已发布基线可停用")

    item["status"] = "disabled"
    item["updated_at"] = _now()

    return _to_baseline_response(item)


@router.delete("/{baseline_id}", response_model=MessageResponse)
async def delete_baseline(baseline_id: str) -> MessageResponse:
    """删除基线，仅草稿状态允许删除。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可删除")

    _BASELINE_STORE.pop(baseline_id, None)
    return MessageResponse(message="基线已删除", success=True)
