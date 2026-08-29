"""
Entity Resolution Service.
Evidence-based merging with multiple corroborating signals required.
"""
import re
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session
from app.models.models import Entity, EntityType, AuditLog
from typing import Optional
import json
from datetime import datetime, timezone


# Evidence signals and their weights
EVIDENCE_SIGNALS = {
    "identical_phone": {"weight": 1.0, "description": "Identical phone number/IMEI"},
    "identical_address": {"weight": 0.8, "description": "Identical address"},
    "identical_dob": {"weight": 0.9, "description": "Identical date of birth"},
    "identical_father_name": {"weight": 0.85, "description": "Identical father's name"},
    "identical_physical": {"weight": 0.7, "description": "Identical physical description"},
    "shared_associates": {"weight": 0.5, "description": "Shared associates in both records"},
    "shared_case": {"weight": 0.2, "description": "Same case number"},
    "shared_io": {"weight": 0.1, "description": "Same investigating officer"},
}

# Thresholds for merge decisions
MERGE_THRESHOLD_STRONG = 2  # 2+ independent signals beyond name → auto merge
MERGE_THRESHOLD_MEDIUM = 1  # 1 signal beyond name → merge with medium confidence
NO_MERGE_FLAG = "possible_duplicate_unconfirmed"


def extract_corroborating_signals(entity_a: Entity, entity_b: Entity, db: Session) -> dict:
    """
    Extract all corroborating signals between two entities.
    Returns dict of signal_type → {matched: bool, evidence: str, weight: float}
    """
    signals = {}
    
    # 1. Phone number matching
    phones_a = set()
    phones_b = set()
    
    for entity, phone_set in [(entity_a, phones_a), (entity_b, phones_b)]:
        attrs = entity.attributes or {}
        for k, v in attrs.items():
            if 'phone' in k.lower() or 'number' in k.lower():
                if isinstance(v, list):
                    for item in v:
                        phone_set.add(re.sub(r'[^\d]', '', str(item)))
                else:
                    phone_set.add(re.sub(r'[^\d]', '', str(v)))
        
        # Also check if name looks like a phone
        if re.match(r'^[\d\+\-\(\)\s]{7,15}$', entity.name):
            phone_set.add(re.sub(r'[^\d]', '', entity.name))
    
    if phones_a and phones_b and phones_a & phones_b:
        signals["identical_phone"] = {
            "matched": True,
            "evidence": f"Phone numbers: {list(phones_a & phones_b)}",
            "weight": EVIDENCE_SIGNALS["identical_phone"]["weight"]
        }
    
    # 2. Address matching
    addrs_a = set()
    addrs_b = set()
    
    for entity, addr_set in [(entity_a, addrs_a), (entity_b, addrs_b)]:
        attrs = entity.attributes or {}
        for k, v in attrs.items():
            if 'address' in k.lower() or 'location' in k.lower():
                if isinstance(v, str):
                    addr_set.add(v.lower().strip())
    
    if addrs_a and addrs_b and addrs_a & addrs_b:
        signals["identical_address"] = {
            "matched": True,
            "evidence": f"Addresses: {list(addrs_a & addrs_b)}",
            "weight": EVIDENCE_SIGNALS["identical_address"]["weight"]
        }
    
    # 3. DOB matching
    dob_a = entity_a.attributes.get("dob") or entity_a.attributes.get("date_of_birth")
    dob_b = entity_b.attributes.get("dob") or entity_b.attributes.get("date_of_birth")
    
    if dob_a and dob_b and str(dob_a).strip() == str(dob_b).strip():
        signals["identical_dob"] = {
            "matched": True,
            "evidence": f"DOB: {dob_a}",
            "weight": EVIDENCE_SIGNALS["identical_dob"]["weight"]
        }
    
    # 4. Father's name matching
    father_a = entity_a.attributes.get("father_name") or entity_a.attributes.get("father")
    father_b = entity_b.attributes.get("father_name") or entity_b.attributes.get("father")
    
    if father_a and father_b:
        if fuzz.token_sort_ratio(str(father_a).lower(), str(father_b).lower()) > 85:
            signals["identical_father_name"] = {
                "matched": True,
                "evidence": f"Father's name: {father_a}",
                "weight": EVIDENCE_SIGNALS["identical_father_name"]["weight"]
            }
    
    # 5. Physical description matching
    phys_keys = ["height", "weight", "build", "marks", "identification"]
    phys_a = []
    phys_b = []
    
    for entity, phys_list in [(entity_a, phys_a), (entity_b, phys_b)]:
        attrs = entity.attributes or {}
        for k, v in attrs.items():
            if any(pk in k.lower() for pk in phys_keys):
                if v:
                    phys_list.append(f"{k}:{v}")
    
    if phys_a and phys_b:
        # Simple overlap check
        phys_set_a = set(phys_a)
        phys_set_b = set(phys_b)
        if phys_set_a & phys_set_b:
            signals["identical_physical"] = {
                "matched": True,
                "evidence": f"Physical: {list(phys_set_a & phys_set_b)}",
                "weight": EVIDENCE_SIGNALS["identical_physical"]["weight"]
            }
    
    # 6. Shared associates (entities connected to both)
    from app.models.models import Relationship
    
    rels_a_source = db.query(Relationship).filter(
        Relationship.source_entity_id == entity_a.id
    ).all()
    rels_a_target = db.query(Relationship).filter(
        Relationship.target_entity_id == entity_a.id
    ).all()
    rels_b_source = db.query(Relationship).filter(
        Relationship.source_entity_id == entity_b.id
    ).all()
    rels_b_target = db.query(Relationship).filter(
        Relationship.target_entity_id == entity_b.id
    ).all()
    
    connected_a = set()
    connected_b = set()
    
    for rel in rels_a_source + rels_a_target:
        other = rel.target_entity_id if rel.source_entity_id == entity_a.id else rel.source_entity_id
        connected_a.add(other)
    
    for rel in rels_b_source + rels_b_target:
        other = rel.target_entity_id if rel.source_entity_id == entity_b.id else rel.source_entity_id
        connected_b.add(other)
    
    shared = connected_a & connected_b
    if len(shared) >= 2:  # At least 2 shared associates
        signals["shared_associates"] = {
            "matched": True,
            "evidence": f"{len(shared)} shared associates",
            "weight": EVIDENCE_SIGNALS["shared_associates"]["weight"]
        }
    
    # 7. Same case
    if entity_a.case_id == entity_b.case_id:
        signals["shared_case"] = {
            "matched": True,
            "evidence": "Same case",
            "weight": EVIDENCE_SIGNALS["shared_case"]["weight"]
        }
    
    return signals


