from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal, Bill, BillEndorsement, BillDiscount
from routers.auth import verify_token
from datetime import datetime
import uuid

router = APIRouter()

class BillCreateReq(BaseModel):
    bill_type: str
    drawer: str
    acceptor: str
    payee: str
    amount: float
    issue_date: str
    due_date: str

class EndorseReq(BaseModel):
    bill_no: str
    endorsee: str
    endorsed_at: str
    purpose: str

class DiscountReq(BaseModel):
    bill_no: str
    bank_name: str
    discount_rate: float
    discount_amount: float
    discount_date: str

@router.post("/create")
def create_bill(req: BillCreateReq, Authorization: str = Header(...)):
    user = verify_token(Authorization)
    db = SessionLocal()

    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="票据金额必须大于0")
    if req.issue_date >= req.due_date:
        raise HTTPException(status_code=400, detail="到期日必须晚于出票日")

    bill_no = "BA" + datetime.now().strftime("%Y%m%d%H%M%S") + str(uuid.uuid4())[:4].upper()
    bill = Bill(
        bill_no=bill_no,
        bill_type=req.bill_type,
        drawer=req.drawer,
        acceptor=req.acceptor,
        payee=req.payee,
        amount=req.amount,
        issue_date=req.issue_date,
        due_date=req.due_date,
        status="holding",
        created_by=user.username
    )
    db.add(bill)
    db.commit()
    db.close()
    return {"code": 200, "message": "票据录入成功", "data": {"bill_no": bill_no}}

@router.get("/list")
def list_bills(
    status: Optional[str] = None,
    bill_type: Optional[str] = None,
    Authorization: str = Header(...)
):
    verify_token(Authorization)
    db = SessionLocal()
    query = db.query(Bill)
    if status:
        query = query.filter(Bill.status == status)
    if bill_type:
        query = query.filter(Bill.bill_type == bill_type)
    bills = query.order_by(Bill.created_at.desc()).all()
    result = [{"bill_no": b.bill_no, "bill_type": b.bill_type,
               "drawer": b.drawer, "amount": b.amount,
               "issue_date": b.issue_date, "due_date": b.due_date,
               "status": b.status} for b in bills]
    db.close()
    return {"code": 200, "data": result}

@router.post("/endorse")
def endorse_bill(req: EndorseReq, Authorization: str = Header(...)):
    user = verify_token(Authorization)
    db = SessionLocal()

    bill = db.query(Bill).filter(Bill.bill_no == req.bill_no).first()
    if not bill:
        raise HTTPException(status_code=404, detail="票据不存在")
    if bill.status != "holding":
        raise HTTPException(status_code=400, detail=f"当前票据状态{bill.status}，不可背书")

    endorsement = BillEndorsement(
        bill_no=req.bill_no,
        endorsee=req.endorsee,
        endorsed_at=req.endorsed_at,
        purpose=req.purpose,
        operator=user.username
    )
    bill.status = "endorsed"
    db.add(endorsement)
    db.commit()
    db.close()
    return {"code": 200, "message": "背书转让成功"}

@router.post("/discount")
def discount_bill(req: DiscountReq, Authorization: str = Header(...)):
    user = verify_token(Authorization)
    db = SessionLocal()

    bill = db.query(Bill).filter(Bill.bill_no == req.bill_no).first()
    if not bill:
        raise HTTPException(status_code=404, detail="票据不存在")
    if bill.status not in ["holding"]:
        raise HTTPException(status_code=400, detail=f"当前票据状态{bill.status}，不可贴现")
    if req.discount_rate <= 0 or req.discount_rate >= 1:
        raise HTTPException(status_code=400, detail="贴现率必须在0到1之间")
    if req.discount_amount <= 0 or req.discount_amount > bill.amount:
        raise HTTPException(status_code=400, detail="贴现金额异常")

    discount = BillDiscount(
        bill_no=req.bill_no,
        bank_name=req.bank_name,
        discount_rate=req.discount_rate,
        discount_amount=req.discount_amount,
        discount_date=req.discount_date,
        operator=user.username
    )
    bill.status = "discounted"
    db.add(discount)
    db.commit()
    db.close()
    return {"code": 200, "message": "贴现成功", "data": {"discount_amount": req.discount_amount}}

@router.get("/expiring")
def expiring_bills(days: int = Query(30), Authorization: str = Header(...)):
    """查询即将到期票据"""
    verify_token(Authorization)
    from datetime import date, timedelta
    db = SessionLocal()
    threshold = (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")
    today = date.today().strftime("%Y-%m-%d")
    bills = db.query(Bill).filter(
        Bill.due_date <= threshold,
        Bill.due_date >= today,
        Bill.status == "holding"
    ).all()
    result = [{"bill_no": b.bill_no, "amount": b.amount,
               "due_date": b.due_date, "bill_type": b.bill_type,
               "drawer": b.drawer} for b in bills]
    db.close()
    return {"code": 200, "data": result, "total": len(result)}