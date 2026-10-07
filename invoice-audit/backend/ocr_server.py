# -*- coding: utf-8 -*-
"""OCR 组件独立服务（分布式部署用，可部署在 GPU 节点）。

启动：bash backend/run_ocr_server.sh（默认端口 8101，可 env OCR_SERVER_PORT 修改）
接口：
  GET  /health   -> {"status":"ok","model_ready":bool}
  POST /ocr      -> body {"file_key": "..."}；服务自行从 MinIO（env 配置）下载识别
                   返回 {"success":true,"fields":{...},"conf":0.95,"stats":{...}}
依赖环境变量：DATABASE_URL（读 configs 表的 vision 调参）、MINIO_*、TEMP_DIR
"""
import logging
import pathlib

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import config
from app.runtime_config import get_section

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("ocr-server")

app = FastAPI(title="发票审计系统 · OCR 组件服务", version="1.0.0")

_engine_ready = False


@app.on_event("startup")
def _startup() -> None:
    global _engine_ready
    # 从共享数据库加载调参（失败则用内置默认值）
    try:
        from app.database import SessionLocal
        from app.runtime_config import load_runtime

        load_runtime(SessionLocal)
        logger.info("runtime config loaded from database")
    except Exception as e:  # noqa: BLE001
        logger.warning("load runtime config failed, use defaults: %s", e)
    # 预热：初始化 PP-StructureV3 引擎（首次调用自动加载模型）
    try:
        from app.services import ocr_service

        cfg = get_section("vision")
        ocr_service._get_engine(cfg)
        _engine_ready = True
        logger.info("ocr engine ready (device=%s)", cfg.get("device"))
    except Exception as e:  # noqa: BLE001
        logger.warning("ocr engine not ready yet: %s", e)


class OcrRequest(BaseModel):
    file_key: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "ocr", "model_ready": _engine_ready}


@app.post("/ocr")
def ocr(req: OcrRequest):
    from app.services import minio_service, ocr_service

    try:
        local = config.TEMP_DIR / f"remote_{pathlib.Path(req.file_key).name}"
        minio_service.download_file(req.file_key, local)
        try:
            ftype = "pdf" if local.suffix.lower() == ".pdf" else "img"
            out = ocr_service.process_file(local, ftype)
            return {"success": True, "fields": out["fields"], "conf": out["conf"],
                    "stats": out.get("stats", {})}
        finally:
            local.unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        logger.exception("ocr failed")
        raise HTTPException(500, f"ocr failed: {e}")
