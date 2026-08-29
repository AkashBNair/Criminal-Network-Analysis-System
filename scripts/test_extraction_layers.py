"""
Layer 8: Regression Test Suite for Entity Extraction Pipeline.

Every bug found in this system becomes a permanent, automatically-run
test case. This stops the whack-a-mole pattern going forward.

Run: cd backend && python -m pytest tests/test_extraction_layers.py -v
"""
import sys
import os
import io

# Ensure UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.services.entity_extraction import extract_entities_from_text
from app.services.entity_type_classifier import (
    fails_basic_sanity, normalize_dedup_key, classify_entity_type,
    commit_entity, looks_like_schema_artifact, is_excluded_token,
)
from app.services.label_stripper import (
    strip_label_value, is_non_extractable_label, preprocess_text_labels,
    is_section_header, strip_section_headers,
)
from app.services.entity_resolution import compute_similarity, _is_partial_name
from app.models.models import Entity, EntityType


def get_entity_names(text, doc_type="dossier"):
    """Extract entity names from text, return as set of (name, type) tuples."""
    entities = extract_entities_from_text(text, doc_type)
    return {(e.name.strip(), e.entity_type.value) for e in entities}


def has_entity_type(entities, name_substr, entity_type):
    """Check if any entity contains the substring and matches the type."""
    return any(
        name_substr.lower() in name.lower() and etype == entity_type
        for name, etype in entities
    )


# ═══════════════════════════════════════════════════════════════════════
# Test Suite
# ═══════════════════════════════════════════════════════════════════════

results = []


def test(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, passed, detail))
    symbol = "+" if passed else "X"
    print(f"  [{symbol}] {name}" + (f" -- {detail}" if detail else ""))


print("=" * 70)
print("LAYER 8: REGRESSION TEST SUITE — Entity Extraction Pipeline")
print("=" * 70)

# ── Test 1: Label:Value stripping (Layer 1) ──────────────────────────
print("\n--- Test 1: Label:Value Stripping (Layer 1) ---")
label, value, mapped = strip_label_value("Full Name: Ajay Malhotra")
test(
    "T1a: 'Full Name: Ajay Malhotra' → label='Full Name', value='Ajay Malhotra'",
    label == "Full Name" and value == "Ajay Malhotra" and mapped == "PERSON",
    f"label={label}, value={value}, type={mapped}"
)
test(
    "T1b: Label 'Full Name' is NOT non-extractable",
    not is_non_extractable_label("Full Name"),
)
test(
    "T1c: Label 'Amount' IS non-extractable",
    is_non_extractable_label("Amount"),
)
entities = get_entity_names("Full Name: Ajay Malhotra\nPhone: +91-9876543210")
test(
    "T1d: Extracting 'Full Name: Ajay Malhotra' yields only 'Ajay Malhotra' as PERSON",
    has_entity_type(entities, "Ajay Malhotra", "Person"),
)

# ── Test 2: Table header exclusion (Layer 3a) ─────────────────────────
print("\n--- Test 2: Table Header Exclusion (Layer 3a) ---")
test(
    "T2a: 'amount_inr' is excluded token",
    is_excluded_token("amount_inr"),
)
test(
    "T2b: 'phone_number' is excluded token",
    is_excluded_token("phone_number"),
)
test(
    "T2c: 'cell_tower' is excluded token",
    is_excluded_token("cell_tower"),
)
test(
    "T2d: Snake_case schema artifacts detected",
    looks_like_schema_artifact("amount_inr"),
)
test(
    "T2e: camelCase schema artifacts detected",
    looks_like_schema_artifact("cellTower"),
)
test(
    "T2f: ALL_CAPS schema artifacts detected",
    looks_like_schema_artifact("TOWER_ID"),
)

