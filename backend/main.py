"""
main.py  —  应用入口（含前端静态文件服务）

新增：
  • 挂载 /frontend 目录，直接提供 HTML 页面
  • GET / → 跳转登录页
  • 依赖：pip install aiofiles  (StaticFiles 需要它)
"""

import logging
import os
import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from database import Base, engine, init_data
from routers import auth, fund, bill, pool
from middleware import TimeoutMiddleware, RequestLogMiddleware

# ── 建表 + 初始数据 ───────────────────────────────────────────
Base.metadata.create_all(bind=engine)
init_data()

settings.print_summary()

# ── 应用 ──────────────────────────────────────────────────────
app = FastAPI(
    title="司库资金管理系统",
    version="1.0.0",
    debug=settings.DEBUG,
)

# ── 中间件 ────────────────────────────────────────────────────
if settings.ENV == "dev":
    app.add_middleware(RequestLogMiddleware)
app.add_middleware(TimeoutMiddleware, timeout=settings.REQUEST_TIMEOUT)

# ── API 路由 ──────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(fund.router, prefix="/api/fund", tags=["资金管理"])
app.include_router(bill.router, prefix="/api/bill", tags=["票据管理"])
app.include_router(pool.router, prefix="/api/pool", tags=["资金集中"])

# ── 根路径跳转登录 ─────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/frontend/login.html")

# ── 挂载前端静态文件 ──────────────────────────────────────────
os.makedirs("frontend", exist_ok=True)
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# ── 健康检查 ──────────────────────────────────────────────────
@app.get("/api/health")
def health():
    from datetime import datetime
    return {
        "code":      200,
        "message":   "系统正常",
        "env":       settings.ENV,
        "timestamp": str(datetime.now()),
    }
