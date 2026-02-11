"""炉次 API 路由。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    BaselineCompareItem,
    CurvePoint,
    DeviationRange,
    HeatAnalyzeRequest,
    HeatAnalyzeResponse,
    HeatCompareResponse,
    HeatListResponse,
    HeatResponse,
    HeatUpdate,
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
    major_issue_triggered = False
    for idx in range(60):
        start_time = now - timedelta(hours=idx + 1)
        end_time = start_time + timedelta(minutes=45)
        status: str = "normal"

        # Demo 两组数据:
        # 组1(前30条): 时间偏移都在容忍值内，但部分数值偏差异常
        # 组2(后30条): 出现重大事故后，后续炉次进入阻断
        group = 1 if idx < 30 else 2

        if group == 1:
            status = "abnormal" if idx % 6 == 0 else "normal"
            cut_status = "normal"
            major_issue = False
            blocked_by_issue = False
            time_offset_percent = round((idx % 5) * 1.5, 2)  # 0~6%
        else:
            if idx == 34:
                major_issue_triggered = True
                status = "abnormal"
                cut_status = "major_issue"
                major_issue = True
                blocked_by_issue = False
                time_offset_percent = 28.5
            elif major_issue_triggered:
                status = "pending"
                cut_status = "blocked"
                major_issue = False
                blocked_by_issue = True
                time_offset_percent = None
            else:
                status = "normal"
                cut_status = "normal"
                major_issue = False
                blocked_by_issue = False
                time_offset_percent = round((idx % 4) * 2.0, 2)

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
            "description": None,
            "start_time": start_time,
            "end_time": end_time,
            "baseline_id": "baseline-001" if status != "pending" else None,
            "baseline_ids": ["baseline-001", "baseline-002"] if status != "pending" else [],
            "deviation_percent": max_dev,
            "avg_deviation_percent": avg_dev,
            "time_offset_percent": time_offset_percent,
            "cut_status": cut_status,
            "major_issue": major_issue,
            "blocked_by_issue": blocked_by_issue,
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
        description=item.get("description"),
        start_time=item["start_time"],
        end_time=item["end_time"],
        baseline_id=item["baseline_id"],
        deviation_percent=item["deviation_percent"],
        avg_deviation_percent=item["avg_deviation_percent"],
        time_offset_percent=item.get("time_offset_percent"),
        cut_status=item.get("cut_status", "normal"),
        major_issue=item.get("major_issue", False),
        blocked_by_issue=item.get("blocked_by_issue", False),
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


@router.get("/stream/mock", response_model=HeatListResponse)
async def get_mock_stream(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> HeatListResponse:
    """模拟实时流入炉次（按最近开始时间返回）。"""
    items = list(_HEAT_STORE.values())
    items.sort(key=lambda x: x["start_time"], reverse=True)
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


@router.patch("/{heat_id}", response_model=HeatResponse)
async def update_heat(heat_id: str, data: HeatUpdate) -> HeatResponse:
    """更新炉次信息（描述、起止时间）。"""
    item = _get_or_404(heat_id)
    original_start = item["start_time"]

    if data.description is not None:
        item["description"] = data.description
    if data.start_time is not None:
        item["start_time"] = data.start_time
    if data.end_time is not None:
        item["end_time"] = data.end_time

    if data.adjust_subsequent and data.start_time is not None:
        delta = data.start_time - original_start
        # 以开始时间顺序调整后续炉次
        current_start = item["start_time"]
        for other in _HEAT_STORE.values():
            if other["id"] == heat_id:
                continue
            if other["start_time"] > current_start:
                other["start_time"] = other["start_time"] + delta
                other["end_time"] = other["end_time"] + delta

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
    baseline_ids = item.get("baseline_ids", [])
    baseline_compares: list[BaselineCompareItem] = []
    for idx, baseline_id in enumerate(baseline_ids):
        baseline_curve_points = _curve_points(
            item["start_time"],
            46,
            435 + idx * 5,
            24 + idx * 3,
            phase=2.0 + idx,
        )
        baseline_voltage_curve_points = _curve_points(
            item["start_time"],
            46,
            380 + idx * 2,
            5 + idx,
            phase=1.0 + idx,
        )

        baseline_curve = [
            (float(point.timestamp), float(point.value)) for point in baseline_curve_points
        ]
        current_curve = [
            (float(point.timestamp), float(point.value)) for point in item["power_curve"]
        ]
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

        baseline_compares.append(
            BaselineCompareItem(
                baseline=BaselineWithCurveSimple(
                    id=baseline_id,
                    name="标准基线 v2.1" if idx == 0 else "高功率基线",
                    power_curve=baseline_curve_points,
                    voltage_curve=baseline_voltage_curve_points,
                    tolerance_percent=15.0,
                ),
                deviation_ranges=deviation_ranges,
                max_deviation=result["max_deviation"],
                avg_deviation=result["avg_deviation"],
            )
        )

    baseline = baseline_compares[0].baseline if baseline_compares else None
    deviation_ranges = baseline_compares[0].deviation_ranges if baseline_compares else []
    max_deviation = baseline_compares[0].max_deviation if baseline_compares else None
    avg_deviation = baseline_compares[0].avg_deviation if baseline_compares else None

    return HeatCompareResponse(
        heat=heat,
        baseline=baseline,
        baselines=baseline_compares,
        deviation_ranges=deviation_ranges,
        max_deviation=max_deviation,
        avg_deviation=avg_deviation,
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
