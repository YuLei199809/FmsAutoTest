from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from database import SessionLocal, User
import uuid

router = APIRouter()

# 内存中存储有效 token：{token: username}
active_tokens: dict[str, str] = {}


class LoginReq(BaseModel):
    username: str
    password: str


def verify_token(token: str):
    if token.startswith("Bearer "):
        token = token[7:]

    username = active_tokens.get(token)  # ← 从内存查，不查数据库
    if not username:
        raise HTTPException(status_code=401, detail="未授权，请先登录")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        return user
    finally:
        db.close()


@router.post("/login")
def login(req: LoginReq):
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.username == req.username,
            User.password == req.password
        ).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = str(uuid.uuid4())
        active_tokens[token] = user.username  # ← add，不覆盖，多个 token 共存

        username = user.username
        role = user.role
    finally:
        db.close()

    return {"code": 200, "message": "登录成功",
            "data": {"token": token, "username": username, "role": role}}


@router.post("/logout")
def logout(Authorization: str = Header(...)):
    token = Authorization.replace("Bearer ", "")

    if token not in active_tokens:
        raise HTTPException(status_code=401, detail="未授权，请先登录")

    active_tokens.pop(token)  # ← 只移除当前 token，其他 token 不受影响

    return {"code": 200, "message": "登出成功"}