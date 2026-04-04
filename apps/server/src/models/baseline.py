"""基线主数据与基线版本模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class BaselineDefinition(Base):
    """基线定义主表。"""

    __tablename__ = "baseline_definitions"
    __table_args__ = (
        Index("idx_baseline_definitions_status", "status"),
        Index("idx_baseline_definitions_name", "definition_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    definition_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="基线定义名称"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="基线定义说明")
    expected_duration_minutes: Mapped[int] = mapped_column(
        nullable=False, comment="预期炉次时长"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="定义状态")
    created_by: Mapped[str] = mapped_column(String(50), nullable=False, comment="创建人")
    updated_by: Mapped[str] = mapped_column(String(50), nullable=False, comment="更新人")
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

    def __repr__(self) -> str:
        return f"<BaselineDefinition(id={self.id}, name={self.definition_name})>"


class BaselineDefinitionMetric(Base):
    """定义下的指标模板表。"""

    __tablename__ = "baseline_definition_metrics"
    __table_args__ = (
        Index("idx_definition_metrics_metric_key", "metric_key"),
        Index("idx_definition_metrics_sort", "definition_id", "sort_order"),
        Index("idx_definition_metrics_channel", "edc_channel_id"),
    )

    definition_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("baseline_definitions.id"),
        primary_key=True,
        comment="所属基线定义ID",
    )
    item: Mapped[str] = mapped_column(String(3), primary_key=True, comment="指标项号")
    item_kind: Mapped[str] = mapped_column(
        String(20), default="metric_item", nullable=False, comment="item 语义类型"
    )
    metric_key: Mapped[str] = mapped_column(String(50), nullable=False, comment="指标业务键")
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="指标名称")
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="单位")
    color: Mapped[str] = mapped_column(String(20), nullable=False, comment="图表颜色")
    sort_order: Mapped[int] = mapped_column(nullable=False, comment="展示顺序")
    edc_channel_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="当前绑定通道ID"
    )
    source_channel_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="通道名称快照"
    )
    source_channel_label: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="通道显示标签快照"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否启用"
    )
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

    def __repr__(self) -> str:
        return f"<BaselineDefinitionMetric(definition_id={self.definition_id}, item={self.item})>"


class Baseline(Base):
    """基线版本表。"""

    __tablename__ = "baselines"
    __table_args__ = (
        Index("idx_baselines_effective_from", "effective_from"),
        Index("idx_baselines_status", "status"),
        Index("idx_baselines_source_heat", "source_heat_id"),
        Index("idx_baselines_definition_published", "definition_id", "status", "published_at"),
    )

    definition_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("baseline_definitions.id"),
        primary_key=True,
        comment="所属基线定义ID",
    )
    item: Mapped[str] = mapped_column(String(3), primary_key=True, comment="基线版本项")
    item_kind: Mapped[str] = mapped_column(
        String(20), default="baseline_version", nullable=False, comment="item 语义类型"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="基线名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="基线描述")
    status: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="基线状态")
    source_heat_id: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="生成该基线的来源炉次"
    )
    selected_start_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="选区开始时间"
    )
    selected_end_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="选区结束时间"
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="生效时间"
    )
    tolerance_percent: Mapped[float] = mapped_column(
        Float, nullable=False, comment="容许误差百分比"
    )
    created_by: Mapped[str] = mapped_column(String(50), nullable=False, comment="创建人")
    updated_by: Mapped[str] = mapped_column(String(50), nullable=False, comment="更新人")
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
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="发布时间"
    )

    def __repr__(self) -> str:
        return f"<Baseline(definition_id={self.definition_id}, item={self.item})>"
