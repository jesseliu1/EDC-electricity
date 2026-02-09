"""仪表盘 API 路由"""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter

from ..schemas import DashboardStats, RecentHeat, RecentHeatsResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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
        active_baseline="标准基线 v2.1",
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
    points = 60 if duration == "5m" else 120
    power_curve = []
    voltage_curve = []
    baseline_power = []
    baseline_voltage = []

    for i in range(points):
        ts = int((start_time + (delta / points) * i).timestamp() * 1000)
        power_curve.append({"timestamp": ts, "value": 450 + (i % 10) * 5})
        voltage_curve.append({"timestamp": ts, "value": 380 + (i % 5) * 2})
        baseline_power.append({"timestamp": ts, "value": 460})
        baseline_voltage.append({"timestamp": ts, "value": 385})

    return {
        "timestamp": end_time.isoformat(),
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
