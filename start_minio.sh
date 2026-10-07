#!/usr/bin/env bash
# ============================================================
#  MinIO 启动脚本（幂等；路径全部自动探测，可在 deploy.env 覆盖）
# ============================================================
set -e

# 自身位置自动探测（直接执行有效；管道执行时由 PROJECT_DIR 指定）
if [ -f "${BASH_SOURCE[0]:-}" ]; then
  PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  PROJECT_ROOT="${PROJECT_DIR:-}"
fi
[ -d "${PROJECT_ROOT:-}" ] || { echo "!! 无法定位项目目录：请用 bash <start_minio.sh路径> 直接执行"; exit 1; }
APP_DIR="$PROJECT_ROOT/invoice-audit"

# 统一配置（可选覆盖）
[ -f "$PROJECT_ROOT/deploy.env" ] && source "$PROJECT_ROOT/deploy.env"

# 凭据与后端 .env 同步
export MINIO_ROOT_USER="${MINIO_ROOT_USER:-invoiceaudit}"
export MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-4ugNhV5yxnCEebBNTNsn}"

# 组件路径自动扫描：显式配置 > command -v > conda 常见路径 > find
if [ -z "${MINIO_BIN:-}" ] || [ ! -x "$MINIO_BIN" ]; then
  MINIO_BIN="$(command -v minio 2>/dev/null || true)"
fi
if [ -z "$MINIO_BIN" ]; then
  MINIO_BIN="$(ls /conda/miniconda3/bin/minio /opt/miniconda3/bin/minio /opt/conda/bin/minio /usr/local/bin/minio 2>/dev/null | head -1)"
fi
if [ -z "$MINIO_BIN" ]; then
  MINIO_BIN="$(find /conda /opt "$HOME" -maxdepth 5 -type f -name minio 2>/dev/null | head -1)"
fi
[ -n "$MINIO_BIN" ] && [ -x "$MINIO_BIN" ] || { echo "!! 未找到 minio 二进制，请在 deploy.env 配置 MINIO_BIN"; exit 1; }
echo "minio bin: $MINIO_BIN"

DATA_HOME="${DATA_HOME:-$HOME}"
DATA_DIR="$DATA_HOME/minio/data"
LOG="$DATA_HOME/minio/minio.log"
mkdir -p "$DATA_DIR" "$(dirname "$LOG")"

if pgrep -x minio >/dev/null 2>&1; then
  echo "minio already running"
else
  nohup setsid "$MINIO_BIN" server "$DATA_DIR" --address :9000 --console-address :9001 >>"$LOG" 2>&1 &
  sleep 4
fi
curl -s -o /dev/null -w 'minio health http=%{http_code}\n' http://127.0.0.1:9000/minio/health/live
