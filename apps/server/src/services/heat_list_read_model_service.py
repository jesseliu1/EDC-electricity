"""炉次列表读模型组装。"""

from __future__ import annotations

from typing import Any


def build_heat_list_items(
    *,
    formal_items: list[dict[str, Any]],
    previous_runtime_items: dict[str, dict[str, Any]],
    active_runtime_items: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """按真源层原样拼接列表项，不做跨来源吞并或覆盖判断。"""

    items: list[dict[str, Any]] = []
    items.extend(formal_items)
    items.extend(previous_runtime_items.values())
    items.extend(active_runtime_items.values())
    return items
