#!/usr/bin/env bash
# GPU 环境包装 + 运行（缺一不可的 LD_LIBRARY_PATH 注入）
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
export LD_LIBRARY_PATH=$(/conda/miniconda3/envs/SF157/bin/python -c "import os,sysconfig,glob; print(':'.join(sorted(glob.glob(os.path.join(sysconfig.get_paths()['purelib'],'nvidia','*','lib')))))"):$LD_LIBRARY_PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python probe_ocr.py 2>&1 | tail -60
