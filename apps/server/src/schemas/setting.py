"""设置 Pydantic 模式"""

from pydantic import BaseModel, Field


class SettingItem(BaseModel):
    """设置项"""

    key: str = Field(..., description="配置键名")
    value: str = Field(..., description="配置值")
    description: str | None = Field(default=None, description="配置描述")


class SettingsResponse(BaseModel):
    """设置列表响应"""

    items: list[SettingItem] = Field(..., description="设置列表")


class HostChannelItem(BaseModel):
    """宿主层已添加通道项"""

    id: str = Field(..., description="宿主通道唯一ID")
    device_name: str = Field(..., description="来源设备名称")
    device_type: str = Field(..., description="来源设备类型")
    area: str = Field(..., description="来源区域")
    suid: str = Field(..., description="设备UID")
    cuid: str = Field(..., description="通道UID")
    channel_name: str = Field(..., description="通道名称")
    unit: str = Field(..., description="通道单位")
    last_value: str = Field(..., description="最近一次读数")
    status: str = Field(..., description="通道状态")


class HostChannelCollectionResponse(BaseModel):
    """宿主层已添加通道列表响应"""

    items: list[HostChannelItem] = Field(..., description="宿主层已添加通道列表")
    total: int = Field(..., description="通道总数")


class SettingsUpdateRequest(BaseModel):
    """批量更新设置请求"""

    settings: dict[str, str] = Field(..., description="键值对形式的设置")


class ToleranceSettingRequest(BaseModel):
    """容许误差设置请求"""

    tolerance_percent: float = Field(..., ge=0, le=100, description="容许误差百分比")


class EDCConnectionRequest(BaseModel):
    """EDC 连接配置请求"""

    base_url: str = Field(..., description="EDC API 基础URL")
    api_key: str | None = Field(default=None, description="API 密钥")


class ReportSettingRequest(BaseModel):
    """报表设置请求"""

    generation_hour: int = Field(..., ge=0, le=23, description="日报生成时间（小时）")


class CuttingSettingRequest(BaseModel):
    """炉次切割设置请求"""

    time_tolerance_percent: float = Field(..., ge=0, le=100, description="时间偏移容忍率")
    major_issue_duration_minutes: int = Field(
        ..., ge=1, le=120, description="持续不一致判定重大事故的分钟数"
    )
    work_start_time: str = Field(..., description="上班时间，格式 HH:mm")
    work_end_time: str = Field(..., description="下班时间，格式 HH:mm")
    break_periods: list[str] = Field(default_factory=list, description="休息时段，格式 HH:mm-HH:mm")


class BaselineLengthScopeSettingRequest(BaseModel):
    """基线等长校验范围设置"""

    scope_mode: str = Field(
        ..., description="等长校验范围: definition/system/production_line(预留)"
    )
