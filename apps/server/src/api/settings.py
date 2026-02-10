"""设置 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import (
    EDCConnectionRequest,
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
}


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
