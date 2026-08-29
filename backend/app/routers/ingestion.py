"""
Ingestion Router.
File upload, structured data import, document processing.
Auto case registration from uploaded files.
"""
import csv
import io
import re
import hashlib
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.models import (
    User, Case, CaseAssignment, Entity, Relationship, Document, IngestionJob,
    EntityType, RelationshipType, JobStatus, CaseStatus
)
from app.auth import get_current_user, RoleChecker, UPLOAD_ROLES
from app.services.entity_extraction import (
    extract_entities_from_text,
    extract_entities_from_structured,
)
from app.services.label_stripper import preprocess_text_labels
from app.services.pattern_detection import run_all_detections, extract_social_media_entities
from app.utils import log_audit

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes with Label:Value stripping."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        # Apply Label:Value stripping to remove labels before entity extraction
        text = preprocess_text_labels(text)
        return text
    except Exception:
        return ""


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX bytes with Label:Value stripping."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))

        # Extract paragraph text
        para_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

        # Extract tables with label-aware parsing (skip headers, type values)
        table_rows = []
        for table in doc.tables:
            if not table.rows:
                continue
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(cells)
            table_rows.append(rows)

        # Get table text using label-aware preprocessing
        from app.services.label_stripper import preprocess_docx_tables
        table_text = preprocess_docx_tables(table_rows)

        # Combine paragraph and table text
        text = para_text
        if table_text:
            text += "\n" + table_text

        # Apply Label:Value stripping to all text
        # This removes labels like "Full Name:" and keeps only "Vikram Solanki"
        text = preprocess_text_labels(text)

        return text
    except Exception:
        return ""


