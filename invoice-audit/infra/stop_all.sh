#!/usr/bin/env bash
# 下线：停止后端 + MinIO（MySQL 由 root 单独停）
pkill -f "uvicorn app.main" 2>/dev/null && echo "backend: 已停止" || echo "backend: 未运行"
sleep 2
pkill -x minio 2>/dev/null && echo "minio: 已停止" || echo "minio: 未运行"
sleep 1
echo "== 校验 =="
pgrep -f "uvicorn app.main" >/dev/null && echo "backend: 仍在运行!" || echo "backend: STOPPED ✓"
pgrep -x minio >/dev/null && echo "minio: 仍在运行!" || echo "minio: STOPPED ✓"
ss -tlnp 2>/dev/null | grep -E ':(8000|9000|9001) ' || echo "端口 8000/9000/9001 已释放 ✓"
