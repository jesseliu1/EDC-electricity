"""炉次 API 测试。"""

import pytest

from src.schemas.common import CurvePoint


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
async def test_heat_compare_prefers_edc_curves_when_available(client, monkeypatch) -> None:
    list_resp = await client.get("/api/heats", params={"page_size": 20})
    heat_id = next(
        item["id"] for item in list_resp.json()["items"] if item.get("baseline_id") is not None
    )

    async def fake_load_metric_current_curves_from_edc(**_kwargs):
        return {
            "metric-001": [
                CurvePoint(timestamp=1000, value=501.0),
                CurvePoint(timestamp=2000, value=502.0),
            ],
            "metric-002": [
                CurvePoint(timestamp=1000, value=331.0),
                CurvePoint(timestamp=2000, value=332.0),
            ],
        }

    monkeypatch.setattr(
        "src.api.heats._load_metric_current_curves_from_edc",
        fake_load_metric_current_curves_from_edc,
    )

    compare_resp = await client.get(f"/api/heats/{heat_id}/compare")
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    first_baseline = payload["baselines"][0]
    assert first_baseline["metric_curves"][0]["current_curve"][0]["value"] == 501.0
    assert first_baseline["metric_curves"][1]["current_curve"][1]["value"] == 332.0


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
