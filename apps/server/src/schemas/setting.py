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
