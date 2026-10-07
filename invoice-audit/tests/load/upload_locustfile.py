# -*- coding: utf-8 -*-
"""上传接口专用压测：仅 UploadUser。"""
import os
import pathlib

from locust import HttpUser, between, task

# 样本自动探测：LOCUST_PDF / TEST_INVOICE_DIR > <工作区>/发票汇总/trip.pdf
_PDF_PATH = os.environ.get("LOCUST_PDF") or os.environ.get("TEST_INVOICE_DIR", "")
if not _PDF_PATH:
    _ws = pathlib.Path(__file__).resolve().parents[2].parent  # 工作区根
    _PDF_PATH = str(_ws / "发票汇总" / "trip.pdf") if (_ws / "发票汇总").is_dir() else str(_ws / "trip.pdf")
with open(_PDF_PATH, "rb") as _f:
    TRIP_PDF = _f.read()


class UploadUser(HttpUser):
    wait_time = between(0.8, 1.5)

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
