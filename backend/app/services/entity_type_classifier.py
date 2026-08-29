"""
Entity Type Classifier — Strict Taxonomy Enforcement

Every extracted item must pass through this classifier before entering
the entity store. Items on the exclusion list are NEVER promoted to
graph nodes or appear in Common Link / Threat Assessment / People Graph.

This is a lead-generation tool, NOT an automated accusation system.
"""
from __future__ import annotations
import re
from typing import Optional


# ── Valid Entity Types (closed set) ────────────────────────────────
VALID_ENTITY_TYPES = {
    "PERSON",           # Named individuals
    "ORGANIZATION",     # Companies, gangs, agencies
    "LOCATION",         # Addresses, places, towers
    "VEHICLE",          # Vehicle registration numbers
    "PHONE_NUMBER",     # Phone/IMEI numbers
    "FINANCIAL_ACCOUNT", # Bank accounts, UPI IDs (the account, not the method)
    "CASE_REFERENCE",   # FIR numbers, case IDs
}


# ── Exclusion Lists ────────────────────────────────────────────────
# Items in these sets must NEVER become standalone graph nodes.
# They are stored as ATTRIBUTES of relationships/records instead.

# Communication platforms / apps → attribute of a communication edge
EXCLUDED_PLATFORMS = {
    "telegram", "whatsapp", "signal", "instagram", "facebook",
    "facebook messenger", "twitter", "snapchat", "discord", "slack",
    "imessage", "facetime", "viber", "line", "wechat", "imo",
    "hike", "gpay", "phonepe", "paytm",
    "email", "sms", "text message", "voice call", "video call",
    "x",  # Twitter/X — platform, not an entity
    "gmail",  # Email service, not a person
}

# Payment methods / rails → attribute of a financial transaction edge
EXCLUDED_PAYMENT_METHODS = {
    "neft", "rtgs", "imps", "upi", "cash", "cheque", "check",
    "demand draft", "dd", "hawala", "crypto", "bitcoin",
    "transfer", "wire transfer", "bank transfer", "online transfer",
    "atm withdrawal", "credit card", "debit card", "net banking",
}

# Generic offense/case-type labels → property of the CASE, not entities
EXCLUDED_OFFENSE_LABELS = {
    "assault", "fraud", "extortion", "murder", "robbery", "theft",
    "burglary", "arson", "kidnapping", "trafficking", "smuggling",
    "ndps", "bribery", "corruption", "cybercrime", "forgery",
    "dacoity", "riot", "attempt to murder", "culpable homicide",
    "cheating", "criminal intimidation", "house trespass",
    "extortion", "murder", "robbery", "theft",
}

# Table header patterns — never extract these as entities
EXCLUDED_HEADER_PATTERNS = re.compile(
    r'^(?:txn|transaction|sr\.?\s*no|serial|amount|date|time|timestamp|'
    r'duration|reference|ref|id|number|status|type|mode|method|'
    r'from|to|sender|receiver|caller|callee|balance|debit|credit|'
    r'amount_inr|amount_rs|phone_number|cell_tower|location_lat|'
    r'location_lng|description|remarks|notes|source|category|'
    r'victim|accused|complainant|investigating|officer|'
    r'name|age|gender|address|occupation|risk_level|'
    r'state|district|police_station|fir_number|'
    r'signature|overkill|staging|approach|control|weapon|'
    r'latitude|longitude|tower_id|imei|call_duration|'
    r'bank_name|account_number|ifsc|branch)$',
    re.IGNORECASE
)

# Document section headers — these are structural labels, not entities
EXCLUDED_SECTION_HEADERS = {
    'call detail records', 'call detail record', 'cdr',
    'field intelligence / surveillance', 'field intelligence',
    'surveillance report', 'surveillance',
    'financial transaction ledger', 'financial transactions',
    'financial ledger', 'transaction ledger',
    'socmint report', 'socmint',
    'police master database dossier', 'master database dossier',
    'dossier', 'case file',
    'first information report', 'fir',
    'haryana past cases', 'past cases', 'criminal history',
    'known addresses', 'known aliases', 'known associates',
    'associated phone', 'associated phones',
    'national id hash', 'national id', 'aadhaar hash',
    'physical surveillance', 'recent posts',
    'brief facts', 'incident details', 'crime details',
    'suspect details', 'victim details', 'witness details',
    'complainant details', 'investigation details',
    'evidence', 'seizure', 'arrest details', 'recovery',
    'modus operandi', 'background',
}

