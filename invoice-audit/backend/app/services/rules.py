# -*- coding: utf-8 -*-
"""报销规则引擎（确定性规则用代码计算，可解释、可审计）。

hard_fail  → 硬性不报销；needs_review → 转人工；warnings → 提示。
LLM 只做语义判断，规则结论随字段一并交给 LLM 参考。
"""
import re
from datetime import datetime

from ..models import Claim, User


class RuleResult:
    def __init__(self) -> None:
        self.hard_fail: list[str] = []
        self.warnings: list[str] = []
        self.needs_review: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.hard_fail and not self.needs_review

    def to_dict(self) -> dict:
        return {
            "hard_fail": self.hard_fail,
            "warnings": self.warnings,
            "needs_review": self.needs_review,
        }


def _num(text) -> float | None:
    if text is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(text).replace(",", ""))
    return float(m.group()) if m else None


def _norm_no(text) -> str:
    return re.sub(r"\D", "", text or "")


def _parse_date(text: str) -> datetime | None:
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", text)
    if m:
        try:
            return datetime.strptime(m.group(), "%Y-%m-%d")
        except ValueError:
            return None
    return None


def _items_text(fields: dict) -> str:
    parts = []
    for it in fields.get("items") or []:
        if isinstance(it, dict):
            parts.append(str(it.get("name", "")))
        else:
            parts.append(str(it))
    return " ".join(parts)


def evaluate(
    fields: dict,
    user: User,
    user_note: str,
    rules: dict,
    db,
) -> RuleResult:
    r = RuleResult()
    invoice_no = _norm_no(fields.get("invoice_no"))
    invoice_date = (fields.get("invoice_date") or "").strip()
    total = _num(fields.get("total_amount"))
    tax = _num(fields.get("tax_total"))
    amount = _num(fields.get("amount_total"))
    buyer_tax_id = _norm_no(fields.get("buyer_tax_id"))
    buyer_name = (fields.get("buyer_name") or "").strip()
    items_text = _items_text(fields)

    # 1. 票面要素完整性
    if not invoice_no:
        r.hard_fail.append("发票号码缺失或无法识别")
    if not invoice_date:
        r.hard_fail.append("开票日期缺失或无法识别")
    if total is None:
        r.hard_fail.append("价税合计缺失或无法识别")

    # 2. 重复报销检测（同发票号已有报销记录）
    if invoice_no and rules.get("deduplicate_no", True):
        prev = db.query(Claim).all()
        for row in prev:
            if not row.ocr_text or row.reimb_result != 0:
                continue
            prev_no = _norm_no((row.ocr_text or {}).get("invoice_no"))
            if prev_no and prev_no == invoice_no:
                r.hard_fail.append(f"发票号 {invoice_no} 已报销过（重复报销）")
                break

    # 3. 发票有效期
    max_age = int(rules.get("max_age_days", 365))
    dt = _parse_date(invoice_date) if invoice_date else None
    if invoice_date and dt is None:
        r.hard_fail.append(f"开票日期格式无法解析：{invoice_date}")
    elif dt is not None:
        age_days = (datetime.now() - dt).days
        if age_days < 0:
            r.hard_fail.append(f"发票日期为未来时间（{invoice_date}）")
        elif age_days > max_age:
            r.hard_fail.append(f"发票已过期 {age_days} 天（有效期 {max_age} 天）")

    # 4. 抬头校验
    if rules.get("require_buyer_match", True):
        company_name = (rules.get("company_name") or "").strip()
        company_tax_id = _norm_no(rules.get("company_tax_id") or "")
        if buyer_name in ("个人", "个人消费") or (not buyer_name and not buyer_tax_id):
            r.hard_fail.append("购买方抬头为个人或缺失，不符合报销要求")
        elif (company_tax_id or company_name) and not (
            (company_tax_id and company_tax_id == buyer_tax_id)
            or (company_name and company_name in buyer_name)
        ):
            r.hard_fail.append(f"购买方抬头与公司不符（买方：{buyer_name or buyer_tax_id}）")

    # 5. 金额算术校验
    if rules.get("check_arithmetic", True) and total is not None:
        if amount is not None and tax is not None and abs((amount + tax) - total) > 0.02:
            r.hard_fail.append(f"金额算术不符：金额 {amount} + 税额 {tax} ≠ 价税合计 {total}")
        cn = (fields.get("total_amount_cn") or "").strip()
        if cn and re.search(r"\d", cn) is None:
            cn_norm = _norm_no(cn)
            if cn_norm:
                r.warnings.append("大写金额可读性存疑，请核对")

    # 6. 税率合法性（票面出现值）
    rates_found = re.findall(r"(\d{1,2})%", items_text + " " + str(fields.get("tax_rate") or ""))
    allowed = rules.get("allow_tax_rates", [])
    for rate in rates_found:
        if f"{rate}%" not in allowed:
            r.warnings.append(f"出现非常规税率 {rate}%，请按开票日期/行业核实")

    # 7. 敏感品类
    sensitive = [s for s in rules.get("sensitive_categories", []) if s in items_text]
    if sensitive:
        if rules.get("sensitive_requires_note", True) and not (user_note or "").strip():
            r.hard_fail.append(f"敏感品类（{'、'.join(sensitive)}）未填写报销事由备注")
        else:
            r.warnings.append(f"敏感品类：{'、'.join(sensitive)}，请核查用途与标准")

    # 8. 限额：单笔 / 每人月累计
    per_claim = _num(str(rules.get("per_claim_limit", 5000)))
    if total is not None and per_claim is not None and total > per_claim:
        r.needs_review.append(f"单笔金额 {total} 超出上限 {per_claim}，转人工审查")

    per_month = _num(str(rules.get("per_month_limit", 20000)))
    if total is not None and per_month is not None:
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_claims = (
            db.query(Claim)
            .filter(
                Claim.user_id == user.id,
                Claim.reimb_result == 0,
                Claim.submitted_at >= month_start,
            )
            .all()
        )
        spent = sum(
            _num((row.ocr_text or {}).get("total_amount")) or 0.0 for row in month_claims
        )
        if spent + total > per_month:
            msg = f"当月已报销 {spent:.2f} + 本单 {total} 超出月限额 {per_month}"
            action = rules.get("per_month_limit_action", "review")
            if action == "reject":
                r.hard_fail.append(msg + "，不予报销")
            else:
                r.needs_review.append(msg + "，转人工审查")
    return r
