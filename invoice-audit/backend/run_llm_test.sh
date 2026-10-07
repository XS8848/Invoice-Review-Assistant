#!/usr/bin/env bash
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
export DATABASE_URL=sqlite:////home/backer/invoice-audit/invoice_audit.db
set -a
source $SCRIPT_DIR/../.env
set +a
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python llm_test.py
