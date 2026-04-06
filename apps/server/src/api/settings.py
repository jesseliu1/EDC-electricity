"""设置 API 路由。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from ..channel_roles import (
    channel_score,
    default_channel_role_bindings,
    describe_channel_role_bindings,
    normalize_channel_role_bindings,
    reconcile_channel_role_bindings,
    resolve_channel_role,
)
from ..config import DEFAULT_EDC_BASE_URL, settings as app_settings
from ..request_mode import is_showtime_mode
from ..runtime_state import persist_runtime_state
from ..schemas import (
    BaselineLengthScopeSettingRequest,
    ChannelRoleBindingCollectionResponse,
    ChannelRoleBindingUpdateRequest,
    CuttingSettingRequest,
    EDCConnectionRequest,
    HostBootstrapResponse,
    HostChannelCollectionResponse,
    HostChannelCollectionUpdateRequest,
    HostChannelItem,
    HostConnectivityStatusResponse,
    HostConnectivityStatusUpdateRequest,
    HostRuntimeSyncRequest,
    HostRuntimeSyncResponse,
    HostSourceConfig,
    MessageResponse,
    ReportSettingRequest,
    RuntimeStatusResponse,
    SettingItem,
    SettingsResponse,
    SettingsUpdateRequest,
    SourceSwitchRequest,
    SourceSwitchResponse,
    ToleranceSettingRequest,
)
from ..services import EDCClient, EDCClientError
from ..services.heat_cutting_service import HeatCuttingConfig, normalize_cutting_mode
from ..services.source_switch_service import (
    SourceConnectionPayload,
    apply_source_connection_change,
)
from ..time_utils import resolve_plant_timezone_name, utc_now

router = APIRouter(prefix="/settings", tags=["Settings"])
_HOST_SYNC_HEADER = "x-asns-host-sync"

_SETTINGS_STORE: dict[str, dict[str, str | None]] = {
    "default_tolerance_percent": {"value": "15.0", "description": "默认容许误差百分比"},
    "edc_base_url": {"value": app_settings.edc_base_url, "description": "EDC API 基础URL"},
    "edc_username": {"value": app_settings.edc_username or "", "description": "EDC 登录账号"},
    "edc_password": {"value": app_settings.edc_password or "", "description": "EDC 登录密码"},
    "edc_api_key": {"value": app_settings.edc_api_key or "", "description": "EDC API 密钥"},
    "report_generation_hour": {"value": "2", "description": "日报生成时间（小时）"},
    "active_baseline_id": {"value": "baseline-001", "description": "当前激活的基线ID"},
    "time_tolerance_percent": {"value": "10.0", "description": "炉次切割时间偏移容忍率(%)"},
    "major_issue_duration_minutes": {"value": "8", "description": "持续不一致判定重大事故分钟数"},
    "plant_timezone": {"value": "Asia/Shanghai", "description": "工厂业务时区"},
    "work_start_time": {"value": "08:00", "description": "上班时间"},
    "work_end_time": {"value": "18:00", "description": "下班时间"},
    "break_periods": {"value": "12:00-13:00", "description": "休息时间段，逗号分隔"},
    "cutting_mode": {"value": "signal_inference", "description": "炉次切割模式"},
    "fixed_interval_minutes": {"value": "", "description": "固定间隔硬切割时长（分钟）"},
    "live_heat_inference_enabled": {
        "value": "true",
        "description": "是否启用基于真实功率曲线推断炉次台账",
    },
    "baseline_length_scope_mode": {
        "value": "definition",
        "description": "基线等长校验范围: definition/system/production_line",
    },
}

_HOST_CHANNEL_FALLBACKS: list[dict[str, str]] = []

_HOST_CHANNEL_STORE: list[dict[str, str]] = [item.copy() for item in _HOST_CHANNEL_FALLBACKS]
_HOST_CHANNEL_CATALOG_CACHE: list[dict[str, str]] = [item.copy() for item in _HOST_CHANNEL_FALLBACKS]
_CHANNEL_ROLE_BINDING_STORE: dict[str, str | None] = default_channel_role_bindings()
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
_HOST_SOURCE_REVISION = 1


def get_plant_timezone() -> str:
    """返回当前工厂业务时区。"""
    raw_value = _SETTINGS_STORE.get("plant_timezone", {}).get("value")
    return resolve_plant_timezone_name(str(raw_value) if raw_value is not None else None)


def _parse_optional_int(raw_value: object) -> int | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def get_cutting_config() -> HeatCuttingConfig:
    """返回当前炉次切割配置。"""

    break_raw = str(_SETTINGS_STORE.get("break_periods", {}).get("value") or "12:00-13:00")
    break_periods = tuple(item.strip() for item in break_raw.split(",") if item.strip())
    return HeatCuttingConfig(
        cutting_mode=normalize_cutting_mode(_SETTINGS_STORE.get("cutting_mode", {}).get("value")),
        fixed_interval_minutes=_parse_optional_int(
            _SETTINGS_STORE.get("fixed_interval_minutes", {}).get("value")
        ),
        time_tolerance_percent=float(
            _SETTINGS_STORE.get("time_tolerance_percent", {}).get("value") or 10.0
        ),
        major_issue_duration_minutes=int(
            _SETTINGS_STORE.get("major_issue_duration_minutes", {}).get("value") or 8
        ),
        plant_timezone=get_plant_timezone(),
        work_start_time=str(_SETTINGS_STORE.get("work_start_time", {}).get("value") or "08:00"),
        work_end_time=str(_SETTINGS_STORE.get("work_end_time", {}).get("value") or "18:00"),
        break_periods=break_periods,
    )


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


def _contains_phase(text: str) -> bool:
    lowered = text.lower()
    return "a相" in lowered or "b相" in lowered or "c相" in lowered


def _contains_total(channel_name: str) -> bool:
    return "总" in channel_name or "總" in channel_name


def _contains_fundamental(text: str) -> bool:
    lowered = text.lower()
    return "基波" in lowered or "fundamental" in lowered


def _looks_like_pressure(channel_name: str, text: str, unit: str) -> bool:
    normalized_unit = unit.lower()
    return (
        normalized_unit == "mpa"
        or "压力" in channel_name
        or "壓力" in channel_name
        or "pressure" in text
    )


def _channel_score(channel_name: str, unit: str, device_type: str) -> int:
    return channel_score(channel_name, unit, device_type)


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
    _HOST_CHANNEL_LAST_SYNC_AT = utc_now()
    return _HOST_CHANNEL_CATALOG_CACHE


def _derive_legacy_channel_role_preferences() -> dict[str, str]:
    from .baseline_definitions import _DEFINITION_STORE
    from .baselines import _resolve_active_baseline_item

    preferred: dict[str, str] = {}
    baseline = _resolve_active_baseline_item()
    if not baseline:
        return preferred

    definition_id = str(baseline.get("definition_id") or "").strip()
    definition = _DEFINITION_STORE.get(definition_id) if definition_id else None
    metrics = list(definition.get("metrics", [])) if definition else []

    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        channel_id = str(metric.get("edc_channel_id") or "").strip()
        if not channel_id:
            continue
        name = str(metric.get("name") or "").lower()
        unit = str(metric.get("unit") or "")
        if (
            "dashboard_primary" not in preferred
            and ("功率" in name or "power" in name or unit == "kW")
        ):
            preferred["dashboard_primary"] = channel_id
            preferred["live_heat_inference"] = channel_id
            continue
        if (
            "dashboard_secondary" not in preferred
            and ("电压" in name or "電壓" in name or "voltage" in name or unit == "V")
        ):
            preferred["dashboard_secondary"] = channel_id
    return preferred


def _reconcile_channel_role_binding_store(*, fill_defaults: bool = True) -> None:
    current_bindings = dict(_CHANNEL_ROLE_BINDING_STORE)
    preferred_channel_ids = _derive_legacy_channel_role_preferences()
    reconciled = reconcile_channel_role_bindings(
        current_bindings,
        _HOST_CHANNEL_STORE,
        preferred_channel_ids=preferred_channel_ids,
        fill_defaults=fill_defaults,
    )
    _CHANNEL_ROLE_BINDING_STORE.clear()
    _CHANNEL_ROLE_BINDING_STORE.update(reconciled)


def _clear_channel_role_bindings() -> int:
    normalized = normalize_channel_role_bindings(_CHANNEL_ROLE_BINDING_STORE)
    cleared_count = sum(1 for channel_id in normalized.values() if channel_id)
    _CHANNEL_ROLE_BINDING_STORE.clear()
    _CHANNEL_ROLE_BINDING_STORE.update(default_channel_role_bindings())
    return cleared_count


def _channel_role_bindings_response() -> ChannelRoleBindingCollectionResponse:
    return ChannelRoleBindingCollectionResponse.model_validate(
        describe_channel_role_bindings(_CHANNEL_ROLE_BINDING_STORE, _HOST_CHANNEL_STORE)
    )


def _to_response() -> SettingsResponse:
    return SettingsResponse(
        items=[
            SettingItem(key=key, value=str(payload["value"]), description=payload["description"])
            for key, payload in _SETTINGS_STORE.items()
        ]
    )


def _host_channel_collection_response(
    items: list[dict[str, str]] | None = None,
) -> HostChannelCollectionResponse:
    payload = [HostChannelItem(**item) for item in (items if items is not None else _HOST_CHANNEL_STORE)]
    return HostChannelCollectionResponse(items=payload, total=len(payload))


def _host_connectivity_response() -> HostConnectivityStatusResponse:
    return HostConnectivityStatusResponse.model_validate(_HOST_CONNECTIVITY_STATUS)


def _host_source_config_response() -> HostSourceConfig:
    config = get_edc_connection_config()
    return HostSourceConfig(
        endpoint=config["base_url"],
        username=config["username"],
        password=config["password"],
    )


def _current_source_revision() -> int:
    return max(int(_HOST_SOURCE_REVISION), 1)


def _bump_source_revision() -> int:
    global _HOST_SOURCE_REVISION
    _HOST_SOURCE_REVISION = _current_source_revision() + 1
    return _HOST_SOURCE_REVISION


def _assert_source_revision(expected_revision: int) -> None:
    current_revision = _current_source_revision()
    if expected_revision != current_revision:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "当前来源配置已在其它入口变更，请刷新后重试",
                "current_source_revision": current_revision,
            },
        )


def _host_bootstrap_response() -> HostBootstrapResponse:
    return HostBootstrapResponse(
        source_revision=_current_source_revision(),
        config=_host_source_config_response(),
        host_channels=_host_channel_collection_response(),
        host_channel_catalog=_host_channel_collection_response(_HOST_CHANNEL_CATALOG_CACHE),
        connectivity_status=_host_connectivity_response(),
    )


def _has_app_level_edc_connection_override() -> bool:
    return (
        app_settings.edc_base_url.strip() != DEFAULT_EDC_BASE_URL
        or bool((app_settings.edc_username or "").strip())
        or bool((app_settings.edc_password or "").strip())
        or bool((app_settings.edc_api_key or "").strip())
    )


def apply_app_edc_connection_override() -> bool:
    """启动恢复时让显式环境配置覆盖旧 runtime 连接信息。"""
    if not _has_app_level_edc_connection_override():
        return False

    previous_payload = _build_source_connection_payload(
        base_url=str(_SETTINGS_STORE.get("edc_base_url", {}).get("value") or ""),
        username=str(_SETTINGS_STORE.get("edc_username", {}).get("value") or ""),
        password=str(_SETTINGS_STORE.get("edc_password", {}).get("value") or ""),
        api_key=str(_SETTINGS_STORE.get("edc_api_key", {}).get("value") or ""),
    )
    next_payload = _build_source_connection_payload(
        base_url=app_settings.edc_base_url,
        username=app_settings.edc_username or "",
        password=app_settings.edc_password or "",
        api_key=app_settings.edc_api_key or "",
    )
    result = apply_source_connection_change(previous_payload, next_payload)
    if not result.connection_material_changed:
        return False
    return True


def _build_runtime_status_response() -> RuntimeStatusResponse:
    """构建业务页统一消费的运行态摘要。"""
    from .heats import _resolve_live_heat_inference_context
    from .baselines import _resolve_active_baseline_item

    _reconcile_channel_role_binding_store()
    host_response = _host_connectivity_response()
    host_connected = host_response.is_connected
    edc_config = get_edc_connection_config()
    edc_configured = bool(
        edc_config["base_url"] and edc_config["username"] and edc_config["password"]
    )
    enabled_channel_count = host_response.meta.enabled_channel_count
    host_channel_total = len(_HOST_CHANNEL_STORE)
    channel_role_summary = describe_channel_role_bindings(
        _CHANNEL_ROLE_BINDING_STORE,
        _HOST_CHANNEL_STORE,
    )
    dashboard_primary_channel = resolve_channel_role(
        "dashboard_primary",
        _CHANNEL_ROLE_BINDING_STORE,
        _HOST_CHANNEL_STORE,
    )
    live_heat_inference_ready = _resolve_live_heat_inference_context() is not None
    dashboard_ready = dashboard_primary_channel is not None
    business_channel_ready = host_channel_total > 0 and (
        dashboard_ready or live_heat_inference_ready
    )
    live_heat_inference_enabled = (
        str(_SETTINGS_STORE.get("live_heat_inference_enabled", {}).get("value") or "true")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )
    showtime_enabled = is_showtime_mode()
    active_baseline_item = _resolve_active_baseline_item()
    cutting_config = get_cutting_config()

    def _pipeline_code(section: str) -> str:
        if showtime_enabled:
            return "showtime"
        if not host_connected:
            return "host_disconnected"
        if not edc_configured:
            return "edc_unconfigured"
        if section == "settings":
            return "ready"
        if section == "dashboard" and not dashboard_ready:
            return "no_enabled_channels"
        if section == "heats" and not live_heat_inference_ready:
            return "no_enabled_channels"
        if section == "inbox" and not live_heat_inference_ready:
            return "no_enabled_channels"
        if not business_channel_ready:
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
    elif not business_channel_ready:
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
                "plant_timezone": get_plant_timezone(),
                "cutting_mode": cutting_config.cutting_mode,
                "fixed_interval_minutes": cutting_config.fixed_interval_minutes,
            },
            "channel_roles": channel_role_summary,
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


def _build_disconnected_host_connectivity_status(source: str) -> dict[str, object]:
    return {
        "is_connected": False,
        "machine_name": "--",
        "last_sync_label": "--",
        "meta": {
            "source": source or "--",
            "sensor_count": 0,
            "channel_count": 0,
            "enabled_channel_count": 0,
        },
    }


def _invalidate_compare_runtime_caches() -> None:
    from .heats import invalidate_compare_runtime_caches

    invalidate_compare_runtime_caches(include_shared=True)


def _invalidate_heat_cutting_runtime_caches() -> None:
    from .heats import invalidate_live_heat_runtime_cache

    _invalidate_compare_runtime_caches()
    invalidate_live_heat_runtime_cache()


def _schedule_heat_runtime_refresh() -> None:
    from .heats import schedule_heat_runtime_refresh

    schedule_heat_runtime_refresh(reason="settings_changed")


def _build_source_connection_payload(
    *,
    base_url: str,
    username: str,
    password: str,
    api_key: str,
) -> SourceConnectionPayload:
    return SourceConnectionPayload(
        base_url=base_url.strip(),
        username=username.strip(),
        password=password.strip(),
        api_key=api_key.strip(),
    )


def _resolve_source_switch_payload(
    data: SourceSwitchRequest | EDCConnectionRequest,
) -> SourceConnectionPayload:
    previous_config = get_edc_connection_config()
    previous_api_key = str(_SETTINGS_STORE.get("edc_api_key", {}).get("value") or "").strip()
    return _build_source_connection_payload(
        base_url=data.base_url,
        username=data.username if data.username is not None else previous_config["username"],
        password=data.password if data.password is not None else previous_config["password"],
        api_key=data.api_key or previous_api_key,
    )


async def _apply_source_switch_request(
    data: SourceSwitchRequest | EDCConnectionRequest,
) -> SourceSwitchResponse:
    _assert_source_revision(data.source_revision)
    previous_config = get_edc_connection_config()
    previous_payload = _build_source_connection_payload(
        base_url=previous_config["base_url"],
        username=previous_config["username"],
        password=previous_config["password"],
        api_key=str(_SETTINGS_STORE.get("edc_api_key", {}).get("value") or ""),
    )
    next_payload = _resolve_source_switch_payload(data)
    result = apply_source_connection_change(previous_payload, next_payload)

    sections_to_persist = {"settings_store"}
    next_source_revision = _current_source_revision()
    if result.connection_material_changed:
        next_source_revision = _bump_source_revision()
        sections_to_persist.update(
            {
                "source_revision",
                "host_channel_catalog",
                "host_channel_last_sync_at",
                "host_connectivity_status",
            }
        )
    if result.source_identity_changed:
        sections_to_persist.update(
            {
                "host_channels",
                "channel_role_bindings",
                "baseline_definitions",
            }
        )
    await persist_runtime_state(*sections_to_persist)

    if result.source_identity_changed:
        message = "EDC 来源已切换，旧来源相关配置已统一清空"
    elif result.connection_material_changed:
        message = "EDC 连接材料已更新，连线状态已重置，等待重新验证"
    else:
        message = "EDC 连接配置未发生变化"

    return SourceSwitchResponse(
        success=True,
        message=message,
        source_revision=next_source_revision,
        source_identity_changed=result.source_identity_changed,
        connection_material_changed=result.connection_material_changed,
        cleared_host_channel_count=result.cleared_host_channel_count,
        cleared_host_channel_catalog_count=result.cleared_host_channel_catalog_count,
        cleared_channel_role_binding_count=result.cleared_channel_role_binding_count,
        cleared_definition_binding_count=result.cleared_definition_binding_count,
        cleared_active_baseline_id=result.cleared_active_baseline_id,
        next_source=result.next_source,
    )


async def _sync_host_runtime_state(
    *,
    source_revision: int,
    host_channels: list[HostChannelItem],
    host_channel_catalog: list[HostChannelItem],
    connection: HostConnectivityStatusResponse,
) -> HostRuntimeSyncResponse:
    global _HOST_CHANNEL_LAST_SYNC_AT

    _assert_source_revision(source_revision)

    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend([item.model_dump() for item in host_channels])
    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend([item.model_dump() for item in host_channel_catalog])
    _HOST_CHANNEL_LAST_SYNC_AT = utc_now() if host_channel_catalog else None
    _HOST_CONNECTIVITY_STATUS.clear()
    _HOST_CONNECTIVITY_STATUS.update(connection.model_dump())
    _reconcile_channel_role_binding_store()
    _invalidate_compare_runtime_caches()

    next_source_revision = _bump_source_revision()
    await persist_runtime_state(
        "source_revision",
        "host_channels",
        "host_channel_catalog",
        "host_channel_last_sync_at",
        "channel_role_bindings",
        "host_connectivity_status",
    )
    return HostRuntimeSyncResponse(
        success=True,
        message="宿主运行态已同步",
        source_revision=next_source_revision,
        host_channels=_host_channel_collection_response(),
        host_channel_catalog=_host_channel_collection_response(_HOST_CHANNEL_CATALOG_CACHE),
        connectivity_status=_host_connectivity_response(),
    )


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """获取所有系统设置。"""
    return _to_response()


@router.get("/host-bootstrap", response_model=HostBootstrapResponse)
async def get_host_bootstrap() -> HostBootstrapResponse:
    """获取宿主页启动所需的后端当前真源快照。"""
    return _host_bootstrap_response()


@router.get("/host-channels", response_model=HostChannelCollectionResponse)
async def get_host_channels() -> HostChannelCollectionResponse:
    """获取宿主层已添加通道清单。"""
    return _host_channel_collection_response()


@router.get("/channel-role-bindings", response_model=ChannelRoleBindingCollectionResponse)
async def get_channel_role_bindings() -> ChannelRoleBindingCollectionResponse:
    """获取业务通道角色绑定。"""
    _reconcile_channel_role_binding_store()
    return _channel_role_bindings_response()


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
    _assert_source_revision(data.source_revision)
    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend([item.model_dump() for item in data.items])
    _reconcile_channel_role_binding_store()
    _invalidate_compare_runtime_caches()
    _bump_source_revision()
    await persist_runtime_state("source_revision", "host_channels", "channel_role_bindings")
    return MessageResponse(message=f"宿主通道清单已保存，共 {len(data.items)} 条", success=True)


@router.put("/channel-role-bindings", response_model=ChannelRoleBindingCollectionResponse)
async def update_channel_role_bindings(
    data: ChannelRoleBindingUpdateRequest,
) -> ChannelRoleBindingCollectionResponse:
    """更新业务通道角色绑定。"""
    merged_bindings = dict(_CHANNEL_ROLE_BINDING_STORE)
    for role_key, channel_id in data.bindings.items():
        if role_key not in merged_bindings:
            continue
        merged_bindings[role_key] = channel_id

    reconciled = reconcile_channel_role_bindings(
        merged_bindings,
        _HOST_CHANNEL_STORE,
        fill_defaults=False,
    )
    _CHANNEL_ROLE_BINDING_STORE.clear()
    _CHANNEL_ROLE_BINDING_STORE.update(reconciled)
    await persist_runtime_state("channel_role_bindings")
    return _channel_role_bindings_response()


@router.put("/host-connectivity-status", response_model=HostConnectivityStatusResponse)
async def update_host_connectivity_status(
    data: HostConnectivityStatusUpdateRequest,
    request: Request,
) -> HostConnectivityStatusResponse:
    """保存宿主同步到后端的连接状态摘要。"""
    _assert_host_sync_request(request)
    _assert_source_revision(data.source_revision)
    _HOST_CONNECTIVITY_STATUS.clear()
    _HOST_CONNECTIVITY_STATUS.update(data.model_dump(exclude={"source_revision"}))
    _bump_source_revision()
    await persist_runtime_state("source_revision", "host_connectivity_status")
    return _host_connectivity_response()


@router.put("/host-runtime-sync", response_model=HostRuntimeSyncResponse)
async def update_host_runtime_sync(
    data: HostRuntimeSyncRequest,
    request: Request,
) -> HostRuntimeSyncResponse:
    """原子同步宿主当前真源态，避免多接口并发写入分叉。"""
    _assert_host_sync_request(request)
    return await _sync_host_runtime_state(
        source_revision=data.source_revision,
        host_channels=data.items,
        host_channel_catalog=data.catalog_items,
        connection=data.connection,
    )


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
    _assert_host_sync_request(request)
    result = await _apply_source_switch_request(data)
    return MessageResponse(message=result.message, success=result.success)


@router.post("/source-switch", response_model=SourceSwitchResponse)
async def source_switch(data: SourceSwitchRequest, request: Request) -> SourceSwitchResponse:
    """统一换源入口：更新来源并按边界重置来源相关配置。"""
    _assert_host_sync_request(request)
    return await _apply_source_switch_request(data)


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
    _SETTINGS_STORE["cutting_mode"]["value"] = data.cutting_mode
    _SETTINGS_STORE["fixed_interval_minutes"]["value"] = (
        str(data.fixed_interval_minutes) if data.fixed_interval_minutes is not None else ""
    )
    _SETTINGS_STORE["time_tolerance_percent"]["value"] = str(data.time_tolerance_percent)
    _SETTINGS_STORE["major_issue_duration_minutes"]["value"] = str(
        data.major_issue_duration_minutes
    )
    _SETTINGS_STORE["plant_timezone"]["value"] = resolve_plant_timezone_name(data.plant_timezone)
    _SETTINGS_STORE["work_start_time"]["value"] = data.work_start_time
    _SETTINGS_STORE["work_end_time"]["value"] = data.work_end_time
    _SETTINGS_STORE["break_periods"]["value"] = ",".join(data.break_periods)
    await persist_runtime_state("settings_store")
    _invalidate_heat_cutting_runtime_caches()
    _schedule_heat_runtime_refresh()
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
