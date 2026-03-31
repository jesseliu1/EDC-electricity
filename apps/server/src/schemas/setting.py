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


class HostChannelCollectionUpdateRequest(BaseModel):
    """宿主层已添加通道列表更新请求"""

    source_revision: int = Field(..., ge=1, description="调用方认知的当前 source_revision")
    items: list[HostChannelItem] = Field(..., description="宿主层保存的已添加通道列表")


class ChannelRoleBindingItem(BaseModel):
    """业务通道角色绑定项"""

    role_key: str = Field(..., description="角色键")
    label: str = Field(..., description="角色名称")
    description: str = Field(..., description="角色说明")
    metric_kind: str = Field(..., description="默认匹配的指标类型")
    required: bool = Field(..., description="是否为必需角色")
    channel_id: str | None = Field(default=None, description="当前绑定的宿主通道 ID")
    configured: bool = Field(..., description="当前是否已完成绑定")
    source_channel_name: str | None = Field(default=None, description="来源通道名称")
    source_channel_label: str | None = Field(default=None, description="来源通道显示标签")


class ChannelRoleBindingCollectionResponse(BaseModel):
    """业务通道角色绑定列表响应"""

    items: list[ChannelRoleBindingItem] = Field(..., description="角色绑定列表")
    total: int = Field(..., ge=0, description="角色总数")
    configured_count: int = Field(..., ge=0, description="已配置角色数")
    missing_required_role_keys: list[str] = Field(
        default_factory=list,
        description="当前缺失的必需角色键",
    )


class ChannelRoleBindingUpdateRequest(BaseModel):
    """业务通道角色绑定更新请求"""

    bindings: dict[str, str | None] = Field(..., description="role_key -> channel_id")


class HostConnectivityMeta(BaseModel):
    """宿主连接摘要元信息"""

    source: str = Field(..., description="宿主直连来源描述")
    sensor_count: int = Field(..., ge=0, description="已发现设备数")
    channel_count: int = Field(..., ge=0, description="已发现通道总数")
    enabled_channel_count: int = Field(..., ge=0, description="已启用通道数")


class HostConnectivityStatusResponse(BaseModel):
    """宿主连接状态响应"""

    is_connected: bool = Field(..., description="宿主当前是否已连入 EDC")
    machine_name: str = Field(..., description="宿主最近一次验证通过的节点名称")
    last_sync_label: str = Field(..., description="宿主显示用最近同步时间")
    meta: HostConnectivityMeta = Field(..., description="宿主连接摘要元信息")


class HostConnectivityStatusUpdateRequest(BaseModel):
    """宿主连接状态更新请求"""

    source_revision: int = Field(..., ge=1, description="调用方认知的当前 source_revision")
    is_connected: bool = Field(..., description="宿主当前是否已连入 EDC")
    machine_name: str = Field(..., description="宿主最近一次验证通过的节点名称")
    last_sync_label: str = Field(..., description="宿主显示用最近同步时间")
    meta: HostConnectivityMeta = Field(..., description="宿主连接摘要元信息")


class HostSourceConfig(BaseModel):
    """宿主当前生效的 EDC 连接配置。"""

    endpoint: str = Field(..., description="当前生效的 EDC URL")
    username: str = Field(..., description="当前生效的 EDC 账号")
    password: str = Field(..., description="当前生效的 EDC 密码")


class HostBootstrapResponse(BaseModel):
    """宿主页启动所需的后端真源快照。"""

    source_revision: int = Field(..., ge=1, description="当前后端 source_revision")
    config: HostSourceConfig = Field(..., description="当前生效的宿主连接配置")
    host_channels: HostChannelCollectionResponse = Field(..., description="当前已生效的宿主通道")
    host_channel_catalog: HostChannelCollectionResponse = Field(
        ...,
        description="当前已缓存的宿主通道目录",
    )
    connectivity_status: HostConnectivityStatusResponse = Field(
        ...,
        description="当前已生效的宿主连接摘要",
    )


class HostRuntimeSyncRequest(BaseModel):
    """宿主原子同步当前运行态。"""

    source_revision: int = Field(..., ge=1, description="调用方认知的当前 source_revision")
    items: list[HostChannelItem] = Field(..., description="当前已生效的宿主通道")
    catalog_items: list[HostChannelItem] = Field(..., description="当前已缓存的宿主通道目录")
    connection: HostConnectivityStatusResponse = Field(..., description="当前宿主连接摘要")


