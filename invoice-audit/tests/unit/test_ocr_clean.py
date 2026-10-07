# -*- coding: utf-8 -*-
"""单元测试：OCR 清洗函数（用真实发票识别文本快照）。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

from app.services.ocr_service import _agg_conf, _is_noise, clean_fields  # noqa: E402

VAT_RAW = """用发票
4400154130
12270279
No
12270279
4400154130
2016年06月12日
开票日期：
1>5590/-<097<*7*9474<<+781>
深圳市购机汇网络有限公司
名
称：
440300083885931
密码区
C
纳税人识别号：
深圳市龙华新区民治街道民治大道展活科技大厦A12070755-23806606
中国工商银行股份有限公司深圳园岭支行4000024709200172809
597.43589744
2987.18
5
小米红米3全网通版时尚金色
17%
税率
￥507.82
￥2987.18
计
（小写）
￥3495.00
叁仟肆佰玖拾伍圆整
价税合计（大写）
称：广州晶东贸易有限公司
91440101664041243T
纳税人识别号：
销售方
广州市黄埔区九龙镇九龙工业园凤凰三横路99号66216500
工行北京路支行3602000919200384952
开票人：
收款人：王梅"""

EINV_SAME_LINE = """电子发票（普通发票）
发票号码：26612000001568908351
开票日期：2026年08月05日
名称：西安国科动力科技有限公司
名称：西安启星酒店管理有限公司
统一社会信用代码/纳税人识别号：91610131MAK4HN8C1L
统一社会信用代码/纳税人识别号：91610131MA6U6DMDXT
*生产生活服务*餐饮费
497.17
6%
29.83
合计
￥497.17
￥29.83
价税合计（大写）
伍佰贰拾柒圆整
(小写）￥527.00
开票人：李媛"""

EINV_SPLIT_LAYER = """电子发票（普通发票）
发票号码：
开票日期：
统一社会信用代码/纳税人识别号：
名称：
项目名称
合计
价税合计（大写）
（小写）
开票人：
26317000003121778947
2026年09月10日
个人
上海三快智送科技有限公司
91310000MA1FW9A80N
*生产生活服务*配送服务
0.94
6%
0.06
￥0.94
￥0.06
￥1.00
壹圆整
何娟"""


class TestCleanFields:
    def test_vat_fields(self):
        f = clean_fields(VAT_RAW)
        assert f["invoice_type"] == "增值税专用发票", f["invoice_type"]
        assert f["invoice_code"] == "4400154130"
        assert f["invoice_no"] == "12270279"
        assert f["invoice_date"] == "2016-06-12"
        assert f["buyer_name"] == "深圳市购机汇网络有限公司"
        assert f["buyer_tax_id"] == "440300083885931"
        assert f["seller_name"] == "广州晶东贸易有限公司"
        assert f["seller_tax_id"] == "91440101664041243T"
        assert f["total_amount"] == "3495.00"
        assert f["amount_total"] == "2987.18"
        assert f["tax_total"] == "507.82"
        assert f["tax_rate"] == "17%"

    def test_einvoice_same_line(self):
        f = clean_fields(EINV_SAME_LINE)
        assert f["invoice_no"] == "26612000001568908351"
        assert f["invoice_date"] == "2026-08-05"
        assert f["buyer_name"] == "西安国科动力科技有限公司"
        assert f["buyer_tax_id"] == "91610131MAK4HN8C1L"
        assert f["seller_name"] == "西安启星酒店管理有限公司"
        assert f["seller_tax_id"] == "91610131MA6U6DMDXT"
        assert f["total_amount"] == "527.00"
        assert f["amount_total"] == "497.17"
        assert f["tax_total"] == "29.83"
        assert f["drawer"] == "李媛"

    def test_einvoice_split_layer(self):
        f = clean_fields(EINV_SPLIT_LAYER)
        assert f["invoice_no"] == "26317000003121778947"
        assert f["invoice_date"] == "2026-09-10"
        assert f["buyer_name"] == "个人"
        assert f["seller_name"] == "上海三快智送科技有限公司"
        assert f["seller_tax_id"] == "91310000MA1FW9A80N"
        assert f["total_amount"] == "1.00"
        assert f["drawer"] == "何娟"

    def test_bank_line_not_taxid(self):
        f = clean_fields(VAT_RAW)
        assert f["seller_tax_id"] != "3602000919200384952"  # 银行账号被剔除
        assert f["buyer_tax_id"] != "4000024709200172809"

    def test_item_extraction(self):
        f = clean_fields(EINV_SAME_LINE)
        names = [i["name"] for i in f["items"]]
        assert any("餐饮" in n for n in names), names


class TestAgg:
    def test_noise_filter(self):
        assert _is_noise("C")
        assert _is_noise("Knn")
        assert _is_noise("C2C")
        assert not _is_noise("91440101664041243T")
        assert not _is_noise("￥3495.00")

    def test_agg_conf(self):
        lines = [
            ("发票号码", 0.99, 10, 0), ("12345678", 0.98, 20, 0),
            ("C", 0.1, 30, 0), ("Knn", 0.2, 40, 0),
        ]
        st = _agg_conf(lines, [0.8, 0.2])
        assert st["used"] == 2
        assert st["conf"] > 0.95
