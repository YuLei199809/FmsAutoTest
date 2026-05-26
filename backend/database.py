"""
database.py  —  数据库层（含连接池 + 断连重试）

新增能力：
  • pool_pre_ping  ：每次取连接前自动 ping，断连后 SQLAlchemy 自动重建连接
  • pool_recycle   ：超过时限的连接主动回收，防止数据库服务端踢掉闲置连接
  • db_retry 装饰器：数据库操作遇到 OperationalError / DisconnectionError 时
                    按指数退避自动重试，重试次数和间隔由 settings 控制
  • get_db_safe    ：可在 FastAPI 依赖注入以外的地方安全使用的上下文管理器
"""

import time
import logging
import functools
from contextlib import contextmanager

from sqlalchemy import create_engine, event, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

import settings  # ← 从环境配置读参数

log = logging.getLogger("database")

# ─────────────────────────────────────────────
# 1. 引擎 —— 根据数据库类型自动适配参数
# ─────────────────────────────────────────────
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# SQLite 不支持连接池参数，用 NullPool 避免警告；PG 正常使用连接池
if _is_sqlite:
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=_connect_args,
        echo=settings.DB_ECHO,
        poolclass=StaticPool,          # SQLite：单一共享连接
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        pool_pre_ping=settings.DB_POOL_PRE_PING,   # 使用前 ping，自动剔除断连
        pool_recycle=settings.DB_POOL_RECYCLE,      # 定期回收老连接
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
    )
    # 额外监听：连接被 checkout 时打 debug 日志（排查连接泄漏用）
    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, conn_record, conn_proxy):
        log.debug("DB 连接 checkout，pool_size=%s", engine.pool.size())

Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ─────────────────────────────────────────────
# 2. db_retry 装饰器（指数退避）
# ─────────────────────────────────────────────
def db_retry(func=None, *, max_retries: int = None, delay: float = None):
    """
    数据库操作重试装饰器。

    捕获 OperationalError / DisconnectionError，按指数退避重试。
    重试次数和间隔默认读 settings，也可以单独覆盖：

        @db_retry
        def my_query(db): ...

        @db_retry(max_retries=5, delay=1.0)
        def my_query(db): ...
    """
    _max = max_retries if max_retries is not None else settings.DB_MAX_RETRIES
    _delay = delay if delay is not None else settings.DB_RETRY_DELAY

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, _max + 1):
                try:
                    return fn(*args, **kwargs)
                except (OperationalError, DisconnectionError) as exc:
                    last_exc = exc
                    wait = _delay * (2 ** (attempt - 1))   # 指数退避：0.5s, 1s, 2s …
                    log.warning(
                        "[db_retry] %s 第 %d/%d 次失败，%.1fs 后重试。原因: %s",
                        fn.__name__, attempt, _max, wait, exc,
                    )
                    if attempt < _max:
                        time.sleep(wait)
            log.error("[db_retry] %s 重试 %d 次后仍失败", fn.__name__, _max)
            raise last_exc
        return wrapper

    # 支持 @db_retry 和 @db_retry(...) 两种用法
    if func is not None:
        return decorator(func)
    return decorator


# ─────────────────────────────────────────────
# 3. FastAPI 依赖注入用的 get_db（带重试）
# ─────────────────────────────────────────────
def get_db():
    """
    FastAPI Depends 用法：
        def my_endpoint(db: Session = Depends(get_db)): ...

    内置重试：若 session 创建或首次操作遇到断连，自动重建。
    """
    db = None
    last_exc = None
    for attempt in range(1, settings.DB_MAX_RETRIES + 1):
        try:
            db = SessionLocal()
            yield db
            return                      # 正常结束，跳出循环
        except (OperationalError, DisconnectionError) as exc:
            last_exc = exc
            wait = settings.DB_RETRY_DELAY * (2 ** (attempt - 1))
            log.warning(
                "[get_db] 第 %d/%d 次断连，%.1fs 后重试",
                attempt, settings.DB_MAX_RETRIES, wait,
            )
            if db:
                try:
                    db.rollback()
                    db.close()
                except Exception:
                    pass
                db = None
            if attempt < settings.DB_MAX_RETRIES:
                time.sleep(wait)
        finally:
            if db:
                db.close()
    raise last_exc


