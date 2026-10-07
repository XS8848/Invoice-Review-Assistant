# -*- coding: utf-8 -*-
"""API 业务流转测试：状态机全分支，用发票汇总真实发票驱动。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from util import (  # noqa: E402
    INVOICE_DIR,
    ROOT_INVOICE_DIR,
    admin_token,
    auth,
    client,
    employee,
    upload_files,
    wait_terminal,
)

INV = INVOICE_DIR
ROOT = ROOT_INVOICE_DIR


class TestBusinessFlow:
    def test_personal_buyer_rejected(self, client, employee):
        """分支1：抬头为个人 → 规则硬拦截不报销（不调LLM）。"""
        token, _ = employee
        created = upload_files(client, token, [INV / "397dd4f7-8d62-4b93-8ac5-064ca5fb418b756.pdf"])
        rows = wait_terminal(client, token, [c["id"] for c in created])
        r = rows[0]
        assert r["flow_status"] == 0 and r["reimb_result"] == 1
        assert ("抬头" in r["model_note"]) or ("个人" in r["model_note"]), r["model_note"]
        assert r["rule_check"]["hard_fail"], r["rule_check"]

    def test_expired_rejected(self, client, employee):
        """分支2：过期发票 → 规则硬拦截。"""
        token, _ = employee
        created = upload_files(
            client, token, [ROOT / "95adbd866ebd52e6a1e2c0298bfec8b3.jpg"])
        rows = wait_terminal(client, token, [c["id"] for c in created])
        r = rows[0]
        assert r["flow_status"] == 0 and r["reimb_result"] == 1
        assert "过期" in r["model_note"], r["model_note"]

    def test_vision_fallback_manual_review(self, client, employee, admin_token):
        """分支3：视觉关键字段缺失 → 待人工 → 审查员判定闭环。"""
        token, _ = employee
        created = upload_files(client, token, [ROOT / "b16.jpg"])
        rows = wait_terminal(client, token, [c["id"] for c in created])
        r = rows[0]
        assert r["flow_status"] == 3 and r["exception_type"] == 1, (r["flow_status"], r["exception_type"])
        queue = client.get("/api/review/queue", headers=auth(admin_token)).json()
        assert any(q["id"] == r["id"] for q in queue)
        resp = client.post(f"/api/review/{r['id']}", headers=auth(admin_token),
                           json={"result": 1, "note": "人工复核：不予报销"})
        assert resp.status_code == 200
        assert resp.json()["flow_status"] == 0 and resp.json()["reimb_result"] == 1

    def test_llm_or_rule_path(self, client, employee, admin_token):
        """分支4：正常发票 → 规则通过则 LLM 判定；硬不过则规则拦截（记录实际分支）。"""
        token, _ = employee
        created = upload_files(
            client, token,
            [INV / "宁波高新区岚强餐饮店（个体工商户）_发票金额1500.00元.pdf"],
            note="客户招待用餐，事由：项目庆功宴",
        )
        rows = wait_terminal(client, token, [c["id"] for c in created])
        r = rows[0]
        assert r["flow_status"] in (0, 3), r
        if r["flow_status"] == 3:  # LLM 无法判断 → 人工兜底
            assert r["exception_type"] == 2
            resp = client.post(f"/api/review/{r['id']}", headers=auth(admin_token),
                               json={"result": 0, "note": "人工复核通过"})
            assert resp.status_code == 200
            r = resp.json()
        if r["rule_check"]["hard_fail"]:
            assert r["reimb_result"] == 1
        else:
            assert r["reimb_result"] in (0, 1)  # LLM 语义判定

    def test_batch_grouping(self, client, employee):
        """同一次上传 = 一个批次；批次接口返回全部文件。"""
        token, _ = employee
        created = upload_files(client, token, [INV / "trip.pdf", INV / "invoice.pdf"])
        batch_id = created[0]["batch_id"]
        assert all(c["batch_id"] == batch_id for c in created) and len(created) == 2
        batch = client.get(f"/api/claims/batch/{batch_id}", headers=auth(token))
        assert batch.status_code == 200
        assert len(batch.json()) == 2
        ids = {c["id"] for c in created}
        mine_ids = {c["id"] for c in client.get("/api/claims/mine", headers=auth(token)).json()}
        assert ids <= mine_ids

    def test_batch_forbidden_for_other_employee(self, client, employee):
        token, _ = employee
        created = upload_files(client, token, [INV / "trip.pdf"])
        other = client.post("/api/auth/register", json={
            "emp_no": "T9999001", "name": "别人", "password": "Passw0rd!x"})
        assert other.status_code in (200, 409)
        other_token = client.post("/api/auth/login", json={
            "emp_no": "T9999001", "password": "Passw0rd!x"}).json()["token"]
        r = client.get(f"/api/claims/batch/{created[0]['batch_id']}",
                       headers=auth(other_token))
        assert r.status_code == 403

    def test_delete_pending_claim(self, client, employee):
        token, _ = employee
        created = upload_files(client, token, [INV / "trip.pdf"])
        cid = created[0]["id"]
        r = client.delete(f"/api/claims/{cid}", headers=auth(token))
        assert r.status_code == 200, r.text
        assert client.delete(f"/api/claims/{cid}", headers=auth(token)).status_code == 404

    def test_monthly_limit_reject(self, client, employee, admin_token):
        """月累计限额：调低限额 → 新单据硬拦截 → 恢复配置。"""
        token, _ = employee
        cfg = client.get("/api/config", headers=auth(admin_token)).json()
        orig = dict(cfg["rules"])
        low = dict(orig)
        low.update({"per_month_limit": 1, "per_month_limit_action": "reject"})
        try:
            assert client.put("/api/config", headers=auth(admin_token),
                              json={"section": "rules", "value": low}).status_code == 200
            created = upload_files(client, token, [INV / "invoice.pdf"],
                                   note="客户招待用餐")
            rows = wait_terminal(client, token, [c["id"] for c in created])
            r = rows[0]
            assert r["flow_status"] == 0 and r["reimb_result"] == 1
            assert "月限额" in r["model_note"], r["model_note"]
        finally:
            assert client.put("/api/config", headers=auth(admin_token),
                              json={"section": "rules", "value": orig}).status_code == 200

    def test_requeue_reprocess(self, client, employee, admin_token):
        """重派：终态单据重新走完整流程，再次得出不报销（过期）。"""
        token, _ = employee
        created = upload_files(
            client, token, [ROOT / "95adbd866ebd52e6a1e2c0298bfec8b3.jpg"])
        cid = created[0]["id"]
        wait_terminal(client, token, [cid])
        r = client.put(f"/api/dashboard/claims/{cid}/requeue", headers=auth(admin_token))
        assert r.status_code == 200
        rows = wait_terminal(client, token, [cid])
        r = rows[0]
        assert r["flow_status"] == 0 and r["reimb_result"] == 1
        assert "过期" in r["model_note"], r["model_note"]
        assert r["ocr_conf"] is not None  # 重新跑过视觉识别

    def test_concurrent_batches_no_loss(self, client, employee):
        """并发两批上传 → 单据数量精确、无丢失/无重复。"""
        import threading

        token, _ = employee
        results = {}

        def upload_batch(key, paths):
            results[key] = upload_files(client, token, paths)

        t1 = threading.Thread(target=upload_batch, args=("a", [INV / "trip.pdf", INV / "invoice.pdf"]))
        t2 = threading.Thread(target=upload_batch, args=("b", [INV / "滴滴电子发票.pdf"]))
        t1.start(); t2.start(); t1.join(); t2.join()
        ids = [c["id"] for c in results["a"] + results["b"]]
        assert len(ids) == len(set(ids)) == 3
        rows = wait_terminal(client, token, ids)
        assert len(rows) == 3
