"""基线 Pydantic 模式"""
from typing import Literal

from pydantic import BaseModel, Field

from .common import CurvePoint, OptionalTimestampMs, TimestampMs


class CurveData(BaseModel):
    """按指标ID存储的曲线数据"""

    metric_id: str = Field(..., description="指标ID")
    metric_name: str = Field(..., description="指标名称")
    unit: str = Field(..., description="单位")
    color: str = Field(..., description="颜色")
    edc_channel_id: str | None = Field(default=None, description="绑定的宿主通道ID")
    source_channel_name: str | None = Field(default=None, description="来源通道名称")
    source_channel_label: str | None = Field(default=None, description="来源通道摘要")
    points: list[CurvePoint] = Field(..., description="曲线数据点")


class BaselineCreate(BaseModel):
    """创建基线请求（黄金基线实例）"""

    name: str = Field(..., min_length=1, max_length=100, description="实例名称")
    description: str | None = Field(default=None, description="基线描述")
    definition_id: str = Field(..., description="所属基线定义ID")
    source_heat_id: str | None = Field(default=None, description="来源炉次ID，可为空")
    selected_start_time: TimestampMs = Field(..., description="图上选点开始时间")
    selected_end_time: TimestampMs = Field(..., description="图上选点结束时间")
    effective_from: OptionalTimestampMs = Field(default=None, description="生效时间")
    tolerance_percent: float = Field(default=15.0, ge=0, le=100, description="容许误差百分比")
    is_default: bool = Field(default=False, description="是否默认黄金基线")


class BaselineUpdate(BaseModel):
    """更新基线请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="基线名称")
    description: str | None = Field(default=None, description="基线描述")
    selected_start_time: OptionalTimestampMs = Field(default=None, description="图上选点开始时间")
    selected_end_time: OptionalTimestampMs = Field(default=None, description="图上选点结束时间")
    effective_from: OptionalTimestampMs = Field(default=None, description="生效时间")
    tolerance_percent: float | None = Field(
        default=None, ge=0, le=100, description="容许误差百分比"
    )
    is_default: bool | None = Field(default=None, description="是否默认黄金基线")


class BaselineResponse(BaseModel):
    """基线响应（黄金基线实例）"""

    id: str = Field(..., description="基线ID")
    name: str = Field(..., description="实例名称")
    description: str | None = Field(default=None, description="基线描述")
    definition_id: str = Field(..., description="所属基线定义ID")
    definition_name: str = Field(default="", description="所属基线定义名称")
    expected_duration_minutes: int = Field(..., description="所属定义的预期炉次时长（分钟）")
    is_default: bool = Field(default=False, description="是否默认黄金基线")
    source_heat_id: str | None = Field(default=None, description="来源炉次ID，可为空")
    selected_start_time: OptionalTimestampMs = Field(default=None, description="图上选点开始时间")
    selected_end_time: OptionalTimestampMs = Field(default=None, description="图上选点结束时间")
    effective_from: OptionalTimestampMs = Field(default=None, description="生效时间")
    tolerance_percent: float = Field(..., description="容许误差百分比")
    status: str = Field(..., description="状态: draft/published/disabled")
    version: int = Field(..., description="版本号")
    curve_source: str = Field(default="none", description="基线曲线来源")
    created_at: TimestampMs = Field(..., description="创建时间")
    updated_at: TimestampMs = Field(..., description="更新时间")
    published_at: OptionalTimestampMs = Field(default=None, description="发布时间")

    model_config = {"from_attributes": True}


class BaselineWithCurve(BaselineResponse):
    """带曲线数据的基线响应"""

    # 新字段：按指标ID存储的动态曲线
    curves_data: list[CurveData] = Field(default_factory=list, description="动态曲线数据")
    # 旧字段：保留兼容（先加新不破旧）
    power_curve: list[CurvePoint] = Field(default_factory=list, description="功率曲线")
    voltage_curve: list[CurvePoint] = Field(default_factory=list, description="电压曲线")
    temperature: float | None = Field(default=None, description="出汤温度")


class BaselinePreviewResponse(BaseModel):
    """基线向导候选曲线预览响应"""

    definition_id: str = Field(..., description="所属定义ID")
    source_heat_id: str | None = Field(default=None, description="来源炉次ID，可为空")
    range_start: TimestampMs = Field(..., description="预览开始时间")
    range_end: TimestampMs = Field(..., description="预览结束时间")
    curves_data: list[CurveData] = Field(default_factory=list, description="候选曲线数据")


class BaselinePreviewJobResponse(BaseModel):
    """基线向导整天预览任务状态响应"""

    job_key: str = Field(..., description="预览任务键")
    definition_id: str = Field(..., description="所属定义ID")
    source_heat_id: str | None = Field(default=None, description="来源炉次ID，可为空")
    status: Literal["idle", "running", "succeeded", "failed"] = Field(
        ..., description="任务状态"
    )
    range_start: TimestampMs = Field(..., description="预览开始时间")
    range_end: TimestampMs = Field(..., description="预览结束时间")
    curves_data: list[CurveData] = Field(default_factory=list, description="候选曲线数据")
    last_error: str | None = Field(default=None, description="最近错误")
    created_at: OptionalTimestampMs = Field(default=None, description="任务创建时间")
    started_at: OptionalTimestampMs = Field(default=None, description="任务开始时间")
    updated_at: OptionalTimestampMs = Field(default=None, description="最近状态更新时间")
    completed_at: OptionalTimestampMs = Field(default=None, description="任务完成时间")


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
    is_default: bool = Field(default=False, description="是否默认黄金基线")

    model_config = {"from_attributes": True}
