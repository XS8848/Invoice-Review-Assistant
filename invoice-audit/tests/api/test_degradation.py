# -*- coding: utf-8 -*-
"""API 故障降级与恢复测试：LLM 不可用→转人工；worker 崩溃锁→租约自动回收。"""
import pathlib
import sys
import time

import pymysql
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from util import (  # noqa: E402
    INVOICE_DIR,
    admin_token,
    auth,
    client,
    employee,
    upload_files,
    wait_terminal,
)

INV = INVOICE_DIR
DB = dict(host="127.0.0.1", user="invoice", password="InvoiceAudit_2026_Str0ng",
          database="invoice_audit", charset="utf8mb4", autocommit=True)


def _db_exec(sql, args=()):
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
    finally:
        conn.close()


class TestLLMDegradation:
    """语言模型不可用（base_url 指向无效地址）→ 工具调用两次失败 → 转人工，不丢单。"""

    def test_llm_down_falls_back_to_manual(self, client, employee, admin_token):
        token, _ = employee
        cfg = client.get("/api/config", headers=auth(admin_token)).json()
        orig_llm = dict(cfg["llm"])
        bad = dict(orig_llm)
        bad["base_url"] = "http://127.0.0.1:9/v1"  # 不可达端口
        try:
            assert client.put("/api/config", headers=auth(admin_token),
                              json={"section": "llm", "value": bad}).status_code == 200
            # e_1.jpg 历史已验证可过规则进入 LLM 阶段（此前异常类型=2 无法判断）
            created = upload_files(client, token, [INV / "e_1.jpg"], note="客户招待用餐")
            rows = wait_terminal(client, token, [c["id"] for c in created], timeout=300)
            r = rows[0]
            assert r["flow_status"] == 3, f"应转人工而非终态: {r}"
            assert r["exception_type"] == 2
            assert "转人工" in r["model_note"], r["model_note"]
            # 人工兜底判定闭环
            resp = client.post(f"/api/review/{r['id']}", headers=auth(admin_token),
                               json={"result": 1, "note": "降级测试人工判定"})
            assert resp.status_code == 200
            assert resp.json()["flow_status"] == 0
        finally:
            assert client.put("/api/config", headers=auth(admin_token),
                              json={"section": "llm", "value": orig_llm}).status_code == 200


class TestCrashLockRecovery:
    """worker 崩溃遗留的过期锁（queue=0 + 20 分钟前锁）→ 租约回收线程 60s 内重置 → 正常处理到终态。"""

    @pytest.mark.parametrize("trial", range(3))
    def test_lease_reaper_recovers(self, client, employee, trial):
        token, _ = employee
        created = upload_files(client, token, [INV / "trip.pdf"])
        cid = created[0]["id"]
        # 伪造崩溃遗留锁（仅当尚未被领取时生效）
        _db_exec(
            "UPDATE claims SET queue_state=0, lock_owner='dead-worker', "
            "lock_acquired_at = NOW() - INTERVAL 20 MINUTE "
            "WHERE id=%s AND queue_state=1",
            (cid,),
        )
        rows = wait_terminal(client, token, [cid], timeout=180)
        r = rows[0]
        assert r["flow_status"] in (0, 3, 4), r
        # 若伪造成功（被租约重置后处理），锁应已清空
        mine = client.get("/api/claims/mine", headers=auth(token)).json()
        rec = next(x for x in mine if x["id"] == cid)
        assert rec["queue_state"] in (1, 2), rec
