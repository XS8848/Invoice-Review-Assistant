# -*- coding: utf-8 -*-
"""系统监控：CPU / GPU / 内存 / 磁盘 / 显存 / 数据库 / MinIO。"""
import subprocess

import psutil
from fastapi import APIRouter, Depends

from .. import config
from ..database import engine
from ..models import User
from ..security import require_admin
from ..services import minio_service

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


# GPU 指标缓存 3 秒：nvidia-smi 子进程开销大，避免每次请求都 spawn
_gpu_cache: dict = {"ts": 0.0, "val": None}


def _gpu() -> dict:
    import time

    now = time.time()
    if _gpu_cache["val"] is not None and now - _gpu_cache["ts"] < 3:
        return _gpu_cache["val"]
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        line = out.stdout.strip().splitlines()[0]
        name, util, mem_used, mem_total, temp = [x.strip() for x in line.split(",")]
        val = {
            "available": True,
            "name": name,
            "util": float(util),
            "mem_used_mb": float(mem_used),
            "mem_total_mb": float(mem_total),
            "temp_c": float(temp),
        }
    except Exception:
        val = {"available": False}
    _gpu_cache["ts"] = now
    _gpu_cache["val"] = val
    return val


def _db_status() -> dict:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        return {"status": f"error: {type(e).__name__}"}


# 整响应缓存 2 秒：压测显示 cpu_percent(interval=0.5) 阻塞 0.5s/请求，缓存后显著降延迟
_mon_cache: dict = {"ts": 0.0, "val": None}


def _collect() -> dict:
    cpu = psutil.cpu_percent(interval=None)  # 非阻塞采样（自上次调用以来）
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu": {"percent": cpu, "count": psutil.cpu_count()},
        "memory": {
            "total_mb": round(mem.total / 1024 / 1024),
            "used_mb": round(mem.used / 1024 / 1024),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1024**3),
            "used_gb": round(disk.used / 1024**3),
            "percent": disk.percent,
        },
        "gpu": _gpu(),
        "database": {**_db_status(), "url": config.DATABASE_URL.split("//")[-1]},
        "minio": {"healthy": minio_service.is_healthy(), "endpoint": config.MINIO_ENDPOINT},
        "workers": {"lock_lease_seconds": 600, "poll_interval_seconds": 2},
    }


@router.get("")
def monitor(_: User = Depends(require_admin)):
    import time

    now = time.time()
    if _mon_cache["val"] is None or now - _mon_cache["ts"] >= 2:
        _mon_cache["val"] = _collect()
        _mon_cache["ts"] = now
    return _mon_cache["val"]
