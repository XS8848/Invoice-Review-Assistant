# -*- coding: utf-8 -*-
"""独立 OCR 测试：对 5 张样本发票跑 PP-StructureV3 + 清洗，打印字段。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from app.runtime_config import load_runtime  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services import ocr_service  # noqa: E402
import app.models  # noqa: E402,F401  确保模型注册进 Base.metadata

Base.metadata.create_all(engine)
load_runtime(SessionLocal)

SAMPLES = [
    "95adbd866ebd52e6a1e2c0298bfec8b3.jpg",
    "c138a50b121caf9657fba47e4e962c03.jpg",
    "b16.jpg",
    "9206c870-3516-483a-a273-22744be79f15473(1).pdf",
    "397dd4f7-8d62-4b93-8ac5-064ca5fb418b756.pdf",
]

BASE = pathlib.Path(__file__).resolve().parents[2].parent  # 工作区根
_extra = BASE / "发票汇总"
if _extra.is_dir():
    BASE = _extra

for name in SAMPLES:
    fp = BASE / name
    if not fp.exists():
        print(f"!! missing {name}")
        continue
    ftype = "pdf" if fp.suffix.lower() == ".pdf" else "img"
    res = ocr_service.process_file(fp, ftype)
    print(f"\n===== {name} (conf={res['conf']} stats={res['stats']}) =====")
    print(json.dumps(res["fields"], ensure_ascii=False, indent=1))
