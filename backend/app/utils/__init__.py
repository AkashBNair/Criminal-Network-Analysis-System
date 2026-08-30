"""
Audit logging utility with blockchain hash-chain integrity.

Every log_audit() call appends a hash-chained block so that any
tampering with historical entries is detectable.
"""
from sqlalchemy.orm import Session
from app.models.models import AuditLog
from app.services.blockchain import build_block, GENESIS_HASH, compute_hash, _serialize_for_hash
import json
import logging

logger = logging.getLogger(__name__)


def _get_next_block_index(db: Session) -> int:
    """Get the next block index (max existing + 1)."""
    max_index = db.query(AuditLog.block_index).filter(
        AuditLog.block_index.isnot(None)
    ).order_by(AuditLog.block_index.desc()).first()
    return (max_index[0] + 1) if max_index and max_index[0] is not None else 0


def _get_previous_hash(db: Session) -> str:
    """Get the hash of the most recent block in the chain."""
    last = db.query(AuditLog).filter(
        AuditLog.block_hash.isnot(None)
    ).order_by(AuditLog.block_index.desc()).first()
    return last.block_hash if last else GENESIS_HASH


def log_audit(
    db: Session,
    user_id: str,
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    details: dict = None,
    ip_address: str = None,
):
    """
    Create an audit log entry with blockchain hash-chain.
    
    Computes:
    - details_hash: SHA-256 of the details JSON (fixed-length fingerprint)
    - previous_hash: hash of the most recent prior block (chain linkage)
    - block_hash: SHA-256 of this block's content + previous_hash (chain integrity)
    - block_index: sequential position in the chain
    """
    details = details or {}
    
    # Determine chain position
    block_index = _get_next_block_index(db)
    previous_hash = _get_previous_hash(db)
    
    # Build the hash-chained block
    block = build_block(
        audit_log_id="pending",  # will be set after commit
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        previous_hash=previous_hash,
        block_index=block_index,
    )
    
    # Create the audit log entry with blockchain fields
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        block_index=block_index,
        previous_hash=previous_hash,
        block_hash=block.block_hash,
        details_hash=block.details_hash,
        block_timestamp=block.timestamp,
        nonce=0,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    # Update the block with the actual audit_log_id and recompute hash
    block.audit_log_id = entry.id
    block.compute_block_hash()
    entry.block_hash = block.block_hash
    db.commit()
    
    logger.debug(f"Audit block #{block_index} committed: {entry.id[:8]}... action={action}")
    return entry
