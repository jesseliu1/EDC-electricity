"""最小可观测性辅助。"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import date, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("asns.observability")


def configure_observability() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def create_request_id() -> str:
    return uuid4().hex


def set_request_id(request_id: str) -> Token[str | None]:
    return _REQUEST_ID.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID.reset(token)


def get_request_id() -> str | None:
    return _REQUEST_ID.get()


def now_counter() -> float:
    return perf_counter()


def elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 1)


def log_event(event: str, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "event": event,
        "request_id": get_request_id(),
    }
    payload.update(fields)
    logger.info(json.dumps(payload, ensure_ascii=False, default=_json_default))


def _json_default(value: Any) -> str | float | int | bool | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