def _is_partial_name(name: str) -> bool:
    """
    Detect if a name is partial (surname-only or first-name-only).
    A single-word name is always partial — it could represent multiple
    different people who share that surname.
    """
    words = name.strip().split()
    if len(words) <= 1:
        return True  # Single word = surname-only or first-name-only
    if len(name.strip()) < 4:
        return True  # Very short names are likely fragments
    return False


def compute_similarity(entity_a: Entity, entity_b: Entity) -> float:
    """
    Compute name similarity score between two entities (0.0-1.0).
    Used for initial candidate selection, NOT for merge decision.

    IMPORTANT: Partial/surname-only names are NEVER merged based on
    name similarity alone. If either entity has a partial name, the
    similarity score is set to 0.0 unless corroborating evidence exists.
    """
    if entity_a.entity_type != entity_b.entity_type:
        return 0.0
    
    name_a = entity_a.name.lower().strip()
    name_b = entity_b.name.lower().strip()
    
    # ── PARTIAL NAME GUARD ──
    # If either entity has a partial name (surname-only), do NOT allow
    # name-only merge. Partial names must have corroborating evidence
    # (phone, address, DOB) to be merged.
    if _is_partial_name(entity_a.name) or _is_partial_name(entity_b.name):
        # Check if entity has a partial_identity flag from extraction
        attrs_a = entity_a.attributes or {}
        attrs_b = entity_b.attributes or {}
        is_partial_a = attrs_a.get("partial_identity", False) or _is_partial_name(entity_a.name)
        is_partial_b = attrs_b.get("partial_identity", False) or _is_partial_name(entity_b.name)
        
        if is_partial_a or is_partial_b:
            # For partial names, require ALL name words to be contained in the other
            # AND the partial entity must have fewer words
            words_a = set(name_a.split())
            words_b = set(name_b.split())
            
            # If both are single-word and different, return 0
            if len(words_a) == 1 and len(words_b) == 1:
                if name_a != name_b:
                    return 0.0  # Different surnames — definitely different people
                # Same surname — still return 0 for name-only merge
                # (corroborating evidence required)
                return 0.0
            
            # If one is partial and the other is full, check containment
            if len(words_a) == 1 and words_a.issubset(words_b):
                return 0.3  # Low score — partial match, needs corroboration
            if len(words_b) == 1 and words_b.issubset(words_a):
                return 0.3  # Low score — partial match, needs corroboration

    # ── Layer 7: Block partial-vs-different-full-name false matches ──
    # If one name is a single word and the other is a different multi-word name,
    # the single word might appear as a substring, causing false fuzzy matches.
    is_one_partial = len(name_a.split()) == 1 or len(name_b.split()) == 1
    if is_one_partial:
        # Check if the partial name is actually contained in the full name
        words_a_set = set(name_a.split())
        words_b_set = set(name_b.split())
        if not words_a_set.issubset(words_b_set) and not words_b_set.issubset(words_a_set):
            # Partial name is NOT contained in the other — different people
            return 0.0

    name_score = fuzz.token_sort_ratio(name_a, name_b) / 100.0
    
    # Check aliases too
    aliases_a = set(a.lower() for a in (entity_a.aliases or []))
    aliases_b = set(a.lower() for a in (entity_b.aliases or []))
    all_names_a = aliases_a | {name_a}
    all_names_b = aliases_b | {name_b}
    
    best_score = name_score
    for na in all_names_a:
        for nb in all_names_b:
            s = fuzz.token_sort_ratio(na, nb) / 100.0
            best_score = max(best_score, s)
    
    return best_score


