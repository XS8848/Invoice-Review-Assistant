# -*- coding: utf-8 -*-
"""视觉模型服务：PP-StructureV3（GPU）+ 清洗为发票标准键值对 + 置信度聚合。

结构依据（已实测 PP-StructureV3 3.7.2）：
  result.json["res"]["overall_ocr_res"] -> {"rec_texts": [...], "rec_scores": [...], "rec_polys": [...]}
注意：
- 空文本行 rec_score 为 0，聚合置信度必须过滤空行与噪声行；
- PDF 优先合并其自带文本层（born-digital 票面最准确），OCR 作为补充。
"""
import json
import pathlib
import re
import threading
from statistics import mean

from ..runtime_config import get_section

_engine = None
_engine_lock = threading.Lock()
_predict_lock = threading.Lock()


def _get_engine(vision_cfg: dict):
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from paddleocr import PPStructureV3

                device = vision_cfg.get("device", "gpu:0")
                kwargs = dict(
                    lang="ch",
                    device=device,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_chart_recognition=False,
                    use_formula_recognition=False,
                    use_seal_recognition=False,
                )
                if device == "cpu":
                    kwargs["enable_mkldnn"] = bool(vision_cfg.get("enable_mkldnn", False))
                _engine = PPStructureV3(**kwargs)
    return _engine


def _maybe_downscale(img_path: pathlib.Path, max_side: int) -> pathlib.Path:
    """边长超过 max_side 的图缩放到 max_side（防 paddle OOM，见环境报告已知坑）。"""
    from PIL import Image

    with Image.open(img_path) as im:
        w, h = im.size
        if max(w, h) <= max_side:
            return img_path
        scale = max_side / max(w, h)
        out = img_path.with_name(f"{img_path.stem}_rs.png")
        im.convert("RGB").resize((int(w * scale), int(h * scale)), Image.LANCZOS).save(out)
        return out


def _render_pdf(pdf_path: pathlib.Path, dpi: int = 200) -> list[pathlib.Path]:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        out = pdf_path.with_name(f"{pdf_path.stem}_p{i + 1}.png")
        pix.save(str(out))
        pages.append(out)
    doc.close()
    return pages


def _pdf_text_layer(pdf_path: pathlib.Path) -> str:
    try:
        import pymupdf

        doc = pymupdf.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception:
        return ""


def _sorted_lines(overall: dict) -> list[tuple[str, float, float, float]]:
    """按版面位置排序的（文本, 分数, cy, cx）行，过滤空行。"""
    texts = overall.get("rec_texts") or []
    scores = overall.get("rec_scores") or []
    polys = overall.get("rec_polys") or []
    boxes = overall.get("rec_boxes") or []
    items = []
    for i, t in enumerate(texts):
        t = (t or "").strip()
        if not t:
            continue
        cy = cx = 0.0
        if boxes and i < len(boxes):
            b = boxes[i]
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        elif polys and i < len(polys):
            p = polys[i]
            xs = [pt[0] for pt in p]
            ys = [pt[1] for pt in p]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        score = float(scores[i]) if i < len(scores) else 0.0
        items.append((t, score, cy, cx))
    items.sort(key=lambda x: (round(x[2] / 10), x[3]))
    return items


def _is_noise(text: str) -> bool:
    t = text.strip()
    if len(t) < 2:
        return True
    if re.fullmatch(r"[\W_]+", t):  # 纯标点/符号
        return True
    has_cjk = re.search(r"[\u4e00-\u9fff]", t) is not None
    has_digit = re.search(r"\d", t) is not None
    if not has_cjk and not has_digit:
        return True  # 纯字母杂讯（Knn、C2C 之类）
    if has_digit and not has_cjk and len(t) < 8 and not re.search(r"[￥¥%.]", t):
        return True  # 短数字/字母混排杂讯
    return False


def _agg_conf(lines: list[tuple[str, float, float, float]], weights: list[float]) -> dict:
    """聚合置信度：过滤噪声行后 平均分/最低分 加权。返回 {conf, avg, min, used}。"""
    scores = [s for t, s, _, _ in lines if not _is_noise(t) and s >= 0.3]
    if not scores:
        return {"conf": 0.0, "avg": 0.0, "min": 0.0, "used": 0}
    w_avg, w_min = (weights + [0.8, 0.2])[:2]
    avg, mn = mean(scores), min(scores)
    return {
        "conf": round(w_avg * avg + w_min * mn, 4),
        "avg": round(avg, 4),
        "min": round(mn, 4),
        "used": len(scores),
    }


