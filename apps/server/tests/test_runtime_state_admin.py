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
    RUNTIME_HOST_CHANNELS_KEY,
    RUNTIME_HOST_CHANNEL_CATALOG_KEY,
    RUNTIME_HOST_CHANNEL_LAST_SYNC_KEY,
    RUNTIME_HOST_CONNECTIVITY_STATUS_KEY,
    RUNTIME_SETTINGS_STORE_KEY,
    factory_reset_runtime_state,
    refresh_runtime_source_state,
)


def _init_settings_db(db_path: Path) -> None:
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
            values (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (key, encoded, f"test:{key}"),
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


class _FakeEDCClient:
    def __init__(self, **_kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeEDCClient":
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
    assert last_sync["__type__"] == "datetime"
    assert [
        metric["edc_channel_id"]
        for metric in definitions["def-001"]["metrics"]
    ] == [
        "2752-199",
        "2752-128",
        "300000000000000000001-128",
        "2755-128",
    ]


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

        async def __aenter__(self) -> "_FakeLivePreferEDCClient":
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