# ─────────────────────────────────────────────
# 4. 在 FastAPI 依赖注入之外安全使用（脚本、定时任务等）
# ─────────────────────────────────────────────
@contextmanager
def get_db_safe():
    """
    with 语法用法（非 FastAPI endpoint 场景）：
        with get_db_safe() as db:
            db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────
# 5. 数据模型（与原版完全一致，仅缩减注释）
# ─────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String)
    token = Column(String, nullable=True)

class ApprovalConfig(Base):
    __tablename__ = "approval_configs"
    id = Column(Integer, primary_key=True)
    biz_type = Column(String)
    amount_min = Column(Float)
    amount_max = Column(Float)
    steps = Column(Text)

class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True)
    account_no = Column(String, unique=True)
    bank_name = Column(String)
    account_name = Column(String)
    currency = Column(String, default="CNY")
    balance = Column(Float, default=0.0)
    status = Column(String, default="active")

class PaymentRequest(Base):
    __tablename__ = "payment_requests"
    id = Column(Integer, primary_key=True)
    req_no = Column(String, unique=True)
    from_account = Column(String)
    to_account = Column(String)
    to_bank = Column(String)
    to_name = Column(String)
    amount = Column(Float)
    currency = Column(String, default="CNY")
    purpose = Column(String)
    status = Column(String, default="pending")
    current_step = Column(String, nullable=True)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    remark = Column(Text, nullable=True)

class ApprovalRecord(Base):
    __tablename__ = "approval_records"
    id = Column(Integer, primary_key=True)
    req_no = Column(String)
    step = Column(String)
    action = Column(String)
    operator = Column(String)
    comment = Column(Text, nullable=True)
    operated_at = Column(DateTime, default=datetime.now)

class FundTransfer(Base):
    __tablename__ = "fund_transfers"
    id = Column(Integer, primary_key=True)
    transfer_no = Column(String, unique=True)
    from_account = Column(String)
    to_account = Column(String)
    amount = Column(Float)
    transfer_type = Column(String)
    status = Column(String, default="pending")
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True)
    receipt_no = Column(String, unique=True)
    to_account = Column(String)
    from_name = Column(String)
    amount = Column(Float)
    currency = Column(String, default="CNY")
    receipt_date = Column(String)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True)
    bill_no = Column(String, unique=True)
    bill_type = Column(String)
    drawer = Column(String)
    acceptor = Column(String)
    payee = Column(String)
    amount = Column(Float)
    issue_date = Column(String)
    due_date = Column(String)
    status = Column(String, default="holding")
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class BillEndorsement(Base):
    __tablename__ = "bill_endorsements"
    id = Column(Integer, primary_key=True)
    bill_no = Column(String)
    endorsee = Column(String)
    endorsed_at = Column(String)
    purpose = Column(String)
    operator = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class BillDiscount(Base):
    __tablename__ = "bill_discounts"
    id = Column(Integer, primary_key=True)
    bill_no = Column(String)
    bank_name = Column(String)
    discount_rate = Column(Float)
    discount_amount = Column(Float)
    discount_date = Column(String)
    operator = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class CashPool(Base):
    __tablename__ = "cash_pools"
    id = Column(Integer, primary_key=True)
    pool_no = Column(String, unique=True)
    pool_name = Column(String)
    master_account = Column(String)
    interest_rate = Column(Float, default=0.02)
    status = Column(String, default="active")

class PoolMember(Base):
    __tablename__ = "pool_members"
    id = Column(Integer, primary_key=True)
    pool_no = Column(String)
    member_account = Column(String)
    join_date = Column(String)

class PoolSweep(Base):
    __tablename__ = "pool_sweeps"
    id = Column(Integer, primary_key=True)
    sweep_no = Column(String, unique=True)
    pool_no = Column(String)
    sweep_type = Column(String)
    from_account = Column(String)
    to_account = Column(String)
    amount = Column(Float)
    sweep_date = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class InterestRecord(Base):
    __tablename__ = "interest_records"
    id = Column(Integer, primary_key=True)
    pool_no = Column(String)
    account_no = Column(String)
    principal = Column(Float)
    rate = Column(Float)
    days = Column(Integer)
    interest = Column(Float)
    calc_date = Column(String)
    created_at = Column(DateTime, default=datetime.now)


# ─────────────────────────────────────────────
# 6. 初始化数据（与原版一致）
# ─────────────────────────────────────────────
def init_data():
    db = SessionLocal()
    if db.query(User).count() == 0:
        users = [
            User(username="cashier01", password="123456", role="cashier"),
            User(username="finance01", password="123456", role="finance"),
            User(username="manager01", password="123456", role="manager"),
            User(username="admin",     password="admin123", role="admin"),
        ]
        db.add_all(users)

        configs = [
            ApprovalConfig(biz_type="payment", amount_min=0, amount_max=100000,
                           steps=json.dumps(["manager", "finance"])),
            ApprovalConfig(biz_type="payment", amount_min=100000, amount_max=999999999,
                           steps=json.dumps(["manager", "finance", "admin"])),
        ]
        db.add_all(configs)

        accounts = [
            BankAccount(account_no="1001", bank_name="工商银行", account_name="集团总部",   balance=5000000.0),
            BankAccount(account_no="1002", bank_name="建设银行", account_name="华东分公司", balance=1200000.0),
            BankAccount(account_no="1003", bank_name="农业银行", account_name="华南分公司", balance=800000.0),
            BankAccount(account_no="1004", bank_name="中国银行", account_name="已冻结账户", balance=0.0, status="frozen"),
        ]
        db.add_all(accounts)

        bills = [
            Bill(bill_no="BA2024001", bill_type="银行承兑汇票", drawer="供应商A",
                 acceptor="工商银行", payee="集团总部", amount=500000.0,
                 issue_date="2024-01-01", due_date="2024-07-01",
                 status="holding", created_by="cashier01"),
            Bill(bill_no="BA2024002", bill_type="商业承兑汇票", drawer="供应商B",
                 acceptor="供应商B", payee="集团总部", amount=200000.0,
                 issue_date="2024-02-01", due_date="2024-08-01",
                 status="holding", created_by="cashier01"),
            Bill(bill_no="BA2024003", bill_type="银行承兑汇票", drawer="供应商C",
                 acceptor="建设银行", payee="集团总部", amount=300000.0,
                 issue_date="2023-06-01", due_date="2023-12-01",
                 status="overdue", created_by="cashier01"),
        ]
        db.add_all(bills)

        pool = CashPool(pool_no="POOL001", pool_name="集团现金池",
                        master_account="1001", interest_rate=0.02)
        db.add(pool)
        db.add_all([
            PoolMember(pool_no="POOL001", member_account="1002", join_date="2024-01-01"),
            PoolMember(pool_no="POOL001", member_account="1003", join_date="2024-01-01"),
        ])
        db.commit()
    db.close()
