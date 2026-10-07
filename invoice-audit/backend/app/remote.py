# -*- coding: utf-8 -*-
"""分布式组件通信：OCR / LLM 服务的 FastAPI HTTP 客户端。

调度器（dispatcher）按 .env 配置决定：
- OCR_SERVICE_URL / LLM_SERVICE_URL 为空 → 内嵌模式（本进程线程池执行，单机部署默认）
- 填写 → 远程模式（HTTP 调用独立部署的 ocr_server / llm_server）
"""
import httpx

from . import config


def ocr_remote_available() -> bool:
    return bool(config.OCR_SERVICE_URL)


def llm_remote_available() -> bool:
    return bool(config.LLM_SERVICE_URL)


def call_remote_ocr(file_key: str, timeout: float = 600.0) -> dict:
    """远程识别：POST /ocr {file_key} → {fields, conf, stats}。失败抛异常（由调度器兜底）。"""
    r = httpx.post(
        f"{config.OCR_SERVICE_URL}/ocr",
        json={"file_key": file_key},
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success", True) and "error" in body:
        raise RuntimeError(f"remote ocr error: {body['error']}")
    return {"fields": body.get("fields", {}), "conf": body.get("conf", 0.0),
            "stats": body.get("stats", {})}


def call_remote_llm(claim_info: dict, rules: dict, timeout: float = 300.0) -> dict:
    """远程审计：POST /audit {claim_info, rules} → {result, note}。失败抛异常（由调度器兜底转人工）。"""
    r = httpx.post(
        f"{config.LLM_SERVICE_URL}/audit",
        json={"claim_info": claim_info, "rules": rules},
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    result = int(body.get("result", 2))
    if result not in (0, 1, 2):
        result = 2
    return {"result": result, "note": str(body.get("note", ""))[:500]}
