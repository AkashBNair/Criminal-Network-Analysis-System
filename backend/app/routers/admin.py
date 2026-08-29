"""
Admin Router.
User management, role assignment, audit log access.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.models import User, AuditLog, UserRole
from app.auth import get_current_user, RoleChecker, get_password_hash, ADMIN_ROLES
from app.utils import log_audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    role: str = "investigating_officer"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/users")
def list_users(
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    users = db.query(User).all()
    return [{
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    } for user in users]


@router.post("/users")
def create_user(
    user_data: UserCreate,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    # Check unique username
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole(user_data.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit(db, current_user.id, "create_user", "user", user.id,
              {"username": user.username})

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: str,
    update: UserUpdate,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if update.email is not None:
        user.email = update.email
    if update.full_name is not None:
        user.full_name = update.full_name
    if update.role is not None:
        user.role = UserRole(update.role)
    if update.is_active is not None:
        user.is_active = update.is_active

    db.commit()

    log_audit(db, current_user.id, "update_user", "user", user_id,
              {"changes": update.dict(exclude_unset=True)})

    return {"message": "User updated", "id": user.id}


@router.get("/audit-log")
def get_audit_log(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))

    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()

    return [{
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "details": log.details or {},
        "ip_address": log.ip_address,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
    } for log in logs]
