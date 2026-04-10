"""replay 显式黄金基线选择服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .formal_baseline_service import decode_baseline_id, get_baseline_record, get_definition_record


@dataclass(slots=True)
class ReplayBaselineSelection:
    """本次 replay 任务选择的黄金基线集合。

    业务语义：
    - `primary_baseline` 是本次批量初始化/重放的默认主黄金基线
    - `selected_baselines` 是本次允许参与绑定与分析的黄金基线集合
    - `definition_id` 表示这些黄金基线对应的炉次指标定义模板
    - `expected_duration_minutes` 表示这次切炉次时使用的预期炉次时长
    """

    primary_baseline: dict[str, Any]
    selected_baselines: list[dict[str, Any]]
    definition_id: str
    expected_duration_minutes: int


class ReplayBaselineSelectionService:
    """校验并解析 replay 请求里的显式黄金基线选择。"""

    async def resolve_selection(
        self,
        *,
        primary_baseline_id: str,
        baseline_ids: list[str],
    ) -> ReplayBaselineSelection:
        normalized_ids = [str(item).strip() for item in baseline_ids if str(item).strip()]
        if not normalized_ids:
            raise ValueError("replay_baseline_ids_missing")

        normalized_primary_id = str(primary_baseline_id).strip()
        if not normalized_primary_id:
            raise ValueError("replay_primary_baseline_missing")
        if normalized_primary_id not in normalized_ids:
            raise ValueError("replay_primary_baseline_not_in_selection")

        selected_baselines: list[dict[str, Any]] = []
        primary_baseline: dict[str, Any] | None = None
        definition_id: str | None = None

        for baseline_id in normalized_ids:
            definition_part, item_part = decode_baseline_id(baseline_id)
            baseline = await get_baseline_record(definition_part, item_part)
            if baseline is None:
                raise ValueError("replay_selected_baseline_not_found")
            if str(baseline.get("status") or "") != "published":
                raise ValueError("replay_selected_baseline_not_published")

            normalized_definition_id = str(baseline.get("definition_id") or "").strip()
            if not normalized_definition_id:
                raise ValueError("replay_selected_baseline_definition_missing")
            if definition_id is None:
                definition_id = normalized_definition_id
            elif normalized_definition_id != definition_id:
                raise ValueError("replay_selected_baselines_cross_definition")

            normalized = dict(baseline)
            normalized["is_default"] = baseline_id == normalized_primary_id
            selected_baselines.append(normalized)
            if baseline_id == normalized_primary_id:
                primary_baseline = normalized

        if primary_baseline is None or definition_id is None:
            raise ValueError("replay_primary_baseline_not_found")

        definition = await get_definition_record(definition_id)
        if definition is None:
            raise ValueError("replay_primary_definition_not_found")

        expected_duration_minutes = int(definition.get("expected_duration_minutes") or 0)
        if expected_duration_minutes <= 0:
            raise ValueError("replay_primary_definition_duration_invalid")

        return ReplayBaselineSelection(
            primary_baseline=primary_baseline,
            selected_baselines=selected_baselines,
            definition_id=definition_id,
            expected_duration_minutes=expected_duration_minutes,
        )
