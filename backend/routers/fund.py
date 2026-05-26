from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal, BankAccount, PaymentRequest, ApprovalRecord, ApprovalConfig, FundTransfer, Receipt
from routers.auth import verify_token
from datetime import datetime
import uuid, json

router = APIRouter()

class PaymentReq(BaseModel):
    from_account: str
    to_account: str
    to_bank: str
    to_name: str
    amount: float
    currency: str = "CNY"
    purpose: str
    remark: Optional[str] = None

class ApprovalReq(BaseModel):
    req_no: str
    action: str   # approve / reject
    comment: Optional[str] = None

class TransferReq(BaseModel):
    from_account: str
    to_account: str
    amount: float
    transfer_type: str  # 上划/下拨/调拨

class ReceiptReq(BaseModel):
    to_account: str
    from_name: str
    amount: float
    currency: str = "CNY"
    receipt_date: str


@router.get("/accounts")
def get_accounts(Authorization: str = Header(...)):
    verify_token(Authorization)
    db = SessionLocal()
    try:
        accounts = db.query(BankAccount).all()
        result = [
            {
                "account_no": a.account_no,
                "bank_name": a.bank_name,
                "account_name": a.account_name,
                "balance": a.balance,
                "currency": a.currency,
                "status": a.status,
            }
            for a in accounts
        ]
    finally:
        db.close()
    return {"code": 200, "data": result}


@router.get("/accounts/{account_no}")
def get_account(account_no: str, Authorization: str = Header(...)):
    verify_token(Authorization)
    db = SessionLocal()
    try:
        acc = db.query(BankAccount).filter(BankAccount.account_no == account_no).first()
        if not acc:
            raise HTTPException(status_code=404, detail="账户不存在")
        data = {
            "account_no": acc.account_no,
            "bank_name": acc.bank_name,
            "balance": acc.balance,
            "status": acc.status,
        }
    finally:
        db.close()
    return {"code": 200, "data": data}


@router.post("/payment/apply")
def apply_payment(req: PaymentReq, Authorization: str = Header(...)):
    user = verify_token(Authorization)
    db = SessionLocal()
    try:
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="付款金额必须大于0")

        from_acc = db.query(BankAccount).filter(BankAccount.account_no == req.from_account).first()
        if not from_acc:
            raise HTTPException(status_code=404, detail="付款账户不存在")
        if from_acc.status != "active":
            raise HTTPException(status_code=400, detail="付款账户状态异常")
        if from_acc.balance < req.amount:
            raise HTTPException(status_code=400, detail="账户余额不足")

        config = db.query(ApprovalConfig).filter(
            ApprovalConfig.biz_type == "payment",
            ApprovalConfig.amount_min <= req.amount,
            ApprovalConfig.amount_max >= req.amount
        ).first()
        first_step = json.loads(config.steps)[0] if config else "finance"

        req_no = "PAY" + datetime.now().strftime("%Y%m%d%H%M%S") + str(uuid.uuid4())[:4].upper()
        payment = PaymentRequest(
            req_no=req_no,
            from_account=req.from_account,
            to_account=req.to_account,
            to_bank=req.to_bank,
            to_name=req.to_name,
            amount=req.amount,
            currency=req.currency,
            purpose=req.purpose,
            remark=req.remark,
            status="pending",
            current_step=first_step,
            created_by=user.username,
        )
        db.add(payment)
        db.commit()
        data = {"req_no": req_no, "current_step": first_step}
    finally:
        db.close()
    return {"code": 200, "message": "付款申请已提交", "data": data}


