"""仪表盘 API 路由"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Literal

from fastapi import APIRouter, HTTPException

from ..observability import log_event
from ..schemas import DashboardStats, RecentHeat, RecentHeatsResponse
from ..schemas.common import CurvePoint
from ..services import EDCClient, EDCClientError
from .baseline_definitions import _DEFINITION_STORE
from .baselines import _BASELINE_STORE
from .settings import _HOST_CHANNEL_STORE, _SETTINGS_STORE, get_edc_connection_config

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DASHBOARD_REALTIME_EDC_TIMEOUT_SECONDS = 8.0


async def _sorted_dashboard_heats() -> list[dict[str, Any]]:
    from . import heats as heats_api

    items = list((await heats_api._list_heat_store()).values())
    items.sort(key=lambda item: item["start_time"], reverse=True)
    return items


def _resolve_host_channel(channel_id: str | None) -> dict[str, str] | None:
    if not channel_id:
        return None
    return next((item for item in _HOST_CHANNEL_STORE if item["id"] == channel_id), None)


def _format_host_channel_label(channel: dict[str, str] | None) -> str | None:
    if not channel:
        return None
    return f'{channel["device_name"]} / {channel["channel_name"]} / {channel["unit"] or "--"}'


def _infer_metric_key(metric: dict[str, Any], index: int) -> str:
    name = str(metric.get("name") or "").lower()
    unit = str(metric.get("unit") or "")
    if "功率" in name or "power" in name or unit == "kW":
        return "power"
    if "电压" in name or "電壓" in name or "voltage" in name or unit == "V":
        return "voltage"
    return f"metric_{index + 1}"


def _resolve_active_baseline() -> dict[str, Any] | None:
    active_baseline_id = _SETTINGS_STORE.get("active_baseline_id", {}).get("value")
    if isinstance(active_baseline_id, str) and active_baseline_id:
        item = _BASELINE_STORE.get(active_baseline_id)
        if item:
            return item

    published = [item for item in _BASELINE_STORE.values() if item["status"] == "published"]
    if not published:
        return None
    published.sort(key=lambda item: item["published_at"] or item["updated_at"], reverse=True)
    return published[0]


def _resolve_dashboard_sources() -> dict[str, str | None]:
    baseline = _resolve_active_baseline()
    if not baseline:
        return {
            "baseline_id": None,
            "baseline_name": None,
            "power_source_label": None,
            "voltage_source_label": None,
        }

    definition = _DEFINITION_STORE.get(str(baseline.get("definition_id")))
    metrics = list(definition.get("metrics", [])) if definition else []
    power_metric = next(
        (item for index, item in enumerate(metrics) if _infer_metric_key(item, index) == "power"),
        None,
    )
    voltage_metric = next(
        (item for index, item in enumerate(metrics) if _infer_metric_key(item, index) == "voltage"),
        None,
    )
    return {
        "baseline_id": str(baseline.get("id")) if baseline.get("id") else None,
        "baseline_name": str(baseline.get("name")) if baseline.get("name") else None,
        "power_source_label": _format_host_channel_label(
            _resolve_host_channel(power_metric.get("edc_channel_id")) if power_metric else None
        ),
        "voltage_source_label": _format_host_channel_label(
            _resolve_host_channel(voltage_metric.get("edc_channel_id")) if voltage_metric else None
        ),
    }


async def _load_realtime_curves_from_edc(
    *,
    duration: Literal["5m", "1h", "6h", "24h"],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]] | None:
    """尝试从真实 EDC 读取实时功率/电压曲线。"""
    baseline = _resolve_active_baseline()
    definition = (
        _DEFINITION_STORE.get(str(baseline.get("definition_id")))
        if baseline and baseline.get("definition_id")
        else None
    )
    metrics = list(definition.get("metrics", [])) if definition else []
    power_metric = next(
        (item for index, item in enumerate(metrics) if _infer_metric_key(item, index) == "power"),
        None,
    )
    voltage_metric = next(
        (item for index, item in enumerate(metrics) if _infer_metric_key(item, index) == "voltage"),
        None,
    )
    power_channel = _resolve_host_channel(power_metric.get("edc_channel_id")) if power_metric else None
    voltage_channel = (
        _resolve_host_channel(voltage_metric.get("edc_channel_id")) if voltage_metric else None
    )
    if not power_channel or not voltage_channel:
        return None

    config = get_edc_connection_config()
    if not config["base_url"] or not config["username"] or not config["password"]:
        return None

    try:
        async with EDCClient(
            **config,
            timeout=DASHBOARD_REALTIME_EDC_TIMEOUT_SECONDS,
        ) as client:
            await client.login()
            power_points, voltage_points = await asyncio.gather(
                client.get_local_datas(
                    suid=power_channel["suid"],
                    cuid=power_channel["cuid"],
                    start_time=start_time,
                    end_time=end_time,
                ),
                client.get_local_datas(
                    suid=voltage_channel["suid"],
                    cuid=voltage_channel["cuid"],
                    start_time=start_time,
                    end_time=end_time,
                ),
            )
    except EDCClientError as exc:
        raise EDCClientError(f"实时曲线拉取失败：{exc}") from exc

    if not power_points or not voltage_points:
        return None

    baseline_power = _build_flat_baseline_curve(power_points, 460.0)
    baseline_voltage = _build_flat_baseline_curve(voltage_points, 385.0)
    return {
        "power": power_points,
        "voltage": voltage_points,
        "baseline_power": baseline_power,
        "baseline_voltage": baseline_voltage,
    }


def _build_flat_baseline_curve(points: list[CurvePoint], value: float) -> list[CurvePoint]:
    """沿真实时间轴生成平直基线。"""
    return [CurvePoint(timestamp=item.timestamp, value=value) for item in points]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats() -> DashboardStats:
    """获取仪表盘统计数据

    返回当日生产概况：炉次数、平均偏差、待处理任务数等。
    """
    from .tasks import _list_task_store

    sources = _resolve_dashboard_sources()
    heats = await _sorted_dashboard_heats()
    today = datetime.now().date()
    today_heats = [item for item in heats if item["start_time"].date() == today]
    scoped_heats = today_heats or heats
    deviations = [
        float(item["deviation_percent"])
        for item in scoped_heats
        if item.get("deviation_percent") is not None
    ]
    normal_count = sum(1 for item in scoped_heats if item.get("status") == "normal")
    pending_tasks = sum(
        1
        for item in _list_task_store().values()
        if item.get("status") in {"pending", "in_progress"}
    )

    return DashboardStats(
        today_heats=len(today_heats),
        avg_deviation=round(sum(deviations) / len(deviations), 3) if deviations else 0.0,
        pending_tasks=pending_tasks,
        active_baseline=sources["baseline_name"],
        normal_rate=round((normal_count / len(scoped_heats)) * 100, 2) if scoped_heats else 0.0,
    )


@router.get("/realtime")
async def get_realtime_data(
    duration: Literal["5m", "1h", "6h", "24h"] = "5m",
) -> dict:
    """获取实时曲线数据

    Args:
        duration: 时间范围 (5分钟/1小时/6小时/24小时)

    Returns:
        包含功率和电压曲线数据的字典
    """
    started_at = perf_counter()
    # 时间范围映射
    duration_map = {
        "5m": timedelta(minutes=5),
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
    }
    delta = duration_map[duration]
    end_time = datetime.now()
    start_time = end_time - delta

    sources = _resolve_dashboard_sources()
    try:
        realtime_curves = await _load_realtime_curves_from_edc(
            duration=duration,
            start_time=start_time,
            end_time=end_time,
        )
    except EDCClientError as exc:
        detail = str(exc)
        log_event(
            "api_dashboard_realtime",
            duration=duration,
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            available=False,
            error=detail,
        )
        raise HTTPException(status_code=503, detail=detail) from exc

    if realtime_curves is None:
        log_event(
            "api_dashboard_realtime",
            duration=duration,
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            available=False,
            error="no_realtime_data",
        )
        raise HTTPException(
            status_code=503,
            detail="未获取到真实实时数据，请检查宿主连接和通道绑定",
        )

    power_curve = [item.model_dump() for item in realtime_curves["power"]]
    voltage_curve = [item.model_dump() for item in realtime_curves["voltage"]]
    baseline_power = [item.model_dump() for item in realtime_curves["baseline_power"]]
    baseline_voltage = [item.model_dump() for item in realtime_curves["baseline_voltage"]]

    response = {
        "timestamp": end_time.isoformat(),
        "baseline_id": sources["baseline_id"],
        "baseline_name": sources["baseline_name"],
        "power_source_label": sources["power_source_label"],
        "voltage_source_label": sources["voltage_source_label"],
        "power": power_curve,
        "voltage": voltage_curve,
        "baseline_power": baseline_power,
        "baseline_voltage": baseline_voltage,
    }
    log_event(
        "api_dashboard_realtime",
        duration=duration,
        power_points=len(power_curve),
        voltage_points=len(voltage_curve),
        baseline_power_points=len(baseline_power),
        baseline_voltage_points=len(baseline_voltage),
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
        available=True,
    )
    return response


@router.get("/recent-heats", response_model=RecentHeatsResponse)
async def get_recent_heats(limit: int = 10) -> RecentHeatsResponse:
    """获取最近炉次列表

    Args:
        limit: 返回数量限制，默认10条

    Returns:
        最近炉次列表
    """
    heats = await _sorted_dashboard_heats()
    items = [
        RecentHeat(
            id=str(item["id"]),
            heat_no=str(item["heat_no"]),
            start_time=item["start_time"],
            end_time=item["end_time"],
            status=str(item["status"]),
            deviation_percent=(
                float(item["deviation_percent"])
                if item.get("deviation_percent") is not None
                else None
            ),
        )
        for item in heats[: max(limit, 0)]
    ]
    return RecentHeatsResponse(items=items)
