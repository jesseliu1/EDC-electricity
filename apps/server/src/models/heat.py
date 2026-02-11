"""炉次模型"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .baseline import Baseline
    from .task import Task


class HeatStatus(enum.Enum):
    """炉次偏差状态枚举"""

    NORMAL = "normal"  # 正常
    ABNORMAL = "abnormal"  # 异常
    PENDING = "pending"  # 待分析


class Heat(Base):
    """炉次模型

    存储每一炉次的生产数据，包括功率曲线、电压曲线，以及与基线的偏差分析结果。
    """

    __tablename__ = "heats"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 炉次编号
    heat_no: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="炉次编号"
    )

    # 炉次描述（用户可选填）
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="炉次描述")

    # 时间范围
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="开始时间")
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="结束时间")

    # 曲线数据（JSON 格式存储）
    power_curve: Mapped[str] = mapped_column(Text, nullable=False, comment="功率曲线JSON")
    voltage_curve: Mapped[str] = mapped_column(Text, nullable=False, comment="电压曲线JSON")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True, comment="出汤温度(°C)")

    # 偏差分析结果
    baseline_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("baselines.id"), nullable=True, comment="对比基线ID"
    )
    deviation_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="最大偏差百分比"
    )
    avg_deviation_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="平均偏差百分比"
    )
    deviation_details: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="偏差区间详情JSON"
    )
    status: Mapped[HeatStatus] = mapped_column(
        Enum(HeatStatus), default=HeatStatus.PENDING, comment="偏差状态"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="创建时间"
    )

    # 关系
    baseline: Mapped["Baseline | None"] = relationship("Baseline", back_populates="heats")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="heat")

    def __repr__(self) -> str:
        return f"<Heat(id={self.id}, heat_no={self.heat_no}, status={self.status.value})>"
