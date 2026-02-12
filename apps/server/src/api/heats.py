"""炉次 API 路由。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    BaselineCompareItem,
    CurvePoint,
    CuttingTimelineEvent,
    CuttingTimelineResponse,
    DeviationRange,
    HeatAnalyzeRequest,
    HeatAnalyzeResponse,
    HeatCompareResponse,
    HeatListResponse,
    HeatResponse,
    HeatResumeCuttingRequest,
    HeatUpdate,
    HeatWithCurve,
)
from ..schemas.heat import BaselineWithCurveSimple
from ..services import DeviationService
from .settings import _SETTINGS_STORE

router = APIRouter(prefix="/heats", tags=["Heats"])
deviation_service = DeviationService()


def _get_cutting_config() -> dict[str, Any]:
    """读取切割配置。"""
    tolerance = float(_SETTINGS_STORE.get("time_tolerance_percent", {}).get("value") or 10.0)
    major_issue_minutes = int(
        _SETTINGS_STORE.get("major_issue_duration_minutes", {}).get("value") or 8
    )
    work_start = str(_SETTINGS_STORE.get("work_start_time", {}).get("value") or "08:00")
    work_end = str(_SETTINGS_STORE.get("work_end_time", {}).get("value") or "18:00")
    break_raw = str(_SETTINGS_STORE.get("break_periods", {}).get("value") or "12:00-13:00")
    break_periods = [item.strip() for item in break_raw.split(",") if item.strip()]
    return {
        "tolerance": tolerance,
        "major_issue_minutes": major_issue_minutes,
        "work_start": work_start,
        "work_end": work_end,
        "break_periods": break_periods,
    }


def _to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _schedule_tag_of(start_time: datetime, config: dict[str, Any]) -> str:
    """根据时间判断班次标签。"""
    current = start_time.hour * 60 + start_time.minute
    work_start = _to_minutes(config["work_start"])
    work_end = _to_minutes(config["work_end"])
    if current < work_start or current > work_end:
        return "off_shift"

    for period in config["break_periods"]:
        try:
            start_str, end_str = period.split("-", 1)
            if _to_minutes(start_str) <= current <= _to_minutes(end_str):
                return "break"
        except ValueError:
            continue
    return "work"


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
    config = _get_cutting_config()
    seeded: dict[str, dict[str, Any]] = {}
    major_issue_triggered = False
    for idx in range(60):
        start_time = now - timedelta(hours=idx + 1)
        end_time = start_time + timedelta(minutes=45)
        status: str = "normal"

        # Demo 两组数据:
        # 组1(前30条): 时间偏移都在容忍值内，但部分数值偏差异常
        # 组2(后30条): 连续不一致超过阈值触发重大事故，后续阻断
        group = 1 if idx < 30 else 2

        schedule_tag = _schedule_tag_of(start_time, config)
        mismatch_minutes = 3 + (idx % 6)
        time_offset_percent = round((idx % 7) * 1.6, 2)
        cut_reason: str | None = None
        cut_status = "normal"
        major_issue = False
        blocked_by_issue = False

        if group == 1:
            status = "abnormal" if idx % 6 == 0 else "normal"
            mismatch_minutes = 4 + (idx % 4)
            time_offset_percent = round((idx % 5) * 1.4, 2)
        else:
            mismatch_minutes = 6 + (idx % 7)
            if idx == 34:
                mismatch_minutes = max(config["major_issue_minutes"] + 2, mismatch_minutes)

        if schedule_tag in {"break", "off_shift"}:
            cut_status = "blocked"
            blocked_by_issue = True
            status = "pending"
            cut_reason = "schedule_window"
            time_offset_percent = None
        elif major_issue_triggered:
            cut_status = "blocked"
            blocked_by_issue = True
            status = "pending"
            cut_reason = "major_issue_lock"
            time_offset_percent = None
        elif mismatch_minutes >= config["major_issue_minutes"]:
            cut_status = "major_issue"
            major_issue = True
            status = "abnormal"
            cut_reason = "continuous_mismatch"
            major_issue_triggered = True
        elif time_offset_percent > config["tolerance"]:
            status = "abnormal"
            cut_reason = "time_offset_exceed"
        else:
            cut_reason = "within_tolerance"

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
            "mismatch_duration_minutes": mismatch_minutes,
            "schedule_tag": schedule_tag,
            "cut_reason": cut_reason,
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
_NEXT_HEAT_INDEX = len(_HEAT_STORE) + 1


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
        mismatch_duration_minutes=item.get("mismatch_duration_minutes"),
        schedule_tag=item.get("schedule_tag", "work"),
        cut_reason=item.get("cut_reason"),
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


def _latest_heat() -> dict[str, Any] | None:
    if not _HEAT_STORE:
        return None
    return max(_HEAT_STORE.values(), key=lambda x: x["start_time"])


def _build_ingested_heat() -> dict[str, Any]:
    """构造一条实时流入的模拟炉次。"""
    global _NEXT_HEAT_INDEX

    config = _get_cutting_config()
    latest = _latest_heat()
    start_time = (
        latest["start_time"] + timedelta(minutes=50)
        if latest
        else datetime.now().replace(second=0, microsecond=0)
    )
    end_time = start_time + timedelta(minutes=45)

    schedule_tag = _schedule_tag_of(start_time, config)
    mismatch_minutes = 3 + (_NEXT_HEAT_INDEX % 9)
    time_offset_percent = round((_NEXT_HEAT_INDEX % 8) * 1.7, 2)

    has_major_issue_lock = any(
        item.get("cut_status") == "major_issue" or item.get("cut_reason") == "major_issue_lock"
        for item in _HEAT_STORE.values()
    )

    cut_status = "normal"
    status = "normal"
    major_issue = False
    blocked_by_issue = False
    cut_reason = "within_tolerance"

    if schedule_tag in {"break", "off_shift"}:
        cut_status = "blocked"
        status = "pending"
        blocked_by_issue = True
        cut_reason = "schedule_window"
        time_offset_percent = None
    elif has_major_issue_lock:
        cut_status = "blocked"
        status = "pending"
        blocked_by_issue = True
        cut_reason = "major_issue_lock"
        time_offset_percent = None
    elif mismatch_minutes >= config["major_issue_minutes"]:
        cut_status = "major_issue"
        status = "abnormal"
        major_issue = True
        cut_reason = "continuous_mismatch"
    elif time_offset_percent > config["tolerance"]:
        status = "abnormal"
        cut_reason = "time_offset_exceed"

    power_curve = _curve_points(
        start_time, 46, 430 + (_NEXT_HEAT_INDEX % 7), 35, phase=float(_NEXT_HEAT_INDEX)
    )
    voltage_curve = _curve_points(
        start_time, 46, 378 + (_NEXT_HEAT_INDEX % 5), 8, phase=float(_NEXT_HEAT_INDEX + 3)
    )
    baseline_power_curve = _curve_points(start_time, 46, 435, 24, phase=2.0)
    baseline_voltage_curve = _curve_points(start_time, 46, 380, 5, phase=1.0)

    max_dev = None if status == "pending" else round(4.2 + (_NEXT_HEAT_INDEX % 9) * 1.8, 3)
    avg_dev = None if status == "pending" else round(2.1 + (_NEXT_HEAT_INDEX % 7) * 1.1, 3)

    heat_id = f"heat-{_NEXT_HEAT_INDEX:03d}"
    heat = {
        "id": heat_id,
        "heat_no": f"H{start_time.strftime('%Y%m%d')}-{_NEXT_HEAT_INDEX:03d}",
        "description": None,
        "start_time": start_time,
        "end_time": end_time,
        "baseline_id": "baseline-001" if status != "pending" else None,
        "baseline_ids": ["baseline-001", "baseline-002"] if status != "pending" else [],
        "deviation_percent": max_dev,
        "avg_deviation_percent": avg_dev,
        "time_offset_percent": time_offset_percent,
        "mismatch_duration_minutes": mismatch_minutes,
        "schedule_tag": schedule_tag,
        "cut_reason": cut_reason,
        "cut_status": cut_status,
        "major_issue": major_issue,
        "blocked_by_issue": blocked_by_issue,
        "status": status,
        "temperature": round(1450 + (_NEXT_HEAT_INDEX % 6) * 5.5, 2),
        "created_at": start_time,
        "power_curve": power_curve,
        "voltage_curve": voltage_curve,
        "baseline_power_curve": baseline_power_curve,
        "baseline_voltage_curve": baseline_voltage_curve,
    }
    _NEXT_HEAT_INDEX += 1
    return heat


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


@router.post("/stream/mock/ingest", response_model=HeatResponse)
async def ingest_mock_stream_heat() -> HeatResponse:
    """模拟实时流入一条新炉次并返回。"""
    heat = _build_ingested_heat()
    _HEAT_STORE[heat["id"]] = heat
    return _to_heat_response(heat)


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


@router.post("/{heat_id}/resume-cutting", response_model=HeatResponse)
async def resume_cutting(heat_id: str, data: HeatResumeCuttingRequest) -> HeatResponse:
    """恢复重大事故后的炉次切割。"""
    item = _get_or_404(heat_id)

    item["cut_status"] = "normal"
    item["major_issue"] = False
    item["blocked_by_issue"] = False
    item["cut_reason"] = "manual_resume"
    item["schedule_tag"] = "work"
    item["mismatch_duration_minutes"] = min(item.get("mismatch_duration_minutes") or 0, 4)
    if item["status"] == "pending":
        item["status"] = "normal"
    item["time_offset_percent"] = min(item.get("time_offset_percent") or 0.0, 8.0)

    if data.adjust_subsequent:
        current_start = item["start_time"]
        for other in _HEAT_STORE.values():
            if other["id"] == heat_id:
                continue
            if other["start_time"] > current_start and other.get("cut_status") == "blocked":
                other["cut_status"] = "normal"
                other["blocked_by_issue"] = False
                other["major_issue"] = False
                other["cut_reason"] = "manual_resume_followup"
                other["schedule_tag"] = "work"
                other["mismatch_duration_minutes"] = 4
                if other["status"] == "pending":
                    other["status"] = "normal"
                other["time_offset_percent"] = 6.0

    return _to_heat_response(item)


@router.get("/{heat_id}/cutting-timeline", response_model=CuttingTimelineResponse)
async def get_cutting_timeline(heat_id: str) -> CuttingTimelineResponse:
    """获取炉次切割判定时间轴。"""
    item = _get_or_404(heat_id)
    config = _get_cutting_config()

    start_time: datetime = item["start_time"]
    events: list[CuttingTimelineEvent] = [
        CuttingTimelineEvent(
            timestamp=start_time,
            event_type="stream_in",
            title="实时流入",
            detail="炉次进入切割判定队列",
        ),
        CuttingTimelineEvent(
            timestamp=start_time + timedelta(minutes=1),
            event_type="window_check",
            title="窗口判定",
            detail=(
                f"连续不一致 {item.get('mismatch_duration_minutes') or 0} 分钟，"
                f"阈值 {config['major_issue_minutes']} 分钟"
            ),
        ),
        CuttingTimelineEvent(
            timestamp=start_time + timedelta(minutes=2),
            event_type="schedule_check",
            title="班次窗口检查",
            detail=f"当前窗口：{item.get('schedule_tag', 'work')}",
        ),
    ]

    cut_status = item.get("cut_status", "normal")
    if cut_status == "major_issue":
        events.append(
            CuttingTimelineEvent(
                timestamp=start_time + timedelta(minutes=3),
                event_type="major_issue",
                title="触发重大事故",
                detail="连续不一致超过阈值，后续炉次阻断",
            )
        )
    elif cut_status == "blocked":
        events.append(
            CuttingTimelineEvent(
                timestamp=start_time + timedelta(minutes=3),
                event_type="blocked",
                title="切割阻断",
                detail=f"阻断原因：{item.get('cut_reason') or 'unknown'}",
            )
        )
    else:
        events.append(
            CuttingTimelineEvent(
                timestamp=start_time + timedelta(minutes=3),
                event_type="normal",
                title="判定正常",
                detail="切割继续执行",
            )
        )

    return CuttingTimelineResponse(heat_id=heat_id, events=events)


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
