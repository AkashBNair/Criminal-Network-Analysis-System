"""
NLP Entity Extraction Service.
Uses regex patterns + spaCy NER for extracting entities from unstructured text.

Every extracted entity passes through entity_type_classifier.validate_entity_name()
before being returned. Tokens from the exclusion list (platforms, payment methods,
table headers, metadata labels) are NEVER promoted to graph nodes.

This is a lead-generation tool, NOT an automated accusation system.
"""
import re, logging
import spacy
from typing import Optional

logger = logging.getLogger(__name__)
from app.models.models import EntityType
from app.services.entity_type_classifier import (
    classify_entity_type, is_excluded_token, validate_entity_name, commit_entity,
    looks_like_schema_artifact, EXCLUDED_PLATFORMS, EXCLUDED_PAYMENT_METHODS,
    EXCLUDED_HEADER_PATTERNS,
)
from app.services.label_stripper import strip_label_value, is_non_extractable_label
from app.services.entity_type_classifier import normalize_dedup_key
from app.services.llm_entity_validator import validate_entity_candidate

# Load spaCy model (small English model for hackathon)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = spacy.blank("en")


# Regex patterns for entity extraction
PHONE_PATTERN = re.compile(
    r'(?:\+91[-\s]?)?(?:0)?([6-9]\d{9})\b|'
    r'(\d{3}[-.\s]\d{3}[-.\s]\d{4})\b|'
    r'(\(\d{3}\)\s*\d{3}[-.\s]\d{4})',
    re.IGNORECASE
)

VEHICLE_PATTERN = re.compile(
    r'\b([A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{1,4})\b|'
    r'\b(\d{1,2}[-][A-Z]{3}[-]\d{4})\b',
    re.IGNORECASE
)

DATE_PATTERN = re.compile(
    r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b|'
    r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b|'
    r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',
    re.IGNORECASE
)

AMOUNT_PATTERN = re.compile(
    r'(?:₹|Rs\.?|INR|USD|\$)\s*([\d,]+(?:\.\d{2})?)',
    re.IGNORECASE
)

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')


class ExtractedEntity:
    def __init__(self, name: str, entity_type: EntityType, confidence: float,
                 attributes: dict = None, source_text: str = ""):
        self.name = name
        self.entity_type = entity_type
        self.confidence = confidence
        self.attributes = attributes or {}
        self.source_text = source_text


# ── Layer 5: Alias Detection Patterns ─────────────────────────────
# Detects explicit alias relationships in source text.
ALIAS_PATTERNS = [
    # "X, alias Y" / "X, aliases Y"
    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*,\s*alias(?:es)?\s+([A-Z][a-zA-Z\s]+)', re.IGNORECASE),
    # "X aka Y" / "X a.k.a. Y"
    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:aka|a\.k\.a\.)\s+([A-Z][a-zA-Z\s]+)', re.IGNORECASE),
    # "X, also known as Y"
    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*,?\s+also\s+known\s+as\s+([A-Z][a-zA-Z\s]+)', re.IGNORECASE),
    # "X @Y" or "X (Y)" after a name line in dossier format
    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\(([A-Z][a-zA-Z\s]+)\)\s*$', re.MULTILINE),
]


def detect_alias_pairs(text: str) -> list[tuple[str, str]]:
    """
    Layer 5: Detect explicit alias relationships in source text.
    Returns list of (primary_name, alias_name) pairs.
    """
    pairs = []
    for pattern in ALIAS_PATTERNS:
        for match in pattern.finditer(text):
            primary = match.group(1).strip()
            alias = match.group(2).strip()
            if primary and alias and len(primary) > 2 and len(alias) > 1:
                pairs.append((primary, alias))
    return pairs


