#!/usr/bin/env bash
# 只跑关键字段验证：95adbd 的购销方解析
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
export LD_LIBRARY_PATH=$(/conda/miniconda3/envs/SF157/bin/python -c "import os,sysconfig,glob; print(':'.join(sorted(glob.glob(os.path.join(sysconfig.get_paths()['purelib'],'nvidia','*','lib')))))"):$LD_LIBRARY_PATH
export DATABASE_URL=sqlite:////home/backer/invoice-audit/invoice_audit.db
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python - <<'PYEOF' 2>/dev/null
import json, pathlib, sys
sys.path.insert(0, ".")
import app.models  # noqa
from app.database import Base, SessionLocal, engine
from app.runtime_config import load_runtime
from app.services import ocr_service
Base.metadata.create_all(engine)
load_runtime(SessionLocal)
for name in ["95adbd866ebd52e6a1e2c0298bfec8b3.jpg", "b16.jpg"]:
    _ws = pathlib.Path(".").resolve().parents[2].parent  # 工作区根
    res = ocr_service.process_file(_ws / name, "img")
    f = res["fields"]
    print(name, "conf=", res["conf"])
    print("  type:", f["invoice_type"], "code:", f["invoice_code"], "no:", f["invoice_no"])
    print("  buyer:", f["buyer_name"], "|", f["buyer_tax_id"])
    print("  seller:", f["seller_name"], "|", f["seller_tax_id"])
PYEOF
