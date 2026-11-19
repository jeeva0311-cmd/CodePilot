"""Approval request endpoints — human-in-the-loop for high-risk operations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models import ApprovalRequest

router = APIRouter()


class ApprovalDecision(BaseModel):
    decision: str   # "approved" | "rejected"
    reason: Optional[str] = ""


@router.get("/approvals/pending")
def list_pending(db: Session = Depends(get_db)):
    items = db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending").all()
    return [_approval_dict(a) for a in items]


@router.get("/approvals/{approval_id}")
def get_approval(approval_id: str, db: Session = Depends(get_db)):
    item = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not item:
        raise HTTPException(404, "Approval request not found")
    return _approval_dict(item)


@router.post("/approvals/{approval_id}/decide")
def decide_approval(approval_id: str, body: ApprovalDecision, db: Session = Depends(get_db)):
    item = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not item:
        raise HTTPException(404, "Approval request not found")
    if item.status != "pending":
        raise HTTPException(400, f"Approval already {item.status}")
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")

    item.status = body.decision
    item.decided_at = datetime.utcnow()
    item.reason = body.reason or ""
    db.commit()

    # Signal the waiting agent loop via the in-memory registry
    from app.services.approval_service import approval_service
    approval_service.signal(approval_id, body.decision)

    return {"success": True, "approval_id": approval_id, "decision": body.decision}


def _approval_dict(a: ApprovalRequest) -> dict:
    return {
        "id": a.id,
        "task_id": a.task_id,
        "tool_name": a.tool_name,
        "operation_summary": a.operation_summary,
        "risk_level": a.risk_level,
        "input_json": a.input_json,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "reason": a.reason,
    }
