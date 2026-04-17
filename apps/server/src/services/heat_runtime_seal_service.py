"""运行态 sealed history 入口选择服务。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from .formal_heat_service import build_runtime_preseal_payload
from .heat_runtime_factory import HeatRuntimeFactory


def _time_window(item: dict[str, Any]) -> tuple[datetime, datetime] | None:
    start_time = item.get("start_time")
    end_time = item.get("end_time")
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        return None
    return start_time, end_time


def _windows_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_window = _time_window(left)
    right_window = _time_window(right)
    if left_window is None or right_window is None:
        return False
    left_start, left_end = left_window
    right_start, right_end = right_window
    return left_start <= right_end and right_start <= left_end


class HeatRuntimeSealService:
    """负责把 sealed signal 解析成真正的正式入库真源。"""

    def __init__(self) -> None:
        self._runtime_factory = HeatRuntimeFactory()

    def resolve_seal_sources(
        self,
        *,
        sealed_candidates: list[dict[str, Any]],
        existing_previous_item: dict[str, Any] | None,
        existing_active_item: dict[str, Any] | None,
        trigger_source: str,
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for candidate in sealed_candidates:
            source_item = self._resolve_runtime_source(
                candidate,
                existing_previous_item=existing_previous_item,
            )
            if source_item is None:
                if self._is_historical_seal_signal(
                    candidate,
                    existing_previous_item=existing_previous_item,
                    existing_active_item=existing_active_item,
                ):
                    continue
                raise ValueError("sealed_runtime_source_missing")
            prepared = self._prepare_runtime_item_for_seal(
                source_item,
                trigger_source=trigger_source,
            )
            if not isinstance(prepared.get("preseal_payload"), dict):
                raise ValueError("sealed_runtime_preseal_payload_missing")
            resolved.append(prepared)
        return resolved

    def _resolve_runtime_source(
        self,
        candidate: dict[str, Any],
        *,
        existing_previous_item: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        runtime_item = existing_previous_item
        if not isinstance(runtime_item, dict):
            return None
        if str(runtime_item.get("id") or "") == str(candidate.get("id") or ""):
            return runtime_item
        if _windows_overlap(runtime_item, candidate):
            return runtime_item
        return None

    def _is_historical_seal_signal(
        self,
        candidate: dict[str, Any],
        *,
        existing_previous_item: dict[str, Any] | None,
        existing_active_item: dict[str, Any] | None,
    ) -> bool:
        candidate_window = _time_window(candidate)
        if candidate_window is None:
            return False
        candidate_end_time = candidate_window[1]
        runtime_starts = [
            window[0]
            for window in (
                _time_window(existing_previous_item) if isinstance(existing_previous_item, dict) else None,
                _time_window(existing_active_item) if isinstance(existing_active_item, dict) else None,
            )
            if window is not None
        ]
        if not runtime_starts:
            return False
        return candidate_end_time < min(runtime_starts)

    def _prepare_runtime_item_for_seal(
        self,
        runtime_item: dict[str, Any],
        *,
        trigger_source: str,
    ) -> dict[str, Any]:
        prepared = deepcopy(runtime_item)
        frozen_inputs = self._runtime_factory.resolve_frozen_analysis_inputs(prepared)
        if frozen_inputs is None:
            return prepared
        prepared["preseal_payload"] = build_runtime_preseal_payload(
            prepared,
            applicable_baselines=frozen_inputs.applicable_baselines,
            trigger_source=trigger_source,
        ).to_dict()
        return prepared
