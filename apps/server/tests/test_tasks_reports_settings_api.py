"""任务/报表/设置 API 测试。"""

import datetime as dt

import pytest


@pytest.mark.asyncio
async def test_tasks_crud_and_pdf(client) -> None:
    list_resp = await client.get("/api/tasks", params={"page_size": 5})
    assert list_resp.status_code == 200
    first_id = list_resp.json()["items"][0]["id"]

    detail_resp = await client.get(f"/api/tasks/{first_id}")
    assert detail_resp.status_code == 200

    create_resp = await client.post("/api/tasks", json={"heat_id": "heat-001"})
    assert create_resp.status_code == 201
    created_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/tasks/{created_id}",
        json={"cause_analysis": "原因", "improvement": "改善", "prevention": "预防"},
    )
    assert update_resp.status_code == 200

    complete_resp = await client.post(
        f"/api/tasks/{created_id}/complete",
        json={"cause_analysis": "原因", "improvement": "改善", "prevention": "预防"},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    pdf_resp = await client.get(f"/api/tasks/{created_id}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_reports_list_detail_generate_pdf(client) -> None:
    list_resp = await client.get("/api/reports/daily", params={"page_size": 5})
    assert list_resp.status_code == 200
    first_date = list_resp.json()["items"][0]["date"]

    detail_resp = await client.get(f"/api/reports/daily/{first_date}")
    assert detail_resp.status_code == 200

    gen_resp = await client.post(f"/api/reports/daily/{first_date}/generate")
    assert gen_resp.status_code == 200

    pdf_resp = await client.get(f"/api/reports/daily/{first_date}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")

    future = (dt.date.today() + dt.timedelta(days=10)).isoformat()
    not_found_resp = await client.get(f"/api/reports/daily/{future}")
    assert not_found_resp.status_code == 404


@pytest.mark.asyncio
async def test_settings_get_and_update(client) -> None:
    get_resp = await client.get("/api/settings")
    assert get_resp.status_code == 200

    patch_resp = await client.patch(
        "/api/settings", json={"settings": {"report_generation_hour": "3"}}
    )
    assert patch_resp.status_code == 200

    tol_resp = await client.put("/api/settings/tolerance", json={"tolerance_percent": 12.5})
    assert tol_resp.status_code == 200

    edc_resp = await client.put(
        "/api/settings/edc-connection",
        json={"base_url": "http://localhost:8080", "api_key": "abc"},
    )
    assert edc_resp.status_code == 200

    test_resp = await client.post("/api/settings/edc-connection/test")
    assert test_resp.status_code == 200

    report_resp = await client.put("/api/settings/report", json={"generation_hour": 6})
    assert report_resp.status_code == 200
