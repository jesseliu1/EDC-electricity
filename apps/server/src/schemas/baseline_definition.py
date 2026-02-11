"""黄金基线定义 Pydantic 模式"""

from datetime import datetime

from pydantic import BaseModel, Field


class MetricDefinitionResponse(BaseModel):
    """指标通道响应"""

    id: str = Field(..., description="指标ID")
    name: str = Field(..., description="指标名称")
    unit: str = Field(..., description="单位")
    color: str = Field(..., description="图表显示颜色")
    sort_order: int = Field(..., description="排序序号")
    edc_channel_id: str | None = Field(default=None, description="EDC通道ID（L1阶段映射）")


class MetricDefinitionCreate(BaseModel):
    """创建指标通道请求"""

    name: str = Field(..., min_length=1, max_length=50, description="指标名称")
    unit: str = Field(..., min_length=1, max_length=20, description="单位")
    color: str = Field(..., min_length=4, max_length=9, description="颜色值，如 #409EFF")
    sort_order: int = Field(default=0, ge=0, description="排序序号")
    edc_channel_id: str | None = Field(default=None, description="EDC通道ID")


class MetricDefinitionUpdate(BaseModel):
    """更新指标通道请求"""

    name: str | None = Field(default=None, min_length=1, max_length=50, description="指标名称")
    unit: str | None = Field(default=None, min_length=1, max_length=20, description="单位")
    color: str | None = Field(default=None, min_length=4, max_length=9, description="颜色值")
    sort_order: int | None = Field(default=None, ge=0, description="排序序号")
    edc_channel_id: str | None = Field(default=None, description="EDC通道ID")


class BaselineDefinitionCreate(BaseModel):
    """创建黄金基线定义请求"""

    definition_name: str = Field(..., min_length=1, max_length=100, description="黄金基线定义名")
    description: str | None = Field(default=None, description="描述")
    expected_duration_minutes: int = Field(..., ge=1, le=1440, description="预期炉次时长（分钟）")
    metrics: list[MetricDefinitionCreate] = Field(default_factory=list, description="指标通道列表")


class BaselineDefinitionUpdate(BaseModel):
    """更新黄金基线定义请求"""

    definition_name: str | None = Field(
        default=None, min_length=1, max_length=100, description="黄金基线定义名"
    )
    description: str | None = Field(default=None, description="描述")
    expected_duration_minutes: int | None = Field(
        default=None, ge=1, le=1440, description="预期炉次时长（分钟）"
    )


class BaselineDefinitionResponse(BaseModel):
    """黄金基线定义响应"""

    id: str = Field(..., description="定义ID")
    definition_name: str = Field(..., description="黄金基线定义名")
    description: str | None = Field(default=None, description="描述")
    expected_duration_minutes: int = Field(..., description="预期炉次时长（分钟）")
    status: str = Field(..., description="状态: active/disabled")
    metrics: list[MetricDefinitionResponse] = Field(
        default_factory=list, description="指标通道列表"
    )
    instance_count: int = Field(default=0, description="关联的黄金基线实例数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class BaselineDefinitionListResponse(BaseModel):
    """黄金基线定义列表响应"""

    items: list[BaselineDefinitionResponse] = Field(..., description="定义列表")
    total: int = Field(..., description="总数")
