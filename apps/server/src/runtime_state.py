"""运行态持久化。

将当前仍使用内存 store 的原型数据落到 SQLite，避免开发期 reload 后状态丢失。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import settings as app_settings
from .database import async_session_maker
from .models import Setting
from .time_utils import from_timestamp_ms, to_timestamp_ms, utc_now

_SECTION_TO_KEY = {
    "settings_store": "runtime_settings_store",
    "source_revision": "runtime_source_revision",
    "host_channels": "runtime_host_channels",
    "host_channel_catalog": "runtime_host_channel_catalog",
    "channel_role_bindings": "runtime_channel_role_bindings",
    "host_channel_last_sync_at": "runtime_host_channel_last_sync_at",
    "host_connectivity_status": "runtime_host_connectivity_status",
    "baseline_definitions": "runtime_baseline_definitions",
    "baselines": "runtime_baselines",
    "heats": "runtime_heats",
    "active_heat_runtime": "runtime_active_heat_runtime",
    "previous_heat_runtime": "runtime_previous_heat_runtime",
    "heat_id_aliases": "runtime_heat_id_aliases",
    "heat_runtime_refresh_meta": "runtime_heat_runtime_refresh_meta",
    "tasks": "runtime_tasks",
    "mock_heats": "runtime_mock_heats",
    "next_heat_index": "runtime_next_heat_index",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__type__": "timestamp_ms", "value": to_timestamp_ms(value)}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _json_object_hook(value: dict[str, Any]) -> Any:
    if value.get("__type__") == "timestamp_ms" and isinstance(value.get("value"), int):
        return from_timestamp_ms(value["value"])
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
    from .api import tasks as tasks_api

    selected_sections = sections or tuple(_SECTION_TO_KEY.keys())
    state_by_section: dict[str, Any] = {
        "settings_store": settings_api._SETTINGS_STORE,
        "source_revision": settings_api._HOST_SOURCE_REVISION,
        "host_channels": settings_api._HOST_CHANNEL_STORE,
        "host_channel_catalog": settings_api._HOST_CHANNEL_CATALOG_CACHE,
        "channel_role_bindings": settings_api._CHANNEL_ROLE_BINDING_STORE,
        "host_channel_last_sync_at": settings_api._HOST_CHANNEL_LAST_SYNC_AT,
        "host_connectivity_status": settings_api._HOST_CONNECTIVITY_STATUS,
        "baseline_definitions": baseline_definitions_api._DEFINITION_STORE,
        "baselines": baselines_api._BASELINE_STORE,
        "heats": heats_api._HEAT_STORE,
        "active_heat_runtime": heats_api._ACTIVE_HEAT_RUNTIME,
        "previous_heat_runtime": heats_api._PREVIOUS_HEAT_RUNTIME,
        "heat_id_aliases": heats_api._HEAT_ID_ALIAS_STORE,
        "heat_runtime_refresh_meta": heats_api._HEAT_RUNTIME_REFRESH_META,
        "tasks": tasks_api._TASK_STORE,
        "mock_heats": heats_api._MOCK_HEAT_STREAM_STORE,
        "next_heat_index": heats_api._NEXT_MOCK_HEAT_INDEX,
    }

    async with async_session_maker() as session:
        for section in selected_sections:
            if section not in _SECTION_TO_KEY:
                continue
            key = _SECTION_TO_KEY[section]
            encoded = json.dumps(state_by_section[section], default=_json_default, ensure_ascii=False)
            updated_at = utc_now()
            statement = sqlite_insert(Setting).values(
                key=key,
                value=encoded,
                description=f"运行态持久化：{section}",
                updated_at=updated_at,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[Setting.key],
                set_={
                    "value": encoded,
                    "description": f"运行态持久化：{section}",
                    "updated_at": updated_at,
                },
            )
            await session.execute(statement)
        await session.commit()


async def load_runtime_state() -> None:
    """从 SQLite 恢复运行态；首次启动时写入当前默认值。"""
    from .api import baseline_definitions as baseline_definitions_api
    from .api import baselines as baselines_api
    from .api import heats as heats_api
    from .api import settings as settings_api
    from .api import tasks as tasks_api

    payloads = await _read_runtime_payloads()
    if not any(payload is not None for payload in payloads.values()):
        if app_settings.bootstrap_mode.strip().lower() == "blank":
            settings_api._HOST_CHANNEL_STORE.clear()
            settings_api._HOST_CHANNEL_CATALOG_CACHE.clear()
            settings_api._clear_channel_role_bindings()
            settings_api._HOST_CHANNEL_LAST_SYNC_AT = None
            settings_api._HOST_CONNECTIVITY_STATUS.clear()
            settings_api._HOST_CONNECTIVITY_STATUS.update(
                settings_api._build_disconnected_host_connectivity_status(
                    app_settings.edc_base_url
                )
            )
            settings_api._SETTINGS_STORE["active_baseline_id"]["value"] = ""
            baseline_definitions_api._DEFINITION_STORE.clear()
            baselines_api._BASELINE_STORE.clear()
            heats_api._HEAT_STORE.clear()
            heats_api._ACTIVE_HEAT_RUNTIME.clear()
            heats_api._PREVIOUS_HEAT_RUNTIME.clear()
            heats_api._HEAT_ID_ALIAS_STORE.clear()
            heats_api._reset_heat_runtime_refresh_meta()
            tasks_api._TASK_STORE.clear()
            heats_api._MOCK_HEAT_STREAM_STORE.clear()
            heats_api._NEXT_MOCK_HEAT_INDEX = 1
        await persist_runtime_state()
        return

    default_settings_store = {
        key: dict(payload) for key, payload in settings_api._SETTINGS_STORE.items()
    }

    if isinstance(payloads.get("settings_store"), dict):
        settings_api._SETTINGS_STORE.clear()
        settings_api._SETTINGS_STORE.update(default_settings_store)
        settings_api._SETTINGS_STORE.update(payloads["settings_store"])

    if isinstance(payloads.get("source_revision"), int):
        settings_api._HOST_SOURCE_REVISION = max(payloads["source_revision"], 1)

    edc_connection_overridden = settings_api.apply_app_edc_connection_override()

    if isinstance(payloads.get("host_channels"), list) and not edc_connection_overridden:
        settings_api._HOST_CHANNEL_STORE.clear()
        settings_api._HOST_CHANNEL_STORE.extend(payloads["host_channels"])

    if isinstance(payloads.get("host_channel_catalog"), list) and not edc_connection_overridden:
        settings_api._HOST_CHANNEL_CATALOG_CACHE.clear()
        settings_api._HOST_CHANNEL_CATALOG_CACHE.extend(payloads["host_channel_catalog"])

    if isinstance(payloads.get("channel_role_bindings"), dict):
        settings_api._CHANNEL_ROLE_BINDING_STORE.clear()
        settings_api._CHANNEL_ROLE_BINDING_STORE.update(payloads["channel_role_bindings"])

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

    if isinstance(payloads.get("active_heat_runtime"), dict):
        heats_api._ACTIVE_HEAT_RUNTIME.clear()
        heats_api._ACTIVE_HEAT_RUNTIME.update(payloads["active_heat_runtime"])

    if isinstance(payloads.get("previous_heat_runtime"), dict):
        heats_api._PREVIOUS_HEAT_RUNTIME.clear()
        heats_api._PREVIOUS_HEAT_RUNTIME.update(payloads["previous_heat_runtime"])

    if isinstance(payloads.get("heat_id_aliases"), dict):
        heats_api._HEAT_ID_ALIAS_STORE.clear()
        heats_api._HEAT_ID_ALIAS_STORE.update(
            {
                str(source_id): str(target_id)
                for source_id, target_id in payloads["heat_id_aliases"].items()
                if source_id and target_id
            }
        )

    if isinstance(payloads.get("heat_runtime_refresh_meta"), dict):
        heats_api._HEAT_RUNTIME_REFRESH_META.clear()
        heats_api._HEAT_RUNTIME_REFRESH_META.update(payloads["heat_runtime_refresh_meta"])
    else:
        heats_api._reset_heat_runtime_refresh_meta()

    if isinstance(payloads.get("tasks"), dict):
        tasks_api._TASK_STORE.clear()
        tasks_api._TASK_STORE.update(payloads["tasks"])

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

    settings_api._reconcile_channel_role_binding_store()

    if edc_connection_overridden:
        await persist_runtime_state(
            "settings_store",
            "host_channels",
            "host_channel_catalog",
            "channel_role_bindings",
            "host_channel_last_sync_at",
            "host_connectivity_status",
            "baseline_definitions",
        )
