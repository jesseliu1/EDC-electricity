"""仪表盘 API 路由"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Literal

from fastapi import APIRouter, HTTPException

from ..channel_roles import format_host_channel_label, resolve_channel_role
from ..observability import log_event
from ..schemas import DashboardStats, RecentHeat, RecentHeatsResponse
from ..schemas.common import CurvePoint
from ..services import EDCClient, EDCClientError
from ..time_utils import plant_date_of, to_timestamp_ms, utc_now
from .baselines import _BASELINE_STORE
from .settings import (
    _CHANNEL_ROLE_BINDING_STORE,
    _HOST_CHANNEL_STORE,
    _SETTINGS_STORE,
    get_edc_connection_config,
    get_plant_timezone,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DASHBOARD_REALTIME_EDC_TIMEOUT_SECONDS = 8.0


async def _sorted_dashboard_heats() -> list[dict[str, Any]]:
    from . import heats as heats_api

    items = list((await heats_api._list_heat_store()).values())
    items.sort(key=lambda item: item["start_time"], reverse=True)
    return items


def _resolve_active_baseline() -> dict[str, Any] | None:
    from .baselines import _resolve_active_baseline_item

    return _resolve_active_baseline_item()

def _resolve_dashboard_realtime_context() -> dict[str, Any]:
    baseline = _resolve_active_baseline()
    power_channel = resolve_channel_role(
        "dashboard_primary",
        _CHANNEL_ROLE_BINDING_STORE,
        _HOST_CHANNEL_STORE,
    )
    voltage_channel = resolve_channel_role(
        "dashboard_secondary",
        _CHANNEL_ROLE_BINDING_STORE,
        _HOST_CHANNEL_STORE,
    )
    missing_required_roles: list[str] = []
    if not power_channel:
        missing_required_roles.append("dashboard_primary")
    return {
        "baseline_id": str(baseline.get("id")) if baseline and baseline.get("id") else None,
        "baseline_name": str(baseline.get("name")) if baseline and baseline.get("name") else None,
        "power_channel": power_channel,
        "voltage_channel": voltage_channel,
        "power_source_label": format_host_channel_label(power_channel),
        "voltage_source_label": format_host_channel_label(voltage_channel),
        "missing_required_roles": missing_required_roles,
    }


async def _load_realtime_curves_from_edc(
    *,
    duration: Literal["5m", "1h", "6h", "24h"],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[CurvePoint]] | None:
    """尝试从真实 EDC 读取实时功率/电压曲线。"""
    context = _resolve_dashboard_realtime_context()
    power_channel = context["power_channel"]
    voltage_channel = context["voltage_channel"]
    if not power_channel:
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
            tasks: dict[str, asyncio.Task[list[CurvePoint]]] = {
                "power": asyncio.create_task(
                    client.get_local_datas(
                        suid=power_channel["suid"],
                        cuid=power_channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
            }
            if voltage_channel:
                tasks["voltage"] = asyncio.create_task(
                    client.get_local_datas(
                        suid=voltage_channel["suid"],
                        cuid=voltage_channel["cuid"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
            results = await asyncio.gather(*tasks.values())
    except EDCClientError as exc:
        raise EDCClientError(f"实时曲线拉取失败：{exc}") from exc

    curves_by_key = {
        metric_key: result
        for metric_key, result in zip(tasks.keys(), results, strict=False)
    }
    power_points = curves_by_key.get("power") or []
    voltage_points = curves_by_key.get("voltage") or []

    if not power_points:
        return None

    baseline_power = _build_flat_baseline_curve(power_points, 460.0)
    baseline_voltage = (
        _build_flat_baseline_curve(voltage_points, 385.0) if voltage_points else []
    )
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

    sources = _resolve_dashboard_realtime_context()
    heats = await _sorted_dashboard_heats()
    timezone_name = get_plant_timezone()
    today = plant_date_of(utc_now(), timezone_name)
    today_heats = [item for item in heats if plant_date_of(item["start_time"], timezone_name) == today]
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
    end_time = utc_now()
    start_time = end_time - delta

    sources = _resolve_dashboard_realtime_context()
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
        missing_required_roles = sources.get("missing_required_roles", [])
        detail = "未获取到真实实时数据，请检查宿主连接和通道绑定"
        if missing_required_roles:
            detail = (
                "Dashboard 实时主曲线角色未配置，请先绑定 dashboard_primary 对应通道"
            )
        log_event(
            "api_dashboard_realtime",
            duration=duration,
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            available=False,
            error="no_realtime_data",
            missing_required_roles=missing_required_roles,
        )
        raise HTTPException(
            status_code=503,
            detail=detail,
        )

    power_curve = [item.model_dump() for item in realtime_curves["power"]]
    voltage_curve = [item.model_dump() for item in realtime_curves["voltage"]]
    baseline_power = [item.model_dump() for item in realtime_curves["baseline_power"]]
    baseline_voltage = [item.model_dump() for item in realtime_curves["baseline_voltage"]]

    response = {
        "timestamp": to_timestamp_ms(end_time),
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
