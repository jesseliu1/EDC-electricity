"""正式基线主数据 API 测试。"""

import pytest

from src.api.heats import _HEAT_STORE
from src.time_utils import to_timestamp_ms


@pytest.mark.asyncio
async def test_definition_crud_flows_through_formal_tables(client) -> None:
    create_resp = await client.post(
        "/api/baseline-definitions",
        json={
            "definition_name": "正式定义 A",
            "description": "测试定义",
            "expected_duration_minutes": 30,
            "metrics": [
                {
                    "name": "总有功功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "sort_order": 1,
                    "edc_channel_id": "2349-199",
                }
            ],
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["definition_name"] == "正式定义 A"
    assert created["metrics"][0]["id"] == "001"

    definition_id = created["id"]

    list_resp = await client.get("/api/baseline-definitions")
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["total"] >= 1
    assert any(item["id"] == definition_id for item in payload["items"])

    metric_update_resp = await client.patch(
        f"/api/baseline-definitions/{definition_id}/metrics/001",
        json={"color": "#67C23A"},
    )
    assert metric_update_resp.status_code == 200
    assert metric_update_resp.json()["metrics"][0]["color"] == "#67C23A"

    disable_resp = await client.post(f"/api/baseline-definitions/{definition_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"

    enable_resp = await client.post(f"/api/baseline-definitions/{definition_id}/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_baseline_version_crud_flows_through_formal_tables(client, monkeypatch) -> None:
    async def fake_load_preview_curves_for_selection(
        *, definition_id, selected_start_time, selected_end_time
    ):
        return [
            {
                "metric_id": "001",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#409EFF",
                "points": [
                    {"timestamp": to_timestamp_ms(selected_start_time), "value": 401.0},
                    {"timestamp": to_timestamp_ms(selected_end_time), "value": 402.0},
                ],
            }
        ]

    monkeypatch.setattr(
        "src.api.baselines._load_preview_curves_for_selection",
        fake_load_preview_curves_for_selection,
    )

    definition_resp = await client.post(
        "/api/baseline-definitions",
        json={
            "definition_name": "正式定义 B",
            "description": "测试基线版本",
            "expected_duration_minutes": 30,
            "metrics": [
                {
                    "name": "总有功功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "sort_order": 1,
                    "edc_channel_id": "2349-199",
                }
            ],
        },
    )
    assert definition_resp.status_code == 201
    definition_id = definition_resp.json()["id"]

    heat_id = next(iter(_HEAT_STORE.keys()))
    heat_item = _HEAT_STORE[heat_id]
    create_resp = await client.post(
        "/api/baselines",
        json={
            "name": "正式基线 V1",
            "description": "版本测试",
            "definition_id": definition_id,
            "source_heat_id": heat_id,
            "selected_start_time": to_timestamp_ms(heat_item["start_time"]),
            "selected_end_time": to_timestamp_ms(heat_item["end_time"]),
            "tolerance_percent": 15.0,
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["id"] == f"{definition_id}:001"
    assert created["version"] == 1
    assert created["status"] == "draft"

    baseline_id = created["id"]

    publish_resp = await client.post(f"/api/baselines/{baseline_id}/publish")
    assert publish_resp.status_code == 200
    assert publish_resp.json()["status"] == "published"

    activate_resp = await client.post(f"/api/baselines/{baseline_id}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["id"] == baseline_id

    active_resp = await client.get("/api/baselines/active")
    assert active_resp.status_code == 200
    assert active_resp.json()["id"] == baseline_id

    disable_resp = await client.post(f"/api/baselines/{baseline_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_baseline_create_allows_blank_source_heat_id(client, monkeypatch) -> None:
    async def fake_load_preview_curves_for_selection(
        *, definition_id, selected_start_time, selected_end_time
    ):
        return [
            {
                "metric_id": "001",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#409EFF",
                "points": [
                    {"timestamp": to_timestamp_ms(selected_start_time), "value": 401.0},
                    {"timestamp": to_timestamp_ms(selected_end_time), "value": 402.0},
                ],
            }
        ]

    monkeypatch.setattr(
        "src.api.baselines._load_preview_curves_for_selection",
        fake_load_preview_curves_for_selection,
    )

    heat_item = _HEAT_STORE["heat-001"]
    create_resp = await client.post(
        "/api/baselines",
        json={
            "name": "全天选点基线",
            "description": "不绑定来源炉次",
            "definition_id": "def-001",
            "selected_start_time": to_timestamp_ms(heat_item["start_time"]),
            "selected_end_time": to_timestamp_ms(heat_item["end_time"]),
            "tolerance_percent": 15.0,
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["source_heat_id"] is None

    detail_resp = await client.get(f"/api/baselines/{created['id']}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["source_heat_id"] is None


@pytest.mark.asyncio
async def test_created_baseline_persists_metric_series_and_reads_from_formal_db(
    client, monkeypatch
) -> None:
    async def fake_load_preview_curves_for_selection(
        *, definition_id, selected_start_time, selected_end_time
    ):
        return [
            {
                "metric_id": "001",
                "metric_name": "总有功功率",
                "unit": "kW",
                "color": "#409EFF",
                "points": [
                    {"timestamp": to_timestamp_ms(selected_start_time), "value": 401.0},
                    {"timestamp": to_timestamp_ms(selected_end_time), "value": 402.0},
                ],
            },
            {
                "metric_id": "002",
                "metric_name": "A相电压",
                "unit": "V",
                "color": "#67C23A",
                "points": [
                    {"timestamp": to_timestamp_ms(selected_start_time), "value": 221.0},
                    {"timestamp": to_timestamp_ms(selected_end_time), "value": 222.0},
                ],
            },
        ]

    monkeypatch.setattr(
        "src.api.baselines._load_preview_curves_for_selection",
        fake_load_preview_curves_for_selection,
    )

    definition_resp = await client.post(
        "/api/baseline-definitions",
        json={
            "definition_name": "正式定义 C",
            "description": "测试基线指标值",
            "expected_duration_minutes": 30,
            "metrics": [
                {
                    "name": "总有功功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "sort_order": 1,
                    "edc_channel_id": "2349-199",
                },
                {
                    "name": "A相电压",
                    "unit": "V",
                    "color": "#67C23A",
                    "sort_order": 2,
                    "edc_channel_id": "2349-128",
                },
            ],
        },
    )
    assert definition_resp.status_code == 201
    definition_id = definition_resp.json()["id"]

    heat_id = next(iter(_HEAT_STORE.keys()))
    heat_item = _HEAT_STORE[heat_id]
    create_resp = await client.post(
        "/api/baselines",
        json={
            "name": "正式基线 V2",
            "description": "版本测试",
            "definition_id": definition_id,
            "source_heat_id": heat_id,
            "selected_start_time": to_timestamp_ms(heat_item["start_time"]),
            "selected_end_time": to_timestamp_ms(heat_item["end_time"]),
            "tolerance_percent": 15.0,
        },
    )
    assert create_resp.status_code == 201
    baseline_id = create_resp.json()["id"]

    detail_resp = await client.get(f"/api/baselines/{baseline_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["curve_source"] == "formal_db"
    assert len(detail["curves_data"]) >= 2
    assert len(detail["power_curve"]) > 0
