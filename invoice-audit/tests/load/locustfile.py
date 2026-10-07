# -*- coding: utf-8 -*-
"""Locust 压力测试：员工视图 + 管理员视图 + 上传接口混合负载。"""
import os
import pathlib

from locust import HttpUser, between, task

# 样本自动探测：TEST_INVOICE_DIR 或 env LOCUST_PDF > <工作区>/发票汇总/trip.pdf
_PDF_PATH = os.environ.get("LOCUST_PDF") or os.environ.get("TEST_INVOICE_DIR", "")
if not _PDF_PATH:
    _ws = pathlib.Path(__file__).resolve().parents[2].parent  # 工作区根
    _PDF_PATH = str(_ws / "发票汇总" / "trip.pdf") if (_ws / "发票汇总").is_dir() else str(_ws / "trip.pdf")
with open(_PDF_PATH, "rb") as _f:
    TRIP_PDF = _f.read()


class EmployeeUser(HttpUser):
    weight = 5
    wait_time = between(0.3, 1.0)

    def on_start(self):
        r = self.client.post(
            "/api/auth/login",
            json={"emp_no": "TEST0001", "password": "test123456"},
            timeout=30,
        )
        self.token = r.json().get("token", "") if r.status_code == 200 else ""
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(4)
    def health(self):
        self.client.get("/api/health", timeout=10)

    @task(3)
    def enums(self):
        self.client.get("/api/enums", timeout=10)

    @task(2)
    def my_claims(self):
        if self.token:
            self.client.get("/api/claims/mine", headers=self.headers, timeout=20)

    @task(1)
    def login(self):
        self.client.post(
            "/api/auth/login",
            json={"emp_no": "TEST0001", "password": "test123456"},
            timeout=30,
        )


class AdminUser(HttpUser):
    weight = 1
    wait_time = between(0.5, 1.5)

    def on_start(self):
        r = self.client.post(
            "/api/auth/login",
            json={"emp_no": "admin", "password": "admin"},
            timeout=30,
        )
        self.token = r.json().get("token", "") if r.status_code == 200 else ""
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def stats(self):
        self.client.get("/api/dashboard/stats", headers=self.headers, timeout=20)

    @task(1)
    def monitor(self):
        self.client.get("/api/monitor", headers=self.headers, timeout=20)

    @task(1)
    def tables(self):
        self.client.get("/api/dashboard/tables", headers=self.headers, timeout=20)


class UploadUser(HttpUser):
    """上传接口专项压测（multipart，小 PDF）。"""

    wait_time = between(1.0, 2.0)

    def on_start(self):
        r = self.client.post(
            "/api/auth/login",
            json={"emp_no": "TEST0001", "password": "test123456"},
            timeout=30,
        )
        self.token = r.json().get("token", "") if r.status_code == 200 else ""
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task
    def upload_invoice(self):
        self.client.post(
            "/api/claims",
            params={"note": "压测上传"},
            headers=self.headers,
            files={"files": ("trip.pdf", TRIP_PDF, "application/octet-stream")},
            timeout=60,
        )