# Generic metadata terms that appear as standalone extracted entities
EXCLUDED_METADATA_TERMS = {
    'ids', 'id', 'fifth', 'the bharat', 'the bharatiya',
    'transit house', 'house', 'street', 'road',
    'b-12', 'a-1', 'c-3',  # flat/apartment numbers without context
    'full name', 'first name', 'last name',
    'contact number', 'phone number', 'mobile number',
    'associated phone', 'call detail',
    'past cases', 'haryana past cases',
    'username', 'user id', 'user name',
}

# Indian law/statute names — legal references, not graph nodes
EXCLUDED_STATUTE_NAMES = {
    'bharatiya', 'bharatiya nyaya', 'bharatiya nagarik',
    'immoral traffic', 'narcotic drugs', 'psychotropic',
    'sohna road industrial',
}


# ── Platform/Method Pattern (for detection in text) ────────────────
# Detects platform names mentioned in text context (not as entities)
_PLATFORM_CONTEXT = re.compile(
    r'(?:via|through|on|using|using)\s+(?:'
    + '|'.join(re.escape(p) for p in EXCLUDED_PLATFORMS)
    + r')\b',
    re.IGNORECASE
)


def classify_entity_type(
    raw_text: str,
    spaCy_label: Optional[str] = None,
    source_context: str = "general",
) -> Optional[str]:
    """
    Classify extracted text into a valid entity type, or return None
    if it should be excluded entirely.

    Returns: One of VALID_ENTITY_TYPES strings, or None if excluded.
    """
    text = raw_text.strip()
    text_lower = text.lower()

    # ── 1. Check exclusion lists first ─────────────────────────────
    if text_lower in EXCLUDED_PLATFORMS:
        return None  # Platform name — never a node
    if text_lower in EXCLUDED_PAYMENT_METHODS:
        return None  # Payment method — never a node
    if text_lower in EXCLUDED_OFFENSE_LABELS:
        return None  # Offense label — property of the case, not a node
    if text_lower in EXCLUDED_SECTION_HEADERS:
        return None  # Document section header — structural label
    if text_lower in EXCLUDED_METADATA_TERMS:
        return None  # Generic metadata term — not an entity
    # Check statute/law names (partial match since they're often long)
    for statute in EXCLUDED_STATUTE_NAMES:
        if statute in text_lower:
            return None  # Legal statute reference — not an entity

    # ── 2. Check for table headers ─────────────────────────────────
    if EXCLUDED_HEADER_PATTERNS.match(text_lower):
        return None  # Column header — not an entity

    # Check if it looks like a generic snake_case or label-like metadata
    if re.match(r'^[a-z_]+(_[a-z_]+)+$', text_lower):
        return None  # snake_case metadata field name
    if re.match(r'^[A-Z][A-Z_]+$', text):
        return None  # ALL_CAPS header label

    # Multi-word ALL CAPS or Title Case that looks like a section header
    if text.isupper() and len(text) > 10:
        return None  # ALL_CAPS phrase — likely a section header

    # ── 3. Platform names in context (e.g., "via Telegram") ────────
    # These should be attributes, not entities
    for platform in EXCLUDED_PLATFORMS:
        if text_lower == platform:
            return None

    # ── 4. Route to valid type based on patterns + spaCy label ─────

    # Phone number pattern
    if re.match(r'^\d{7,15}$', text.replace(' ', '').replace('-', '').replace('+', '')):
        return "PHONE_NUMBER"

    # Vehicle pattern (Indian: MH-12-AB-1234)
    if re.match(r'^[A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{1,4}$', text.upper()):
        return "VEHICLE"

    # FIR / Case reference
    if re.match(r'(?:FIR|Case|CrPC|IPC)\s*[/-]?\s*\d', text, re.IGNORECASE):
        return "CASE_REFERENCE"

    # Financial account (bank account number, UPI ID — but not payment method)
    if re.match(r'^\d{9,18}$', text.replace(' ', '')):
        return "FINANCIAL_ACCOUNT"  # Could be account number
    if re.match(r'^[\w.+-]+@[\w]+$', text):  # UPI-style
        return "FINANCIAL_ACCOUNT"

    # ── 5. Use spaCy label for NER results ─────────────────────────
    if spaCy_label:
        if spaCy_label in ("PERSON", "PER"):
            return "PERSON"
        elif spaCy_label in ("GPE", "LOC", "FAC", "LOC"):
            return "LOCATION"
        elif spaCy_label in ("ORG",):
            # But first check if it's actually a platform
            if text_lower in EXCLUDED_PLATFORMS or text_lower in EXCLUDED_OFFENSE_LABELS:
                return None
            return "ORGANIZATION"
        elif spaCy_label in ("NORP",):
            # NORP = nationalities, religious/political groups
            # These can be organizations in crime context
            if text_lower in EXCLUDED_OFFENSE_LABELS:
                return None
            return "ORGANIZATION"

    # ── 6. Heuristic fallbacks ─────────────────────────────────────
    # If it looks like a person name (capitalized words, reasonable length)
    words = text.split()
    if 1 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
        # Could be a person name — but check it's not a platform/method
        if text_lower not in EXCLUDED_PLATFORMS and text_lower not in EXCLUDED_PAYMENT_METHODS:
            return "PERSON"

    # If it looks like a location (contains common Indian location words)
    location_words = {'road', 'street', 'nagar', 'colony', 'sector', 'block',
                      'district', 'police', 'station', 'camp', 'market',
                      'bazaar', 'mandi', 'extension', 'layout', 'puram',
                      'ville', 'abad', 'garh', 'ganj', 'pura'}
    if any(w.lower() in location_words for w in words):
        return "LOCATION"

    return None  # Default: exclude — don't create a node for ambiguous tokens


