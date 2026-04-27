"""报表 API 路由。"""

from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime
from io import BytesIO
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..schemas.common import OptionalTimestampMs
from ..time_utils import plant_date_of, utc_now
from .settings import get_plant_timezone
from .tasks import _list_task_store

router = APIRouter(prefix="/reports", tags=["Reports"])


class DailyReportSummary(BaseModel):
    """日报摘要。"""

    date: dt_date = Field(..., description="日期")
    total_heats: int = Field(..., description="总炉次数")
    normal_heats: int = Field(..., description="正常炉次数")
    abnormal_heats: int = Field(..., description="异常炉次数")
    avg_deviation_score: float = Field(..., description="平均偏离分数")
    pending_tasks: int = Field(..., description="待处理任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    generated_at: OptionalTimestampMs = Field(default=None, description="生成时间")


class DailyReportListResponse(BaseModel):
    """日报列表响应。"""

    items: list[DailyReportSummary] = Field(..., description="日报列表")
    total: int = Field(..., description="总数")


class DailyReportDetail(DailyReportSummary):
    """日报详情。"""

    normal_rate: float = Field(..., description="正常率百分比")
    effective_hours: float = Field(..., description="有效稼动时间（小时）")
    top_deviations: list[dict] = Field(..., description="偏差最大的炉次")


def _task_anchor_date(task: dict[str, Any]) -> dt_date | None:
    timezone_name = get_plant_timezone()
    completed_at = task.get("completed_at")
    if isinstance(completed_at, datetime):
        return plant_date_of(completed_at, timezone_name)

    updated_at = task.get("updated_at")
    if isinstance(updated_at, datetime):
        return plant_date_of(updated_at, timezone_name)

    created_at = task.get("created_at")
    if isinstance(created_at, datetime):
        return plant_date_of(created_at, timezone_name)
    return None


def _top_deviations_for_heats(heats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sortable = [
        item
        for item in heats
        if isinstance(item.get("deviation_score"), (float, int)) and item.get("heat_no")
    ]
    sortable.sort(key=lambda item: float(item["deviation_score"]), reverse=True)
    return [
        {
            "heat_no": str(item["heat_no"]),
            "deviation_score": round(float(item["deviation_score"]), 3),
        }
        for item in sortable[:3]
    ]


def _build_daily_report(
    *,
    report_date: dt_date,
    heats: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> DailyReportDetail:
    timezone_name = get_plant_timezone()
    scoped_heats = [
        item
        for item in heats
        if isinstance(item.get("start_time"), datetime)
        and plant_date_of(item["start_time"], timezone_name) == report_date
    ]
    if not scoped_heats:
        raise HTTPException(status_code=404, detail="日报不存在")

    scoped_tasks = [item for item in tasks if _task_anchor_date(item) == report_date]
    deviations = [
        float(item["deviation_score"])
        for item in scoped_heats
        if isinstance(item.get("deviation_score"), (float, int))
    ]
    normal_heats = sum(1 for item in scoped_heats if item.get("status") == "normal")
    abnormal_heats = sum(1 for item in scoped_heats if item.get("status") == "abnormal")
    total_heats = len(scoped_heats)
    normal_rate = round((normal_heats / total_heats) * 100, 2) if total_heats else 0.0
    effective_hours = round(
        sum(
            max((item["end_time"] - item["start_time"]).total_seconds(), 0) / 3600
            for item in scoped_heats
        ),
        2,
    )

    generated_candidates = [
        item["start_time"] for item in scoped_heats if isinstance(item.get("start_time"), datetime)
    ] + [
        item["updated_at"] for item in scoped_tasks if isinstance(item.get("updated_at"), datetime)
    ]

    return DailyReportDetail(
        date=report_date,
        total_heats=total_heats,
        normal_heats=normal_heats,
        abnormal_heats=abnormal_heats,
        avg_deviation_score=round(sum(deviations) / len(deviations), 3) if deviations else 0.0,
        pending_tasks=sum(
            1 for item in scoped_tasks if item.get("status") in {"pending", "in_progress"}
        ),
        completed_tasks=sum(1 for item in scoped_tasks if item.get("status") == "completed"),
        generated_at=max(generated_candidates) if generated_candidates else None,
        normal_rate=normal_rate,
        effective_hours=effective_hours,
        top_deviations=_top_deviations_for_heats(scoped_heats),
    )


async def _report_context() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from . import heats as heats_api

    store = await heats_api._list_heat_store()
    if isinstance(store, dict):
        raw_heats = list(store.values())
    elif isinstance(store, list):
        raw_heats = list(store)
    else:
        raw_heats = []

    heats = [item for item in raw_heats if isinstance(item, dict)]
    tasks = list(_list_task_store().values())
    return heats, tasks


@router.get("/daily", response_model=DailyReportListResponse)
async def list_daily_reports(
    start_date: dt_date | None = Query(default=None, description="开始日期"),  # noqa: B008
    end_date: dt_date | None = Query(default=None, description="结束日期"),  # noqa: B008
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> DailyReportListResponse:
    """获取日报列表。"""
    heats, tasks = await _report_context()
    timezone_name = get_plant_timezone()
    report_dates = sorted(
        {
            plant_date_of(item["start_time"], timezone_name)
            for item in heats
            if isinstance(item.get("start_time"), datetime)
        },
        reverse=True,
    )

    if start_date:
        report_dates = [item for item in report_dates if item >= start_date]
    if end_date:
        report_dates = [item for item in report_dates if item <= end_date]

    total = len(report_dates)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_dates = report_dates[start_idx:end_idx]
    items = [
        DailyReportSummary(
            **_build_daily_report(report_date=item, heats=heats, tasks=tasks).model_dump()
        )
        for item in paged_dates
    ]
    return DailyReportListResponse(items=items, total=total)


@router.get("/daily/{report_date}", response_model=DailyReportDetail)
async def get_daily_report(report_date: dt_date) -> DailyReportDetail:
    """获取指定日期的日报详情。"""
    heats, tasks = await _report_context()
    return _build_daily_report(report_date=report_date, heats=heats, tasks=tasks)


@router.get("/daily/{report_date}/pdf")
async def export_daily_report_pdf(report_date: dt_date) -> StreamingResponse:
    """导出日报 PDF（MVP 占位 PDF）。"""
    report = await get_daily_report(report_date)
    content = (
        "%PDF-1.4\n"
        "1 0 obj<<>>endobj\n"
        "2 0 obj<< /Type /Catalog /Pages 3 0 R >>endobj\n"
        "3 0 obj<< /Type /Pages /Kids [4 0 R] /Count 1 >>endobj\n"
        "4 0 obj<< /Type /Page /Parent 3 0 R /MediaBox [0 0 595 842] /Contents 5 0 R >>endobj\n"
        f"5 0 obj<< /Length 74 >>stream\nBT /F1 12 Tf 50 780 Td (Daily Report: {report.date.isoformat()}) Tj ET\nendstream endobj\n"
        "xref\n0 6\n0000000000 65535 f\n"
        "trailer<< /Root 2 0 R /Size 6 >>\nstartxref\n0\n%%EOF"
    ).encode("latin-1", errors="ignore")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=daily-{report.date.isoformat()}.pdf"
        },
    )


@router.post("/daily/{report_date}/generate", response_model=DailyReportDetail)
async def generate_daily_report(report_date: dt_date) -> DailyReportDetail:
    """手动生成指定日期日报。"""
    report = await get_daily_report(report_date)
    report.generated_at = utc_now()
    return report
