#!/usr/bin/env bash
# E2E 验收（对运行中的 127.0.0.1:8000 后端）
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python e2e_test.py
