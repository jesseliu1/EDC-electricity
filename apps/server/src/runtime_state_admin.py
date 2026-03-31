"""运行态运维脚本。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .channel_roles import (
    binding_score,
    channel_score,
    default_channel_role_bindings,
    infer_metric_kind,
    normalize_channel_role_bindings,
    reconcile_channel_role_bindings,
)
from .config import settings as app_settings
from .runtime_state import _SECTION_TO_KEY
from .services import EDCClient, EDCClientError

RUNTIME_SETTINGS_STORE_KEY = _SECTION_TO_KEY["settings_store"]
RUNTIME_HOST_CHANNELS_KEY = _SECTION_TO_KEY["host_channels"]
RUNTIME_HOST_CHANNEL_CATALOG_KEY = _SECTION_TO_KEY["host_channel_catalog"]
RUNTIME_CHANNEL_ROLE_BINDINGS_KEY = _SECTION_TO_KEY["channel_role_bindings"]
RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY = _SECTION_TO_KEY["host_channel_last_sync_at"]
RUNTIME_HOST_CONNECTIVITY_STATUS_KEY = _SECTION_TO_KEY["host_connectivity_status"]
RUNTIME_BASELINE_DEFINITIONS_KEY = _SECTION_TO_KEY["baseline_definitions"]
REALTIME_PROBE_WINDOW = timedelta(minutes=5)
MAX_LIVE_PROBE_CANDIDATES = 12


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _load_json_record(connection: sqlite3.Connection, key: str) -> Any:
    row = connection.execute("select value from settings where key = ?", (key,)).fetchone()
    if row is None or row["value"] is None:
        return None
    return json.loads(row["value"])


def _upsert_json_record(
    connection: sqlite3.Connection,
    *,
    key: str,
    payload: Any,
    description: str,
) -> None:
    encoded = json.dumps(payload, ensure_ascii=False)
    row = connection.execute("select 1 from settings where key = ?", (key,)).fetchone()
    if row is None:
        connection.execute(
            """
            insert into settings (key, value, description, updated_at)
            values (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (key, encoded, description),
        )
    else:
        connection.execute(
            """
            update settings
            set value = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            where key = ?
            """,
            (encoded, description, key),
        )


def _delete_record(connection: sqlite3.Connection, key: str) -> None:
    connection.execute("delete from settings where key = ?", (key,))


def _get_setting_value(settings_store: dict[str, Any], key: str, fallback: str = "") -> str:
    payload = settings_store.get(key)
    if isinstance(payload, dict):
        return str(payload.get("value") or fallback).strip()
    return fallback


