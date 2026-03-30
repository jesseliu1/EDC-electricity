"""EDC 换源与连接配置收口服务。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceConnectionPayload:
    """归一化后的 EDC 连接配置。"""

    base_url: str
    username: str
    password: str
    api_key: str


@dataclass(frozen=True)
class SourceSwitchMutationResult:
    """换源/改连接统一收口结果。"""

    source_identity_changed: bool
    connection_material_changed: bool
    cleared_host_channel_count: int
    cleared_host_channel_catalog_count: int
    cleared_definition_binding_count: int
    cleared_active_baseline_id: str
    next_source: str


def normalize_source_identity(base_url: str, username: str) -> tuple[str, str]:
    """定义“源身份”：地址 + 账号，不包含密码。"""

    return (base_url.strip().rstrip("/"), username.strip())


def normalize_connection_material(payload: SourceConnectionPayload) -> tuple[str, str, str, str]:
    """定义“连接材料”：地址 + 账号 + 密码 + API Key。"""

    return (
        payload.base_url.strip().rstrip("/"),
        payload.username.strip(),
        payload.password.strip(),
        payload.api_key.strip(),
    )


def apply_source_connection_change(
    previous_payload: SourceConnectionPayload,
    next_payload: SourceConnectionPayload,
) -> SourceSwitchMutationResult:
    """统一应用 EDC 连接变更，并按边界重置来源相关运行态。"""

    from ..api import baseline_definitions as baseline_definitions_api
    from ..api import settings as settings_api

    previous_source = normalize_source_identity(
        previous_payload.base_url,
        previous_payload.username,
    )
    next_source = normalize_source_identity(
        next_payload.base_url,
        next_payload.username,
    )
    previous_connection = normalize_connection_material(previous_payload)
    next_connection = normalize_connection_material(next_payload)

    source_identity_changed = previous_source != next_source
    connection_material_changed = previous_connection != next_connection

    settings_api._SETTINGS_STORE["edc_base_url"]["value"] = next_payload.base_url
    settings_api._SETTINGS_STORE["edc_username"]["value"] = next_payload.username
    settings_api._SETTINGS_STORE["edc_password"]["value"] = next_payload.password
    settings_api._SETTINGS_STORE["edc_api_key"]["value"] = next_payload.api_key

    cleared_host_channel_count = 0
    cleared_definition_binding_count = 0
    cleared_active_baseline_id = ""
    cleared_host_channel_catalog_count = len(settings_api._HOST_CHANNEL_CATALOG_CACHE)

    if connection_material_changed:
        settings_api._HOST_CHANNEL_CATALOG_CACHE.clear()
        settings_api._HOST_CHANNEL_LAST_SYNC_AT = None
        settings_api._HOST_CONNECTIVITY_STATUS.clear()
        settings_api._HOST_CONNECTIVITY_STATUS.update(
            settings_api._build_disconnected_host_connectivity_status(next_payload.base_url)
        )

    if source_identity_changed:
        cleared_host_channel_count = len(settings_api._HOST_CHANNEL_STORE)
        settings_api._HOST_CHANNEL_STORE.clear()

        cleared_active_baseline_id = str(
            settings_api._SETTINGS_STORE.get("active_baseline_id", {}).get("value") or ""
        ).strip()
        settings_api._SETTINGS_STORE["active_baseline_id"]["value"] = ""

        for definition in baseline_definitions_api._DEFINITION_STORE.values():
            for metric in list(definition.get("metrics", [])):
                if metric.get("edc_channel_id") is None:
                    continue
                metric["edc_channel_id"] = None
                cleared_definition_binding_count += 1

    if connection_material_changed:
        settings_api._invalidate_compare_runtime_caches()

    return SourceSwitchMutationResult(
        source_identity_changed=source_identity_changed,
        connection_material_changed=connection_material_changed,
        cleared_host_channel_count=cleared_host_channel_count,
        cleared_host_channel_catalog_count=cleared_host_channel_catalog_count,
        cleared_definition_binding_count=cleared_definition_binding_count,
        cleared_active_baseline_id=cleared_active_baseline_id,
        next_source=next_payload.base_url or "--",
    )
