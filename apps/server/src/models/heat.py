"""炉次业务模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .task import Task


class Heat(Base):
    """正式历史炉次主表。"""

    __tablename__ = "heats"
    __table_args__ = (
        Index("idx_heats_start_time", "start_time"),
        Index("idx_heats_end_time", "end_time"),
        Index("idx_heats_furnace_time", "furnace_id", "start_time"),
        Index(
            "idx_heats_baseline_binding",
            "baseline_definition_id",
            "baseline_item",
            "start_time",
        ),
        Index("idx_heats_status", "status", "start_time"),
        Index("idx_heats_deviation_status", "deviation_status", "start_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    heat_no: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="炉次编号"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="炉次备注")
    furnace_id: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="炉号/设备ID")
    start_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="炉次真实开始时间"
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="炉次真实结束时间"
    )
    context_start_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="上下文窗口开始时间"
    )
    context_end_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="上下文窗口结束时间"
    )
    sealed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="固化入库时间"
    )
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False, comment="来源类型")
    baseline_definition_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, comment="绑定的基线定义ID"
    )
    baseline_item: Mapped[str | None] = mapped_column(
        String(3), nullable=True, comment="绑定的基线版本项"
    )
    baseline_effective_from_snapshot: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="绑定时的基线生效时间快照"
    )
    deviation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="偏离度状态"
    )
    deviation_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="最大偏离度"
    )
    avg_deviation_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="平均偏离度"
    )
    deviation_details_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="偏离详情JSON"
    )
    time_offset_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="时间偏移比例"
    )
    mismatch_duration_minutes: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="连续不一致时长"
    )
    cut_reason: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="切割原因")
    cut_status: Mapped[str] = mapped_column(String(30), nullable=False, comment="切割状态")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="炉次状态")
    created_by: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="创建人")
    updated_by: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="更新人")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="更新时间",
    )

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="heat")

    def __repr__(self) -> str:
        return f"<Heat(id={self.id}, heat_no={self.heat_no}, status={self.status})>"
