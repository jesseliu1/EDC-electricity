"""FastAPI 应用入口"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .config import settings
from .database import init_db
from .request_mode import reset_showtime_mode, resolve_showtime_mode, set_showtime_mode
from .runtime_state import load_runtime_state


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    await load_runtime_state()
    yield
    # 关闭时清理资源


app = FastAPI(
    title=settings.app_name,
    description="基于黄金基线的中频炉熔炼过程偏差监控与纠偏系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bind_request_mode(request, call_next):
    """为每个请求绑定 showtime 模式。"""
    token = set_showtime_mode(resolve_showtime_mode(request))
    try:
        return await call_next(request)
    finally:
        reset_showtime_mode(token)

# 注册路由
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查接口"""
    return {"status": "ok"}
