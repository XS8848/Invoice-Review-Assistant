#!/usr/bin/env bash
# 启动发票审计后端（GPU 环境包装 + uvicorn；路径自动探测）
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR"
APP_DIR="$(dirname "$BACKEND_DIR")"
PROJECT_ROOT="$(dirname "$APP_DIR")"

[ -f "$PROJECT_ROOT/deploy.env" ] && source "$PROJECT_ROOT/deploy.env"

if [ -z "${PY_BIN:-}" ] || [ ! -x "$PY_BIN" ]; then
  PY_BIN="$(ls /conda/miniconda3/envs/SF157/bin/python /opt/miniconda3/envs/SF157/bin/python 2>/dev/null | head -1)"
fi
[ -n "$PY_BIN" ] && [ -x "$PY_BIN" ] || { echo "!! 未找到 Python 环境"; exit 1; }

export PATH="$(dirname "$PY_BIN"):$PATH"
export LD_LIBRARY_PATH=$($PY_BIN -c "import os,sysconfig,glob; print(':'.join(sorted(glob.glob(os.path.join(sysconfig.get_paths()['purelib'],'nvidia','*','lib')))))"):$LD_LIBRARY_PATH
cd "$BACKEND_DIR"
set -a; [ -f "$PROJECT_ROOT/deploy.env" ] && source "$PROJECT_ROOT/deploy.env"; set +a
exec "$PY_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --env-file ../.env