def _pick_first(payload: dict[str, object], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
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


def _pick_default_added_channel_ids(catalog: list[dict[str, str]]) -> list[str]:
    selected_ids: list[str] = []
    used_ids: set[str] = set()

    def add_first(predicate) -> None:
        for item in catalog:
            if item["id"] in used_ids:
                continue
            if not predicate(item):
                continue
            used_ids.add(item["id"])
            selected_ids.append(item["id"])
            return

    add_first(lambda item: item["unit"].lower() == "kw" or "功率" in item["channel_name"])
    add_first(
        lambda item: item["unit"] == "V"
        or "电压" in item["channel_name"]
        or "電壓" in item["channel_name"]
    )
    add_first(
        lambda item: item["unit"] in {"℃", "°C", "°c"} or "温" in item["channel_name"] or "溫" in item["channel_name"]
    )
    add_first(
        lambda item: _looks_like_pressure(item["channel_name"], item["channel_name"], item["unit"])
    )

    for item in catalog:
        if len(selected_ids) >= 6:
            break
        if item["id"] in used_ids:
            continue
        used_ids.add(item["id"])
        selected_ids.append(item["id"])

    return selected_ids


def _reconcile_selected_host_channels(
    current_channels: list[dict[str, Any]],
    catalog: list[dict[str, str]],
    *,
    required_channels: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    catalog_by_id = {item["id"]: item for item in catalog}
    reconciled_ids: list[str] = []
    seen_ids: set[str] = set()

    for channel in required_channels or []:
        channel_id = str(channel.get("id") or "").strip()
        if not channel_id or channel_id in seen_ids:
            continue
        if channel_id not in catalog_by_id:
            continue
        seen_ids.add(channel_id)
        reconciled_ids.append(channel_id)

    for channel in current_channels:
        if not isinstance(channel, dict):
            continue
        channel_id = str(channel.get("id") or "").strip()
        if not channel_id or channel_id in seen_ids:
            continue
        if channel_id not in catalog_by_id:
            continue
        seen_ids.add(channel_id)
        reconciled_ids.append(channel_id)

    for channel_id in _pick_default_added_channel_ids(catalog):
        if channel_id in seen_ids:
            continue
        seen_ids.add(channel_id)
        reconciled_ids.append(channel_id)
        if len(reconciled_ids) >= 6:
            break

    return [catalog_by_id[channel_id] for channel_id in reconciled_ids[:6]]


def _metric_kind(metric_name: str, unit: str) -> str:
    return infer_metric_kind(metric_name, unit)


def _binding_score(metric: dict[str, Any], channel: dict[str, str]) -> int:
    kind = _metric_kind(str(metric.get("name") or ""), str(metric.get("unit") or ""))
    return binding_score(kind, channel)


def _rebind_definition_payloads(
    definition_store: dict[str, Any],
    catalog: list[dict[str, str]],
    *,
    preferred_channel_ids: dict[str, str] | None = None,
    probe_counts: dict[str, int] | None = None,
) -> int:
    updated_count = 0
    catalog_by_id = {item["id"]: item for item in catalog}
    preferred_channel_ids = preferred_channel_ids or {}
    probe_counts = probe_counts or {}
    for definition in definition_store.values():
        metrics = definition.get("metrics", [])
        if not isinstance(metrics, list):
            continue
        used_ids: set[str] = set()
        for metric in metrics:
            if not isinstance(metric, dict):
                continue

            metric_kind = _metric_kind(str(metric.get("name") or ""), str(metric.get("unit") or ""))
            current_channel_id = str(metric.get("edc_channel_id") or "").strip()
            preferred_channel_id = preferred_channel_ids.get(metric_kind)
            current_probe_count = probe_counts.get(current_channel_id)
            preferred_probe_count = probe_counts.get(preferred_channel_id or "")
            current_binding_score = (
                _binding_score(metric, catalog_by_id[current_channel_id])
                if current_channel_id in catalog_by_id
                else 0
            )
            should_replace_zero_data_binding = (
                preferred_channel_id is not None
                and preferred_channel_id != current_channel_id
                and preferred_probe_count is not None
                and preferred_probe_count > 0
                and current_probe_count == 0
            )
            if (
                current_channel_id
                and current_channel_id in catalog_by_id
                and current_binding_score > 0
                and current_channel_id not in used_ids
                and not should_replace_zero_data_binding
            ):
                used_ids.add(current_channel_id)
                continue

            best_channel = None
            best_score = 0
            if preferred_channel_id and preferred_channel_id in catalog_by_id and preferred_channel_id not in used_ids:
                best_channel = catalog_by_id[preferred_channel_id]
                best_score = max(best_score, 1)
            for channel in catalog:
                if channel["id"] in used_ids:
                    continue
                score = _binding_score(metric, channel)
                if score > best_score:
                    best_score = score
                    best_channel = channel
            next_channel_id = best_channel["id"] if best_channel and best_score > 0 else None
            if metric.get("edc_channel_id") != next_channel_id:
                metric["edc_channel_id"] = next_channel_id
                updated_count += 1
            if next_channel_id:
                used_ids.add(next_channel_id)
    return updated_count


def _metric_probe_score(metric_key: str, channel: dict[str, str]) -> int:
    if metric_key == "power":
        return _binding_score({"name": "功率", "unit": "kW"}, channel)
    if metric_key == "voltage":
        return _binding_score({"name": "电压", "unit": "V"}, channel)
    return 0


def _collect_bound_channels(
    definition_store: dict[str, Any] | None,
    catalog: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not isinstance(definition_store, dict):
        return []

    catalog_by_id = {item["id"]: item for item in catalog}
    collected: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for definition in definition_store.values():
        metrics = definition.get("metrics", [])
        if not isinstance(metrics, list):
            continue
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            channel_id = str(metric.get("edc_channel_id") or "").strip()
            if not channel_id or channel_id in seen_ids:
                continue
            channel = catalog_by_id.get(channel_id)
            if channel is None:
                continue
            seen_ids.add(channel_id)
            collected.append(channel)
    return collected


def _collect_role_bound_channels(
    role_bindings: dict[str, Any] | None,
    catalog: list[dict[str, str]],
) -> list[dict[str, str]]:
    normalized = normalize_channel_role_bindings(role_bindings)
    catalog_by_id = {item["id"]: item for item in catalog}
    collected: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for channel_id in normalized.values():
        if not channel_id or channel_id in seen_ids:
            continue
        channel = catalog_by_id.get(channel_id)
        if channel is None:
            continue
        seen_ids.add(channel_id)
        collected.append(channel)
    return collected


def _reconcile_runtime_role_bindings(
    current_role_bindings: dict[str, Any] | None,
    selected_channels: list[dict[str, str]],
    *,
    preferred_channel_ids: dict[str, str],
    probe_counts: dict[str, int],
) -> dict[str, str | None]:
    current = normalize_channel_role_bindings(current_role_bindings)
    selected_by_id = {item["id"]: item for item in selected_channels}
    reconciled = default_channel_role_bindings()

    for role_key in reconciled:
        current_channel_id = current.get(role_key)
        preferred_channel_id = str(preferred_channel_ids.get(role_key) or "").strip()
        current_probe_count = probe_counts.get(current_channel_id or "")
        preferred_probe_count = probe_counts.get(preferred_channel_id)
        should_replace_zero_data_binding = (
            preferred_channel_id
            and preferred_channel_id != current_channel_id
            and preferred_channel_id in selected_by_id
            and preferred_probe_count is not None
            and preferred_probe_count > 0
            and current_probe_count == 0
        )
        if (
            current_channel_id
            and current_channel_id in selected_by_id
            and not should_replace_zero_data_binding
        ):
            reconciled[role_key] = current_channel_id
            continue
        if preferred_channel_id and preferred_channel_id in selected_by_id:
            reconciled[role_key] = preferred_channel_id

    return reconcile_channel_role_bindings(
        reconciled,
        selected_channels,
        preferred_channel_ids=preferred_channel_ids,
    )


async def _pick_live_metric_channel(
    client: EDCClient,
    *,
    metric_key: str,
    preferred_channels: list[dict[str, Any]],
    catalog: list[dict[str, str]],
    start_time: datetime,
    end_time: datetime,
    probe_counts: dict[str, int],
) -> dict[str, str] | None:
    candidate_ids: set[str] = set()
    ordered_candidates: list[dict[str, str]] = []

    def add_candidate(candidate: dict[str, Any]) -> None:
        if not isinstance(candidate, dict):
            return
        channel_id = str(candidate.get("id") or "").strip()
        if not channel_id or channel_id in candidate_ids:
            return
        score = _metric_probe_score(metric_key, candidate)
        if score <= 0:
            return
        candidate_ids.add(channel_id)
        ordered_candidates.append(candidate)

    for channel in preferred_channels:
        add_candidate(channel)

    fallback_candidates = [
        channel
        for channel in catalog
        if channel["id"] not in candidate_ids and _metric_probe_score(metric_key, channel) > 0
    ]
    fallback_candidates.sort(
        key=lambda channel: (
            -_metric_probe_score(metric_key, channel),
            channel["device_name"],
            channel["channel_name"],
        )
    )
    for channel in fallback_candidates[:MAX_LIVE_PROBE_CANDIDATES]:
        add_candidate(channel)

    for channel in ordered_candidates:
        channel_id = channel["id"]
        points_count = probe_counts.get(channel_id)
        if points_count is None:
            points = await client.get_local_datas(
                suid=channel["suid"],
                cuid=channel["cuid"],
                start_time=start_time,
                end_time=end_time,
            )
            points_count = len(points)
            probe_counts[channel_id] = points_count
        if points_count > 0:
            return channel
    return None


def _build_connected_status(
    *,
    base_url: str,
    sensor_count: int,
    channel_count: int,
    enabled_channel_count: int,
    checked_at: datetime,
) -> dict[str, Any]:
    host = urlparse(base_url).netloc or base_url or "--"
    return {
        "is_connected": True,
        "machine_name": f"EDC Gateway ({host})",
        "last_sync_label": (
            f"{checked_at.year}/{checked_at.month}/{checked_at.day} "
            f"{checked_at:%H:%M:%S}"
        ),
        "meta": {
            "source": base_url or "--",
            "sensor_count": sensor_count,
            "channel_count": channel_count,
            "enabled_channel_count": enabled_channel_count,
        },
    }


def _build_disconnected_status(base_url: str) -> dict[str, Any]:
    return {
        "is_connected": False,
        "machine_name": "--",
        "last_sync_label": "--",
        "meta": {
            "source": base_url or "--",
            "sensor_count": 0,
            "channel_count": 0,
            "enabled_channel_count": 0,
        },
    }


def clear_source_bound_runtime_state(
    db_path: Path,
    *,
    clear_active_baseline: bool = False,
    clear_definition_bindings: bool = True,
) -> None:
    connection = _connect(db_path)
    try:
        settings_store = _load_json_record(connection, RUNTIME_SETTINGS_STORE_KEY)
        if isinstance(settings_store, dict) and clear_active_baseline:
            active_payload = settings_store.get("active_baseline_id")
            if isinstance(active_payload, dict):
                active_payload["value"] = ""
                _upsert_json_record(
                    connection,
                    key=RUNTIME_SETTINGS_STORE_KEY,
                    payload=settings_store,
                    description="运行态持久化：settings_store",
                )

        if clear_definition_bindings:
            definition_store = _load_json_record(connection, RUNTIME_BASELINE_DEFINITIONS_KEY)
            if isinstance(definition_store, dict):
                _rebind_definition_payloads(definition_store, [])
                _upsert_json_record(
                    connection,
                    key=RUNTIME_BASELINE_DEFINITIONS_KEY,
                    payload=definition_store,
                    description="运行态持久化：baseline_definitions",
                )

        for key in (
            RUNTIME_HOST_CHANNELS_KEY,
            RUNTIME_HOST_CHANNEL_CATALOG_KEY,
            RUNTIME_CHANNEL_ROLE_BINDINGS_KEY,
            RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY,
            RUNTIME_HOST_CONNECTIVITY_STATUS_KEY,
        ):
            _delete_record(connection, key)

        connection.commit()
    finally:
        connection.close()


async def refresh_runtime_source_state(
    db_path: Path,
    *,
    rebind_definitions: bool = True,
) -> None:
    connection: sqlite3.Connection | None = _connect(db_path)
    try:
        settings_store = _load_json_record(connection, RUNTIME_SETTINGS_STORE_KEY)
        settings_store = settings_store if isinstance(settings_store, dict) else {}
        current_host_channels = _load_json_record(connection, RUNTIME_HOST_CHANNELS_KEY)
        current_host_channels = current_host_channels if isinstance(current_host_channels, list) else []
        current_role_bindings = _load_json_record(connection, RUNTIME_CHANNEL_ROLE_BINDINGS_KEY)
        current_role_bindings = (
            current_role_bindings if isinstance(current_role_bindings, dict) else default_channel_role_bindings()
        )
        definition_store = _load_json_record(connection, RUNTIME_BASELINE_DEFINITIONS_KEY)
        definition_store = definition_store if isinstance(definition_store, dict) else None
        base_url = _get_setting_value(settings_store, "edc_base_url", app_settings.edc_base_url)
        username = _get_setting_value(settings_store, "edc_username", app_settings.edc_username or "")
        password = _get_setting_value(settings_store, "edc_password", app_settings.edc_password or "")

        if not base_url or not username or not password:
            connection.close()
            connection = None
            clear_source_bound_runtime_state(
                db_path,
                clear_active_baseline=False,
                clear_definition_bindings=rebind_definitions,
            )
            disconnected_status = _build_disconnected_status(base_url)
            connection = _connect(db_path)
            _upsert_json_record(
                connection,
                key=RUNTIME_HOST_CONNECTIVITY_STATUS_KEY,
                payload=disconnected_status,
                description="运行态持久化：host_connectivity_status",
            )
            connection.commit()
            return

        async with EDCClient(base_url=base_url, username=username, password=password) as client:
            sensor_list = await client.get_all_sensor_list()
            catalog = _normalize_host_channels(sensor_list)
            probe_counts: dict[str, int] = {}
            probe_end = datetime.now()
            probe_start = probe_end - REALTIME_PROBE_WINDOW
            preferred_probe_channels = [
                *current_host_channels,
                *_collect_role_bound_channels(current_role_bindings, catalog),
                *_collect_bound_channels(definition_store, catalog),
            ]
            live_power_channel = await _pick_live_metric_channel(
                client,
                metric_key="power",
                preferred_channels=preferred_probe_channels,
                catalog=catalog,
                start_time=probe_start,
                end_time=probe_end,
                probe_counts=probe_counts,
            )
            live_voltage_channel = await _pick_live_metric_channel(
                client,
                metric_key="voltage",
                preferred_channels=preferred_probe_channels,
                catalog=catalog,
                start_time=probe_start,
                end_time=probe_end,
                probe_counts=probe_counts,
            )

        selected_channels = _reconcile_selected_host_channels(
            current_host_channels,
            catalog,
            required_channels=[
                channel
                for channel in (live_power_channel, live_voltage_channel)
                if channel is not None
            ],
        )
        checked_at = datetime.now()
        connected_status = _build_connected_status(
            base_url=base_url,
            sensor_count=len(sensor_list),
            channel_count=len(catalog),
            enabled_channel_count=len(selected_channels),
            checked_at=checked_at,
        )
        preferred_role_channel_ids = {
            role_key: channel["id"]
            for role_key, channel in {
                "dashboard_primary": live_power_channel,
                "dashboard_secondary": live_voltage_channel,
                "live_heat_inference": live_power_channel,
            }.items()
            if channel is not None
        }
        role_bindings = _reconcile_runtime_role_bindings(
            current_role_bindings,
            selected_channels,
            preferred_channel_ids=preferred_role_channel_ids,
            probe_counts=probe_counts,
        )

        _upsert_json_record(
            connection,
            key=RUNTIME_HOST_CHANNEL_CATALOG_KEY,
            payload=catalog,
            description="运行态持久化：host_channel_catalog",
        )
        _upsert_json_record(
            connection,
            key=RUNTIME_HOST_CHANNELS_KEY,
            payload=selected_channels,
            description="运行态持久化：host_channels",
        )
        _upsert_json_record(
            connection,
            key=RUNTIME_CHANNEL_ROLE_BINDINGS_KEY,
            payload=role_bindings,
            description="运行态持久化：channel_role_bindings",
        )
        _upsert_json_record(
            connection,
            key=RUNTIME_HOST_CONNECTIVITY_STATUS_KEY,
            payload=connected_status,
            description="运行态持久化：host_connectivity_status",
        )
        _upsert_json_record(
            connection,
            key=RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY,
            payload={"__type__": "datetime", "value": checked_at.isoformat()},
            description="运行态持久化：host_channel_last_sync_at",
        )

        if rebind_definitions:
            if isinstance(definition_store, dict):
                preferred_channel_ids = {
                    metric_key: channel["id"]
                    for metric_key, channel in {
                        "power": live_power_channel,
                        "voltage": live_voltage_channel,
                    }.items()
                    if channel is not None
                }
                _rebind_definition_payloads(
                    definition_store,
                    catalog,
                    preferred_channel_ids=preferred_channel_ids,
                    probe_counts=probe_counts,
                )
                _upsert_json_record(
                    connection,
                    key=RUNTIME_BASELINE_DEFINITIONS_KEY,
                    payload=definition_store,
                    description="运行态持久化：baseline_definitions",
                )

        connection.commit()
    finally:
        if connection is not None:
            connection.close()


def factory_reset_runtime_state(db_path: Path) -> None:
    connection = _connect(db_path)
    try:
        for key in _SECTION_TO_KEY.values():
            _delete_record(connection, key)
        connection.commit()
    finally:
        connection.close()


async def _run() -> None:
    parser = argparse.ArgumentParser(description="运行态运维工具")
    parser.add_argument("--db", required=True, help="SQLite 数据库路径")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["deploy-refresh", "clear-source-bound", "factory-reset"],
        help="执行模式",
    )
    parser.add_argument(
        "--no-rebind-definitions",
        action="store_true",
        help="部署刷新时不要自动重绑基线定义通道",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if args.mode == "deploy-refresh":
        await refresh_runtime_source_state(
            db_path,
            rebind_definitions=not args.no_rebind_definitions,
        )
        return
    if args.mode == "clear-source-bound":
        clear_source_bound_runtime_state(
            db_path,
            clear_active_baseline=False,
            clear_definition_bindings=True,
        )
        return
    if args.mode == "factory-reset":
        factory_reset_runtime_state(db_path)
        return
    raise RuntimeError(f"未知模式: {args.mode}")


def main() -> None:
    try:
        asyncio.run(_run())
    except EDCClientError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