# ---------- 清洗：OCR 文本 -> 发票标准键值对 ----------

_LABEL_NOISE = {
    "规格型号", "单位", "数量", "单价", "金额", "税率", "税额", "合计", "计", "合",
    "价税合计（大写）", "（小写）", "备注", "密码区", "销售方", "购买方", "购买方信息",
    "销售方信息", "项目名称", "名称", "称：", "纳税人识别号：", "开票日期：", "发票号码：",
}

_COMPANY_RE = re.compile(
    r"(有限公司|公司|集团|大学|学院|医院|中心|事务所|工作室|学校|个人|餐饮|酒店|饭店|餐馆|店)"
)
_SKIP_NAME_LINE = ("银行", "税总函", "印刷", "密码", "发票", "税务局", "第二联", "下载次数")


def _label_val(lines: list[str], idx: int, pattern: str, scan: int = 4) -> str:
    """标签行 idx 的取值：同行为主，向下扫描 pattern 匹配的行为辅。"""
    l = lines[idx]
    rest = re.sub(r"^[^\:：]*[:：]", "", l).strip()
    m = re.search(pattern, rest)
    if m:
        return m.group(1).strip()
    for nxt in lines[idx + 1:idx + 1 + scan]:
        if not nxt or any(k in nxt for k in _SKIP_NAME_LINE):
            continue
        m = re.search(pattern, nxt)
        if m:
            return m.group(1).strip()
    return ""


def _company_lines(text: str) -> list[str]:
    """值式成对解析：按出现顺序收集“公司/个人/餐饮店”等名称行。"""
    out = []
    for line in text.splitlines():
        ls = line.strip()
        if not ls or len(ls) < 2:
            continue
        if any(k in ls for k in _SKIP_NAME_LINE):
            continue
        cand = re.sub(r"^[名称为]{0,2}[:：]\s*", "", ls)
        if cand and _COMPANY_RE.search(cand) and len(cand) <= 60:
            if cand not in out:
                out.append(cand)
    return out


def _taxid_runs(text: str) -> list[str]:
    """值式成对解析：按行找 15-20 位字母数字串（不压平文本，避免代码+号码粘连；
    排除 20 位纯数字发票号；排除银行账号行）。"""
    out: list[str] = []
    for line in text.splitlines():
        if any(k in line for k in ("银行", "开户行", "支行", "账号")):
            continue
        for r in re.findall(r"[0-9A-Za-z]{15,20}", line.strip()):
            if re.fullmatch(r"\d{20}", r):  # 电子发票号码
                continue
            if r not in out:
                out.append(r)
    return out


