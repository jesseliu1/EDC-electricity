"""指标值模型。"""

from datetime import datetime

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db_types import TimestampMsType
from ..database import Base
from ..time_utils import utc_now


class MetricSeries(Base):
    """基线或炉次的指标值表。"""

    __tablename__ = "metric_series"
    __table_args__ = (
        Index("idx_metric_series_owner_type", "owner_type", "owner_key"),
        Index("idx_metric_series_definition", "definition_id"),
        Index("idx_metric_series_metric_key", "metric_key"),
    )

    owner_key: Mapped[str] = mapped_column(String(80), primary_key=True, comment="所属对象键")
    item: Mapped[str] = mapped_column(String(3), primary_key=True, comment="指标项号")
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="所属对象类型 baseline/heat"
    )
    definition_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, comment="所属基线定义ID"
    )
    item_kind: Mapped[str] = mapped_column(
        String(20), default="metric_item", nullable=False, comment="item 语义类型"
    )
    metric_key: Mapped[str] = mapped_column(String(50), nullable=False, comment="指标业务键")
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="指标名称")
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="单位")
    color: Mapped[str] = mapped_column(String(20), nullable=False, comment="图表颜色")
    sort_order: Mapped[int] = mapped_column(nullable=False, comment="展示顺序")
    source_channel_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="通道ID快照"
    )
    source_channel_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="通道名称快照"
    )
    source_channel_label: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="通道标签快照"
    )
    series_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="指标完整窗口数据JSON"
    )
    stat_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="统计信息JSON")
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
        return f"<MetricSeries(owner_key={self.owner_key}, item={self.item})>"
