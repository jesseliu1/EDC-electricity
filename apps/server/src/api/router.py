"""API 路由汇总"""

from fastapi import APIRouter

from .baselines import router as baselines_router
from .dashboard import router as dashboard_router
from .heats import router as heats_router
from .reports import router as reports_router
from .settings import router as settings_router
from .tasks import router as tasks_router

api_router = APIRouter()

# 注册所有子路由
api_router.include_router(dashboard_router)
api_router.include_router(baselines_router)
api_router.include_router(heats_router)
api_router.include_router(tasks_router)
api_router.include_router(reports_router)
api_router.include_router(settings_router)
