"""炉次 API 测试。"""

from datetime import datetime, timedelta

import pytest

from src.api.baseline_definitions import _resolve_preview_window
from src.api.baselines import _resolve_baseline_time_window
from src.api.settings import _SETTINGS_STORE
from src.schemas.common import CurvePoint


def _build_live_power_points(start: datetime) -> list[CurvePoint]:
    points: list[CurvePoint] = []

    def append_block(offset_minutes: int, length_minutes: int, value: float) -> None:
        for index in range(length_minutes):
            timestamp = int(
                (start + timedelta(minutes=offset_minutes + index)).timestamp() * 1000
            )
            points.append(CurvePoint(timestamp=timestamp, value=value))

    append_block(0, 10, 42.0)
    append_block(10, 30, 124.0)
    append_block(40, 12, 46.0)
    append_block(52, 28, 129.0)
    append_block(80, 10, 38.0)
    return points


async def _pick_heat_id(client, *, require_baseline: bool = True) -> str:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    assert list_resp.status_code == 200
    return next(
        item["id"]
        for item in list_resp.json()["items"]
        if not require_baseline or item.get("baseline_id") is not None
    )


@pytest.mark.asyncio
async def test_list_heats_with_pagination(client) -> None:
    response = await client.get("/api/heats", params={"page": 1, "page_size": 10})
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["items"]) <= 10
    assert data["total"] >= len(data["items"])


@pytest.mark.asyncio
async def test_list_heats_filter_by_status(client) -> None:
    response = await client.get("/api/heats", params={"status": "abnormal", "page_size": 20})
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "abnormal" for item in data["items"])


@pytest.mark.asyncio
async def test_get_heat_not_found(client) -> None:
    response = await client.get("/api/heats/not-exists")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_heat_curve_and_compare(client) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    heat_id = next(
        item["id"] for item in list_resp.json()["items"] if item.get("baseline_id") is not None
    )

    curve_resp = await client.get(f"/api/heats/{heat_id}/curve")
    assert curve_resp.status_code == 200
    curve_data = curve_resp.json()
    assert len(curve_data["power_curve"]) > 0

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    compare_data = compare_resp.json()
    assert "deviation_ranges" in compare_data
    assert compare_data["heat"]["id"] == heat_id
    assert len(compare_data["baselines"]) > 0
    first_baseline = compare_data["baselines"][0]
    second_baseline = compare_data["baselines"][1]
    assert len(first_baseline["metric_curves"]) == 3
    assert len(second_baseline["metric_curves"]) == 4
    assert [item["metric_key"] for item in first_baseline["metric_curves"]] == [
        "power",
        "voltage",
        "temperature",
    ]
    assert [item["metric_key"] for item in second_baseline["metric_curves"]] == [
        "power",
        "voltage",
        "temperature",
        "pressure",
    ]
    assert all("source_channel_label" in item for item in first_baseline["metric_curves"])
    assert all("source_channel_name" in item for item in second_baseline["metric_curves"])


