#!/usr/bin/env bash
# 查询历史单据中"规则通过、LLM判定"过的发票文件名（用于降级测试选样）
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
/conda/miniconda3/envs/SF157/bin/python - <<'PYEOF'
import pymysql
conn = pymysql.connect(host="127.0.0.1", user="invoice", password="InvoiceAudit_2026_Str0ng",
                       database="invoice_audit", charset="utf8mb4")
cur = conn.cursor()
cur.execute("SELECT file_name, flow_status, reimb_result, exception_type FROM claims WHERE rule_check IS NOT NULL ORDER BY id DESC LIMIT 40")
for row in cur.fetchall():
    print(row)
conn.close()
PYEOF
