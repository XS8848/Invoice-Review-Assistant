# -*- coding: utf-8 -*-
"""运行时配置中心：启动时从 configs 表加载，admin 修改后热更新。

四大区块：
- vision: 视觉模型参数（置信度阈值、聚合权重、设备、最大边长）
- llm:    语言模型参数（模型名、base_url、温度、系统提示词模板）
- rules:  报销规则（发票有效期/抬头校验/去重/算术/敏感品类/限额）
- enums:  部门/职级/岗位下拉选项
"""
import threading

DEFAULT_CONFIG: dict[str, dict] = {
    "vision": {
        "device": "gpu:0",          # gpu:0 | cpu
        "conf_threshold": 0.75,     # 聚合置信度低于此值 → 打回人工
        "agg_weights": [0.8, 0.2],  # [平均分权重, 最低分权重]
        "max_side": 1600,           # 图片最长边（超过缩放，防 OOM）
        "enable_mkldnn": False,     # CPU 模式必须 False（paddle 3.3 bug）
    },
    "llm": {
        "model": "deepseek-flash",
        "base_url": "https://api.deepseek.com/v1",
        "temperature": 0.1,
        "max_rounds": 3,
        "timeout_seconds": 120,
        "system_prompt": (
            "你是公司的发票审计助手。公司报销制度见下方【报销规则】。"
            "请根据传入的员工信息、发票识别结果和规则引擎结论，判断该发票是否可报销。"
            "判定原则：\n"
            "1. 确定性规则（规则引擎已给出硬性结论）必须遵守，不得推翻；\n"
            "2. 语义层面判断发票用途是否与员工岗位/部门相关、备注是否合理；\n"
            "3. 金额、品类异常或信息矛盾时倾向不报销并说明理由；\n"
            "4. 无法依据现有信息判断时，必须选择 2（无法判断）交给人工审查，禁止猜。\n"
            "流程要求：第一步调用 get_claim_info 获取报销单信息，第二步调用 submit_verdict 提交结论。"
            "提交结论时备注要言简意赅（一句话），无需多描述。"
        ),
    },
    "rules": {
        "company_name": "",             # 抬头校验基准名称（空=仅拦截“个人”抬头）
        "company_tax_id": "",           # 抬头校验基准税号（空=不校验税号）
        "max_age_days": 365,            # 发票有效期（天）
        "deduplicate_no": True,         # 同发票号重复提交检测
        "check_arithmetic": True,       # 金额=价税合计-税额 校验
        "require_buyer_match": True,    # 抬头必须匹配公司
        "allow_tax_rates": ["1%", "3%", "6%", "9%", "13%", "17%"],
        "sensitive_categories": ["餐饮", "烟", "酒", "礼品", "娱乐", "住宿"],
        "sensitive_requires_note": True,  # 敏感品类必须有备注
        "per_claim_limit": 5000,        # 单笔上限（超出转人工）
        "per_month_limit": 20000,       # 每人月累计上限（超出按 action 处理）
        "per_month_limit_action": "review",  # review=转人工 | reject=直接不报销
        "hard_fail_skips_llm": True,    # 硬规则不过时直接不报销，不再调 LLM
    },
    "enums": {
        "departments": ["技术部", "市场部", "销售部", "财务部", "人事部", "行政部"],
        "job_levels": ["P1", "P2", "P3", "P4", "P5", "P6", "M1", "M2"],
        "positions": ["工程师", "产品经理", "销售专员", "财务专员", "人事专员", "行政专员", "主管", "经理"],
    },
}

_lock = threading.Lock()
_runtime: dict[str, dict] = {}
_loaded = False


def load_runtime(session_factory) -> None:
    """启动时调用：DB 覆盖默认值。"""
    global _loaded
    from .models import AppConfig

    with _lock:
        for section in DEFAULT_CONFIG:
            _runtime[section] = dict(DEFAULT_CONFIG[section])
        with session_factory() as db:
            rows = db.query(AppConfig).all()
            for row in rows:
                if row.key in _runtime and isinstance(row.value, dict):
                    _runtime[row.key] = {**DEFAULT_CONFIG[row.key], **row.value}
        _loaded = True


def get_section(section: str) -> dict:
    with _lock:
        return dict(_runtime.get(section, DEFAULT_CONFIG.get(section, {})))


def set_section(session_factory, section: str, value: dict, updated_by: str = "") -> None:
    from .models import AppConfig

    if section not in DEFAULT_CONFIG:
        raise KeyError(f"未知配置区块: {section}")
    merged = {**DEFAULT_CONFIG[section], **value}
    with _lock:
        _runtime[section] = merged
    with session_factory() as db:
        row = db.query(AppConfig).filter(AppConfig.key == section).first()
        if row is None:
            db.add(AppConfig(key=section, value=merged, updated_by=updated_by))
        else:
            row.value = merged
            row.updated_by = updated_by
        db.commit()


def all_sections() -> dict:
    with _lock:
        return {k: dict(v) for k, v in _runtime.items()}
