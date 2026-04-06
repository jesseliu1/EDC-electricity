"""炉次-黄金基线绑定模型。"""

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKeyConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db_types import TimestampMsType
from ..database import Base
from ..time_utils import utc_now


class HeatBaselineBinding(Base):
    """正式炉次与黄金基线的 1:N 绑定表。"""

    __tablename__ = "heat_baseline_bindings"
    __table_args__ = (
        ForeignKeyConstraint(["heat_id"], ["heats.id"]),
        ForeignKeyConstraint(
            ["baseline_definition_id", "baseline_item"],
            ["baselines.definition_id", "baselines.item"],
        ),
        Index("idx_heat_baseline_bindings_primary", "heat_id", "is_primary"),
        Index(
            "idx_heat_baseline_bindings_baseline",
            "baseline_definition_id",
            "baseline_item",
            "effective_from_snapshot",
        ),
        Index("idx_heat_baseline_bindings_analysis_status", "analysis_status", "updated_at"),
    )

    heat_id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="炉次ID")
    baseline_definition_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, comment="基线定义ID"
    )
    baseline_item: Mapped[str] = mapped_column(String(3), primary_key=True, comment="基线版本项")
    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否主黄金基线"
    )
    effective_from_snapshot: Mapped[datetime | None] = mapped_column(
        TimestampMsType(), nullable=True, comment="绑定时的基线生效时间快照"
    )
    tolerance_percent_snapshot: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="绑定时的基线容许误差快照"
    )
    analysis_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, comment="分析状态"
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

    def __repr__(self) -> str:
        return (
            "<HeatBaselineBinding("
            f"heat_id={self.heat_id}, "
            f"baseline_definition_id={self.baseline_definition_id}, "
            f"baseline_item={self.baseline_item}, "
            f"is_primary={self.is_primary}"
            ")>"
        )
