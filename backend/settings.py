"""
环境配置中心  settings.py

切换方式（三选一，优先级从高到低）：
  1. 系统环境变量：  export ENV=staging
  2. .env.{env} 文件：项目根目录放 .env.dev / .env.staging / .env.prod
  3. 代码默认值（兜底）

支持的环境：dev（默认） / staging / prod
"""

import os
import logging

log = logging.getLogger("settings")

# ─────────────────────────────────────────────
# 0. 确定当前环境
# ─────────────────────────────────────────────
ENV = os.getenv("ENV", "dev").lower()
if ENV not in ("dev", "staging", "prod"):
    raise ValueError(f"ENV={ENV!r} 不合法，可选：dev / staging / prod")

# 尝试加载 .env 文件（需要 pip install python-dotenv，没装也不报错）
try:
    from dotenv import load_dotenv
    load_dotenv(".env", override=False)          # 通用基础配置（低优先级）
    load_dotenv(f".env.{ENV}", override=True)    # 环境专属配置（高优先级）
except ImportError:
    pass  # 直接用系统环境变量，不强依赖 dotenv


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def _str(key: str, default: str) -> str:
    return os.getenv(key, default)

def _int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))

def _float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))

def _bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes")


# ─────────────────────────────────────────────
# 1. 数据库配置
# ─────────────────────────────────────────────
# dev 默认 SQLite；staging/prod 建议换成 PostgreSQL
_default_db_url = {
    "dev":     "sqlite:///treasury_dev.db",
    "staging": "sqlite:///treasury_staging.db",  # 改为 postgresql+psycopg2://user:pwd@host/db
    "prod":    "sqlite:///treasury_prod.db",      # 改为 postgresql+psycopg2://user:pwd@host/db
}
DATABASE_URL     = _str("DATABASE_URL", _default_db_url[ENV])

# 连接池（对 SQLite 不生效，切 PG 后自动起作用）
DB_POOL_PRE_PING = _bool("DB_POOL_PRE_PING", True)     # 每次使用连接前 ping，自动剔除断连
DB_POOL_RECYCLE  = _int("DB_POOL_RECYCLE",  3600)       # 连接最大复用时长（秒）
DB_POOL_SIZE     = _int("DB_POOL_SIZE",     5)          # 连接池大小（PG 有效）
DB_MAX_OVERFLOW  = _int("DB_MAX_OVERFLOW",  10)         # 超出池大小后最多额外建多少连接

# DB 操作失败重试
DB_MAX_RETRIES   = _int("DB_MAX_RETRIES",   3)          # 最多重试次数
DB_RETRY_DELAY   = _float("DB_RETRY_DELAY", 0.5)        # 重试间隔（秒），指数退避基数

# ─────────────────────────────────────────────
# 2. 请求超时
# ─────────────────────────────────────────────
_default_timeout = {"dev": 60, "staging": 30, "prod": 20}
REQUEST_TIMEOUT  = _int("REQUEST_TIMEOUT", _default_timeout[ENV])  # 单次请求最长等待（秒）

# ─────────────────────────────────────────────
# 3. 日志 / 调试
# ─────────────────────────────────────────────
DEBUG     = _bool("DEBUG",     ENV == "dev")
DB_ECHO   = _bool("DB_ECHO",   ENV == "dev")   # 是否打印 SQL（dev 开，其他关）
LOG_LEVEL = _str("LOG_LEVEL",  "DEBUG" if ENV == "dev" else "INFO")


# ─────────────────────────────────────────────
# 4. 启动摘要（被 main.py 调用）
# ─────────────────────────────────────────────
def print_summary() -> None:
    bar = "═" * 42
    print(f"\n╔{bar}╗")
    print(f"  运行环境      : {ENV.upper()}")
    print(f"  DATABASE_URL  : {DATABASE_URL}")
    print(f"  pool_pre_ping : {DB_POOL_PRE_PING}   pool_recycle: {DB_POOL_RECYCLE}s")
    print(f"  DB 重试       : 最多 {DB_MAX_RETRIES} 次，间隔 {DB_RETRY_DELAY}s（指数退避）")
    print(f"  请求超时      : {REQUEST_TIMEOUT}s")
    print(f"  DB_ECHO       : {DB_ECHO}   DEBUG: {DEBUG}")
    print(f"╚{bar}╝\n")
