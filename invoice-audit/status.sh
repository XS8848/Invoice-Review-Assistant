#!/usr/bin/env bash
# 服务状态巡检
echo "== 后端 =="
curl -s http://127.0.0.1:8000/api/health && echo || echo "后端未运行"
pgrep -f "uvicorn app.main" >/dev/null && echo "进程: 运行中" || echo "进程: 未运行"

echo "== MinIO =="
curl -s -o /dev/null -w 'health http=%{http_code}\n' --max-time 3 http://127.0.0.1:9000/minio/health/live || echo "MinIO 未运行"

echo "== MySQL =="
mysqladmin ping --silent 2>/dev/null && echo "mysql: ok" || echo "mysql: 未运行（需要时：wsl -u root bash invoice-audit/infra/install_mysql.sh）"

echo "== GPU =="
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null || echo "GPU 不可用"

echo "== 端口 =="
ss -tlnp 2>/dev/null | grep -E ':(8000|9000|3306) ' || true

echo "== 后端日志尾部 =="
tail -n 5 /home/backer/invoice-audit/backend.log 2>/dev/null || echo "无日志文件"
