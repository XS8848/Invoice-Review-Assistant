# -*- coding: utf-8 -*-
"""探测 PP-StructureV3 真实返回结构（一次性工具，用于确定清洗字段取值路径）。"""
import json
import pathlib

from paddleocr import PPStructureV3

p = PPStructureV3(
    lang="ch",
    device="gpu:0",
    enable_mkldnn=False,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_chart_recognition=False,
    use_formula_recognition=False,
    use_seal_recognition=False,
)

# 样本自动探测：env PROBE_IMG > <工作区>/b16.jpg
import os

f = os.environ.get("PROBE_IMG") or str(
    pathlib.Path(__file__).resolve().parents[2].parent / "b16.jpg"
)
print("probe image:", f)
r = p.predict(input=f)
res_obj = r[0]
print("result type:", type(res_obj))
print("attrs:", [a for a in dir(res_obj) if not a.startswith("_")])
print("has .json:", hasattr(res_obj, "json"))
print("has .res:", hasattr(res_obj, "res"))

d = res_obj.res if isinstance(getattr(res_obj, "res", None), dict) else {}
print("res is dict:", isinstance(d, dict))
if isinstance(d, dict):
    print("res keys:", list(d.keys()))
    overall = d.get("overall_ocr_res")
    print("overall_ocr_res type:", type(overall))
    if isinstance(overall, dict):
        print("overall keys:", list(overall.keys()))
        for k, v in overall.items():
            try:
                ln = len(v)
            except TypeError:
                ln = ""
            print(f"  {k}: type={type(v).__name__} len={ln} sample={str(v)[:200]}")
    for k in ("parsing_res_list", "table_res_list", "layout_det_res"):
        v = d.get(k)
        if v is not None:
            print(f"{k}: type={type(v).__name__} len={len(v) if hasattr(v, '__len__') else ''} sample={str(v)[:400]}")
else:
    print("res sample:", str(d)[:500])

# json 视图
try:
    j = res_obj.json
    print("json keys:", list(j.keys()) if isinstance(j, dict) else type(j))
    if isinstance(j, dict):
        print("json.res keys:", list(j["res"].keys()) if isinstance(j["res"], dict) else type(j["res"]))
        overall = j["res"].get("overall_ocr_res")
        if isinstance(overall, dict):
            print("json overall keys:", list(overall.keys()))
            print("rec_texts:", overall.get("rec_texts"))
            print("rec_scores:", overall.get("rec_scores"))
except Exception as e:
    print("json access error:", e)
