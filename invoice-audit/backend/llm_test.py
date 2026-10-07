# -*- coding: utf-8 -*-
"""LLM 服务联调测试：真实调用 DeepSeek API 走两轮工具调用。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import app.models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.runtime_config import load_runtime, get_section
from app.services.llm_service import run_audit
from app.services.rules import RuleResult

Base.metadata.create_all(engine)
load_runtime(SessionLocal)

FIELDS = {
    "invoice_type": "电子发票(普通发票)",
    "invoice_code": "",
    "invoice_no": "26612000001568908351",
    "invoice_date": "2026-08-05",
    "buyer_name": "西安国科动力科技有限公司",
    "buyer_tax_id": "91610131MAK4HN8C1L",
    "seller_name": "西安启星酒店管理有限公司",
    "seller_tax_id": "91610131MA6U6DMDXT",
    "items": [{"name": "*生产生活服务*餐饮费", "line": "*生产生活服务*餐饮费"}],
    "amount_total": "497.17",
    "tax_total": "29.83",
    "total_amount": "527.00",
    "total_amount_cn": "伍佰贰拾柒圆整",
    "tax_rate": "6%",
    "remarks": "",
    "drawer": "李媛",
}

info = {
    "员工信息": {"工号": "A0000001", "姓名": "张三", "部门": "销售部", "职级": "P3", "岗位": "销售专员"},
    "发票识别字段": FIELDS,
    "规则引擎结论": {"hard_fail": [], "warnings": ["敏感品类：餐饮，请核查用途与标准"], "needs_review": []},
    "员工备注": "客户接待晚餐",
    "报销单编号": 1,
}

rules = get_section("rules")
print("=== 用例1：正常餐饮票+有备注（期望 0 或 2）===")
print(json.dumps(run_audit(info, rules), ensure_ascii=False, indent=2))

print("\n=== 用例2：2016年过期发票（期望 1 不报销）===")
info2 = json.loads(json.dumps(info))
info2["发票识别字段"]["invoice_date"] = "2016-06-12"
info2["发票识别字段"]["invoice_no"] = "12270279"
info2["发票识别字段"]["invoice_type"] = "增值税专用发票"
info2["发票识别字段"]["items"] = [{"name": "小米红米3手机", "line": "小米红米3手机"}]
info2["员工备注"] = ""
print(json.dumps(run_audit(info2, rules), ensure_ascii=False, indent=2))

print("\n=== 用例3：抬头为个人（期望 1 不报销）===")
info3 = json.loads(json.dumps(info))
info3["发票识别字段"]["buyer_name"] = "个人"
info3["发票识别字段"]["buyer_tax_id"] = ""
print(json.dumps(run_audit(info3, rules), ensure_ascii=False, indent=2))
