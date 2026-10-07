#!/usr/bin/env bash
# 排查分布式模式上传失败原因
PY=/conda/miniconda3/envs/SF157/bin/python
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"emp_no":"TEST0001","password":"test123456"}' | $PY -c 'import sys,json;print(json.load(sys.stdin)["token"])')
echo "TOKEN_LEN=${#TOKEN}"
echo "--- 上传原始响应 ---"
curl -s -X POST 'http://127.0.0.1:8000/api/claims?note=distributed_check' \
  -H "Authorization: Bearer $TOKEN" \
  -F 'files=@/mnt/c/Users/35192/Desktop/test/发票汇总/trip.pdf' \
  -w $'\nHTTP=%{http_code}\n' | head -c 800
echo ""
echo "--- 后端日志尾部 ---"
tail -8 /home/backer/invoice-audit/backend.log
