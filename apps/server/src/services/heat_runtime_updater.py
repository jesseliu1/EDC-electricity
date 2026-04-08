"""当前炉次运行态增量更新器。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from .formal_heat_service import (
    MetricCurveLoader,
    build_runtime_preseal_payload,
    hydrate_candidate_runtime_metric_series,
)
from .heat_deviation_analysis_service import HeatDeviationAnalysisService
from .heat_runtime_factory import HeatRuntimeFactory


class HeatRuntimeUpdater:
    """只负责把已有 runtime 按冻结快照更新到当前最新增量状态。"""

    def __init__(self) -> None:
        self._runtime_factory = HeatRuntimeFactory()
        self._analysis_service = HeatDeviationAnalysisService()

    async def update_existing_runtime(
        self,
        *,
        existing_item: dict[str, Any],
        candidate: dict[str, Any],
        trigger_source: str,
        processing_mode: str = "live_incremental",
        request_anchor_time: datetime | None = None,
        metric_curve_loader: MetricCurveLoader | None = None,
    ) -> dict[str, Any]:
        frozen_inputs = self._runtime_factory.resolve_frozen_analysis_inputs(existing_item)
        if frozen_inputs is None:
            raise ValueError("runtime_birth_context_missing")

        updated = dict(existing_item)
        updated.update(candidate)
        updated["created_at"] = existing_item.get("created_at") or candidate.get("created_at")
        updated["birth_context"] = deepcopy(existing_item.get("birth_context"))
        updated["definition_metric_snapshots"] = deepcopy(
            existing_item.get("definition_metric_snapshots") or []
        )
        updated["baseline_curve_snapshots"] = deepcopy(
            existing_item.get("baseline_curve_snapshots") or []
        )
        updated = await hydrate_candidate_runtime_metric_series(
            updated,
            definition_templates=frozen_inputs.definition_metric_snapshots,
            metric_curve_loader=metric_curve_loader,
        )

        binding_analyses = self._analysis_service.analyze_candidate_bindings(
            candidate=updated,
            applicable_baselines=frozen_inputs.applicable_baselines,
            baseline_curve_payloads=frozen_inputs.baseline_curve_payloads,
        )
        updated = self._analysis_service.apply_binding_analysis_to_candidate(
            candidate=updated,
            binding_analyses=binding_analyses,
        )
        updated["definition_metric_snapshots"] = deepcopy(
            existing_item.get("definition_metric_snapshots") or []
        )
        updated["baseline_curve_snapshots"] = deepcopy(
            existing_item.get("baseline_curve_snapshots") or []
        )
        updated["birth_context"] = deepcopy(existing_item.get("birth_context"))
        updated["processing_meta"] = {
            "processing_mode": processing_mode,
            "trigger_source": trigger_source,
            "request_anchor_time": request_anchor_time or candidate.get("start_time"),
            "batch_cursor": None,
            "last_processed_heat_id": str(updated.get("id") or ""),
        }
        updated["preseal_payload"] = build_runtime_preseal_payload(
            updated,
            applicable_baselines=frozen_inputs.applicable_baselines,
            trigger_source=trigger_source,
        ).to_dict()
        return updated