def extract_entities_from_text(text: str, document_type: str = "general") -> list[ExtractedEntity]:
    """
    Extract entities from unstructured text using regex patterns and spaCy NER.
    Returns a list of ExtractedEntity objects.

    EXCLUSION ENFORCEMENT:
    - Financial amounts are NOT extracted as standalone entities (record metadata only)
    - Emails are stored as PHONE/CONTACT type, NOT as PERSON
    - spaCy NER results pass through entity_type_classifier which rejects
      platforms, payment methods, headers, and metadata labels
    """
    entities = []
    seen = set()

    # 1. Phone number extraction (high confidence - regex is reliable)
    for match in PHONE_PATTERN.finditer(text):
        phone = None
        for group in match.groups():
            if group:
                cleaned = re.sub(r'[^\d]', '', group)
                if len(cleaned) >= 10:
                    phone = cleaned[-10:]
                    break
        if phone and phone not in seen:
            seen.add(phone)
            entities.append(ExtractedEntity(
                name=phone,
                entity_type=EntityType.PHONE,
                confidence=0.95,
                attributes={"raw_match": match.group().strip()},
                source_text=match.group().strip()
            ))

    # 2. Vehicle registration extraction
    for match in VEHICLE_PATTERN.finditer(text):
        vehicle = match.group().strip()
        if vehicle and vehicle not in seen and len(vehicle) >= 6:
            seen.add(vehicle)
            entities.append(ExtractedEntity(
                name=vehicle.upper(),
                entity_type=EntityType.VEHICLE,
                confidence=0.90,
                attributes={"raw_match": match.group().strip()},
                source_text=match.group().strip()
            ))

    # 3. Date extraction
    for match in DATE_PATTERN.finditer(text):
        date_str = match.group().strip()
        if date_str and date_str not in seen:
            seen.add(date_str)
            entities.append(ExtractedEntity(
                name=date_str,
                entity_type=EntityType.DATE,
                confidence=0.85,
                attributes={"raw_match": match.group().strip()},
                source_text=match.group().strip()
            ))

    # 4. Financial amounts — NOT extracted as standalone entities.
    # Amounts are data values belonging to transaction records.
    # They are stored as attributes on relationships/documents, not graph nodes.
    for match in AMOUNT_PATTERN.finditer(text):
        amount = match.group(1).replace(',', '')
        if amount and f"AMOUNT:{amount}" not in seen:
            seen.add(f"AMOUNT:{amount}")
            # Intentionally NOT creating an entity node for monetary amounts.

    # 5. Email addresses — stored as contact info, NOT as PERSON entities
    for match in EMAIL_PATTERN.finditer(text):
        email = match.group().strip()
        if email and email.lower() not in seen:
            seen.add(email.lower())
            entities.append(ExtractedEntity(
                name=email,
                entity_type=EntityType.PHONE,  # Contact info, not a person
                confidence=0.85,
                attributes={"email": email, "type": "email_address"},
                source_text=match.group().strip()
            ))

    # 6. spaCy NER for names, locations, organizations
    # ── Layer 2 denylists (catch platform/payment/offense in narrative text) ──
    LAYER2_PLATFORM_DENYLIST = {
        "telegram", "whatsapp", "signal", "instagram", "facebook",
        "facebook messenger", "snapchat", "wechat", "imo", "sms",
        "email", "twitter", "x", "gmail",
    }
    LAYER2_PAYMENT_DENYLIST = {
        "neft", "rtgs", "upi", "imps", "cash", "hawala", "cheque",
        "check", "demand draft", "dd", "wire transfer", "credit card",
        "debit card",
    }
    LAYER2_OFFENSE_DENYLIST = {
        "ndps", "extortion", "assault", "fraud", "murder", "robbery",
        "theft", "smuggling", "trafficking",
    }

    doc = nlp(text[:50000])  # Limit text length for performance
    for ent in doc.ents:
        name = ent.text.strip()
        if len(name) < 2:
            continue
        # Layer 4: Use normalized dedup key to catch punctuation/case variants
        dedup_key = normalize_dedup_key(name)
        if dedup_key in seen:
            continue

        # ── LAYER 1: Strip residual Label:Value patterns ────────────
        # If the NER picked up a "Label: Value" pair, extract only the value
        if ':' in name:
            label_part, value_part = name.split(':', 1)
            label_part = label_part.strip()
            value_part = value_part.strip()
            if label_part and is_non_extractable_label(label_part):
                continue  # Label is metadata — skip entirely
            if value_part and len(value_part) >= 2:
                name = value_part  # Use only the value part

        # ── CLASSIFY AND FILTER via entity_type_classifier ──────────
        classified_type = classify_entity_type(name, spaCy_label=ent.label_)
        if classified_type is None:
            continue

        # ── LAYER 2: Additional denylist checks ────────────────────
        name_lower = name.lower()
        if name_lower in LAYER2_PLATFORM_DENYLIST:
            continue  # Platform in narrative text — attribute, not entity
        if name_lower in LAYER2_PAYMENT_DENYLIST:
            continue  # Payment method in narrative — attribute, not entity
        if name_lower in LAYER2_OFFENSE_DENYLIST:
            continue  # Offense label — case property, not entity

        # ── LAYER 2: Schema artifact detection ──────────────────────
        if looks_like_schema_artifact(name):
            continue  # snake_case, camelCase, ALL_CAPS header

        # Map classifier output to EntityType enum
        type_map = {
            "PERSON": EntityType.PERSON,
            "LOCATION": EntityType.LOCATION,
            "ORGANIZATION": EntityType.ORGANIZATION,
            "PHONE_NUMBER": EntityType.PHONE,
            "VEHICLE": EntityType.VEHICLE,
            "CASE_REFERENCE": EntityType.EVENT,
            "FINANCIAL_ACCOUNT": EntityType.PHONE,
        }
        entity_type = type_map.get(classified_type)
        if entity_type is None:
            continue

        # Validate the name
        is_valid, reason = validate_entity_name(name, classified_type)
        if not is_valid:
            continue

        # ── LLM contextual validation gate (spaCy NER only) ──────
        # Rejects false positives that pass all structural checks
        # (e.g. "Wolf", "Three" misclassified as PERSON)
        surrounding_text = ent.sent.text if ent.sent else text[max(0, ent.start_char-200):ent.end_char+200]
        llm_verdict = validate_entity_candidate(
            candidate_name=name,
            entity_type_guess=classified_type,
            surrounding_context=surrounding_text,
        )
        if not llm_verdict["is_genuine_entity"]:
            logger.info("Entity REJECTED by LLM gate: '%s' (%s) — %s",
                        name, classified_type, llm_verdict.get("reasoning", ""))
            continue

        attrs = {"role": "mentioned"}
        if reason == "partial_name":
            attrs["partial_identity"] = True
            attrs["partial_reason"] = "Surname-only or single-word name - may represent multiple individuals"
            attrs["resolution_warning"] = "Do not merge with other same-surname entities without corroborating evidence"

        # Store LLM validation metadata
        attrs["extraction_reasoning"] = llm_verdict.get("reasoning", "")
        attrs["llm_confidence"] = llm_verdict.get("confidence", 0)
        attrs["llm_backend"] = llm_verdict.get("backend", "unknown")

        if dedup_key not in seen:
            seen.add(dedup_key)
            # Use LLM confidence instead of hardcoded value
            llm_conf = llm_verdict.get("confidence", 75) / 100.0
            entities.append(ExtractedEntity(
                name=name,
                entity_type=entity_type,
                confidence=llm_conf,
                attributes=attrs,
                source_text=ent.text
            ))

    # ── Layer 5: Merge alias pairs ────────────────────────────────
    # If source text says "X, alias Y", merge Y into X as an alias
    # attribute — don't store Y as a separate entity.
    alias_pairs = detect_alias_pairs(text)
    if alias_pairs:
        alias_map = {}  # alias_lower -> primary_name
        for primary, alias in alias_pairs:
            alias_map[alias.lower().strip()] = primary

        merged_entities = []
        skipped_aliases = set()
        for ent in entities:
            ent_lower = ent.name.lower().strip()
            if ent_lower in alias_map:
                # This entity is an alias — merge into the primary
                primary_name = alias_map[ent_lower]
                skipped_aliases.add(ent_lower)
                # Find or create the primary entity
                primary_found = False
                for existing in merged_entities:
                    if existing.name.lower().strip() == primary_name.lower().strip():
                        # Add this alias to the primary's attributes
                        aliases = existing.attributes.get("aliases", [])
                        if ent.name not in aliases:
                            aliases.append(ent.name)
                        existing.attributes["aliases"] = aliases
                        primary_found = True
                        break
                if not primary_found:
                    # Primary wasn't extracted yet — add the alias as the primary
                    # with the alias name stored as attribute
                    ent.name = primary_name
                    ent.attributes["aliases"] = [ent.name]
                    merged_entities.append(ent)
            else:
                merged_entities.append(ent)
        entities = merged_entities

    return entities


