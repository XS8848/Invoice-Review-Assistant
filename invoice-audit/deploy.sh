#!/usr/bin/env bash
# ============================================================
#  发票审计系统 一键部署（幂等）：MinIO + MySQL + 前端 + 后端
#  路径全部自动探测（脚本自身位置 + 组件扫描），可在 deploy.env 覆盖
# ============================================================
set -e

# 自身位置自动探测（直接执行有效；管道执行时由 PROJECT_DIR 指定）
if [ -f "${BASH_SOURCE[0]:-}" ]; then
  APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  APP_DIR="${PROJECT_DIR:+$PROJECT_DIR/invoice-audit}"
fi
[ -d "${APP_DIR:-}" ] || { echo "!! 无法定位项目目录：请用 bash <deploy.sh路径> 直接执行"; exit 1; }
PROJECT_ROOT="$(dirname "$APP_DIR")"

# 统一配置（可选覆盖）
[ -f "$PROJECT_ROOT/deploy.env" ] && source "$PROJECT_ROOT/deploy.env"

# Python 环境自动扫描：显式配置 > conda 常见路径 > command -v
if [ -z "${PY_BIN:-}" ] || [ ! -x "$PY_BIN" ]; then
  PY_BIN="$(ls /conda/miniconda3/envs/SF157/bin/python /opt/miniconda3/envs/SF157/bin/python /opt/conda/envs/SF157/bin/python 2>/dev/null | head -1)"
fi
[ -z "$PY_BIN" ] && PY_BIN="$(command -v python3 2>/dev/null || true)"
[ -n "$PY_BIN" ] && [ -x "$PY_BIN" ] || { echo "!! 未找到 Python 环境，请在 deploy.env 配置 PY_BIN"; exit 1; }
PIP_BIN="${PIP_BIN:-${PY_BIN%/python*}/pip}"
[ -x "$PIP_BIN" ] || PIP_BIN="$PY_BIN -m pip"
echo "python: $PY_BIN"

DATA_HOME="${DATA_HOME:-$HOME}"
LOG_FILE="$DATA_HOME/invoice-audit/backend.log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "== [1/5] MinIO =="
tr -d '\r' < "$PROJECT_ROOT/start_minio.sh" | bash

echo "== [2/5] MySQL =="
if grep -q "^DATABASE_URL=mysql" "$APP_DIR/.env"; then
  if mysqladmin ping --silent 2>/dev/null; then
    echo "mysql ok"
  else
    (service mysql start 2>/dev/null || true)
    sleep 6
    if mysqladmin ping --silent 2>/dev/null; then
      echo "mysql ok"
    else
      echo "!! MySQL 未运行：请先执行  wsl -u root bash < $APP_DIR/infra/install_mysql.sh"
      exit 1
    fi
  fi
else
  echo "DATABASE_URL 为 SQLite，跳过 MySQL"
fi

echo "== [3/5] Python 依赖 =="
$PIP_BIN install -q -r "$APP_DIR/backend/requirements.txt" pymysql -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "deps ok"

echo "== [4/5] 前端构建 =="
if [ -d "$APP_DIR/frontend/dist" ]; then
  echo "dist 已存在，跳过（重建：cd invoice-audit/frontend && npm run build）"
else
  cd "$APP_DIR/frontend"
  npm install --no-audit --no-fund
  npm run build
fi

echo "== [5/5] 后端 =="
if pgrep -f "uvicorn app.main" >/dev/null 2>&1; then
  echo "backend already running"
else
  cd "$APP_DIR/backend"
  export PATH="$(dirname "$PY_BIN"):$PATH"
  export LD_LIBRARY_PATH=$($PY_BIN -c "import os,sysconfig,glob; print(':'.join(sorted(glob.glob(os.path.join(sysconfig.get_paths()['purelib'],'nvidia','*','lib')))))"):$LD_LIBRARY_PATH
  # deploy.env 中的变量以环境变量形式注入（优先级高于 .env 文件）
  set -a; [ -f "$PROJECT_ROOT/deploy.env" ] && source "$PROJECT_ROOT/deploy.env"; set +a
  nohup setsid $PY_BIN -m uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --env-file ../.env > "$LOG_FILE" 2>&1 &
  sleep 8
fi
echo "health: $(curl -s http://127.0.0.1:${APP_PORT:-8000}/api/health)"
echo "DEPLOY DONE -> http://localhost:${APP_PORT:-8000}"