def _buyer_seller(text: str) -> dict:
    """统一购销方解析：标签解析与值式成对解析融合，取信息更全者。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    names_l, taxids_l = [], []
    for i, l in enumerate(lines):
        if "项目名称" in l or "货物" in l:
            continue
        if re.search(r"名称[:：]", l) and "纳税人识别号" not in l and "信用代码" not in l:
            v = _label_val(lines, i, r"^(.{2,60})$")
            if v and _COMPANY_RE.search(v):
                names_l.append(v)
        if "纳税人识别号" in l or "信用代码" in l:
            v = _label_val(lines, i, r"^([0-9A-Za-z]{15,20})$")
            if v:
                taxids_l.append(v)

    names_v = _company_lines(text)
    taxids_v = _taxid_runs(text)

    names = names_l if len(names_l) >= 2 else names_v
    taxids = taxids_l if len(taxids_l) >= 2 else taxids_v

    buyer_name = names[0] if names else ""
    seller_name = names[1] if len(names) > 1 else ""
    buyer_tax = ""
    seller_tax = ""
    if len(taxids) >= 2:
        buyer_tax, seller_tax = taxids[0], taxids[1]
    elif len(taxids) == 1:
        if buyer_name in ("个人", "个人消费"):
            seller_tax = taxids[0]
        else:
            buyer_tax = taxids[0]
    return {
        "buyer_name": buyer_name,
        "buyer_tax_id": buyer_tax,
        "seller_name": seller_name,
        "seller_tax_id": seller_tax,
    }


def _extract_items(text: str) -> list[dict]:
    out: list[dict] = []
    # 1) *服务* 特征段（电子发票商品名最可靠的特征，整段贪婪匹配）
    _CAT = "服务|餐饮|住宿|交通|办公|材料|维修|租赁|咨询|培训|配送"
    for m in re.finditer(r"[\*＊][^\n*＊\s]{1,30}[\*＊][^\n*＊\s]{0,30}", text):
        seg = m.group(0)
        if re.search(_CAT, seg):
            name = seg[:60]
            if name and all(it["name"] != name for it in out):
                out.append({"name": name, "line": seg})
    # 2) 表格区候选（增值税票）
    item_lines = []
    collecting = False
    for line in text.splitlines():
        ls = line.strip()
        if not ls:
            continue
        if any(k in ls for k in ("货物或应税劳务", "项目名称", "服务名称")):
            collecting = True
            continue
        if ls.startswith("合计") or ls in ("合", "计") or ls.startswith("价税合计"):
            collecting = False
            continue
        if collecting:
            item_lines.append(ls)
    for ln in item_lines:
        norm = ln.replace(" ", "")
        if norm in _LABEL_NOISE or len(ln) < 2:
            continue
        if re.fullmatch(r"[\d.,￥¥%\s]+", ln):
            continue
        if re.fullmatch(r"[零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整〇\s]+", ln):
            continue
        if any(k in ln for k in ("规格", "单位", "数量", "单价", "金额", "税率", "税额", "第二联", "税总函")):
            continue
        name = re.sub(r"[\d.,%￥¥\s]+", "", ln)[:60]
        if name and all(it["name"] != name for it in out):
            out.append({"name": name, "line": ln})
    return out


def clean_fields(text: str) -> dict:
    flat = re.sub(r"\s+", "", text)

    fields: dict = {
        "invoice_type": "",
        "invoice_code": "",
        "invoice_no": "",
        "invoice_date": "",
        "buyer_name": "",
        "buyer_tax_id": "",
        "seller_name": "",
        "seller_tax_id": "",
        "items": [],
        "amount_total": "",
        "tax_total": "",
        "total_amount": "",
        "total_amount_cn": "",
        "tax_rate": "",
        "remarks": "",
        "drawer": "",
        "raw_text": text[:4000],
    }

    # 发票类型
    if "增值税专用发票" in flat:
        fields["invoice_type"] = "增值税专用发票"
    elif "电子发票" in flat and "普通发票" in flat:
        fields["invoice_type"] = "电子发票(普通发票)"
    elif "增值税普通发票" in flat:
        fields["invoice_type"] = "增值税普通发票"
    elif "普通发票" in flat:
        fields["invoice_type"] = "普通发票"

    # 发票号码
    m = re.search(r"发票号码[:：]?\s*(\d{8,20})", text)
    if m:
        fields["invoice_no"] = m.group(1)
    else:
        m = re.search(r"No[.．\s:：]*(\d{8})", text)
        if m:
            fields["invoice_no"] = m.group(1)
        else:
            m = re.search(r"(?<!\d)(\d{20})", flat)
            if m:
                fields["invoice_no"] = m.group(1)

    # 发票代码（10 位，增值税票；按行匹配避免与号码粘连）
    m = re.search(r"发票代码[:：]?\s*(\d{10,12})", text)
    if m:
        fields["invoice_code"] = m.group(1)
    else:
        for line in text.splitlines():
            m = re.fullmatch(r"\s*(\d{10})\s*", line)
            if m:
                fields["invoice_code"] = m.group(1)
                break
    if not fields["invoice_type"] and fields["invoice_code"] and len(fields["invoice_no"]) == 8:
        fields["invoice_type"] = "增值税专用发票"

    # 开票日期
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        fields["invoice_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    else:
        m = re.search(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", text)
        if m:
            fields["invoice_date"] = m.group().replace("/", "-").replace(".", "-")

    # 购销方（统一解析）
    fields.update(_buyer_seller(text))

    # 价税合计（小写/大写，支持跨行）
    m = re.search(r"（小写）[￥¥]?\s*([\d,]+\.\d{2})", text)
    if m:
        fields["total_amount"] = m.group(1).replace(",", "")
    else:
        cands = re.findall(r"[￥¥]\s*([\d,]+\.\d{2})", text)
        if cands:
            fields["total_amount"] = max(cands, key=lambda x: float(x.replace(",", ""))).replace(",", "")
    m = re.search(r"（大写）[:：]?\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整〇]+)", text)
    if not m:
        m = re.search(r"（大写）[:：]?\s*\n\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整〇]+)", text)
    if m:
        fields["total_amount_cn"] = m.group(1)

    # 合计行：金额 + 税额（OCR 顺序可能颠倒 → 按大小修正：金额 ≥ 税额）
    m = re.search(r"合\s*计[^\n]*[￥¥]\s*([\d,]+\.\d{2})[^\n￥¥]*[￥¥]\s*([\d,]+\.\d{2})", text)
    if m:
        a, b = m.group(1).replace(",", ""), m.group(2).replace(",", "")
    else:
        m = re.search(r"[￥¥]\s*([\d,]+\.\d{2})\s+[￥¥]\s*([\d,]+\.\d{2})", text)
        if m:
            a, b = m.group(1).replace(",", ""), m.group(2).replace(",", "")
        else:
            a, b = "", ""
    if a and b:
        fa, fb = float(a), float(b)
        fields["amount_total"] = (a if fa >= fb else b)
        fields["tax_total"] = (b if fa >= fb else a)

    # 税率
    m = re.search(r"(\d{1,2})%", text)
    if m:
        fields["tax_rate"] = m.group(1) + "%"

    # 开票人（同行为主；纯数字则向后找中文名，排除购销方名称）
    lines = text.splitlines()
    drawer = ""
    for i, l in enumerate(lines):
        if "开票人" not in l:
            continue
        m = re.search(r"开票人[:：]\s*([^\s\n]{1,12})", l)
        if m and not re.fullmatch(r"\d+", m.group(1)):
            drawer = m.group(1)
            break
        for nxt in lines[i + 1:i + 31]:
            m2 = re.search(r"^[\u4e00-\u9fff]{2,4}$", nxt.strip())
            if m2 and m2.group(0) not in (fields["buyer_name"], fields["seller_name"]) \
                    and not re.fullmatch(r"[零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整〇]+", m2.group(0)):
                drawer = m2.group(0)
                break
        break
    fields["drawer"] = drawer

    # 商品明细
    fields["items"] = _extract_items(text)

    return fields


def _merge_fields(primary: dict, fallback: dict) -> dict:
    """primary 非空则优先，空则取 fallback。"""
    out = dict(primary)
    for k, v in fallback.items():
        if not out.get(k):
            out[k] = v
    # items：谁有数据用谁
    if not out.get("items"):
        out["items"] = fallback.get("items") or []
    return out


def process_file(file_path: pathlib.Path, file_type: str) -> dict:
    """入口：返回 {fields, conf, stats}。PDF 合并文本层 + OCR。"""
    vision_cfg = get_section("vision")
    max_side = int(vision_cfg.get("max_side", 2000))

    text_layer = ""
    images: list[pathlib.Path] = []
    if file_type == "pdf":
        text_layer = _pdf_text_layer(file_path)
        images = _render_pdf(file_path)
    else:
        images = [file_path]

    # OCR（引擎延迟初始化）
    engine = _get_engine(vision_cfg)
    all_lines: list[tuple[str, float, float, float]] = []
    with _predict_lock:
        for img in images:
            rs = _maybe_downscale(img, max_side)
            results = engine.predict(input=str(rs))
            jres = results[0].json["res"]
            all_lines.extend(_sorted_lines(jres.get("overall_ocr_res") or {}))

    stats = _agg_conf(all_lines, vision_cfg.get("agg_weights", [0.6, 0.4]))
    ocr_text = "\n".join(t for t, _, _, _ in all_lines)
    ocr_fields = clean_fields(ocr_text)

    if text_layer.strip():
        tl_fields = clean_fields(text_layer)
        fields = _merge_fields(tl_fields, ocr_fields)
        # 文本层是 born-digital 权威数据，关键字段来自文本层时置信度视为高
        if tl_fields.get("invoice_no"):
            stats["conf"] = max(stats["conf"], 0.99)
            stats["from_text_layer"] = True
    else:
        fields = ocr_fields

    return {"fields": fields, "conf": stats["conf"], "stats": stats}


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:]:
        fp = pathlib.Path(p)
        res = process_file(fp, "pdf" if fp.suffix.lower() == ".pdf" else "img")
        print(json.dumps(res, ensure_ascii=False, indent=2))
