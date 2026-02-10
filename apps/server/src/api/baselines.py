"""基线 API 路由"""

from datetime import datetime
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
    MessageResponse,
)

router = APIRouter(prefix="/baselines", tags=["Baselines"])


def _build_curve(seed: int) -> list[dict[str, float]]:
    """生成稳定的模拟曲线数据。"""
    return [
        {"timestamp": 1000.0 * i, "value": float(430 + ((i + seed) % 12) * 3)} for i in range(100)
    ]


def _now() -> datetime:
    return datetime.now()


_BASELINE_STORE: dict[str, dict[str, Any]] = {
    "baseline-001": {
        "id": "baseline-001",
        "name": "标准基线 v2.1",
        "description": "2024年优化后的标准生产基线",
        "source_heat_id": "heat-ref-001",
        "tolerance_percent": 15.0,
        "status": "published",
        "version": 2,
        "created_at": _now(),
        "updated_at": _now(),
        "published_at": _now(),
        "power_curve": _build_curve(1),
        "voltage_curve": _build_curve(3),
        "temperature": 1450.0,
    },
    "baseline-002": {
        "id": "baseline-002",
        "name": "高功率基线",
        "description": "高功率生产模式基线",
        "source_heat_id": "heat-ref-002",
        "tolerance_percent": 12.0,
        "status": "draft",
        "version": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "published_at": None,
        "power_curve": _build_curve(5),
        "voltage_curve": _build_curve(7),
        "temperature": 1460.0,
    },
}


def _to_baseline_response(item: dict[str, Any]) -> BaselineResponse:
    return BaselineResponse(
        id=item["id"],
        name=item["name"],
        description=item["description"],
        source_heat_id=item["source_heat_id"],
        tolerance_percent=item["tolerance_percent"],
        status=item["status"],
        version=item["version"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        published_at=item["published_at"],
    )


def _to_baseline_with_curve(item: dict[str, Any]) -> BaselineWithCurve:
    return BaselineWithCurve(
        id=item["id"],
        name=item["name"],
        description=item["description"],
        source_heat_id=item["source_heat_id"],
        tolerance_percent=item["tolerance_percent"],
        status=item["status"],
        version=item["version"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        published_at=item["published_at"],
        power_curve=item["power_curve"],
        voltage_curve=item["voltage_curve"],
        temperature=item["temperature"],
    )


def _get_or_404(baseline_id: str) -> dict[str, Any]:
    item = _BASELINE_STORE.get(baseline_id)
    if not item:
        raise HTTPException(status_code=404, detail="基线不存在")
    return item


@router.get("", response_model=BaselineListResponse)
async def list_baselines(
    status: Literal["draft", "published", "disabled"] | None = Query(
        default=None, description="状态筛选"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> BaselineListResponse:
    """获取基线列表，支持状态筛选与分页。"""
    items = list(_BASELINE_STORE.values())
    items.sort(key=lambda x: x["updated_at"], reverse=True)

    if status:
        items = [item for item in items if item["status"] == status]

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
    return _to_baseline_with_curve(item)


@router.post("", response_model=BaselineResponse, status_code=201)
async def create_baseline(data: BaselineCreate) -> BaselineResponse:
    """创建新基线，默认草稿状态。"""
    now = _now()
    baseline_id = f"baseline-{uuid4()}"
    item = {
        "id": baseline_id,
        "name": data.name,
        "description": data.description,
        "source_heat_id": data.source_heat_id,
        "tolerance_percent": data.tolerance_percent,
        "status": "draft",
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "power_curve": _build_curve(9),
        "voltage_curve": _build_curve(11),
        "temperature": 1455.0,
    }
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
    if data.tolerance_percent is not None:
        item["tolerance_percent"] = data.tolerance_percent
    item["updated_at"] = _now()

    return _to_baseline_response(item)


@router.post("/{baseline_id}/publish", response_model=BaselineResponse)
async def publish_baseline(baseline_id: str) -> BaselineResponse:
    """发布草稿基线。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可发布")

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
