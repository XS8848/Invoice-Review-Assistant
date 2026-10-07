# -*- coding: utf-8 -*-
"""API 测试：认证（注册/登录/改密/限流/鉴权）。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from util import TEST_PASSWORD, auth, client, new_emp_no  # noqa: E402


class TestRegister:
    def test_success(self, client):
        emp = new_emp_no()
        r = client.post("/api/auth/register", json={
            "emp_no": emp, "name": "测试员工", "password": TEST_PASSWORD,
            "department": "技术部", "job_level": "P3", "position": "工程师",
        })
        assert r.status_code == 200, r.text

    def test_duplicate(self, client):
        emp = new_emp_no()
        body = {"emp_no": emp, "name": "测试员工", "password": TEST_PASSWORD}
        assert client.post("/api/auth/register", json=body).status_code == 200
        assert client.post("/api/auth/register", json=body).status_code == 409

    def test_emp_no_too_short(self, client):
        body = {"emp_no": "T123456", "name": "x", "password": TEST_PASSWORD}
        assert client.post("/api/auth/register", json=body).status_code == 422

    def test_emp_no_too_long(self, client):
        body = {"emp_no": "T12345678", "name": "x", "password": TEST_PASSWORD}
        assert client.post("/api/auth/register", json=body).status_code == 422

    def test_emp_no_symbol(self, client):
        body = {"emp_no": "T123456!", "name": "x", "password": TEST_PASSWORD}
        assert client.post("/api/auth/register", json=body).status_code == 422

    def test_invalid_department(self, client):
        body = {"emp_no": new_emp_no(), "name": "x", "password": TEST_PASSWORD,
                "department": "不存在的部门"}
        assert client.post("/api/auth/register", json=body).status_code == 400

    def test_short_password(self, client):
        body = {"emp_no": new_emp_no(), "name": "x", "password": "123"}
        assert client.post("/api/auth/register", json=body).status_code == 422


class TestLogin:
    def test_ok_and_wrong(self, client):
        emp = new_emp_no()
        client.post("/api/auth/register", json={
            "emp_no": emp, "name": "测试员工", "password": TEST_PASSWORD})
        r = client.post("/api/auth/login", json={"emp_no": emp, "password": TEST_PASSWORD})
        assert r.status_code == 200 and r.json()["token"]
        r2 = client.post("/api/auth/login", json={"emp_no": emp, "password": "wrong-pass"})
        assert r2.status_code == 401

    def test_throttle(self, client):
        emp = new_emp_no()  # 不存在的工号也纳入限流，不影响真实账号
        codes = [
            client.post("/api/auth/login", json={"emp_no": emp, "password": "wrong"}).status_code
            for _ in range(6)
        ]
        assert codes[:5] == [401] * 5, codes
        assert codes[5] == 429, codes


class TestChangePassword:
    def test_full_flow(self, client):
        emp = new_emp_no()
        client.post("/api/auth/register", json={
            "emp_no": emp, "name": "测试员工", "password": TEST_PASSWORD})
        token = client.post("/api/auth/login", json={
            "emp_no": emp, "password": TEST_PASSWORD}).json()["token"]
        r = client.post("/api/auth/change-password", headers=auth(token), json={
            "emp_no": emp, "old_password": TEST_PASSWORD, "new_password": "NewPassw0rd!"})
        assert r.status_code == 200, r.text
        assert client.post("/api/auth/login", json={
            "emp_no": emp, "password": TEST_PASSWORD}).status_code == 401
        assert client.post("/api/auth/login", json={
            "emp_no": emp, "password": "NewPassw0rd!"}).status_code == 200

    def test_wrong_old_password(self, client):
        emp = new_emp_no()
        client.post("/api/auth/register", json={
            "emp_no": emp, "name": "测试员工", "password": TEST_PASSWORD})
        token = client.post("/api/auth/login", json={
            "emp_no": emp, "password": TEST_PASSWORD}).json()["token"]
        r = client.post("/api/auth/change-password", headers=auth(token), json={
            "emp_no": emp, "old_password": "wrong", "new_password": "NewPassw0rd!"})
        assert r.status_code == 400

    def test_change_others_forbidden(self, client):
        emp1, emp2 = new_emp_no(), new_emp_no()
        for emp in (emp1, emp2):
            client.post("/api/auth/register", json={
                "emp_no": emp, "name": "测试员工", "password": TEST_PASSWORD})
        token1 = client.post("/api/auth/login", json={
            "emp_no": emp1, "password": TEST_PASSWORD}).json()["token"]
        r = client.post("/api/auth/change-password", headers=auth(token1), json={
            "emp_no": emp2, "old_password": TEST_PASSWORD, "new_password": "NewPassw0rd!"})
        assert r.status_code == 403


class TestAuthZ:
    def test_no_token(self, client):
        assert client.get("/api/claims/mine").status_code == 401

    def test_tampered_token(self, client):
        emp = new_emp_no()
        client.post("/api/auth/register", json={
            "emp_no": emp, "name": "测试员工", "password": TEST_PASSWORD})
        token = client.post("/api/auth/login", json={
            "emp_no": emp, "password": TEST_PASSWORD}).json()["token"]
        bad = token[:-4] + "abcd"
        assert client.get("/api/claims/mine", headers=auth(bad)).status_code == 401
