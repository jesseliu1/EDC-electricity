"""业务通道角色绑定辅助工具。"""

from __future__ import annotations

from typing import Any

CHANNEL_ROLE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "role_key": "dashboard_primary",
        "label": "Dashboard 主曲线",
        "description": "Dashboard 实时主曲线绑定",
        "metric_kind": "power",
        "required": True,
    },
    {
        "role_key": "dashboard_secondary",
        "label": "Dashboard 辅曲线",
        "description": "Dashboard 实时辅曲线绑定",
        "metric_kind": "voltage",
        "required": False,
    },
    {
        "role_key": "live_heat_inference",
        "label": "炉次推断主信号",
        "description": "真实炉次推断主信号绑定",
        "metric_kind": "power",
        "required": True,
    },
)

CHANNEL_ROLE_KEYS: tuple[str, ...] = tuple(
    str(item["role_key"]) for item in CHANNEL_ROLE_DEFINITIONS
)


def default_channel_role_bindings() -> dict[str, str | None]:
    return {role_key: None for role_key in CHANNEL_ROLE_KEYS}


def normalize_channel_role_bindings(
    payload: dict[str, Any] | None,
) -> dict[str, str | None]:
    normalized = default_channel_role_bindings()
    if not isinstance(payload, dict):
        return normalized

    for role_key in CHANNEL_ROLE_KEYS:
        channel_id = payload.get(role_key)
        if channel_id is None:
            continue
        text = str(channel_id).strip()
        if text:
            normalized[role_key] = text
    return normalized


def contains_phase(text: str) -> bool:
    lowered = text.lower()
    return "a相" in lowered or "b相" in lowered or "c相" in lowered


def contains_total(channel_name: str) -> bool:
    return "总" in channel_name or "總" in channel_name


def contains_fundamental(text: str) -> bool:
    lowered = text.lower()
    return "基波" in lowered or "fundamental" in lowered


def looks_like_pressure(channel_name: str, text: str, unit: str) -> bool:
    normalized_unit = unit.lower()
    return (
        normalized_unit == "mpa"
        or "压力" in channel_name
        or "壓力" in channel_name
        or "pressure" in text
    )


def infer_metric_kind(metric_name: str, unit: str) -> str:
    name = metric_name.lower()
    normalized_unit = unit.lower()
    if "功率" in metric_name or "power" in name or normalized_unit == "kw":
        return "power"
    if "电压" in metric_name or "電壓" in metric_name or "voltage" in name or unit == "V":
        return "voltage"
    if "温" in metric_name or "溫" in metric_name or "temperature" in name or unit in {"°C", "℃"}:
        return "temperature"
    if looks_like_pressure(metric_name, name, unit):
        return "pressure"
    return "generic"


def channel_score(channel_name: str, unit: str, device_type: str) -> int:
    text = f"{channel_name} {unit} {device_type}".lower()
    score = 0
    if (
        "有功" in channel_name
        or "實功" in channel_name
        or "实功" in channel_name
        or "power" in text
        or unit.lower() == "kw"
    ):
        score += 120
    if "电压" in channel_name or "電壓" in channel_name or unit.lower() == "v":
        score += 110
    if "温" in channel_name or "溫" in channel_name or "temp" in text or unit in {"℃", "°c", "°C"}:
        score += 100
    if looks_like_pressure(channel_name, text, unit):
        score += 90
    if contains_total(channel_name):
        score += 24
    if contains_phase(text):
        score += 8
    if contains_fundamental(text):
        score -= 16
    return score


def binding_score(metric_kind: str, channel: dict[str, str]) -> int:
    channel_name = str(channel.get("channel_name") or "")
    unit = str(channel.get("unit") or "")
    device_type = str(channel.get("device_type") or "")
    text = f"{channel_name} {unit} {device_type}".lower()
    score = 0

    if metric_kind == "power":
        if unit.lower() == "kw":
            score += 120
        if (
            "功率" in channel_name
            or "有功" in channel_name
            or "實功" in channel_name
            or "实功" in channel_name
            or "power" in text
        ):
            score += 100
        if contains_total(channel_name):
            score += 24
    elif metric_kind == "voltage":
        if unit == "V":
            score += 120
        if "电压" in channel_name or "電壓" in channel_name or "voltage" in text:
            score += 100
        if "a相" in channel_name.lower():
            score += 12
    elif metric_kind == "temperature":
        if unit in {"℃", "°C", "°c"}:
            score += 120
        if "温" in channel_name or "溫" in channel_name or "temp" in text:
            score += 100
    elif metric_kind == "pressure":
        if unit.lower() == "mpa":
            score += 120
        if looks_like_pressure(channel_name, text, unit):
            score += 100
    else:
        score += channel_score(channel_name, unit, device_type)

    if contains_fundamental(text):
        score -= 16
    return score


