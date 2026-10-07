# -*- coding: utf-8 -*-
"""密码哈希（pbkdf2_hmac，零外部依赖）与 JWT 登录态。"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import User

_ITERATIONS = 600_000
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "emp_no": user.emp_no,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    try:
        payload = decode_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录态无效或已过期")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要审查员权限")
    return user
