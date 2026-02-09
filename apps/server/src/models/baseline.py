"""黄金基线模型"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .heat import Heat


class BaselineStatus(enum.Enum):
    """基线状态枚举"""

    DRAFT = "draft"  # 草稿
    PUBLISHED = "published"  # 已发布
    DISABLED = "disabled"  # 已停用


class Baseline(Base):
    """黄金基线模型

    存储生产标准基线数据，包括功率曲线、电压曲线等参考数据。
    """

    __tablename__ = "baselines"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 基本信息
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="基线名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="基线描述")

    # 关联炉次（基线来源）
    source_heat_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="来源炉次ID")

    # 曲线数据（JSON 格式存储）
    # 格式: [[timestamp_ms, value], ...]
    power_curve: Mapped[str] = mapped_column(Text, nullable=False, comment="功率曲线JSON")
    voltage_curve: Mapped[str] = mapped_column(Text, nullable=False, comment="电压曲线JSON")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True, comment="出汤温度(°C)")

    # 参数设置
    tolerance_percent: Mapped[float] = mapped_column(Float, default=15.0, comment="容许误差百分比")

    # 状态管理
    status: Mapped[BaselineStatus] = mapped_column(
        Enum(BaselineStatus), default=BaselineStatus.DRAFT, comment="状态"
    )
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="发布时间"
    )

    # 关系
    heats: Mapped[list["Heat"]] = relationship("Heat", back_populates="baseline")

    def __repr__(self) -> str:
        return f"<Baseline(id={self.id}, name={self.name}, status={self.status.value})>"
