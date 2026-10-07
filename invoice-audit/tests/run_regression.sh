#!/usr/bin/env bash
# 最终全量回归：单元 + 全部 API 套件（含看板专项/降级/业务流转）
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python -m pytest unit api -q --tb=short -p no:cacheprovider