def extract_entities_from_cdr(row: dict) -> list[ExtractedEntity]:
    """
    Extract entities from a CDR (Call Detail Record) row.
    Expected columns: caller, callee, duration, timestamp, cell_tower, etc.
    """
    entities = []
    seen = set()

    caller = str(row.get("caller", row.get("caller_number", ""))).strip()
    callee = str(row.get("callee", row.get("callee_number", ""))).strip()

    for phone in [caller, callee]:
        cleaned = re.sub(r'[^\d]', '', phone)
        if cleaned and cleaned not in seen and len(cleaned) >= 7:
            seen.add(cleaned)
            entities.append(ExtractedEntity(
                name=cleaned,
                entity_type=EntityType.PHONE,
                confidence=1.0,
                attributes={"source": "cdr"},
                source_text=phone
            ))

    return entities


def extract_entities_from_financial(row: dict) -> list[ExtractedEntity]:
    """
    Extract entities from a financial transaction row.
    Only extracts sender/receiver account names — NOT amounts, methods, or references.
    Amounts and payment methods are stored as transaction attributes.
    """
    entities = []
    seen = set()

    for field in ["sender", "receiver", "from_account", "to_account"]:
        val = str(row.get(field, "")).strip()
        if val and val.lower() not in seen:
            # Classify the value — reject if it's a payment method or metadata
            classified = classify_entity_type(val)
            if classified is None:
                continue
            if is_excluded_token(val):
                continue
            seen.add(val.lower())
            entities.append(ExtractedEntity(
                name=val,
                entity_type=EntityType.PERSON,
                confidence=0.90,
                attributes={"field": field, "source": "financial"},
                source_text=val
            ))

    return entities


