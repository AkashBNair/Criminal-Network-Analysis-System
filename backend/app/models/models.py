"""
Database models for the AI-Powered Criminal Network Analysis System.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Text, Boolean, DateTime,
    ForeignKey, JSON, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


def gen_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    SYSTEM_ADMIN = "system_admin"
    SENIOR_OFFICIAL = "senior_official"
    CRIME_ANALYST = "crime_analyst"
    INVESTIGATING_OFFICER = "investigating_officer"
    DATA_ENTRY = "data_entry"
    AUDITOR = "auditor"


class EntityType(str, enum.Enum):
    PERSON = "Person"
    LOCATION = "Location"
    PHONE = "Phone"
    VEHICLE = "Vehicle"
    ORGANIZATION = "Organization"
    EVENT = "Event"
    DATE = "Date"


class RelationshipType(str, enum.Enum):
    COMMUNICATION = "Communication"
    FINANCIAL = "Financial Transaction"
    FAMILY = "Family"
    CO_ACCUSED = "Co-accused"
    ASSOCIATE = "Associate"
    EMPLOYMENT = "Employment"
    OWNERSHIP = "Ownership"
    LOCATION_PRESENCE = "Location Presence"


class AlertStatus(str, enum.Enum):
    NEW = "New"
    UNDER_REVIEW = "Under Review"
    CONFIRMED = "Confirmed"
    DISMISSED = "Dismissed"


class AlertType(str, enum.Enum):
    CROSS_CASE_MATCH = "Cross-Case Match"
    COMMUNICATION_BURST = "Communication Burst"
    CIRCULAR_TRANSACTION = "Circular Transaction"
    SHARED_PHONE = "Shared Phone Number"
    SHARED_ADDRESS = "Shared Address"


class CaseStatus(str, enum.Enum):
    ACTIVE = "Active"
    ARCHIVED = "Archived"


class JobStatus(str, enum.Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.INVESTIGATING_OFFICER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    case_assignments = relationship("CaseAssignment", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, default=gen_uuid)
    case_number = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(CaseStatus), default=CaseStatus.ACTIVE)
    jurisdiction = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, ForeignKey("users.id"))

    assignments = relationship("CaseAssignment", back_populates="case")
    entities = relationship("Entity", back_populates="case")
    documents = relationship("Document", back_populates="case")
    alerts = relationship("Alert", back_populates="case")
    ingestion_jobs = relationship("IngestionJob", back_populates="case")


class CaseAssignment(Base):
    __tablename__ = "case_assignments"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    assigned_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="case_assignments")
    case = relationship("Case", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint('user_id', 'case_id', name='uq_user_case'),
    )


class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    entity_type = Column(SAEnum(EntityType), nullable=False)
    name = Column(String(255), nullable=False)
    aliases = Column(JSON, default=list)
    attributes = Column(JSON, default=dict)  # Flexible: phones, addresses, etc.
    confidence_score = Column(Float, default=1.0)
    source_document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    source_record_ids = Column(JSON, default=list)
    is_ai_extracted = Column(Boolean, default=False)
    is_reviewed = Column(Boolean, default=True)
    is_merged_into = Column(String, ForeignKey("entities.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    case = relationship("Case", back_populates="entities")
    source_document = relationship("Document", back_populates="entities")
    relationships_as_source = relationship(
        "Relationship", foreign_keys="Relationship.source_entity_id",
        back_populates="source_entity"
    )
    relationships_as_target = relationship(
        "Relationship", foreign_keys="Relationship.target_entity_id",
        back_populates="target_entity"
    )


class Relationship(Base):
    __tablename__ = "relationships"
    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    source_entity_id = Column(String, ForeignKey("entities.id"), nullable=False)
    target_entity_id = Column(String, ForeignKey("entities.id"), nullable=False)
    relationship_type = Column(SAEnum(RelationshipType), nullable=False)
    weight = Column(Float, default=1.0)
    confidence_score = Column(Float, default=1.0)
    is_ai_generated = Column(Boolean, default=False)
    is_reviewed = Column(Boolean, default=True)
    justification = Column(Text, nullable=True)
    first_observed = Column(DateTime, nullable=True)
    last_observed = Column(DateTime, nullable=True)
    source_record_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)

    source_entity = relationship("Entity", foreign_keys=[source_entity_id], back_populates="relationships_as_source")
    target_entity = relationship("Entity", foreign_keys=[target_entity_id], back_populates="relationships_as_target")


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=True)
    alert_type = Column(SAEnum(AlertType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    involved_entity_ids = Column(JSON, default=list)
    supporting_evidence = Column(JSON, default=dict)
    status = Column(SAEnum(AlertStatus), default=AlertStatus.NEW)
    severity = Column(String(20), default="medium")
    detective_notes = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)

    case = relationship("Case", back_populates="alerts")


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, default=0)
    file_hash = Column(String(64), nullable=True)
    file_path = Column(String(500), nullable=False)
    content_text = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=True)  # fir, cdr, financial, report
    ingestion_status = Column(String(20), default="completed")
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=utcnow)

    case = relationship("Case", back_populates="documents")
    entities = relationship("Entity", back_populates="source_document")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    entities_extracted = Column(Integer, default=0)
    relationships_created = Column(Integer, default=0)
    errors = Column(JSON, default=list)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    case = relationship("Case", back_populates="ingestion_jobs")


class DetectionRule(Base):
    __tablename__ = "detection_rules"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    rule_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True)
    threshold = Column(Float, default=10.0)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="audit_logs")
