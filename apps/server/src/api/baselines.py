"""基线 API 路由（黄金基线实例）"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from ..mock_dataset import is_mock_dataset_enabled
from ..runtime_state import persist_runtime_state
from ..schemas import (
    BaselineCreate,
    BaselineListResponse,
    BaselineResponse,
    BaselineSummary,
    BaselineUpdate,
    BaselineWithCurve,
    CurveData,
    MessageResponse,
)
from ..schemas.common import CurvePoint
from ..services import EDCClient, EDCClientError

# 引用 definition store 以做关联校验
from .baseline_definitions import _DEFINITION_STORE
from .settings import _HOST_CHANNEL_STORE, _SETTINGS_STORE, get_edc_connection_config

router = APIRouter(prefix="/baselines", tags=["Baselines"])


def _build_curve(seed: int, length: int = 100) -> list[dict[str, float]]:
    """生成稳定的演示曲线数据。"""
    return [
        {"timestamp": 1000.0 * i, "value": float(430 + ((i + seed) % 12) * 3)}
        for i in range(length)
    ]


def _build_curves_data(definition_id: str, seed: int) -> list[dict[str, Any]]:
    """根据定义的指标生成动态曲线数据。"""
    definition = _DEFINITION_STORE.get(definition_id)
    if not definition:
        return []

    curves = []
    for idx, metric in enumerate(definition["metrics"]):
        points = _build_curve(seed + idx * 2)
        host_channel = _resolve_host_channel(metric.get("edc_channel_id"))
        curves.append(
            {
                "metric_id": metric["id"],
                "metric_name": metric["name"],
                "unit": metric["unit"],
                "color": metric["color"],
                "edc_channel_id": metric.get("edc_channel_id"),
                "source_channel_name": host_channel["channel_name"] if host_channel else None,
                "source_channel_label": _format_host_channel_label(host_channel),
                "points": points,
            }
        )
    return curves


def _curve_points_to_dicts(points: list[CurvePoint]) -> list[dict[str, float | int]]:
    """将 Pydantic 曲线点转回存储结构。"""
    return [point.model_dump() for point in points]


def _get_definition_name(definition_id: str) -> str:
    """获取定义名称。"""
    definition = _DEFINITION_STORE.get(definition_id)
    return definition["definition_name"] if definition else ""


def _resolve_host_channel(channel_id: str | None) -> dict[str, str] | None:
    if not channel_id:
        return None
    return next((item for item in _HOST_CHANNEL_STORE if item["id"] == channel_id), None)


def _format_host_channel_label(channel: dict[str, str] | None) -> str | None:
    if not channel:
        return None
    return (
        f'{channel["device_name"]} / '
        f'{channel["channel_name"]} / '
        f'{channel["unit"] or "--"}'
    )


def _now() -> datetime:
    return datetime.now()


def _resolve_curve_seed(item: dict[str, Any], fallback: int = 1) -> int:
    seed = item.get("curve_seed")
    if isinstance(seed, int):
        return seed

    item_id = str(item.get("id") or "")
    if not item_id:
        return fallback

    return sum(ord(char) for char in item_id) % 97 + fallback


def _empty_curve_payload() -> dict[str, Any]:
    return {
        "power_curve": [],
        "voltage_curve": [],
        "curves_data": [],
        "curve_source": "none",
    }


def _build_demo_curve_payload(item: dict[str, Any]) -> dict[str, Any]:
    seed = _resolve_curve_seed(item)
    definition_id = str(item.get("definition_id") or "")
    curves_data = _build_curves_data(definition_id, seed)
    power_curve = next(
        (
            curve["points"]
            for curve in curves_data
            if "功率" in str(curve.get("metric_name") or "") or str(curve.get("unit") or "") == "kW"
        ),
        _build_curve(seed),
    )
    voltage_curve = next(
        (
            curve["points"]
            for curve in curves_data
            if (
                "电压" in str(curve.get("metric_name") or "")
                or "電壓" in str(curve.get("metric_name") or "")
                or str(curve.get("unit") or "") == "V"
            )
        ),
        _build_curve(seed + 2),
    )
    return {
        "power_curve": power_curve,
        "voltage_curve": voltage_curve,
        "curves_data": curves_data,
        "curve_source": "demo_curve",
    }


def _with_curve_payload(item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(item)
    hydrated["power_curve"] = payload.get("power_curve", [])
    hydrated["voltage_curve"] = payload.get("voltage_curve", [])
    hydrated["curves_data"] = payload.get("curves_data", [])
    hydrated["curve_source"] = payload.get("curve_source", "none")
    return hydrated


_BASELINE_STORE: dict[str, dict[str, Any]] = {
    "baseline-001": {
        "id": "baseline-001",
        "name": "标准基线 v2.1",
        "description": "2024年优化后的标准生产基线",
        "definition_id": "def-001",
        "source_heat_id": "heat-ref-001",
        "selected_start_time": None,
        "selected_end_time": None,
        "tolerance_percent": 15.0,
        "status": "published",
        "version": 2,
        "curve_seed": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "published_at": _now(),
        "power_curve": [],
        "voltage_curve": [],
        "temperature": 1450.0,
        "curve_source": "none",
        "curves_data": [],
    },
    "baseline-002": {
        "id": "baseline-002",
        "name": "高功率基线",
        "description": "高功率生产模式基线",
        "definition_id": "def-002",
        "source_heat_id": "heat-ref-002",
        "selected_start_time": None,
        "selected_end_time": None,
        "tolerance_percent": 12.0,
        "status": "draft",
        "version": 1,
        "curve_seed": 5,
        "created_at": _now(),
        "updated_at": _now(),
        "published_at": None,
        "power_curve": [],
        "voltage_curve": [],
        "temperature": 1460.0,
        "curve_source": "none",
        "curves_data": [],
    },
}


def _published_baselines() -> list[dict[str, Any]]:
    published = [item for item in _BASELINE_STORE.values() if item["status"] == "published"]
    published.sort(key=lambda item: item["published_at"] or item["updated_at"], reverse=True)
    return published


def _resolve_active_baseline_item() -> dict[str, Any] | None:
    active_baseline_id = _SETTINGS_STORE.get("active_baseline_id", {}).get("value")
    if isinstance(active_baseline_id, str) and active_baseline_id:
        active_item = _BASELINE_STORE.get(active_baseline_id)
        if active_item and active_item["status"] == "published":
            return active_item

    published = _published_baselines()
    return published[0] if published else None


def _to_baseline_response(item: dict[str, Any]) -> BaselineResponse:
    return BaselineResponse(
        id=item["id"],
        name=item["name"],
        description=item["description"],
        definition_id=item["definition_id"],
        definition_name=_get_definition_name(item["definition_id"]),
        source_heat_id=item["source_heat_id"],
        selected_start_time=item.get("selected_start_time"),
        selected_end_time=item.get("selected_end_time"),
        tolerance_percent=item["tolerance_percent"],
        status=item["status"],
        version=item["version"],
        curve_source=str(item.get("curve_source") or "none"),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        published_at=item["published_at"],
    )


def _to_baseline_with_curve(item: dict[str, Any]) -> BaselineWithCurve:
    curves_data = [
        CurveData(
            metric_id=curve["metric_id"],
            metric_name=curve["metric_name"],
            unit=curve["unit"],
            color=curve["color"],
            edc_channel_id=curve.get("edc_channel_id"),
            source_channel_name=curve.get("source_channel_name"),
            source_channel_label=curve.get("source_channel_label"),
            points=curve["points"],
        )
        for curve in item.get("curves_data", [])
    ]

    return BaselineWithCurve(
        id=item["id"],
        name=item["name"],
        description=item["description"],
        definition_id=item["definition_id"],
        definition_name=_get_definition_name(item["definition_id"]),
        source_heat_id=item["source_heat_id"],
        selected_start_time=item.get("selected_start_time"),
        selected_end_time=item.get("selected_end_time"),
        tolerance_percent=item["tolerance_percent"],
        status=item["status"],
        version=item["version"],
        curve_source=str(item.get("curve_source") or "none"),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        published_at=item["published_at"],
        curves_data=curves_data,
        power_curve=item.get("power_curve", []),
        voltage_curve=item.get("voltage_curve", []),
        temperature=item.get("temperature"),
    )


async def _resolve_baseline_time_window(item: dict[str, Any]) -> tuple[datetime, datetime]:
    """优先按选区时间，其次按来源炉次时间，最后回退最近一小时。"""
    selected_start = item.get("selected_start_time")
    selected_end = item.get("selected_end_time")
    if isinstance(selected_start, datetime) and isinstance(selected_end, datetime):
        return selected_start, selected_end

    from .heats import (
        _HEAT_STORE,
        _parse_live_heat_id,
        build_live_heat_lookup_context,
        resolve_heat_time_window,
    )

    source_heat_id = str(item.get("source_heat_id") or "").strip()
    if (
        not is_mock_dataset_enabled()
        and source_heat_id
        and source_heat_id not in _HEAT_STORE
        and _parse_live_heat_id(source_heat_id) is None
    ):
        end_time = datetime.now()
        return end_time - timedelta(hours=1), end_time

    preferred_live_context = build_live_heat_lookup_context(
        definition_id=str(item.get("definition_id") or "") or None
    )
    source_window = await resolve_heat_time_window(
        source_heat_id,
        preferred_live_context=preferred_live_context,
    )
    if source_window:
        return source_window

    end_time = datetime.now()
    return end_time - timedelta(hours=1), end_time


async def _load_baseline_curves_from_edc(
    item: dict[str, Any],
) -> dict[str, list[dict[str, Any]]] | None:
    """按基线定义绑定通道尝试拉取真实基线曲线。"""
    definition = _DEFINITION_STORE.get(str(item.get("definition_id")))
    metrics = list(definition.get("metrics", [])) if definition else []
    if not metrics:
        return None

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return None

    start_time, end_time = await _resolve_baseline_time_window(item)
    bound_metrics: list[tuple[dict[str, Any], dict[str, str]]] = []
    for metric in metrics:
        channel = _resolve_host_channel(metric.get("edc_channel_id"))
        if channel:
            bound_metrics.append((metric, channel))

    if not bound_metrics:
        return None

    try:
        async with EDCClient(**config) as client:
            tasks = {
                str(metric["id"]): asyncio.create_task(
                    client.get_local_datas(
                        suid=channel["suid"],
                        cuid=channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
                for metric, channel in bound_metrics
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    except EDCClientError:
        return None

    points_by_metric: dict[str, list[CurvePoint]] = {}
    for metric_id, result in zip(tasks.keys(), results, strict=False):
        if isinstance(result, Exception) or not result:
            continue
        points_by_metric[metric_id] = result

    if not points_by_metric:
        return None

    hydrated_curves: list[dict[str, Any]] = []
    power_curve: list[dict[str, float | int]] = []
    voltage_curve: list[dict[str, float | int]] = []

    for metric in metrics:
        metric_id = str(metric["id"])
        host_channel = _resolve_host_channel(metric.get("edc_channel_id"))
        points = points_by_metric.get(metric_id)
        if points:
            stored_points = _curve_points_to_dicts(points)
        else:
            stored_points = []

        metric_name = str(metric.get("name") or "")
        unit = str(metric.get("unit") or "")
        hydrated_curves.append(
            {
                "metric_id": metric_id,
                "metric_name": metric_name,
                "unit": unit,
                "color": metric["color"],
                "edc_channel_id": metric.get("edc_channel_id"),
                "source_channel_name": host_channel["channel_name"] if host_channel else None,
                "source_channel_label": _format_host_channel_label(host_channel),
                "points": stored_points,
            }
        )

        if ("功率" in metric_name or unit == "kW") and stored_points:
            power_curve = stored_points
        if ("电压" in metric_name or "電壓" in metric_name or unit == "V") and stored_points:
            voltage_curve = stored_points

    return {
        "curves_data": hydrated_curves,
        "power_curve": power_curve,
        "voltage_curve": voltage_curve,
        "curve_source": "live_edc" if points_by_metric else "none",
    }


async def _hydrate_baseline_item(item: dict[str, Any]) -> dict[str, Any]:
    """为当前请求解析基线曲线来源，不把 showtime 演示曲线污染回共享 store。"""
    curves = await _load_baseline_curves_from_edc(item)
    if curves:
        return _with_curve_payload(item, curves)

    if is_mock_dataset_enabled():
        return _with_curve_payload(item, _build_demo_curve_payload(item))

    return _with_curve_payload(item, _empty_curve_payload())


def _get_or_404(baseline_id: str) -> dict[str, Any]:
    item = _BASELINE_STORE.get(baseline_id)
    if not item:
        raise HTTPException(status_code=404, detail="基线不存在")
    return item


def _validate_definition(definition_id: str) -> dict[str, Any]:
    """校验定义存在且为 active 状态。"""
    definition = _DEFINITION_STORE.get(definition_id)
    if not definition:
        raise HTTPException(status_code=400, detail="基线定义不存在")
    if definition["status"] != "active":
        raise HTTPException(status_code=400, detail="基线定义已停用，无法创建实例")
    return definition


def _validate_equal_length(definition_id: str, current_id: str | None = None) -> None:
    """按配置范围校验已发布实例曲线长度一致性。"""
    scope_mode = str(
        _SETTINGS_STORE.get("baseline_length_scope_mode", {}).get("value") or "definition"
    )

    def scope_key(item: dict[str, Any]) -> str:
        if scope_mode == "system":
            return "system"
        if scope_mode == "production_line":
            # 生产线字段预留：MVP 先不引生产线，缺省回落到定义维度
            production_line = item.get("production_line_id")
            if production_line:
                return f"production_line:{production_line}"
        return f"definition:{item['definition_id']}"

    current_item = _BASELINE_STORE.get(current_id) if current_id else None
    current_scope = scope_key(current_item) if current_item else f"definition:{definition_id}"

    published = [
        item
        for item in _BASELINE_STORE.values()
        if item["status"] == "published"
        and item["id"] != current_id
        and scope_key(item) == current_scope
    ]
    if len(published) < 2:
        return

    first = published[0].get("curves_data", [])
    if not first:
        return

    first_lengths = [len(c["points"]) for c in first]
    for item in published[1:]:
        curves = item.get("curves_data", [])
        lengths = [len(c["points"]) for c in curves]
        if lengths != first_lengths:
            raise HTTPException(status_code=400, detail="同一定义下黄金基线实例曲线长度不一致")


def _invalidate_compare_runtime_caches() -> None:
    from .heats import invalidate_compare_runtime_caches

    invalidate_compare_runtime_caches(include_shared=True)


@router.get("", response_model=BaselineListResponse)
async def list_baselines(
    status: Literal["draft", "published", "disabled"] | None = Query(
        default=None, description="状态筛选"
    ),
    definition_id: str | None = Query(default=None, description="基线定义ID筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> BaselineListResponse:
    """获取基线列表，支持状态筛选与分页。"""
    items = list(_BASELINE_STORE.values())
    items.sort(key=lambda x: x["updated_at"], reverse=True)

    if status:
        items = [item for item in items if item["status"] == status]

    if definition_id:
        items = [item for item in items if item["definition_id"] == definition_id]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paged = items[start:end]

    return BaselineListResponse(items=[_to_baseline_response(x) for x in paged], total=total)


@router.get("/active", response_model=BaselineSummary | None)
async def get_active_baseline() -> BaselineSummary | None:
    """获取当前激活基线。"""
    active = _resolve_active_baseline_item()
    if not active:
        return None

    return BaselineSummary(
        id=active["id"],
        name=active["name"],
        status=active["status"],
        version=active["version"],
    )


@router.post("/{baseline_id}/activate", response_model=BaselineSummary)
async def activate_baseline(baseline_id: str) -> BaselineSummary:
    """设置默认黄金基线。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "published":
        raise HTTPException(status_code=400, detail="仅已发布基线可设为默认黄金基线")

    _SETTINGS_STORE["active_baseline_id"]["value"] = baseline_id
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("settings_store")
    return BaselineSummary(
        id=item["id"],
        name=item["name"],
        status=item["status"],
        version=item["version"],
    )