def find_potential_matches(
    db: Session,
    entity: Entity,
    case_id: str = None,
    threshold: float = 0.60,
    limit: int = 10
) -> list[dict]:
    """
    Find potential duplicate entities matching the given entity.
    Returns list with similarity score AND corroborating signals.
    """
    query = db.query(Entity).filter(
        Entity.entity_type == entity.entity_type,
        Entity.id != entity.id,
        Entity.is_merged_into.is_(None),
    )
    if case_id:
        query = query.filter(Entity.case_id == case_id)
    
    candidates = query.all()
    matches = []
    
    for candidate in candidates:
        name_score = compute_similarity(entity, candidate)
        if name_score >= threshold:
            # Gather corroborating signals
            signals = extract_corroborating_signals(entity, candidate, db)
            signal_count = sum(1 for s in signals.values() if s["matched"])
            
            # ── PARTIAL NAME CHECK ──
            # If either entity has a partial name (surname-only), require
            # MORE corroborating signals to prevent merging different people
            is_partial = (
                _is_partial_name(entity.name)
                or _is_partial_name(candidate.name)
                or (entity.attributes or {}).get("partial_identity", False)
                or (candidate.attributes or {}).get("partial_identity", False)
            )
            if is_partial:
                # Require at least 2 strong signals (phone, address, DOB) for partial names
                strong_signals = sum(
                    1 for k, v in signals.items()
                    if v["matched"] and k in ("identical_phone", "identical_address", "identical_dob", "identical_father_name")
                )
                if strong_signals < 2:
                    # Not enough evidence to merge partial-name entities
                    continue

            # ── Layer 7: Cross-Case Name Collision Protection ──
            # Never merge two entities across different cases based on name
            # match alone — require at least one corroborating signal.
            is_cross_case = entity.case_id != candidate.case_id
            if is_cross_case and signal_count == 0:
                # Same name but different cases with no corroborating evidence
                # (no shared phone, address, DOB, associates) — skip
                continue

            matches.append({
                "entity_id": candidate.id,
                "entity_name": candidate.name,
                "entity_type": candidate.entity_type.value,
                "name_similarity": round(name_score, 4),
                "signal_count": signal_count,
                "signals": {k: v for k, v in signals.items() if v["matched"]},
                "merge_recommendation": _get_merge_recommendation(signal_count, is_partial=is_partial),
                "case_id": candidate.case_id,
                "is_partial_name_match": is_partial,
            })
    
    matches.sort(key=lambda x: (x["signal_count"], x["name_similarity"]), reverse=True)
    return matches[:limit]