def pick_best_channel_for_metric_kind(
    available_channels: list[dict[str, str]],
    metric_kind: str,
) -> dict[str, str] | None:
    best_channel: dict[str, str] | None = None
    best_score = 0
    for channel in available_channels:
        score = binding_score(metric_kind, channel)
        if score <= best_score:
            continue
        best_score = score
        best_channel = channel
    if best_score <= 0:
        return None
    return best_channel


def format_host_channel_label(channel: dict[str, str] | None) -> str | None:
    if not channel:
        return None
    return f'{channel["device_name"]} / {channel["channel_name"]} / {channel["unit"] or "--"}'


def resolve_channel_role(
    role_key: str,
    bindings: dict[str, Any] | None,
    available_channels: list[dict[str, str]],
) -> dict[str, str] | None:
    normalized = normalize_channel_role_bindings(bindings)
    channel_id = normalized.get(role_key)
    if not channel_id:
        return None
    return next((item for item in available_channels if item["id"] == channel_id), None)


def describe_channel_role_bindings(
    bindings: dict[str, Any] | None,
    available_channels: list[dict[str, str]],
) -> dict[str, Any]:
    normalized = normalize_channel_role_bindings(bindings)
    available_by_id = {item["id"]: item for item in available_channels}
    items: list[dict[str, Any]] = []
    missing_required_role_keys: list[str] = []
    configured_count = 0

    for definition in CHANNEL_ROLE_DEFINITIONS:
        role_key = str(definition["role_key"])
        channel = available_by_id.get(str(normalized.get(role_key) or ""))
        configured = channel is not None
        if configured:
            configured_count += 1
        if bool(definition["required"]) and not configured:
            missing_required_role_keys.append(role_key)
        items.append(
            {
                "role_key": role_key,
                "label": str(definition["label"]),
                "description": str(definition["description"]),
                "metric_kind": str(definition["metric_kind"]),
                "required": bool(definition["required"]),
                "channel_id": channel["id"] if channel else None,
                "configured": configured,
                "source_channel_name": channel["channel_name"] if channel else None,
                "source_channel_label": format_host_channel_label(channel),
            }
        )

    return {
        "items": items,
        "total": len(items),
        "configured_count": configured_count,
        "missing_required_role_keys": missing_required_role_keys,
    }


def reconcile_channel_role_bindings(
    current_bindings: dict[str, Any] | None,
    available_channels: list[dict[str, str]],
    *,
    preferred_channel_ids: dict[str, str] | None = None,
    fill_defaults: bool = True,
) -> dict[str, str | None]:
    available_by_id = {item["id"]: item for item in available_channels}
    preferred_channel_ids = preferred_channel_ids or {}
    current = normalize_channel_role_bindings(current_bindings)
    reconciled = default_channel_role_bindings()

    for role_key in CHANNEL_ROLE_KEYS:
        current_channel_id = current.get(role_key)
        if current_channel_id and current_channel_id in available_by_id:
            reconciled[role_key] = current_channel_id

    for role_key in CHANNEL_ROLE_KEYS:
        if reconciled[role_key] is not None:
            continue
        preferred_channel_id = str(preferred_channel_ids.get(role_key) or "").strip()
        if preferred_channel_id and preferred_channel_id in available_by_id:
            reconciled[role_key] = preferred_channel_id

    if not fill_defaults:
        return reconciled

    if reconciled["dashboard_primary"] is None:
        primary = pick_best_channel_for_metric_kind(available_channels, "power")
        if primary is not None:
            reconciled["dashboard_primary"] = primary["id"]

    if reconciled["dashboard_secondary"] is None:
        secondary = pick_best_channel_for_metric_kind(available_channels, "voltage")
        if secondary is not None:
            reconciled["dashboard_secondary"] = secondary["id"]

    if reconciled["live_heat_inference"] is None:
        if reconciled["dashboard_primary"] is not None:
            reconciled["live_heat_inference"] = reconciled["dashboard_primary"]
        else:
            inference = pick_best_channel_for_metric_kind(available_channels, "power")
            if inference is not None:
                reconciled["live_heat_inference"] = inference["id"]

    return reconciled
