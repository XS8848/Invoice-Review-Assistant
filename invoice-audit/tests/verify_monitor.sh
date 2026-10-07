#!/usr/bin/env bash
# 验证 /api/monitor 缓存优化后的延迟
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"emp_no":"admin","password":"admin"}' | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "monitor %{time_total}s http=%{http_code}\n" \
    -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/monitor
done