def _get_merge_recommendation(signal_count: int, is_partial: bool = False) -> dict:
    """
    Get merge recommendation based on signal count.
    For partial names (surname-only), auto_merge is NEVER allowed —
    always require human review.
    """
    if is_partial:
        # Partial names NEVER auto-merge — always require human review
        if signal_count >= MERGE_THRESHOLD_STRONG:
            return {
                "action": "merge_with_review",
                "confidence": "medium",
                "reason": f"Partial name match with {signal_count} corroborating signals - REQUIRES human verification (surname-only entities may represent different individuals)"
            }
        else:
            return {
                "action": "do_not_merge",
                "confidence": "low",
                "reason": "Partial name (surname-only) with insufficient corroborating evidence - may represent different individuals"
            }
    
    if signal_count >= MERGE_THRESHOLD_STRONG:
        return {
            "action": "auto_merge",
            "confidence": "high",
            "reason": f"{signal_count} corroborating signals beyond name match"
        }
    elif signal_count >= MERGE_THRESHOLD_MEDIUM:
        return {
            "action": "merge_with_review",
            "confidence": "medium",
            "reason": f"{signal_count} corroborating signal(s) - recommend human review"
        }
    else:
        return {
            "action": "do_not_merge",
            "confidence": "low",
            "reason": "Insufficient corroborating evidence beyond name match"
        }


