#!/usr/bin/env bash
# 分布式链路验证：后端(远程OCR模式) → 上传 → OCR 组件服务经 HTTP 处理 → 终态
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"emp_no":"TEST0001","password":"test123456"}' | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
FILE="/mnt/c/Users/35192/Desktop/test/发票审计系统/invoice-audit/../发票汇总/trip.pdf"
[ -f "$FILE" ] || FILE="/mnt/c/Users/35192/Desktop/test/发票汇总/trip.pdf"
echo "sample: $FILE"
CREATED=$(curl -s -X POST "http://127.0.0.1:8000/api/claims?note=分布式OCR链路验证" \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@$FILE" | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json;d=json.load(sys.stdin);print(d[0]["id"])')
echo "claim id: $CREATED"
for i in $(seq 1 40); do
  sleep 5
  ROW=$(curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/claims/mine \
    | /conda/miniconda3/envs/SF157/bin/python -c "import sys,json;m=json.load(sys.stdin);r=[c for c in m if c['id']==$CREATED][0];print(r['flow_status'],r['reimb_result'],r['ocr_conf'])")
  echo "  poll: flow result conf=$ROW"
  FLOW=$(echo $ROW | cut -d' ' -f1)
  if [ "$FLOW" = "0" ] || [ "$FLOW" = "3" ] || [ "$FLOW" = "4" ]; then break; fi
done