# ── Test 3: Section header stripping (Layer 2) ────────────────────────
print("\n--- Test 3: Section Header + Block Text Stripping (Layer 2) ---")
test(
    "T3a: 'Previous Criminal History' detected as section header",
    is_section_header("Previous Criminal History", "He was previously arrested"),
)
test(
    "T3b: 'Previous Criminal History:' with colon detected",
    is_section_header("Previous Criminal History:", "He was previously arrested"),
)
test(
    "T3c: Normal person name is NOT a section header",
    not is_section_header("Vikram Solanki", "is a suspect"),
)
test(
    "T3d: Section header stripped from text",
    "Criminal History" not in strip_section_headers(
        "Previous Criminal History\nHe was arrested in 2020 for theft"
    ),
)

# ── Test 4: Platform denylist (Layer 4) ──────────────────────────────
print("\n--- Test 4: Platform Denylist (Layer 4) ---")
entities = get_entity_names(
    "The accused contacted the victim via Telegram and WhatsApp."
    "He sent messages on Signal and Instagram."
)
test(
    "T4a: 'Telegram' NOT extracted as entity",
    not has_entity_type(entities, "Telegram", "Person"),
)
test(
    "T4b: 'WhatsApp' NOT extracted as entity",
    not has_entity_type(entities, "WhatsApp", "Person"),
)
test(
    "T4c: 'Signal' NOT extracted as entity",
    not has_entity_type(entities, "Signal", "Person"),
)
test(
    "T4d: 'Instagram' NOT extracted as entity",
    not has_entity_type(entities, "Instagram", "Person"),
)

# ── Test 5: Payment method denylist (Layer 4) ────────────────────────
print("\n--- Test 5: Payment Method Denylist (Layer 4) ---")
entities = get_entity_names(
    "Payment was made through NEFT and RTGS. Cash was also used."
    "He transferred via UPI and demand draft."
)
test(
    "T5a: 'NEFT' NOT extracted as entity",
    not has_entity_type(entities, "NEFT", "Person"),
)
test(
    "T5b: 'Cash' NOT extracted as entity",
    not has_entity_type(entities, "Cash", "Person"),
)
test(
    "T5c: 'UPI' NOT extracted as entity",
    not has_entity_type(entities, "UPI", "Person"),
)

# ── Test 6: Offense label denylist (Layer 4) ─────────────────────────
print("\n--- Test 6: Offense Label Denylist (Layer 4) ---")
entities = get_entity_names(
    "The case involves NDPS trafficking and extortion charges."
    "The murder was related to robbery and theft."
)
test(
    "T6a: 'NDPS' NOT extracted as entity",
    not has_entity_type(entities, "NDPS", "Person"),
    f"Found: {entities}"
)
test(
    "T6b: 'extortion' NOT extracted as entity",
    not has_entity_type(entities, "extortion", "Person"),
)
test(
    "T6c: 'murder' NOT extracted as entity",
    not has_entity_type(entities, "murder", "Person"),
)
test(
    "T6d: 'trafficking' NOT extracted as entity",
    not has_entity_type(entities, "trafficking", "Person"),
)

# ── Test 7: Partial identity protection (Layer 6) ─────────────────────
print("\n--- Test 7: Partial Identity Protection (Layer 6) ---")
test(
    "T7a: 'Khan' is detected as partial name",
    _is_partial_name("Khan"),
)
test(
    "T7b: 'Khan Ali' is NOT partial (full name)",
    not _is_partial_name("Khan Ali"),
)
test(
    "T7c: 'Rajesh Kumar' is NOT partial",
    not _is_partial_name("Rajesh Kumar"),
)

e1 = Entity(id="1", name="Khan", entity_type=EntityType.PERSON, attributes={}, aliases=[])
e2 = Entity(id="2", name="Khan", entity_type=EntityType.PERSON, attributes={}, aliases=[])
e3 = Entity(id="3", name="Rajesh Kumar", entity_type=EntityType.PERSON, attributes={}, aliases=[])

test(
    "T7d: Khan vs Khan (same surname) similarity = 0.0 (never auto-merge)",
    compute_similarity(e1, e2) == 0.0,
    f"Got: {compute_similarity(e1, e2)}"
)
test(
    "T7e: Khan vs Rajesh Kumar similarity = 0.0 (different names)",
    compute_similarity(e1, e3) == 0.0,
    f"Got: {compute_similarity(e1, e3)}"
)

