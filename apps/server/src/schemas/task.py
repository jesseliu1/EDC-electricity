"""任务 Pydantic 模式"""

from pydantic import BaseModel, Field

from .common import OptionalTimestampMs, TimestampMs


class TaskCreate(BaseModel):
    """创建任务请求"""

    heat_id: str = Field(..., description="关联炉次ID")
    baseline_id: str | None = Field(default=None, description="所选基线ID")
    heat_no: str | None = Field(default=None, description="关联炉次编号快照")
    deviation_score: float | None = Field(default=None, description="偏离分数快照")
    avg_deviation_score: float | None = Field(default=None, description="平均偏离分数快照")
    abnormal_duration_minutes: float | None = Field(
        default=None, description="连续异常时长快照（分钟）"
    )


class TaskUpdate(BaseModel):
    """更新任务请求"""

    cause_analysis: str | None = Field(default=None, description="原因分析")
    improvement: str | None = Field(default=None, description="改善方法")
    prevention: str | None = Field(default=None, description="预防对策")


class TaskResponse(BaseModel):
    """任务响应"""

    id: str = Field(..., description="任务ID")
    task_no: str = Field(..., description="任务编号")
    heat_id: str = Field(..., description="关联炉次ID")
    deviation_score: float | None = Field(default=None, description="偏离分数")
    cause_analysis: str | None = Field(default=None, description="原因分析")
    improvement: str | None = Field(default=None, description="改善方法")
    prevention: str | None = Field(default=None, description="预防对策")
    status: str = Field(..., description="状态: pending/in_progress/completed/cancelled")
    created_at: TimestampMs = Field(..., description="创建时间")
    updated_at: TimestampMs = Field(..., description="更新时间")
    completed_at: OptionalTimestampMs = Field(default=None, description="完成时间")

    model_config = {"from_attributes": True}


class TaskWithHeat(TaskResponse):
    """带炉次信息的任务响应"""

    heat_no: str = Field(..., description="炉次编号")
    heat_start_time: TimestampMs = Field(..., description="炉次开始时间")
    heat_end_time: TimestampMs = Field(..., description="炉次结束时间")


class TaskListResponse(BaseModel):
    """任务列表响应"""

    items: list[TaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


class TaskDetailResponse(TaskResponse):
    """任务详情响应"""

    analysis_snapshot: dict = Field(..., description="统一分析详情快照")
    heat_no: str = Field(..., description="炉次编号")


class TaskCompleteRequest(BaseModel):
    """完成任务请求"""

    cause_analysis: str = Field(..., min_length=1, description="原因分析（必填）")
    improvement: str = Field(..., min_length=1, description="改善方法（必填）")
    prevention: str = Field(..., min_length=1, description="预防对策（必填）")