class HostRuntimeSyncResponse(BaseModel):
    """宿主原子同步响应。"""

    success: bool = Field(..., description="是否同步成功")
    message: str = Field(..., description="同步结果摘要")
    source_revision: int = Field(..., ge=1, description="同步完成后的最新 source_revision")
    host_channels: HostChannelCollectionResponse = Field(..., description="当前已生效的宿主通道")
    host_channel_catalog: HostChannelCollectionResponse = Field(
        ...,
        description="当前已缓存的宿主通道目录",
    )
    connectivity_status: HostConnectivityStatusResponse = Field(
        ...,
        description="当前已生效的宿主连接摘要",
    )


class RuntimeEDCConnectionSummary(BaseModel):
    """后端统一读取面的 EDC 连接摘要"""

    configured: bool = Field(..., description="EDC 连接配置是否完整")
    base_url: str = Field(..., description="当前 EDC 地址")
    username_present: bool = Field(..., description="是否存在账号配置")
    host_channel_total: int = Field(..., ge=0, description="宿主已同步通道总数")
    enabled_channel_count: int = Field(..., ge=0, description="宿主启用通道数")


class RuntimeActiveBaselineSummary(BaseModel):
    """统一运行态中的激活基线摘要"""

    id: str | None = Field(default=None, description="当前激活基线 ID")
    name: str | None = Field(default=None, description="当前激活基线名称")
    status: str | None = Field(default=None, description="当前激活基线状态")


class RuntimeFlagsSummary(BaseModel):
    """统一运行态中的关键布尔/模式配置"""

    showtime_enabled: bool = Field(..., description="当前请求是否处于 Showtime 模式")
    live_heat_inference_enabled: bool = Field(..., description="是否启用真实炉次推断")
    baseline_length_scope_mode: str = Field(..., description="基线等长校验范围")


class RuntimePipelineStatus(BaseModel):
    """业务链路就绪状态"""

    code: str = Field(..., description="链路状态码")
    ready: bool = Field(..., description="链路是否就绪")


class RuntimePipelinesSummary(BaseModel):
    """各业务页面应消费的统一链路状态"""

    dashboard: RuntimePipelineStatus = Field(..., description="Dashboard 实时链路")
    heats: RuntimePipelineStatus = Field(..., description="炉次浏览链路")
    inbox: RuntimePipelineStatus = Field(..., description="偏差收件箱链路")
    tasks: RuntimePipelineStatus = Field(..., description="纠偏任务链路")
    reports: RuntimePipelineStatus = Field(..., description="日报与审计链路")
    baselines: RuntimePipelineStatus = Field(..., description="黄金基线链路")
    settings: RuntimePipelineStatus = Field(..., description="系统设置链路")


class RuntimeChannelRolesSummary(BaseModel):
    """运行态中的业务通道角色摘要"""

    configured_count: int = Field(..., ge=0, description="已配置角色数")
    missing_required_role_keys: list[str] = Field(
        default_factory=list,
        description="缺失的必需角色键",
    )
    items: list[ChannelRoleBindingItem] = Field(default_factory=list, description="角色绑定详情")


class RuntimeStatusResponse(BaseModel):
    """统一运行态读取面响应"""

    overall_code: str = Field(..., description="整体系统状态码")
    host: HostConnectivityStatusResponse = Field(..., description="宿主连接状态")
    edc: RuntimeEDCConnectionSummary = Field(..., description="EDC 连接摘要")
    active_baseline: RuntimeActiveBaselineSummary = Field(..., description="当前激活基线摘要")
    runtime: RuntimeFlagsSummary = Field(..., description="运行模式与关键设置")
    channel_roles: RuntimeChannelRolesSummary = Field(..., description="业务通道角色摘要")
    pipelines: RuntimePipelinesSummary = Field(..., description="关键业务链路就绪状态")


class SettingsUpdateRequest(BaseModel):
    """批量更新设置请求"""

    settings: dict[str, str] = Field(..., description="键值对形式的设置")


class ToleranceSettingRequest(BaseModel):
    """容许误差设置请求"""

    tolerance_percent: float = Field(..., ge=0, le=100, description="容许误差百分比")


class EDCConnectionRequest(BaseModel):
    """EDC 连接配置请求"""

    source_revision: int = Field(..., ge=1, description="调用方认知的当前 source_revision")
    base_url: str = Field(..., description="EDC API 基础URL")
    username: str | None = Field(default=None, description="账号名称")
    password: str | None = Field(default=None, description="账号密码")
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
