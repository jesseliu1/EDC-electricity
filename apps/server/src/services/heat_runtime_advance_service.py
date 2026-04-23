"""运行态单步推进决策服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(slots=True)
class RuntimeHeadState:
    current_item: dict[str, Any] | None
    previous_item: dict[str, Any] | None
    latest_history_item: dict[str, Any] | None = None


@dataclass(slots=True)
class DiscoveredSlotSummary:
    slot_key: str


@dataclass(slots=True)
class RuntimeDiscoveryResult:
    ordered_slots: list[DiscoveredSlotSummary]
    active_slot_key: str | None
    previous_slot_key: str | None
    sealed_slot_keys: list[str]
    snapshot_watermark: Any = None
    processor_state_snapshot: dict[str, Any] | None = None


@dataclass(slots=True)
class RuntimeAdvancePlan:
    action: Literal[
        "noop",
        "bootstrap_current",
        "promote_current_to_previous",
        "seal_previous_and_shift",
        "reattach_to_discovery_tail",
    ]
    seal_slot_key: str | None
    next_previous_slot_key: str | None
    next_current_slot_key: str | None
    remaining_closed_backlog: int
    refresh_outcome: str


def runtime_slot_key(item: dict[str, Any] | None) -> str | None:
    if not isinstance(item, dict):
        return None
    slot_start_timestamp_ms = item.get("_live_slot_start_timestamp_ms")
    if slot_start_timestamp_ms is not None:
        key = f"slot-start:{int(slot_start_timestamp_ms)}"
    else:
        key = str(item.get("id") or "").strip()
    return key or None


class HeatRuntimeAdvanceService:
    """把识别结果收敛成 current -> previous -> db 的单步推进计划。"""

    def advance_once(
        self,
        head_state: RuntimeHeadState,
        discovery_result: RuntimeDiscoveryResult,
    ) -> RuntimeAdvancePlan:
        ordered_keys = [
            slot.slot_key.strip()
            for slot in discovery_result.ordered_slots
            if isinstance(slot.slot_key, str) and slot.slot_key.strip()
        ]
        ordered_index = {slot_key: index for index, slot_key in enumerate(ordered_keys)}
        sealed_keys = {
            str(slot_key).strip()
            for slot_key in discovery_result.sealed_slot_keys
            if str(slot_key).strip()
        }

        current_key = runtime_slot_key(head_state.current_item)
        previous_key = runtime_slot_key(head_state.previous_item)
        active_slot_key = (
            str(discovery_result.active_slot_key).strip()
            if discovery_result.active_slot_key
            else None
        ) or None
        previous_slot_key = (
            str(discovery_result.previous_slot_key).strip()
            if discovery_result.previous_slot_key
            else None
        ) or None

        if self._is_disconnected_head(
            head_keys=[current_key, previous_key],
            ordered_index=ordered_index,
            discovery_keys=[active_slot_key, previous_slot_key],
            sealed_keys=sealed_keys,
        ):
            next_previous_key, next_current_key = self._discovery_tail_keys(
                ordered_keys=ordered_keys,
                active_slot_key=active_slot_key,
                previous_slot_key=previous_slot_key,
            )
            if next_current_key is not None:
                return RuntimeAdvancePlan(
                    action="reattach_to_discovery_tail",
                    seal_slot_key=None,
                    next_previous_slot_key=next_previous_key,
                    next_current_slot_key=next_current_key,
                    remaining_closed_backlog=self._remaining_backlog(
                        sealed_keys=sealed_keys,
                        consumed_keys={
                            key
                            for key in (next_previous_key, next_current_key)
                            if key is not None
                        },
                    ),
                    refresh_outcome="reattached_stale_runtime_head",
                )

        if current_key is None and previous_key is None:
            next_current_key = active_slot_key or previous_slot_key or (
                ordered_keys[0] if ordered_keys else None
            )
            next_previous_key = previous_slot_key if active_slot_key else None
            return RuntimeAdvancePlan(
                action="bootstrap_current",
                seal_slot_key=None,
                next_previous_slot_key=next_previous_key,
                next_current_slot_key=next_current_key,
                remaining_closed_backlog=self._remaining_backlog(
                    sealed_keys=sealed_keys,
                    consumed_keys={
                        key
                        for key in (next_previous_key, next_current_key)
                        if key is not None
                    },
                ),
                refresh_outcome="bootstrap_current",
            )

        if current_key is None and previous_key is not None:
            next_current_key = (
                active_slot_key
                or self._next_after(previous_key, ordered_keys, ordered_index)
                or previous_slot_key
            )
            return RuntimeAdvancePlan(
                action="bootstrap_current",
                seal_slot_key=None,
                next_previous_slot_key=previous_key,
                next_current_slot_key=next_current_key,
                remaining_closed_backlog=self._remaining_backlog(
                    sealed_keys=sealed_keys,
                    consumed_keys={
                        key for key in (previous_key, next_current_key) if key is not None
                    },
                ),
                refresh_outcome="bootstrap_current",
            )

        if current_key is None:
            return RuntimeAdvancePlan(
                action="noop",
                seal_slot_key=None,
                next_previous_slot_key=previous_key,
                next_current_slot_key=None,
                remaining_closed_backlog=self._remaining_backlog(
                    sealed_keys=sealed_keys,
                    consumed_keys={key for key in (previous_key,) if key is not None},
                ),
                refresh_outcome="no_new_heat_born",
            )

        next_previous_key, next_current_key = self._resolve_shift_targets(
            previous_key=previous_key,
            current_key=current_key,
            ordered_keys=ordered_keys,
            ordered_index=ordered_index,
        )

        if next_previous_key is None and next_current_key is None:
            return RuntimeAdvancePlan(
                action="noop",
                seal_slot_key=None,
                next_previous_slot_key=previous_key,
                next_current_slot_key=current_key,
                remaining_closed_backlog=self._remaining_backlog(
                    sealed_keys=sealed_keys,
                    consumed_keys={key for key in (previous_key, current_key) if key is not None},
                ),
                refresh_outcome="active_heat_continues",
            )

        consumed_keys = {
            key
            for key in (previous_key, current_key, next_previous_key, next_current_key)
            if key is not None
        }
        if previous_key is not None:
            return RuntimeAdvancePlan(
                action="seal_previous_and_shift",
                seal_slot_key=previous_key,
                next_previous_slot_key=next_previous_key,
                next_current_slot_key=next_current_key,
                remaining_closed_backlog=self._remaining_backlog(
                    sealed_keys=sealed_keys,
                    consumed_keys=consumed_keys,
                ),
                refresh_outcome="backlog_catchup",
            )

        return RuntimeAdvancePlan(
            action="promote_current_to_previous",
            seal_slot_key=None,
            next_previous_slot_key=next_previous_key,
            next_current_slot_key=next_current_key,
            remaining_closed_backlog=self._remaining_backlog(
                sealed_keys=sealed_keys,
                consumed_keys=consumed_keys,
            ),
            refresh_outcome="new_heat_born",
        )

    @staticmethod
    def _next_after(
        slot_key: str,
        ordered_keys: list[str],
        ordered_index: dict[str, int],
    ) -> str | None:
        index = ordered_index.get(slot_key)
        if index is None:
            return None
        next_index = index + 1
        if next_index >= len(ordered_keys):
            return None
        return ordered_keys[next_index]

    @staticmethod
    def _is_disconnected_head(
        *,
        head_keys: list[str | None],
        ordered_index: dict[str, int],
        discovery_keys: list[str | None],
        sealed_keys: set[str],
    ) -> bool:
        present_keys = [key for key in head_keys if key is not None]
        if not present_keys:
            return False
        discovered_keys = {
            key for key in discovery_keys if isinstance(key, str) and key
        }
        return all(
            key not in ordered_index
            and key not in discovered_keys
            and key not in sealed_keys
            for key in present_keys
        )

    @staticmethod
    def _discovery_tail_keys(
        *,
        ordered_keys: list[str],
        active_slot_key: str | None,
        previous_slot_key: str | None,
    ) -> tuple[str | None, str | None]:
        tail_current_key = active_slot_key or previous_slot_key or (
            ordered_keys[-1] if ordered_keys else None
        )
        if tail_current_key is None:
            return None, None
        if active_slot_key is not None and previous_slot_key is not None:
            return previous_slot_key, active_slot_key
        if tail_current_key == previous_slot_key:
            return None, tail_current_key
        if len(ordered_keys) >= 2:
            return ordered_keys[-2], ordered_keys[-1]
        return None, tail_current_key

    def _resolve_shift_targets(
        self,
        *,
        previous_key: str | None,
        current_key: str,
        ordered_keys: list[str],
        ordered_index: dict[str, int],
    ) -> tuple[str | None, str | None]:
        current_index = ordered_index.get(current_key)
        previous_index = ordered_index.get(previous_key) if previous_key is not None else None

        if previous_index is not None and current_index is not None:
            if current_index - previous_index > 1:
                next_previous_key = ordered_keys[previous_index + 1]
                return next_previous_key, current_key
            if current_index - previous_index == 1:
                next_current_key = self._next_after(current_key, ordered_keys, ordered_index)
                if next_current_key is None:
                    return None, None
                return current_key, next_current_key

        if current_index is not None:
            if previous_key is not None and current_index > 0:
                predecessor = ordered_keys[current_index - 1]
                if predecessor != previous_key:
                    return predecessor, current_key
            next_current_key = self._next_after(current_key, ordered_keys, ordered_index)
            if next_current_key is not None:
                return current_key, next_current_key

        return None, None

    @staticmethod
    def _remaining_backlog(*, sealed_keys: set[str], consumed_keys: set[str]) -> int:
        return len([slot_key for slot_key in sealed_keys if slot_key not in consumed_keys])
