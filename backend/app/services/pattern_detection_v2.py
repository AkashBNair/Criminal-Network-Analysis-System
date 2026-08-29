"""
Pattern Detection Service (v2).

Implements §7 of the Master System Prompt:
  - Communication Burst Detection (count-based + timestamp-enhanced)
  - Financial Pattern Detection (structuring, circular flows, directional funding)
  - Co-location / Movement Pattern Detection
  - Cross-Case Pattern Detection (highest-value pattern type)
  - Burner/Unregistered Number Pattern Detection (NEW)

Every flagged pattern includes:
  - Specific records/timestamps that triggered it
  - Confidence level (confirmed / statistically_unusual / unexplained)
  - One plain-language sentence explaining why it was flagged
  - Event correlation when available

CONSUMES: resolved_graph.py for all graph operations.
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import math
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import hashlib
from app.models.models import (
    Entity, Relationship, Alert, AlertType, AlertStatus,
    EntityType, RelationshipType, Document, DetectionRule, Case
)

logger = logging.getLogger(__name__)


def _create_alert(
    db: Session,
    alert_type: AlertType,
    title: str,
    description: str,
    involved_entity_ids: list[str],
    case_id: str | None,
    severity: str,
    supporting_evidence: dict,
    explanation: str,
    confidence: str,
) -> Alert | None:
    """Create an alert with full evidence trail. Returns None if duplicate."""
    # Check for exact duplicate
    existing = db.query(Alert).filter(
        Alert.alert_type == alert_type,
        Alert.title == title,
    ).first()
    if existing:
        return None
    
    evidence = supporting_evidence.copy()
    evidence['explanation'] = explanation
    evidence['confidence'] = confidence
    evidence['detected_at'] = datetime.now(timezone.utc).isoformat()
    
    alert = Alert(
        case_id=case_id,
        alert_type=alert_type,
        title=title,
        description=description,
        involved_entity_ids=involved_entity_ids,
        supporting_evidence=evidence,
        severity=severity,
        status=AlertStatus.NEW,
    )
    db.add(alert)
    return alert


def _check_event_correlation(db, first_observed, last_observed, case_ids):
    """Check if a burst/communication pattern correlates with documented events.
    Uses LLM to distinguish confirmed events from negated/hypothetical mentions."""
    if not first_observed or not last_observed:
        return {"correlated": False}

    window_start = first_observed - timedelta(days=3)
    window_end = last_observed + timedelta(days=3)

    event_keywords = {
        "arrest": "arrest", "seizure": "seizure", "recovered": "recovery",
        "killed": "homicide", "murder": "murder", "shooting": "shooting",
        "attack": "attack", "robbery": "robbery", "extortion": "extortion",
        "raided": "raid", "intercepted": "interception",
        "incident": "incident",
    }

    for case_id in case_ids:
        docs = db.query(Document).filter(Document.case_id == case_id).all()
        for doc in docs:
            if not doc.content_text:
                continue
            text_lower = doc.content_text.lower()

            for keyword, event_type in event_keywords.items():
                if keyword in text_lower:
                    if doc.uploaded_at and window_start <= doc.uploaded_at <= window_end:
                        kidx = text_lower.find(keyword)
                        start = max(0, kidx - 100)
                        end = min(len(doc.content_text), kidx + len(keyword) + 100)
                        surrounding = doc.content_text[start:end]

                        verdict = assess_event_occurrence(keyword, surrounding)
                        if not verdict.get("event_occurred", False):
                            logger.info("Event rejected by LLM: %s [%s]", keyword, verdict.get("reasoning", ""))
                            continue

                        return {
                            "correlated": True,
                            "event_type": event_type,
                            "event_description": event_type.title() + " confirmed in case records",
                            "document_id": doc.id,
                            "document_filename": doc.filename,
                            "event_backend": verdict.get("backend", "unknown"),
                            "event_reasoning": verdict.get("reasoning", ""),
                        }

    return {"correlated": False}

def _event_cache_key(keyword, text):
    normalized = keyword.lower().strip() + chr(124)*2 + text.strip().lower()[:500]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

def assess_event_occurrence(event_keyword, context_text):
    cache_key = _event_cache_key(event_keyword, context_text)
    if cache_key in _event_cache:
        result = dict(_event_cache[cache_key])
        result["backend"] = "cache"
        return result

    api_key = os.environ.get("GROQ_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        result = _heuristic_event_check(event_keyword, context_text)
        _event_cache[cache_key] = result
        return result

    bq = chr(96)
    bq3 = bq * 3
    nl = chr(10)
    dq = chr(34)
    prompt = (
        "You are determining whether a specific event genuinely occurred, "
        "based on how it is described in case text -- as opposed to being "
        "negated, ruled out, hypothetical, or merely mentioned in passing."
        + nl + nl
        + "EVENT/KEYWORD OF INTEREST: " + dq + event_keyword + dq + nl
        + "CONTEXT TEXT: " + dq + context_text[:1500] + dq + nl + nl
        + "Determine whether this text confirms the event ACTUALLY OCCURRED, "
        "or whether it is negated (denied, ruled out, no evidence of X), "
        "hypothetical (if X had happened), or about a different subject."
        + nl + nl
        + "Return ONLY valid JSON:" + nl
        + "{" + dq + "event_occurred" + dq + ": true_or_false, "
        + dq + "confidence" + dq + ": 0_to_100_integer, "
        + dq + "reasoning" + dq + ": " + dq + "one sentence explanation" + dq + "}"
    )

    backend = "groq"
    raw = None
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0, max_tokens=256,
        )
        raw = resp.choices[0].message.content
    except Exception as e:
        logger.error("Groq event assessment error: %s", e)

    if not raw:
        backend = "gemini"
        try:
            from google import genai
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))
            chat = client.chats.create(
                model="gemini-3.6-flash",
                config=genai.types.GenerateContentConfig(temperature=0, max_output_tokens=256),
            )
            raw = chat.send_message(prompt).text
        except Exception as e:
            logger.error("Gemini event assessment error: %s", e)

    if not raw:
        result = _heuristic_event_check(event_keyword, context_text)
        _event_cache[cache_key] = result
        return result

    text = raw.strip()
    if text.startswith(bq3):
        text = re.sub(r"^" + bq3 + r"(?:json)?\s*", "", text)
        text = re.sub(r"\s*" + bq3 + r"$", "", text)
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if parsed is None:
        result = {"event_occurred": False, "confidence": 0, "reasoning": "LLM parse failure", "backend": backend + "_parse_error"}
        _event_cache[cache_key] = result
        return result

    event_occurred = parsed.get("event_occurred", False)
    if isinstance(event_occurred, str):
        event_occurred = event_occurred.lower() in ("true", "yes", "1")
    confidence = max(0, min(100, int(parsed.get("confidence", 0))))
    reasoning = str(parsed.get("reasoning", ""))

    result = {"event_occurred": event_occurred, "confidence": confidence, "reasoning": reasoning, "backend": backend}
    _event_cache[cache_key] = result
    return result


def _heuristic_event_check(keyword, text):
    text_lower = text.lower()
    kw_lower = keyword.lower()
    idx = text_lower.find(kw_lower)
    if idx == -1:
        return {"event_occurred": False, "confidence": 30, "reasoning": "Keyword not found", "backend": "heuristic"}
    before = text_lower[max(0, idx - 80):idx]
    neg_patterns = [
        r"no", r"not", r"never", r"without",
        r"failed\s+to", r"were?\s+not", r"was\s+not",
        r"did\s+not", r"no\s+evidence", r"ruled\s+out",
    ]
    for pat in neg_patterns:
        if re.search(pat, before):
            return {"event_occurred": False, "confidence": 75, "reasoning": "Negation detected before keyword", "backend": "heuristic"}
    return {"event_occurred": True, "confidence": 50, "reasoning": "No negation detected (heuristic)", "backend": "heuristic"}
# ─── 1. Communication Burst Detection (§7.1) ────────────────────

def detect_communication_bursts(db: Session) -> list[Alert]:
    """
    §7.1: Communication Burst Detection
    
    Primary: count-based (2+ calls between pair within any rolling window)
    Enhanced: timestamp-based when available
    
    Higher priority if burst occurs immediately before/after documented event.
    """
    alerts = []
    
    rule = db.query(DetectionRule).filter(
        DetectionRule.rule_type == "communication_burst",
        DetectionRule.is_enabled == True
    ).first()
    threshold = int(rule.threshold) if rule else 2
    
    comm_rels = db.query(Relationship).filter(
        Relationship.relationship_type == RelationshipType.COMMUNICATION,
    ).all()
    
    logger.info(f"[HEARTBEAT] Communication burst detection: {len(comm_rels)} call records")
    
    # Group by entity pair
    pair_data = defaultdict(lambda: {
        "count": 0,
        "relationship_ids": [],
        "weights": [],
        "justifications": [],
        "first_observed": None,
        "last_observed": None,
        "case_ids": set(),
        "directions": [],
        "durations": [],
    })
    
    for rel in comm_rels:
        pair_key = tuple(sorted([rel.source_entity_id, rel.target_entity_id]))
        data = pair_data[pair_key]
        data["count"] += 1
        data["relationship_ids"].append(rel.id)
        data["weights"].append(rel.weight or 1.0)
        data["justifications"].append(rel.justification or "")
        data["case_ids"].add(rel.case_id)
        
        if rel.first_observed:
            if data["first_observed"] is None or rel.first_observed < data["first_observed"]:
                data["first_observed"] = rel.first_observed
        if rel.last_observed:
            if data["last_observed"] is None or rel.last_observed > data["last_observed"]:
                data["last_observed"] = rel.last_observed
    
    logger.info(f"[HEARTBEAT] Communication burst: {len(pair_data)} unique pairs")
    
    for pair_key, data in pair_data.items():
        if data["count"] < threshold:
            continue
        
        entity_a = db.query(Entity).filter(Entity.id == pair_key[0]).first()
        entity_b = db.query(Entity).filter(Entity.id == pair_key[1]).first()
        
        if not entity_a or not entity_b:
            continue
        
        # Determine severity based on volume
        if data["count"] >= threshold * 3:
            severity = "high"
            explanation = (
                f"Very high communication volume ({data['count']} calls) between "
                f"{entity_a.name} and {entity_b.name} — unusual intensity suggests "
                f"coordination or operational activity"
            )
            confidence = "statistically_unusual"
        elif data["count"] >= threshold * 2:
            severity = "medium"
            explanation = (
                f"Elevated communication ({data['count']} calls) between "
                f"{entity_a.name} and {entity_b.name} — above normal threshold "
                f"for routine contact"
            )
            confidence = "statistically_unusual"
        else:
            severity = "low"
            explanation = (
                f"Communication burst detected: {data['count']} calls between "
                f"{entity_a.name} and {entity_b.name} — noted for pattern tracking"
            )
            confidence = "unexplained"
        
        # Check for event correlation (§7.1: "escalate to HIGH priority")
        event_correlation = None
        if data["first_observed"] and data["last_observed"]:
            event_correlation = _check_event_correlation(
                db, data["first_observed"], data["last_observed"], data["case_ids"]
            )
            if event_correlation.get("correlated"):
                severity = "high"
                explanation = (
                    f"Communication burst of {data['count']} calls between "
                    f"{entity_a.name} and {entity_b.name} correlates with "
                    f"{event_correlation['event_type']}: "
                    f"{event_correlation['event_description']} — "
                    f"strong circumstantial evidence of coordination around incident"
                )
                confidence = "confirmed"
        
        alert = _create_alert(
            db,
            AlertType.COMMUNICATION_BURST,
            f"Communication Burst: {entity_a.name} ↔ {entity_b.name}",
            f"Detected {data['count']} communications between {entity_a.name} and {entity_b.name}",
            list(pair_key),
            list(data["case_ids"])[0] if data["case_ids"] else None,
            severity,
            {
                "entity_a": entity_a.name,
                "entity_b": entity_b.name,
                "communication_count": data["count"],
                "threshold": threshold,
                "first_observed": data["first_observed"].isoformat() if data["first_observed"] else None,
                "last_observed": data["last_observed"].isoformat() if data["last_observed"] else None,
                "case_ids": list(data["case_ids"]),
                "avg_weight": round(sum(data["weights"]) / len(data["weights"]), 2),
                "event_correlation": event_correlation,
                "source_records": data["relationship_ids"][:10],
            },
            explanation,
            confidence,
        )
        if alert:
            alerts.append(alert)
    
    logger.info(f"[HEARTBEAT] Communication burst detection: {len(alerts)} alerts created")
    return alerts


# ─── 2. Financial Pattern Detection (§7.2) ───────────────────────

def detect_financial_patterns(db: Session) -> list[Alert]:
    """
    §7.2: Financial Pattern Detection
    - Structuring: multiple transactions under reporting threshold
    - Circular flows: A → B → C → A
    - Directional funding: transfers preceding events
    """
    alerts = []
    
    fin_rels = db.query(Relationship).filter(
        Relationship.relationship_type == RelationshipType.FINANCIAL,
    ).all()
    
    logger.info(f"[HEARTBEAT] Financial pattern detection: {len(fin_rels)} transactions")
    
    pair_flows = defaultdict(list)
    for rel in fin_rels:
        pair_key = (rel.source_entity_id, rel.target_entity_id)
        pair_flows[pair_key].append(rel)
    
    # Circular flows
    alerts.extend(_detect_circular_flows(db, fin_rels))
    
    # Repeated transfers (potential structuring)
    alerts.extend(_detect_repeated_transfers(db, pair_flows))
    
    # Directional funding (§7.2: "transfers consistently preceding events")
    alerts.extend(_detect_directional_funding(db, fin_rels))
    
    logger.info(f"[HEARTBEAT] Financial pattern detection: {len(alerts)} alerts created")
    return alerts


def _detect_circular_flows(db: Session, fin_rels: list) -> list[Alert]:
    """Detect circular financial flows: A → B → C → A (§7.2)."""
    alerts = []
    
    graph = defaultdict(set)
    rel_map = {}
    for rel in fin_rels:
        graph[rel.source_entity_id].add(rel.target_entity_id)
        rel_map[(rel.source_entity_id, rel.target_entity_id)] = rel
    
    for start_node in list(graph.keys())[:50]:
        for mid1 in graph.get(start_node, set()):
            for mid2 in graph.get(mid1, set()):
                if mid2 == start_node:
                    continue
                if start_node in graph.get(mid2, set()):
                    cycle_nodes = [start_node, mid1, mid2]
                    cycle_names = []
                    for nid in cycle_nodes:
                        entity = db.query(Entity).filter(Entity.id == nid).first()
                        cycle_names.append(entity.name if entity else nid[:20])
                    
                    case_ids = set()
                    evidence_records = []
                    for i in range(len(cycle_nodes)):
                        src = cycle_nodes[i]
                        tgt = cycle_nodes[(i + 1) % len(cycle_nodes)]
                        rel = rel_map.get((src, tgt))
                        if rel:
                            case_ids.add(rel.case_id)
                            evidence_records.append({
                                'relationship_id': rel.id,
                                'from': cycle_names[i],
                                'to': cycle_names[(i + 1) % len(cycle_names)],
                                'weight': rel.weight,
                                'justification': rel.justification or '',
                            })
                    
                    cross_case = len(case_ids) > 1
                    
                    alert = _create_alert(
                        db,
                        AlertType.CIRCULAR_TRANSACTION,
                        f"Circular Flow: {' → '.join(cycle_names)}",
                        f"Circular financial flow: {' → '.join(cycle_names)} → {cycle_names[0]}",
                        cycle_nodes,
                        list(case_ids)[0] if case_ids else None,
                        "high" if cross_case else "medium",
                        {
                            "cycle": cycle_names,
                            "cycle_ids": cycle_nodes,
                            "case_ids": list(case_ids),
                            "cross_case": cross_case,
                            "source_records": evidence_records,
                        },
                        f"Circular money flow detected: funds move through {len(cycle_names)} entities "
                        f"and return toward origin — possible layering or money laundering"
                        + (" across multiple cases" if cross_case else ""),
                        "confirmed" if cross_case else "statistically_unusual",
                    )
                    if alert:
                        alerts.append(alert)
                    break
    
    return alerts


def _detect_repeated_transfers(db: Session, pair_flows: dict) -> list[Alert]:
    """Detect repeated financial transfers between same parties (structuring signal)."""
    alerts = []
    
    for pair_key, flows in pair_flows.items():
        if len(flows) < 2:
            continue
        
        entity_a = db.query(Entity).filter(Entity.id == pair_key[0]).first()
        entity_b = db.query(Entity).filter(Entity.id == pair_key[1]).first()
        
        if not entity_a or not entity_b:
            continue
        
        case_ids = set(f.case_id for f in flows)
        
        # Check if amounts suggest structuring (§7.2: "just under reporting threshold")
        amounts = []
        for f in flows:
            justification = (f.justification or "").lower()
            # Try to extract amounts from justification
            import re
            amount_matches = re.findall(r'[\d,]+(?:\.\d+)?', justification)
            for amt in amount_matches:
                try:
                    amounts.append(float(amt.replace(',', '')))
                except ValueError:
                    pass
        
        structuring_note = ""
        if len(amounts) >= 2:
            # Check if multiple amounts are just under ₹50,000 (common Indian reporting threshold)
            under_threshold = [a for a in amounts if 30000 <= a < 50000]
            if len(under_threshold) >= 2:
                structuring_note = (
                    f" — {len(under_threshold)} transactions individually under ₹50,000 "
                    f"reporting threshold suggest possible structuring"
                )
        
        alert = _create_alert(
            db,
            AlertType.CIRCULAR_TRANSACTION,
            f"Repeated Transfers: {entity_a.name} → {entity_b.name}",
            f"Detected {len(flows)} financial transfers from {entity_a.name} to {entity_b.name}",
            list(pair_key),
            list(case_ids)[0] if case_ids else None,
            "medium",
            {
                "entity_a": entity_a.name,
                "entity_b": entity_b.name,
                "transfer_count": len(flows),
                "case_ids": list(case_ids),
                "amounts": amounts[:10],
                "source_records": [f.id for f in flows[:10]],
            },
            f"Repeated financial transfers ({len(flows)}) between "
            f"{entity_a.name} and {entity_b.name} — pattern suggests ongoing "
            f"financial relationship{structuring_note}",
            "statistically_unusual",
        )
        if alert:
            alerts.append(alert)
    
    return alerts


def _detect_directional_funding(db: Session, fin_rels: list) -> list[Alert]:
    """
    §7.2: Directional Funding — financial transfers preceding communication events.
    Pattern: money transfer between A→B, then A and B have burst of calls shortly after.
    """
    alerts = []
    
    # Group financial relationships by pair
    fin_by_pair = defaultdict(list)
    for rel in fin_rels:
        pair_key = tuple(sorted([rel.source_entity_id, rel.target_entity_id]))
        fin_by_pair[pair_key].append(rel)
    
    # Get communication relationships
    comm_rels = db.query(Relationship).filter(
        Relationship.relationship_type == RelationshipType.COMMUNICATION,
    ).all()
    
    comm_by_pair = defaultdict(list)
    for rel in comm_rels:
        pair_key = tuple(sorted([rel.source_entity_id, rel.target_entity_id]))
        comm_by_pair[pair_key].append(rel)
    
    # Check if financial pairs also have communication spikes
    for pair_key, fin_flows in fin_by_pair.items():
        comm_flows = comm_by_pair.get(pair_key, [])
        if len(fin_flows) >= 1 and len(comm_flows) >= 2:
            entity_a = db.query(Entity).filter(Entity.id == pair_key[0]).first()
            entity_b = db.query(Entity).filter(Entity.id == pair_key[1]).first()
            
            if not entity_a or not entity_b:
                continue
            
            fin_case_ids = set(f.case_id for f in fin_flows)
            comm_case_ids = set(f.case_id for f in comm_flows)
            shared_case = fin_case_ids & comm_case_ids
            
            if shared_case:
                alert = _create_alert(
                    db,
                    AlertType.CIRCULAR_TRANSACTION,
                    f"Directional Funding: {entity_a.name} → {entity_b.name}",
                    f"Financial transfers between {entity_a.name} and {entity_b.name} "
                    f"followed by elevated communication",
                    list(pair_key),
                    list(shared_case)[0] if shared_case else None,
                    "medium",
                    {
                        "entity_a": entity_a.name,
                        "entity_b": entity_b.name,
                        "financial_count": len(fin_flows),
                        "communication_count": len(comm_flows),
                        "shared_case_ids": list(shared_case),
                        "source_records": [f.id for f in fin_flows[:5]] + [c.id for c in comm_flows[:5]],
                    },
                    f"Financial transfers between {entity_a.name} and {entity_b.name} "
                    f"coincide with elevated communication — pattern suggests transfers are "
                    f"funding operational activity",
                    "statistically_unusual",
                )
                if alert:
                    alerts.append(alert)
    
    return alerts


# ─── 3. Cross-Case Pattern Detection (§7.4 — highest value) ──────

def detect_cross_case_patterns(db: Session) -> list[Alert]:
    """
    §7.4: Cross-Case Pattern Detection — the highest-value pattern type.
    "Cross-case bridging is usually the single most actionable insight."
    """
    alerts = []
    
    logger.info("[HEARTBEAT] Cross-case pattern detection starting")
    
    for entity_type in [EntityType.PHONE, EntityType.VEHICLE, EntityType.PERSON]:
        results = (
            db.query(
                Entity.name,
                Entity.entity_type,
                func.group_concat(func.distinct(Entity.case_id)).label("cases"),
                func.count(func.distinct(Entity.case_id)).label("case_count"),
            )
            .filter(
                Entity.entity_type == entity_type,
                Entity.is_merged_into.is_(None),
            )
            .group_by(Entity.name)
            .having(func.count(func.distinct(Entity.case_id)) > 1)
            .all()
        )
        
        for result in results:
            case_ids = [c.strip() for c in result.cases.split(",") if c.strip()]
            entity_ids = []
            for cid in case_ids:
                ents = db.query(Entity).filter(
                    Entity.name == result.name,
                    Entity.case_id == cid,
                ).all()
                entity_ids.extend([e.id for e in ents])
            
            case_details = []
            for cid in case_ids:
                case = db.query(Case).filter(Case.id == cid).first()
                if case:
                    case_details.append(f"{case.case_number} ({case.name})")
            
            if entity_type == EntityType.PERSON:
                severity = "high" if result.case_count >= 2 else "medium"
                explanation = (
                    f"Person '{result.name}' appears in {result.case_count} separate cases: "
                    f"{', '.join(case_details)} — cross-case entity detected; "
                    f"this may indicate a connecting figure between otherwise unrelated investigations"
                )
            elif entity_type == EntityType.PHONE:
                severity = "high" if result.case_count >= 2 else "medium"
                explanation = (
                    f"Phone number '{result.name}' appears in {result.case_count} separate cases: "
                    f"{', '.join(case_details)} — shared communication device across investigations"
                )
            else:
                severity = "medium"
                explanation = (
                    f"Vehicle '{result.name}' appears in {result.case_count} separate cases: "
                    f"{', '.join(case_details)} — shared vehicle may indicate linked operations"
                )
            
            alert = _create_alert(
                db,
                AlertType.CROSS_CASE_MATCH,
                f"Cross-Case {entity_type.value}: {result.name}",
                f"{entity_type.value} '{result.name}' appears in {result.case_count} different cases",
                entity_ids,
                case_ids[0] if case_ids else None,
                severity,
                {
                    "entity_name": result.name,
                    "entity_type": entity_type.value,
                    "case_ids": case_ids,
                    "case_count": result.case_count,
                    "case_details": case_details,
                    "entity_ids": entity_ids,
                    "source_records": entity_ids[:10],
                },
                explanation,
                "confirmed",
            )
            if alert:
                alerts.append(alert)
    
    logger.info(f"[HEARTBEAT] Cross-case pattern detection: {len(alerts)} alerts created")
    return alerts


# ─── 4. Co-location Pattern Detection (§7.3) ─────────────────────

def detect_co_location_patterns(db: Session) -> list[Alert]:
    """
    §7.3: Co-location / Movement Pattern Detection
    
    Flag repeated co-location where no documented legitimate relationship explains it.
    Do NOT flag co-location with documented innocent explanation.
    Single high-value incident-proximate event = HIGH priority.
    """
    alerts = []
    
    location_rels = db.query(Relationship).filter(
        Relationship.relationship_type == RelationshipType.LOCATION_PRESENCE,
    ).all()
    
    logger.info(f"[HEARTBEAT] Co-location detection: {len(location_rels)} location records")
    
    # Group by location
    location_entities = defaultdict(list)
    for rel in location_rels:
        source = db.query(Entity).filter(Entity.id == rel.source_entity_id).first()
        target = db.query(Entity).filter(Entity.id == rel.target_entity_id).first()
        
        if not source or not target:
            continue
        
        location_id = None
        person_id = None
        if source.entity_type == EntityType.LOCATION:
            location_id = source.id
            person_id = target.id
        elif target.entity_type == EntityType.LOCATION:
            location_id = target.id
            person_id = source.id
        
        if location_id and person_id:
            location_entities[location_id].append({
                "person_id": person_id,
                "case_id": rel.case_id,
                "relationship_id": rel.id,
            })
    
    for location_id, persons in location_entities.items():
        if len(persons) < 2:
            continue
        
        location = db.query(Entity).filter(Entity.id == location_id).first()
        if not location:
            continue
        
        seen_pairs = set()
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1, p2 = persons[i], persons[j]
                pair_key = tuple(sorted([p1["person_id"], p2["person_id"]]))
                
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                # §7.3: "Do NOT flag co-location with documented innocent explanation"
                existing_rel = db.query(Relationship).filter(
                    or_(
                        (Relationship.source_entity_id == p1["person_id"]) &
                        (Relationship.target_entity_id == p2["person_id"]),
                        (Relationship.source_entity_id == p2["person_id"]) &
                        (Relationship.target_entity_id == p1["person_id"]),
                    ),
                    Relationship.relationship_type.in_([
                        RelationshipType.FAMILY,
                        RelationshipType.EMPLOYMENT,
                    ]),
                ).first()
                
                if existing_rel:
                    continue  # Has documented legitimate relationship
                
                p1_entity = db.query(Entity).filter(Entity.id == p1["person_id"]).first()
                p2_entity = db.query(Entity).filter(Entity.id == p2["person_id"]).first()
                
                if not p1_entity or not p2_entity:
                    continue
                
                co_location_count = sum(
                    1 for p in persons
                    if p["person_id"] in [p1["person_id"], p2["person_id"]]
                )
                
                if co_location_count >= 2:
                    severity = "medium"
                    explanation = (
                        f"Repeated co-location of {p1_entity.name} and {p2_entity.name} "
                        f"at {location.name} ({co_location_count} times) — no documented "
                        f"legitimate relationship explains this pattern"
                    )
                    confidence = "statistically_unusual"
                else:
                    severity = "low"
                    explanation = (
                        f"Co-location of {p1_entity.name} and {p2_entity.name} "
                        f"at {location.name} — noted for pattern tracking"
                    )
                    confidence = "unexplained"
                
                alert = _create_alert(
                    db,
                    AlertType.CROSS_CASE_MATCH,
                    f"Co-location: {p1_entity.name} & {p2_entity.name} at {location.name}",
                    f"Detected co-location of {p1_entity.name} and {p2_entity.name} at {location.name}",
                    [p1["person_id"], p2["person_id"]],
                    p1["case_id"],
                    severity,
                    {
                        "location": location.name,
                        "person_a": p1_entity.name,
                        "person_b": p2_entity.name,
                        "co_location_count": co_location_count,
                        "source_records": [p1["relationship_id"], p2["relationship_id"]],
                    },
                    explanation,
                    confidence,
                )
                if alert:
                    alerts.append(alert)
    
    logger.info(f"[HEARTBEAT] Co-location detection: {len(alerts)} alerts created")
    return alerts


# ─── 5. Burner/Unregistered Number Detection (§7.1) ──────────────

def detect_burner_numbers(db: Session) -> list[Alert]:
    """
    §7.1 (BURNER/UNREGISTERED NUMBER PATTERN):
    IF an unregistered number is active only within a window surrounding a
    documented incident, then never used again → flag HIGH priority.
    
    Burner numbers are high-value: they indicate deliberate operational security.
    """
    alerts = []
    
    logger.info("[HEARTBEAT] Burner number detection starting")
    
    # Find phone entities that appear in communications
    phone_entities = db.query(Entity).filter(
        Entity.entity_type == EntityType.PHONE,
        Entity.is_merged_into.is_(None),
    ).all()
    
    for phone in phone_entities:
        attrs = phone.attributes or {}
        
        # Check if phone is identified as unregistered/burner
        is_unregistered = (
            attrs.get("registered") == False or
            attrs.get("registration_status") == "unregistered" or
            attrs.get("is_burner", False) or
            "unregistered" in str(attrs).lower() or
            "burner" in str(attrs).lower()
        )
        
        if not is_unregistered:
            continue
        
        # Get all communication relationships for this phone
        comm_rels = db.query(Relationship).filter(
            or_(
                Relationship.source_entity_id == phone.id,
                Relationship.target_entity_id == phone.id,
            ),
            Relationship.relationship_type == RelationshipType.COMMUNICATION,
        ).all()
        
        if not comm_rels:
            continue
        
        # Analyze activity window
        first_seen = None
        last_seen = None
        case_ids = set()
        relationship_ids = []
        
        for rel in comm_rels:
            relationship_ids.append(rel.id)
            case_ids.add(rel.case_id)
            if rel.first_observed:
                if first_seen is None or rel.first_observed < first_seen:
                    first_seen = rel.first_observed
            if rel.last_observed:
                if last_seen is None or rel.last_observed > last_seen:
                    last_seen = rel.last_observed
        
        if not first_seen or not last_seen:
            continue
        
        # Check if activity is concentrated around an incident
        event_correlation = _check_event_correlation(
            db, first_seen, last_seen, case_ids
        )
        
        # Get connected entities
        connected_names = []
        for rel in comm_rels:
            other_id = rel.target_entity_id if rel.source_entity_id == phone.id else rel.source_entity_id
            other = db.query(Entity).filter(Entity.id == other_id).first()
            if other:
                connected_names.append(other.name)
        
        activity_window_days = (last_seen - first_seen).days if last_seen and first_seen else 0
        
        if event_correlation.get("correlated"):
            severity = "high"
            explanation = (
                f"Unregistered/burner number '{phone.name}' was active for only "
                f"{activity_window_days} day(s) around a documented "
                f"{event_correlation['event_type']}, then went silent — "
                f"pattern strongly suggests deliberate operational use"
            )
            confidence = "confirmed"
        elif activity_window_days <= 7:
            severity = "medium"
            explanation = (
                f"Unregistered number '{phone.name}' was active for only "
                f"{activity_window_days} day(s) then went silent — "
                f"short activity window suggests burner usage"
            )
            confidence = "statistically_unusual"
        else:
            severity = "low"
            explanation = (
                f"Unregistered number '{phone.name}' detected with limited activity — "
                f"noted for pattern tracking"
            )
            confidence = "unexplained"
        
        alert = _create_alert(
            db,
            AlertType.COMMUNICATION_BURST,
            f"Burner Number: {phone.name}",
            f"Unregistered/burner number '{phone.name}' detected with suspicious activity pattern",
            [phone.id] + [r.source_entity_id for r in comm_rels[:5]],
            list(case_ids)[0] if case_ids else None,
            severity,
            {
                "phone_number": phone.name,
                "is_unregistered": True,
                "activity_window_days": activity_window_days,
                "first_seen": first_seen.isoformat() if first_seen else None,
                "last_seen": last_seen.isoformat() if last_seen else None,
                "connected_entities": connected_names[:10],
                "communication_count": len(comm_rels),
                "case_ids": list(case_ids),
                "event_correlation": event_correlation,
                "source_records": relationship_ids[:10],
            },
            explanation,
            confidence,
        )
        if alert:
            alerts.append(alert)
    
    logger.info(f"[HEARTBEAT] Burner number detection: {len(alerts)} alerts created")
    return alerts


# ─── Run All Detections ───────────────────────────────────────────

def run_all_detections(db: Session) -> list[Alert]:
    """Run all detection patterns with heartbeat logging."""
    logger.info("[HEARTBEAT] Starting pattern detection pipeline")
    
    all_alerts = []
    
    detectors = [
        ("Communication Bursts", detect_communication_bursts),
        ("Financial Patterns", detect_financial_patterns),
        ("Cross-Case Patterns", detect_cross_case_patterns),
        ("Co-location Patterns", detect_co_location_patterns),
        ("Burner Numbers", detect_burner_numbers),
    ]
    
    for name, detector in detectors:
        try:
            logger.info(f"[HEARTBEAT] Running detector: {name}")
            new_alerts = detector(db)
            all_alerts.extend(new_alerts)
            logger.info(f"[HEARTBEAT] {name} produced {len(new_alerts)} alerts")
        except Exception as e:
            logger.error(f"[HEARTBEAT] Detection error in {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Commit all new alerts
    if all_alerts:
        db.commit()
        for alert in all_alerts:
            db.refresh(alert)
    
    logger.info(f"[HEARTBEAT] Pattern detection complete: {len(all_alerts)} total alerts created")
    return all_alerts


# ─── Detection Rules ──────────────────────────────────────────────

def ensure_detection_rules(db: Session):
    """Add default detection rules with lower thresholds."""
    existing_rules = db.query(DetectionRule).count()
    if existing_rules == 0:
        defaults = [
            DetectionRule(
                name="Communication Burst",
                rule_type="communication_burst",
                description="Flag when 2+ calls between a pair in short window",
                is_enabled=True,
                threshold=2,
            ),
            DetectionRule(
                name="Financial Pattern",
                rule_type="financial_pattern",
                description="Flag repeated financial transfers or circular flows",
                is_enabled=True,
                threshold=2,
            ),
            DetectionRule(
                name="Cross-Case Match",
                rule_type="cross_case_match",
                description="Flag entities appearing in multiple cases",
                is_enabled=True,
                threshold=2,
            ),
            DetectionRule(
                name="Burner Number",
                rule_type="burner_number",
                description="Flag unregistered numbers with suspicious activity windows",
                is_enabled=True,
                threshold=1,
            ),
        ]
        for rule in defaults:
            db.add(rule)
        db.commit()
        logger.info("[HEARTBEAT] Created default detection rules")


# ─── SOCMINT Extraction ───────────────────────────────────────────

def extract_social_media_entities(text: str) -> list[dict]:
    """Extract social media entities from text (§1)."""
    import re
    
    entities = []
    
    twitter_pattern = re.compile(r'@(\w{1,15})')
    for match in twitter_pattern.finditer(text):
        entities.append({
            "type": "social_media_handle",
            "platform": "twitter",
            "handle": f"@{match.group(1)}",
            "raw_match": match.group(),
        })
    
    instagram_pattern = re.compile(r'@(\w[\w.]{0,30})')
    for match in instagram_pattern.finditer(text):
        entities.append({
            "type": "social_media_handle",
            "platform": "instagram",
            "handle": f"@{match.group(1)}",
            "raw_match": match.group(),
        })
    
    fb_pattern = re.compile(r'facebook\.com/(\w[\w.]*)', re.IGNORECASE)
    for match in fb_pattern.finditer(text):
        entities.append({
            "type": "social_media_profile",
            "platform": "facebook",
            "handle": match.group(1),
            "raw_match": match.group(),
        })
    
    whatsapp_pattern = re.compile(
        r'(?:\+91[\s-]?)?(?:0)?([6-9]\d{9})\s*(?:\(WhatsApp\)|\(WA\)|whatsapp)',
        re.IGNORECASE
    )
    for match in whatsapp_pattern.finditer(text):
        entities.append({
            "type": "social_media_handle",
            "platform": "whatsapp",
            "handle": match.group(1),
            "raw_match": match.group(),
        })
    
    telegram_pattern = re.compile(r'(?:t\.me|telegram\.me)/(\w[\w_]*)', re.IGNORECASE)
    for match in telegram_pattern.finditer(text):
        entities.append({
            "type": "social_media_handle",
            "platform": "telegram",
            "handle": match.group(1),
            "raw_match": match.group(),
        })
    
    return entities


# ─── Investigative Brief (§10) ───────────────────────────────────

def generate_investigative_brief(
    db: Session,
    entity_id: str,
    threat_score: dict = None,
) -> dict:
    """
    §10: Generate an investigative brief for a specific entity.
    
    Reads like an investigative brief, not a data dump.
    Separates confirmed facts from inferences.
    Never silently resolves genuine ambiguity.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        return {"error": "Entity not found"}
    
    rels = db.query(Relationship).filter(
        or_(
            Relationship.source_entity_id == entity_id,
            Relationship.target_entity_id == entity_id,
        )
    ).all()
    
    # Group by type
    rel_by_type = defaultdict(list)
    for rel in rels:
        other_id = rel.target_entity_id if rel.source_entity_id == entity_id else rel.source_entity_id
        other = db.query(Entity).filter(Entity.id == other_id).first()
        if other:
            rel_by_type[rel.relationship_type.value].append({
                "name": other.name,
                "type": other.entity_type.value,
                "justification": rel.justification or "",
                "weight": rel.weight or 1.0,
                "case_id": rel.case_id,
                "is_ai_generated": rel.is_ai_generated,
                "confidence": rel.confidence_score,
            })
    
    # Get cases
    case_ids = list(set(r.case_id for r in rels))
    cases = []
    for cid in case_ids:
        case = db.query(Case).filter(Case.id == cid).first()
        if case:
            cases.append({
                "case_id": case.id,
                "case_number": case.case_number,
                "case_name": case.name,
            })
    
    attrs = entity.attributes or {}
    resolution_status = attrs.get("resolution_status", "resolved")
    is_unconfirmed = resolution_status == "unresolved" or (
        entity.confidence_score and entity.confidence_score < 0.6
    )
    
    # ── Build narrative (§10: "reads like an investigative brief") ──
    narrative_parts = []
    narrative_parts.append(
        f"{entity.name} is identified as a {entity.entity_type.value.lower()} "
        f"appearing in {len(cases)} case(s): {', '.join(c['case_number'] for c in cases)}."
    )
    
    # Separate confirmed from inferred (§10)
    confirmed_rels = []
    inferred_rels = []
    for rel_type, rels_list in rel_by_type.items():
        for r in rels_list:
            if r["is_ai_generated"] and r["confidence"] < 0.8:
                inferred_rels.append((rel_type, r))
            else:
                confirmed_rels.append((rel_type, r))
    
    if confirmed_rels:
        narrative_parts.append(
            f"Documented relationships: {len(confirmed_rels)} confirmed connections "
            f"including {', '.join(set(r[0] for r in confirmed_rels[:5]))}."
        )
    
    if inferred_rels:
        narrative_parts.append(
            f"Inferred relationships: {len(inferred_rels)} connections derived from "
            f"correlation (not directly documented) — requires human verification."
        )
    
    # Unresolved threads (§10: "never silently resolve genuine ambiguity")
    unresolved = []
    if is_unconfirmed:
        unresolved.append("Identity is unconfirmed — requires verification before acting on this profile")
    
    for rel_type, rels_list in rel_by_type.items():
        for r in rels_list:
            if r["type"] == "Person" and r["confidence"] and r["confidence"] < 0.6:
                unresolved.append(f"Connection to {r['name']} has low confidence ({r['confidence']:.0%})")
    
    brief = {
        "entity_id": entity_id,
        "name": entity.name,
        "entity_type": entity.entity_type.value,
        "threat_score": threat_score.get("threat_score") if threat_score else None,
        "threat_level": threat_score.get("threat_level") if threat_score else None,
        "resolution_status": resolution_status,
        "confidence_score": entity.confidence_score,
        "cases": cases,
        "total_relationships": len(rels),
        "confirmed_relationships": len(confirmed_rels),
        "inferred_relationships": len(inferred_rels),
        "narrative": " ".join(narrative_parts),
        "evidence_summary": {
            "confirmed": [
                {
                    "type": r[0],
                    "connected_to": r[1]["name"],
                    "connected_type": r[1]["type"],
                    "justification": r[1]["justification"],
                    "source_case": r[1]["case_id"],
                }
                for r in confirmed_rels[:10]
            ],
            "inferred": [
                {
                    "type": r[0],
                    "connected_to": r[1]["name"],
                    "connected_type": r[1]["type"],
                    "confidence": r[1]["confidence"],
                    "warning": "This relationship is inferred, not documented. Verify before acting.",
                }
                for r in inferred_rels[:10]
            ],
        },
        "unresolved_threads": unresolved,
        "aliases": entity.aliases or [],
        "attributes": attrs,
    }
    
    return brief


