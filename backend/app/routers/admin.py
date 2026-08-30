"""
Admin Router.
User management, role assignment, audit log access, blockchain verification.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.models import User, AuditLog, UserRole
from app.auth import get_current_user, RoleChecker, get_password_hash, ADMIN_ROLES
from app.utils import log_audit
from app.services.blockchain import verify_chain, GENESIS_HASH

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


# ---------------------------------------------------------------------------
# Blockchain chain verification endpoints
# ---------------------------------------------------------------------------

@router.get("/audit-log/chain-status")
def get_chain_status(
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Return summary stats for the audit hash chain."""
    total = db.query(AuditLog).count()
    chained = db.query(AuditLog).filter(AuditLog.block_hash.isnot(None)).count()
    unchained = total - chained
    last_block = db.query(AuditLog).filter(
        AuditLog.block_hash.isnot(None)
    ).order_by(AuditLog.block_index.desc()).first()

    return {
        "total_entries": total,
        "chained_entries": chained,
        "unchained_entries": unchained,
        "last_block_index": last_block.block_index if last_block else None,
        "last_block_hash": last_block.block_hash[:16] + "..." if last_block and last_block.block_hash else None,
        "chain_integrity": "partial" if unchained > 0 else "full",
    }


@router.post("/audit-log/verify-chain")
def verify_audit_chain(
    limit: int = Query(0, description="0 = verify entire chain"),
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Verify the integrity of the audit hash chain.
    
    Checks:
    1. Each block's previous_hash matches the prior block's block_hash
    2. Each block's own hash is correctly computed from its contents
    
    Returns a detailed verification result.
    """
    query = db.query(AuditLog).filter(
        AuditLog.block_hash.isnot(None)
    ).order_by(AuditLog.block_index.asc())

    if limit > 0:
        query = query.limit(limit)

    logs = query.all()

    if not logs:
        return {
            "is_valid": True,
            "total_blocks": 0,
            "verified_blocks": 0,
            "message": "No chained audit entries found.",
        }

    # Convert to dicts for the verification function
    blocks = []
    for log_entry in logs:
        blocks.append({
            "block_index": log_entry.block_index,
            "timestamp": log_entry.block_timestamp or (log_entry.timestamp.isoformat() if log_entry.timestamp else ""),
            "audit_log_id": log_entry.id,
            "user_id": log_entry.user_id,
            "action": log_entry.action,
            "resource_type": log_entry.resource_type,
            "resource_id": log_entry.resource_id,
            "details_hash": log_entry.details_hash or "",
            "previous_hash": log_entry.previous_hash or GENESIS_HASH,
            "nonce": log_entry.nonce or 0,
            "block_hash": log_entry.block_hash,
        })

    result = verify_chain(blocks)

    log_audit(db, current_user.id, "verify_chain", "audit_log", None,
              {"blocks_checked": result.total_blocks, "is_valid": result.is_valid})

    return result.to_dict()


@router.get("/audit-log/chain-block/{block_index}")
def get_chain_block(
    block_index: int,
    current_user: User = Depends(RoleChecker(ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Get a specific block from the chain by its index."""
    entry = db.query(AuditLog).filter(
        AuditLog.block_index == block_index
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail=f"Block {block_index} not found")

    return {
        "block_index": entry.block_index,
        "audit_log_id": entry.id,
        "user_id": entry.user_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "details": entry.details or {},
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "previous_hash": entry.previous_hash,
        "block_hash": entry.block_hash,
        "details_hash": entry.details_hash,
        "nonce": entry.nonce,
    }