@router.get("/{baseline_id}", response_model=BaselineWithCurve)
async def get_baseline(baseline_id: str) -> BaselineWithCurve:
    """获取基线详情（含曲线数据）。"""
    item = _get_or_404(baseline_id)
    hydrated = await _hydrate_baseline_item(item)
    return _to_baseline_with_curve(hydrated)


@router.post("", response_model=BaselineResponse, status_code=201)
async def create_baseline(data: BaselineCreate) -> BaselineResponse:
    """创建新基线实例，默认草稿状态。"""
    _validate_definition(data.definition_id)

    from .heats import build_live_heat_lookup_context, resolve_heat_record

    preferred_live_context = build_live_heat_lookup_context(definition_id=data.definition_id)
    source_heat = await resolve_heat_record(
        data.source_heat_id,
        preferred_live_context=preferred_live_context,
    )
    if not source_heat:
        raise HTTPException(status_code=400, detail="来源炉次不存在")

    now = _now()
    baseline_id = f"baseline-{uuid4()}"
    item = {
        "id": baseline_id,
        "name": data.name,
        "description": data.description,
        "definition_id": data.definition_id,
        "source_heat_id": str(source_heat["id"]),
        "selected_start_time": data.selected_start_time,
        "selected_end_time": data.selected_end_time,
        "tolerance_percent": data.tolerance_percent,
        "status": "draft",
        "version": 1,
        "curve_seed": sum(ord(char) for char in baseline_id) % 97 + 9,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "power_curve": [],
        "voltage_curve": [],
        "temperature": 1455.0,
        "curve_source": "none",
        "curves_data": [],
    }
    _BASELINE_STORE[baseline_id] = item
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")
    return _to_baseline_response(item)


