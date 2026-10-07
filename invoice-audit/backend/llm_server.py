# -*- coding: utf-8 -*-
"""LLM 组件独立服务（分布式部署用，无状态可多副本）。

启动：bash backend/run_llm_server.sh（默认端口 8102，可 env LLM_SERVER_PORT 修改）
接口：
  GET   /health -> {"status":"ok","service":"llm"}
  POST  /audit  -> body {"claim_info":{...},"rules":{...}} → {"result":0|1|2,"note":"..."}
依赖环境变量：DEEPSEEK_*、DATABASE_URL（读 configs 表的 llm 调参）
"""
import logging

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("llm-server")

app = FastAPI(title="发票审计系统 · LLM 组件服务", version="1.0.0")


@app.on_event("startup")
def _startup() -> None:
    try:
        from app.database import SessionLocal
        from app.runtime_config import load_runtime

        load_runtime(SessionLocal)
        logger.info("runtime config loaded from database")
    except Exception as e:  # noqa: BLE001
        logger.warning("load runtime config failed, use defaults: %s", e)


class AuditRequest(BaseModel):
    claim_info: dict
    rules: dict = {}


@app.get("/health")
def health():
    return {"status": "ok", "service": "llm"}


@app.post("/audit")
def audit(req: AuditRequest):
    from app.services.llm_service import run_audit

    logger.info("audit request, claim info keys=%s", list(req.claim_info.keys()))
    verdict = run_audit(req.claim_info, req.rules)  # 内部含重试与转人工兜底
    return verdict
