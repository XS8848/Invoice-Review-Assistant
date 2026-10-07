#!/usr/bin/env bash
# 验证看板表行数统计（MySQL 修复后）
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"emp_no":"admin","password":"admin"}' | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s http://127.0.0.1:8000/api/dashboard/tables -H "Authorization: Bearer $TOKEN"
echo ""
curl -s -o /dev/null -w 'spa home http=%{http_code}\n' http://127.0.0.1:8000/home/employee
