#!/usr/bin/env bash
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
export LD_LIBRARY_PATH=$(/conda/miniconda3/envs/SF157/bin/python -c "import os,sysconfig,glob; print(':'.join(sorted(glob.glob(os.path.join(sysconfig.get_paths()['purelib'],'nvidia','*','lib')))))"):$LD_LIBRARY_PATH
export DATABASE_URL=sqlite:////home/backer/invoice-audit/invoice_audit.db
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python -m py_compile app/*.py app/api/*.py app/services/*.py app/workers/*.py test_ocr_cli.py && echo COMPILE_OK
/conda/miniconda3/envs/SF157/bin/python test_ocr_cli.py 2>&1 | grep -v "^\[32m" | grep -v UserWarning | grep -v "warnings.warn"
