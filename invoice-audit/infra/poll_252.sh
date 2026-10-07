#!/usr/bin/env bash
# 轮询 claim 252 至终态（远程 OCR 模式）
PY=/conda/miniconda3/envs/SF157/bin/python
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"emp_no":"TEST0001","password":"test123456"}' | $PY -c 'import sys,json;print(json.load(sys.stdin)["token"])')
for i in $(seq 1 40); do
  sleep 5
  ROW=$(curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/claims/mine \
    | $PY -c "import sys,json;m=json.load(sys.stdin);r=[c for c in m if c['id']==252][0];print(r['flow_status'],r['reimb_result'],r['ocr_conf'],r['model_note'][:30])")
  echo "poll $i: flow result conf note=$ROW"
  FLOW=$(echo "$ROW" | cut -d' ' -f1)
  if [ "$FLOW" = "0" ] || [ "$FLOW" = "3" ] || [ "$FLOW" = "4" ]; then
    echo "TERMINAL"
    break
  fi
done
