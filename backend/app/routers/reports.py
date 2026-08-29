"""
Reports Router.
Common-link report generation, entity profile reports, PDF export.
"""
import io
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.models import (
    User, Case, Entity, Relationship, Document, EntityType,
    RelationshipType, CaseAssignment, CaseStatus
)
from app.auth import get_current_user, RoleChecker, ADMIN_ROLES, IO_ROLES, VIEW_ALL_CASES
from app.services.graph_analytics import compute_centrality, detect_communities
from app.utils import log_audit

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


class CommonLinkRequest(BaseModel):
    case_ids: List[str]


def check_case_access(user: User, case_id: str, db: Session) -> bool:
    if user.role in VIEW_ALL_CASES:
        return True
    return db.query(CaseAssignment).filter(
        CaseAssignment.user_id == user.id,
        CaseAssignment.case_id == case_id,
    ).first() is not None


def get_user_case_ids(user: User, db: Session) -> List[str]:
    if user.role in VIEW_ALL_CASES:
        return [c.id for c in db.query(Case).filter(Case.status != CaseStatus.ARCHIVED).all()]
    return [a.case_id for a in user.case_assignments]


@router.post("/common-links")
def find_common_links(
    req: CommonLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find people who appear in MORE than one of the selected cases.
    Returns each common person with their cases and roles.
    """
    user_case_ids = get_user_case_ids(current_user, db)
    allowed = [cid for cid in req.case_ids if cid in user_case_ids]
    if len(allowed) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 accessible cases to find common links")

    # Get case info
    cases_map = {}
    for cid in allowed:
        case = db.query(Case).filter(Case.id == cid).first()
        if case:
            cases_map[cid] = case

    # ── View-Layer Type Enforcement ──
    # Find ALL entities (not just persons) appearing in multiple selected cases.
    # Group by entity type for proper badge display.
    entity_cases = {}  # (name, entity_type) -> {case_id: {attributes, ...}}
    needs_review = []  # entities that failed extraction sanity checks

    for cid in allowed:
        entities = db.query(Entity).filter(
            Entity.case_id == cid,
            Entity.is_merged_into.is_(None),
        ).all()
        for e in entities:
            key = (e.name, e.entity_type.value)
            if key not in entity_cases:
                entity_cases[key] = {}
            attrs = e.attributes or {}
            entity_cases[key][cid] = {
                "entity_id": e.id,
                "attributes": attrs,
                "role": attrs.get("role", attrs.get("Role Alleged", "Unknown")),
                "status": attrs.get("status", "Unknown"),
                "aliases": e.aliases or [],
                "confidence": e.confidence_score,
                "partial_identity": attrs.get("partial_identity", False),
                "is_ai_extracted": e.is_ai_extracted,
            }

    # ── Type Badge Map ──
    TYPE_BADGE_MAP = {
        "Person": {"label": "Person", "color": "#3b82f6", "icon": "user"},
        "Organization": {"label": "Organization", "color": "#6b7280", "icon": "building"},
        "Location": {"label": "Location", "color": "#22c55e", "icon": "pin"},
        "Vehicle": {"label": "Vehicle", "color": "#f59e0b", "icon": "car"},
        "Phone": {"label": "Mobile", "color": "#a855f7", "icon": "phone"},
        "Event": {"label": "Case", "color": "#64748b", "icon": "file"},
    }

    # Filter to entities in 2+ cases
    common_entities = {
        key: cases
        for key, cases in entity_cases.items()
        if len(cases) >= 2
    }

    # Build results grouped by type
    persons = []
    other_entities = []

    for (name, etype), case_info in common_entities.items():
        case_entries = []
        for cid, info in case_info.items():
            case = cases_map.get(cid)
            if case:
                case_entries.append({
                    "case_id": cid,
                    "case_number": case.case_number,
                    "case_name": case.name,
                    "role_in_case": info["role"],
                    "status": info["status"],
                    "aliases": info["aliases"],
                    "entity_id": info["entity_id"],
                    "confidence": info["confidence"],
                    "partial_identity": info["partial_identity"],
                })

        entity_ids = [ce["entity_id"] for ce in case_entries]
        rel_count = db.query(Relationship).filter(
            (Relationship.source_entity_id.in_(entity_ids)) |
            (Relationship.target_entity_id.in_(entity_ids))
        ).count()

        first_attrs = list(case_info.values())[0]["attributes"]
        badge = TYPE_BADGE_MAP.get(etype, {"label": etype, "color": "#6b7280", "icon": "help"})

        entry = {
            "name": name,
            "entity_type": etype,
            "type_badge": badge,
            "case_count": len(case_entries),
            "cases": case_entries,
            "total_relationships": rel_count,
            "profile": {
                "alias": first_attrs.get("alias", None),
                "phone": first_attrs.get("phone", None),
                "history": first_attrs.get("history", None),
                "modus_operandi": first_attrs.get("modus_operandi", None),
            },
            "partial_identity": first_attrs.get("partial_identity", False),
        }

        if etype == "Person":
            persons.append(entry)
        else:
            other_entities.append(entry)

    # Sort each group by case count
    persons.sort(key=lambda x: x["case_count"], reverse=True)
    other_entities.sort(key=lambda x: x["case_count"], reverse=True)

    # Collect needs_review: partial identity entities across cases
    partial_entities = []
    for (name, etype), case_info in entity_cases.items():
        for cid, info in case_info.items():
            if info.get("partial_identity"):
                case = cases_map.get(cid)
                partial_entities.append({
                    "name": name,
                    "entity_type": etype,
                    "case_number": case.case_number if case else "Unknown",
                    "reason": info["attributes"].get("partial_reason", "Partial identity - may represent multiple individuals"),
                })
                break  # Only list once per unique entity

    log_audit(db, current_user.id, "common_link_report", "report", None,
              {"case_ids": allowed, "persons": len(persons), "other": len(other_entities)})

    return {
        "report_type": "common_links",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases_analyzed": len(allowed),
        "case_details": [
            {"case_id": cid, "case_number": cases_map[cid].case_number, "case_name": cases_map[cid].name}
            for cid in allowed if cid in cases_map
        ],
        "common_persons": persons,
        "common_other_entities": other_entities,
        "needs_review": partial_entities,
        "total_common_persons": len(persons),
        "total_common_entities": len(persons) + len(other_entities),
    }


@router.post("/common-links/pdf")
def export_common_links_pdf(
    req: CommonLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export common-link report as PDF."""
    # Get the report data first
    report_data = find_common_links(req, current_user, db)

    # Generate PDF
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=6)
    elements.append(Paragraph("Criminal Network Analysis - Common Link Report", title_style))
    elements.append(Paragraph(f"Generated: {report_data['generated_at'][:10]}", styles['Normal']))
    elements.append(Paragraph(f"Cases Analyzed: {report_data['cases_analyzed']}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Cases table
    elements.append(Paragraph("<b>Cases in This Report:</b>", styles['Normal']))
    case_data = [["Case Number", "Case Name"]]
    for cd in report_data["case_details"]:
        case_data.append([cd["case_number"], cd["case_name"]])

    case_table = Table(case_data, colWidths=[2*inch, 4*inch])
    case_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(case_table)
    elements.append(Spacer(1, 16))

    # Common persons
    elements.append(Paragraph(
        f"<b>Common Links Found: {report_data['total_common_persons']} persons</b>",
        styles['Normal']
    ))
    elements.append(Spacer(1, 8))

    for person in report_data["common_persons"]:
        # Person header
        alias_str = f" (alias: {person['profile']['alias']})" if person['profile'].get('alias') else ""
        elements.append(Paragraph(
            f"<b>{person['name']}</b>{alias_str} - Appears in {person['case_count']} cases",
            ParagraphStyle('PersonHeader', parent=styles['Heading3'], fontSize=12, spaceAfter=4)
        ))

        # Case involvement table
        table_data = [["Case", "Case Name", "Role in Case", "Status"]]
        for case_entry in person["cases"]:
            table_data.append([
                case_entry["case_number"],
                case_entry["case_name"][:40],
                case_entry["role_in_case"],
                case_entry["status"],
            ])

        t = Table(table_data, colWidths=[1.2*inch, 2*inch, 1.8*inch, 1*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#c7d2fe')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t)

        # Additional profile info
        if person['profile'].get('phone'):
            elements.append(Paragraph(f"Phone: {person['profile']['phone']}", styles['Normal']))
        if person['profile'].get('history'):
            elements.append(Paragraph(f"Criminal History: {person['profile']['history']}", styles['Normal']))
        elements.append(Paragraph(f"Total Relationships: {person['total_relationships']}", styles['Normal']))
        elements.append(Spacer(1, 12))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
        elements.append(Spacer(1, 8))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    filename = f"common_link_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/case-summary")
def generate_case_summary(
    req: CommonLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a summary report for selected cases."""
    user_case_ids = get_user_case_ids(current_user, db)
    allowed = [cid for cid in req.case_ids if cid in user_case_ids]

    cases_summary = []
    for cid in allowed:
        case = db.query(Case).filter(Case.id == cid).first()
        if not case:
            continue

        entities = db.query(Entity).filter(
            Entity.case_id == cid, Entity.is_merged_into.is_(None)
        ).all()
        relationships = db.query(Relationship).filter(Relationship.case_id == cid).all()
        alerts = db.query(Alert).filter(Alert.case_id == cid).all()

        entity_type_counts = {}
        for e in entities:
            t = e.entity_type.value
            entity_type_counts[t] = entity_type_counts.get(t, 0) + 1

        # Get top persons by connections
        person_entities = [e for e in entities if e.entity_type == EntityType.PERSON]
        persons_with_connections = []
        for p in person_entities:
            rel_count = db.query(Relationship).filter(
                (Relationship.source_entity_id == p.id) |
                (Relationship.target_entity_id == p.id)
            ).count()
            persons_with_connections.append({
                "name": p.name,
                "connections": rel_count,
                "attributes": p.attributes or {},
            })
        persons_with_connections.sort(key=lambda x: x["connections"], reverse=True)

        cases_summary.append({
            "case_id": cid,
            "case_number": case.case_number,
            "case_name": case.name,
            "status": case.status.value,
            "jurisdiction": case.jurisdiction,
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "alert_count": len(alerts),
            "entity_type_counts": entity_type_counts,
            "top_persons": persons_with_connections[:10],
        })

    return {
        "report_type": "case_summary",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": cases_summary,
    }


@router.get("/export")
def export_case_report(
    case_id: str = Query(...),
    report_type: str = Query("case_summary"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export a report for a single case."""
    if not check_case_access(current_user, case_id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    entities = db.query(Entity).filter(
        Entity.case_id == case_id, Entity.is_merged_into.is_(None)
    ).all()
    relationships = db.query(Relationship).filter(Relationship.case_id == case_id).all()
    alerts = db.query(Alert).filter(Alert.case_id == case_id).all()

    # Build text report
    lines = [
        f"CASE REPORT: {case.case_number}",
        f"{'='*50}",
        f"Name: {case.name}",
        f"Status: {case.status.value}",
        f"Jurisdiction: {case.jurisdiction}",
        f"Description: {case.description or 'N/A'}",
        f"",
        f"STATISTICS",
        f"{'-'*30}",
        f"Total Entities: {len(entities)}",
        f"Total Relationships: {len(relationships)}",
        f"Active Alerts: {len(alerts)}",
        f"",
        f"ENTITIES",
        f"{'-'*30}",
    ]

    for e in entities:
        lines.append(f"  [{e.entity_type.value}] {e.name} (confidence: {e.confidence_score:.0%})")

    lines.extend(["", "RELATIONSHIPS", "-"*30])
    for r in relationships:
        src = db.query(Entity).filter(Entity.id == r.source_entity_id).first()
        tgt = db.query(Entity).filter(Entity.id == r.target_entity_id).first()
        if src and tgt:
            lines.append(f"  {src.name} --[{r.relationship_type.value}]--> {tgt.name}")

    lines.extend(["", "ALERTS", "-"*30])
    for a in alerts:
        lines.append(f"  [{a.severity.upper()}] {a.title}")

    report_text = "\n".join(lines)

    log_audit(db, current_user.id, "export_report", "report", case_id,
              {"report_type": report_type})

    return StreamingResponse(
        io.BytesIO(report_text.encode()),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=report_{case.case_number}.txt"}
    )


# ── Threat Scores ──────────────────────────────────────────────

class ThreatScoreRequest(BaseModel):
    case_ids: Optional[List[str]] = None  # None = all assigned cases


@router.post("/threat-scores")
async def get_threat_scores(
    req: ThreatScoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compute threat/importance scores for all persons in the specified cases.
    Score combines: network centrality (40%), role severity (30%),
    cross-case presence (20%), and activity level (10%).
    """
    from app.services.threat_scoring import compute_threat_scores
    from app.models.models import CaseAssignment

    case_ids = req.case_ids
    if not case_ids:
        # Use all cases assigned to the user
        if current_user.role.value in [r.value for r in VIEW_ALL_CASES]:
            case_ids = [c.id for c in db.query(Case).filter(Case.status == CaseStatus.ACTIVE).all()]
        else:
            case_ids = [a.case_id for a in db.query(CaseAssignment).filter(
                CaseAssignment.user_id == current_user.id
            ).all()]

    scores = compute_threat_scores(db, case_ids if case_ids else None)

    # ── View-Layer Type Enforcement: Assert ALL rows are PERSON ──
    # This runs at the query layer, not UI-side hide.
    # If any non-PERSON entity reaches this output, it means the scoring
    # pipeline itself doesn't distinguish types — a pipeline wiring bug.
    non_persons = []
    for s in scores:
        # Verify via the entity store that this is actually a PERSON
        from app.models.models import Entity as EntityModel
        ent = db.query(EntityModel).filter(EntityModel.id == s['entity_id']).first()
        if ent and ent.entity_type != EntityType.PERSON:
            non_persons.append({"id": s['entity_id'], "name": s['name'], "type": ent.entity_type.value})

    if non_persons:
        # Log but don't crash — these are data quality issues to investigate
        import logging
        logging.warning(f"THREAT ASSESSMENT: {len(non_persons)} non-PERSON entities found in scores")

    return {
        "scores": scores,
        "total": len(scores),
        "cases_analyzed": len(case_ids) if case_ids else 0,
        "type_validation": {
            "all_persons": len(non_persons) == 0,
            "non_person_count": len(non_persons),
            "non_persons": non_persons,
        },
    }


@router.get("/threat-scores/{entity_id}")
async def get_person_threat_score(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed threat score for a specific person."""
    from app.services.threat_scoring import get_person_threat_detail
    detail = get_person_threat_detail(db, entity_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Entity not found or not a person")
    return detail


# ── Validation & Audit ─────────────────────────────────────────

@router.get("/validate-consistency")
def validate_scoring_consistency(
    case_ids: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate that threat scores are consistent with centrality rankings.
    Returns validation report with any divergences.
    """
    from app.services.threat_scoring import validate_threat_score_consistency
    return validate_threat_score_consistency(db, case_ids)


@router.get("/audit-log")
def get_resolution_audit_log(
    entity_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get audit log of entity resolution decisions (merge/split/flag).
    Shows evidence used for each decision.
    """
    from app.services.entity_resolution import get_resolution_audit_log
    return get_resolution_audit_log(db, entity_id, limit)


@router.get("/entity-confidence")
def get_entity_confidence_summary(
    case_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get summary of entity confidence levels and resolution status.
    Helps identify entities needing human review.
    """
    query = db.query(Entity).filter(Entity.is_merged_into.is_(None))
    if case_id:
        query = query.filter(Entity.case_id == case_id)
    
    entities = query.all()
    
    # Categorize by confidence and resolution status
    high_confidence = []
    medium_confidence = []
    low_confidence = []
    unresolved = []
    
    for e in entities:
        confidence = e.confidence_score or 1.0
        attrs = e.attributes or {}
        resolution_status = attrs.get("resolution_status", "resolved")
        
        entry = {
            "entity_id": e.id,
            "name": e.name,
            "entity_type": e.entity_type.value,
            "confidence": confidence,
            "resolution_status": resolution_status,
            "is_ai_extracted": e.is_ai_extracted,
            "case_id": e.case_id,
        }
        
        if resolution_status == "unresolved":
            unresolved.append(entry)
        elif confidence >= 0.8:
            high_confidence.append(entry)
        elif confidence >= 0.5:
            medium_confidence.append(entry)
        else:
            low_confidence.append(entry)
    
    return {
        "total_entities": len(entities),
        "high_confidence": {
            "count": len(high_confidence),
            "entities": high_confidence[:20],
        },
        "medium_confidence": {
            "count": len(medium_confidence),
            "entities": medium_confidence[:20],
        },
        "low_confidence": {
            "count": len(low_confidence),
            "entities": low_confidence[:20],
        },
        "unresolved": {
            "count": len(unresolved),
            "entities": unresolved,
        },
        "needs_review_count": len(medium_confidence) + len(low_confidence) + len(unresolved),
    }


# ── Investigative Briefs ───────────────────────────────────────

@router.get("/brief/{entity_id}")
def generate_investigative_brief(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate an investigative brief for a specific entity.
    Reads like a narrative, not a data dump.
    Separates confirmed facts from inferences.
    """
    from app.services.pattern_detection import generate_investigative_brief
    from app.services.threat_scoring import get_person_threat_detail
    
    # Get threat score if available
    threat_score = get_person_threat_detail(db, entity_id)
    
    brief = generate_investigative_brief(db, entity_id, threat_score)
    if "error" in brief:
        raise HTTPException(status_code=404, detail=brief["error"])
    
    return brief


# ── Graph Connectivity Verification ────────────────────────────

@router.get("/graph-connectivity")
def verify_graph_connectivity(
    case_ids: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify that entity resolution is properly deduplicating.
    Checks for duplicate entities across connected components.
    """
    from app.services.pattern_detection import verify_graph_connectivity
    return verify_graph_connectivity(db, case_ids)


# ── Alert Details ──────────────────────────────────────────────

@router.get("/alerts/{alert_id}")
def get_alert_detail(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed alert information with full evidence trail.
    """
    from app.models.models import Alert
    
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Enrich with entity details
    entity_details = []
    for eid in (alert.involved_entity_ids or []):
        entity = db.query(Entity).filter(Entity.id == eid).first()
        if entity:
            entity_details.append({
                "entity_id": entity.id,
                "name": entity.name,
                "entity_type": entity.entity_type.value,
                "confidence": entity.confidence_score,
                "is_ai_extracted": entity.is_ai_extracted,
            })
    
    return {
        "alert_id": alert.id,
        "alert_type": alert.alert_type.value,
        "title": alert.title,
        "description": alert.description,
        "severity": alert.severity,
        "status": alert.status.value,
        "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
        "involved_entities": entity_details,
        "supporting_evidence": alert.supporting_evidence or {},
        "case_id": alert.case_id,
    }


# ── Serial Pattern Detection ──────────────────────────────────────

class SerialPatternRequest(BaseModel):
    case_ids: Optional[List[str]] = None  # None = all active cases
    use_llm: bool = False  # True = use Gemini LLM for deep behavioral analysis


@router.post("/serial-patterns")
def analyze_serial_patterns(
    req: SerialPatternRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze cases for behavioral patterns consistent with serial offending.
    Examines MO, victimology, geography, temporal spacing, and signature behaviors.

    This is a lead-generation tool — flagged patterns are candidate leads,
    NOT confirmed links. All outputs require human investigator review.
    """
    from app.services.serial_signature_enhancer import run_enhanced_serial_detection

    case_ids = req.case_ids
    if not case_ids:
        # Use all cases assigned to the user
        if current_user.role.value in [r.value for r in VIEW_ALL_CASES]:
            case_ids = [c.id for c in db.query(Case).filter(Case.status == CaseStatus.ACTIVE).all()]
        else:
            case_ids = [a.case_id for a in db.query(CaseAssignment).filter(
                CaseAssignment.user_id == current_user.id
            ).all()]

    result = run_enhanced_serial_detection(db, case_ids)

    # If use_llm=True, also run LLM pairwise analysis and merge results
    if req.use_llm:
        from app.services.serial_pattern_detection import run_llm_pairwise_analysis
        llm_result = run_llm_pairwise_analysis(db, case_ids)
        result["llm_pairwise"] = llm_result

    log_audit(db, current_user.id, "serial_pattern_analysis", "report", None,
              {"case_ids": case_ids or [], "similarity": result.get("overall_similarity", 0)})

    return result


@router.post("/serial-patterns/llm")
def analyze_serial_patterns_llm(
    req: SerialPatternRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    LLM-powered behavioral linkage analysis.
    Reads full case narratives and judges genuine behavioral similarity,
    explicitly rejecting surface-level word overlap.
    """
    from app.services.serial_pattern_detection import run_llm_pairwise_analysis

    case_ids = req.case_ids
    if not case_ids:
        if current_user.role.value in [r.value for r in VIEW_ALL_CASES]:
            case_ids = [c.id for c in db.query(Case).filter(Case.status == CaseStatus.ACTIVE).all()]
        else:
            case_ids = [a.case_id for a in db.query(CaseAssignment).filter(
                CaseAssignment.user_id == current_user.id
            ).all()]

    result = run_llm_pairwise_analysis(db, case_ids)

    log_audit(db, current_user.id, "llm_linkage_analysis", "report", None,
              {"case_ids": case_ids or [], "pairs": result.get("total_pairs", 0)})

    return result


@router.get("/serial-patterns/{case_id}")
def get_case_pattern_context(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed pattern context for a specific case.
    Shows how this case relates to others in the dataset.
    """
    from app.services.serial_signature_enhancer import detect_narrative_signatures, detect_victim_profile_patterns
    from app.services.serial_pattern_detection import (
        _extract_case_document_text, _extract_mo_from_text,
        _extract_victimology_from_text
    )

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    text = _extract_case_document_text(db, case_id)
    mo = _extract_mo_from_text(text) if text else {}
    victimology = _extract_victimology_from_text(text) if text else {}
    narrative_sigs = detect_narrative_signatures(text) if text else {}

    # Get entities
    entities = db.query(Entity).filter(
        Entity.case_id == case_id, Entity.is_merged_into.is_(None)
    ).all()

    entity_summary = {}
    for e in entities:
        t = e.entity_type.value
        if t not in entity_summary:
            entity_summary[t] = []
        entity_summary[t].append(e.name)

    return {
        "case_id": case_id,
        "case_number": case.case_number,
        "case_name": case.name,
        "mo_indicators": mo,
        "victimology": victimology,
        "narrative_signatures": narrative_sigs,
        "entity_summary": entity_summary,
        "document_available": bool(text),
    }
