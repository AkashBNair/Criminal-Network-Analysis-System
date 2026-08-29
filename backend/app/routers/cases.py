"""
Cases Router.
CRUD operations for cases, case assignments, and status management.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.models import (
    User, Case, CaseAssignment, Entity, Relationship,
    Alert, Document, CaseStatus, UserRole
)
from app.auth import get_current_user, RoleChecker, ADMIN_ROLES, IO_ROLES, VIEW_ALL_CASES
from app.utils import log_audit

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


class CaseCreate(BaseModel):
    case_number: str
    name: str
    description: Optional[str] = None
    jurisdiction: Optional[str] = None


class CaseAssign(BaseModel):
    user_id: str


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    jurisdiction: Optional[str] = None
    status: Optional[str] = None


def _case_summary(case, db):
    entity_count = db.query(Entity).filter(
        Entity.case_id == case.id, Entity.is_merged_into.is_(None)
    ).count()
    relationship_count = db.query(Relationship).filter(
        Relationship.case_id == case.id
    ).count()
    alert_count = db.query(Alert).filter(Alert.case_id == case.id).count()
    document_count = db.query(Document).filter(Document.case_id == case.id).count()
    return {
        "id": case.id,
        "case_number": case.case_number,
        "name": case.name,
        "description": case.description,
        "status": case.status.value if hasattr(case.status, 'value') else case.status,
        "jurisdiction": case.jurisdiction,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "entity_count": entity_count,
        "relationship_count": relationship_count,
        "alert_count": alert_count,
        "document_count": document_count,
    }


@router.get("")
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List cases. Default: active only. Can filter by status."""
    if current_user.role in VIEW_ALL_CASES:
        query = db.query(Case)
    else:
        assigned_ids = [a.case_id for a in current_user.case_assignments]
        query = db.query(Case).filter(Case.id.in_(assigned_ids))

    if status_filter:
        query = query.filter(Case.status == CaseStatus(status_filter))
    else:
        # Default: exclude archived
        query = query.filter(Case.status != CaseStatus.ARCHIVED)

    cases = query.all()
    return [_case_summary(c, db) for c in cases]


@router.get("/archived")
def list_archived_cases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List archived/closed cases."""
    if current_user.role in VIEW_ALL_CASES:
        cases = db.query(Case).filter(Case.status == CaseStatus.ARCHIVED).all()
    else:
        assigned_ids = [a.case_id for a in current_user.case_assignments]
        cases = db.query(Case).filter(
            Case.id.in_(assigned_ids),
            Case.status == CaseStatus.ARCHIVED
        ).all()
    return [_case_summary(c, db) for c in cases]


@router.post("")
def create_case(
    case_data: CaseCreate,
    current_user: User = Depends(RoleChecker(IO_ROLES)),
    db: Session = Depends(get_db),
):
    case = Case(
        case_number=case_data.case_number,
        name=case_data.name,
        description=case_data.description,
        jurisdiction=case_data.jurisdiction,
        created_by=current_user.id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    assignment = CaseAssignment(user_id=current_user.id, case_id=case.id)
    db.add(assignment)
    db.commit()

    log_audit(db, current_user.id, "create_case", "case", case.id,
              {"case_number": case.case_number})

    return {
        "id": case.id,
        "case_number": case.case_number,
        "name": case.name,
        "status": case.status.value if hasattr(case.status, 'value') else case.status,
    }


@router.get("/{case_id}")
def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role not in VIEW_ALL_CASES:
        assigned = db.query(CaseAssignment).filter(
            CaseAssignment.user_id == current_user.id,
            CaseAssignment.case_id == case_id,
        ).first()
        if not assigned:
            raise HTTPException(status_code=403, detail="Access denied to this case")

    summary = _case_summary(case, db)

    # Get assigned users
    assignments = db.query(CaseAssignment).filter(CaseAssignment.case_id == case_id).all()
    assigned_users = []
    for a in assignments:
        user = db.query(User).filter(User.id == a.user_id).first()
        if user:
            assigned_users.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role.value,
            })

    summary["assigned_users"] = assigned_users
    return summary


@router.put("/{case_id}")
def update_case(
    case_id: str,
    update: CaseUpdate,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES + IO_ROLES)),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if update.name is not None:
        case.name = update.name
    if update.description is not None:
        case.description = update.description
    if update.jurisdiction is not None:
        case.jurisdiction = update.jurisdiction
    if update.status is not None:
        case.status = CaseStatus(update.status)

    db.commit()

    log_audit(db, current_user.id, "update_case", "case", case_id,
              {"changes": update.dict(exclude_unset=True)})

    return {"message": "Case updated", "status": case.status.value}


@router.post("/{case_id}/close")
def close_case(
    case_id: str,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES + IO_ROLES)),
    db: Session = Depends(get_db),
):
    """Close a case (mark as archived)."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = CaseStatus.ARCHIVED
    db.commit()

    log_audit(db, current_user.id, "close_case", "case", case_id)
    return {"message": "Case closed", "status": "Archived"}


@router.post("/{case_id}/reopen")
def reopen_case(
    case_id: str,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES + IO_ROLES)),
    db: Session = Depends(get_db),
):
    """Reopen a closed/archived case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = CaseStatus.ACTIVE
    db.commit()

    log_audit(db, current_user.id, "reopen_case", "case", case_id)
    return {"message": "Case reopened", "status": "Active"}


@router.post("/{case_id}/assign")
def assign_user(
    case_id: str,
    assignment: CaseAssign,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    user = db.query(User).filter(User.id == assignment.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(CaseAssignment).filter(
        CaseAssignment.user_id == assignment.user_id,
        CaseAssignment.case_id == case_id,
    ).first()
    if existing:
        return {"message": "User already assigned to this case"}

    new_assignment = CaseAssignment(user_id=assignment.user_id, case_id=case_id)
    db.add(new_assignment)
    db.commit()

    log_audit(db, current_user.id, "assign_case_user", "case", case_id,
              {"user_id": assignment.user_id})

    return {"message": "User assigned successfully"}


@router.post("/{case_id}/unassign")
def unassign_user(
    case_id: str,
    assignment: CaseAssign,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Remove an officer's access to a case."""
    existing = db.query(CaseAssignment).filter(
        CaseAssignment.user_id == assignment.user_id,
        CaseAssignment.case_id == case_id,
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Assignment not found")

    db.delete(existing)
    db.commit()

    log_audit(db, current_user.id, "unassign_case_user", "case", case_id,
              {"user_id": assignment.user_id})

    return {"message": "User unassigned successfully"}