@router.patch("/{baseline_id}", response_model=BaselineResponse)
async def update_baseline(baseline_id: str, data: BaselineUpdate) -> BaselineResponse:
    """更新基线，仅草稿状态允许更新。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可编辑")

    if data.name is not None:
        item["name"] = data.name
    if data.description is not None:
        item["description"] = data.description
    if data.selected_start_time is not None:
        item["selected_start_time"] = data.selected_start_time
    if data.selected_end_time is not None:
        item["selected_end_time"] = data.selected_end_time
    if data.tolerance_percent is not None:
        item["tolerance_percent"] = data.tolerance_percent
    item["updated_at"] = _now()
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")

    return _to_baseline_response(item)


@router.post("/{baseline_id}/publish", response_model=BaselineResponse)
async def publish_baseline(baseline_id: str) -> BaselineResponse:
    """发布草稿基线。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可发布")

    _validate_equal_length(item["definition_id"], current_id=baseline_id)

    now = _now()
    item["status"] = "published"
    item["published_at"] = now
    item["updated_at"] = now
    active_item = _resolve_active_baseline_item()
    if active_item is None:
        _SETTINGS_STORE["active_baseline_id"]["value"] = baseline_id
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines", "settings_store")

    return _to_baseline_response(item)


@router.post("/{baseline_id}/disable", response_model=BaselineResponse)
async def disable_baseline(baseline_id: str) -> BaselineResponse:
    """停用已发布基线。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "published":
        raise HTTPException(status_code=400, detail="仅已发布基线可停用")

    item["status"] = "disabled"
    item["updated_at"] = _now()
    if _SETTINGS_STORE.get("active_baseline_id", {}).get("value") == baseline_id:
        next_active = _resolve_active_baseline_item()
        _SETTINGS_STORE["active_baseline_id"]["value"] = (
            str(next_active["id"]) if next_active else ""
        )
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines", "settings_store")

    return _to_baseline_response(item)


@router.delete("/{baseline_id}", response_model=MessageResponse)
async def delete_baseline(baseline_id: str) -> MessageResponse:
    """删除基线，仅草稿状态允许删除。"""
    item = _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可删除")

    _BASELINE_STORE.pop(baseline_id, None)
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")
    return MessageResponse(message="基线已删除", success=True)
