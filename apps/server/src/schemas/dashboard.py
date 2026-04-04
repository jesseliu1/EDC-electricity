"""仪表盘 Pydantic 模式"""

from pydantic import BaseModel, Field

from .common import CurvePoint, TimestampMs


class DashboardStats(BaseModel):
    """仪表盘统计数据"""

    today_heats: int = Field(..., description="当日炉次数")
    avg_deviation: float = Field(..., description="平均偏差百分比")
    pending_tasks: int = Field(..., description="待处理任务数")
    active_baseline: str | None = Field(default=None, description="当前激活基线名称")
    normal_rate: float = Field(..., description="正常率百分比")


class RealtimeCurveData(BaseModel):
    """实时曲线数据"""

    timestamp: TimestampMs = Field(..., description="数据时间")
    power: list[CurvePoint] = Field(..., description="功率曲线")
    voltage: list[CurvePoint] = Field(..., description="电压曲线")
    baseline_power: list[CurvePoint] | None = Field(default=None, description="基线功率曲线")
    baseline_voltage: list[CurvePoint] | None = Field(default=None, description="基线电压曲线")


class RecentHeat(BaseModel):
    """最近炉次摘要"""

    id: str = Field(..., description="炉次ID")
    heat_no: str = Field(..., description="炉次编号")
    start_time: TimestampMs = Field(..., description="开始时间")
    end_time: TimestampMs = Field(..., description="结束时间")
    status: str = Field(..., description="状态")
    deviation_percent: float | None = Field(default=None, description="偏差百分比")


class RecentHeatsResponse(BaseModel):
    """最近炉次列表响应"""

    items: list[RecentHeat] = Field(..., description="炉次列表")