@pytest.mark.asyncio
async def test_heat_list_and_compare_follow_active_default_baseline(client) -> None:
    source_heat_id = await _pick_heat_id(client)

    create_resp = await client.post(
        "/api/baselines",
        json={
            "name": "默认黄金基线测试",
            "description": "用于验证炉次默认基线口径",
            "definition_id": "def-001",
            "source_heat_id": source_heat_id,
            "tolerance_percent": 9.5,
        },
    )
    assert create_resp.status_code == 201
    baseline_id = create_resp.json()["id"]

    publish_resp = await client.post(f"/api/baselines/{baseline_id}/publish")
    assert publish_resp.status_code == 200

    activate_resp = await client.post(f"/api/baselines/{baseline_id}/activate")
    assert activate_resp.status_code == 200

    list_resp = await client.get("/api/heats", params={"page_size": 5})
    assert list_resp.status_code == 200
    heat_item = next(item for item in list_resp.json()["items"] if item["status"] != "pending")
    assert heat_item["baseline_id"] == baseline_id
    assert heat_item["deviation_percent"] is not None

    compare_resp = await client.get(f"/api/heats/{heat_item['id']}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    assert payload["baselines"][0]["baseline"]["id"] == baseline_id
    assert any(item["baseline"]["id"] == "baseline-001" for item in payload["baselines"])


@pytest.mark.asyncio
async def test_mock_stream_endpoints_are_disabled_when_mock_dataset_is_off(client) -> None:
    list_response = await client.get("/api/heats/stream/mock")
    assert list_response.status_code == 503
    assert "mock 数据集未开启" in list_response.json()["detail"]

    ingest_response = await client.post("/api/heats/stream/mock/ingest")
    assert ingest_response.status_code == 503
    assert "mock 数据集未开启" in ingest_response.json()["detail"]


@pytest.mark.asyncio
async def test_heat_compare_prefers_edc_curves_when_available(client, monkeypatch) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    heat_id = next(
        item["id"] for item in list_resp.json()["items"] if item.get("baseline_id") is not None
    )

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 501.0
    assert first_baseline["metric_curves"][1]["current_curve"][1]["value"] == 332.0


@pytest.mark.asyncio
async def test_get_heat_curve_prefers_live_heat_curves(client, monkeypatch) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    heat_id = next(
        item["id"] for item in list_resp.json()["items"] if item.get("baseline_id") is not None
    )

    async def fake_load_heat_curves_from_edc(_item):
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)

    curve_resp = await client.get(f"/api/heats/{heat_id}/curve")
    assert curve_resp.status_code == 200
    payload = curve_resp.json()
    assert payload["power_curve"][0]["value"] == 611.0
    assert payload["voltage_curve"][1]["value"] == 352.0


@pytest.mark.asyncio
async def test_heat_compare_prefers_hydrated_baseline_metric_curves(client, monkeypatch) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    heat_id = next(
        item["id"] for item in list_resp.json()["items"] if item.get("baseline_id") is not None
    )

    async def fake_load_heat_curves_from_edc(_item):
        return None

    async def fake_hydrate_baseline_item(item):
        item["curves_data"] = [
            {
                "metric_id": "metric-001",
                "metric_name": "功率",
                "unit": "kW",
                "color": "#409EFF",
                "points": [
                    {"timestamp": 1000, "value": 701.0},
                    {"timestamp": 2000, "value": 702.0},
                ],
            },
            {
                "metric_id": "metric-002",
                "metric_name": "电压",
                "unit": "V",
                "color": "#67C23A",
                "points": [
                    {"timestamp": 1000, "value": 381.0},
                    {"timestamp": 2000, "value": 382.0},
                ],
            },
        ]
        return item

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)
    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert first_baseline["metric_curves"][0]["baseline_curve"][0]["value"] == 701.0
    assert first_baseline["metric_curves"][1]["baseline_curve"][1]["value"] == 382.0


@pytest.mark.asyncio
async def test_cutting_timeline_uses_abnormal_outcome_for_abnormal_heat(client) -> None:
    list_resp = await client.get("/api/heats", params={"status": "abnormal", "page_size": 50})
    abnormal_items = list_resp.json()["items"]
    assert abnormal_items

    target_heat = next(
        item
        for item in abnormal_items
        if item["cut_status"] in {"normal", "major_issue"}
    )
    timeline_resp = await client.get(f"/api/heats/{target_heat['id']}/cutting-timeline")
    assert timeline_resp.status_code == 200
    events = timeline_resp.json()["events"]
    assert events[-1]["title"] in {"判定异常", "触发重大事故"}


@pytest.mark.asyncio
async def test_analyze_heat_updates_status(client) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 1})
    heat_id = list_resp.json()["items"][0]["id"]

    analyze_resp = await client.post(f"/api/heats/{heat_id}/analyze", json={})
    assert analyze_resp.status_code == 200
    analyze_data = analyze_resp.json()
    assert analyze_data["heat_id"] == heat_id
    assert analyze_data["status"] in {"normal", "abnormal"}

    detail_resp = await client.get(f"/api/heats/{heat_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["status"] == analyze_data["status"]


@pytest.mark.asyncio
async def test_list_heats_prefers_live_inferred_records_when_enabled(client, monkeypatch) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        return live_points

    async def fake_hydrate_baseline_item(item):
        return item

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: ({"id": "2349-199", "suid": "2349", "cuid": "199"}, "baseline-001", 30),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)
    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._LIVE_HEAT_CACHE["expires_at"] = None
    heats_module._LIVE_HEAT_CACHE["items"] = {}

    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert all(item["record_source"] == "live_inferred" for item in payload["items"])
    assert all(item["current_curve_source"] == "live_edc" for item in payload["items"])
    assert payload["items"][0]["id"].startswith("live-heat-")


