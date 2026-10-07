#!/usr/bin/env bash
# 上传接口专项压测（UploadUser 3 并发 20s）+ 观察 OCR 积压消化曲线
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python -m locust -f load/upload_locustfile.py --headless -u 5 -r 5 -t 20s \
  --host http://127.0.0.1:8000 --only-summary 2>&1 | tail -20
echo "--- 积压消化观察 ---"
/conda/miniconda3/envs/SF157/bin/python - <<'PYEOF'
import pymysql, time
conn = pymysql.connect(host="127.0.0.1", user="invoice", password="InvoiceAudit_2026_Str0ng",
                       database="invoice_audit", charset="utf8mb4", autocommit=True)
cur = conn.cursor()
def counts():
    cur.execute("SELECT flow_status, COUNT(*) FROM claims WHERE flow_status IN (1,2) GROUP BY flow_status")
    return dict(cur.fetchall())
start = counts()
print("压测后待处理(flow1+2):", start, flush=True)
t0 = time.time()
while time.time() - t0 < 600:
    c = counts()
    if not c:
        print(f"积压消化完毕 耗时 {time.time()-t0:.0f}s", flush=True)
        break
    print(f"  {time.time()-t0:6.0f}s 待处理 {c}", flush=True)
    time.sleep(15)
else:
    print("!! 10 分钟未消化完：", counts())
conn.close()
PYEOF
