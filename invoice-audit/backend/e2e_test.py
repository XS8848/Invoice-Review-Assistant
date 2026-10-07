# -*- coding: utf-8 -*-
"""端到端验收（MySQL 生产版）：注册→限流→登录→上传5张发票→状态机→人工→月限额→重派。"""
import json
import os
import pathlib
import time

import httpx

BASE = os.environ.get("TEST_BASE", "http://127.0.0.1:8000")
# 样本目录自动探测：TEST_INVOICE_DIR > <工作区>/发票汇总 > <工作区>（初始5张样本）
_env_ws = os.environ.get("TEST_INVOICE_DIR")
if _env_ws:
    WS = pathlib.Path(_env_ws)
else:
    _root = pathlib.Path(__file__).resolve().parents[2].parent  # 工作区根
    WS = (_root / "发票汇总") if (_root / "发票汇总").is_dir() else _root
SAMPLES = [
    "95adbd866ebd52e6a1e2c0298bfec8b3.jpg",
    "c138a50b121caf9657fba47e4e962c03.jpg",
    "b16.jpg",
    "9206c870-3516-483a-a273-22744be79f15473(1).pdf",
    "397dd4f7-8d62-4b93-8ac5-064ca5fb418b756.pdf",
]

c = httpx.Client(base_url=BASE, timeout=120)


def log(*a):
    print(*a, flush=True)


def req(method, path, token=None, expect_ok=True, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = c.request(method, path, headers=headers, **kw)
    if expect_ok and r.status_code >= 400:
        log(f"!! {method} {path} -> {r.status_code}: {r.text[:300]}")
        raise SystemExit(1)
    return r


def rj(r):
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else r


def wait_terminal(token, extra_ids=()):
    for _ in range(120):
        mine = rj(req("GET", "/api/claims/mine", token=token))
        mine = [x for x in mine if x["id"] in extra_ids] if extra_ids else mine
        done = sum(1 for x in mine if x["flow_status"] in (0, 3, 4))
        for x in mine:
            log(f"  #{x['id']} {x['file_name'][:26]:28s} flow={x['flow_status']} result={x['reimb_result']} conf={x['ocr_conf']} note={x['model_note'][:44]}")
        if done == len(mine) and mine:
            break
        log("  ...waiting")
        time.sleep(5)
    else:
        log("!! 超时：仍有单据未到终态")
    return mine


# 1. 健康检查
log("== health ==", json.dumps(rj(req("GET", "/api/health")), ensure_ascii=False))

# 2. 登录限流（假工号 6 连败 → 429，不影响真实账号）
log("== login throttle ==")
codes = []
for i in range(6):
    r = req("POST", "/api/auth/login", expect_ok=False, json={"emp_no": "NOPE0001", "password": "wrong"})
    codes.append(r.status_code)
log("attempts:", codes, "-> 第6次429:", codes[5] == 429)

# 3. 注册 + 登录
log("== register/login ==")
r = req("POST", "/api/auth/register", expect_ok=False, json={
    "emp_no": "TEST0001", "name": "测试员工", "password": "test123456",
    "department": "技术部", "job_level": "P3", "position": "工程师",
})
log("register:", r.status_code, "(200=新建, 409=已存在)")
admin_token = rj(req("POST", "/api/auth/login", json={"emp_no": "admin", "password": "admin"}))["token"]
emp_token = rj(req("POST", "/api/auth/login", json={"emp_no": "TEST0001", "password": "test123456"}))["token"]
log("login ok")

# 4. 上传 5 张发票
log("== upload 5 invoices ==")
files = [("files", (n, (WS / n).read_bytes(), "application/octet-stream")) for n in SAMPLES]
created = rj(req("POST", "/api/claims?note=客户招待用餐报销申请", token=emp_token, files=files))
log("created:", [(x["id"], x["file_name"]) for x in created])

# 5. 轮询到终态
log("== poll status machine ==")
wait_terminal(emp_token)

# 6. 人工审查
log("== review queue ==")
queue = rj(req("GET", "/api/review/queue", token=admin_token))
log("queue:", [(x["id"], x["file_name"], x["exception_type"]) for x in queue])
for item in queue:
    rj(req("POST", f"/api/review/{item['id']}", token=admin_token,
           json={"result": 1, "note": "人工复核：不予报销"}))

# 7. 月累计限额硬拦截：把限额调成 1 元/直接不报销 → 上传新发票 → 应硬拦截
log("== monthly limit (reject) ==")
cfg = rj(req("GET", "/api/config", token=admin_token))
orig_rules = dict(cfg["rules"])
rules_low = dict(orig_rules)
rules_low["per_month_limit"] = 1
rules_low["per_month_limit_action"] = "reject"
rj(req("PUT", "/api/config", token=admin_token, json={"section": "rules", "value": rules_low}))
files2 = [("files", (SAMPLES[3], (WS / SAMPLES[3]).read_bytes(), "application/octet-stream"))]
created2 = rj(req("POST", "/api/claims?note=客户招待用餐", token=emp_token, files=files2))
wait_terminal(emp_token, extra_ids=[x["id"] for x in created2])
# 恢复规则
rj(req("PUT", "/api/config", token=admin_token, json={"section": "rules", "value": orig_rules}))
log("rules restored")

# 8. 失败/已处理重派：把 #1 重新派发 → 应再次走完流程（仍不报销：过期）
log("== requeue #1 ==")
rj(req("PUT", "/api/dashboard/claims/1/requeue", token=admin_token))
wait_terminal(emp_token, extra_ids=[1])

# 9. 看板/监控/审计日志
stats = rj(req("GET", "/api/dashboard/stats", token=admin_token))
log("== dashboard stats ==", json.dumps(stats, ensure_ascii=False))
mon = rj(req("GET", "/api/monitor", token=admin_token))
log("== monitor ==", json.dumps({k: mon[k] for k in ("cpu", "gpu", "database", "minio")}, ensure_ascii=False))
logs = rj(req("GET", "/api/dashboard/audit-logs?page_size=15", token=admin_token))
log("== audit logs ==", [(x["action"], x["table_name"], x["row_id"]) for x in logs])
tables = rj(req("GET", "/api/dashboard/tables", token=admin_token))
log("== tables ==", [(t["table"], t["rows"]) for t in tables])

log("E2E DONE")
