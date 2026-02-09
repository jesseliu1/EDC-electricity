"""报表 API 路由"""

from datetime import date as dt_date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/reports", tags=["Reports"])


class DailyReportSummary(BaseModel):
    """日报摘要"""

    date: dt_date = Field(..., description="日期")
    total_heats: int = Field(..., description="总炉次数")
    normal_heats: int = Field(..., description="正常炉次数")
    abnormal_heats: int = Field(..., description="异常炉次数")
    avg_deviation: float = Field(..., description="平均偏差百分比")
    pending_tasks: int = Field(..., description="待处理任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    generated_at: datetime | None = Field(default=None, description="生成时间")


class DailyReportListResponse(BaseModel):
    """日报列表响应"""

    items: list[DailyReportSummary] = Field(..., description="日报列表")
    total: int = Field(..., description="总数")


class DailyReportDetail(DailyReportSummary):
    """日报详情"""

    normal_rate: float = Field(..., description="正常率百分比")
    effective_hours: float = Field(..., description="有效稼动时间（小时）")
    top_deviations: list[dict] = Field(..., description="偏差最大的炉次")


@router.get("/daily", response_model=DailyReportListResponse)
async def list_daily_reports(
    start_date: dt_date | None = Query(default=None, description="开始日期"),
    end_date: dt_date | None = Query(default=None, description="结束日期"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> DailyReportListResponse:
    """获取日报列表"""
    # TODO: 实现真实逻辑
    today = dt_date.today()
    items = []
    for i in range(min(page_size, 7)):
        report_date = today - timedelta(days=i)
        items.append(
            DailyReportSummary(
                date=report_date,
                total_heats=12 + i,
                normal_heats=10 + i,
                abnormal_heats=2,
                avg_deviation=5.5 + i * 0.3,
                pending_tasks=3 - i if i < 3 else 0,
                completed_tasks=i,
                generated_at=datetime.combine(report_date, datetime.min.time())
                + timedelta(hours=2),
            )
        )

    return DailyReportListResponse(items=items, total=len(items))


@router.get("/daily/{report_date}", response_model=DailyReportDetail)
async def get_daily_report(report_date: dt_date) -> DailyReportDetail:
    """获取指定日期的日报详情"""
    # TODO: 实现真实逻辑
    return DailyReportDetail(
        date=report_date,
        total_heats=12,
        normal_heats=10,
        abnormal_heats=2,
        avg_deviation=5.5,
        pending_tasks=3,
        completed_tasks=5,
        generated_at=datetime.combine(report_date, datetime.min.time()) + timedelta(hours=2),
        normal_rate=83.3,
        effective_hours=18.5,
        top_deviations=[
            {"heat_no": "H20240101-003", "deviation": 22.5},
            {"heat_no": "H20240101-007", "deviation": 18.3},
        ],
    )


@router.get("/daily/{report_date}/pdf")
async def export_daily_report_pdf(report_date: dt_date) -> StreamingResponse:
    """导出日报 PDF"""
    # TODO: 实现真实逻辑
    raise HTTPException(status_code=501, detail="PDF 导出功能尚未实现")


@router.post("/daily/{report_date}/generate", response_model=DailyReportDetail)
async def generate_daily_report(report_date: dt_date) -> DailyReportDetail:
    """手动生成指定日期的日报"""
    # TODO: 实现真实逻辑
    return DailyReportDetail(
        date=report_date,
        total_heats=12,
        normal_heats=10,
        abnormal_heats=2,
        avg_deviation=5.5,
        pending_tasks=3,
        completed_tasks=5,
        generated_at=datetime.now(),
        normal_rate=83.3,
        effective_hours=18.5,
        top_deviations=[
            {"heat_no": "H20240101-003", "deviation": 22.5},
            {"heat_no": "H20240101-007", "deviation": 18.3},
        ],
    )
