# -*- coding: utf-8 -*-
"""单元测试：密码哈希与 JWT（无外部服务）。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

import jwt
import pytest

from app import config
from app.models import User
from app.security import create_token, decode_token, hash_password, verify_password


class TestPassword:
    def test_roundtrip(self):
        h = hash_password("Passw0rd!x")
        assert h.startswith("pbkdf2$")
        assert verify_password("Passw0rd!x", h)

    def test_wrong_password(self):
        h = hash_password("Passw0rd!x")
        assert not verify_password("wrong", h)

    def test_unique_salt(self):
        h1, h2 = hash_password("same"), hash_password("same")
        assert h1 != h2

    def test_malformed_hash(self):
        assert not verify_password("x", "not-a-hash")
        assert not verify_password("x", "pbkdf2$abc$zz$yy")


class TestJWT:
    def _user(self):
        return User(id=1, emp_no="T1234567", name="张三", password_hash="x",
                    role="employee", department="", job_level="", position="")

    def test_roundtrip(self):
        token = create_token(self._user())
        payload = decode_token(token)
        assert payload["emp_no"] == "T1234567"
        assert payload["role"] == "employee"

    def test_tampered(self):
        token = create_token(self._user())
        tampered = token[:-4] + ("aaaa" if token[-4:] != "aaaa" else "bbbb")
        with pytest.raises(jwt.PyJWTError):
            decode_token(tampered)

    def test_wrong_secret(self):
        token = create_token(self._user())
        with pytest.raises(jwt.PyJWTError):
            jwt.decode(token, "another-secret", algorithms=[config.JWT_ALGORITHM])