def parse_case_from_text(text: str) -> dict:
    """
    Extract structured case details from unstructured document text.
    Returns a dict with extracted fields (may be incomplete).
    """
    result = {
        "case_number": "",
        "name": "",
        "description": "",
        "jurisdiction": "",
        "date_filed": "",
        "police_station": "",
        "complainant": "",
        "accused_persons": [],
        "investigating_officer": "",
        "act_sections": "",
        "subject": "",
    }

    # Case number patterns
    case_patterns = [
        r'FIR\s*(?:No\.?|Number|#)?\s*:?\s*([A-Z0-9\-/]+(?:\d{4})?(?:/\d{4})?)',
        r'Case\s*(?:No\.?|Number|#)?\s*:?\s*([A-Z0-9\-/]+)',
        r'FIR\s+(?:No\.?\s*)?(\d+/\d{4})',
    ]
    for pat in case_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["case_number"] = m.group(1).strip()
            break

    # Subject line
    subject_patterns = [
        r'Subject\s*:?\s*(.+?)(?:\n|$)',
        r'Re\s*:?\s*(.+?)(?:\n|$)',
        r'Subject:\s*(.+?)(?:\n|$)',
    ]
    for pat in subject_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["subject"] = m.group(1).strip()[:200]
            break

    # Police station
    ps_patterns = [
        r'(?:Police\s+Station|P\.?S\.?|Station)\s*:?\s*(.+?)(?:\n|$)',
        r'Station\s*:?\s*(.+?)(?:\n|$)',
    ]
    for pat in ps_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["police_station"] = m.group(1).strip()[:200]
            break

    # Date filed
    date_patterns = [
        r'Date\s+(?:of\s+)?(?:Report|Filed|Filing)\s*:?\s*(\d{1,2}[-/]\w+[-/]\d{2,4})',
        r'Date\s*:?\s*(\d{1,2}[-/]\w+[-/]\d{2,4})',
        r'Filed\s+(?:on\s+)?(\d{1,2}[-/]\w+[-/]\d{2,4})',
    ]
    for pat in date_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["date_filed"] = m.group(1).strip()
            break

    # Complainant
    comp_patterns = [
        r'Complainant\s*(?:Details|Name)?\s*:?\s*\n?\s*Name\s*:?\s*(.+?)(?:\n|$)',
        r'Complainant\s*:?\s*(?:Name\s*:?\s*)?(.+?)(?:\n|$)',
    ]
    for pat in comp_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["complainant"] = m.group(1).strip()[:200]
            break

    # Investigating Officer
    io_patterns = [
        r'Investigating\s+Officer\s*:?\s*\n?\s*Name\s*:?\s*(.+?)(?:\n|$)',
        r'I\.?O\.?\s*:?\s*(.+?)(?:\n|$)',
    ]
    for pat in io_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["investigating_officer"] = m.group(1).strip()[:200]
            break

    # Accused persons from table-like patterns
    # Pattern: # | Name | Alias | Role | Status
    accused_section = re.search(
        r'Accused\s+Persons?\s+Named.*?(?=Investigating|$)',
        text, re.IGNORECASE | re.DOTALL
    )
    if accused_section:
        section = accused_section.group()
        # Match lines like: "1 | Vikram Solanki | alias | role | status"
        rows = re.findall(r'\d+\s*\|\s*(.+?)(?:\n|$)', section)
        for row in rows:
            parts = [p.strip() for p in row.split('|') if p.strip()]
            if parts and len(parts[0]) > 2 and not parts[0].startswith('#'):
                name = parts[0]
                alias = parts[1] if len(parts) > 1 and parts[1] != '--' else ''
                role = parts[2] if len(parts) > 2 else ''
                status = parts[-1] if len(parts) > 3 else ''
                result["accused_persons"].append({
                    "name": name,
                    "alias": alias if alias and alias != '--' else '',
                    "role": role,
                    "status": status,
                })

    # Also try to find accused names from "Accused:" sections
    if not result["accused_persons"]:
        accused_names = re.findall(
            r'(?:Accused|Suspect|Named)\s*:?\s*(?:\n\s*)?(?:\d+[.)]\s*)?(?:Name\s*:?\s*)?([A-Z][a-z]+ (?:[A-Z][a-z]+\s*){1,3})',
            text, re.IGNORECASE
        )
        for name in accused_names:
            name = name.strip()
            if len(name) > 3 and name not in [a["name"] for a in result["accused_persons"]]:
                result["accused_persons"].append({"name": name, "alias": "", "role": "", "status": ""})

    # Act and sections
    act_patterns = [
        r'(?:Act|Statute)\s*\(?(?:s?\)?)\s*&?\s*Section\(s?\)\s*:?\s*(.+?)(?:\n|$)',
        r'Section\s+(\d+[a-z]?(?:\(\d+\))?(?:\s*,?\s*\d+[a-z]?(?:\(\d+\))?)*)',
    ]
    for pat in act_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["act_sections"] = m.group(1).strip()[:200]
            break

    # Jurisdiction from location mentions
    loc_patterns = [
        r'(?:District|Jurisdiction)\s*:?\s*(.+?)(?:\n|$)',
        r'P\.?S\.\s+.+?,\s*(.+?)(?:\n|$)',
    ]
    for pat in loc_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["jurisdiction"] = m.group(1).strip()[:200]
            break

    # Generate case name from subject or first meaningful line
    if result["subject"]:
        result["name"] = result["subject"][:150]
    elif result["case_number"]:
        result["name"] = f"Case {result['case_number']}"

    # Generate description from brief facts
    brief_facts = re.search(
        r'Brief\s+Facts?\s+(?:of\s+the\s+)?Case\s*:?\s*(.+?)(?=Accused|Investigating|$)',
        text, re.IGNORECASE | re.DOTALL
    )
    if brief_facts:
        result["description"] = brief_facts.group(1).strip()[:500]

    return result


