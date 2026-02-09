"""基线 API 路由"""

from datetime import datetime
from typing import Literal
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


@router.get("", response_model=BaselineListResponse)
async def list_baselines(
    status: Literal["draft", "published", "disabled"] | None = Query(
        default=None, description="状态筛选"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> BaselineListResponse:
    """获取基线列表

    支持按状态筛选和分页。
    """
    # TODO: 实现真实逻辑，从数据库查询
    now = datetime.now()
    items = [
        BaselineResponse(
            id="baseline-001",
            name="标准基线 v2.1",
            description="2024年优化后的标准生产基线",
            source_heat_id="heat-ref-001",
            tolerance_percent=15.0,
            status="published",
            version=2,
            created_at=now,
            updated_at=now,
            published_at=now,
        ),
        BaselineResponse(
            id="baseline-002",
            name="高功率基线",
            description="高功率生产模式基线",
            source_heat_id="heat-ref-002",
            tolerance_percent=12.0,
            status="draft",
            version=1,
            created_at=now,
            updated_at=now,
            published_at=None,
        ),
    ]

    # 状态筛选
    if status:
        items = [item for item in items if item.status == status]

    return BaselineListResponse(items=items, total=len(items))


@router.get("/active", response_model=BaselineSummary | None)
async def get_active_baseline() -> BaselineSummary | None:
    """获取当前激活的基线"""
    # TODO: 实现真实逻辑
    return BaselineSummary(
        id="baseline-001",
        name="标准基线 v2.1",
        status="published",
        version=2,
    )


@router.get("/{baseline_id}", response_model=BaselineWithCurve)
async def get_baseline(baseline_id: str) -> BaselineWithCurve:
    """获取基线详情

    包含完整的曲线数据。
    """
    # TODO: 实现真实逻辑，从数据库查询
    if baseline_id != "baseline-001":
        raise HTTPException(status_code=404, detail="基线不存在")

    now = datetime.now()
    # 生成模拟曲线数据
    power_curve = [{"timestamp": 1000 * i, "value": 450 + (i % 10) * 5} for i in range(100)]
    voltage_curve = [{"timestamp": 1000 * i, "value": 380 + (i % 5) * 2} for i in range(100)]

    return BaselineWithCurve(
        id="baseline-001",
        name="标准基线 v2.1",
        description="2024年优化后的标准生产基线",
        source_heat_id="heat-ref-001",
        tolerance_percent=15.0,
        status="published",
        version=2,
        created_at=now,
        updated_at=now,
        published_at=now,
        power_curve=power_curve,
        voltage_curve=voltage_curve,
        temperature=1450.0,
    )


@router.post("", response_model=BaselineResponse, status_code=201)
async def create_baseline(data: BaselineCreate) -> BaselineResponse:
    """创建新基线

    新建的基线默认为草稿状态。
    """
    # TODO: 实现真实逻辑，保存到数据库
    now = datetime.now()
    return BaselineResponse(
        id=str(uuid4()),
        name=data.name,
        description=data.description,
        source_heat_id=data.source_heat_id,
        tolerance_percent=data.tolerance_percent,
        status="draft",
        version=1,
        created_at=now,
        updated_at=now,
        published_at=None,
    )


@router.patch("/{baseline_id}", response_model=BaselineResponse)
async def update_baseline(baseline_id: str, data: BaselineUpdate) -> BaselineResponse:
    """更新基线

    仅草稿状态的基线可以更新。
    """
    # TODO: 实现真实逻辑
    if baseline_id != "baseline-002":
        raise HTTPException(status_code=404, detail="基线不存在")

    now = datetime.now()
    return BaselineResponse(
        id=baseline_id,
        name=data.name or "高功率基线",
        description=data.description,
        source_heat_id="heat-ref-002",
        tolerance_percent=data.tolerance_percent or 12.0,
        status="draft",
        version=1,
        created_at=now,
        updated_at=now,
        published_at=None,
    )


@router.post("/{baseline_id}/publish", response_model=BaselineResponse)
async def publish_baseline(baseline_id: str) -> BaselineResponse:
    """发布基线

    将草稿状态的基线发布为正式基线。
    """
    # TODO: 实现真实逻辑
    if baseline_id != "baseline-002":
        raise HTTPException(status_code=404, detail="基线不存在")

    now = datetime.now()
    return BaselineResponse(
        id=baseline_id,
        name="高功率基线",
        description="高功率生产模式基线",
        source_heat_id="heat-ref-002",
        tolerance_percent=12.0,
        status="published",
        version=1,
        created_at=now,
        updated_at=now,
        published_at=now,
    )


@router.post("/{baseline_id}/disable", response_model=BaselineResponse)
async def disable_baseline(baseline_id: str) -> BaselineResponse:
    """停用基线

    停用已发布的基线。
    """
    # TODO: 实现真实逻辑
    now = datetime.now()
    return BaselineResponse(
        id=baseline_id,
        name="标准基线 v2.1",
        description="2024年优化后的标准生产基线",
        source_heat_id="heat-ref-001",
        tolerance_percent=15.0,
        status="disabled",
        version=2,
        created_at=now,
        updated_at=now,
        published_at=now,
    )


@router.delete("/{baseline_id}", response_model=MessageResponse)
async def delete_baseline(baseline_id: str) -> MessageResponse:
    """删除基线

    仅草稿状态的基线可以删除。
    """
    # TODO: 实现真实逻辑
    return MessageResponse(message="基线已删除", success=True)
