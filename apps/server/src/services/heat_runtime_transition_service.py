"""运行态 current / previous 生命周期转换服务。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


def _context_start(item: dict[str, Any] | None) -> datetime | None:
    if not isinstance(item, dict):
        return None
    value = item.get("context_start_time") or item.get("start_time")
    return value if isinstance(value, datetime) else None


def _start_time(item: dict[str, Any] | None) -> datetime | None:
    if not isinstance(item, dict):
        return None
    value = item.get("start_time")
    return value if isinstance(value, datetime) else None


def _context_end(item: dict[str, Any] | None) -> datetime | None:
    if not isinstance(item, dict):
        return None
    value = item.get("context_end_time") or item.get("end_time")
    return value if isinstance(value, datetime) else None


class HeatRuntimeTransitionService:
    """负责 runtime 生命周期中的上下文窗口与 active->previous 升格语义。"""

    def prepare_active_candidate(
        self,
        candidate: dict[str, Any] | None,
        *,
        previous_candidate: dict[str, Any] | None,
        existing_previous_item: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if candidate is None:
            return None
        prepared = dict(candidate)
        context_start_time = (
            _start_time(previous_candidate)
            or _start_time(existing_previous_item)
            or prepared.get("start_time")
        )
        if isinstance(context_start_time, datetime):
            prepared["context_start_time"] = context_start_time
        end_time = prepared.get("end_time")
        if isinstance(end_time, datetime):
            prepared["context_end_time"] = end_time
            prepared["last_point_at"] = end_time
        return prepared

    def prepare_previous_candidate(
        self,
        candidate: dict[str, Any] | None,
        *,
        active_candidate: dict[str, Any] | None,
        existing_previous_item: dict[str, Any] | None,
        existing_active_item: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if candidate is None:
            return None
        prepared = dict(candidate)
        context_source = existing_previous_item
        if (
            context_source is None
            and isinstance(existing_active_item, dict)
            and str(prepared.get("id") or "") == str(existing_active_item.get("id") or "")
        ):
            context_source = existing_active_item
        context_start_time = _context_start(context_source) or prepared.get("start_time")
        if isinstance(context_start_time, datetime):
            prepared["context_start_time"] = context_start_time
        context_end_time = _context_end(active_candidate) or prepared.get("end_time")
        if isinstance(context_end_time, datetime):
            prepared["context_end_time"] = context_end_time
            prepared["last_point_at"] = context_end_time
        return prepared

    def clone_active_as_previous(
        self,
        existing_active_item: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(existing_active_item, dict):
            return None
        return deepcopy(existing_active_item)