# ── Test 8: Dedup normalization (Layer 4) ─────────────────────────────
print("\n--- Test 8: Dedup Normalization (Layer 4) ---")
test(
    "T8a: 'Previous Criminal History' normalizes same as 'Previous Criminal History:'",
    normalize_dedup_key("Previous Criminal History") == normalize_dedup_key("Previous Criminal History:"),
    f"Got: '{normalize_dedup_key('Previous Criminal History')}' vs '{normalize_dedup_key('Previous Criminal History:')}'"
)
test(
    "T8b: 'Vikram Solanki' normalizes same as ' Vikram Solanki '",
    normalize_dedup_key("Vikram Solanki") == normalize_dedup_key(" Vikram Solanki "),
)

# ── Test 9: Sanity validation (Layer 0) ──────────────────────────────
print("\n--- Test 9: Sanity Validation (Layer 0) ---")
test(
    "T9a: Empty string fails sanity",
    fails_basic_sanity(""),
)
test(
    "T9b: Single char fails sanity",
    fails_basic_sanity("A"),
)
test(
    "T9c: String ending in colon fails sanity",
    fails_basic_sanity("Previous Criminal History:"),
)
test(
    "T9d: Repeated word fragments fail sanity (Tower Legend Tower)",
    fails_basic_sanity("Tower Legend Tower"),
)
test(
    "T9e: Normal name passes sanity",
    not fails_basic_sanity("Vikram Solanki"),
)
test(
    "T9f: Long garbled string (>60 chars) fails sanity",
    fails_basic_sanity("A" * 61),
)

# ── Test 10: Vehicle regression (Layer 8) ─────────────────────────────
print("\n--- Test 10: Vehicle Regression (Baseline) ---")
entities = get_entity_names("Vehicle MH-12-AB-1234 was found near the scene.")
test(
    "T10a: Vehicle 'MH-12-AB-1234' still extracts correctly as VEHICLE",
    has_entity_type(entities, "MH-12-AB-1234", "Vehicle"),
    f"Found: {entities}"
)

entities = get_entity_names("The car with registration HR-51-AB-1234 was seized.")
test(
    "T10b: Vehicle 'HR-51-AB-1234' still extracts correctly as VEHICLE",
    has_entity_type(entities, "HR-51-AB-1234", "Vehicle"),
)

# ── Test 11: commit_entity gate ──────────────────────────────────────
print("\n--- Test 11: commit_entity Gate ---")
class MockEntity:
    def __init__(self, text, type_):
        self.text = text
        self.type = type_

test(
    "T11a: 'Vikram Solanki' PERSON → STORE",
    commit_entity(MockEntity("Vikram Solanki", "PERSON")),
)
test(
    "T11b: 'Telegram' PERSON → DENIED",
    not commit_entity(MockEntity("Telegram", "PERSON")),
)
test(
    "T11c: 'NEFT' FINANCIAL_ACCOUNT → DENIED",
    not commit_entity(MockEntity("NEFT", "FINANCIAL_ACCOUNT")),
)
test(
    "T11d: 'amount_inr' PERSON → DENIED (schema artifact)",
    not commit_entity(MockEntity("amount_inr", "PERSON")),
)
test(
    "T11e: 'NDPS' ORGANIZATION → DENIED (offense label)",
    not commit_entity(MockEntity("NDPS", "ORGANIZATION")),
)
test(
    "T11f: 'Previous Criminal History:' → DENIED (ends with colon, sanity)",
    not commit_entity(MockEntity("Previous Criminal History:", "PERSON")),
)

# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
total = len(results)
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
if failed > 0:
    print("\nFAILED TESTS:")
    for name, p, detail in results:
        if not p:
            print(f"  [X] {name}" + (f" -- {detail}" if detail else ""))
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
