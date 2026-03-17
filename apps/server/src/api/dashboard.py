"""仪表盘 API 路由"""

from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter

from ..schemas import DashboardStats, RecentHeat, RecentHeatsResponse
from .baseline_definitions import _DEFINITION_STORE
from .baselines import _BASELINE_STORE
from .settings import _HOST_CHANNEL_STORE, _SETTINGS_STORE

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats() -> DashboardStats:
    """获取仪表盘统计数据

    返回当日生产概况：炉次数、平均偏差、待处理任务数等。
    """
    # TODO: 实现真实逻辑，从数据库查询
    return DashboardStats(
        today_heats=12,
        avg_deviation=8.5,
        pending_tasks=3,
        active_baseline=_resolve_dashboard_sources()["baseline_name"] or "标准基线 v2.1",
        normal_rate=85.0,
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

    # TODO: 实现真实逻辑，从 EDC API 或数据库获取
    # 生成模拟数据
    points_map = {
        "5m": 60,
        "1h": 120,
        "6h": 180,
        "24h": 288,
    }
    points = points_map[duration]
    power_curve = []
    voltage_curve = []
    baseline_power = []
    baseline_voltage = []

    for i in range(points):
        ts = int((start_time + (delta / points) * i).timestamp() * 1000)
        power_curve.append({"timestamp": ts, "value": 450 + ((i + points // 12) % 10) * 5})
        voltage_curve.append({"timestamp": ts, "value": 380 + ((i + points // 24) % 5) * 2})
        baseline_power.append({"timestamp": ts, "value": 460})
        baseline_voltage.append({"timestamp": ts, "value": 385})

    sources = _resolve_dashboard_sources()

    return {
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


@router.get("/recent-heats", response_model=RecentHeatsResponse)
async def get_recent_heats(limit: int = 10) -> RecentHeatsResponse:
    """获取最近炉次列表

    Args:
        limit: 返回数量限制，默认10条

    Returns:
        最近炉次列表
    """
    # TODO: 实现真实逻辑，从数据库查询
    now = datetime.now()
    items = []
    for i in range(min(limit, 10)):
        start = now - timedelta(hours=i + 1)
        end = start + timedelta(minutes=45)
        items.append(
            RecentHeat(
                id=f"heat-{i + 1:03d}",
                heat_no=f"H{now.strftime('%Y%m%d')}-{i + 1:03d}",
                start_time=start,
                end_time=end,
                status="normal" if i % 3 != 0 else "abnormal",
                deviation_percent=5.2 + i * 1.5 if i % 3 == 0 else 3.1 + i * 0.5,
            )
        )

    return RecentHeatsResponse(items=items)