@pytest.mark.asyncio
async def test_live_inferred_heat_ids_can_resolve_preview_and_baseline_windows(
    client, monkeypatch
) -> None:
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "true"
    live_points = _build_live_power_points(datetime(2026, 3, 19, 8, 0))

    async def fake_load_live_heat_inference_power_points(_channel):
        return live_points

    monkeypatch.setattr(
        "src.api.heats._load_live_heat_inference_power_points",
        fake_load_live_heat_inference_power_points,
    )
    monkeypatch.setattr(
        "src.api.heats._resolve_live_heat_inference_context",
        lambda: ({"id": "2349-199", "suid": "2349", "cuid": "199"}, "baseline-001", 30),
    )
    monkeypatch.setattr("src.api.heats._infer_live_activity_threshold", lambda _points: 100.0)

    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    heats_module._LIVE_HEAT_CACHE["expires_at"] = None
    heats_module._LIVE_HEAT_CACHE["items"] = {}

    list_response = await client.get("/api/heats", params={"page_size": 20})
    heat_id = list_response.json()["items"][0]["id"]

    baseline_window = await _resolve_baseline_time_window({"source_heat_id": heat_id})
    preview_window = await _resolve_preview_window(heat_id)
    assert (baseline_window[1] - baseline_window[0]).total_seconds() >= 20 * 60
    assert preview_window[0].hour == 0
    assert preview_window[0].date() == baseline_window[0].date()


@pytest.mark.asyncio
async def test_list_heats_does_not_surface_mock_stream_records(client) -> None:
    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    response = await client.get("/api/heats", params={"page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert all(item["record_source"] != "mock_stream" for item in payload["items"])


@pytest.mark.asyncio
async def test_mock_stream_endpoints_use_dedicated_store(client) -> None:
    import src.api.heats as heats_module

    heats_module._HEAT_STORE.clear()
    list_response = await client.get("/api/heats")
    assert list_response.status_code == 200
    assert list_response.json()["total"] > 0

    mock_list_response = await client.get(
        "/api/heats/stream/mock",
        params={"page_size": 5, "showtime": "true"},
    )
    assert mock_list_response.status_code == 200
    mock_payload = mock_list_response.json()
    assert mock_payload["total"] > 0
    assert all(item["record_source"] == "mock_stream" for item in mock_payload["items"])

    ingest_response = await client.post("/api/heats/stream/mock/ingest?showtime=true")
    assert ingest_response.status_code == 200
    assert ingest_response.json()["record_source"] == "mock_stream"

    ordinary_after_ingest = await client.get("/api/heats")
    assert ordinary_after_ingest.status_code == 200
    assert ordinary_after_ingest.json()["total"] > 0

    ordinary_showtime = await client.get("/api/heats", params={"showtime": "true"})
    assert ordinary_showtime.status_code == 200
    assert ordinary_showtime.json()["items"][0]["record_source"] == "mock_stream"


@pytest.mark.asyncio
async def test_list_heats_does_not_hydrate_baselines(client, monkeypatch) -> None:
    async def fail_hydrate(_item):
        raise AssertionError("list_heats should not hydrate baselines")

    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fail_hydrate)

    response = await client.get("/api/heats", params={"page": 1, "page_size": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]


@pytest.mark.asyncio
async def test_heat_compare_hydrates_each_baseline_only_once(client, monkeypatch) -> None:
    hydrate_calls: list[str] = []

    async def fake_load_heat_curves_from_edc(_item):
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    async def fake_hydrate_baseline_item(item):
        hydrate_calls.append(str(item["id"]))
        if str(item["id"]) == "baseline-001":
            item["curves_data"] = [
                {
                    "metric_id": "metric-001",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "points": [
                        {"timestamp": 1000, "value": 701.0},
                        {"timestamp": 2000, "value": 702.0},
                    ],
                },
                {
                    "metric_id": "metric-002",
                    "metric_name": "电压",
                    "unit": "V",
                    "color": "#67C23A",
                    "points": [
                        {"timestamp": 1000, "value": 381.0},
                        {"timestamp": 2000, "value": 382.0},
                    ],
                },
            ]
        else:
            item["curves_data"] = [
                {
                    "metric_id": "metric-004",
                    "metric_name": "功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "points": [
                        {"timestamp": 1000, "value": 801.0},
                        {"timestamp": 2000, "value": 802.0},
                    ],
                }
            ]
        item["power_curve"] = [
            CurvePoint(timestamp=1000, value=701.0),
            CurvePoint(timestamp=2000, value=702.0),
        ]
        item["voltage_curve"] = [
            CurvePoint(timestamp=1000, value=381.0),
            CurvePoint(timestamp=2000, value=382.0),
        ]
        item["curve_source"] = "live_edc"
        return item

    async def fake_load_channel_curves_from_edc(**_kwargs):
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)
    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )

    heat_id = await _pick_heat_id(client)
    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    assert hydrate_calls.count("baseline-001") == 1
    assert hydrate_calls.count("baseline-002") == 1


