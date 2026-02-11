"""基线 Pydantic 模式"""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import CurvePoint


class CurveData(BaseModel):
    """按指标ID存储的曲线数据"""

    metric_id: str = Field(..., description="指标ID")
    metric_name: str = Field(..., description="指标名称")
    unit: str = Field(..., description="单位")
    color: str = Field(..., description="颜色")
    points: list[CurvePoint] = Field(..., description="曲线数据点")


class BaselineCreate(BaseModel):
    """创建基线请求（黄金基线实例）"""

    name: str = Field(..., min_length=1, max_length=100, description="实例名称")
    description: str | None = Field(default=None, description="基线描述")
    definition_id: str = Field(..., description="所属基线定义ID")
    source_heat_id: str = Field(..., description="来源炉次ID")
    selected_start_time: datetime | None = Field(default=None, description="图上选点开始时间")
    selected_end_time: datetime | None = Field(default=None, description="图上选点结束时间")
    tolerance_percent: float = Field(default=15.0, ge=0, le=100, description="容许误差百分比")


class BaselineUpdate(BaseModel):
    """更新基线请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="基线名称")
    description: str | None = Field(default=None, description="基线描述")
    tolerance_percent: float | None = Field(
        default=None, ge=0, le=100, description="容许误差百分比"
    )


class BaselineResponse(BaseModel):
    """基线响应（黄金基线实例）"""

    id: str = Field(..., description="基线ID")
    name: str = Field(..., description="实例名称")
    description: str | None = Field(default=None, description="基线描述")
    definition_id: str = Field(..., description="所属基线定义ID")
    definition_name: str = Field(default="", description="所属基线定义名称")
    source_heat_id: str = Field(..., description="来源炉次ID")
    selected_start_time: datetime | None = Field(default=None, description="图上选点开始时间")
    selected_end_time: datetime | None = Field(default=None, description="图上选点结束时间")
    tolerance_percent: float = Field(..., description="容许误差百分比")
    status: str = Field(..., description="状态: draft/published/disabled")
    version: int = Field(..., description="版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    published_at: datetime | None = Field(default=None, description="发布时间")

    model_config = {"from_attributes": True}


class BaselineWithCurve(BaselineResponse):
    """带曲线数据的基线响应"""

    # 新字段：按指标ID存储的动态曲线
    curves_data: list[CurveData] = Field(default_factory=list, description="动态曲线数据")
    # 旧字段：保留兼容（先加新不破旧）
    power_curve: list[CurvePoint] = Field(default_factory=list, description="功率曲线")
    voltage_curve: list[CurvePoint] = Field(default_factory=list, description="电压曲线")
    temperature: float | None = Field(default=None, description="出汤温度")


class BaselineListResponse(BaseModel):
    """基线列表响应"""

    items: list[BaselineResponse] = Field(..., description="基线列表")
    total: int = Field(..., description="总数")


class BaselineSummary(BaseModel):
    """基线摘要（用于下拉选择等场景）"""

    id: str = Field(..., description="基线ID")
    name: str = Field(..., description="基线名称")
    status: str = Field(..., description="状态")
    version: int = Field(..., description="版本号")

    model_config = {"from_attributes": True}
