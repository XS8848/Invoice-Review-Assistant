# -*- coding: utf-8 -*-
"""API 测试：管理员看板专项（admin/admin）+ 数据修正链路。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from util import auth, client  # noqa: E402


class TestDashboardDeep:
    def test_admin_login_dashboard(self, client):
        """管理员看板账号 admin/admin 登录与角色。"""
        r = client.post("/api/auth/login", json={"emp_no": "admin", "password": "admin"})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"
        assert r.json()["user"]["emp_no"] == "admin"

    def test_stats_consistent_with_tables(self, client, admin_token):
        st = client.get("/api/dashboard/stats", headers=auth(admin_token)).json()
        tables = {t["table"]: t["rows"] for t in
                  client.get("/api/dashboard/tables", headers=auth(admin_token)).json()}
        assert tables["claims"] == st["total"], (tables, st)
        assert tables["users"] == st["users"]
        assert sum(st["by_flow"].values()) == st["total"]

    def test_filter_by_flow(self, client, admin_token):
        r = client.get("/api/dashboard/claims", params={"flow_status": 0, "page_size": 10},
                       headers=auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert all(x["flow_status"] == 0 for x in body["items"])
        assert body["total"] >= len(body["items"])

    def test_filter_by_result(self, client, admin_token):
        r = client.get("/api/dashboard/claims", params={"reimb_result": 1, "page_size": 10},
                       headers=auth(admin_token))
        body = r.json()
        assert all(x["reimb_result"] == 1 for x in body["items"])

    def test_pagination(self, client, admin_token):
        p1 = client.get("/api/dashboard/claims", params={"page": 1, "page_size": 5},
                        headers=auth(admin_token)).json()
        p2 = client.get("/api/dashboard/claims", params={"page": 2, "page_size": 5},
                        headers=auth(admin_token)).json()
        if p1["total"] > 5:
            ids1 = {x["id"] for x in p1["items"]}
            ids2 = {x["id"] for x in p2["items"]}
            assert ids1.isdisjoint(ids2)
            assert len(p2["items"]) == min(5, p1["total"] - 5)

    def test_edit_then_audit_trail(self, client, admin_token):
        items = client.get("/api/dashboard/claims", params={"page_size": 1},
                           headers=auth(admin_token)).json()["items"]
        cid = items[0]["id"]
        before = items[0]["reimb_result"]
        flip = 1 if before == 0 else 0
        r = client.put(f"/api/dashboard/claims/{cid}", headers=auth(admin_token),
                       json={"reimb_result": flip})
        assert r.status_code == 200
        logs = client.get("/api/dashboard/audit-logs?page_size=30",
                          headers=auth(admin_token)).json()
        rec = next((x for x in logs if x["action"] == "dashboard_edit" and x["row_id"] == cid), None)
        assert rec is not None
        assert rec["before_json"]["reimb_result"] == before
        assert rec["after_json"]["reimb_result"] == flip
        # 还原
        client.put(f"/api/dashboard/claims/{cid}", headers=auth(admin_token),
                   json={"reimb_result": before})

    def test_requeue_audit_trail(self, client, admin_token):
        items = client.get("/api/dashboard/claims", params={"flow_status": 0, "page_size": 1},
                           headers=auth(admin_token)).json()["items"]
        assert items, "需有已处理单据"
        cid = items[0]["id"]
        assert client.put(f"/api/dashboard/claims/{cid}/requeue",
                          headers=auth(admin_token)).status_code == 200
        logs = client.get("/api/dashboard/audit-logs?page_size=30",
                          headers=auth(admin_token)).json()
        assert any(x["action"] == "requeue" and x["row_id"] == cid for x in logs)

    def test_audit_log_pagination(self, client, admin_token):
        r = client.get("/api/dashboard/audit-logs", params={"page": 1, "page_size": 5},
                       headers=auth(admin_token))
        assert r.status_code == 200
        assert len(r.json()) <= 5
        assert r.json()[0]["id"] > r.json()[-1]["id"]  # 按时间倒序

    def test_claim_out_contains_full_fields(self, client, admin_token):
        items = client.get("/api/dashboard/claims", params={"page_size": 1},
                           headers=auth(admin_token)).json()["items"]
        x = items[0]
        for k in ("emp_no", "emp_name", "file_name", "flow_status", "reimb_result",
                  "queue_state", "submitted_at", "batch_id"):
            assert k in x, k
