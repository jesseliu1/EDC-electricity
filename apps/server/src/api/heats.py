"""炉次 API 路由。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    CurvePoint,
    DeviationRange,
    HeatAnalyzeRequest,
    HeatAnalyzeResponse,
    HeatCompareResponse,
    HeatListResponse,
    HeatResponse,
    HeatWithCurve,
)
from ..schemas.heat import BaselineWithCurveSimple
from ..services import DeviationService

router = APIRouter(prefix="/heats", tags=["Heats"])
deviation_service = DeviationService()


def _curve_points(
    start: datetime, minutes: int, base: float, amp: float, phase: float
) -> list[CurvePoint]:
    points: list[CurvePoint] = []
    for idx in range(minutes):
        ts = int((start + timedelta(minutes=idx)).timestamp() * 1000)
        value = base + amp * ((idx + int(phase)) % 10) / 10
        points.append(CurvePoint(timestamp=ts, value=round(value, 3)))
    return points


def _seed_heats() -> dict[str, dict[str, Any]]:
    now = datetime.now().replace(second=0, microsecond=0)
    seeded: dict[str, dict[str, Any]] = {}
    for idx in range(60):
        start_time = now - timedelta(hours=idx + 1)
        end_time = start_time + timedelta(minutes=45)
        status: str
        if idx % 8 == 0:
            status = "pending"
        elif idx % 4 == 0:
            status = "abnormal"
        else:
            status = "normal"

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
            "start_time": start_time,
            "end_time": end_time,
            "baseline_id": "baseline-001" if status != "pending" else None,
            "deviation_percent": max_dev,
            "avg_deviation_percent": avg_dev,
            "status": status,
            "temperature": round(1450 + (idx % 6) * 5.5, 2),
            "created_at": start_time,
            "power_curve": power_curve,
            "voltage_curve": voltage_curve,
            "baseline_power_curve": baseline_power_curve,
            "baseline_voltage_curve": baseline_voltage_curve,
        }
    return seeded


_HEAT_STORE: dict[str, dict[str, Any]] = _seed_heats()


def _to_heat_response(item: dict[str, Any]) -> HeatResponse:
    return HeatResponse(
        id=item["id"],
        heat_no=item["heat_no"],
        start_time=item["start_time"],
        end_time=item["end_time"],
        baseline_id=item["baseline_id"],
        deviation_percent=item["deviation_percent"],
        avg_deviation_percent=item["avg_deviation_percent"],
        status=item["status"],
        temperature=item["temperature"],
        created_at=item["created_at"],
    )


def _to_heat_with_curve(item: dict[str, Any]) -> HeatWithCurve:
    return HeatWithCurve(
        **_to_heat_response(item).model_dump(),
        power_curve=item["power_curve"],
        voltage_curve=item["voltage_curve"],
    )


def _get_or_404(heat_id: str) -> dict[str, Any]:
    item = _HEAT_STORE.get(heat_id)
    if not item:
        raise HTTPException(status_code=404, detail="炉次不存在")
    return item


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
    items = list(_HEAT_STORE.values())
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
        items=[_to_heat_response(item) for item in paged],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{heat_id}", response_model=HeatResponse)
async def get_heat(heat_id: str) -> HeatResponse:
    """获取炉次详情。"""
    item = _get_or_404(heat_id)
    return _to_heat_response(item)


@router.get("/{heat_id}/curve", response_model=HeatWithCurve)
async def get_heat_curve(heat_id: str) -> HeatWithCurve:
    """获取炉次曲线数据。"""
    item = _get_or_404(heat_id)
    return _to_heat_with_curve(item)


@router.get("/{heat_id}/compare", response_model=HeatCompareResponse)
async def get_heat_compare(heat_id: str) -> HeatCompareResponse:
    """获取炉次与基线对比数据。"""
    item = _get_or_404(heat_id)

    heat = _to_heat_with_curve(item)
    baseline = (
        BaselineWithCurveSimple(
            id=item["baseline_id"] or "baseline-001",
            name="标准基线 v2.1",
            power_curve=item["baseline_power_curve"],
            voltage_curve=item["baseline_voltage_curve"],
            tolerance_percent=15.0,
        )
        if item["baseline_id"]
        else None
    )

    baseline_curve = [
        (float(point.timestamp), float(point.value)) for point in item["baseline_power_curve"]
    ]
    current_curve = [(float(point.timestamp), float(point.value)) for point in item["power_curve"]]
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

    return HeatCompareResponse(
        heat=heat,
        baseline=baseline,
        deviation_ranges=deviation_ranges,
        max_deviation=result["max_deviation"],
        avg_deviation=result["avg_deviation"],
    )


@router.post("/{heat_id}/analyze", response_model=HeatAnalyzeResponse)
async def analyze_heat(heat_id: str, data: HeatAnalyzeRequest) -> HeatAnalyzeResponse:
    """触发炉次偏差分析。"""
    item = _get_or_404(heat_id)
    baseline_id = data.baseline_id or item["baseline_id"] or "baseline-001"

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
