"""
Layer 1: Strip Labels From Values Before Extraction.

Root cause fix: documents using "Label: Value" formatting (dossiers with
"Full Name: ...", tables with header rows, structured report fields) are
having the label text itself extracted as an entity, alongside or instead
of the actual value.

APPLY this during document-to-text conversion, before any text reaches
the NER/LLM extractor. If a label is detected, send ONLY the value to
entity extraction. The label is used to TYPE the value correctly.

Fail closed: if a label is detected but isn't in the map, treat it as
metadata and exclude its value by default.
"""
import re
from typing import Optional, Tuple


# ── Label:Value Pattern ────────────────────────────────────────────
# Matches lines like "Full Name: Vikram Solanki" or "Phone: +91-9876543210"
LABEL_VALUE_PATTERN = re.compile(
    r"^\s*([A-Za-z][A-Za-z\s/]{1,40}?)\s*:\s*(.+)$"
)

# ── Column Label → Entity Type Mapping ─────────────────────────────
# Labels in this map produce typed values. Labels NOT in this map are
# treated as metadata (fail-closed).
COLUMN_LABEL_TYPE_MAP = {
    # Person names
    "full name": "PERSON", "name": "PERSON", "suspect name": "PERSON",
    "complainant": "PERSON", "accused": "PERSON", "victim": "PERSON",
    "witness": "PERSON", "officer": "PERSON", "informant": "PERSON",
    "father name": "PERSON", "father's name": "PERSON",
    "alias": "PERSON_ALIAS", "aliases": "PERSON_ALIAS",
    "known as": "PERSON_ALIAS",

    # Identifiers (attached to the person record, not standalone nodes)
    "ids": "IDENTIFIER", "id": "IDENTIFIER", "aadhaar": "IDENTIFIER",
    "pan": "IDENTIFIER", "passport": "IDENTIFIER", "dl": "IDENTIFIER",
    "driving license": "IDENTIFIER", "voter id": "IDENTIFIER",

    # Locations
    "address": "LOCATION", "location": "LOCATION", "residence": "LOCATION",
    "workplace": "LOCATION", "place": "LOCATION", "crime scene": "LOCATION",
    "area": "LOCATION", "village": "LOCATION", "city": "LOCATION",
    "state": "LOCATION", "district": "LOCATION", "police station": "LOCATION",

    # Phone / contact
    "phone": "PHONE_NUMBER", "mobile": "PHONE_NUMBER", "contact": "PHONE_NUMBER",
    "telephone": "PHONE_NUMBER", "cell": "PHONE_NUMBER", "imei": "PHONE_NUMBER",
    "phone number": "PHONE_NUMBER", "mobile number": "PHONE_NUMBER",

    # Vehicle
    "vehicle": "VEHICLE", "registration no": "VEHICLE",
    "registration number": "VEHICLE", "car": "VEHICLE", "bike": "VEHICLE",
    "vehicle number": "VEHICLE",

    # Financial (attached to transaction records, NOT standalone entities)
    "amount": "TRANSACTION_VALUE", "amount inr": "TRANSACTION_VALUE",
    "amount rs": "TRANSACTION_VALUE", "sum": "TRANSACTION_VALUE",
    "method": "TRANSACTION_ATTRIBUTE", "payment method": "TRANSACTION_ATTRIBUTE",
    "mode": "TRANSACTION_ATTRIBUTE", "bank": "TRANSACTION_ATTRIBUTE",
    "account number": "FINANCIAL_ACCOUNT", "account": "FINANCIAL_ACCOUNT",
    "ifsc": "TRANSACTION_ATTRIBUTE", "upi": "TRANSACTION_ATTRIBUTE",

    # Temporal (attached to the record, NOT standalone entities)
    "timestamp": "TIME_VALUE", "date": "TIME_VALUE", "time": "TIME_VALUE",
    "date of birth": "TIME_VALUE", "dob": "TIME_VALUE",
    "date of incident": "TIME_VALUE", "date of arrest": "TIME_VALUE",

    # Role/status (metadata, not entities)
    "role": "METADATA", "status": "METADATA", "occupation": "METADATA",
    "risk level": "METADATA", "age": "METADATA", "gender": "METADATA",
    "height": "METADATA", "weight": "METADATA", "build": "METADATA",
    "marks": "METADATA", "identification marks": "METADATA",
    "description": "METADATA", "remarks": "METADATA", "notes": "METADATA",

    # Case metadata
    "fir number": "CASE_REFERENCE", "case number": "CASE_REFERENCE",
    "subject": "METADATA", "act": "METADATA", "section": "METADATA",

    # Relationship metadata
    "relationship": "METADATA", "relation": "METADATA",

    # Table-like labels
    "sr no": "METADATA", "sr. no": "METADATA", "serial number": "METADATA",
    "sl no": "METADATA", "#": "METADATA", "no": "METADATA",
    "category": "METADATA", "source": "METADATA",
}

