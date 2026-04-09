"""纠偏任务模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db_types import TimestampMsType
from ..database import Base
from ..time_utils import utc_now

if TYPE_CHECKING:
    from .heat import Heat


class Task(Base):
    """纠偏任务主表。"""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_heat", "heat_id", "created_at"),
        Index("idx_tasks_status", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_no: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="任务编号"
    )
    heat_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("heats.id"), nullable=False, comment="对应炉次ID"
    )
    baseline_definition_id_snapshot: Mapped[str | None] = mapped_column(
        String(36), nullable=True, comment="任务创建时基线定义快照"
    )
    baseline_item_snapshot: Mapped[str | None] = mapped_column(
        String(3), nullable=True, comment="任务创建时基线版本项快照"
    )
    deviation_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="任务创建时偏离分数快照"
    )
    analysis_snapshot_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="统一分析详情快照JSON"
    )
    cause_analysis: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原因分析")
    improvement: Mapped[str | None] = mapped_column(Text, nullable=True, comment="改善措施")
    prevention: Mapped[str | None] = mapped_column(Text, nullable=True, comment="预防措施")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="任务状态")
    created_at: Mapped[datetime] = mapped_column(
        TimestampMsType(), default=utc_now, nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampMsType(),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        comment="更新时间",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TimestampMsType(), nullable=True, comment="完成时间"
    )

    heat: Mapped["Heat"] = relationship("Heat", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, task_no={self.task_no}, status={self.status})>"