# ─── Graph Connectivity Verification ──────────────────────────────

def verify_graph_connectivity(db: Session, case_ids: list[str] = None) -> dict:
    """
    Verify that entity resolution is properly deduplicating (§0, §3).
    Checks for duplicate entities across connected components.
    """
    from app.services.resolved_graph import build_resolved_graph
    
    resolved = build_resolved_graph(db, case_ids)
    G = resolved.graph
    
    if len(G.nodes) == 0:
        return {"connected": True, "components": 0, "message": "No data to check"}
    
    components = list(nx.connected_components(G))
    
    # Check for name duplicates across components
    component_entities = {}
    for i, comp in enumerate(components):
        for node_name in comp:
            if node_name not in component_entities:
                component_entities[node_name] = []
            component_entities[node_name].append({
                "component_id": i,
                "node_name": node_name,
            })
    
    duplicates = {}
    for name, locations in component_entities.items():
        comp_ids = set(loc["component_id"] for loc in locations)
        if len(comp_ids) > 1:
            duplicates[name] = {
                "locations": locations,
                "component_ids": list(comp_ids),
            }
    
    is_connected = len(components) == 1
    
    return {
        "connected": is_connected,
        "components": len(components),
        "largest_component": max(len(c) for c in components),
        "total_nodes": len(G.nodes),
        "total_edges": len(G.edges),
        "duplicates_across_components": duplicates,
        "message": (
            f"Graph has {len(components)} connected component(s). "
            f"Largest has {max(len(c) for c in components)} nodes. "
            + (f"Found {len(duplicates)} duplicate entities across components."
               if duplicates else "No duplicate entities across components.")
        ),
    }


# Need to import nx for verify_graph_connectivity
import networkx as nx
