"""当前炉次出生快照工厂。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schemas.common import CurvePoint
from .formal_baseline_service import encode_baseline_id
from .heat_cutting_service import HeatCuttingConfig, normalize_cutting_mode
from .heat_deviation_analysis_service import BaselineCurvePayload


def _field(item: Any, field_name: str) -> Any:
    if isinstance(item, dict):
        return item.get(field_name)
    return getattr(item, field_name, None)


def _coerce_curve_points(points: list[CurvePoint] | list[dict[str, Any]] | None) -> list[CurvePoint]:
    normalized: list[CurvePoint] = []
    for point in points or []:
        if isinstance(point, CurvePoint):
            normalized.append(point)
            continue
        if not isinstance(point, dict):
            continue
        timestamp = point.get("timestamp")
        value = point.get("value")
        if timestamp is None or value is None:
            continue
        normalized.append(CurvePoint(timestamp=int(timestamp), value=float(value)))
    return normalized


@dataclass(slots=True)
class HeatRuntimeAnalysisInputs:
    applicable_baselines: list[dict[str, Any]]
    definition_metric_snapshots: list[dict[str, Any]]
    baseline_curve_snapshots: list[dict[str, Any]]
    baseline_curve_payloads: dict[str, BaselineCurvePayload]


@dataclass(slots=True)
class HeatRuntimeBirthSnapshot:
    birth_context: dict[str, Any]
    definition_metric_snapshots: list[dict[str, Any]]
    baseline_curve_snapshots: list[dict[str, Any]]


class HeatRuntimeFactory:
    """负责创建和解析炉次出生时冻结的业务快照。"""

    def serialize_cutting_config(self, cutting_config: HeatCuttingConfig) -> dict[str, Any]:
        return {
            "time_tolerance_percent": float(cutting_config.time_tolerance_percent),
            "major_issue_duration_minutes": int(cutting_config.major_issue_duration_minutes),
            "plant_timezone": str(cutting_config.plant_timezone),
            "work_start_time": str(cutting_config.work_start_time),
            "work_end_time": str(cutting_config.work_end_time),
            "break_periods": [str(period) for period in cutting_config.break_periods],
            "cutting_mode": normalize_cutting_mode(cutting_config.cutting_mode),
            "fixed_interval_minutes": (
                int(cutting_config.fixed_interval_minutes)
                if cutting_config.fixed_interval_minutes is not None
                else None
            ),
        }

    def resolve_frozen_cutting_config(
        self,
        candidate: dict[str, Any],
        *,
        fallback_config: HeatCuttingConfig | None = None,
    ) -> HeatCuttingConfig | None:
        birth_context = candidate.get("birth_context")
        if not isinstance(birth_context, dict):
            return fallback_config

        raw_snapshot = birth_context.get("cutting_config_snapshot")
        if isinstance(raw_snapshot, dict):
            try:
                fixed_interval_minutes = raw_snapshot.get("fixed_interval_minutes")
                return HeatCuttingConfig(
                    time_tolerance_percent=float(raw_snapshot.get("time_tolerance_percent") or 0.0),
                    major_issue_duration_minutes=int(
                        raw_snapshot.get("major_issue_duration_minutes") or 0
                    ),
                    plant_timezone=str(raw_snapshot.get("plant_timezone") or ""),
                    work_start_time=str(raw_snapshot.get("work_start_time") or ""),
                    work_end_time=str(raw_snapshot.get("work_end_time") or ""),
                    break_periods=tuple(
                        str(period) for period in (raw_snapshot.get("break_periods") or [])
                    ),
                    cutting_mode=normalize_cutting_mode(raw_snapshot.get("cutting_mode")),
                    fixed_interval_minutes=(
                        int(fixed_interval_minutes) if fixed_interval_minutes is not None else None
                    ),
                )
            except (TypeError, ValueError):
                pass

        if fallback_config is None:
            return None

        cutting_mode = normalize_cutting_mode(birth_context.get("cutting_mode"))
        fixed_interval_minutes = fallback_config.fixed_interval_minutes
        if cutting_mode == "fixed_interval" and fixed_interval_minutes is None:
            duration_bucket = candidate.get("_live_duration_bucket_minutes")
            if duration_bucket is not None:
                try:
                    fixed_interval_minutes = int(duration_bucket)
                except (TypeError, ValueError):
                    fixed_interval_minutes = None

        return HeatCuttingConfig(
            time_tolerance_percent=float(fallback_config.time_tolerance_percent),
            major_issue_duration_minutes=int(fallback_config.major_issue_duration_minutes),
            plant_timezone=str(
                birth_context.get("plant_timezone") or fallback_config.plant_timezone
            ),
            work_start_time=str(fallback_config.work_start_time),
            work_end_time=str(fallback_config.work_end_time),
            break_periods=tuple(str(period) for period in fallback_config.break_periods),
            cutting_mode=cutting_mode,
            fixed_interval_minutes=(
                int(fixed_interval_minutes)
                if cutting_mode == "fixed_interval" and fixed_interval_minutes is not None
                else None
            ),
        )

    def has_frozen_birth_context(self, candidate: dict[str, Any]) -> bool:
        return self.resolve_frozen_analysis_inputs(candidate) is not None

    def resolve_frozen_analysis_inputs(
        self,
        candidate: dict[str, Any],
    ) -> HeatRuntimeAnalysisInputs | None:
        birth_context = candidate.get("birth_context")
        if not isinstance(birth_context, dict):
            return None

        raw_bindings = birth_context.get("baseline_bindings_snapshot")
        if not isinstance(raw_bindings, list) or not raw_bindings:
            return None

        definition_metric_snapshots = self._extract_definition_metric_snapshots(candidate)
        baseline_curve_snapshots = self._extract_baseline_curve_snapshots(candidate)
        primary_baseline_id = str(birth_context.get("primary_baseline_id") or "").strip()

        applicable_baselines: list[dict[str, Any]] = []
        for binding in raw_bindings:
            if not isinstance(binding, dict):
                continue
            definition_id = str(binding.get("baseline_definition_id") or "").strip()
            item = str(binding.get("baseline_item") or "").strip()
            if not definition_id or not item:
                continue
            baseline_id = str(binding.get("baseline_id") or "").strip() or encode_baseline_id(
                definition_id,
                item,
            )
            applicable_baselines.append(
                {
                    "id": baseline_id,
                    "definition_id": definition_id,
                    "item": item,
                    "is_default": bool(binding.get("is_primary")) or baseline_id == primary_baseline_id,
                    "effective_from": binding.get("baseline_effective_from"),
                    "tolerance_percent": binding.get("tolerance_percent"),
                }
            )

        if not applicable_baselines:
            return None

        return HeatRuntimeAnalysisInputs(
            applicable_baselines=applicable_baselines,
            definition_metric_snapshots=definition_metric_snapshots,
            baseline_curve_snapshots=baseline_curve_snapshots,
            baseline_curve_payloads=self._build_baseline_curve_payloads(
                baseline_curve_snapshots=baseline_curve_snapshots,
            ),
        )

    def build_birth_snapshot(
        self,
        candidate: dict[str, Any],
        *,
        applicable_baselines: list[Any],
        definition_templates: list[Any],
        baseline_curve_payloads: dict[str, BaselineCurvePayload],
        cutting_config: HeatCuttingConfig,
    ) -> HeatRuntimeBirthSnapshot:
        definition_metric_snapshots = self._build_definition_metric_snapshots(definition_templates)
        baseline_curve_snapshots = self._build_baseline_curve_snapshots(
            applicable_baselines=applicable_baselines,
            baseline_curve_payloads=baseline_curve_payloads,
        )

        birth_context = {
            "heat_id": str(candidate.get("id") or ""),
            "channel_key": str(candidate.get("_live_context_key") or candidate.get("furnace_id") or "") or None,
            "cutting_mode": (
                str(candidate.get("_live_cutting_mode"))
                if candidate.get("_live_cutting_mode") is not None
                else None
            ),
            "expected_duration_minutes": (
                int(candidate.get("_live_expected_duration_minutes"))
                if candidate.get("_live_expected_duration_minutes") is not None
                else None
            ),
            "plant_timezone": (
                str(candidate.get("_live_plant_timezone"))
                if candidate.get("_live_plant_timezone") is not None
                else None
            ),
            "cutting_config_snapshot": self.serialize_cutting_config(cutting_config),
            "primary_baseline_id": str(candidate.get("baseline_id") or "").strip() or None,
            "baseline_bindings_snapshot": [
                dict(binding)
                for binding in (candidate.get("baseline_bindings") or [])
                if isinstance(binding, dict)
            ],
            "definition_metric_snapshots": [dict(snapshot) for snapshot in definition_metric_snapshots],
            "baseline_curve_snapshots": [dict(snapshot) for snapshot in baseline_curve_snapshots],
        }
        return HeatRuntimeBirthSnapshot(
            birth_context=birth_context,
            definition_metric_snapshots=definition_metric_snapshots,
            baseline_curve_snapshots=baseline_curve_snapshots,
        )

    def _extract_definition_metric_snapshots(
        self,
        candidate: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raw_birth_context = candidate.get("birth_context")
        raw_snapshots = candidate.get("definition_metric_snapshots")
        if isinstance(raw_birth_context, dict) and isinstance(
            raw_birth_context.get("definition_metric_snapshots"),
            list,
        ):
            raw_snapshots = raw_birth_context["definition_metric_snapshots"]
        if not isinstance(raw_snapshots, list):
            return []
        return [dict(snapshot) for snapshot in raw_snapshots if isinstance(snapshot, dict)]

    def _extract_baseline_curve_snapshots(
        self,
        candidate: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raw_birth_context = candidate.get("birth_context")
        raw_snapshots = candidate.get("baseline_curve_snapshots")
        if isinstance(raw_birth_context, dict) and isinstance(
            raw_birth_context.get("baseline_curve_snapshots"),
            list,
        ):
            raw_snapshots = raw_birth_context["baseline_curve_snapshots"]
        if not isinstance(raw_snapshots, list):
            return []
        return [dict(snapshot) for snapshot in raw_snapshots if isinstance(snapshot, dict)]

    def _build_definition_metric_snapshots(
        self,
        definition_templates: list[Any],
    ) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for template in definition_templates:
            item = str(_field(template, "item") or "").strip()
            metric_key = str(_field(template, "metric_key") or "").strip()
            metric_name = str(_field(template, "metric_name") or "").strip()
            color = str(_field(template, "color") or "").strip()
            if not item or not metric_key or not metric_name or not color:
                continue
            snapshots.append(
                {
                    "item": item,
                    "metric_key": metric_key,
                    "metric_name": metric_name,
                    "unit": _field(template, "unit"),
                    "color": color,
                    "sort_order": int(_field(template, "sort_order") or 0),
                    "edc_channel_id": _field(template, "edc_channel_id"),
                    "source_channel_name": _field(template, "source_channel_name"),
                    "source_channel_label": _field(template, "source_channel_label"),
                    "enabled": bool(
                        True if _field(template, "enabled") is None else _field(template, "enabled")
                    ),
                }
            )
        return snapshots

    def _build_baseline_curve_snapshots(
        self,
        *,
        applicable_baselines: list[Any],
        baseline_curve_payloads: dict[str, BaselineCurvePayload],
    ) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for baseline in applicable_baselines:
            definition_id = str(_field(baseline, "definition_id") or "").strip()
            item = str(_field(baseline, "item") or "").strip()
            if not definition_id or not item:
                continue
            baseline_id = str(_field(baseline, "id") or "").strip() or encode_baseline_id(
                definition_id,
                item,
            )
            payload = baseline_curve_payloads.get(
                baseline_id,
                BaselineCurvePayload(curves_by_metric={}, curve_source="none"),
            )
            for metric_key, points in payload.curves_by_metric.items():
                snapshots.append(
                    {
                        "baseline_id": baseline_id,
                        "metric_key": metric_key,
                        "curve_source": payload.curve_source,
                        "points": list(points),
                    }
                )
        return snapshots

    def _build_baseline_curve_payloads(
        self,
        *,
        baseline_curve_snapshots: list[dict[str, Any]],
    ) -> dict[str, BaselineCurvePayload]:
        grouped: dict[str, dict[str, Any]] = {}
        for snapshot in baseline_curve_snapshots:
            baseline_id = str(snapshot.get("baseline_id") or "").strip()
            metric_key = str(snapshot.get("metric_key") or "").strip().lower()
            if not baseline_id or not metric_key:
                continue
            payload = grouped.setdefault(
                baseline_id,
                {
                    "curves_by_metric": {},
                    "curve_source": str(snapshot.get("curve_source") or "none"),
                },
            )
            payload["curves_by_metric"][metric_key] = _coerce_curve_points(snapshot.get("points"))
            curve_source = str(snapshot.get("curve_source") or "").strip()
            if curve_source:
                payload["curve_source"] = curve_source

        return {
            baseline_id: BaselineCurvePayload(
                curves_by_metric=dict(payload["curves_by_metric"]),
                curve_source=str(payload["curve_source"] or "none"),
            )
            for baseline_id, payload in grouped.items()
        }