def merge_entities(
    db: Session,
    primary_entity_id: str,
    secondary_entity_id: str,
    user_id: str,
    merge_reason: str = "",
    confidence: str = "high"
) -> Entity:
    """
    Merge two entities with full audit trail.
    Only call when merge criteria are met.
    """
    primary = db.query(Entity).filter(Entity.id == primary_entity_id).first()
    secondary = db.query(Entity).filter(Entity.id == secondary_entity_id).first()
    
    if not primary or not secondary:
        raise ValueError("Entity not found")
    if primary.entity_type != secondary.entity_type:
        raise ValueError("Cannot merge entities of different types")
    
    # Gather evidence for audit
    signals = extract_corroborating_signals(primary, secondary, db)
    evidence = {k: v for k, v in signals.items() if v["matched"]}
    
    # Merge aliases
    aliases = list(set(
        (primary.aliases or []) + (secondary.aliases or []) + [secondary.name]
    ))
    primary.aliases = aliases
    
    # Merge attributes (primary wins on conflict)
    primary_attrs = primary.attributes or {}
    secondary_attrs = secondary.attributes or {}
    for key, value in secondary_attrs.items():
        if key not in primary_attrs:
            primary_attrs[key] = value
        elif isinstance(primary_attrs[key], list) and isinstance(value, list):
            primary_attrs[key] = list(set(primary_attrs[key] + value))
    primary.attributes = primary_attrs
    
    # Update confidence based on evidence strength
    if confidence == "high":
        primary.confidence_score = min(1.0, primary.confidence_score + 0.1)
    
    # Update relationships: redirect secondary's relationships to primary
    from app.models.models import Relationship
    
    # Redirect source relationships
    source_rels = db.query(Relationship).filter(
        Relationship.source_entity_id == secondary_entity_id
    ).all()
    for rel in source_rels:
        rel.source_entity_id = primary_entity_id
        rel.weight = min(rel.weight * 1.2, 10.0)  # Boost merged weight
    
    # Redirect target relationships
    target_rels = db.query(Relationship).filter(
        Relationship.target_entity_id == secondary_entity_id
    ).all()
    for rel in target_rels:
        rel.target_entity_id = primary_entity_id
        rel.weight = min(rel.weight * 1.2, 10.0)
    
    # Deduplicate relationships after merge
    _deduplicate_relationships(db, primary_entity_id)
    
    # Mark secondary as merged
    secondary.is_merged_into = primary_entity_id
    
    # Audit log
    audit_log = AuditLog(
        user_id=user_id,
        action="entity_merge",
        resource_type="entity",
        resource_id=primary_entity_id,
        details={
            "merged_entity_id": secondary_entity_id,
            "merged_entity_name": secondary.name,
            "evidence": evidence,
            "confidence": confidence,
            "reason": merge_reason,
            "signal_count": len(evidence),
        },
        timestamp=datetime.now(timezone.utc)
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(primary)
    return primary


def flag_as_unresolved(
    db: Session,
    entity_id: str,
    reason: str,
    user_id: str
) -> Entity:
    """
    Flag an entity as unresolved/ambiguous for human review.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise ValueError("Entity not found")
    
    attrs = entity.attributes or {}
    attrs["resolution_status"] = "unresolved"
    attrs["resolution_reason"] = reason
    attrs["flagged_by"] = user_id
    attrs["flagged_at"] = datetime.now(timezone.utc).isoformat()
    entity.attributes = attrs
    
    # Reduce confidence
    entity.confidence_score = max(0.1, entity.confidence_score - 0.3)
    
    # Audit log
    audit_log = AuditLog(
        user_id=user_id,
        action="entity_flagged_unresolved",
        resource_type="entity",
        resource_id=entity_id,
        details={
            "reason": reason,
            "previous_confidence": entity.confidence_score + 0.3,
            "new_confidence": entity.confidence_score,
        },
        timestamp=datetime.now(timezone.utc)
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(entity)
    return entity


def _deduplicate_relationships(db: Session, entity_id: str):
    """Remove duplicate relationships after merge."""
    from app.models.models import Relationship
    from sqlalchemy import or_
    
    rels = db.query(Relationship).filter(
        or_(
            Relationship.source_entity_id == entity_id,
            Relationship.target_entity_id == entity_id,
        )
    ).all()
    
    seen = {}
    for rel in rels:
        key = tuple(sorted([rel.source_entity_id, rel.target_entity_id]) + [rel.relationship_type.value])
        if key in seen:
            # Keep the one with higher weight
            if rel.weight > seen[key].weight:
                db.delete(seen[key])
                seen[key] = rel
            else:
                db.delete(rel)
        else:
            seen[key] = rel


def split_entities(
    db: Session,
    primary_entity_id: str,
    secondary_entity_id: str,
    user_id: str,
) -> Entity:
    """
    Split a previously merged entity.
    """
    secondary = db.query(Entity).filter(Entity.id == secondary_entity_id).first()
    if not secondary:
        raise ValueError("Entity not found")
    if secondary.is_merged_into != primary_entity_id:
        raise ValueError("Entity was not merged into the specified primary")
    
    # Audit the split
    audit_log = AuditLog(
        user_id=user_id,
        action="entity_split",
        resource_type="entity",
        resource_id=secondary_entity_id,
        details={
            "split_from_entity_id": primary_entity_id,
            "split_from_entity_name": secondary.name,
        },
        timestamp=datetime.now(timezone.utc)
    )
    db.add(audit_log)
    
    secondary.is_merged_into = None
    # Remove the alias that was added during merge
    if secondary.name in (secondary.aliases or []):
        secondary.aliases = [a for a in secondary.aliases if a != secondary.name]
    
    db.commit()
    db.refresh(secondary)
    return secondary


def get_resolution_audit_log(
    db: Session,
    entity_id: str = None,
    limit: int = 50
) -> list[dict]:
    """
    Get audit log of resolution decisions (merge/split/flag).
    """
    query = db.query(AuditLog).filter(
        AuditLog.action.in_(["entity_merge", "entity_split", "entity_flagged_unresolved"])
    )
    
    if entity_id:
        query = query.filter(
            AuditLog.resource_id == entity_id
        )
    
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": log.id,
            "action": log.action,
            "resource_id": log.resource_id,
            "details": log.details,
            "user_id": log.user_id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]
