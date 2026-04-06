"""运行态运维脚本测试。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src.runtime_state import _SECTION_TO_KEY
from src.runtime_state_admin import (
    RUNTIME_BASELINE_DEFINITIONS_KEY,
    RUNTIME_CHANNEL_ROLE_BINDINGS_KEY,
    RUNTIME_HOST_CHANNEL_CATALOG_KEY,
    RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY,
    RUNTIME_HOST_CHANNELS_KEY,
    RUNTIME_HOST_CONNECTIVITY_STATUS_KEY,
    RUNTIME_SETTINGS_STORE_KEY,
    factory_reset_runtime_state,
    refresh_runtime_source_state,
)
from src.time_utils import utc_now_ms


def _init_settings_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            create table settings (
                key text primary key,
                value text not null,
                description text,
                updated_at integer
            )
            """
        )
        connection.execute(
            """
            create table baseline_definitions (
                id text primary key
            )
            """
        )
        connection.execute(
            """
            create table baseline_definition_metrics (
                definition_id text not null,
                item text not null,
                primary key (definition_id, item)
            )
            """
        )
        connection.execute(
            """
            create table baselines (
                definition_id text not null,
                item text not null,
                primary key (definition_id, item)
            )
            """
        )
        connection.execute(
            """
            create table heats (
                id text primary key,
                heat_no text
            )
            """
        )
        connection.execute(
            """
            create table metric_series (
                owner_key text not null,
                item text not null,
                primary key (owner_key, item)
            )
            """
        )
        connection.execute(
            """
            create table tasks (
                id text primary key,
                heat_id text
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def _write_json_record(db_path: Path, key: str, payload: Any) -> None:
    connection = sqlite3.connect(db_path)
    try:
        encoded = json.dumps(payload, ensure_ascii=False)
        connection.execute(
            """
            insert into settings (key, value, description, updated_at)
            values (?, ?, ?, ?)
            """,
            (key, encoded, f"test:{key}", utc_now_ms()),
        )
        connection.commit()
    finally:
        connection.close()


def _read_json_record(db_path: Path, key: str) -> Any:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute("select value from settings where key = ?", (key,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])
    finally:
        connection.close()


def _table_info(db_path: Path, table_name: str) -> list[sqlite3.Row]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(f"pragma table_info({table_name})").fetchall()
    finally:
        connection.close()


class _FakeEDCClient:
    def __init__(self, **_kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _FakeEDCClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def get_all_sensor_list(self) -> list[dict[str, object]]:
        return [
            {
                "uid": "2752",
                "name": "测试电力",
                "typeName": "三相智能电表",
                "channelList": [
                    {
                        "cuid": "199",
                        "chnName": "总有功功率",
                        "chnDim": "kW",
                        "lastData": "410.2",
                        "status": "1",
                    },
                    {
                        "cuid": "128",
                        "chnName": "A相电压",
                        "chnDim": "V",
                        "lastData": "221.0",
                        "status": "1",
                    },
                ],
            },
            {
                "uid": "300000000000000000001",
                "name": "测试温度",
                "typeName": "热电偶温度采集器",
                "channelList": [
                    {
                        "cuid": "128",
                        "chnName": "热电偶温度采集通道",
                        "chnDim": "℃",
                        "lastData": "1450.0",
                        "status": "1",
                    }
                ],
            },
            {
                "uid": "2755",
                "name": "测试压力",
                "typeName": "压力传感器",
                "channelList": [
                    {
                        "cuid": "128",
                        "chnName": "炉压",
                        "chnDim": "MPa",
                        "lastData": "0.42",
                        "status": "1",
                    }
                ],
            },
        ]

    async def get_local_datas(
        self,
        *,
        suid: str,
        cuid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, float | int]]:
        _ = (start_time, end_time)
        if (suid, cuid) in {
            ("2752", "199"),
            ("2752", "128"),
            ("300000000000000000001", "128"),
            ("2755", "128"),
        }:
            return [{"timestamp": 1774878050195, "value": 1.0}]
        return []


@pytest.mark.asyncio
async def test_refresh_runtime_source_state_rebuilds_catalog_and_rebinds_definitions(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "runtime-admin.db"
    _init_settings_db(db_path)
    _write_json_record(
        db_path,
        RUNTIME_SETTINGS_STORE_KEY,
        {
            "edc_base_url": {"value": "http://61.216.55.133"},
            "edc_username": {"value": "admin"},
            "edc_password": {"value": "admin"},
            "active_baseline_id": {"value": "baseline-001"},
        },
    )
    _write_json_record(
        db_path,
        RUNTIME_BASELINE_DEFINITIONS_KEY,
        {
            "def-001": {
                "id": "def-001",
                "metrics": [
                    {"id": "metric-001", "name": "功率", "unit": "kW", "edc_channel_id": "2349-199"},
                    {"id": "metric-002", "name": "电压", "unit": "V", "edc_channel_id": "2349-128"},
                    {"id": "metric-003", "name": "炉温", "unit": "°C", "edc_channel_id": "2054-128"},
                    {"id": "metric-004", "name": "炉压", "unit": "MPa", "edc_channel_id": "769-128"},
                ],
            }
        },
    )

    monkeypatch.setattr("src.runtime_state_admin.EDCClient", _FakeEDCClient)

    await refresh_runtime_source_state(db_path)

    catalog = _read_json_record(db_path, RUNTIME_HOST_CHANNEL_CATALOG_KEY)
    selected_channels = _read_json_record(db_path, RUNTIME_HOST_CHANNELS_KEY)
    role_bindings = _read_json_record(db_path, RUNTIME_CHANNEL_ROLE_BINDINGS_KEY)
    host_status = _read_json_record(db_path, RUNTIME_HOST_CONNECTIVITY_STATUS_KEY)
    last_sync = _read_json_record(db_path, RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY)
    definitions = _read_json_record(db_path, RUNTIME_BASELINE_DEFINITIONS_KEY)

    assert {item["id"] for item in catalog} == {
        "2752-199",
        "2752-128",
        "300000000000000000001-128",
        "2755-128",
    }
    assert {item["id"] for item in selected_channels} == {
        "2752-199",
        "2752-128",
        "300000000000000000001-128",
        "2755-128",
    }
    assert role_bindings == {
        "dashboard_primary": "2752-199",
        "dashboard_secondary": "2752-128",
        "live_heat_inference": "2752-199",
    }
    assert host_status["is_connected"] is True
    assert host_status["meta"]["source"] == "http://61.216.55.133"
    assert host_status["meta"]["channel_count"] == 4
    assert host_status["meta"]["enabled_channel_count"] == 4
    assert last_sync["__type__"] == "timestamp_ms"
    assert [
        metric["edc_channel_id"]
        for metric in definitions["def-001"]["metrics"]
    ] == [
        "2752-199",
        "2752-128",
        "300000000000000000001-128",
        "2755-128",
    ]
    connection = sqlite3.connect(db_path)
    try:
        updated_at_types = dict(
            connection.execute(
                """
                select key, typeof(updated_at)
                from settings
                where key in (?, ?, ?, ?, ?, ?)
                """,
                (
                    RUNTIME_HOST_CHANNEL_CATALOG_KEY,
                    RUNTIME_HOST_CHANNELS_KEY,
                    RUNTIME_CHANNEL_ROLE_BINDINGS_KEY,
                    RUNTIME_HOST_CONNECTIVITY_STATUS_KEY,
                    RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY,
                    RUNTIME_BASELINE_DEFINITIONS_KEY,
                ),
            ).fetchall()
        )
    finally:
        connection.close()

    assert updated_at_types == {
        RUNTIME_HOST_CHANNEL_CATALOG_KEY: "integer",
        RUNTIME_HOST_CHANNELS_KEY: "integer",
        RUNTIME_CHANNEL_ROLE_BINDINGS_KEY: "integer",
        RUNTIME_HOST_CONNECTIVITY_STATUS_KEY: "integer",
        RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY: "integer",
        RUNTIME_BASELINE_DEFINITIONS_KEY: "integer",
    }


@pytest.mark.asyncio
async def test_refresh_runtime_source_state_replaces_zero_data_fundamental_channels_with_live_defaults(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "runtime-admin.db"
    _init_settings_db(db_path)
    _write_json_record(
        db_path,
        RUNTIME_SETTINGS_STORE_KEY,
        {
            "edc_base_url": {"value": "http://61.216.55.133"},
            "edc_username": {"value": "admin"},
            "edc_password": {"value": "admin"},
            "active_baseline_id": {"value": "baseline-001"},
        },
    )
    _write_json_record(
        db_path,
        RUNTIME_HOST_CHANNELS_KEY,
        [
            {"id": "2755-151", "suid": "2755", "cuid": "151", "channel_name": "A相基波實功功率", "unit": "kW"},
            {"id": "2752-129", "suid": "2752", "cuid": "129", "channel_name": "A相基波電壓 (或VAB)", "unit": "V"},
        ],
    )
    _write_json_record(
        db_path,
        RUNTIME_CHANNEL_ROLE_BINDINGS_KEY,
        {
            "dashboard_primary": "2755-151",
            "dashboard_secondary": "2752-129",
            "live_heat_inference": "2755-151",
        },
    )
    _write_json_record(
        db_path,
        RUNTIME_BASELINE_DEFINITIONS_KEY,
        {
            "def-001": {
                "id": "def-001",
                "metrics": [
                    {"id": "metric-001", "name": "功率", "unit": "kW", "edc_channel_id": "2755-151"},
                    {"id": "metric-002", "name": "电压", "unit": "V", "edc_channel_id": "2752-129"},
                    {"id": "metric-003", "name": "炉压", "unit": "MPa", "edc_channel_id": "2752-242"},
                ],
            }
        },
    )

    class _FakeLivePreferEDCClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeLivePreferEDCClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def get_all_sensor_list(self) -> list[dict[str, object]]:
            return [
                {
                    "uid": "2755",
                    "channelList": [
                        {"cuid": "151", "chnName": "A相基波實功功率", "chnDim": "kW", "status": "1"},
                        {"cuid": "205", "chnName": "總有功功率", "chnDim": "kW", "status": "1"},
                    ],
                },
                {
                    "uid": "2752",
                    "channelList": [
                        {"cuid": "129", "chnName": "A相基波電壓 (或VAB)", "chnDim": "V", "status": "1"},
                        {"cuid": "128", "chnName": "A相電壓 (或VAB)", "chnDim": "V", "status": "1"},
                        {"cuid": "242", "chnName": "A相電壓總諧波含有率", "chnDim": "--", "status": "1"},
                    ],
                },
            ]

        async def get_local_datas(
            self,
            *,
            suid: str,
            cuid: str,
            start_time: datetime,
            end_time: datetime,
        ) -> list[dict[str, float | int]]:
            _ = (start_time, end_time)
            if (suid, cuid) in {("2755", "205"), ("2752", "128")}:
                return [{"timestamp": 1774878050195, "value": 1.0}]
            return []

    monkeypatch.setattr("src.runtime_state_admin.EDCClient", _FakeLivePreferEDCClient)

    await refresh_runtime_source_state(db_path)

    selected_channels = _read_json_record(db_path, RUNTIME_HOST_CHANNELS_KEY)
    role_bindings = _read_json_record(db_path, RUNTIME_CHANNEL_ROLE_BINDINGS_KEY)
    definitions = _read_json_record(db_path, RUNTIME_BASELINE_DEFINITIONS_KEY)

    assert [item["id"] for item in selected_channels[:2]] == ["2755-205", "2752-128"]
    assert role_bindings == {
        "dashboard_primary": "2755-205",
        "dashboard_secondary": "2752-128",
        "live_heat_inference": "2755-205",
    }
    assert [
        metric["edc_channel_id"]
        for metric in definitions["def-001"]["metrics"]
    ] == ["2755-205", "2752-128", None]


@pytest.mark.asyncio
async def test_refresh_runtime_source_state_skips_flat_zero_power_channels(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "runtime-admin.db"
    _init_settings_db(db_path)
    _write_json_record(
        db_path,
        RUNTIME_SETTINGS_STORE_KEY,
        {
            "edc_base_url": {"value": "http://61.216.55.133"},
            "edc_username": {"value": "admin"},
            "edc_password": {"value": "admin"},
        },
    )

    class _FakeZeroPowerEDCClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeZeroPowerEDCClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def get_all_sensor_list(self) -> list[dict[str, object]]:
            return [
                {
                    "uid": "2751",
                    "sensorNickName": "推板式連續爐電力",
                    "channelList": [
                        {"cuid": "205", "chnName": "總有功功率", "chnDim": "kW", "status": "1"},
                        {"cuid": "128", "chnName": "A相電壓 (或VAB)", "chnDim": "V", "status": "1"},
                    ],
                },
                {
                    "uid": "2702",
                    "sensorNickName": "SSTW 高壓側總電力",
                    "channelList": [
                        {"cuid": "205", "chnName": "總有功功率", "chnDim": "kW", "status": "1"},
                        {"cuid": "128", "chnName": "A相電壓 (或VAB)", "chnDim": "V", "status": "1"},
                    ],
                },
            ]

        async def get_local_datas(
            self,
            *,
            suid: str,
            cuid: str,
            start_time: datetime,
            end_time: datetime,
        ) -> list[dict[str, float | int]]:
            _ = (start_time, end_time)
            if (suid, cuid) == ("2751", "205"):
                return [
                    {"timestamp": 1774878050195 + index * 60_000, "value": 0.0}
                    for index in range(12)
                ]
            if (suid, cuid) == ("2702", "205"):
                return [
                    {"timestamp": 1774878050195 + index * 60_000, "value": 60.0 + index}
                    for index in range(12)
                ]
            if cuid == "128":
                return [{"timestamp": 1774878050195, "value": 220.0}]
            return []

    monkeypatch.setattr("src.runtime_state_admin.EDCClient", _FakeZeroPowerEDCClient)

    await refresh_runtime_source_state(db_path)

    selected_channels = _read_json_record(db_path, RUNTIME_HOST_CHANNELS_KEY)
    role_bindings = _read_json_record(db_path, RUNTIME_CHANNEL_ROLE_BINDINGS_KEY)

    assert [item["id"] for item in selected_channels[:2]] == ["2702-205", "2751-128"]
    assert role_bindings == {
        "dashboard_primary": "2702-205",
        "dashboard_secondary": "2751-128",
        "live_heat_inference": "2702-205",
    }


def test_factory_reset_runtime_state_deletes_all_runtime_rows(tmp_path) -> None:
    db_path = tmp_path / "runtime-admin.db"
    _init_settings_db(db_path)
    for key in _SECTION_TO_KEY.values():
        _write_json_record(db_path, key, {"seeded": key})

    factory_reset_runtime_state(db_path)

    connection = sqlite3.connect(db_path)
    try:
        remaining = connection.execute("select key from settings").fetchall()
    finally:
        connection.close()

    assert remaining == []


def test_factory_reset_runtime_state_deletes_formal_tables(tmp_path) -> None:
    db_path = tmp_path / "runtime-admin.db"
    _init_settings_db(db_path)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("insert into baseline_definitions (id) values ('def-001')")
        connection.execute(
            "insert into baseline_definition_metrics (definition_id, item) values ('def-001', '001')"
        )
        connection.execute("insert into baselines (definition_id, item) values ('def-001', '001')")
        connection.execute("insert into heats (id, heat_no) values ('heat-001', 'H001')")
        connection.execute(
            "insert into metric_series (owner_key, item) values ('def-001:001', '001')"
        )
        connection.execute("insert into tasks (id, heat_id) values ('task-001', 'heat-001')")
        connection.commit()
    finally:
        connection.close()

    factory_reset_runtime_state(db_path)

    connection = sqlite3.connect(db_path)
    try:
        remaining_counts = {
            table_name: connection.execute(f"select count(*) from {table_name}").fetchone()[0]
            for table_name in (
                "baseline_definitions",
                "baseline_definition_metrics",
                "baselines",
                "heats",
                "metric_series",
                "tasks",
            )
        }
    finally:
        connection.close()

    assert remaining_counts == {
        "baseline_definitions": 0,
        "baseline_definition_metrics": 0,
        "baselines": 0,
        "heats": 0,
        "metric_series": 0,
        "tasks": 0,
    }


def test_factory_reset_runtime_state_recreates_current_schema_from_stale_db(tmp_path) -> None:
    db_path = tmp_path / "runtime-admin.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            create table settings (
                key text primary key,
                value text not null,
                description text,
                updated_at text
            )
            """
        )
        connection.execute(
            """
            create table baselines (
                definition_id text not null,
                item text not null,
                source_heat_id text not null,
                primary key (definition_id, item)
            )
            """
        )
        connection.execute(
            """
            insert into baselines (definition_id, item, source_heat_id)
            values ('def-001', '001', 'heat-001')
            """
        )
        connection.commit()
    finally:
        connection.close()

    factory_reset_runtime_state(db_path)

    settings_columns = {row["name"]: row for row in _table_info(db_path, "settings")}
    baselines_columns = {row["name"]: row for row in _table_info(db_path, "baselines")}

    assert settings_columns["updated_at"]["type"] == "BIGINT"
    assert "selected_start_time" in baselines_columns
    assert "selected_end_time" in baselines_columns
    assert baselines_columns["source_heat_id"]["notnull"] == 0
