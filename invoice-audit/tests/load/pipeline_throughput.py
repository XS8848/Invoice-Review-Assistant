# -*- coding: utf-8 -*-
"""管道吞吐测试：20 文件批次（发票汇总真实样本）全链路计时 + 并发批次无损校验。

产出 JSON 指标：总耗时、吞吐(文件/分钟)、各状态分布、置信度统计、LLM/规则分支分布。
"""
import json
import pathlib
import statistics
import sys
import time
import uuid

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # tests/

from util import INVOICE_DIR, auth, new_emp_no  # noqa: E402

BASE = "http://127.0.0.1:8000"
INV = INVOICE_DIR

BATCH_FILES = [
    "b0.jpg", "b1.jpg", "b2.jpg", "b3.jpg", "b4.jpg",
    "b5.jpg", "b6.jpg", "b7.jpg", "b8.jpg", "b9.jpg",
    "25119111389000931867-电子发票.pdf",
    "25119220276000001028.pdf",
    "25419220750000055610.pdf",
    "26429165818004912790-电子发票(2).pdf",
    "26429165818004912812-电子发票.pdf",
    "digital_26317000003318848557.pdf",
    "dzfp_24134000000001440516_涿州栩瑶酒店管理有限公司_20260910142252.pdf",
    "dzfp_25132000000109393460_高碑店市尚静酒店管理有限公司_20250626084700.pdf",
    "dzfp_26612000001657216561_陕西境洁佳城市服务有限公司_20260831171126.pdf",
    "滴滴电子发票.pdf",
]


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=180)
    emp = new_emp_no()
    client.post("/api/auth/register", json={
        "emp_no": emp, "name": "压测员工", "password": "Passw0rd!x",
        "department": "技术部", "job_level": "P3", "position": "工程师",
    })
    token = client.post("/api/auth/login", json={
        "emp_no": emp, "password": "Passw0rd!x"}).json()["token"]

    # ---- 20 文件批次 ----
    print("== 20文件批次全链路 ==", flush=True)
    files = [
        ("files", (n, (INV / n).read_bytes(), "application/octet-stream"))
        for n in BATCH_FILES
    ]
    t0 = time.time()
    r = client.post("/api/claims", params={"note": "压测批次：客户招待用餐"},
                    headers=auth(token), files=files)
    upload_sec = time.time() - t0
    assert r.status_code == 200, r.text
    created = r.json()
    ids = [c["id"] for c in created]
    print(f"upload {len(created)} files in {upload_sec:.1f}s", flush=True)

    deadline = time.time() + 1200
    while time.time() < deadline:
        mine = client.get("/api/claims/mine", headers=auth(token)).json()
        subset = [c for c in mine if c["id"] in ids]
        terminal = [c for c in subset if c["flow_status"] in (0, 3, 4)]
        if len(terminal) == len(subset) == len(ids):
            break
        print(f"  progress: {len(terminal)}/{len(ids)} terminal", flush=True)
        time.sleep(8)
    total_sec = time.time() - t0

    subset = [c for c in client.get("/api/claims/mine", headers=auth(token)).json()
              if c["id"] in ids]
    assert len(subset) == len(ids), f"丢失单据: {len(subset)}/{len(ids)}"

    flows = {}
    results = {}
    confs = [c["ocr_conf"] for c in subset if c["ocr_conf"] is not None]
    rule_rejected = sum(1 for c in subset
                        if c.get("rule_check") and c["rule_check"].get("hard_fail"))
    llm_judged = sum(1 for c in subset if c.get("rule_check") and not c["rule_check"].get("hard_fail")
                     and c["flow_status"] in (0, 3))
    for c in subset:
        flows[c["flow_status"]] = flows.get(c["flow_status"], 0) + 1
        results[c["reimb_result"]] = results.get(c["reimb_result"], 0) + 1

    metrics = {
        "files": len(ids),
        "upload_seconds": round(upload_sec, 1),
        "total_seconds": round(total_sec, 1),
        "throughput_files_per_min": round(len(ids) / total_sec * 60, 1),
        "flow_distribution": flows,
        "result_distribution": results,
        "conf": {
            "count": len(confs),
            "min": round(min(confs), 4) if confs else None,
            "avg": round(statistics.mean(confs), 4) if confs else None,
            "max": round(max(confs), 4) if confs else None,
        },
        "rule_rejected": rule_rejected,
        "llm_judged": llm_judged,
        "manual_review_needed": flows.get(3, 0),
    }

    # ---- 并发双批次（3+3）无损校验 ----
    print("== 并发双批次无损校验 ==", flush=True)
    import threading

    box: dict = {}

    def up(key, paths):
        fs = [("files", (n, (INV / n).read_bytes(), "application/octet-stream"))
              for n in paths]
        box[key] = client.post("/api/claims", params={"note": "并发批次"},
                               headers=auth(token), files=fs).json()

    t1 = threading.Thread(target=up, args=("a", ["trip.pdf", "invoice.pdf", "电子发票-0HX5112000lw6ez8048E6.pdf"]))
    t2 = threading.Thread(target=up, args=("b", ["e_1.jpg", "e_2.png", "e_3.jpg"]))
    t1.start(); t2.start(); t1.join(); t2.join()
    conc_ids = [c["id"] for c in box["a"] + box["b"]]
    assert len(conc_ids) == len(set(conc_ids)) == 6
    while time.time() < deadline + 600:
        mine = client.get("/api/claims/mine", headers=auth(token)).json()
        conc = [c for c in mine if c["id"] in conc_ids]
        if len(conc) == 6 and all(c["flow_status"] in (0, 3, 4) for c in conc):
            break
        time.sleep(8)
    conc = [c for c in client.get("/api/claims/mine", headers=auth(token)).json()
            if c["id"] in conc_ids]
    assert len(conc) == 6 and all(c["flow_status"] in (0, 3, 4) for c in conc), "并发批次未全部终态"
    metrics["concurrent_batches"] = {"uploaded": 6, "terminal": len(conc), "loss": 0}

    print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
