"""
Blockchain Hash-Chain for Audit Log Integrity.

Every audit log entry is hashed and chained to the previous entry,
forming a tamper-evident chain. Any modification to a historical
entry breaks the chain and is detectable via verification.

This is a lightweight append-only hash chain — not a full blockchain
with consensus/mining — appropriate for single-institution audit logs
where the institution itself is the trusted writer.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Core hashing utilities
# ---------------------------------------------------------------------------

def _serialize_for_hash(data: dict) -> str:
    """Deterministic JSON serialization for hashing (sorted keys, no whitespace)."""
    return json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))


def compute_hash(payload: str) -> str:
    """SHA-256 hash of an arbitrary string payload."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Block data class
# ---------------------------------------------------------------------------

@dataclass
class AuditBlock:
    """A single block in the audit hash chain."""
    block_index: int
    timestamp: str
    audit_log_id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details_hash: str          # SHA-256 of the details JSON
    previous_hash: str         # hash of the immediately preceding block
    nonce: int = 0             # reserved for future proof-of-work if needed
    block_hash: str = ""       # computed; self-referential

    def compute_block_hash(self) -> str:
        """Compute this block's hash from all its fields (excluding block_hash itself)."""
        payload = _serialize_for_hash({
            "block_index": self.block_index,
            "timestamp": self.timestamp,
            "audit_log_id": self.audit_log_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details_hash": self.details_hash,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        })
        self.block_hash = compute_hash(payload)
        return self.block_hash

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Chain builder (called on every new audit entry)
# ---------------------------------------------------------------------------

GENESIS_HASH = "0" * 64  # 64 zeros — the "genesis block" hash


def build_block(
    audit_log_id: str,
    user_id: Optional[str],
    action: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    details: dict,
    previous_hash: str,
    block_index: int,
) -> AuditBlock:
    """
    Build a new AuditBlock, compute its hash, and return it.
    The caller is responsible for persisting it.
    """
    details_hash = compute_hash(_serialize_for_hash(details or {}))
    now = datetime.now(timezone.utc).isoformat()

    block = AuditBlock(
        block_index=block_index,
        timestamp=now,
        audit_log_id=audit_log_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_hash=details_hash,
        previous_hash=previous_hash,
        nonce=0,
    )
    block.compute_block_hash()
    return block


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Result of verifying an audit hash chain."""
    is_valid: bool
    total_blocks: int
    verified_blocks: int
    first_tampered_block_index: Optional[int] = None
    tampered_audit_log_id: Optional[str] = None
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def verify_chain(blocks: List[dict]) -> VerificationResult:
    """
    Verify a list of audit blocks in order (ascending block_index).
    
    Each block must:
    1. Have a valid block_hash (recomputed matches stored)
    2. Point to the correct previous_hash (chain linkage)
    
    Args:
        blocks: List of dicts, each representing an AuditBlock, sorted by block_index ASC.
    
    Returns:
        VerificationResult with details on integrity.
    """
    start = time.time()

    if not blocks:
        return VerificationResult(
            is_valid=True,
            total_blocks=0,
            verified_blocks=0,
            duration_ms=0,
        )

    prev_hash = GENESIS_HASH
    verified_count = 0

    for block_dict in blocks:
        idx = block_dict.get("block_index", -1)

        # 1. Check chain linkage
        stored_prev = block_dict.get("previous_hash", "")
        if stored_prev != prev_hash:
            return VerificationResult(
                is_valid=False,
                total_blocks=len(blocks),
                verified_blocks=verified_count,
                first_tampered_block_index=idx,
                tampered_audit_log_id=block_dict.get("audit_log_id"),
                expected_hash=prev_hash,
                actual_hash=stored_prev,
                error_message=f"Chain broken at block {idx}: expected previous_hash={prev_hash[:16]}..., got {stored_prev[:16]}...",
                duration_ms=(time.time() - start) * 1000,
            )

        # 2. Recompute block hash and compare
        recomputed_payload = _serialize_for_hash({
            "block_index": block_dict["block_index"],
            "timestamp": block_dict["timestamp"],
            "audit_log_id": block_dict["audit_log_id"],
            "user_id": block_dict.get("user_id"),
            "action": block_dict["action"],
            "resource_type": block_dict.get("resource_type"),
            "resource_id": block_dict.get("resource_id"),
            "details_hash": block_dict["details_hash"],
            "previous_hash": block_dict["previous_hash"],
            "nonce": block_dict.get("nonce", 0),
        })
        recomputed_hash = compute_hash(recomputed_payload)
        stored_hash = block_dict.get("block_hash", "")

        if recomputed_hash != stored_hash:
            return VerificationResult(
                is_valid=False,
                total_blocks=len(blocks),
                verified_blocks=verified_count,
                first_tampered_block_index=idx,
                tampered_audit_log_id=block_dict.get("audit_log_id"),
                expected_hash=recomputed_hash,
                actual_hash=stored_hash,
                error_message=f"Block {idx} hash tampered: expected {recomputed_hash[:16]}..., got {stored_hash[:16]}...",
                duration_ms=(time.time() - start) * 1000,
            )

        prev_hash = block_dict["block_hash"]
        verified_count += 1

    return VerificationResult(
        is_valid=True,
        total_blocks=len(blocks),
        verified_blocks=verified_count,
        duration_ms=(time.time() - start) * 1000,
    )
