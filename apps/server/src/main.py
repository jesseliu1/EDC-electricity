"""FastAPI 应用入口"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .config import settings
from .database import init_db
from .observability import (
    REQUEST_ID_HEADER,
    configure_observability,
    create_request_id,
    log_event,
    reset_request_id,
    set_request_id,
)
from .request_mode import reset_showtime_mode, resolve_showtime_mode, set_showtime_mode
from .runtime_state import load_runtime_state
from .services import close_shared_edc_clients


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理"""
    configure_observability()
    # 启动时初始化数据库
    await init_db()
    await load_runtime_state()
    yield
    # 关闭时清理资源
    await close_shared_edc_clients()


app = FastAPI(
    title=settings.app_name,
    description="基于黄金基线的中频炉熔炼过程偏差监控与纠偏系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bind_request_mode(request, call_next):
    """为每个请求绑定 showtime 模式。"""
    mode_token = set_showtime_mode(resolve_showtime_mode(request))
    request_id = request.headers.get(REQUEST_ID_HEADER) or create_request_id()
    request_id_token = set_request_id(request_id)
    started_at = perf_counter()
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        duration_ms = round((perf_counter() - started_at) * 1000, 1)
        should_log = (
            duration_ms >= 1000
            or response.status_code >= 500
            or request.url.path in {"/api/heats", "/api/dashboard/realtime"}
            or request.url.path.endswith("/compare")
        )
        if should_log:
            log_event(
                "http_request",
                method=request.method,
                path=request.url.path,
                query=str(request.url.query),
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        return response
    except Exception:
        duration_ms = round((perf_counter() - started_at) * 1000, 1)
        log_event(
            "http_request_error",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            duration_ms=duration_ms,
        )
        raise
    finally:
        reset_request_id(request_id_token)
        reset_showtime_mode(mode_token)

# 注册路由
app.include_router(api_router, prefix="/api")


@app.get("/health")
@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """健康检查接口"""
    return {"status": "ok"}
