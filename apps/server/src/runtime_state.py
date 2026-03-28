"""运行态持久化。

将当前仍使用内存 store 的原型数据落到 SQLite，避免开发期 reload 后状态丢失。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from .database import async_session_maker
from .models import Setting

_SECTION_TO_KEY = {
    "settings_store": "runtime_settings_store",
    "host_channels": "runtime_host_channels",
    "host_channel_catalog": "runtime_host_channel_catalog",
    "host_channel_last_sync_at": "runtime_host_channel_last_sync_at",
    "host_connectivity_status": "runtime_host_connectivity_status",
    "baseline_definitions": "runtime_baseline_definitions",
    "baselines": "runtime_baselines",
    "heats": "runtime_heats",
    "mock_heats": "runtime_mock_heats",
    "next_heat_index": "runtime_next_heat_index",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__type__": "datetime", "value": value.isoformat()}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _json_object_hook(value: dict[str, Any]) -> Any:
    if value.get("__type__") == "datetime" and isinstance(value.get("value"), str):
        return datetime.fromisoformat(value["value"])
    return value


async def _read_runtime_payloads() -> dict[str, Any]:
    async with async_session_maker() as session:
        rows = await session.execute(
            select(Setting).where(Setting.key.in_(_SECTION_TO_KEY.values()))
        )
        records = {row.key: row.value for row in rows.scalars()}

    payloads: dict[str, Any] = {}
    for section, key in _SECTION_TO_KEY.items():
        raw_value = records.get(key)
        if not raw_value:
            payloads[section] = None
            continue
        payloads[section] = json.loads(raw_value, object_hook=_json_object_hook)
    return payloads


async def persist_runtime_state(*sections: str) -> None:
    """将当前内存态写入 SQLite。"""
    from .api import baseline_definitions as baseline_definitions_api
    from .api import baselines as baselines_api
    from .api import heats as heats_api
    from .api import settings as settings_api

    selected_sections = sections or tuple(_SECTION_TO_KEY.keys())
    state_by_section: dict[str, Any] = {
        "settings_store": settings_api._SETTINGS_STORE,
        "host_channels": settings_api._HOST_CHANNEL_STORE,
        "host_channel_catalog": settings_api._HOST_CHANNEL_CATALOG_CACHE,
        "host_channel_last_sync_at": settings_api._HOST_CHANNEL_LAST_SYNC_AT,
        "host_connectivity_status": settings_api._HOST_CONNECTIVITY_STATUS,
        "baseline_definitions": baseline_definitions_api._DEFINITION_STORE,
        "baselines": baselines_api._BASELINE_STORE,
        "heats": heats_api._HEAT_STORE,
        "mock_heats": heats_api._MOCK_HEAT_STREAM_STORE,
        "next_heat_index": heats_api._NEXT_MOCK_HEAT_INDEX,
    }

    async with async_session_maker() as session:
        for section in selected_sections:
            if section not in _SECTION_TO_KEY:
                continue
            key = _SECTION_TO_KEY[section]
            encoded = json.dumps(state_by_section[section], default=_json_default, ensure_ascii=False)
            row = await session.get(Setting, key)
            if row is None:
                session.add(
                    Setting(
                        key=key,
                        value=encoded,
                        description=f"运行态持久化：{section}",
                    )
                )
            else:
                row.value = encoded
                row.description = f"运行态持久化：{section}"
        await session.commit()


async def load_runtime_state() -> None:
    """从 SQLite 恢复运行态；首次启动时写入当前默认值。"""
    from .api import baseline_definitions as baseline_definitions_api
    from .api import baselines as baselines_api
    from .api import heats as heats_api
    from .api import settings as settings_api

    payloads = await _read_runtime_payloads()
    if not any(payload is not None for payload in payloads.values()):
        await persist_runtime_state()
        return

    if isinstance(payloads.get("settings_store"), dict):
        settings_api._SETTINGS_STORE.clear()
        settings_api._SETTINGS_STORE.update(payloads["settings_store"])

    edc_connection_overridden = settings_api.apply_app_edc_connection_override()

    if isinstance(payloads.get("host_channels"), list) and not edc_connection_overridden:
        settings_api._HOST_CHANNEL_STORE.clear()
        settings_api._HOST_CHANNEL_STORE.extend(payloads["host_channels"])

    if isinstance(payloads.get("host_channel_catalog"), list) and not edc_connection_overridden:
        settings_api._HOST_CHANNEL_CATALOG_CACHE.clear()
        settings_api._HOST_CHANNEL_CATALOG_CACHE.extend(payloads["host_channel_catalog"])

    if not edc_connection_overridden:
        settings_api._HOST_CHANNEL_LAST_SYNC_AT = payloads.get("host_channel_last_sync_at")

    if isinstance(payloads.get("host_connectivity_status"), dict) and not edc_connection_overridden:
        settings_api._HOST_CONNECTIVITY_STATUS.clear()
        settings_api._HOST_CONNECTIVITY_STATUS.update(payloads["host_connectivity_status"])

    if isinstance(payloads.get("baseline_definitions"), dict):
        baseline_definitions_api._DEFINITION_STORE.clear()
        baseline_definitions_api._DEFINITION_STORE.update(payloads["baseline_definitions"])

    if isinstance(payloads.get("baselines"), dict):
        baselines_api._BASELINE_STORE.clear()
        baselines_api._BASELINE_STORE.update(payloads["baselines"])

    if isinstance(payloads.get("heats"), dict):
        ordinary_heats = {
            heat_id: item
            for heat_id, item in payloads["heats"].items()
            if not heats_api._is_mock_heat_record(item)
        }
        heats_api._HEAT_STORE.clear()
        heats_api._HEAT_STORE.update(ordinary_heats)

    legacy_mock_heats = None
    if isinstance(payloads.get("heats"), dict):
        legacy_mock_heats = {
            heat_id: item
            for heat_id, item in payloads["heats"].items()
            if heats_api._is_mock_heat_record(item)
        }

    if isinstance(payloads.get("mock_heats"), dict):
        heats_api._MOCK_HEAT_STREAM_STORE.clear()
        heats_api._MOCK_HEAT_STREAM_STORE.update(payloads["mock_heats"])
    elif isinstance(legacy_mock_heats, dict) and legacy_mock_heats:
        heats_api._MOCK_HEAT_STREAM_STORE.clear()
        heats_api._MOCK_HEAT_STREAM_STORE.update(legacy_mock_heats)

    if isinstance(payloads.get("next_heat_index"), int):
        heats_api._NEXT_MOCK_HEAT_INDEX = payloads["next_heat_index"]

    if edc_connection_overridden:
        await persist_runtime_state(
            "settings_store",
            "host_channels",
            "host_channel_catalog",
            "host_channel_last_sync_at",
            "host_connectivity_status",
        )
