# -*- coding: utf-8 -*-
"""认证：注册 / 登录 / 改密。"""
import re
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User
from ..runtime_config import get_section
from ..schemas import ChangePasswordIn, LoginIn, RegisterIn, UserOut
from ..security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 登录失败限流：同工号 1 分钟最多 5 次
_login_lock = threading.Lock()
_login_attempts: dict[str, deque] = defaultdict(deque)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60


def _login_allowed(emp_no: str) -> bool:
    now = time.time()
    with _login_lock:
        q = _login_attempts[emp_no]
        while q and now - q[0] > _LOGIN_WINDOW_SECONDS:
            q.popleft()
        return len(q) < _LOGIN_MAX_ATTEMPTS


def _login_record(emp_no: str, success: bool) -> None:
    if success:
        return
    with _login_lock:
        _login_attempts[emp_no].append(time.time())


@router.post("/register", response_model=UserOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    enums = get_section("enums")
    if body.department and body.department not in enums["departments"]:
        raise HTTPException(400, "部门不在可选范围内")
    if body.job_level and body.job_level not in enums["job_levels"]:
        raise HTTPException(400, "职级不在可选范围内")
    if body.position and body.position not in enums["positions"]:
        raise HTTPException(400, "岗位不在可选范围内")
    if db.query(User).filter(User.emp_no == body.emp_no).first():
        raise HTTPException(409, "员工工号已存在")
    user = User(
        emp_no=body.emp_no,
        name=body.name,
        password_hash=hash_password(body.password),
        role="employee",
        department=body.department,
        job_level=body.job_level,
        position=body.position,
    )
    db.add(user)
    db.add(AuditLog(operator=body.emp_no, action="register", table_name="users", row_id=0,
                    after_json={"emp_no": body.emp_no}))
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    if not _login_allowed(body.emp_no):
        raise HTTPException(429, "登录尝试过于频繁，请1分钟后再试")
    user = db.query(User).filter(User.emp_no == body.emp_no).first()
    if user is None or not verify_password(body.password, user.password_hash):
        _login_record(body.emp_no, success=False)
        raise HTTPException(401, "工号或密码错误")
    _login_record(body.emp_no, success=True)
    return {
        "token": create_token(user),
        "user": UserOut.model_validate(user).model_dump(),
    }


@router.post("/change-password")
def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.emp_no != user.emp_no and user.role != "admin":
        raise HTTPException(403, "只能修改自己的密码")
    target = db.query(User).filter(User.emp_no == body.emp_no).first()
    if target is None:
        raise HTTPException(404, "员工工号不存在")
    if not verify_password(body.old_password, target.password_hash):
        raise HTTPException(400, "原始密码错误")
    target.password_hash = hash_password(body.new_password)
    target.must_change_password = False
    db.add(AuditLog(operator=user.emp_no, action="change_password", table_name="users",
                    row_id=target.id))
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
