"""replay 运行态聚合构建服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .formal_heat_service import MetricCurveLoader, compile_runtime_candidates
from .heat_cutting_service import HeatCuttingConfig
from .heat_runtime_seal_service import HeatRuntimeSealService
from .heat_runtime_transition_service import HeatRuntimeTransitionService
from .heat_runtime_updater import HeatRuntimeUpdater


@dataclass(slots=True)
class ReplayAggregateResult:
    sealed_history_candidates: list[dict[str, Any]]
    final_previous_candidate: dict[str, Any] | None
    final_active_candidate: dict[str, Any] | None
    processor_snapshot: dict[str, Any] | None
    all_segment_count: int
    history_segment_count: int


class HeatReplayRuntimeAggregateService:
    """按 live 同一套 current/previous/seal 语义回放 replay 历史段。"""

    def __init__(self) -> None:
        self._transition_service = HeatRuntimeTransitionService()
        self._runtime_updater = HeatRuntimeUpdater()
        self._seal_service = HeatRuntimeSealService()

    @staticmethod
    def _apply_declared_context(
        target: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        for field_name in ("context_start_time", "context_end_time"):
            if source.get(field_name) is not None:
                target[field_name] = source[field_name]
        return target

    async def build_replay_runtime_aggregate(
        self,
        candidates: list[dict[str, Any]],
        *,
        trigger_source: str,
        cutting_config: HeatCuttingConfig | None = None,
        metric_curve_loader: MetricCurveLoader | None = None,
        explicit_baselines: list[Any] | None = None,
        explicit_primary_baseline_id: str | None = None,
        processor_snapshot: dict[str, Any] | None = None,
        all_segment_count: int | None = None,
    ) -> ReplayAggregateResult:
        if not candidates:
            return ReplayAggregateResult(
                sealed_history_candidates=[],
                final_previous_candidate=None,
                final_active_candidate=None,
                processor_snapshot=processor_snapshot,
                all_segment_count=int(all_segment_count or 0),
                history_segment_count=0,
            )

        prepared_candidates = (
            [dict(candidate) for candidate in candidates]
            if all(isinstance(candidate.get("preseal_payload"), dict) for candidate in candidates)
            else await compile_runtime_candidates(
                sorted(
                    candidates,
                    key=lambda candidate: (
                        candidate.get("start_time"),
                        str(candidate.get("id") or ""),
                    ),
                ),
                processing_mode="replay_batch",
                trigger_source=trigger_source,
                cutting_config=cutting_config,
                explicit_baselines=explicit_baselines,
                explicit_primary_baseline_id=explicit_primary_baseline_id,
                metric_curve_loader=metric_curve_loader,
            )
        )
        prepared_candidates.sort(
            key=lambda candidate: (
                candidate.get("start_time"),
                str(candidate.get("id") or ""),
            )
        )

        sealed_history_candidates: list[dict[str, Any]] = []
        current_previous: dict[str, Any] | None = None
        current_active: dict[str, Any] | None = None

        for prepared_candidate in prepared_candidates:
            next_candidate = dict(prepared_candidate)
            if current_active is None:
                current_active = next_candidate
                continue

            if isinstance(current_previous, dict):
                sealed_history_candidates.extend(
                    self._seal_service.resolve_seal_sources(
                        sealed_candidates=[dict(current_previous)],
                        existing_previous_item=current_previous,
                        existing_active_item=current_active,
                        trigger_source=trigger_source,
                    )
                )

            promoted_previous = (
                self._transition_service.clone_active_as_previous(current_active)
                or dict(current_active)
            )
            promoted_previous = self._transition_service.prepare_previous_candidate(
                promoted_previous,
                active_candidate=next_candidate,
                existing_previous_item=current_previous,
                existing_active_item=current_active,
            )
            if promoted_previous is None:
                raise ValueError("replay_previous_candidate_prepare_failed")

            updated_previous = await self._runtime_updater.update_existing_runtime(
                existing_item=current_active,
                candidate=promoted_previous,
                trigger_source=trigger_source,
                processing_mode="replay_batch",
                request_anchor_time=promoted_previous.get("start_time"),
                metric_curve_loader=metric_curve_loader,
                preserve_binding_analysis=True,
            )
            updated_previous = self._apply_declared_context(updated_previous, promoted_previous)

            next_active = self._transition_service.prepare_active_candidate(
                next_candidate,
                previous_candidate=updated_previous,
                existing_previous_item=current_previous,
            )
            if next_active is None:
                raise ValueError("replay_active_candidate_prepare_failed")

            updated_active = await self._runtime_updater.update_existing_runtime(
                existing_item=prepared_candidate,
                candidate=next_active,
                trigger_source=trigger_source,
                processing_mode="replay_batch",
                request_anchor_time=next_active.get("start_time"),
                metric_curve_loader=metric_curve_loader,
            )
            updated_active = self._apply_declared_context(updated_active, next_active)

            current_previous = updated_previous
            current_active = updated_active

        head_count = int(current_previous is not None) + int(current_active is not None)
        total_segment_count = int(all_segment_count or len(prepared_candidates))
        history_segment_count = max(total_segment_count - head_count, 0)
        return ReplayAggregateResult(
            sealed_history_candidates=sealed_history_candidates,
            final_previous_candidate=current_previous,
            final_active_candidate=current_active,
            processor_snapshot=processor_snapshot,
            all_segment_count=total_segment_count,
            history_segment_count=history_segment_count,
        )
