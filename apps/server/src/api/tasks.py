"""任务 API 路由"""

from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..schemas import (
    MessageResponse,
    TaskCompleteRequest,
    TaskCreate,
    TaskDetailResponse,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Literal["pending", "in_progress", "completed", "cancelled"] | None = Query(
        default=None, description="状态筛选"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> TaskListResponse:
    """获取任务列表

    支持按状态筛选和分页。
    """
    # TODO: 实现真实逻辑，从数据库查询
    now = datetime.now()
    items = []
    statuses = ["pending", "in_progress", "completed"]
    for i in range(page_size):
        task_status = statuses[i % 3]
        if status and task_status != status:
            continue
        items.append(
            TaskResponse(
                id=f"task-{i + 1:03d}",
                task_no=f"T{now.strftime('%Y%m%d')}-{i + 1:03d}",
                heat_id=f"heat-{i + 1:03d}",
                deviation_percent=15.5 + i * 2,
                cause_analysis="温度波动导致功率异常" if task_status != "pending" else None,
                improvement="调整加热曲线斜率" if task_status == "completed" else None,
                prevention="增加温度监控频率" if task_status == "completed" else None,
                status=task_status,
                created_at=now - timedelta(days=i),
                updated_at=now - timedelta(hours=i),
                completed_at=now if task_status == "completed" else None,
            )
        )

    return TaskListResponse(
        items=items[:page_size],
        total=30,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str) -> TaskDetailResponse:
    """获取任务详情"""
    # TODO: 实现真实逻辑
    now = datetime.now()
    return TaskDetailResponse(
        id=task_id,
        task_no=f"T{now.strftime('%Y%m%d')}-001",
        heat_id="heat-001",
        deviation_percent=18.5,
        cause_analysis="温度波动导致功率异常",
        improvement="调整加热曲线斜率",
        prevention="增加温度监控频率",
        status="in_progress",
        created_at=now - timedelta(days=1),
        updated_at=now,
        completed_at=None,
        deviation_snapshot={
            "max_deviation": 22.3,
            "avg_deviation": 8.5,
            "deviation_ranges": [
                {"start": 20000, "end": 35000, "deviation": 18.5},
                {"start": 60000, "end": 75000, "deviation": 22.3},
            ],
        },
        heat_no="H20240101-001",
    )


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(data: TaskCreate) -> TaskResponse:
    """创建纠偏任务

    从炉次创建纠偏任务单。
    """
    # TODO: 实现真实逻辑
    now = datetime.now()
    return TaskResponse(
        id=str(uuid4()),
        task_no=f"T{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}",
        heat_id=data.heat_id,
        deviation_percent=18.5,  # 从炉次获取
        cause_analysis=None,
        improvement=None,
        prevention=None,
        status="pending",
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, data: TaskUpdate) -> TaskResponse:
    """更新任务

    更新原因分析、改善方法、预防对策等内容。
    """
    # TODO: 实现真实逻辑
    now = datetime.now()
    return TaskResponse(
        id=task_id,
        task_no=f"T{now.strftime('%Y%m%d')}-001",
        heat_id="heat-001",
        deviation_percent=18.5,
        cause_analysis=data.cause_analysis or "温度波动导致功率异常",
        improvement=data.improvement,
        prevention=data.prevention,
        status="in_progress",
        created_at=now - timedelta(days=1),
        updated_at=now,
        completed_at=None,
    )


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: str, data: TaskCompleteRequest) -> TaskResponse:
    """完成任务

    提交完整的纠偏报告并完成任务。
    """
    # TODO: 实现真实逻辑
    now = datetime.now()
    return TaskResponse(
        id=task_id,
        task_no=f"T{now.strftime('%Y%m%d')}-001",
        heat_id="heat-001",
        deviation_percent=18.5,
        cause_analysis=data.cause_analysis,
        improvement=data.improvement,
        prevention=data.prevention,
        status="completed",
        created_at=now - timedelta(days=1),
        updated_at=now,
        completed_at=now,
    )


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str) -> TaskResponse:
    """取消任务"""
    # TODO: 实现真实逻辑
    now = datetime.now()
    return TaskResponse(
        id=task_id,
        task_no=f"T{now.strftime('%Y%m%d')}-001",
        heat_id="heat-001",
        deviation_percent=18.5,
        cause_analysis=None,
        improvement=None,
        prevention=None,
        status="cancelled",
        created_at=now - timedelta(days=1),
        updated_at=now,
        completed_at=None,
    )


@router.get("/{task_id}/pdf")
async def export_task_pdf(task_id: str) -> StreamingResponse:
    """导出任务 PDF

    生成纠偏任务单 PDF 文件。
    """
    # TODO: 实现真实逻辑，使用 WeasyPrint 生成 PDF
    # 暂时返回占位响应
    raise HTTPException(status_code=501, detail="PDF 导出功能尚未实现")
