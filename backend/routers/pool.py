from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal, CashPool, PoolMember, PoolSweep, InterestRecord, BankAccount
from routers.auth import verify_token
from datetime import datetime, date
import uuid

router = APIRouter()

class SweepReq(BaseModel):
    pool_no: str
    sweep_type: str    # 上划/下拨
    member_account: str
    amount: float

class InterestCalcReq(BaseModel):
    pool_no: str
    account_no: str
    principal: float
    days: int
    calc_date: str

@router.get("/list")
def list_pools(Authorization: str = Header(...)):
    verify_token(Authorization)
    db = SessionLocal()
    pools = db.query(CashPool).all()
    result = []
    for p in pools:
        members = db.query(PoolMember).filter(PoolMember.pool_no == p.pool_no).all()
        result.append({
            "pool_no": p.pool_no,
            "pool_name": p.pool_name,
            "master_account": p.master_account,
            "interest_rate": p.interest_rate,
            "status": p.status,
            "member_count": len(members)
        })
    db.close()
    return {"code": 200, "data": result}

@router.get("/{pool_no}/members")
def get_pool_members(pool_no: str, Authorization: str = Header(...)):
    verify_token(Authorization)
    db = SessionLocal()
    pool = db.query(CashPool).filter(CashPool.pool_no == pool_no).first()
    if not pool:
        raise HTTPException(status_code=404, detail="现金池不存在")
    members = db.query(PoolMember).filter(PoolMember.pool_no == pool_no).all()
    result = []
    for m in members:
        acc = db.query(BankAccount).filter(BankAccount.account_no == m.member_account).first()
        result.append({
            "member_account": m.member_account,
            "account_name": acc.account_name if acc else "",
            "balance": acc.balance if acc else 0,
            "join_date": m.join_date
        })
    db.close()
    return {"code": 200, "data": result}

@router.post("/sweep")
def pool_sweep(req: SweepReq, Authorization: str = Header(...)):
    """上划下拨 - 余额归集"""
    user = verify_token(Authorization)
    db = SessionLocal()

    pool = db.query(CashPool).filter(CashPool.pool_no == req.pool_no).first()
    if not pool:
        raise HTTPException(status_code=404, detail="现金池不存在")
    if pool.status != "active":
        raise HTTPException(status_code=400, detail="现金池状态异常")
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="归集金额必须大于0")

    member = db.query(PoolMember).filter(
        PoolMember.pool_no == req.pool_no,
        PoolMember.member_account == req.member_account
    ).first()
    if not member:
        raise HTTPException(status_code=400, detail="该账户不是现金池成员")

    master_acc = db.query(BankAccount).filter(BankAccount.account_no == pool.master_account).first()
    member_acc = db.query(BankAccount).filter(BankAccount.account_no == req.member_account).first()

    if req.sweep_type == "上划":
        if member_acc.balance < req.amount:
            raise HTTPException(status_code=400, detail="成员账户余额不足")
        member_acc.balance -= req.amount
        master_acc.balance += req.amount
        from_acc, to_acc = req.member_account, pool.master_account
    elif req.sweep_type == "下拨":
        if master_acc.balance < req.amount:
            raise HTTPException(status_code=400, detail="主账户余额不足")
        master_acc.balance -= req.amount
        member_acc.balance += req.amount
        from_acc, to_acc = pool.master_account, req.member_account
    else:
        raise HTTPException(status_code=400, detail="归集类型只支持：上划/下拨")

    sweep_no = "SWP" + datetime.now().strftime("%Y%m%d%H%M%S")
    sweep = PoolSweep(
        sweep_no=sweep_no,
        pool_no=req.pool_no,
        sweep_type=req.sweep_type,
        from_account=from_acc,
        to_account=to_acc,
        amount=req.amount,
        sweep_date=date.today().strftime("%Y-%m-%d")
    )
    db.add(sweep)
    db.commit()
    db.close()
    return {"code": 200, "message": f"{req.sweep_type}成功", "data": {"sweep_no": sweep_no}}

@router.post("/interest/calc")
def calc_interest(req: InterestCalcReq, Authorization: str = Header(...)):
    """利息计算"""
    verify_token(Authorization)
    db = SessionLocal()

    pool = db.query(CashPool).filter(CashPool.pool_no == req.pool_no).first()
    if not pool:
        raise HTTPException(status_code=404, detail="现金池不存在")
    if req.principal <= 0 or req.days <= 0:
        raise HTTPException(status_code=400, detail="本金和天数必须大于0")

    # 利息 = 本金 × 年利率 × 天数/365
    interest = round(req.principal * pool.interest_rate * req.days / 365, 2)

    record = InterestRecord(
        pool_no=req.pool_no,
        account_no=req.account_no,
        principal=req.principal,
        rate=pool.interest_rate,
        days=req.days,
        interest=interest,
        calc_date=req.calc_date
    )
    db.add(record)
    db.commit()
    db.close()
    return {"code": 200, "data": {"principal": req.principal, "rate": pool.interest_rate,
                                   "days": req.days, "interest": interest}}

@router.get("/sweep/history")
def sweep_history(pool_no: Optional[str] = None, Authorization: str = Header(...)):
    verify_token(Authorization)
    db = SessionLocal()
    query = db.query(PoolSweep)
    if pool_no:
        query = query.filter(PoolSweep.pool_no == pool_no)
    sweeps = query.order_by(PoolSweep.created_at.desc()).limit(50).all()
    result = [{"sweep_no": s.sweep_no, "sweep_type": s.sweep_type,
               "from_account": s.from_account, "to_account": s.to_account,
               "amount": s.amount, "sweep_date": s.sweep_date} for s in sweeps]
    db.close()
    return {"code": 200, "data": result}