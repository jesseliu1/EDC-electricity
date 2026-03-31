"""换源统一入口 schema。"""

from pydantic import BaseModel, Field


class SourceSwitchRequest(BaseModel):
    """统一换源请求。"""

    source_revision: int = Field(..., ge=1, description="调用方认知的当前 source_revision")
    base_url: str = Field(..., description="目标 EDC API 基础URL")
    username: str | None = Field(default=None, description="目标账号")
    password: str | None = Field(default=None, description="目标密码")
    api_key: str | None = Field(default=None, description="目标 API Key")


class SourceSwitchResponse(BaseModel):
    """统一换源响应。"""

    success: bool = Field(..., description="是否处理成功")
    message: str = Field(..., description="处理结果摘要")
    source_revision: int = Field(..., ge=1, description="处理完成后的最新 source_revision")
    source_identity_changed: bool = Field(..., description="源身份是否发生变化")
    connection_material_changed: bool = Field(..., description="连接材料是否发生变化")
    cleared_host_channel_count: int = Field(..., ge=0, description="清空的宿主通道数")
    cleared_host_channel_catalog_count: int = Field(..., ge=0, description="清空的通道目录缓存数")
    cleared_channel_role_binding_count: int = Field(
        ...,
        ge=0,
        description="清空的业务通道角色绑定数",
    )
    cleared_definition_binding_count: int = Field(..., ge=0, description="清空的基线定义通道绑定数")
    cleared_active_baseline_id: str = Field(..., description="被解除的活动基线 ID")
    next_source: str = Field(..., description="切换后的源地址")
