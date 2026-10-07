# -*- coding: utf-8 -*-
"""审查员：待人工队列 + 判定。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Claim, User
from ..schemas import ClaimOut, ReviewIn
from ..security import require_admin

router = APIRouter(prefix="/api/review", tags=["review"])


def _to_out(c: Claim) -> ClaimOut:
    out = ClaimOut.model_validate(c)
    if c.user is not None:
        out.emp_no = c.user.emp_no
        out.emp_name = c.user.name
        out.department = c.user.department
        out.job_level = c.user.job_level
        out.position = c.user.position
    return out


@router.get("/queue", response_model=list[ClaimOut])
def queue(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(Claim)
        .filter(Claim.flow_status == 3)
        .order_by(Claim.submitted_at.asc())
        .all()
    )
    return [_to_out(c) for c in rows]


@router.post("/{claim_id}", response_model=ClaimOut)
def review(
    claim_id: int,
    body: ReviewIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "报销单不存在")
    if claim.flow_status != 3:
        raise HTTPException(400, "该单据不在待人工审查队列")
    before = {
        "flow_status": claim.flow_status,
        "reimb_result": claim.reimb_result,
        "reviewer_note": claim.reviewer_note,
    }
    claim.reimb_result = body.result
    claim.flow_status = 0
    claim.queue_state = 2
    claim.reviewer_note = body.note[:1000]
    claim.processed_at = datetime.now()
    db.add(
        AuditLog(
            operator=admin.emp_no,
            action="review",
            table_name="claims",
            row_id=claim.id,
            before_json=before,
            after_json={"reimb_result": body.result, "reviewer_note": body.note[:1000]},
        )
    )
    db.commit()
    db.refresh(claim)
    return _to_out(claim)
