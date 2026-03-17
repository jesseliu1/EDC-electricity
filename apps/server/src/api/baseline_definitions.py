"""黄金基线定义 API 路由"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

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

router = APIRouter(prefix="/baseline-definitions", tags=["BaselineDefinitions"])


def _now() -> datetime:
    return datetime.now()


# Mock 指标数据
_DEFINITION_STORE: dict[str, dict[str, Any]] = {
    "def-001": {
        "id": "def-001",
        "definition_name": "标准熔炼基线",
        "description": "中频炉标准熔炼过程，适用于常规铸铁生产",
        "expected_duration_minutes": 30,
        "status": "active",
        "metrics": [
            {
                "id": "metric-001",
                "name": "功率",
                "unit": "kW",
                "color": "#409EFF",
                "sort_order": 1,
                "edc_channel_id": "2349-199",
            },
            {
                "id": "metric-002",
                "name": "电压",
                "unit": "V",
                "color": "#67C23A",
                "sort_order": 2,
                "edc_channel_id": "2349-128",
            },
            {
                "id": "metric-003",
                "name": "炉温",
                "unit": "°C",
                "color": "#E6A23C",
                "sort_order": 3,
                "edc_channel_id": "2054-128",
            },
        ],
        "created_at": _now(),
        "updated_at": _now(),
    },
    "def-002": {
        "id": "def-002",
        "definition_name": "高功率熔炼基线",
        "description": "高强度钢生产专用，包含压力监控",
        "expected_duration_minutes": 45,
        "status": "active",
        "metrics": [
            {
                "id": "metric-004",
                "name": "功率",
                "unit": "kW",
                "color": "#409EFF",
                "sort_order": 1,
                "edc_channel_id": "2349-142",
            },
            {
                "id": "metric-005",
                "name": "电压",
                "unit": "V",
                "color": "#67C23A",
                "sort_order": 2,
                "edc_channel_id": "2349-130",
            },
            {
                "id": "metric-006",
                "name": "炉温",
                "unit": "°C",
                "color": "#E6A23C",
                "sort_order": 3,
                "edc_channel_id": "2066-128",
            },
            {
                "id": "metric-007",
                "name": "炉压",
                "unit": "MPa",
                "color": "#F56C6C",
                "sort_order": 4,
                "edc_channel_id": "769-128",
            },
        ],
        "created_at": _now(),
        "updated_at": _now(),
    },
}


def _to_response(item: dict[str, Any]) -> BaselineDefinitionResponse:
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
        instance_count=0,  # TODO: 后续关联实例后计算
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


def _get_or_404(definition_id: str) -> dict[str, Any]:
    item = _DEFINITION_STORE.get(definition_id)
    if not item:
        raise HTTPException(status_code=404, detail="黄金基线定义不存在")
    return item


@router.get("", response_model=BaselineDefinitionListResponse)
async def list_definitions(
    status: str | None = Query(default=None, description="状态筛选: active/disabled"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> BaselineDefinitionListResponse:
    """获取黄金基线定义列表。"""
    items = list(_DEFINITION_STORE.values())
    items.sort(key=lambda x: x["updated_at"], reverse=True)

    if status:
        items = [item for item in items if item["status"] == status]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paged = items[start:end]

    return BaselineDefinitionListResponse(items=[_to_response(x) for x in paged], total=total)


@router.get("/{definition_id}", response_model=BaselineDefinitionResponse)
async def get_definition(definition_id: str) -> BaselineDefinitionResponse:
    """获取黄金基线定义详情。"""
    item = _get_or_404(definition_id)
    return _to_response(item)


@router.post("", response_model=BaselineDefinitionResponse, status_code=201)
async def create_definition(data: BaselineDefinitionCreate) -> BaselineDefinitionResponse:
    """创建黄金基线定义。"""
    now = _now()
    definition_id = f"def-{uuid4()}"

    metrics = []
    for idx, m in enumerate(data.metrics):
        metrics.append(
            {
                "id": f"metric-{uuid4()}",
                "name": m.name,
                "unit": m.unit,
                "color": m.color,
                "sort_order": m.sort_order if m.sort_order else idx + 1,
                "edc_channel_id": m.edc_channel_id,
            }
        )

    item: dict[str, Any] = {
        "id": definition_id,
        "definition_name": data.definition_name,
        "description": data.description,
        "expected_duration_minutes": data.expected_duration_minutes,
        "status": "active",
        "metrics": metrics,
        "created_at": now,
        "updated_at": now,
    }
    _DEFINITION_STORE[definition_id] = item
    return _to_response(item)


@router.patch("/{definition_id}", response_model=BaselineDefinitionResponse)
async def update_definition(
    definition_id: str, data: BaselineDefinitionUpdate
) -> BaselineDefinitionResponse:
    """更新黄金基线定义。"""
    item = _get_or_404(definition_id)

    if data.definition_name is not None:
        item["definition_name"] = data.definition_name
    if data.description is not None:
        item["description"] = data.description
    if data.expected_duration_minutes is not None:
        item["expected_duration_minutes"] = data.expected_duration_minutes
    item["updated_at"] = _now()

    return _to_response(item)


@router.delete("/{definition_id}", response_model=MessageResponse)
async def delete_definition(definition_id: str) -> MessageResponse:
    """删除黄金基线定义（无关联实例时）。"""
    _get_or_404(definition_id)
    # TODO: 后续检查是否有关联的黄金基线实例
    _DEFINITION_STORE.pop(definition_id, None)
    return MessageResponse(message="黄金基线定义已删除", success=True)


@router.post("/{definition_id}/disable", response_model=BaselineDefinitionResponse)
async def disable_definition(definition_id: str) -> BaselineDefinitionResponse:
    """停用黄金基线定义。"""
    item = _get_or_404(definition_id)
    if item["status"] != "active":
        raise HTTPException(status_code=400, detail="仅激活状态可停用")
    item["status"] = "disabled"
    item["updated_at"] = _now()
    return _to_response(item)


@router.post("/{definition_id}/enable", response_model=BaselineDefinitionResponse)
async def enable_definition(definition_id: str) -> BaselineDefinitionResponse:
    """启用黄金基线定义。"""
    item = _get_or_404(definition_id)
    if item["status"] != "disabled":
        raise HTTPException(status_code=400, detail="仅停用状态可启用")
    item["status"] = "active"
    item["updated_at"] = _now()
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
    item = _get_or_404(definition_id)
    metric = {
        "id": f"metric-{uuid4()}",
        "name": data.name,
        "unit": data.unit,
        "color": data.color,
        "sort_order": data.sort_order if data.sort_order else len(item["metrics"]) + 1,
        "edc_channel_id": data.edc_channel_id,
    }
    item["metrics"].append(metric)
    item["updated_at"] = _now()
    return _to_response(item)


@router.patch(
    "/{definition_id}/metrics/{metric_id}",
    response_model=BaselineDefinitionResponse,
)
async def update_metric(
    definition_id: str, metric_id: str, data: MetricDefinitionUpdate
) -> BaselineDefinitionResponse:
    """更新指标通道。"""
    item = _get_or_404(definition_id)
    metric = next((m for m in item["metrics"] if m["id"] == metric_id), None)
    if not metric:
        raise HTTPException(status_code=404, detail="指标通道不存在")

    if data.name is not None:
        metric["name"] = data.name
    if data.unit is not None:
        metric["unit"] = data.unit
    if data.color is not None:
        metric["color"] = data.color
    if data.sort_order is not None:
        metric["sort_order"] = data.sort_order
    if data.edc_channel_id is not None:
        metric["edc_channel_id"] = data.edc_channel_id
    item["updated_at"] = _now()
    return _to_response(item)


@router.delete(
    "/{definition_id}/metrics/{metric_id}",
    response_model=BaselineDefinitionResponse,
)
async def delete_metric(definition_id: str, metric_id: str) -> BaselineDefinitionResponse:
    """删除指标通道。"""
    item = _get_or_404(definition_id)
    original_len = len(item["metrics"])
    item["metrics"] = [m for m in item["metrics"] if m["id"] != metric_id]
    if len(item["metrics"]) == original_len:
        raise HTTPException(status_code=404, detail="指标通道不存在")
    item["updated_at"] = _now()
    return _to_response(item)
