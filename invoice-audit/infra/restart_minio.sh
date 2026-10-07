#!/usr/bin/env bash
# 重启 MinIO（应用 start_minio.sh 中的凭据；路径自动探测）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # infra/
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"          # 发票审计系统/
pkill -x minio 2>/dev/null || true
sleep 2
pgrep -x minio >/dev/null 2>&1 && echo "minio still running" || echo "minio stopped"
tr -d '\r' < "$PROJECT_ROOT/start_minio.sh" | bash
