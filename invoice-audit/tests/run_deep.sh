#!/usr/bin/env bash
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python -m pytest api/test_dashboard_deep.py api/test_degradation.py -q --tb=short -p no:cacheprovider
