"""系统设置模型"""

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db_types import TimestampMsType
from ..database import Base
from ..time_utils import utc_now


class Setting(Base):
    """系统设置模型

    键值对形式存储系统配置项。
    """

    __tablename__ = "settings"

    # 主键（配置键名）
    key: Mapped[str] = mapped_column(String(100), primary_key=True, comment="配置键名")

    # 配置值
    value: Mapped[str] = mapped_column(Text, nullable=False, comment="配置值JSON")

    # 描述
    description: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="配置描述")

    # 时间戳
    updated_at: Mapped[datetime] = mapped_column(
        TimestampMsType(), default=utc_now, onupdate=utc_now, comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<Setting(key={self.key})>"


# 预定义的系统设置键名
class SettingKeys:
    """系统设置键名常量"""

    # 默认容许误差
    DEFAULT_TOLERANCE_PERCENT = "default_tolerance_percent"

    # EDC 连接配置
    EDC_BASE_URL = "edc_base_url"
    EDC_API_KEY = "edc_api_key"

    # 报表设置
    REPORT_GENERATION_HOUR = "report_generation_hour"

    # 当前激活的基线ID
    ACTIVE_BASELINE_ID = "active_baseline_id"
