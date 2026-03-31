"""任务 API 路由。"""

from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..request_mode import is_showtime_mode
from ..schemas import (
    TaskCompleteRequest,
    TaskCreate,
    TaskDetailResponse,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _now() -> datetime:
    return datetime.now()


def _seed_tasks() -> dict[str, dict[str, Any]]:
    seeded: dict[str, dict[str, Any]] = {}
    now = _now()
    status_cycle = ["pending", "in_progress", "completed", "cancelled"]
    for idx in range(36):
        task_id = f"task-{idx + 1:03d}"
        status = status_cycle[idx % len(status_cycle)]
        created = now - timedelta(days=idx)
        updated = created + timedelta(hours=idx % 8)
        completed_at = updated if status == "completed" else None
        seeded[task_id] = {
            "id": task_id,
            "task_no": f"T{now.strftime('%Y%m%d')}-{idx + 1:03d}",
            "heat_id": f"heat-{idx + 1:03d}",
            "heat_no": f"H{now.strftime('%Y%m%d')}-{idx + 1:03d}",
            "deviation_percent": round(8 + (idx % 9) * 1.9, 3),
            "deviation_snapshot": {
                "max_deviation": round(12 + (idx % 7) * 2.1, 3),
                "avg_deviation": round(5 + (idx % 6) * 1.2, 3),
                "deviation_ranges": [
                    {"start": 20000 + idx * 80, "end": 26000 + idx * 80, "deviation": 16.5}
                ],
            },
            "cause_analysis": "温度波动导致功率异常" if status != "pending" else None,
            "improvement": "调整加热曲线斜率" if status in {"in_progress", "completed"} else None,
            "prevention": "提高采样频率并监控温度" if status == "completed" else None,
            "status": status,
            "created_at": created,
            "updated_at": updated,
            "completed_at": completed_at,
        }
    return seeded


_TASK_STORE: dict[str, dict[str, Any]] = {}
_SHOWTIME_TASK_STORE: dict[str, dict[str, Any]] = _seed_tasks()


def _list_task_store() -> dict[str, dict[str, Any]]:
    return _SHOWTIME_TASK_STORE if is_showtime_mode() else _TASK_STORE


def _to_task_response(item: dict[str, Any]) -> TaskResponse:
    return TaskResponse(
        id=item["id"],
        task_no=item["task_no"],
        heat_id=item["heat_id"],
        deviation_percent=item["deviation_percent"],
        cause_analysis=item["cause_analysis"],
        improvement=item["improvement"],
        prevention=item["prevention"],
        status=item["status"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        completed_at=item["completed_at"],
    )


def _to_task_detail(item: dict[str, Any]) -> TaskDetailResponse:
    return TaskDetailResponse(
        **_to_task_response(item).model_dump(),
        deviation_snapshot=item["deviation_snapshot"],
        heat_no=item["heat_no"],
    )


def _get_or_404(task_id: str) -> dict[str, Any]:
    item = _list_task_store().get(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="任务不存在")
    return item


async def _persist_tasks_if_needed() -> None:
    if is_showtime_mode():
        return
    from ..runtime_state import persist_runtime_state

    await persist_runtime_state("tasks")


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Literal["pending", "in_progress", "completed", "cancelled"] | None = Query(
        default=None, description="状态筛选"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> TaskListResponse:
    """获取任务列表。"""
    items = list(_list_task_store().values())
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    if status:
        items = [item for item in items if item["status"] == status]

    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged = items[start_idx:end_idx]

    return TaskListResponse(
        items=[_to_task_response(item) for item in paged],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str) -> TaskDetailResponse:
    """获取任务详情。"""
    return _to_task_detail(_get_or_404(task_id))


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(data: TaskCreate) -> TaskResponse:
    """创建纠偏任务。"""
    from .heats import _build_heat_list_view, _get_or_404 as _get_heat_or_404

    now = _now()
    if data.heat_no:
        heat_item = {
            "heat_no": data.heat_no,
            "deviation_percent": data.deviation_percent,
            "avg_deviation_percent": data.avg_deviation_percent,
            "time_offset_percent": data.time_offset_percent,
            "mismatch_duration_minutes": data.mismatch_duration_minutes,
        }
    else:
        heat_item = _build_heat_list_view(await _get_heat_or_404(data.heat_id))
    task_id = f"task-{uuid4()}"
    item = {
        "id": task_id,
        "task_no": f"T{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}",
        "heat_id": data.heat_id,
        "heat_no": heat_item["heat_no"],
        "deviation_percent": heat_item.get("deviation_percent"),
        "deviation_snapshot": {
            "max_deviation": heat_item.get("deviation_percent"),
            "avg_deviation": heat_item.get("avg_deviation_percent"),
            "deviation_ranges": [],
            "time_offset_percent": heat_item.get("time_offset_percent"),
            "mismatch_duration_minutes": heat_item.get("mismatch_duration_minutes"),
        },
        "cause_analysis": None,
        "improvement": None,
        "prevention": None,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    _list_task_store()[task_id] = item
    await _persist_tasks_if_needed()
    return _to_task_response(item)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, data: TaskUpdate) -> TaskResponse:
    """更新任务文本内容。"""
    item = _get_or_404(task_id)
    if item["status"] in {"completed", "cancelled"}:
        raise HTTPException(status_code=400, detail="已完成或已取消任务不可编辑")

    if data.cause_analysis is not None:
        item["cause_analysis"] = data.cause_analysis
    if data.improvement is not None:
        item["improvement"] = data.improvement
    if data.prevention is not None:
        item["prevention"] = data.prevention

    if item["status"] == "pending" and any(
        text for text in [item["cause_analysis"], item["improvement"], item["prevention"]]
    ):
        item["status"] = "in_progress"

    item["updated_at"] = _now()
    await _persist_tasks_if_needed()
    return _to_task_response(item)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: str, data: TaskCompleteRequest) -> TaskResponse:
    """完成任务。"""
    item = _get_or_404(task_id)
    if item["status"] == "cancelled":
        raise HTTPException(status_code=400, detail="已取消任务不可完成")

    now = _now()
    item["cause_analysis"] = data.cause_analysis
    item["improvement"] = data.improvement
    item["prevention"] = data.prevention
    item["status"] = "completed"
    item["updated_at"] = now
    item["completed_at"] = now
    await _persist_tasks_if_needed()
    return _to_task_response(item)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str) -> TaskResponse:
    """取消任务。"""
    item = _get_or_404(task_id)
    if item["status"] == "completed":
        raise HTTPException(status_code=400, detail="已完成任务不可取消")

    item["status"] = "cancelled"
    item["updated_at"] = _now()
    await _persist_tasks_if_needed()
    return _to_task_response(item)


@router.get("/{task_id}/pdf")
async def export_task_pdf(task_id: str) -> StreamingResponse:
    """导出任务 PDF（MVP 返回轻量 PDF 占位）。"""
    item = _get_or_404(task_id)
    content = (
        "%PDF-1.4\n"
        "1 0 obj<<>>endobj\n"
        "2 0 obj<< /Type /Catalog /Pages 3 0 R >>endobj\n"
        "3 0 obj<< /Type /Pages /Kids [4 0 R] /Count 1 >>endobj\n"
        "4 0 obj<< /Type /Page /Parent 3 0 R /MediaBox [0 0 595 842] /Contents 5 0 R >>endobj\n"
        f"5 0 obj<< /Length 58 >>stream\nBT /F1 12 Tf 50 780 Td (Task: {item['task_no']}) Tj ET\nendstream endobj\n"
        "xref\n0 6\n0000000000 65535 f\n"
        "trailer<< /Root 2 0 R /Size 6 >>\nstartxref\n0\n%%EOF"
    ).encode("latin-1", errors="ignore")

    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={item['task_no']}.pdf"},
    )
