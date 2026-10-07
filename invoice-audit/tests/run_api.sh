#!/usr/bin/env bash
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python -m pytest api/test_auth.py api/test_edge_security.py api/test_admin_api.py api/test_business_flow.py -q --tb=short -p no:cacheprovider -o log_cli=false