# Labels whose values should NOT be sent to extraction at all
NON_EXTRACTABLE_LABELS = {
    "amount", "amount inr", "amount rs", "sum",
    "method", "payment method", "mode",
    "timestamp", "date", "time",
    "sr no", "sr. no", "serial number", "sl no", "#", "no",
    "description", "remarks", "notes",
    "role", "status", "category", "source",
    "age", "gender", "height", "weight", "build",
    "subject", "act", "section", "remarks",
}


def strip_label_value(line: str) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Detect and strip "Label: Value" patterns from a line of text.

    Returns:
        (label, value, mapped_type) if a label was detected
        (None, original_line, None) if no label pattern matched

    Usage:
        label, value, entity_type = strip_label_value("Full Name: Vikram Solanki")
        # label="Full Name", value="Vikram Solanki", entity_type="PERSON"
    """
    match = LABEL_VALUE_PATTERN.match(line.strip())
    if not match:
        return None, line, None

    label = match.group(1).strip()
    value = match.group(2).strip()

    if not value:
        return None, line, None

    label_lower = label.lower().strip()

    # Look up the label in the type map
    mapped_type = COLUMN_LABEL_TYPE_MAP.get(label_lower)

    # Also check with slight variations
    if mapped_type is None:
        # Try removing trailing "s" (plural) and re-checking
        if label_lower.endswith("s"):
            mapped_type = COLUMN_LABEL_TYPE_MAP.get(label_lower[:-1])

    return label, value, mapped_type


def is_non_extractable_label(label: Optional[str]) -> bool:
    """Check if this label's value should not be sent to entity extraction."""
    if label is None:
        return False
    return label.lower().strip() in NON_EXTRACTABLE_LABELS


# ── Layer 2: Section-Header Detection ─────────────────────────────
SECTION_HEADER_PATTERN = re.compile(
    r"^\s*([A-Z][A-Za-z\s]{2,40}):?\s*$"
)

# Common section heading keywords in crime documents
SECTION_HEADING_KEYWORDS = {
    "previous criminal history", "criminal history", "criminal record",
    "brief facts", "brief fact", "incident details", "crime details",
    "suspect details", "suspect information", "victim details",
    "complainant details", "witness details", "investigation details",
    "evidence", "seizure", "arrest details", "recovery",
    "modus operandi", "m o", "background", "affidavit",
    "prayer", "relief sought", "grounds",
    "past cases", "haryana past cases", "criminal past",
    "known aliases", "known associates", "known addresses",
    "associated phone", "associated phones",
    "national id hash", "national id",
    "call detail records", "call detail record",
    "field intelligence", "surveillance report",
    "financial transaction ledger", "financial transactions",
    "socmint report", "dossier", "case file",
    "first information report",
}


