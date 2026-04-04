"""数据库自定义类型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.types import BigInteger, TypeDecorator

from .time_utils import from_timestamp_ms, to_timestamp_ms


class TimestampMsType(TypeDecorator):
    """SQLite 中按 int64(timestamp_ms) 存储，Python 侧仍使用 datetime。"""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: datetime | int | None, dialect):
        if value is None:
            return None
        return to_timestamp_ms(value)

    def process_result_value(self, value: int | None, dialect):
        if value is None:
            return None
        return from_timestamp_ms(value)
