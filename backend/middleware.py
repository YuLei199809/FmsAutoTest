"""
middleware.py  —  FastAPI 中间件集合

当前包含：
  • TimeoutMiddleware   ：请求超时保护，超时后返回 408，由 settings.REQUEST_TIMEOUT 控制
  • RequestLogMiddleware：请求日志（仅 dev 环境启用，自动过滤 /api/health 心跳）
"""

import asyncio
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import settings

log = logging.getLogger("middleware")


# ─────────────────────────────────────────────
# 1. 请求超时中间件
# ─────────────────────────────────────────────
class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    若下游 handler 在 timeout 秒内未响应，直接返回 408。

    实现原理：asyncio.wait_for 包裹 call_next，超时后取消协程。
    注意：仅能保护异步等待阶段；若某同步操作阻塞事件循环，需在
         业务代码里用 run_in_executor 处理。
    """

    def __init__(self, app, timeout: int = None):
        super().__init__(app)
        self.timeout = timeout or settings.REQUEST_TIMEOUT

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            log.warning(
                "请求超时 [%s %s] > %ds",
                request.method, request.url.path, self.timeout,
            )
            return JSONResponse(
                status_code=408,
                content={
                    "code": 408,
                    "message": f"请求超时（超过 {self.timeout}s），请稍后重试",
                },
            )
        except Exception as exc:
            # 让 FastAPI 的异常处理器接管其他异常，不在这里吞掉
            raise exc


# ─────────────────────────────────────────────
# 2. 请求日志中间件（dev 下自动开启）
# ─────────────────────────────────────────────
_SKIP_LOG_PATHS = {"/api/health", "/docs", "/openapi.json", "/redoc"}

class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    打印每次请求的方法、路径、耗时、状态码。
    dev 环境默认启用；staging/prod 建议改用 access log 工具（如 uvicorn --access-log）。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_LOG_PATHS:
            return await call_next(request)

        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        log.log(
            level,
            "%s %s  →  %d  (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