# ── Layer 0: General Entity Sanity Validation ────────────────────
def fails_basic_sanity(text: str) -> bool:
    """
    Catches malformed/corrupted entity strings regardless of specific bug.
    Apply BEFORE any type-specific logic.
    """
    text = text.strip()
    if len(text) < 2 or len(text) > 60:
        return True
    # Mostly non-alphanumeric (garbled/corrupted extraction)
    alnum_ratio = sum(c.isalnum() or c.isspace() for c in text) / max(len(text), 1)
    if alnum_ratio < 0.6:
        return True
    # Ends in a colon (section header leaking through)
    if text.rstrip().endswith(":"):
        return True
    # Repeated word fragments (e.g., "Tower Legend Tower" pattern)
    words = text.lower().split()
    if len(words) >= 2 and len(set(words)) < len(words):
        return True
    return False


def normalize_dedup_key(text: str) -> str:
    """
    Normalize text for deduplication matching.
    Lowercases, strips trailing punctuation, collapses whitespace.
    Fixes 'Previous Criminal History' vs 'Previous Criminal History:' duplicates.
    """
    import unicodedata
    t = text.strip().lower()
    # Strip trailing punctuation
    import string
    t = t.rstrip(string.punctuation)
    # Collapse whitespace
    t = " ".join(t.split())
    # Normalize unicode
    t = unicodedata.normalize("NFKD", t)
    return t


def looks_like_schema_artifact(text: str) -> bool:
    """
    Detect if text looks like a table header, field label, or metadata key.
    Returns True if the text matches common schema artifact patterns:
    - snake_case (e.g., "amount_inr", "phone_number")
    - camelCase (e.g., "cellTower")
    - ALL_CAPS labels (e.g., "TOWER_ID")
    """
    t = text.strip()
    t_lower = t.lower()

    # snake_case: "amount_inr", "cell_tower"
    if re.match(r'^[a-z]+(_[a-z0-9]+)+$', t_lower):
        return True
    # camelCase: "cellTower", "phoneNumber"
    if re.match(r'^[a-z]+([A-Z][a-z0-9]*)+$', t):
        return True
    # ALL_CAPS with underscores: "TOWER_ID"
    if re.match(r'^[A-Z]+(_[A-Z0-9]+)+$', t):
        return True
    # ALL_CAPS short labels: "FIR", "CDR", "NDPS"
    if re.match(r'^[A-Z]{2,8}$', t):
        # These could be acronyms — check if they're in offense list
        if t_lower in EXCLUDED_OFFENSE_LABELS:
            return True
        # Leave short acronyms that aren't offenses (like FIR) as-is
        return False

    return False


