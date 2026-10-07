#!/usr/bin/env bash
# 编译检查全部后端代码 + 单元测试（路径自动探测）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # tests/
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH

cd "$BACKEND_DIR"
/conda/miniconda3/envs/SF157/bin/python -m py_compile app/*.py app/api/*.py app/services/*.py app/workers/*.py ocr_server.py llm_server.py && echo COMPILE_OK

cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python -m pytest unit -q --tb=short -p no:cacheprovider 2>&1 | tail -2
