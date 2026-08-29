"""
Alerts Router.
Alert management, status updates, detection rules.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.models import (
    User, Alert, AlertStatus, AlertType, DetectionRule
)
from app.auth import get_current_user, RoleChecker, IO_ROLES, ANALYST_ROLES
from app.services.pattern_detection import run_all_detections
from app.utils import log_audit

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class AlertStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class DetectionRuleUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    threshold: Optional[float] = None


@router.get("")
def list_alerts(
    case_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Alert)

    if case_id:
        query = query.filter(Alert.case_id == case_id)
    if status:
        query = query.filter(Alert.status == status)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if severity:
        query = query.filter(Alert.severity == severity)

    alerts = query.order_by(Alert.detected_at.desc()).limit(200).all()

    results = []
    for alert in alerts:
        results.append({
            "id": alert.id,
            "alert_type": alert.alert_type.value,
            "title": alert.title,
            "description": alert.description,
            "status": alert.status.value,
            "severity": alert.severity,
            "involved_entity_ids": alert.involved_entity_ids or [],
            "supporting_evidence": alert.supporting_evidence or {},
            "detective_notes": alert.detective_notes,
            "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
            "reviewed_at": alert.reviewed_at.isoformat() if alert.reviewed_at else None,
            "case_id": alert.case_id,
        })

    return results


@router.get("/stats")
def get_alert_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = db.query(Alert).count()
    new_count = db.query(Alert).filter(Alert.status == AlertStatus.NEW).count()
    under_review = db.query(Alert).filter(Alert.status == AlertStatus.UNDER_REVIEW).count()
    confirmed = db.query(Alert).filter(Alert.status == AlertStatus.CONFIRMED).count()
    dismissed = db.query(Alert).filter(Alert.status == AlertStatus.DISMISSED).count()

    high_severity = db.query(Alert).filter(
        Alert.severity == "high",
        Alert.status.in_([AlertStatus.NEW, AlertStatus.UNDER_REVIEW])
    ).count()

    return {
        "total": total,
        "new": new_count,
        "under_review": under_review,
        "confirmed": confirmed,
        "dismissed": dismissed,
        "high_severity_active": high_severity,
    }


@router.put("/{alert_id}/status")
def update_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
    current_user: User = Depends(RoleChecker(IO_ROLES)),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Validate status transition
    valid_statuses = ["New", "Under Review", "Confirmed", "Dismissed"]
    if update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    # Dismiss requires a reason
    if update.status == "Dismissed" and not update.notes:
        raise HTTPException(status_code=400, detail="Dismissal requires a mandatory reason/note")

    alert.status = AlertStatus(update.status)
    alert.reviewed_at = datetime.now(timezone.utc)
    alert.reviewed_by = current_user.id
    if update.notes:
        alert.detective_notes = update.notes

    db.commit()

    log_audit(db, current_user.id, "update_alert_status", "alert", alert_id,
              {"new_status": update.status})

    return {"message": "Alert status updated", "status": update.status}


@router.post("/run-detection")
def trigger_detection(
    current_user: User = Depends(RoleChecker(ANALYST_ROLES)),
    db: Session = Depends(get_db),
):
    alerts = run_all_detections(db)
    return {
        "message": f"Detection complete. {len(alerts)} new alerts generated.",
        "alerts_created": len(alerts),
    }


# Detection Rules endpoints
@router.get("/rules")
def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rules = db.query(DetectionRule).all()
    return [{
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "description": rule.description,
        "is_enabled": rule.is_enabled,
        "threshold": rule.threshold,
        "config": rule.config or {},
    } for rule in rules]


@router.put("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    update: DetectionRuleUpdate,
    current_user: User = Depends(RoleChecker(ANALYST_ROLES)),
    db: Session = Depends(get_db),
):
    rule = db.query(DetectionRule).filter(DetectionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if update.is_enabled is not None:
        rule.is_enabled = update.is_enabled
    if update.threshold is not None:
        if update.threshold < 0:
            raise HTTPException(status_code=400, detail="Threshold must be non-negative")
        rule.threshold = update.threshold

    db.commit()
    log_audit(db, current_user.id, "update_detection_rule", "rule", rule_id,
              {"enabled": rule.is_enabled, "threshold": rule.threshold})

    return {"message": "Rule updated", "id": rule.id}