def extract_entities_from_structured(row: dict, source_type: str = "general") -> list[ExtractedEntity]:
    """
    Extract entities from a structured data row based on source type.

    CRITICAL: Only extract from DATA values in entity-relevant columns.
    Column headers are schema metadata — never extract them as entities.
    Amount, timestamp, duration, reference-number columns produce DATA VALUES
    attached to the record, NOT standalone entities.
    """
    if source_type in ("cdr", "call", "calls"):
        return extract_entities_from_cdr(row)
    elif source_type in ("financial", "transaction", "bank"):
        return extract_entities_from_financial(row)
    else:
        # Generic extraction: scan string values BUT skip headers and metadata fields
        entities = []
        for key, value in row.items():
            # Skip header-like keys
            if is_excluded_token(key):
                continue

            if isinstance(value, str) and value.strip():
                text = value.strip()

                # Skip if the value itself is an excluded token
                if is_excluded_token(text):
                    continue

                # Only extract phone numbers from recognized entity columns
                phone_match = PHONE_PATTERN.search(text)
                if phone_match:
                    for group in phone_match.groups():
                        if group:
                            cleaned = re.sub(r'[^\d]', '', group)
                            if len(cleaned) >= 10:
                                classified = classify_entity_type(cleaned[-10:])
                                if classified == "PHONE_NUMBER":
                                    entities.append(ExtractedEntity(
                                        name=cleaned[-10:],
                                        entity_type=EntityType.PHONE,
                                        confidence=0.90,
                                        attributes={"field": key},
                                        source_text=text
                                    ))
                                break
        return entities
