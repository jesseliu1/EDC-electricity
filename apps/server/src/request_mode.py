"""请求级运行模式。"""

from __future__ import annotations

from contextvars import ContextVar, Token

from fastapi import Request

_SHOWTIME_MODE: ContextVar[bool] = ContextVar("showtime_mode", default=False)


def _parse_showtime_value(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_showtime_mode(request: Request) -> bool:
    """从 query/header 解析 showtime 模式。"""
    query_value = request.query_params.get("showtime")
    header_value = request.headers.get("X-Showtime")
    return _parse_showtime_value(query_value) or _parse_showtime_value(header_value)


def set_showtime_mode(enabled: bool) -> Token[bool]:
    return _SHOWTIME_MODE.set(bool(enabled))


def reset_showtime_mode(token: Token[bool]) -> None:
    _SHOWTIME_MODE.reset(token)


def is_showtime_mode() -> bool:
    return _SHOWTIME_MODE.get()
