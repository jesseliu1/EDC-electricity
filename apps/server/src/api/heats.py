"""炉次 API 路由"""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    HeatAnalyzeRequest,
    HeatAnalyzeResponse,
    HeatCompareResponse,
    HeatListResponse,
    HeatResponse,
    HeatWithCurve,
)

router = APIRouter(prefix="/heats", tags=["Heats"])


@router.get("", response_model=HeatListResponse)
async def list_heats(
    status: Literal["normal", "abnormal", "pending"] | None = Query(
        default=None, description="状态筛选"
    ),
    start_date: datetime | None = Query(default=None, description="开始日期"),
    end_date: datetime | None = Query(default=None, description="结束日期"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> HeatListResponse:
    """获取炉次列表

    支持按状态和日期范围筛选。
    """
    # TODO: 实现真实逻辑，从数据库查询
    now = datetime.now()
    items = []
    for i in range(page_size):
        start = now - timedelta(hours=i + 1)
        end = start + timedelta(minutes=45)
        heat_status = "normal" if i % 4 != 0 else "abnormal"
        if status and heat_status != status:
            continue
        items.append(
            HeatResponse(
                id=f"heat-{i + 1:03d}",
                heat_no=f"H{now.strftime('%Y%m%d')}-{i + 1:03d}",
                start_time=start,
                end_time=end,
                baseline_id="baseline-001" if i % 2 == 0 else None,
                deviation_percent=5.2 + i * 1.5 if i % 4 == 0 else 3.1 + i * 0.5,
                avg_deviation_percent=4.5 + i * 0.8 if i % 4 == 0 else 2.5 + i * 0.3,
                status=heat_status,
                temperature=1450.0 + i * 5,
                created_at=start,
            )
        )

    return HeatListResponse(
        items=items[:page_size],
        total=50,  # 模拟总数
        page=page,
        page_size=page_size,
    )


@router.get("/{heat_id}", response_model=HeatResponse)
async def get_heat(heat_id: str) -> HeatResponse:
    """获取炉次详情"""
    # TODO: 实现真实逻辑
    now = datetime.now()
    return HeatResponse(
        id=heat_id,
        heat_no=f"H{now.strftime('%Y%m%d')}-001",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=15),
        baseline_id="baseline-001",
        deviation_percent=8.5,
        avg_deviation_percent=5.2,
        status="abnormal",
        temperature=1455.0,
        created_at=now - timedelta(hours=1),
    )


@router.get("/{heat_id}/curve", response_model=HeatWithCurve)
async def get_heat_curve(heat_id: str) -> HeatWithCurve:
    """获取炉次曲线数据"""
    # TODO: 实现真实逻辑
    now = datetime.now()

    # 生成模拟曲线数据
    power_curve = [{"timestamp": 1000 * i, "value": 440 + (i % 15) * 6} for i in range(100)]
    voltage_curve = [{"timestamp": 1000 * i, "value": 375 + (i % 8) * 3} for i in range(100)]

    return HeatWithCurve(
        id=heat_id,
        heat_no=f"H{now.strftime('%Y%m%d')}-001",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=15),
        baseline_id="baseline-001",
        deviation_percent=8.5,
        avg_deviation_percent=5.2,
        status="abnormal",
        temperature=1455.0,
        created_at=now - timedelta(hours=1),
        power_curve=power_curve,
        voltage_curve=voltage_curve,
    )


@router.get("/{heat_id}/compare", response_model=HeatCompareResponse)
async def get_heat_compare(heat_id: str) -> HeatCompareResponse:
    """获取炉次与基线对比数据"""
    # TODO: 实现真实逻辑
    now = datetime.now()

    # 生成模拟曲线数据
    heat_power = [{"timestamp": 1000 * i, "value": 440 + (i % 15) * 6} for i in range(100)]
    heat_voltage = [{"timestamp": 1000 * i, "value": 375 + (i % 8) * 3} for i in range(100)]
    baseline_power = [{"timestamp": 1000 * i, "value": 450 + (i % 10) * 5} for i in range(100)]
    baseline_voltage = [{"timestamp": 1000 * i, "value": 380 + (i % 5) * 2} for i in range(100)]

    heat = HeatWithCurve(
        id=heat_id,
        heat_no=f"H{now.strftime('%Y%m%d')}-001",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=15),
        baseline_id="baseline-001",
        deviation_percent=8.5,
        avg_deviation_percent=5.2,
        status="abnormal",
        temperature=1455.0,
        created_at=now - timedelta(hours=1),
        power_curve=heat_power,
        voltage_curve=heat_voltage,
    )

    from ..schemas.heat import BaselineWithCurveSimple

    baseline = BaselineWithCurveSimple(
        id="baseline-001",
        name="标准基线 v2.1",
        power_curve=baseline_power,
        voltage_curve=baseline_voltage,
        tolerance_percent=15.0,
    )

    # 模拟偏差区间
    deviation_ranges = [
        {"start": 20000, "end": 35000, "deviation": 18.5},
        {"start": 60000, "end": 75000, "deviation": 22.3},
    ]

    return HeatCompareResponse(
        heat=heat,
        baseline=baseline,
        deviation_ranges=deviation_ranges,
        max_deviation=22.3,
        avg_deviation=8.5,
    )


@router.post("/{heat_id}/analyze", response_model=HeatAnalyzeResponse)
async def analyze_heat(heat_id: str, data: HeatAnalyzeRequest) -> HeatAnalyzeResponse:
    """触发炉次偏差分析

    使用指定基线或当前激活基线进行偏差分析。
    """
    # TODO: 实现真实逻辑
    baseline_id = data.baseline_id or "baseline-001"

    return HeatAnalyzeResponse(
        heat_id=heat_id,
        baseline_id=baseline_id,
        max_deviation=22.3,
        avg_deviation=8.5,
        status="abnormal",
        deviation_ranges=[
            {"start": 20000, "end": 35000, "deviation": 18.5},
            {"start": 60000, "end": 75000, "deviation": 22.3},
        ],
    )
