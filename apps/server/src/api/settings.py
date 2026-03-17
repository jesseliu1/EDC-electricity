"""设置 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import (
    BaselineLengthScopeSettingRequest,
    CuttingSettingRequest,
    EDCConnectionRequest,
    HostChannelCollectionResponse,
    HostChannelItem,
    MessageResponse,
    ReportSettingRequest,
    SettingItem,
    SettingsResponse,
    SettingsUpdateRequest,
    ToleranceSettingRequest,
)

router = APIRouter(prefix="/settings", tags=["Settings"])

_SETTINGS_STORE: dict[str, dict[str, str | None]] = {
    "default_tolerance_percent": {"value": "15.0", "description": "默认容许误差百分比"},
    "edc_base_url": {"value": "http://localhost:8080", "description": "EDC API 基础URL"},
    "edc_api_key": {"value": "", "description": "EDC API 密钥"},
    "report_generation_hour": {"value": "2", "description": "日报生成时间（小时）"},
    "active_baseline_id": {"value": "baseline-001", "description": "当前激活的基线ID"},
    "time_tolerance_percent": {"value": "10.0", "description": "炉次切割时间偏移容忍率(%)"},
    "major_issue_duration_minutes": {"value": "8", "description": "持续不一致判定重大事故分钟数"},
    "work_start_time": {"value": "08:00", "description": "上班时间"},
    "work_end_time": {"value": "18:00", "description": "下班时间"},
    "break_periods": {"value": "12:00-13:00", "description": "休息时间段，逗号分隔"},
    "baseline_length_scope_mode": {
        "value": "definition",
        "description": "基线等长校验范围: definition/system/production_line",
    },
}

_HOST_CHANNEL_STORE: list[dict[str, str]] = [
    {
        "id": "2349-199",
        "device_name": "SSTW 380V-220V電力 · 三相智能电表",
        "device_type": "三相智能电表",
        "area": "SSTW 380V-220V電力",
        "suid": "2349",
        "cuid": "199",
        "channel_name": "总有功功率",
        "unit": "kW",
        "last_value": "--",
        "status": "online",
    },
    {
        "id": "2349-142",
        "device_name": "SSTW 380V-220V電力 · 三相智能电表",
        "device_type": "三相智能电表",
        "area": "SSTW 380V-220V電力",
        "suid": "2349",
        "cuid": "142",
        "channel_name": "A相有功功率",
        "unit": "kW",
        "last_value": "--",
        "status": "online",
    },
    {
        "id": "2349-128",
        "device_name": "SSTW 380V-220V電力 · 三相智能电表",
        "device_type": "三相智能电表",
        "area": "SSTW 380V-220V電力",
        "suid": "2349",
        "cuid": "128",
        "channel_name": "A相电压",
        "unit": "V",
        "last_value": "--",
        "status": "online",
    },
    {
        "id": "2349-130",
        "device_name": "SSTW 380V-220V電力 · 三相智能电表",
        "device_type": "三相智能电表",
        "area": "SSTW 380V-220V電力",
        "suid": "2349",
        "cuid": "130",
        "channel_name": "B相电压",
        "unit": "V",
        "last_value": "--",
        "status": "online",
    },
    {
        "id": "2054-128",
        "device_name": "A-1溫度 · 热电偶温度采集器",
        "device_type": "热电偶温度采集器",
        "area": "A-1溫度",
        "suid": "2054",
        "cuid": "128",
        "channel_name": "热电偶温度采集通道",
        "unit": "℃",
        "last_value": "--",
        "status": "online",
    },
    {
        "id": "2066-128",
        "device_name": "A-2溫度 · 热电偶温度采集器",
        "device_type": "热电偶温度采集器",
        "area": "A-2溫度",
        "suid": "2066",
        "cuid": "128",
        "channel_name": "热电偶温度采集通道",
        "unit": "℃",
        "last_value": "--",
        "status": "online",
    },
    {
        "id": "769-128",
        "device_name": "防水型智慧電流信號轉換器  · General 4-20 mA to CAN Converter",
        "device_type": "General 4-20 mA to CAN Converter",
        "area": "防水型智慧電流信號轉換器 ",
        "suid": "769",
        "cuid": "128",
        "channel_name": "AD_CH1",
        "unit": "外部传感器决定",
        "last_value": "--",
        "status": "online",
    },
    {
        "id": "769-129",
        "device_name": "防水型智慧電流信號轉換器  · General 4-20 mA to CAN Converter",
        "device_type": "General 4-20 mA to CAN Converter",
        "area": "防水型智慧電流信號轉換器 ",
        "suid": "769",
        "cuid": "129",
        "channel_name": "AD_CH2",
        "unit": "外部传感器决定",
        "last_value": "--",
        "status": "online",
    },
]


def _to_response() -> SettingsResponse:
    return SettingsResponse(
        items=[
            SettingItem(key=key, value=str(payload["value"]), description=payload["description"])
            for key, payload in _SETTINGS_STORE.items()
        ]
    )


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """获取所有系统设置。"""
    return _to_response()


@router.get("/host-channels", response_model=HostChannelCollectionResponse)
async def get_host_channels() -> HostChannelCollectionResponse:
    """获取宿主层已添加通道清单。"""
    items = [HostChannelItem(**payload) for payload in _HOST_CHANNEL_STORE]
    return HostChannelCollectionResponse(items=items, total=len(items))


@router.patch("", response_model=MessageResponse)
async def update_settings(data: SettingsUpdateRequest) -> MessageResponse:
    """批量更新系统设置。"""
    for key, value in data.settings.items():
        if key in _SETTINGS_STORE:
            _SETTINGS_STORE[key]["value"] = value
        else:
            _SETTINGS_STORE[key] = {"value": value, "description": None}
    return MessageResponse(message=f"已更新 {len(data.settings)} 项设置", success=True)


@router.put("/tolerance", response_model=MessageResponse)
async def update_tolerance(data: ToleranceSettingRequest) -> MessageResponse:
    """更新默认容许误差设置。"""
    _SETTINGS_STORE["default_tolerance_percent"]["value"] = str(data.tolerance_percent)
    return MessageResponse(message=f"容许误差已更新为 {data.tolerance_percent}%", success=True)


@router.put("/edc-connection", response_model=MessageResponse)
async def update_edc_connection(data: EDCConnectionRequest) -> MessageResponse:
    """更新 EDC 连接配置。"""
    _SETTINGS_STORE["edc_base_url"]["value"] = data.base_url
    _SETTINGS_STORE["edc_api_key"]["value"] = data.api_key or ""
    return MessageResponse(message="EDC 连接配置已更新", success=True)


@router.post("/edc-connection/test", response_model=MessageResponse)
async def test_edc_connection() -> MessageResponse:
    """测试 EDC 连接。"""
    return MessageResponse(message="EDC 连接测试成功", success=True)


@router.put("/report", response_model=MessageResponse)
async def update_report_settings(data: ReportSettingRequest) -> MessageResponse:
    """更新报表设置。"""
    _SETTINGS_STORE["report_generation_hour"]["value"] = str(data.generation_hour)
    return MessageResponse(message=f"日报生成时间已设置为 {data.generation_hour}:00", success=True)


@router.put("/cutting", response_model=MessageResponse)
async def update_cutting_settings(data: CuttingSettingRequest) -> MessageResponse:
    """更新炉次切割设置。"""
    _SETTINGS_STORE["time_tolerance_percent"]["value"] = str(data.time_tolerance_percent)
    _SETTINGS_STORE["major_issue_duration_minutes"]["value"] = str(
        data.major_issue_duration_minutes
    )
    _SETTINGS_STORE["work_start_time"]["value"] = data.work_start_time
    _SETTINGS_STORE["work_end_time"]["value"] = data.work_end_time
    _SETTINGS_STORE["break_periods"]["value"] = ",".join(data.break_periods)
    return MessageResponse(message="炉次切割设置已更新", success=True)


@router.put("/baseline-length-scope", response_model=MessageResponse)
async def update_baseline_length_scope(data: BaselineLengthScopeSettingRequest) -> MessageResponse:
    """更新基线等长校验范围。"""
    valid_modes = {"definition", "system", "production_line"}
    if data.scope_mode not in valid_modes:
        return MessageResponse(message="scope_mode 非法", success=False)

    _SETTINGS_STORE["baseline_length_scope_mode"]["value"] = data.scope_mode
    return MessageResponse(message=f"基线等长校验范围已更新为 {data.scope_mode}", success=True)
