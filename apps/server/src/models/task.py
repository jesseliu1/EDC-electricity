"""纠偏任务模型"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .heat import Heat


class TaskStatus(enum.Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 待处理
    IN_PROGRESS = "in_progress"  # 处理中
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消


class Task(Base):
    """纠偏任务模型

    存储偏差纠偏任务单，包含原因分析、改善方法、预防对策等内容。
    """

    __tablename__ = "tasks"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 任务编号
    task_no: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="任务编号"
    )

    # 关联炉次
    heat_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("heats.id"), nullable=False, comment="关联炉次ID"
    )

    # 偏差信息（创建时快照）
    deviation_percent: Mapped[float] = mapped_column(Float, nullable=False, comment="偏差百分比")
    deviation_snapshot: Mapped[str] = mapped_column(
        Text, nullable=False, comment="偏差详情快照JSON"
    )

    # 处理内容
    cause_analysis: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原因分析")
    improvement: Mapped[str | None] = mapped_column(Text, nullable=True, comment="改善方法")
    prevention: Mapped[str | None] = mapped_column(Text, nullable=True, comment="预防对策")

    # 状态
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, comment="任务状态"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="完成时间"
    )

    # 关系
    heat: Mapped["Heat"] = relationship("Heat", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, task_no={self.task_no}, status={self.status.value})>"
