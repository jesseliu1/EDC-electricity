"""当前炉次运行态增量更新器。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from .formal_heat_service import (
    MetricCurveLoader,
    _build_runtime_baseline_views,
    build_runtime_preseal_payload,
    hydrate_candidate_runtime_metric_series,
)
from .heat_deviation_analysis_service import HeatDeviationAnalysisService
from .heat_runtime_factory import HeatRuntimeFactory
from .heat_runtime_frozen_input_resolver import (
    resolve_runtime_baseline_metric_specs_from_frozen_inputs,
    resolve_runtime_hydrate_specs_from_frozen_inputs,
)


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
        preserve_binding_analysis: bool = False,
    ) -> dict[str, Any]:
        frozen_inputs = self._runtime_factory.resolve_frozen_analysis_inputs(existing_item)
        if frozen_inputs is None:
            raise ValueError("runtime_birth_context_missing")
        metric_union_specs = resolve_runtime_hydrate_specs_from_frozen_inputs(existing_item)
        if not metric_union_specs:
            raise ValueError("runtime_birth_context_missing")
        baseline_metric_specs_by_id = resolve_runtime_baseline_metric_specs_from_frozen_inputs(
            existing_item,
            applicable_baselines=frozen_inputs.applicable_baselines,
        )
        if not baseline_metric_specs_by_id:
            raise ValueError("runtime_birth_context_missing")

        updated = dict(existing_item)
        updated.update(candidate)
        updated["created_at"] = existing_item.get("created_at") or candidate.get("created_at")
        updated["birth_context"] = deepcopy(existing_item.get("birth_context"))
        updated["definition_metric_snapshots"] = deepcopy(metric_union_specs)
        updated["baseline_curve_snapshots"] = deepcopy(
            existing_item.get("baseline_curve_snapshots") or []
        )
        updated["baseline_views"] = []
        updated = await hydrate_candidate_runtime_metric_series(
            updated,
            metric_specs=metric_union_specs,
            metric_curve_loader=metric_curve_loader,
        )
        updated["definition_metric_snapshots"] = deepcopy(metric_union_specs)
        updated["baseline_views"] = _build_runtime_baseline_views(
            candidate=updated,
            applicable_baselines=frozen_inputs.applicable_baselines,
            baseline_metric_specs_by_id=baseline_metric_specs_by_id,
        )
        if preserve_binding_analysis:
            updated["baseline_bindings"] = deepcopy(existing_item.get("baseline_bindings") or [])
            updated["baseline_ids"] = deepcopy(existing_item.get("baseline_ids") or [])
            for field_name in (
                "baseline_id",
                "baseline_version_id",
                "baseline_definition_id",
                "baseline_item",
                "baseline_effective_from",
                "analysis_status",
                "analysis_reason",
                "analysis_message",
                "deviation_score",
                "avg_deviation_score",
                "abnormal_duration_minutes",
                "status",
            ):
                updated[field_name] = deepcopy(existing_item.get(field_name))
        else:
            binding_analyses = self._analysis_service.analyze_candidate_bindings(
                candidate=updated,
                applicable_baselines=frozen_inputs.applicable_baselines,
                baseline_curve_payloads=frozen_inputs.baseline_curve_payloads,
            )
            updated = self._analysis_service.apply_binding_analysis_to_candidate(
                candidate=updated,
                binding_analyses=binding_analyses,
            )
        updated["baseline_views"] = _build_runtime_baseline_views(
            candidate=updated,
            applicable_baselines=frozen_inputs.applicable_baselines,
            baseline_metric_specs_by_id=baseline_metric_specs_by_id,
        )
        updated["definition_metric_snapshots"] = deepcopy(metric_union_specs)
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