@router.post("/payment/approve")
def approve_payment(req: ApprovalReq, Authorization: str = Header(...)):
    user = verify_token(Authorization)
    db = SessionLocal()
    try:
        payment = db.query(PaymentRequest).filter(PaymentRequest.req_no == req.req_no).first()
        if not payment:
            raise HTTPException(status_code=404, detail="付款申请不存在")
        if payment.status != "pending":
            raise HTTPException(status_code=400, detail="该申请已处理，无法再次审批")
        if payment.current_step != user.role:
            raise HTTPException(status_code=403, detail=f"当前审批步骤需要{payment.current_step}角色")

        record = ApprovalRecord(
            req_no=req.req_no,
            step=user.role,
            action=req.action,
            operator=user.username,
            comment=req.comment,
        )
        db.add(record)

        if req.action == "reject":
            payment.status = "rejected"
            db.commit()
            return {"code": 200, "message": "已拒绝"}

        config = db.query(ApprovalConfig).filter(
            ApprovalConfig.biz_type == "payment",
            ApprovalConfig.amount_min <= payment.amount,
            ApprovalConfig.amount_max >= payment.amount
        ).first()
        steps = json.loads(config.steps) if config else ["finance"]
        current_idx = steps.index(user.role) if user.role in steps else -1
        next_idx = current_idx + 1

        if next_idx >= len(steps):
            from_acc = db.query(BankAccount).filter(BankAccount.account_no == payment.from_account).first()
            from_acc.balance -= payment.amount
            payment.status = "executed"
            payment.current_step = None
            msg = "审批通过，付款已执行"
        else:
            payment.current_step = steps[next_idx]
            payment.status = "pending"
            msg = f"审批通过，流转至下一步：{steps[next_idx]}"

        db.commit()
    finally:
        db.close()
    return {"code": 200, "message": msg}


@router.get("/payment/list")
def list_payments(
    status: Optional[str] = None,
    Authorization: str = Header(...),
):
    verify_token(Authorization)
    db = SessionLocal()
    try:
        query = db.query(PaymentRequest)
        if status:
            query = query.filter(PaymentRequest.status == status)
        payments = query.order_by(PaymentRequest.created_at.desc()).limit(50).all()
        result = [
            {
                "req_no": p.req_no,
                "from_account": p.from_account,
                "to_name": p.to_name,
                "amount": p.amount,
                "status": p.status,
                "current_step": p.current_step,
                "created_by": p.created_by,
                "created_at": str(p.created_at),
            }
            for p in payments
        ]
    finally:
        db.close()
    return {"code": 200, "data": result}


@router.post("/transfer")
def fund_transfer(req: TransferReq, Authorization: str = Header(...)):
    user = verify_token(Authorization)
    db = SessionLocal()
    try:
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="调拨金额必须大于0")
        if req.from_account == req.to_account:
            raise HTTPException(status_code=400, detail="调出和调入账户不能相同")

        from_acc = db.query(BankAccount).filter(BankAccount.account_no == req.from_account).first()
        to_acc = db.query(BankAccount).filter(BankAccount.account_no == req.to_account).first()

        if not from_acc or not to_acc:
            raise HTTPException(status_code=404, detail="账户不存在")
        if from_acc.status != "active" or to_acc.status != "active":
            raise HTTPException(status_code=400, detail="账户状态异常")
        if from_acc.balance < req.amount:
            raise HTTPException(status_code=400, detail="余额不足")

        from_acc.balance -= req.amount
        to_acc.balance += req.amount

        transfer_no = "TRF" + datetime.now().strftime("%Y%m%d%H%M%S")
        transfer = FundTransfer(
            transfer_no=transfer_no,
            from_account=req.from_account,
            to_account=req.to_account,
            amount=req.amount,
            transfer_type=req.transfer_type,
            status="completed",
            created_by=user.username,
        )
        db.add(transfer)
        db.commit()
        data = {"transfer_no": transfer_no}
    finally:
        db.close()
    return {"code": 200, "message": "调拨成功", "data": data}


@router.post("/receipt")
def create_receipt(req: ReceiptReq, Authorization: str = Header(...)):
    user = verify_token(Authorization)
    db = SessionLocal()
    try:
        acc = db.query(BankAccount).filter(BankAccount.account_no == req.to_account).first()
        if not acc:
            raise HTTPException(status_code=404, detail="收款账户不存在")
        if acc.status != "active":
            raise HTTPException(status_code=400, detail="账户状态异常")
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="收款金额必须大于0")

        acc.balance += req.amount
        receipt_no = "RCP" + datetime.now().strftime("%Y%m%d%H%M%S")
        receipt = Receipt(
            receipt_no=receipt_no,
            to_account=req.to_account,
            from_name=req.from_name,
            amount=req.amount,
            currency=req.currency,
            receipt_date=req.receipt_date,
            created_by=user.username,
        )
        db.add(receipt)
        db.commit()
        data = {"receipt_no": receipt_no}
    finally:
        db.close()
    return {"code": 200, "message": "收款登记成功", "data": data}