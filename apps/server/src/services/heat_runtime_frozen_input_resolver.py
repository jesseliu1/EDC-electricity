"""解析 runtime 冻结分析输入，作为续刷唯一真源。"""

from __future__ import annotations

from typing import Any

from .formal_baseline_service import encode_baseline_id


def _field(item: Any, field_name: str) -> Any:
    if isinstance(item, dict):
        return item.get(field_name)
    return getattr(item, field_name, None)


def _normalize_metric_spec(snapshot: Any) -> dict[str, Any] | None:
    item = str(_field(snapshot, "item") or "").strip()
    metric_key = str(_field(snapshot, "metric_key") or "").strip().lower()
    metric_name = str(_field(snapshot, "metric_name") or "").strip()
    color = str(_field(snapshot, "color") or "").strip()
    if not item or not metric_key or not metric_name or not color:
        return None

    edc_channel_id = _field(snapshot, "edc_channel_id") or _field(snapshot, "source_channel_id")
    source_channel_id = _field(snapshot, "source_channel_id") or edc_channel_id
    return {
        "item": item,
        "metric_key": metric_key,
        "metric_name": metric_name,
        "unit": _field(snapshot, "unit"),
        "color": color,
        "sort_order": int(_field(snapshot, "sort_order") or 0),
        "edc_channel_id": str(edc_channel_id).strip() if edc_channel_id is not None else None,
        "source_channel_id": (
            str(source_channel_id).strip() if source_channel_id is not None else None
        ),
        "source_channel_name": _field(snapshot, "source_channel_name"),
        "source_channel_label": _field(snapshot, "source_channel_label"),
        "enabled": bool(True if _field(snapshot, "enabled") is None else _field(snapshot, "enabled")),
    }


def _definition_metric_snapshot_candidates(item: dict[str, Any]) -> list[list[dict[str, Any]]]:
    birth_context = item.get("birth_context")
    candidates: list[list[dict[str, Any]]] = []
    if isinstance(birth_context, dict) and isinstance(
        birth_context.get("definition_metric_snapshots"),
        list,
    ):
        candidates.append(
            [snapshot for snapshot in birth_context["definition_metric_snapshots"] if isinstance(snapshot, dict)]
        )
    if isinstance(item.get("definition_metric_snapshots"), list):
        candidates.append(
            [snapshot for snapshot in item["definition_metric_snapshots"] if isinstance(snapshot, dict)]
        )
    return candidates


def resolve_runtime_hydrate_specs_from_frozen_inputs(item: dict[str, Any]) -> list[dict[str, Any]]:
    """从冻结快照恢复 hydrate 所需的统一 metric specs。"""

    resolved: dict[str, dict[str, Any]] = {}
    for candidate_snapshots in _definition_metric_snapshot_candidates(item):
        for snapshot in candidate_snapshots:
            spec = _normalize_metric_spec(snapshot)
            if spec is None:
                continue
            metric_key = str(spec["metric_key"])
            existing = resolved.get(metric_key)
            if existing is None:
                resolved[metric_key] = spec
                continue
            merged = dict(existing)
            for field_name in (
                "edc_channel_id",
                "source_channel_id",
                "source_channel_name",
                "source_channel_label",
            ):
                if not merged.get(field_name) and spec.get(field_name):
                    merged[field_name] = spec.get(field_name)
            resolved[metric_key] = merged

    specs = list(resolved.values())
    if not specs:
        return []

    missing_channel_metric_keys = [
        str(spec.get("metric_key") or "")
        for spec in specs
        if not str(spec.get("edc_channel_id") or "").strip()
    ]
    if missing_channel_metric_keys:
        raise ValueError("runtime_frozen_metric_channel_missing")
    return specs


def _baseline_id_from_binding(binding: dict[str, Any]) -> str | None:
    baseline_id = str(binding.get("baseline_id") or "").strip()
    if baseline_id:
        return baseline_id
    definition_id = str(binding.get("baseline_definition_id") or "").strip()
    item = str(binding.get("baseline_item") or "").strip()
    if not definition_id or not item:
        return None
    return encode_baseline_id(definition_id, item)


def _baseline_id_from_runtime_baseline(baseline: Any) -> str | None:
    baseline_id = str(_field(baseline, "id") or "").strip()
    if baseline_id:
        return baseline_id
    definition_id = str(_field(baseline, "definition_id") or "").strip()
    item = str(_field(baseline, "item") or "").strip()
    if not definition_id or not item:
        return None
    return encode_baseline_id(definition_id, item)


def _baseline_ids_from_frozen_inputs(
    item: dict[str, Any],
    *,
    applicable_baselines: list[Any] | None = None,
) -> list[str]:
    baseline_ids: list[str] = []
    if applicable_baselines:
        for baseline in applicable_baselines:
            baseline_id = _baseline_id_from_runtime_baseline(baseline)
            if baseline_id and baseline_id not in baseline_ids:
                baseline_ids.append(baseline_id)
        if baseline_ids:
            return baseline_ids

    birth_context = item.get("birth_context")
    raw_bindings = (
        birth_context.get("baseline_bindings_snapshot")
        if isinstance(birth_context, dict)
        else item.get("baseline_bindings")
    )
    if isinstance(raw_bindings, list):
        for binding in raw_bindings:
            if not isinstance(binding, dict):
                continue
            baseline_id = _baseline_id_from_binding(binding)
            if baseline_id and baseline_id not in baseline_ids:
                baseline_ids.append(baseline_id)
    return baseline_ids


def resolve_runtime_baseline_metric_specs_from_frozen_inputs(
    item: dict[str, Any],
    *,
    applicable_baselines: list[Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """从冻结快照恢复 baseline -> metric specs 映射。"""

    union_specs = resolve_runtime_hydrate_specs_from_frozen_inputs(item)
    if not union_specs:
        return {}

    baseline_ids = _baseline_ids_from_frozen_inputs(item, applicable_baselines=applicable_baselines)
    if not baseline_ids:
        return {}

    birth_context = item.get("birth_context")
    raw_curve_snapshots = (
        birth_context.get("baseline_curve_snapshots")
        if isinstance(birth_context, dict)
        else item.get("baseline_curve_snapshots")
    )
    metric_keys_by_baseline: dict[str, set[str]] = {}
    if isinstance(raw_curve_snapshots, list):
        for snapshot in raw_curve_snapshots:
            if not isinstance(snapshot, dict):
                continue
            baseline_id = str(snapshot.get("baseline_id") or "").strip()
            metric_key = str(snapshot.get("metric_key") or "").strip().lower()
            if not baseline_id or not metric_key:
                continue
            metric_keys_by_baseline.setdefault(baseline_id, set()).add(metric_key)

    resolved: dict[str, list[dict[str, Any]]] = {}
    for baseline_id in baseline_ids:
        metric_keys = metric_keys_by_baseline.get(baseline_id)
        if metric_keys:
            specs = [
                dict(spec)
                for spec in union_specs
                if str(spec.get("metric_key") or "").strip().lower() in metric_keys
            ]
        else:
            specs = [dict(spec) for spec in union_specs]
        if specs:
            resolved[baseline_id] = specs
    return resolved
