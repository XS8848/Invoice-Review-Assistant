# -*- coding: utf-8 -*-
"""应用配置：从环境变量读取（uvicorn --env-file 注入 .env）。
所有路径基于本文件位置自动推导（BASE_DIR），无硬编码绝对路径。"""
import os
import tempfile
from pathlib import Path


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


BASE_DIR = Path(__file__).resolve().parent.parent.parent  # invoice-audit/

DEEPSEEK_API_KEY = _get("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = _get("DEEPSEEK_MODEL", "deepseek-flash")

MINIO_ENDPOINT = _get("MINIO_ENDPOINT", "127.0.0.1:9000")
# 对外访问地址：生成预签名 URL 时使用（局域网/公网映射端口）；默认等于内部地址
MINIO_PUBLIC_ENDPOINT = _get("MINIO_PUBLIC_ENDPOINT", MINIO_ENDPOINT)
MINIO_ACCESS_KEY = _get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = _get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = _get("MINIO_BUCKET", "reimb-invoices")
MINIO_SECURE = _get("MINIO_SECURE", "false").lower() == "true"

DATABASE_URL = _get("DATABASE_URL", "sqlite:///./invoice_audit.db")

APP_HOST = _get("APP_HOST", "0.0.0.0")
APP_PORT = int(_get("APP_PORT", "8000"))
JWT_SECRET = _get("JWT_SECRET", "dev-only-insecure-secret-please-override-in-production-32+")
if len(JWT_SECRET) < 32:
    import warnings

    warnings.warn(f"JWT_SECRET 长度 {len(JWT_SECRET)} < 32 字节，请在生产 .env 中配置强密钥",
                  RuntimeWarning)
JWT_EXPIRE_MINUTES = int(_get("JWT_EXPIRE_MINUTES", "720"))
JWT_ALGORITHM = "HS256"

UPLOAD_MAX_FILES = int(_get("UPLOAD_MAX_FILES", "20"))
UPLOAD_MAX_SIZE_MB = int(_get("UPLOAD_MAX_SIZE_MB", "20"))

# 状态机 worker 并发（OCR 受 GPU 显存限制建议 1-2；LLM 受 API 并发限制）
OCR_WORKERS = max(1, int(_get("OCR_WORKERS", "1")))
LLM_WORKERS = max(1, int(_get("LLM_WORKERS", "2")))

# 公司主体信息（抬头校验基准，可在调参页修改）
COMPANY_NAME = _get("COMPANY_NAME", "")
COMPANY_TAX_ID = _get("COMPANY_TAX_ID", "")

FRONTEND_DIST = str(BASE_DIR / "frontend" / "dist")

# 临时目录：优先环境变量 TEMP_DIR，否则使用系统临时目录（自动探测，不写死）
TEMP_DIR = Path(_get("TEMP_DIR") or (Path(tempfile.gettempdir()) / "invoice-audit"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ===== 分布式部署：组件通信地址（FastAPI 服务化）=====
# 留空 = 内嵌模式（OCR/LLM 在本进程线程池内执行，单机部署默认）
# 填写 = 远程模式（调度器经 HTTP 调用独立部署的组件服务，如 http://192.168.1.10:8101）
OCR_SERVICE_URL = _get("OCR_SERVICE_URL").rstrip("/") if _get("OCR_SERVICE_URL") else ""
LLM_SERVICE_URL = _get("LLM_SERVICE_URL").rstrip("/") if _get("LLM_SERVICE_URL") else ""

# 独立组件服务端口（分布式模式下各节点启动 ocr_server/llm_server 时使用）
OCR_SERVER_PORT = int(_get("OCR_SERVER_PORT", "8101"))
LLM_SERVER_PORT = int(_get("LLM_SERVER_PORT", "8102"))

# 文件类型白名单
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