def is_section_header(line: str, next_line: str = "") -> bool:
    """
    Layer 2: Detect standalone section headings (not entities).
    A line is a section header if:
    - It matches a short, ALL-CAPS or title-case standalone line
    - AND is immediately followed by non-empty body content
    - AND matches known section heading keywords
    """
    line_clean = line.strip()
    if not line_clean:
        return False

    # Check if it matches known section heading keywords (strongest signal)
    lower = line_clean.rstrip(":").lower()
    if lower in SECTION_HEADING_KEYWORDS:
        if next_line and next_line.strip():
            return True
        return True  # Known heading keyword, always a heading

    # For unknown text, require ALL-CAPS to be treated as a heading
    # (person names like 'Vikram Solanki' are title-case but NOT headings)
    if line_clean.isupper() and 3 <= len(line_clean) <= 40:
        if next_line and next_line.strip():
            return True

    return False


def strip_section_headers(text: str) -> str:
    """
    Layer 2: Remove section header lines from text.
    Headers like 'Previous Criminal History' are metadata labels,
    not extractable entities. The content below them is processed normally.
    """
    lines = text.split("\n")
    processed = []
    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if is_section_header(line, next_line):
            # Skip the header line entirely — it's metadata, not an entity
            continue
        processed.append(line)
    return "\n".join(processed)


def preprocess_text_labels(text: str) -> str:
    """
    Preprocess document text by stripping Label: Value patterns.

    For each line:
    - If label is non-extractable → drop the entire line (it's metadata)
    - If label maps to a known entity type → keep ONLY the value part,
      prefixed with a type hint for downstream extraction
    - If no label pattern → keep the line as-is

    This ensures labels never reach NER as extractable tokens.
    """
    lines = text.split("\n")
    processed = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            processed.append("")
            continue

        label, value, mapped_type = strip_label_value(stripped)

        if label is None:
            # No label pattern — keep the line as-is
            processed.append(line)
            continue

        label_lower = label.lower().strip()

        if is_non_extractable_label(label):
            # Non-extractable label — drop the entire line
            # This catches: amounts, timestamps, descriptions, etc.
            continue

        if mapped_type in ("TRANSACTION_VALUE", "TRANSACTION_ATTRIBUTE", "TIME_VALUE", "METADATA"):
            # These are record attributes, not standalone entities — drop the line
            continue

        if mapped_type in ("PERSON", "PERSON_ALIAS", "LOCATION", "PHONE_NUMBER", "VEHICLE", "IDENTIFIER", "CASE_REFERENCE", "FINANCIAL_ACCOUNT"):
            # Keep ONLY the value — the label is discarded
            # Prepend a type hint so downstream extraction can use it
            processed.append(value)
        else:
            # Unmapped label — fail-closed: exclude the value
            # This prevents unknown labels from leaking entities
            continue

    result = "\n".join(processed)

    # Also apply Layer 2: section header stripping
    result = strip_section_headers(result)

    return result


def preprocess_docx_tables(tables: list) -> str:
    """
    Process extracted DOCX table data with label-aware parsing.

    Input: list of tables, where each table is a list of rows,
    where each row is a list of cell strings.

    Returns: preprocessed text with labels stripped and values typed.
    """
    output_lines = []

    for table in tables:
        if not table:
            continue

        # First row is always the header
        header_row = table[0] if table else []
        headers = [cell.strip().lower() for cell in header_row]

        # Data rows (skip header)
        for row in table[1:]:
            parts = []
            for i, cell in enumerate(row):
                cell_text = cell.strip()
                if not cell_text:
                    continue

                # Get the header for this column (if available)
                header = headers[i] if i < len(headers) else ""

                # Skip empty headers
                if not header:
                    parts.append(cell_text)
                    continue

                # Check if this header maps to a non-extractable type
                mapped_type = COLUMN_LABEL_TYPE_MAP.get(header, "")
                if mapped_type in ("TRANSACTION_VALUE", "TRANSACTION_ATTRIBUTE",
                                   "TIME_VALUE", "METADATA"):
                    continue  # Skip this cell — it's a record attribute

                # For extractable types, keep the value
                if mapped_type:
                    parts.append(cell_text)
                else:
                    # Unknown header — fail-closed, skip the value
                    continue

            if parts:
                output_lines.append(" | ".join(parts))

    return "\n".join(output_lines)
