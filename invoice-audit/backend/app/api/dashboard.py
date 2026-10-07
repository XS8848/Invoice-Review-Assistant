# -*- coding: utf-8 -*-
"""数据看板：全表查询 + 统计 + 历史结果修正（写审计日志）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from ..database import engine, get_db
from ..models import AuditLog, Claim, User
from ..schemas import ClaimOut, DashboardEditIn
from ..security import require_admin

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/tables")
def tables(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    insp = inspect(engine)
    quote = engine.dialect.identifier_preparer.quote
    out = []
    for name in insp.get_table_names():
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {quote(name)}")).scalar()
        except Exception:
            count = None
        out.append({"table": name, "rows": count, "columns": [c["name"] for c in insp.get_columns(name)]})
    return out


@router.get("/table/{table_name}")
def table_data(
    table_name: str,
    page: int = 1,
    page_size: int = 20,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """浏览任意表的数据（含密码表 users，密码为哈希值）。"""
    import datetime as _dt
    import decimal as _dec

    insp = inspect(engine)
    allowed = set(insp.get_table_names())
    if table_name not in allowed:
        raise HTTPException(404, f"表不存在: {table_name}")
    quote = engine.dialect.identifier_preparer.quote
    total = db.execute(text(f"SELECT COUNT(*) FROM {quote(table_name)}")).scalar()
    offset = max(0, (page - 1) * page_size)
    rows = db.execute(
        text(f"SELECT * FROM {quote(table_name)} LIMIT :limit OFFSET :offset"),
        {"limit": page_size, "offset": offset},
    ).mappings().all()
    cols = [c["name"] for c in insp.get_columns(table_name)]

    def conv(v):
        if isinstance(v, (_dt.datetime, _dt.date, _dec.Decimal)):
            return str(v)
        return v

    return {
        "table": table_name,
        "columns": cols,
        "rows": [{c: conv(r.get(c)) for c in cols} for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/claims")
def all_claims(
    page: int = 1,
    page_size: int = 50,
    flow_status: int | None = None,
    reimb_result: int | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Claim)
    if flow_status is not None:
        q = q.filter(Claim.flow_status == flow_status)
    if reimb_result is not None:
        q = q.filter(Claim.reimb_result == reimb_result)
    total = q.count()
    rows = q.order_by(Claim.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    out = []
    for c in rows:
        o = ClaimOut.model_validate(c)
        if c.user:
            o.emp_no, o.emp_name = c.user.emp_no, c.user.name
            o.department, o.job_level, o.position = c.user.department, c.user.job_level, c.user.position
        out.append(o)
    return {"total": total, "items": [x.model_dump(mode="json") for x in out]}


@router.get("/stats")
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    def counts(col):
        rows = db.query(col, func.count()).group_by(col).all()
        return {int(k): v for k, v in rows}

    return {
        "total": db.query(Claim).count(),
        "by_flow": counts(Claim.flow_status),
        "by_result": counts(Claim.reimb_result),
        "users": db.query(User).count(),
    }


@router.put("/claims/{claim_id}")
def edit_claim(
    claim_id: int,
    body: DashboardEditIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "报销单不存在")
    before = {
        "flow_status": claim.flow_status,
        "reimb_result": claim.reimb_result,
        "model_note": claim.model_note,
        "reviewer_note": claim.reviewer_note,
    }
    if body.reimb_result is not None:
        claim.reimb_result = body.reimb_result
    if body.flow_status is not None:
        claim.flow_status = body.flow_status
    if body.model_note is not None:
        claim.model_note = body.model_note[:1000]
    if body.reviewer_note is not None:
        claim.reviewer_note = body.reviewer_note[:1000]
    after = {
        "flow_status": claim.flow_status,
        "reimb_result": claim.reimb_result,
        "model_note": claim.model_note,
        "reviewer_note": claim.reviewer_note,
    }
    db.add(
        AuditLog(
            operator=admin.emp_no,
            action="dashboard_edit",
            table_name="claims",
            row_id=claim.id,
            before_json=before,
            after_json=after,
        )
    )
    db.commit()
    return {"ok": True}


@router.put("/claims/{claim_id}/requeue")
def requeue_claim(
    claim_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重新派发：失败/已处理单据重置回视觉识别流程（flow=1, queue=1）。"""
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "报销单不存在")
    before = {"flow_status": claim.flow_status, "reimb_result": claim.reimb_result,
              "queue_state": claim.queue_state}
    claim.flow_status = 1
    claim.queue_state = 1
    claim.reimb_result = 2
    claim.exception_type = 0
    claim.model_note = f"[重新派发] {claim.model_note}".strip()
    claim.reviewer_note = ""
    claim.lock_owner = ""
    claim.lock_acquired_at = None
    after = {"flow_status": 1, "queue_state": 1}
    db.add(
        AuditLog(
            operator=admin.emp_no,
            action="requeue",
            table_name="claims",
            row_id=claim.id,
            before_json=before,
            after_json=after,
        )
    )
    db.commit()
    return {"ok": True}


@router.get("/audit-logs")
def audit_logs(page: int = 1, page_size: int = 50, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [
        {
            "id": r.id,
            "operator": r.operator,
            "action": r.action,
            "table_name": r.table_name,
            "row_id": r.row_id,
            "before_json": r.before_json,
            "after_json": r.after_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
