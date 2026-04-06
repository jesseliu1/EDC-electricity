"""基线 API 路由（黄金基线实例）"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Literal

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
from ..services import (
    EDCClientError,
    create_baseline_record,
    decode_baseline_id,
    delete_baseline_record,
    get_baseline_record,
    get_definition_record,
    get_shared_edc_client,
    list_baseline_records,
    load_baseline_metric_series,
    load_baseline_store,
    replace_baseline_metric_series,
    set_default_baseline,
    set_baseline_status,
    update_baseline_record,
)
from ..time_utils import plant_date_of, plant_day_bounds_datetime, utc_now

# 引用 definition store 以做关联校验
from .baseline_definitions import (
    _DEFINITION_STORE,
    _build_preview_curves,
    _preview_curves_have_points,
    _reload_definition_store,
)
from .settings import _HOST_CHANNEL_STORE, _SETTINGS_STORE, get_edc_connection_config, get_plant_timezone

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
    return utc_now()


def _validate_selection_window(
    *,
    selected_start_time: datetime,
    selected_end_time: datetime,
) -> None:
    if selected_start_time > selected_end_time:
        raise HTTPException(status_code=400, detail="基线选区开始时间不能晚于结束时间")
    if plant_date_of(selected_start_time, get_plant_timezone()) != plant_date_of(
        selected_end_time,
        get_plant_timezone(),
    ):
        raise HTTPException(status_code=400, detail="基线选区必须位于同一个业务日内")


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


_BASELINE_STORE: dict[str, dict[str, Any]] = {}


async def _reload_baseline_store() -> None:
    store = await load_baseline_store()
    _BASELINE_STORE.clear()
    _BASELINE_STORE.update(store)


def _published_baselines() -> list[dict[str, Any]]:
    published = [item for item in _BASELINE_STORE.values() if item["status"] == "published"]
    published.sort(key=lambda item: item["published_at"] or item["updated_at"], reverse=True)
    return published


def _resolve_active_baseline_item() -> dict[str, Any] | None:
    active_items = [
        item
        for item in _BASELINE_STORE.values()
        if item["status"] == "published" and bool(item.get("is_default"))
    ]
    if not active_items:
        return None
    active_items.sort(
        key=lambda item: (item.get("published_at") or item["updated_at"], item["updated_at"]),
        reverse=True,
    )
    return active_items[0]


def _resolve_next_active_baseline_item(excluded_id: str | None = None) -> dict[str, Any] | None:
    for item in _published_baselines():
        if excluded_id and item["id"] == excluded_id:
            continue
        return item
    return None


def _to_baseline_response(item: dict[str, Any]) -> BaselineResponse:
    return BaselineResponse(
        id=item["id"],
        name=item["name"],
        description=item["description"],
        definition_id=item["definition_id"],
        definition_name=_get_definition_name(item["definition_id"]),
        is_default=bool(item.get("is_default")),
        source_heat_id=item["source_heat_id"],
        selected_start_time=item.get("selected_start_time"),
        selected_end_time=item.get("selected_end_time"),
        effective_from=item.get("effective_from"),
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
        is_default=bool(item.get("is_default")),
        source_heat_id=item["source_heat_id"],
        selected_start_time=item.get("selected_start_time"),
        selected_end_time=item.get("selected_end_time"),
        effective_from=item.get("effective_from"),
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

    from .heats import build_live_heat_lookup_context, resolve_heat_time_window

    source_heat_id = str(item.get("source_heat_id") or "").strip()
    if source_heat_id:
        preferred_live_context = build_live_heat_lookup_context(
            definition_id=str(item.get("definition_id") or "") or None
        )
        source_window = await resolve_heat_time_window(
            source_heat_id,
            preferred_live_context=preferred_live_context,
        )
        if source_window:
            return source_window

    end_time = utc_now()
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
        client = await get_shared_edc_client(**config)
        await client.login()
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
    stored_curves = await load_baseline_metric_series(
        str(item.get("definition_id") or ""),
        str(item.get("item") or ""),
    )
    if stored_curves.get("curves_data"):
        return _with_curve_payload(item, stored_curves)

    if is_mock_dataset_enabled():
        return _with_curve_payload(item, _build_demo_curve_payload(item))

    return _with_curve_payload(item, _empty_curve_payload())


async def _get_or_404(baseline_id: str) -> dict[str, Any]:
    try:
        definition_id, item = decode_baseline_id(baseline_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="基线不存在") from exc
    record = await get_baseline_record(definition_id, item)
    if record is None:
        await _reload_baseline_store()
        record = _BASELINE_STORE.get(baseline_id)
    item = record
    if not item:
        raise HTTPException(status_code=404, detail="基线不存在")
    return item


async def _get_definition_or_400(definition_id: str) -> dict[str, Any]:
    definition = await get_definition_record(definition_id)
    if not definition:
        raise HTTPException(status_code=400, detail="基线定义不存在")
    return definition


async def _validate_definition(definition_id: str) -> dict[str, Any]:
    """校验定义存在且为 active 状态。"""
    definition = await _get_definition_or_400(definition_id)
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


def _normalize_source_heat_id(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _serialize_preview_curves(curves: list[CurveData]) -> list[dict[str, Any]]:
    return [curve.model_dump() for curve in curves]


async def _load_preview_curves_for_selection(
    *,
    definition_id: str,
    selected_start_time: datetime,
    selected_end_time: datetime,
) -> list[dict[str, Any]]:
    definition = await _get_definition_or_400(definition_id)
    range_start, range_end = plant_day_bounds_datetime(
        selected_start_time,
        get_plant_timezone(),
    )
    preview_curves = await _build_preview_curves(
        definition=definition,
        range_start=range_start,
        range_end=range_end,
    )
    if not _preview_curves_have_points(preview_curves):
        raise HTTPException(
            status_code=503,
            detail="未获取到真实预览数据，请检查宿主连接和通道绑定",
        )
    return _serialize_preview_curves(preview_curves)


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
    items, total = await list_baseline_records(
        status=status,
        definition_id=definition_id,
        page=page,
        page_size=page_size,
    )
    await _reload_definition_store()
    await _reload_baseline_store()
    return BaselineListResponse(items=[_to_baseline_response(x) for x in items], total=total)


@router.get("/active", response_model=BaselineSummary | None)
async def get_active_baseline() -> BaselineSummary | None:
    """获取当前激活基线。"""
    await _reload_definition_store()
    await _reload_baseline_store()
    active = _resolve_active_baseline_item()
    if not active:
        return None

    return BaselineSummary(
        id=active["id"],
        name=active["name"],
        status=active["status"],
        version=active["version"],
        is_default=bool(active.get("is_default")),
    )


@router.post("/{baseline_id}/activate", response_model=BaselineSummary)
async def activate_baseline(baseline_id: str) -> BaselineSummary:
    """设置默认黄金基线。"""
    item = await _get_or_404(baseline_id)
    if item["status"] != "published":
        raise HTTPException(status_code=400, detail="仅已发布基线可设为默认黄金基线")

    definition_id, item_no = decode_baseline_id(baseline_id)
    updated = await set_default_baseline(
        definition_id=definition_id,
        item=item_no,
        actor="system",
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="基线不存在")
    await _reload_baseline_store()
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")
    return BaselineSummary(
        id=updated["id"],
        name=updated["name"],
        status=updated["status"],
        version=updated["version"],
        is_default=bool(updated.get("is_default")),
    )


@router.get("/{baseline_id}", response_model=BaselineWithCurve)
async def get_baseline(baseline_id: str) -> BaselineWithCurve:
    """获取基线详情（含曲线数据）。"""
    await _reload_definition_store()
    item = await _get_or_404(baseline_id)
    hydrated = await _hydrate_baseline_item(item)
    return _to_baseline_with_curve(hydrated)


@router.post("", response_model=BaselineResponse, status_code=201)
async def create_baseline(data: BaselineCreate) -> BaselineResponse:
    """创建新基线实例，默认草稿状态。"""
    await _validate_definition(data.definition_id)
    if data.is_default:
        raise HTTPException(status_code=400, detail="草稿基线不能直接设置为默认黄金基线")
    selected_start_time = data.selected_start_time
    selected_end_time = data.selected_end_time
    _validate_selection_window(
        selected_start_time=selected_start_time,
        selected_end_time=selected_end_time,
    )
    preview_curves = await _load_preview_curves_for_selection(
        definition_id=data.definition_id,
        selected_start_time=selected_start_time,
        selected_end_time=selected_end_time,
    )

    source_heat_id = _normalize_source_heat_id(data.source_heat_id)
    if source_heat_id:
        from .heats import build_live_heat_lookup_context, resolve_heat_record

        preferred_live_context = build_live_heat_lookup_context(definition_id=data.definition_id)
        source_heat = await resolve_heat_record(
            source_heat_id,
            preferred_live_context=preferred_live_context,
        )
        if not source_heat:
            raise HTTPException(status_code=400, detail="来源炉次不存在")
        source_heat_id = str(source_heat["id"])

    item = await create_baseline_record(
        definition_id=data.definition_id,
        name=data.name,
        description=data.description,
        source_heat_id=source_heat_id,
        selected_start_time=selected_start_time,
        selected_end_time=selected_end_time,
        effective_from=data.effective_from,
        tolerance_percent=data.tolerance_percent,
        is_default=False,
        actor="system",
    )
    await replace_baseline_metric_series(
        definition_id=data.definition_id,
        item=str(item["item"]),
        source_curves_data=preview_curves,
        selected_start_time=selected_start_time,
        selected_end_time=selected_end_time,
    )
    item = await get_baseline_record(data.definition_id, str(item["item"])) or item
    await _reload_definition_store()
    await _reload_baseline_store()
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")
    return _to_baseline_response(item)


@router.patch("/{baseline_id}", response_model=BaselineResponse)
async def update_baseline(baseline_id: str, data: BaselineUpdate) -> BaselineResponse:
    """更新基线，仅草稿状态允许更新。"""
    item = await _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可编辑")
    if data.is_default is not None:
        raise HTTPException(status_code=400, detail="草稿基线不能设置默认黄金基线")
    definition_id, item_no = decode_baseline_id(baseline_id)

    next_selected_start_time = data.selected_start_time or item.get("selected_start_time")
    next_selected_end_time = data.selected_end_time or item.get("selected_end_time")
    if not isinstance(next_selected_start_time, datetime) or not isinstance(
        next_selected_end_time, datetime
    ):
        raise HTTPException(status_code=400, detail="基线选区时间不能为空")

    _validate_selection_window(
        selected_start_time=next_selected_start_time,
        selected_end_time=next_selected_end_time,
    )

    selection_changed = (
        data.selected_start_time is not None or data.selected_end_time is not None
    ) and (
        next_selected_start_time != item.get("selected_start_time")
        or next_selected_end_time != item.get("selected_end_time")
    )
    preview_curves: list[dict[str, Any]] | None = None
    if selection_changed:
        preview_curves = await _load_preview_curves_for_selection(
            definition_id=definition_id,
            selected_start_time=next_selected_start_time,
            selected_end_time=next_selected_end_time,
        )

    item = await update_baseline_record(
        definition_id=definition_id,
        item=item_no,
        name=data.name,
        description=data.description,
        selected_start_time=data.selected_start_time,
        selected_end_time=data.selected_end_time,
        effective_from=data.effective_from,
        tolerance_percent=data.tolerance_percent,
        is_default=None,
        actor="system",
    )
    if not item:
        raise HTTPException(status_code=404, detail="基线不存在")
    if selection_changed and preview_curves is not None:
        await replace_baseline_metric_series(
            definition_id=definition_id,
            item=item_no,
            source_curves_data=preview_curves,
            selected_start_time=item["selected_start_time"],
            selected_end_time=item["selected_end_time"],
        )
        item = await get_baseline_record(definition_id, item_no) or item
    await _reload_definition_store()
    await _reload_baseline_store()
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")

    return _to_baseline_response(item)


@router.post("/{baseline_id}/publish", response_model=BaselineResponse)
async def publish_baseline(baseline_id: str) -> BaselineResponse:
    """发布草稿基线。"""
    item = await _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可发布")

    _validate_equal_length(item["definition_id"], current_id=baseline_id)

    now = _now()
    definition_id, item_no = decode_baseline_id(baseline_id)
    item = await set_baseline_status(
        definition_id=definition_id,
        item=item_no,
        status="published",
        actor="system",
        publish_time=now,
        effective_from=item.get("effective_from") if isinstance(item.get("effective_from"), datetime) else now,
        is_default=False,
    )
    if not item:
        raise HTTPException(status_code=404, detail="基线不存在")
    await _reload_definition_store()
    await _reload_baseline_store()
    if _resolve_active_baseline_item() is None:
        default_item = await activate_baseline(baseline_id)
        await _reload_baseline_store()
        item = await _get_or_404(default_item.id)
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")

    return _to_baseline_response(item)


@router.post("/{baseline_id}/disable", response_model=BaselineResponse)
async def disable_baseline(baseline_id: str) -> BaselineResponse:
    """停用已发布基线。"""
    item = await _get_or_404(baseline_id)
    if item["status"] != "published":
        raise HTTPException(status_code=400, detail="仅已发布基线可停用")
    was_default = bool(item.get("is_default"))

    definition_id, item_no = decode_baseline_id(baseline_id)
    item = await set_baseline_status(
        definition_id=definition_id,
        item=item_no,
        status="disabled",
        actor="system",
    )
    if not item:
        raise HTTPException(status_code=404, detail="基线不存在")
    await _reload_definition_store()
    await _reload_baseline_store()
    if was_default:
        next_active = _resolve_next_active_baseline_item(excluded_id=baseline_id)
        if next_active:
            next_definition_id, next_item_no = decode_baseline_id(str(next_active["id"]))
            await set_default_baseline(
                definition_id=next_definition_id,
                item=next_item_no,
                actor="system",
            )
            await _reload_baseline_store()
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")

    return _to_baseline_response(item)


@router.delete("/{baseline_id}", response_model=MessageResponse)
async def delete_baseline(baseline_id: str) -> MessageResponse:
    """删除基线，仅草稿状态允许删除。"""
    item = await _get_or_404(baseline_id)
    if item["status"] != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可删除")

    definition_id, item_no = decode_baseline_id(baseline_id)
    deleted = await delete_baseline_record(definition_id, item_no)
    if not deleted:
        raise HTTPException(status_code=404, detail="基线不存在")
    await _reload_baseline_store()
    _invalidate_compare_runtime_caches()
    await persist_runtime_state("baselines")
    return MessageResponse(message="基线已删除", success=True)
