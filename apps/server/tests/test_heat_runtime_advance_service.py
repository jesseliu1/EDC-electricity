from __future__ import annotations

from datetime import datetime

from src.services.heat_runtime_advance_service import (
    DiscoveredSlotSummary,
    HeatRuntimeAdvanceService,
    RuntimeDiscoveryResult,
    RuntimeHeadState,
)


def _runtime_item(
    heat_id: str,
    start_time: datetime,
    *,
    slot_start_timestamp_ms: int | None = None,
) -> dict[str, object]:
    item = {
        "id": heat_id,
        "start_time": start_time,
    }
    if slot_start_timestamp_ms is not None:
        item["_live_slot_start_timestamp_ms"] = slot_start_timestamp_ms
    return item


def test_advance_once_bootstraps_live_head_from_discovery_tail() -> None:
    service = HeatRuntimeAdvanceService()

    plan = service.advance_once(
        RuntimeHeadState(current_item=None, previous_item=None),
        RuntimeDiscoveryResult(
            ordered_slots=[
                DiscoveredSlotSummary(slot_key="slot-0800"),
                DiscoveredSlotSummary(slot_key="slot-0830"),
            ],
            active_slot_key="slot-0830",
            previous_slot_key="slot-0800",
            sealed_slot_keys=[],
        ),
    )

    assert plan.action == "bootstrap_current"
    assert plan.next_previous_slot_key == "slot-0800"
    assert plan.next_current_slot_key == "slot-0830"


def test_advance_once_shifts_head_by_one_when_new_slot_is_born() -> None:
    service = HeatRuntimeAdvanceService()

    plan = service.advance_once(
        RuntimeHeadState(
            current_item=_runtime_item("slot-1030", datetime(2026, 4, 20, 10, 30)),
            previous_item=_runtime_item("slot-1000", datetime(2026, 4, 20, 10, 0)),
        ),
        RuntimeDiscoveryResult(
            ordered_slots=[
                DiscoveredSlotSummary(slot_key="slot-1030"),
                DiscoveredSlotSummary(slot_key="slot-1100"),
                DiscoveredSlotSummary(slot_key="slot-1130"),
            ],
            active_slot_key="slot-1130",
            previous_slot_key="slot-1100",
            sealed_slot_keys=["slot-1030", "slot-1100"],
        ),
    )

    assert plan.action == "seal_previous_and_shift"
    assert plan.seal_slot_key == "slot-1000"
    assert plan.next_previous_slot_key == "slot-1030"
    assert plan.next_current_slot_key == "slot-1100"


def test_advance_once_repairs_non_adjacent_previous_before_advancing_current() -> None:
    service = HeatRuntimeAdvanceService()

    plan = service.advance_once(
        RuntimeHeadState(
            current_item=_runtime_item("slot-0900", datetime(2026, 4, 20, 9, 0)),
            previous_item=_runtime_item("slot-0800", datetime(2026, 4, 20, 8, 0)),
        ),
        RuntimeDiscoveryResult(
            ordered_slots=[
                DiscoveredSlotSummary(slot_key="slot-0831"),
                DiscoveredSlotSummary(slot_key="slot-0900"),
            ],
            active_slot_key="slot-0900",
            previous_slot_key="slot-0831",
            sealed_slot_keys=["slot-0831"],
        ),
    )

    assert plan.action == "seal_previous_and_shift"
    assert plan.seal_slot_key == "slot-0800"
    assert plan.next_previous_slot_key == "slot-0831"
    assert plan.next_current_slot_key == "slot-0900"


def test_advance_once_noops_when_current_continues_without_next_slot() -> None:
    service = HeatRuntimeAdvanceService()

    plan = service.advance_once(
        RuntimeHeadState(
            current_item=_runtime_item("slot-1500", datetime(2026, 4, 20, 15, 0)),
            previous_item=_runtime_item("slot-1430", datetime(2026, 4, 20, 14, 30)),
        ),
        RuntimeDiscoveryResult(
            ordered_slots=[
                DiscoveredSlotSummary(slot_key="slot-1430"),
                DiscoveredSlotSummary(slot_key="slot-1500"),
            ],
            active_slot_key="slot-1500",
            previous_slot_key="slot-1430",
            sealed_slot_keys=[],
        ),
    )

    assert plan.action == "noop"
    assert plan.seal_slot_key is None
    assert plan.next_previous_slot_key == "slot-1430"
    assert plan.next_current_slot_key == "slot-1500"


def test_advance_once_reattaches_when_both_runtime_heads_are_outside_discovery_sequence() -> None:
    service = HeatRuntimeAdvanceService()

    plan = service.advance_once(
        RuntimeHeadState(
            current_item=_runtime_item("stale-active", datetime(2026, 4, 20, 16, 0)),
            previous_item=_runtime_item("stale-previous", datetime(2026, 4, 20, 15, 30)),
        ),
        RuntimeDiscoveryResult(
            ordered_slots=[
                DiscoveredSlotSummary(slot_key="slot-1100"),
                DiscoveredSlotSummary(slot_key="slot-1130"),
            ],
            active_slot_key="slot-1130",
            previous_slot_key="slot-1100",
            sealed_slot_keys=["slot-1030", "slot-1100"],
        ),
    )

    assert plan.action == "reattach_to_discovery_tail"
    assert plan.seal_slot_key is None
    assert plan.next_previous_slot_key == "slot-1100"
    assert plan.next_current_slot_key == "slot-1130"
    assert plan.refresh_outcome == "reattached_stale_runtime_head"


def test_advance_once_reattaches_single_slot_discovery_without_previous() -> None:
    service = HeatRuntimeAdvanceService()

    plan = service.advance_once(
        RuntimeHeadState(
            current_item=_runtime_item("stale-active", datetime(2026, 4, 20, 16, 0)),
            previous_item=_runtime_item("stale-previous", datetime(2026, 4, 20, 15, 30)),
        ),
        RuntimeDiscoveryResult(
            ordered_slots=[DiscoveredSlotSummary(slot_key="slot-1130")],
            active_slot_key="slot-1130",
            previous_slot_key=None,
            sealed_slot_keys=[],
        ),
    )

    assert plan.action == "reattach_to_discovery_tail"
    assert plan.seal_slot_key is None
    assert plan.next_previous_slot_key is None
    assert plan.next_current_slot_key == "slot-1130"


def test_advance_once_uses_stable_slot_key_before_runtime_id() -> None:
    service = HeatRuntimeAdvanceService()

    plan = service.advance_once(
        RuntimeHeadState(
            current_item=_runtime_item(
                "legacy-active-runtime-id",
                datetime(2026, 4, 20, 15, 0),
                slot_start_timestamp_ms=1713596400000,
            ),
            previous_item=_runtime_item(
                "legacy-previous-runtime-id",
                datetime(2026, 4, 20, 14, 30),
                slot_start_timestamp_ms=1713594600000,
            ),
        ),
        RuntimeDiscoveryResult(
            ordered_slots=[
                DiscoveredSlotSummary(slot_key="slot-start:1713594600000"),
                DiscoveredSlotSummary(slot_key="slot-start:1713596400000"),
            ],
            active_slot_key="slot-start:1713596400000",
            previous_slot_key="slot-start:1713594600000",
            sealed_slot_keys=[],
        ),
    )

    assert plan.action == "noop"
    assert plan.next_previous_slot_key == "slot-start:1713594600000"
    assert plan.next_current_slot_key == "slot-start:1713596400000"
