# -*- coding: utf-8 -*-
"""报销单：上传 / 我的历史 / 原图 / 撤销。"""
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import Claim, User
from ..schemas import ClaimOut
from ..security import get_current_user
from ..services import minio_service

router = APIRouter(prefix="/api/claims", tags=["claims"])

_MAGIC = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG": "png",
    b"%PDF": "pdf",
}


def _detect_type(head: bytes) -> str:
    for magic, t in _MAGIC.items():
        if head.startswith(magic):
            return t
    return ""


def _to_out(c: Claim, u: User | None = None) -> ClaimOut:
    out = ClaimOut.model_validate(c)
    if u is not None:
        out.emp_no = u.emp_no
        out.emp_name = u.name
        out.department = u.department
        out.job_level = u.job_level
        out.position = u.position
    return out


@router.post("", response_model=list[ClaimOut])
async def upload(
    files: list[UploadFile] = File(...),
    note: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(files) > config.UPLOAD_MAX_FILES:
        raise HTTPException(400, f"单次最多上传 {config.UPLOAD_MAX_FILES} 个文件")
    batch_id = uuid.uuid4().hex[:16]
    created: list[Claim] = []
    for idx, f in enumerate(files):
        ext = ("." + f.filename.rsplit(".", 1)[-1].lower()) if "." in (f.filename or "") else ""
        if ext not in config.ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"不支持的文件类型: {f.filename}")
        content = await f.read()
        if len(content) > config.UPLOAD_MAX_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"文件超过 {config.UPLOAD_MAX_SIZE_MB}MB: {f.filename}")
        ftype = _detect_type(content[:16])
        if ftype == "" or (ext in (".jpg", ".jpeg") and ftype != "jpg") or (ext == ".png" and ftype != "png") or (ext == ".pdf" and ftype != "pdf"):
            raise HTTPException(400, f"文件内容与扩展名不符: {f.filename}")
        # 文件名净化：仅取最后一段，防路径穿越/控制字符
        safe_name = (f.filename or "").replace("\\", "/").split("/")[-1].strip() or f"file{idx:02d}{ext}"
        safe_name = re.sub(r"[\x00-\x1f]", "", safe_name)[:200]

        key = f"{user.emp_no}/{batch_id}/{idx:02d}_{safe_name}"
        tmp = config.TEMP_DIR / f"{uuid.uuid4().hex}{ext}"
        tmp.write_bytes(content)
        try:
            minio_service.put_file(tmp, key, content_type=f.content_type or "")
        finally:
            tmp.unlink(missing_ok=True)

        claim = Claim(
            batch_id=batch_id,
            user_id=user.id,
            file_key=key,
            file_name=safe_name,
            file_type=ftype,
            file_size=len(content),
            flow_status=1,
            reimb_result=2,
            exception_type=0,
            queue_state=1,
            user_note=(note or "")[:1000],
        )
        db.add(claim)
        created.append(claim)
    db.commit()
    for c in created:
        db.refresh(c)
    return [_to_out(c, user) for c in created]


@router.get("/mine", response_model=list[ClaimOut])
def my_claims(
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Claim)
        .filter(Claim.user_id == user.id)
        .order_by(Claim.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_to_out(c, user) for c in rows]


@router.get("/batch/{batch_id}", response_model=list[ClaimOut])
def batch_claims(
    batch_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批次内全部文件（审查员或批次所属员工可查，用于聚合审查上下文）。"""
    rows = db.query(Claim).filter(Claim.batch_id == batch_id).order_by(Claim.id).all()
    if not rows:
        raise HTTPException(404, "批次不存在")
    if user.role != "admin" and rows[0].user_id != user.id:
        raise HTTPException(403, "无权查看该批次")
    owner = db.get(User, rows[0].user_id)
    return [_to_out(c, owner) for c in rows]


@router.get("/{claim_id}/file")
def claim_file(claim_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "报销单不存在")
    if user.role != "admin" and claim.user_id != user.id:
        raise HTTPException(403, "无权查看该报销单")
    # 返回 JSON URL：前端用 axios（携带 JWT）获取后再加载，避免 <img>/<iframe> 直连被 401
    url = minio_service.presigned_url_for_host(claim.file_key, request.headers.get("host", ""))
    return {"url": url}


@router.delete("/{claim_id}")
def delete_claim(claim_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "报销单不存在")
    if claim.user_id != user.id:
        raise HTTPException(403, "只能撤销自己的报销单")
    if claim.queue_state != 1 or claim.flow_status not in (1, 3):
        raise HTTPException(400, "仅待处理或待人工审查的单据可撤销")
    try:
        minio_service.remove_file(claim.file_key)
    except Exception:
        pass
    db.delete(claim)
    db.commit()
    return {"ok": True}