@router.post("/auto-register")
async def auto_register_case(
    file: UploadFile = File(...),
    current_user: User = Depends(RoleChecker(UPLOAD_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Upload a case file (PDF/DOCX/TXT) and auto-extract case details.
    Returns extracted data for review before finalizing.
    """
    content = await file.read()

    # Extract text based on file type
    text = ""
    filename = file.filename or "unknown"

    if filename.endswith(".pdf"):
        text = extract_text_from_pdf(content)
    elif filename.endswith(".docx"):
        text = extract_text_from_docx(content)
    elif filename.endswith((".txt", ".csv", ".json")):
        text = content.decode("utf-8", errors="replace")
    else:
        # Try as text
        text = content.decode("utf-8", errors="replace")

    if not text or len(text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file.")

    # Parse case details
    extracted = parse_case_from_text(text)

    # Also extract entities for preview
    entities_preview = extract_entities_from_text(text[:50000], "fir")

    entity_summary = {}
    for e in entities_preview:
        t = e.entity_type.value
        if t not in entity_summary:
            entity_summary[t] = []
        if len(entity_summary[t]) < 5:
            entity_summary[t].append({"name": e.name, "confidence": round(e.confidence, 2)})

    log_audit(db, current_user.id, "auto_register_preview", "case", None,
              {"filename": filename, "extracted_fields": list(extracted.keys())})

    return {
        "filename": filename,
        "text_preview": text[:2000],
        "extracted_case": extracted,
        "entities_preview": entity_summary,
        "status": "ready_for_review",
    }


@router.post("/auto-register/confirm")
async def confirm_auto_register(
    case_number: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    jurisdiction: str = Form(""),
    date_filed: str = Form(""),
    police_station: str = Form(""),
    accused_persons_json: str = Form("[]"),
    file: UploadFile = File(...),
    current_user: User = Depends(RoleChecker(UPLOAD_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Confirm and create a case from auto-registered data.
    Saves the file, creates the case, and ingests entities.
    """
    import json as _json

    # Create case
    case = Case(
        case_number=case_number,
        name=name,
        description=description or f"Auto-registered from {file.filename}",
        jurisdiction=jurisdiction or police_station,
        created_by=current_user.id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Auto-assign creator
    db.add(CaseAssignment(user_id=current_user.id, case_id=case.id))
    db.commit()

    # Save and process the file
    content = await file.read()
    file_hash = compute_file_hash(content)

    upload_dir = os.path.join("uploads", case.id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text
    text = ""
    if file.filename and file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(content)
    elif file.filename and file.filename.endswith(".docx"):
        text = extract_text_from_docx(content)
    else:
        text = content.decode("utf-8", errors="replace")

    # Create document record
    document = Document(
        case_id=case.id,
        filename=file.filename or "uploaded_file",
        file_type=file.content_type or "unknown",
        file_size=len(content),
        file_hash=file_hash,
        file_path=file_path,
        content_text=text,
        source_type="fir",
        uploaded_by=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Process: extract entities
    entities_created = 0
    relationships_created = 0

    extracted = extract_entities_from_text(text, "fir")
    entity_ids = []
    for ext in extracted:
        entity = Entity(
            case_id=case.id,
            entity_type=ext.entity_type,
            name=ext.name,
            attributes=ext.attributes,
            confidence_score=ext.confidence,
            source_document_id=document.id,
            is_ai_extracted=True,
            is_reviewed=ext.confidence >= 0.85,
        )
        db.add(entity)
        db.flush()
        entity_ids.append(entity.id)
        entities_created += 1

    # Co-occurrence relationships
    for i in range(len(entity_ids)):
        for j in range(i + 1, min(len(entity_ids), i + 20)):
            rel = Relationship(
                case_id=case.id,
                source_entity_id=entity_ids[i],
                target_entity_id=entity_ids[j],
                relationship_type=RelationshipType.ASSOCIATE,
                weight=1.0,
                confidence_score=0.6,
                is_ai_generated=True,
                is_reviewed=False,
                source_record_ids=[document.id],
            )
            db.add(rel)
            relationships_created += 1

    # Add accused persons from parsed data
    try:
        accused = _json.loads(accused_persons_json)
        for acc in accused:
            if isinstance(acc, dict) and acc.get("name"):
                entity = Entity(
                    case_id=case.id,
                    entity_type=EntityType.PERSON,
                    name=acc["name"],
                    attributes={
                        "alias": acc.get("alias", ""),
                        "role": acc.get("role", ""),
                        "status": acc.get("status", ""),
                        "source": "auto_registered",
                    },
                    confidence_score=1.0,
                    source_document_id=document.id,
                    is_ai_extracted=False,
                    is_reviewed=True,
                )
                db.add(entity)
                db.flush()
                entities_created += 1
    except Exception:
        pass

    db.commit()

    # Run pattern detection
    try:
        run_all_detections(db)
    except Exception:
        pass

    log_audit(db, current_user.id, "auto_register_confirm", "case", case.id,
              {"case_number": case_number, "entities": entities_created})

    return {
        "case_id": case.id,
        "case_number": case.case_number,
        "name": case.name,
        "status": "created",
        "entities_extracted": entities_created,
        "relationships_created": relationships_created,
    }


@router.post("/upload")
async def upload_document(
    case_id: str = Form(...),
    source_type: str = Form("general"),
    file: UploadFile = File(...),
    current_user: User = Depends(RoleChecker(UPLOAD_ROLES)),
    db: Session = Depends(get_db),
):
    # Validate case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    content = await file.read()
    file_hash = compute_file_hash(content)

    existing = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate file detected. Originally uploaded as '{existing.filename}'."
        )

    upload_dir = os.path.join("uploads", case_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

    content_text = ""
    if file.content_type in ("text/plain", "text/csv", "application/json"):
        content_text = content.decode("utf-8", errors="replace")
    elif file.filename and file.filename.endswith((".txt", ".csv", ".json")):
        content_text = content.decode("utf-8", errors="replace")
    elif file.filename and file.filename.endswith(".pdf"):
        content_text = extract_text_from_pdf(content)
    elif file.filename and file.filename.endswith((".docx", ".doc")):
        content_text = extract_text_from_docx(content)
    else:
        content_text = content.decode("utf-8", errors="replace")

    document = Document(
        case_id=case_id,
        filename=file.filename,
        file_type=file.content_type or "unknown",
        file_size=len(content),
        file_hash=file_hash,
        file_path=file_path,
        content_text=content_text,
        source_type=source_type,
        uploaded_by=current_user.id,
    )
    db.add(document)
    db.flush()

    job = IngestionJob(
        case_id=case_id,
        document_id=document.id,
        status=JobStatus.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(document)

    entities_created = 0
    relationships_created = 0
    errors = []

    try:
        if source_type in ("cdr", "call", "calls", "financial", "transaction", "bank"):
            if file.content_type == "text/csv" or (file.filename and file.filename.endswith(".csv")):
                reader = csv.DictReader(io.StringIO(content_text))
                for row in reader:
                    try:
                        extracted = extract_entities_from_structured(row, source_type)
                        entity_ids = []
                        for ext in extracted:
                            entity = Entity(
                                case_id=case_id,
                                entity_type=ext.entity_type,
                                name=ext.name,
                                attributes=ext.attributes,
                                confidence_score=ext.confidence,
                                source_document_id=document.id,
                                is_ai_extracted=True,
                                is_reviewed=ext.confidence >= 0.85,
                            )
                            db.add(entity)
                            db.flush()
                            entity_ids.append(entity.id)
                            entities_created += 1

                        for i in range(len(entity_ids)):
                            for j in range(i + 1, len(entity_ids)):
                                rel_type = RelationshipType.COMMUNICATION
                                if source_type in ("financial", "transaction", "bank"):
                                    rel_type = RelationshipType.FINANCIAL
                                rel = Relationship(
                                    case_id=case_id,
                                    source_entity_id=entity_ids[i],
                                    target_entity_id=entity_ids[j],
                                    relationship_type=rel_type,
                                    weight=1.0,
                                    is_ai_generated=True,
                                    is_reviewed=False,
                                    source_record_ids=[document.id],
                                )
                                db.add(rel)
                                relationships_created += 1
                    except Exception as e:
                        errors.append(f"Row error: {str(e)}")
        else:
            extracted = extract_entities_from_text(content_text, source_type)
            entity_ids = []
            for ext in extracted:
                entity = Entity(
                    case_id=case_id,
                    entity_type=ext.entity_type,
                    name=ext.name,
                    attributes=ext.attributes,
                    confidence_score=ext.confidence,
                    source_document_id=document.id,
                    is_ai_extracted=True,
                    is_reviewed=ext.confidence >= 0.85,
                )
                db.add(entity)
                db.flush()
                entity_ids.append(entity.id)
                entities_created += 1

            for i in range(len(entity_ids)):
                for j in range(i + 1, min(len(entity_ids), i + 20)):
                    rel = Relationship(
                        case_id=case_id,
                        source_entity_id=entity_ids[i],
                        target_entity_id=entity_ids[j],
                        relationship_type=RelationshipType.ASSOCIATE,
                        weight=1.0,
                        confidence_score=0.6,
                        is_ai_generated=True,
                        is_reviewed=False,
                        source_record_ids=[document.id],
                    )
                    db.add(rel)
                    relationships_created += 1

    except Exception as e:
        errors.append(f"Processing error: {str(e)}")

    job.status = JobStatus.COMPLETED
    job.entities_extracted = entities_created
    job.relationships_created = relationships_created
    job.errors = errors
    job.completed_at = datetime.now(timezone.utc)
    db.commit()

    try:
        run_all_detections(db)
    except Exception:
        pass

    log_audit(db, current_user.id, "upload_document", "document", document.id,
              {"filename": file.filename, "entities": entities_created})

    return {
        "document_id": document.id,
        "filename": file.filename,
        "job_id": job.id,
        "entities_extracted": entities_created,
        "relationships_created": relationships_created,
        "errors": errors,
        "status": "completed",
    }


@router.post("/upload-text")
async def upload_text_content(
    case_id: str = Form(...),
    source_type: str = Form("general"),
    title: str = Form(""),
    content: str = Form(...),
    current_user: User = Depends(RoleChecker(UPLOAD_ROLES)),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    upload_dir = os.path.join("uploads", case_id)
    os.makedirs(upload_dir, exist_ok=True)

    file_hash = hashlib.sha256(content.encode()).hexdigest()
    file_path = os.path.join(upload_dir, f"{file_hash}_text.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    document = Document(
        case_id=case_id,
        filename=title or "text_upload.txt",
        file_type="text/plain",
        file_size=len(content),
        file_hash=file_hash,
        file_path=file_path,
        content_text=content,
        source_type=source_type,
        uploaded_by=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    entities_created = 0
    relationships_created = 0

    # Extract standard entities
    extracted = extract_entities_from_text(content, source_type)
    entity_ids = []
    for ext in extracted:
        entity = Entity(
            case_id=case_id,
            entity_type=ext.entity_type,
            name=ext.name,
            attributes=ext.attributes,
            confidence_score=ext.confidence,
            source_document_id=document.id,
            is_ai_extracted=True,
            is_reviewed=ext.confidence >= 0.85,
        )
        db.add(entity)
        db.flush()
        entity_ids.append(entity.id)
        entities_created += 1

    # Extract social media entities if source type is social_media or the content contains social media indicators
    if source_type in ("social_media", "social", "socmint") or "@" in content or "facebook.com" in content or "instagram.com" in content:
        social_entities = extract_social_media_entities(content)
        for se in social_entities:
            if se["type"] == "social_media_handle":
                entity = Entity(
                    case_id=case_id,
                    entity_type=EntityType.PERSON,
                    name=se["handle"],
                    attributes={
                        "platform": se["platform"],
                        "source": "social_media",
                        "raw_match": se["raw_match"],
                    },
                    confidence_score=0.85,
                    source_document_id=document.id,
                    is_ai_extracted=True,
                    is_reviewed=False,
                )
                db.add(entity)
                db.flush()
                entity_ids.append(entity.id)
                entities_created += 1
            elif se["type"] == "social_media_profile_data":
                # Store as attribute on the document for later association
                pass

    for i in range(len(entity_ids)):
        for j in range(i + 1, min(len(entity_ids), i + 20)):
            rel = Relationship(
                case_id=case_id,
                source_entity_id=entity_ids[i],
                target_entity_id=entity_ids[j],
                relationship_type=RelationshipType.ASSOCIATE,
                weight=1.0,
                confidence_score=0.6,
                is_ai_generated=True,
                is_reviewed=False,
                source_record_ids=[document.id],
            )
            db.add(rel)
            relationships_created += 1

    db.commit()

    try:
        run_all_detections(db)
    except Exception:
        pass

    log_audit(db, current_user.id, "upload_text", "document", document.id,
              {"title": title, "entities": entities_created})

    return {
        "document_id": document.id,
        "entities_extracted": entities_created,
        "relationships_created": relationships_created,
        "social_media_entities": len([e for e in entity_ids if True]),  # Count of social media entities
    }


@router.post("/upload-social")
async def upload_social_media_content(
    case_id: str = Form(...),
    platform: str = Form("unknown"),  # twitter, instagram, facebook, whatsapp, telegram
    title: str = Form(""),
    content: str = Form(...),
    current_user: User = Depends(RoleChecker(UPLOAD_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Upload social media intelligence (SOCMINT) data.
    Handles structured or unstructured social media content.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    upload_dir = os.path.join("uploads", case_id, "socmint")
    os.makedirs(upload_dir, exist_ok=True)

    file_hash = hashlib.sha256(content.encode()).hexdigest()
    file_path = os.path.join(upload_dir, f"{file_hash}_{platform}.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    document = Document(
        case_id=case_id,
        filename=title or f"socmint_{platform}.txt",
        file_type="text/plain",
        file_size=len(content),
        file_hash=file_hash,
        file_path=file_path,
        content_text=content,
        source_type="social_media",
        uploaded_by=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    entities_created = 0
    relationships_created = 0

    # Extract social media entities
    social_entities = extract_social_media_entities(content)
    entity_ids = []
    
    for se in social_entities:
        if se["type"] == "social_media_handle":
            entity = Entity(
                case_id=case_id,
                entity_type=EntityType.PERSON,
                name=se["handle"],
                attributes={
                    "platform": se["platform"],
                    "source": "social_media",
                    "raw_match": se["raw_match"],
                },
                confidence_score=0.85,
                source_document_id=document.id,
                is_ai_extracted=True,
                is_reviewed=False,
            )
            db.add(entity)
            db.flush()
            entity_ids.append(entity.id)
            entities_created += 1

    # Also extract standard entities (names, phones, etc.)
    standard_entities = extract_entities_from_text(content, "social_media")
    for ext in standard_entities:
        entity = Entity(
            case_id=case_id,
            entity_type=ext.entity_type,
            name=ext.name,
            attributes=ext.attributes,
            confidence_score=ext.confidence,
            source_document_id=document.id,
            is_ai_extracted=True,
            is_reviewed=ext.confidence >= 0.85,
        )
        db.add(entity)
        db.flush()
        entity_ids.append(entity.id)
        entities_created += 1

    # Create relationships between co-occurring entities
    for i in range(len(entity_ids)):
        for j in range(i + 1, min(len(entity_ids), i + 10)):
            rel = Relationship(
                case_id=case_id,
                source_entity_id=entity_ids[i],
                target_entity_id=entity_ids[j],
                relationship_type=RelationshipType.ASSOCIATE,
                weight=0.8,
                confidence_score=0.7,
                is_ai_generated=True,
                is_reviewed=False,
                source_record_ids=[document.id],
            )
            db.add(rel)
            relationships_created += 1

    db.commit()

    try:
        run_all_detections(db)
    except Exception:
        pass

    log_audit(db, current_user.id, "upload_social_media", "document", document.id,
              {"platform": platform, "entities": entities_created})

    return {
        "document_id": document.id,
        "platform": platform,
        "entities_extracted": entities_created,
        "relationships_created": relationships_created,
        "social_handles_found": len([se for se in social_entities if se["type"] == "social_media_handle"]),
    }


@router.get("/jobs/{case_id}")
def get_jobs(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = db.query(IngestionJob).filter(
        IngestionJob.case_id == case_id
    ).order_by(IngestionJob.created_at.desc()).limit(50).all()

    return [{
        "id": job.id,
        "status": job.status.value,
        "entities_extracted": job.entities_extracted,
        "relationships_created": job.relationships_created,
        "errors": job.errors or [],
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    } for job in jobs]