@pytest.mark.asyncio
async def test_heat_compare_reuses_short_ttl_cache(client, monkeypatch) -> None:
    hydrate_calls: list[str] = []
    channel_load_calls = 0
    heat_curve_calls = 0

    async def fake_hydrate_baseline_item(item):
        hydrate_calls.append(str(item["id"]))
        item["curves_data"] = [
            {
                "metric_id": "metric-001",
                "metric_name": "功率",
                "unit": "kW",
                "color": "#409EFF",
                "points": [
                    {"timestamp": 1000, "value": 701.0},
                    {"timestamp": 2000, "value": 702.0},
                ],
            },
            {
                "metric_id": "metric-002",
                "metric_name": "电压",
                "unit": "V",
                "color": "#67C23A",
                "points": [
                    {"timestamp": 1000, "value": 381.0},
                    {"timestamp": 2000, "value": 382.0},
                ],
            },
        ]
        item["power_curve"] = [
            CurvePoint(timestamp=1000, value=701.0),
            CurvePoint(timestamp=2000, value=702.0),
        ]
        item["voltage_curve"] = [
            CurvePoint(timestamp=1000, value=381.0),
            CurvePoint(timestamp=2000, value=382.0),
        ]
        item["curve_source"] = "live_edc"
        return item

    async def fake_load_channel_curves_from_edc(**_kwargs):
        nonlocal channel_load_calls
        channel_load_calls += 1
        return {
            "2349:199": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "2349:128": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    async def fake_load_heat_curves_from_edc(_item):
        nonlocal heat_curve_calls
        heat_curve_calls += 1
        return {
            "power": [
                CurvePoint(timestamp=1000, value=611.0),
                CurvePoint(timestamp=2000, value=612.0),
            ],
            "voltage": [
                CurvePoint(timestamp=1000, value=351.0),
                CurvePoint(timestamp=2000, value=352.0),
            ],
        }

    monkeypatch.setattr("src.api.baselines._hydrate_baseline_item", fake_hydrate_baseline_item)
    monkeypatch.setattr(
        "src.api.heats._load_channel_curves_from_edc",
        fake_load_channel_curves_from_edc,
    )
    monkeypatch.setattr("src.api.heats._load_heat_curves_from_edc", fake_load_heat_curves_from_edc)

    heat_id = await _pick_heat_id(client)
    first_resp = await client.get(f"/api/heats/{heat_id}/compare")
    second_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert first_resp.json() == second_resp.json()
    assert hydrate_calls.count("baseline-001") == 1
    assert hydrate_calls.count("baseline-002") == 1
    assert channel_load_calls == 1
    assert heat_curve_calls == 0
