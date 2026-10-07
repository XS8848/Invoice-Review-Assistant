#!/usr/bin/env bash
# 新路径部署后验证
curl -s -o /dev/null -w 'spa login http=%{http_code}\n' http://127.0.0.1:8000/login
curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"emp_no":"admin","password":"admin"}' -o /dev/null -w 'admin login http=%{http_code}\n'
curl -s http://127.0.0.1:8000/api/health
echo ""
