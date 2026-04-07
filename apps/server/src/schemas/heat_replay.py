"""炉次 replay 任务模式。"""

from pydantic import BaseModel, Field

from .common import OptionalTimestampMs, TimestampMs


class HeatReplayJobCreateRequest(BaseModel):
    """创建 replay 任务请求。"""

    job_kind: str = Field(default="replay_batch", description="任务类型")
    anchor_time: TimestampMs = Field(..., description="起始时间")
    end_time: TimestampMs = Field(..., description="结束时间")
    force_replace: bool = Field(default=True, description="是否强制替换范围")


class HeatReplayJobResponse(BaseModel):
    """replay 任务响应。"""

    id: str = Field(..., description="任务ID")
    job_kind: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    anchor_time: TimestampMs = Field(..., description="起始时间")
    end_time: TimestampMs = Field(..., description="结束时间")
    channel_key: str = Field(..., description="通道键")
    force_replace: bool = Field(default=True, description="是否强制替换范围")
    progress_cursor: OptionalTimestampMs = Field(default=None, description="当前游标")
    processed_chunk_count: int = Field(default=0, description="已处理 chunk 数")
    generated_heat_count: int = Field(default=0, description="生成炉次数")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: TimestampMs = Field(..., description="创建时间")
    started_at: OptionalTimestampMs = Field(default=None, description="开始时间")
    completed_at: OptionalTimestampMs = Field(default=None, description="完成时间")
    updated_at: TimestampMs = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class HeatReplayJobListResponse(BaseModel):
    """replay 任务列表响应。"""

    items: list[HeatReplayJobResponse] = Field(default_factory=list, description="任务列表")
