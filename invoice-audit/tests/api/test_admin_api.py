# -*- coding: utf-8 -*-
"""API 测试：管理员接口（调参/监控/看板/审计日志）。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from util import admin_token, auth, client  # noqa: E402


class TestConfigApi:
    def test_get_sections(self, client, admin_token):
        cfg = client.get("/api/config", headers=auth(admin_token)).json()
        assert set(cfg) >= {"vision", "llm", "rules", "enums"}

    def test_no_api_key_leak(self, client, admin_token):
        cfg = client.get("/api/config", headers=auth(admin_token)).json()
        llm = cfg["llm"]
        assert "api_key" not in llm or llm.get("api_key") in ("", "***")

    def test_invalid_section(self, client, admin_token):
        r = client.put("/api/config", headers=auth(admin_token),
                       json={"section": "not_exist", "value": {}})
        assert r.status_code == 400

    def test_roundtrip(self, client, admin_token):
        cfg = client.get("/api/config", headers=auth(admin_token)).json()
        orig = cfg["vision"]["conf_threshold"]
        try:
            val = dict(cfg["vision"])
            val["conf_threshold"] = 0.66
            r = client.put("/api/config", headers=auth(admin_token),
                           json={"section": "vision", "value": val})
            assert r.status_code == 200
            got = client.get("/api/config", headers=auth(admin_token)).json()
            assert got["vision"]["conf_threshold"] == 0.66
        finally:
            val = dict(client.get("/api/config", headers=auth(admin_token)).json()["vision"])
            val["conf_threshold"] = orig
            client.put("/api/config", headers=auth(admin_token),
                       json={"section": "vision", "value": val})


class TestMonitor:
    def test_monitor_keys(self, client, admin_token):
        mon = client.get("/api/monitor", headers=auth(admin_token)).json()
        for k in ("cpu", "memory", "disk", "gpu", "database", "minio"):
            assert k in mon, mon.keys()
        assert mon["database"]["status"] == "ok"
        assert mon["minio"]["healthy"] is True

    def test_gpu_available(self, client, admin_token):
        mon = client.get("/api/monitor", headers=auth(admin_token)).json()
        assert mon["gpu"]["available"] is True
        assert mon["gpu"]["mem_total_mb"] > 0


class TestDashboard:
    def test_stats(self, client, admin_token):
        st = client.get("/api/dashboard/stats", headers=auth(admin_token)).json()
        assert isinstance(st["total"], int) and st["total"] > 0
        assert set(st) >= {"total", "by_flow", "by_result", "users"}

    def test_tables(self, client, admin_token):
        tables = client.get("/api/dashboard/tables", headers=auth(admin_token)).json()
        names = {t["table"] for t in tables}
        assert {"users", "claims", "configs", "audit_logs"} <= names
        for t in tables:
            assert t["rows"] is not None, t  # MySQL 方言引号修复生效

    def test_audit_logs(self, client, admin_token):
        logs = client.get("/api/dashboard/audit-logs", headers=auth(admin_token)).json()
        assert isinstance(logs, list)
        assert any(x["action"] in ("register", "review", "requeue", "update_config")
                   for x in logs), logs[:5]

    def test_edit_claim_writes_audit(self, client, admin_token):
        items = client.get("/api/dashboard/claims?page_size=5",
                           headers=auth(admin_token)).json()["items"]
        assert items, "库中应有历史单据"
        cid = items[0]["id"]
        r = client.put(f"/api/dashboard/claims/{cid}", headers=auth(admin_token),
                       json={"reimb_result": items[0]["reimb_result"]})
        assert r.status_code == 200
        logs = client.get("/api/dashboard/audit-logs?page_size=20",
                          headers=auth(admin_token)).json()
        assert any(x["action"] == "dashboard_edit" and x["row_id"] == cid for x in logs)

    def test_requeue_endpoint(self, client, admin_token):
        items = client.get("/api/dashboard/claims?page_size=5",
                           headers=auth(admin_token)).json()["items"]
        cid = items[0]["id"]
        r = client.put(f"/api/dashboard/claims/{cid}/requeue", headers=auth(admin_token))
        assert r.status_code == 200
