"""炉次 Pydantic 模式"""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import CurvePoint


class DeviationRange(BaseModel):
    """偏差区间"""

    start: int = Field(..., description="开始时间戳(毫秒)")
    end: int = Field(..., description="结束时间戳(毫秒)")
    deviation: float = Field(..., description="偏差百分比")


class HeatResponse(BaseModel):
    """炉次响应"""

    id: str = Field(..., description="炉次ID")
    heat_no: str = Field(..., description="炉次编号")
    description: str | None = Field(default=None, description="炉次描述")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    baseline_id: str | None = Field(default=None, description="对比基线ID")
    deviation_percent: float | None = Field(default=None, description="最大偏差百分比")
    avg_deviation_percent: float | None = Field(default=None, description="平均偏差百分比")
    status: str = Field(..., description="状态: normal/abnormal/pending")
    temperature: float | None = Field(default=None, description="出汤温度")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class HeatWithCurve(HeatResponse):
    """带曲线数据的炉次响应"""

    power_curve: list[CurvePoint] = Field(..., description="功率曲线")
    voltage_curve: list[CurvePoint] = Field(..., description="电压曲线")


class HeatCompareResponse(BaseModel):
    """炉次与基线对比响应"""

    heat: HeatWithCurve = Field(..., description="炉次数据")
    baseline: "BaselineWithCurveSimple | None" = Field(default=None, description="基线数据")
    deviation_ranges: list[DeviationRange] = Field(default_factory=list, description="偏差区间列表")
    max_deviation: float | None = Field(default=None, description="最大偏差百分比")
    avg_deviation: float | None = Field(default=None, description="平均偏差百分比")


class BaselineWithCurveSimple(BaseModel):
    """简化的带曲线基线数据（用于对比）"""

    id: str = Field(..., description="基线ID")
    name: str = Field(..., description="基线名称")
    power_curve: list[CurvePoint] = Field(..., description="功率曲线")
    voltage_curve: list[CurvePoint] = Field(..., description="电压曲线")
    tolerance_percent: float = Field(..., description="容许误差百分比")


class HeatListResponse(BaseModel):
    """炉次列表响应"""

    items: list[HeatResponse] = Field(..., description="炉次列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


class HeatAnalyzeRequest(BaseModel):
    """炉次分析请求"""

    baseline_id: str | None = Field(default=None, description="指定基线ID，为空则使用当前激活基线")


class HeatAnalyzeResponse(BaseModel):
    """炉次分析响应"""

    heat_id: str = Field(..., description="炉次ID")
    baseline_id: str = Field(..., description="使用的基线ID")
    max_deviation: float = Field(..., description="最大偏差百分比")
    avg_deviation: float = Field(..., description="平均偏差百分比")
    status: str = Field(..., description="分析结果状态")
    deviation_ranges: list[DeviationRange] = Field(..., description="偏差区间列表")


class HeatUpdate(BaseModel):
    """更新炉次请求"""

    description: str | None = Field(default=None, description="炉次描述")
    start_time: datetime | None = Field(default=None, description="开始时间")
    end_time: datetime | None = Field(default=None, description="结束时间")


# 更新前向引用
HeatCompareResponse.model_rebuild()
