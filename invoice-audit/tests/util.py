# -*- coding: utf-8 -*-
"""测试公共工具与 fixture（路径自动探测：环境变量优先，否则按项目位置推导）。"""
import os
import pathlib
import sys
import time
import uuid

import httpx
import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

BASE = os.environ.get("TEST_BASE", "http://127.0.0.1:8000")


def _find_invoice_dir() -> pathlib.Path:
    """样本目录自动探测：TEST_INVOICE_DIR > <工作区>/发票汇总 > <工作区>（初始5张样本）。"""
    env = os.environ.get("TEST_INVOICE_DIR")
    if env:
        return pathlib.Path(env)
    project_root = pathlib.Path(__file__).resolve().parents[2]   # 发票审计系统/
    workspace = project_root.parent                              # 工作区根
    cand = workspace / "发票汇总"
    return cand if cand.is_dir() else workspace


INVOICE_DIR = _find_invoice_dir()
ROOT_INVOICE_DIR = INVOICE_DIR.parent
TEST_PASSWORD = "Passw0rd!x"


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE, timeout=120) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post("/api/auth/login", json={"emp_no": "admin", "password": "admin"})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return r.json()["token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def new_emp_no() -> str:
    return "T" + uuid.uuid4().hex[:7].upper()


def register_employee(client: httpx.Client, emp_no: str | None = None) -> str:
    emp = emp_no or new_emp_no()
    r = client.post(
        "/api/auth/register",
        json={
            "emp_no": emp,
            "name": "测试员工",
            "password": TEST_PASSWORD,
            "department": "技术部",
            "job_level": "P3",
            "position": "工程师",
        },
    )
    assert r.status_code == 200, f"register failed: {r.text}"
    return emp


@pytest.fixture()
def employee(client):
    """新建员工并登录，返回 (token, emp_no)。"""
    emp = register_employee(client)
    r = client.post("/api/auth/login", json={"emp_no": emp, "password": TEST_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"], emp


def upload_files(client: httpx.Client, token: str, paths: list, note: str = ""):
    files = [
        ("files", (p.name, p.read_bytes(), "application/octet-stream")) for p in paths
    ]
    r = client.post("/api/claims", params={"note": note}, headers=auth(token), files=files)
    assert r.status_code == 200, f"upload failed: {r.text}"
    return r.json()


def wait_terminal(client: httpx.Client, token: str, claim_ids: list[int],
                  timeout: int = 900, poll: int = 5) -> list:
    ids = set(claim_ids)
    deadline = time.time() + timeout
    while time.time() < deadline:
        mine = client.get("/api/claims/mine", headers=auth(token)).json()
        subset = [c for c in mine if c["id"] in ids]
        if subset and all(c["flow_status"] in (0, 3, 4) for c in subset):
            return subset
        time.sleep(poll)
    raise AssertionError(f"等待终态超时: {sorted(ids)}")
