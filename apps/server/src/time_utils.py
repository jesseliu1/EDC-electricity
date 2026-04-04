"""时间语义工具。

统一绝对时间为 UTC 对应的 timestamp(ms)，
统一业务日期语义为 settings.plant_timezone。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_PLANT_TIMEZONE = "Asia/Shanghai"


def utc_now() -> datetime:
    """返回 UTC naive datetime，避免系统本地时区参与运算。"""
    return datetime.now(UTC).replace(tzinfo=None)


def utc_now_ms() -> int:
    """返回当前 UTC 毫秒时间戳。"""
    return to_timestamp_ms(utc_now())


def normalize_utc_datetime(value: datetime) -> datetime:
    """统一为 UTC naive datetime。"""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def to_timestamp_ms(value: datetime | int | float) -> int:
    """将 datetime/int/float 统一转换为毫秒时间戳。"""
    if isinstance(value, bool):
        raise TypeError("boolean is not a valid timestamp value")
    if isinstance(value, (int, float)):
        return int(value)
    normalized = normalize_utc_datetime(value)
    return int(normalized.replace(tzinfo=UTC).timestamp() * 1000)


def from_timestamp_ms(value: int | float) -> datetime:
    """将毫秒时间戳转换为 UTC naive datetime。"""
    return datetime.fromtimestamp(int(value) / 1000, UTC).replace(tzinfo=None)


def parse_timestamp_ms(value: object) -> datetime:
    """解析 API 传入的 timestamp(ms) 为 UTC naive datetime。"""
    if isinstance(value, datetime):
        return normalize_utc_datetime(value)
    if isinstance(value, bool):
        raise ValueError("invalid timestamp")
    if isinstance(value, (int, float)):
        return from_timestamp_ms(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("invalid timestamp")
        if stripped.lstrip("-").isdigit():
            return from_timestamp_ms(int(stripped))
        return normalize_utc_datetime(datetime.fromisoformat(stripped))
    raise ValueError("invalid timestamp")


def resolve_plant_timezone_name(value: str | None) -> str:
    """校验并返回有效的 IANA 时区名。"""
    candidate = (value or "").strip() or DEFAULT_PLANT_TIMEZONE
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return DEFAULT_PLANT_TIMEZONE
    return candidate


def get_plant_zoneinfo(value: str | None) -> ZoneInfo:
    """返回工厂时区对象。"""
    return ZoneInfo(resolve_plant_timezone_name(value))


def to_plant_datetime(value: datetime | int | float, timezone_name: str | None) -> datetime:
    """转换为工厂时区 aware datetime。"""
    if isinstance(value, datetime):
        utc_value = normalize_utc_datetime(value).replace(tzinfo=UTC)
    else:
        utc_value = from_timestamp_ms(value).replace(tzinfo=UTC)
    return utc_value.astimezone(get_plant_zoneinfo(timezone_name))


def plant_date_of(value: datetime | int | float, timezone_name: str | None) -> date:
    """返回工厂时区下的本地日期。"""
    return to_plant_datetime(value, timezone_name).date()


def plant_day_bounds_ms(value: datetime | int | float, timezone_name: str | None) -> tuple[int, int]:
    """返回工厂时区当日 [start, end) 的 UTC 毫秒时间戳。"""
    local_value = to_plant_datetime(value, timezone_name)
    local_day_start = local_value.replace(hour=0, minute=0, second=0, microsecond=0)
    local_day_end = local_day_start + timedelta(days=1)
    return (
        to_timestamp_ms(local_day_start.astimezone(UTC)),
        to_timestamp_ms(local_day_end.astimezone(UTC)),
    )


def plant_day_bounds_datetime(
    value: datetime | int | float,
    timezone_name: str | None,
) -> tuple[datetime, datetime]:
    """返回工厂时区当日 [start, end) 的 UTC naive datetime。"""
    start_ms, end_ms = plant_day_bounds_ms(value, timezone_name)
    return from_timestamp_ms(start_ms), from_timestamp_ms(end_ms)


def minutes_since_midnight(value: datetime | int | float, timezone_name: str | None) -> int:
    """返回工厂时区下的分钟位移。"""
    local_value = to_plant_datetime(value, timezone_name)
    return local_value.hour * 60 + local_value.minute

