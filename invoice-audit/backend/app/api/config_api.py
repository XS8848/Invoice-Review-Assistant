# -*- coding: utf-8 -*-
"""调参接口 + 枚举选项（仅 admin）。"""
from fastapi import APIRouter, Depends, HTTPException

from ..database import SessionLocal
from ..models import AuditLog, User
from ..runtime_config import all_sections, get_section, set_section
from ..schemas import ConfigPutIn
from ..security import require_admin

router = APIRouter(prefix="/api/config", tags=["config"])


def _safe_view() -> dict:
    out = all_sections()
    llm = out.get("llm", {})
    if "api_key" in llm:
        llm["api_key"] = "***"  # 永不回显密钥
    return out


@router.get("")
def get_config(_: User = Depends(require_admin)):
    return _safe_view()


@router.put("")
def put_config(body: ConfigPutIn, admin: User = Depends(require_admin)):
    try:
        set_section(SessionLocal, body.section, body.value, updated_by=admin.emp_no)
    except KeyError:
        raise HTTPException(400, f"未知配置区块: {body.section}")
    with SessionLocal() as db:
        db.add(
            AuditLog(
                operator=admin.emp_no,
                action="update_config",
                table_name="configs",
                row_id=0,
                after_json={"section": body.section, "value": body.value},
            )
        )
        db.commit()
    return _safe_view()
