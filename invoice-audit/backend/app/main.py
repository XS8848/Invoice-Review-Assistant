# -*- coding: utf-8 -*-
"""FastAPI 入口：建库、种子数据、启动状态机 worker、静态托管前端。"""
import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import auth, claims, config_api, dashboard, monitor, review
from .database import Base, SessionLocal, engine
from .models import User
from .runtime_config import load_runtime
from .security import hash_password
from .services import minio_service
from .workers.dispatcher import dispatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("main")


def _seed() -> None:
    with SessionLocal() as db:
        if db.query(User).filter(User.emp_no == "admin").first() is None:
            db.add(
                User(
                    emp_no="admin",
                    name="审查员",
                    password_hash=hash_password("admin"),
                    role="admin",
                    department="财务部",
                    job_level="M2",
                    position="审查员",
                    must_change_password=True,
                )
            )
            db.commit()
            logger.info("seeded admin account (emp_no=admin, 首次登录请修改密码)")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    _seed()
    load_runtime(SessionLocal)
    try:
        minio_service.ensure_bucket()
        logger.info("minio bucket ready: %s", config.MINIO_BUCKET)
    except Exception as e:
        logger.warning("minio not ready: %s", e)
    task = asyncio.create_task(dispatcher.loop())
    reaper = asyncio.create_task(dispatcher.lease_reaper())
    yield
    dispatcher.stop()
    task.cancel()
    reaper.cancel()


app = FastAPI(title="发票审计系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(review.router)
app.include_router(config_api.router)
app.include_router(monitor.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "invoice-audit", "version": "1.0.0"}


@app.get("/api/enums", tags=["enums"])
def public_enums():
    """部门/职级/岗位下拉选项（注册页需要，公开访问）。"""
    from .runtime_config import get_section

    return get_section("enums")


# 前端静态托管（构建产物存在时）
_dist = Path(config.FRONTEND_DIST)
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("assets/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        target = _dist / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(_dist / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return JSONResponse({"app": "发票审计系统", "hint": "前端未构建，请先构建 frontend（npm run build）"})
