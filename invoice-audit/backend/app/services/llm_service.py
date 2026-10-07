# -*- coding: utf-8 -*-
"""语言模型服务：DeepSeek（OpenAI 兼容）Function Calling 两轮审计。

第一轮强制调用 get_claim_info（服务端返回单据信息），
第二轮强制调用 submit_verdict（模型提交 0报销/1不报销/2无法判断 + 备注）。
"""
import json
import time

import httpx

from .. import config
from ..runtime_config import get_section

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_claim_info",
            "description": "获取当前待审计报销单的全部信息：员工信息（工号/姓名/部门/职级/岗位）、"
            "发票识别字段（类型/号码/日期/购销方/金额/税额/税率/商品明细）、规则引擎结论与员工备注。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_verdict",
            "description": "提交本次报销审计结论。",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "integer",
                        "enum": [0, 1, 2],
                        "description": "0=认为可报销；1=认为不可报销；2=无法判断（交给人工审查）",
                    },
                    "note": {
                        "type": "string",
                        "description": "简要理由，一句话即可，可为空字符串",
                    },
                },
                "required": ["result", "note"],
            },
        },
    },
]


def _chat(client: httpx.Client, llm_cfg: dict, messages: list, tool_choice) -> dict:
    url = llm_cfg.get("base_url", config.DEEPSEEK_BASE_URL).rstrip("/") + "/chat/completions"
    payload = {
        "model": llm_cfg.get("model", config.DEEPSEEK_MODEL),
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": tool_choice,
        "temperature": float(llm_cfg.get("temperature", 0.1)),
        "stream": False,
        # deepseek-flash 默认思考模式：不支持强制 tool_choice 且耗 token；
        # 审计场景关闭思考模式（更快、更省、支持温度与强制工具调用）。
        "thinking": {"type": "disabled"},
    }
    resp = client.post(url, json=payload, timeout=float(llm_cfg.get("timeout_seconds", 120)))
    resp.raise_for_status()
    return resp.json()


def _assistant_message(msg: dict) -> dict:
    """只保留可回传字段（DeepSeek 思考模式可能带 reasoning_content，回传会报错）。"""
    out = {"role": "assistant", "content": msg.get("content") or ""}
    if msg.get("tool_calls"):
        out["tool_calls"] = msg["tool_calls"]
    return out


def run_audit(claim_info: dict, rules: dict) -> dict:
    """返回 {"result": 0|1|2, "note": str}。任何异常→2（转人工）。"""
    llm_cfg = get_section("llm")
    system = str(llm_cfg.get("system_prompt", ""))
    system += "\n\n【报销规则】\n" + json.dumps(rules, ensure_ascii=False, indent=2)

    headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"}
    try:
        with httpx.Client(headers=headers) as client:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": "请审计这条报销单。第一步：调用 get_claim_info 获取报销单信息。"},
            ]
            force_info = {"type": "function", "function": {"name": "get_claim_info"}}
            r1 = _chat(client, llm_cfg, messages, force_info)
            msg1 = r1["choices"][0]["message"]
            tc = (msg1.get("tool_calls") or [{}])[0]
            messages.append(_assistant_message(msg1))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", "call_1"),
                    "content": json.dumps(claim_info, ensure_ascii=False),
                }
            )
            messages.append(
                {"role": "user", "content": "第二步：根据上述信息完成审计，调用 submit_verdict 提交结论。"}
            )
            force_verdict = {"type": "function", "function": {"name": "submit_verdict"}}
            r2 = _chat(client, llm_cfg, messages, force_verdict)
            msg2 = r2["choices"][0]["message"]
            tc2 = (msg2.get("tool_calls") or [{}])[0]
            args = json.loads(tc2.get("function", {}).get("arguments") or "{}")
            result = int(args.get("result", 2))
            if result not in (0, 1, 2):
                result = 2
            note = str(args.get("note", ""))[:500]
            return {"result": result, "note": note}
    except Exception as e:
        # 重试一次
        try:
            time.sleep(1)
            return _run_single_attempt(claim_info, rules, llm_cfg, system)
        except Exception as e2:
            return {"result": 2, "note": f"语言模型调用失败，转人工审查（{type(e2).__name__}）"}


def _run_single_attempt(claim_info: dict, rules: dict, llm_cfg: dict, system: str) -> dict:
    headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"}
    with httpx.Client(headers=headers) as client:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "请审计这条报销单。第一步：调用 get_claim_info 获取信息。"},
        ]
        r1 = _chat(client, llm_cfg, messages, {"type": "function", "function": {"name": "get_claim_info"}})
        msg1 = r1["choices"][0]["message"]
        tc = (msg1.get("tool_calls") or [{}])[0]
        messages.append(_assistant_message(msg1))
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id", "call_1"),
                "content": json.dumps(claim_info, ensure_ascii=False),
            }
        )
        messages.append(
            {"role": "user", "content": "第二步：调用 submit_verdict 提交结论。"}
        )
        r2 = _chat(client, llm_cfg, messages, {"type": "function", "function": {"name": "submit_verdict"}})
        msg2 = r2["choices"][0]["message"]
        tc2 = (msg2.get("tool_calls") or [{}])[0]
        args = json.loads(tc2.get("function", {}).get("arguments") or "{}")
        result = int(args.get("result", 2))
        if result not in (0, 1, 2):
            result = 2
        return {"result": result, "note": str(args.get("note", ""))[:500]}