# ── Review Queue ───────────────────────────────────────────────────
# Denied entities go here, not silent deletion.
_review_queue: list[dict] = []

def send_to_review_queue(entity) -> None:
    """
    Add a denied entity to the review queue instead of silently dropping it.
    This ensures nothing legitimate is lost by mistake.
    """
    _review_queue.append({
        "text": getattr(entity, 'text', str(entity)),
        "type": getattr(entity, 'type', 'UNKNOWN'),
        "reason": "excluded_by_classifier",
    })


def get_review_queue() -> list[dict]:
    """Return and clear the review queue."""
    items = _review_queue.copy()
    _review_queue.clear()
    return items


def commit_entity(entity) -> bool:
    """
    Gate function: should this entity be stored in the graph?

    No entity reaches the graph store without passing through this gate.
    Denied items go to a review queue, not silent deletion.

    Returns True if the entity should be stored, False if denied.
    """
    text = getattr(entity, 'text', str(entity)).strip()
    # Normalize BEFORE any comparison (Layer 4 fix)
    normalized = normalize_dedup_key(text)
    entity_type = getattr(entity, 'type', 'UNKNOWN')

    # ── Layer 0: General sanity check ──────────────────────────────
    if fails_basic_sanity(text):
        send_to_review_queue(entity)
        return False

    # Check: is the entity type in the allowed set?
    if entity_type not in VALID_ENTITY_TYPES:
        send_to_review_queue(entity)
        return False

    # Check: is the token a platform, payment method, or offense label?
    if normalized in (EXCLUDED_PLATFORMS
                      | EXCLUDED_PAYMENT_METHODS
                      | EXCLUDED_OFFENSE_LABELS):
        send_to_review_queue(entity)
        return False

    # Check: does it look like a schema artifact?
    if looks_like_schema_artifact(text):
        send_to_review_queue(entity)
        return False

    # Passed all checks — safe to store
    return True


def is_excluded_token(text: str) -> bool:
    """Quick check: should this token be excluded from entity extraction entirely?"""
    text_stripped = text.strip()
    text_lower = text_stripped.lower()
    # Layer 0: sanity check first
    if fails_basic_sanity(text_stripped):
        return True
    return bool(
        text_lower in EXCLUDED_PLATFORMS
        or text_lower in EXCLUDED_PAYMENT_METHODS
        or text_lower in EXCLUDED_OFFENSE_LABELS
        or text_lower in EXCLUDED_SECTION_HEADERS
        or text_lower in EXCLUDED_METADATA_TERMS
        or any(s in text_lower for s in EXCLUDED_STATUTE_NAMES)
        or EXCLUDED_HEADER_PATTERNS.match(text_lower)
        or re.match(r'^[a-z_]+(_[a-z_]+)+$', text_lower)
        or re.match(r'^[A-Z][A-Z_]+$', text_stripped)
        or (text_stripped.isupper() and len(text_stripped) > 10)
        or looks_like_schema_artifact(text_stripped)
    )


def is_partial_name(name: str) -> bool:
    """
    Detect if a name is partial (surname-only or first-name-only).
    Returns True if the name is likely incomplete.
    """
    name = name.strip()
    words = name.split()

    # Single word — could be surname-only
    if len(words) == 1:
        return True

    # Two words where one is very short (initial)
    if len(words) == 2 and any(len(w) <= 2 for w in words):
        # Could be initials — still flag as potentially partial
        return False  # Two-word names with initials are usually OK

    # Very short total character count
    if len(name) < 4:
        return True

    return False


def validate_entity_name(name: str, entity_type: str) -> tuple[bool, str]:
    """
    Validate that an entity name is suitable for storage.
    Returns (is_valid, reason_if_invalid).
    """
    if not name or not name.strip():
        return False, "Empty name"

    name = name.strip()

    # Check exclusions
    if is_excluded_token(name):
        return False, f"Excluded token: {name} is a platform/method/metadata label"

    # Check for partial names (person entities only)
    if entity_type == "PERSON" and is_partial_name(name):
        # Allow partial names but flag them
        # They'll be stored with a flag, not merged with others
        return True, "partial_name"

    # Check minimum length
    if len(name) < 2:
        return False, f"Name too short: {name}"

    return True, "ok"
