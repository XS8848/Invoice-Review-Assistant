# -*- coding: utf-8 -*-
"""单元测试：报销规则引擎全分支（SQLite 内存库，不依赖运行中的服务）。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401  注册模型
from app.models import Claim, User
from app.runtime_config import DEFAULT_CONFIG
from app.services import rules as R


@pytest.fixture()
def ctx():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(
        emp_no="T1234567", name="张三", password_hash="x", role="employee",
        department="技术部", job_level="P3", position="工程师",
    )
    db.add(user)
    db.commit()
    yield db, user
    db.close()


def base_fields(**overrides) -> dict:
    f = {
        "invoice_type": "电子发票(普通发票)",
        "invoice_code": "",
        "invoice_no": "26612000001568908351",
        "invoice_date": "2026-09-05",
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
    f.update(overrides)
    return f


def rules(**overrides) -> dict:
    r = dict(DEFAULT_CONFIG["rules"])
    r.update(overrides)
    return r


class TestRuleEngine:
    def test_clean_pass(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(), user, "客户招待用餐", rules(), db)
        assert r.hard_fail == [], r.to_dict()
        assert r.needs_review == [], r.to_dict()

    def test_missing_invoice_no(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(invoice_no=""), user, "", rules(), db)
        assert any("发票号码" in m for m in r.hard_fail)

    def test_missing_date(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(invoice_date=""), user, "", rules(), db)
        assert any("开票日期" in m for m in r.hard_fail)

    def test_expired(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(invoice_date="2016-06-12"), user, "", rules(), db)
        assert any("过期" in m for m in r.hard_fail), r.to_dict()

    def test_future_date(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(invoice_date="2030-01-01"), user, "", rules(), db)
        assert any("未来" in m for m in r.hard_fail)

    def test_bad_date_format(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(invoice_date="去年某天"), user, "", rules(), db)
        assert any("无法解析" in m for m in r.hard_fail)

    def test_personal_buyer(self, ctx):
        db, user = ctx
        r = R.evaluate(
            base_fields(buyer_name="个人", buyer_tax_id=""), user, "", rules(), db
        )
        assert any("抬头" in m or "个人" in m for m in r.hard_fail), r.to_dict()

    def test_company_mismatch(self, ctx):
        db, user = ctx
        r = R.evaluate(
            base_fields(buyer_name="别的公司"), user, "",
            rules(company_name="本公司"), db,
        )
        assert any("不符" in m for m in r.hard_fail), r.to_dict()

    def test_arithmetic_mismatch(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(tax_total="99.99"), user, "", rules(), db)
        assert any("算术" in m for m in r.hard_fail), r.to_dict()

    def test_duplicate_invoice_no(self, ctx):
        db, user = ctx
        prev = Claim(
            batch_id="b1", user_id=user.id, file_key="k", file_name="a.pdf",
            flow_status=0, reimb_result=0, queue_state=2,
            ocr_text={"invoice_no": "26612000001568908351"},
        )
        db.add(prev)
        db.commit()
        r = R.evaluate(base_fields(), user, "", rules(), db)
        assert any("重复报销" in m for m in r.hard_fail), r.to_dict()

    def test_sensitive_no_note(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(), user, "", rules(), db)
        assert any("敏感品类" in m for m in r.hard_fail), r.to_dict()

    def test_sensitive_with_note_only_warns(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(), user, "客户接待晚餐", rules(), db)
        assert not any("敏感品类" in m for m in r.hard_fail)
        assert any("敏感品类" in m for m in r.warnings), r.to_dict()

    def test_per_claim_limit(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(total_amount="6000.00"), user, "",
                       rules(per_claim_limit=5000), db)
        assert any("单笔" in m for m in r.needs_review), r.to_dict()

    def test_monthly_limit_reject(self, ctx):
        db, user = ctx
        prev = Claim(
            batch_id="b1", user_id=user.id, file_key="k", file_name="a.pdf",
            flow_status=0, reimb_result=0, queue_state=2,
            ocr_text={"total_amount": "100.00"},
        )
        db.add(prev)
        db.commit()
        r = R.evaluate(base_fields(total_amount="200.00"), user, "",
                       rules(per_month_limit=250, per_month_limit_action="reject"), db)
        assert any("月限额" in m for m in r.hard_fail), r.to_dict()

    def test_monthly_limit_review(self, ctx):
        db, user = ctx
        prev = Claim(
            batch_id="b1", user_id=user.id, file_key="k", file_name="a.pdf",
            flow_status=0, reimb_result=0, queue_state=2,
            ocr_text={"total_amount": "100.00"},
        )
        db.add(prev)
        db.commit()
        r = R.evaluate(base_fields(total_amount="200.00"), user, "",
                       rules(per_month_limit=250, per_month_limit_action="review"), db)
        assert any("月限额" in m for m in r.needs_review), r.to_dict()

    def test_unusual_tax_rate_warns(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(tax_rate="25%"), user, "", rules(), db)
        assert any("非常规税率" in m for m in r.warnings), r.to_dict()

    def test_allow_tax_rate_ok(self, ctx):
        db, user = ctx
        r = R.evaluate(base_fields(tax_rate="1%"), user, "",
                       rules(allow_tax_rates=["1%", "6%"]), db)
        assert not any("非常规税率" in m for m in r.warnings)
