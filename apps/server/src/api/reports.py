"""报表 API 路由。"""

from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/reports", tags=["Reports"])


class DailyReportSummary(BaseModel):
    """日报摘要。"""

    date: dt_date = Field(..., description="日期")
    total_heats: int = Field(..., description="总炉次数")
    normal_heats: int = Field(..., description="正常炉次数")
    abnormal_heats: int = Field(..., description="异常炉次数")
    avg_deviation: float = Field(..., description="平均偏差百分比")
    pending_tasks: int = Field(..., description="待处理任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    generated_at: datetime | None = Field(default=None, description="生成时间")


class DailyReportListResponse(BaseModel):
    """日报列表响应。"""

    items: list[DailyReportSummary] = Field(..., description="日报列表")
    total: int = Field(..., description="总数")


class DailyReportDetail(DailyReportSummary):
    """日报详情。"""

    normal_rate: float = Field(..., description="正常率百分比")
    effective_hours: float = Field(..., description="有效稼动时间（小时）")
    top_deviations: list[dict] = Field(..., description="偏差最大的炉次")


def _build_report(report_date: dt_date, offset: int = 0) -> DailyReportDetail:
    total = 12 + offset
    abnormal = 2 + (offset % 2)
    normal = max(total - abnormal, 0)
    normal_rate = round((normal / total) * 100, 2) if total else 0.0
    avg_dev = round(5.3 + offset * 0.25, 3)
    return DailyReportDetail(
        date=report_date,
        total_heats=total,
        normal_heats=normal,
        abnormal_heats=abnormal,
        avg_deviation=avg_dev,
        pending_tasks=max(3 - offset, 0),
        completed_tasks=6 + offset,
        generated_at=datetime.combine(report_date, datetime.min.time()) + timedelta(hours=2),
        normal_rate=normal_rate,
        effective_hours=round(18.0 + offset * 0.4, 2),
        top_deviations=[
            {
                "heat_no": f"H{report_date.strftime('%Y%m%d')}-003",
                "deviation": round(22.5 - offset, 3),
            },
            {
                "heat_no": f"H{report_date.strftime('%Y%m%d')}-007",
                "deviation": round(18.3 - offset * 0.5, 3),
            },
        ],
    )


@router.get("/daily", response_model=DailyReportListResponse)
async def list_daily_reports(
    start_date: dt_date | None = Query(default=None, description="开始日期"),  # noqa: B008
    end_date: dt_date | None = Query(default=None, description="结束日期"),  # noqa: B008
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> DailyReportListResponse:
    """获取日报列表。"""
    today = dt_date.today()
    all_items = [_build_report(today - timedelta(days=i), i) for i in range(30)]

    if start_date:
        all_items = [item for item in all_items if item.date >= start_date]
    if end_date:
        all_items = [item for item in all_items if item.date <= end_date]

    total = len(all_items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged = all_items[start_idx:end_idx]

    summaries = [DailyReportSummary(**item.model_dump()) for item in paged]
    return DailyReportListResponse(items=summaries, total=total)


@router.get("/daily/{report_date}", response_model=DailyReportDetail)
async def get_daily_report(report_date: dt_date) -> DailyReportDetail:
    """获取指定日期的日报详情。"""
    if report_date > dt_date.today() + timedelta(days=1):
        raise HTTPException(status_code=404, detail="日报不存在")
    return _build_report(report_date, 0)


@router.get("/daily/{report_date}/pdf")
async def export_daily_report_pdf(report_date: dt_date) -> StreamingResponse:
    """导出日报 PDF（MVP 占位 PDF）。"""
    report = _build_report(report_date)
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
    generated = _build_report(report_date)
    generated.generated_at = datetime.now()
    return generated
