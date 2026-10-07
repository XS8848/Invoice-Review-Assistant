# -*- coding: utf-8 -*-
"""API 边界与安全测试：文件校验、注入、越权、XSS。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from util import INVOICE_DIR, auth, client, employee, new_emp_no  # noqa: E402

PDF_BYTES = (INVOICE_DIR / "trip.pdf").read_bytes()


class TestFileValidation:
    def test_unsupported_extension(self, client, employee):
        token, _ = employee
        files = [("files", ("evil.exe", b"MZ\x90\x00", "application/octet-stream"))]
        r = client.post("/api/claims", headers=auth(token), files=files)
        assert r.status_code == 400

    def test_fake_magic(self, client, employee):
        token, _ = employee
        files = [("files", ("fake.pdf", b"this is not a pdf", "application/octet-stream"))]
        r = client.post("/api/claims", headers=auth(token), files=files)
        assert r.status_code == 400

    def test_oversize(self, client, employee):
        token, _ = employee
        big = b"%PDF-1.4\n" + b"0" * (21 * 1024 * 1024)
        files = [("files", ("big.pdf", big, "application/octet-stream"))]
        r = client.post("/api/claims", headers=auth(token), files=files)
        assert r.status_code == 400

    def test_too_many_files(self, client, employee):
        token, _ = employee
        files = [("files", (f"f{i}.pdf", PDF_BYTES, "application/octet-stream"))
                 for i in range(21)]
        r = client.post("/api/claims", headers=auth(token), files=files)
        assert r.status_code == 400

    def test_traversal_filename_sanitized(self, client, employee):
        token, _ = employee
        files = [("files", ("../../evil.pdf", PDF_BYTES, "application/octet-stream"))]
        r = client.post("/api/claims", headers=auth(token), files=files)
        assert r.status_code == 200, r.text
        created = r.json()[0]
        assert created["file_name"] == "evil.pdf", created["file_name"]
        assert ".." not in created["file_name"]

    def test_xss_note_stored_as_text(self, client, employee):
        token, _ = employee
        note = "<script>alert('xss')</script>"
        r = client.post("/api/claims", params={"note": note},
                        headers=auth(token),
                        files=[("files", ("trip.pdf", PDF_BYTES, "application/octet-stream"))])
        assert r.status_code == 200
        assert r.json()[0]["user_note"] == note
        # 前端 Vue 模板插值渲染（{{ }}）自动转义，不执行脚本（见测试报告说明）


class TestInjection:
    def test_sql_injection_login(self, client):
        for payload in ["admin' OR '1'='1", "admin' --", 'admin"; DROP TABLE users; --']:
            r = client.post("/api/auth/login",
                            json={"emp_no": payload, "password": "x"})
            assert r.status_code in (401, 429), f"{payload} -> {r.status_code}"

    def test_sql_injection_emp_no_register(self, client):
        for payload in ["T' OR 1=1--", "T1234567;DROP TABLE users"]:
            r = client.post("/api/auth/register",
                            json={"emp_no": payload, "name": "x", "password": "Passw0rd!x"})
            assert r.status_code == 422, f"{payload} -> {r.status_code}"


class TestAuthZ:
    def test_employee_cannot_access_review_queue(self, client, employee):
        token, _ = employee
        assert client.get("/api/review/queue", headers=auth(token)).status_code == 403

    def test_employee_cannot_touch_config(self, client, employee):
        token, _ = employee
        assert client.get("/api/config", headers=auth(token)).status_code == 403
        assert client.put("/api/config", headers=auth(token),
                          json={"section": "rules", "value": {}}).status_code == 403

    def test_employee_cannot_dashboard(self, client, employee):
        token, _ = employee
        assert client.get("/api/dashboard/stats", headers=auth(token)).status_code == 403
        assert client.get("/api/monitor", headers=auth(token)).status_code == 403

    def test_employee_cannot_view_others_file(self, client, employee):
        token, _ = employee
        created = client.post("/api/claims", headers=auth(token),
                              files=[("files", ("trip.pdf", PDF_BYTES, "application/octet-stream"))]).json()
        other_emp = new_emp_no()
        client.post("/api/auth/register", json={
            "emp_no": other_emp, "name": "别人", "password": "Passw0rd!x"})
        other_token = client.post("/api/auth/login", json={
            "emp_no": other_emp, "password": "Passw0rd!x"}).json()["token"]
        r = client.get(f"/api/claims/{created[0]['id']}/file", headers=auth(other_token))
        assert r.status_code == 403

    def test_admin_can_view_any_file(self, client, employee, admin_token):
        token, _ = employee
        created = client.post("/api/claims", headers=auth(token),
                              files=[("files", ("trip.pdf", PDF_BYTES, "application/octet-stream"))]).json()
        r = client.get(f"/api/claims/{created[0]['id']}/file", headers=auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("url", "").startswith("http"), body  # 预签名 URL 以 JSON 返回
        assert ":9000/" in body["url"] or ":9000?" in body["url"]


class TestReviewValidation:
    def test_review_terminal_claim_rejected(self, client, employee, admin_token):
        token, _ = employee
        created = client.post("/api/claims", headers=auth(token),
                              files=[("files", ("trip.pdf", PDF_BYTES, "application/octet-stream"))]).json()
        cid = created[0]["id"]
        r = client.post(f"/api/review/{cid}", headers=auth(admin_token),
                        json={"result": 1, "note": "x"})
        assert r.status_code == 400  # 尚未进入待人工状态

    def test_review_invalid_result(self, client, employee, admin_token):
        token, _ = employee
        created = client.post("/api/claims", headers=auth(token),
                              files=[("files", ("trip.pdf", PDF_BYTES, "application/octet-stream"))]).json()
        r = client.post(f"/api/review/{created[0]['id']}", headers=auth(admin_token),
                        json={"result": 9, "note": "x"})
        assert r.status_code == 422
