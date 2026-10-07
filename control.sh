#!/usr/bin/env bash
# ============================================================
#  发票审计系统 · 控制脚本（WSL 内执行；路径自动探测）
#  用法: bash control.sh <命令> [参数]
#    start            一键部署全部服务（MinIO + MySQL + 后端，幂等）
#    stop             停止全部服务（后端 + MinIO + MySQL）
#    restart          重启全部服务
#    status           状态巡检
#    port <端口>      修改后端运行端口（.env APP_PORT）并重启
#    lanip            显示当前局域网 IP
#    maphelp          显示局域网端口映射操作方法
#    logs             尾随后端日志
# ============================================================
set -e

# 自身位置自动探测（直接执行有效；管道执行时由 PROJECT_DIR 指定）
if [ -f "${BASH_SOURCE[0]:-}" ]; then
  PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  PROJECT_ROOT="${PROJECT_DIR:-}"
fi
[ -d "${PROJECT_ROOT:-}" ] || { echo "!! 无法定位项目目录：请用 bash <control.sh路径> 直接执行"; exit 1; }
APP_DIR="$PROJECT_ROOT/invoice-audit"
ENV_FILE="$APP_DIR/.env"

[ -f "$PROJECT_ROOT/deploy.env" ] && source "$PROJECT_ROOT/deploy.env"
DATA_HOME="${DATA_HOME:-$HOME}"
LOG_FILE="$DATA_HOME/invoice-audit/backend.log"

CMD="${1:-status}"
ARG="${2:-}"

run() { tr -d '\r' < "$1" | PROJECT_DIR="$PROJECT_ROOT" bash; }

stop_backend()  { pkill -f "uvicorn app.main" 2>/dev/null && echo "backend: 已停止" || echo "backend: 未运行"; }
start_backend() { run "$APP_DIR/deploy.sh"; }
stop_minio()    { pkill -x minio 2>/dev/null && echo "minio: 已停止" || echo "minio: 未运行"; }
stop_mysql()    { (service mysql stop 2>/dev/null || mysqladmin shutdown 2>/dev/null) && echo "mysql: 已停止" || echo "mysql: 未运行"; }

case "$CMD" in
  start)
    start_backend
    ;;
  stop)
    stop_backend
    sleep 1
    stop_minio
    stop_mysql
    echo "== 全部服务已停止 =="
    ;;
  restart)
    stop_backend; sleep 2
    stop_minio
    start_backend
    ;;
  status)
    run "$APP_DIR/status.sh"
    ;;
  port)
    if [[ ! "$ARG" =~ ^[0-9]{2,5}$ ]]; then
      echo "用法: bash control.sh port <端口号>  例如: bash control.sh port 9000"
      exit 1
    fi
    echo "修改后端端口 -> $ARG（写入 .env APP_PORT）"
    sed -i "s/^APP_PORT=.*/APP_PORT=$ARG/" "$ENV_FILE"
    grep '^APP_PORT=' "$ENV_FILE"
    echo "重启后端使端口生效..."
    stop_backend; sleep 2
    start_backend
    echo "完成。前端随后端同端口提供：http://localhost:$ARG"
    ;;
  lanip)
    echo -n "本机局域网 IPv4: "
    powershell.exe -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { \$_.IPAddress -like '192.168.*' -and \$_.InterfaceAlias -notmatch 'WSL|vEthernet' } | Select-Object -First 1).IPAddress" 2>/dev/null || ip -4 addr show | grep -oP '(?<=inet\s)192\.168\.[0-9.]+' | head -1
    ;;
  maphelp)
    echo "局域网访问（其他设备 → 本机）需要端口映射，在 Windows PowerShell（管理员）执行："
    echo "  powershell -ExecutionPolicy Bypass -File \"$APP_DIR/infra/lan_expose.ps1\""
    echo "（脚本自动探测当前 IP，映射 8000/9000/9001 并放行防火墙；下线清理执行 infra/offline_cleanup.ps1）"
    ;;
  logs)
    tail -f "$LOG_FILE"
    ;;
  *)
    echo "未知命令: $CMD"
    echo "可用命令: start | stop | restart | status | port <端口> | lanip | maphelp | logs"
    exit 1
    ;;
esac
