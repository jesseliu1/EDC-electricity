"""炉次 replay 任务模型。"""

from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..db_types import TimestampMsType
from ..time_utils import utc_now


class HeatReplayJob(Base):
    """历史初始化 / 重算任务。"""

    __tablename__ = "heat_replay_jobs"
    __table_args__ = (
        Index("idx_heat_replay_jobs_status", "status", "created_at"),
        Index("idx_heat_replay_jobs_channel", "channel_key", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_kind: Mapped[str] = mapped_column(String(32), nullable=False, comment="任务类型")
    status: Mapped[str] = mapped_column(String(24), nullable=False, comment="任务状态")
    anchor_time: Mapped[datetime] = mapped_column(
        TimestampMsType(), nullable=False, comment="起始时间"
    )
    end_time: Mapped[datetime] = mapped_column(
        TimestampMsType(), nullable=False, comment="结束时间"
    )
    channel_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="通道键")
    force_replace: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否强制范围替换"
    )
    cutting_config_snapshot_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="切割配置快照"
    )
    progress_cursor: Mapped[datetime | None] = mapped_column(
        TimestampMsType(), nullable=True, comment="已处理到的游标"
    )
    processed_chunk_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="已处理 chunk 数"
    )
    generated_heat_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="生成炉次数"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    created_at: Mapped[datetime] = mapped_column(
        TimestampMsType(), default=utc_now, nullable=False, comment="创建时间"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TimestampMsType(), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TimestampMsType(), nullable=True, comment="完成时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampMsType(),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        comment="更新时间",
    )
