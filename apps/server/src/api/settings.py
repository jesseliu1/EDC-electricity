"""设置 API 路由。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from ..config import settings as app_settings
from ..request_mode import is_showtime_mode
from ..runtime_state import persist_runtime_state
from ..schemas import (
    BaselineLengthScopeSettingRequest,
    CuttingSettingRequest,
    EDCConnectionRequest,
    HostChannelCollectionResponse,
    HostChannelCollectionUpdateRequest,
    HostChannelItem,
    HostConnectivityStatusResponse,
    HostConnectivityStatusUpdateRequest,
    MessageResponse,
    ReportSettingRequest,
    RuntimeStatusResponse,
    SettingItem,
    SettingsResponse,
    SettingsUpdateRequest,
    ToleranceSettingRequest,
)
from ..services import EDCClient, EDCClientError

router = APIRouter(prefix="/settings", tags=["Settings"])
_HOST_SYNC_HEADER = "x-asns-host-sync"

_SETTINGS_STORE: dict[str, dict[str, str | None]] = {
    "default_tolerance_percent": {"value": "15.0", "description": "默认容许误差百分比"},
    "edc_base_url": {"value": "http://60.251.229.32", "description": "EDC API 基础URL"},
    "edc_username": {"value": "volapu", "description": "EDC 登录账号"},
    "edc_password": {"value": "admin", "description": "EDC 登录密码"},
    "edc_api_key": {"value": "", "description": "EDC API 密钥"},
    "report_generation_hour": {"value": "2", "description": "日报生成时间（小时）"},
    "active_baseline_id": {"value": "baseline-001", "description": "当前激活的基线ID"},
    "time_tolerance_percent": {"value": "10.0", "description": "炉次切割时间偏移容忍率(%)"},
    "major_issue_duration_minutes": {"value": "8", "description": "持续不一致判定重大事故分钟数"},
    "work_start_time": {"value": "08:00", "description": "上班时间"},
    "work_end_time": {"value": "18:00", "description": "下班时间"},
    "break_periods": {"value": "12:00-13:00", "description": "休息时间段，逗号分隔"},
    "live_heat_inference_enabled": {
        "value": "true",
        "description": "是否启用基于真实功率曲线推断炉次台账",
    },
    "baseline_length_scope_mode": {
        "value": "definition",
        "description": "基线等长校验范围: definition/system/production_line",
    },
}

_HOST_CHANNEL_FALLBACKS: list[dict[str, str]] = [
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

_HOST_CHANNEL_STORE: list[dict[str, str]] = [item.copy() for item in _HOST_CHANNEL_FALLBACKS]
_HOST_CHANNEL_CATALOG_CACHE: list[dict[str, str]] = [item.copy() for item in _HOST_CHANNEL_FALLBACKS]
_HOST_CHANNEL_LAST_SYNC_AT: datetime | None = None
_HOST_CONNECTIVITY_STATUS: dict[str, object] = {
    "is_connected": False,
    "machine_name": "--",
    "last_sync_label": "--",
    "meta": {
        "source": "--",
        "sensor_count": 0,
        "channel_count": 0,
        "enabled_channel_count": 0,
    },
}


def _stringify(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _pick_first(payload: dict[str, object], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = _stringify(value)
        if text:
            return text
    return default


def _channel_score(channel_name: str, unit: str, device_type: str) -> int:
    text = f"{channel_name} {unit} {device_type}".lower()
    score = 0
    if "有功" in channel_name or "power" in text or unit.lower() == "kw":
        score += 120
    if "电压" in channel_name or unit.lower() == "v":
        score += 110
    if "温" in channel_name or "temp" in text or unit in {"℃", "°c"}:
        score += 100
    if "压" in channel_name or unit.lower() == "mpa":
        score += 90
    if "总" in channel_name:
        score += 15
    if "a相" in channel_name or "b相" in channel_name or "c相" in channel_name:
        score += 8
    return score


def _normalize_host_channels(sensor_list: list[dict[str, object]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for sensor in sensor_list:
        suid = _pick_first(sensor, "uid", "suid")
        if not suid:
            continue

        area = _pick_first(sensor, "name", "areaName", "tagName", default="未命名区域")
        device_type = _pick_first(
            sensor,
            "typeName",
            "devTypeName",
            "deviceType",
            "sensorType",
            default="未知设备",
        )
        device_name = f"{area} · {device_type}"

        channel_list = sensor.get("channelList")
        if not isinstance(channel_list, list):
            continue

        for channel in channel_list:
            if not isinstance(channel, dict):
                continue

            status = channel.get("status")
            if status is not None and str(status) != "1":
                continue

            cuid = _pick_first(channel, "cuid", "uid")
            if not cuid:
                continue

            channel_name = _pick_first(channel, "chnName", "name", "title", default=f"通道 {cuid}")
            unit = _pick_first(channel, "chnDim", "unit", default="--")
            last_value = _pick_first(channel, "lastData", "lastValue", default="--")

            items.append(
                {
                    "id": f"{suid}-{cuid}",
                    "device_name": device_name,
                    "device_type": device_type,
                    "area": area,
                    "suid": suid,
                    "cuid": cuid,
                    "channel_name": channel_name,
                    "unit": unit,
                    "last_value": last_value,
                    "status": "online",
                }
            )

    items.sort(
        key=lambda item: (
            -_channel_score(item["channel_name"], item["unit"], item["device_type"]),
            item["device_name"],
            item["channel_name"],
        )
    )
    return items


async def _sync_host_channel_catalog_from_edc(force: bool = False) -> list[dict[str, str]]:
    """按需从真实 EDC 同步全量通道目录缓存。"""
    global _HOST_CHANNEL_LAST_SYNC_AT

    if _HOST_CHANNEL_CATALOG_CACHE and _HOST_CHANNEL_LAST_SYNC_AT is not None and not force:
        return _HOST_CHANNEL_CATALOG_CACHE

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return _HOST_CHANNEL_CATALOG_CACHE

    try:
        async with EDCClient(**config) as client:
            sensor_list = await client.get_all_sensor_list()
    except EDCClientError:
        return _HOST_CHANNEL_CATALOG_CACHE

    normalized = _normalize_host_channels(sensor_list)
    if not normalized:
        return _HOST_CHANNEL_CATALOG_CACHE

    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend(normalized)
    _HOST_CHANNEL_LAST_SYNC_AT = datetime.now()
    return _HOST_CHANNEL_CATALOG_CACHE


def _to_response() -> SettingsResponse:
    return SettingsResponse(
        items=[
            SettingItem(key=key, value=str(payload["value"]), description=payload["description"])
            for key, payload in _SETTINGS_STORE.items()
        ]
    )


def _host_connectivity_response() -> HostConnectivityStatusResponse:
    return HostConnectivityStatusResponse.model_validate(_HOST_CONNECTIVITY_STATUS)


def _build_runtime_status_response() -> RuntimeStatusResponse:
    """构建业务页统一消费的运行态摘要。"""
    from .baselines import _BASELINE_STORE

    host_response = _host_connectivity_response()
    host_connected = host_response.is_connected
    edc_config = get_edc_connection_config()
    edc_configured = bool(
        edc_config["base_url"] and edc_config["username"] and edc_config["password"]
    )
    enabled_channel_count = host_response.meta.enabled_channel_count
    host_channel_total = len(_HOST_CHANNEL_STORE)
    live_heat_inference_enabled = (
        str(_SETTINGS_STORE.get("live_heat_inference_enabled", {}).get("value") or "true")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )
    showtime_enabled = is_showtime_mode()
    active_baseline_id = str(_SETTINGS_STORE.get("active_baseline_id", {}).get("value") or "").strip()
    active_baseline_item = _BASELINE_STORE.get(active_baseline_id) if active_baseline_id else None

    def _pipeline_code(section: str) -> str:
        if showtime_enabled:
            return "showtime"
        if not host_connected:
            return "host_disconnected"
        if not edc_configured:
            return "edc_unconfigured"
        if enabled_channel_count <= 0:
            return "no_enabled_channels"
        if section == "heats" and not live_heat_inference_enabled:
            return "heat_inference_disabled"
        return "ready"

    overall_code = "ready"
    if showtime_enabled:
        overall_code = "showtime"
    elif not host_connected:
        overall_code = "host_disconnected"
    elif not edc_configured:
        overall_code = "edc_unconfigured"
    elif enabled_channel_count <= 0:
        overall_code = "no_enabled_channels"

    return RuntimeStatusResponse.model_validate(
        {
            "overall_code": overall_code,
            "host": host_response.model_dump(),
            "edc": {
                "configured": edc_configured,
                "base_url": edc_config["base_url"],
                "username_present": bool(edc_config["username"]),
                "host_channel_total": host_channel_total,
                "enabled_channel_count": enabled_channel_count,
            },
            "active_baseline": {
                "id": active_baseline_item["id"] if active_baseline_item else None,
                "name": active_baseline_item["name"] if active_baseline_item else None,
                "status": active_baseline_item["status"] if active_baseline_item else None,
            },
            "runtime": {
                "showtime_enabled": showtime_enabled,
                "live_heat_inference_enabled": live_heat_inference_enabled,
                "baseline_length_scope_mode": str(
                    _SETTINGS_STORE.get("baseline_length_scope_mode", {}).get("value") or "definition"
                ),
            },
            "pipelines": {
                "dashboard": {
                    "code": _pipeline_code("dashboard"),
                    "ready": _pipeline_code("dashboard") == "ready",
                },
                "heats": {
                    "code": _pipeline_code("heats"),
                    "ready": _pipeline_code("heats") == "ready",
                },
                "inbox": {
                    "code": _pipeline_code("heats"),
                    "ready": _pipeline_code("heats") == "ready",
                },
                "tasks": {
                    "code": _pipeline_code("dashboard"),
                    "ready": _pipeline_code("dashboard") == "ready",
                },
                "reports": {
                    "code": _pipeline_code("dashboard"),
                    "ready": _pipeline_code("dashboard") == "ready",
                },
                "baselines": {
                    "code": _pipeline_code("baselines"),
                    "ready": _pipeline_code("baselines") == "ready",
                },
                "settings": {
                    "code": _pipeline_code("settings"),
                    "ready": _pipeline_code("settings") == "ready",
                },
            },
        }
    )


def _assert_host_sync_request(request: Request) -> None:
    if request.headers.get(_HOST_SYNC_HEADER, "").lower() != "true":
        raise HTTPException(status_code=403, detail="该写接口仅允许宿主同步调用")


def get_edc_connection_config() -> dict[str, str]:
    """读取当前 EDC 连接配置。"""
    base_url = str(_SETTINGS_STORE.get("edc_base_url", {}).get("value") or app_settings.edc_base_url)
    username = str(
        _SETTINGS_STORE.get("edc_username", {}).get("value") or app_settings.edc_username or ""
    )
    password = str(
        _SETTINGS_STORE.get("edc_password", {}).get("value") or app_settings.edc_password or ""
    )
    return {
        "base_url": base_url.strip(),
        "username": username.strip(),
        "password": password.strip(),
    }


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """获取所有系统设置。"""
    return _to_response()


@router.get("/host-channels", response_model=HostChannelCollectionResponse)
async def get_host_channels() -> HostChannelCollectionResponse:
    """获取宿主层已添加通道清单。"""
    items = [HostChannelItem(**payload) for payload in _HOST_CHANNEL_STORE]
    return HostChannelCollectionResponse(items=items, total=len(items))


@router.get("/host-connectivity-status", response_model=HostConnectivityStatusResponse)
async def get_host_connectivity_status() -> HostConnectivityStatusResponse:
    """获取宿主同步到后端的连接状态摘要。"""
    return _host_connectivity_response()


@router.get("/runtime-status", response_model=RuntimeStatusResponse)
async def get_runtime_status() -> RuntimeStatusResponse:
    """获取业务页统一消费的运行态摘要。"""
    return _build_runtime_status_response()


@router.put("/host-channels", response_model=MessageResponse)
async def update_host_channels(
    data: HostChannelCollectionUpdateRequest,
    request: Request,
) -> MessageResponse:
    """保存宿主层已添加通道清单。"""
    _assert_host_sync_request(request)
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend([item.model_dump() for item in data.items])
    await persist_runtime_state("host_channels")
    return MessageResponse(message=f"宿主通道清单已保存，共 {len(data.items)} 条", success=True)


@router.put("/host-connectivity-status", response_model=HostConnectivityStatusResponse)
async def update_host_connectivity_status(
    data: HostConnectivityStatusUpdateRequest,
    request: Request,
) -> HostConnectivityStatusResponse:
    """保存宿主同步到后端的连接状态摘要。"""
    _assert_host_sync_request(request)
    _HOST_CONNECTIVITY_STATUS.clear()
    _HOST_CONNECTIVITY_STATUS.update(data.model_dump())
    await persist_runtime_state("host_connectivity_status")
    return _host_connectivity_response()


@router.patch("", response_model=MessageResponse)
async def update_settings(data: SettingsUpdateRequest) -> MessageResponse:
    """批量更新系统设置。"""
    for key, value in data.settings.items():
        if key in _SETTINGS_STORE:
            _SETTINGS_STORE[key]["value"] = value
        else:
            _SETTINGS_STORE[key] = {"value": value, "description": None}
    await persist_runtime_state("settings_store")
    return MessageResponse(message=f"已更新 {len(data.settings)} 项设置", success=True)


@router.put("/tolerance", response_model=MessageResponse)
async def update_tolerance(data: ToleranceSettingRequest) -> MessageResponse:
    """更新默认容许误差设置。"""
    _SETTINGS_STORE["default_tolerance_percent"]["value"] = str(data.tolerance_percent)
    await persist_runtime_state("settings_store")
    return MessageResponse(message=f"容许误差已更新为 {data.tolerance_percent}%", success=True)


@router.put("/edc-connection", response_model=MessageResponse)
async def update_edc_connection(data: EDCConnectionRequest, request: Request) -> MessageResponse:
    """更新 EDC 连接配置。"""
    global _HOST_CHANNEL_LAST_SYNC_AT
    _assert_host_sync_request(request)
    _SETTINGS_STORE["edc_base_url"]["value"] = data.base_url
    if data.username is not None:
        _SETTINGS_STORE["edc_username"]["value"] = data.username
    if data.password is not None:
        _SETTINGS_STORE["edc_password"]["value"] = data.password
    _SETTINGS_STORE["edc_api_key"]["value"] = data.api_key or ""
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_LAST_SYNC_AT = None
    await persist_runtime_state(
        "settings_store",
        "host_channel_catalog",
        "host_channel_last_sync_at",
    )
    return MessageResponse(message="EDC 连接配置已更新", success=True)


@router.post("/edc-connection/test", response_model=MessageResponse)
async def test_edc_connection() -> MessageResponse:
    """测试 EDC 连接。"""
    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return MessageResponse(message="EDC 连接信息不完整", success=False)

    try:
        async with EDCClient(**config) as client:
            await client.login()
    except EDCClientError as exc:
        return MessageResponse(message=str(exc), success=False)

    return MessageResponse(message="EDC 连接测试成功", success=True)


@router.put("/report", response_model=MessageResponse)
async def update_report_settings(data: ReportSettingRequest) -> MessageResponse:
    """更新报表设置。"""
    _SETTINGS_STORE["report_generation_hour"]["value"] = str(data.generation_hour)
    await persist_runtime_state("settings_store")
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
    await persist_runtime_state("settings_store")
    return MessageResponse(message="炉次切割设置已更新", success=True)


@router.put("/baseline-length-scope", response_model=MessageResponse)
async def update_baseline_length_scope(data: BaselineLengthScopeSettingRequest) -> MessageResponse:
    """更新基线等长校验范围。"""
    valid_modes = {"definition", "system", "production_line"}
    if data.scope_mode not in valid_modes:
        return MessageResponse(message="scope_mode 非法", success=False)

    _SETTINGS_STORE["baseline_length_scope_mode"]["value"] = data.scope_mode
    await persist_runtime_state("settings_store")
    return MessageResponse(message=f"基线等长校验范围已更新为 {data.scope_mode}", success=True)
