"""
Test LLM Linkage Analysis with known case pairs.
Validates that:
- Known-linked pairs get HIGH scores with genuine shared behaviors
- Known-unrelated pairs with shared keywords get LOW scores
  with those words in false_positive_words_ignored
"""

import sys
import io
import json
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import SessionLocal
from app.models.models import Case, Document
from app.services.llm_linkage_analysis import (
    llm_case_pair_analysis,
    pre_filter_pairs,
    SIMILARITY_MAP,
)
from app.services.serial_pattern_detection import _extract_case_document_text

db = SessionLocal()

# ─── Load case data ────────────────────────────────────────────
cases = db.query(Case).order_by(Case.case_number).all()
case_data = []
for c in cases:
    text = _extract_case_document_text(db, c.id)
    case_data.append({
        "case_id": c.id,
        "case_number": c.case_number,
        "name": c.name,
        "text": text or "",
    })

print(f"Loaded {len(case_data)} cases")
for cd in case_data:
    print(f"  {cd['case_number']}: {cd['name']} ({len(cd['text'])} chars)")

# ─── Define test pairs ────────────────────────────────────────
# Known LINKED pairs (same serial killer, different victims/locations)
# These should get HIGH linkage_score
linked_pairs = [
    ("BCI-114-B-001", "BCI-114-B-002"),  # Bemis ↔ Okafor: brass key, dead frequency, alone
    ("BCI-114-B-002", "BCI-114-B-004"),  # Okafor ↔ Chandrasekaran: dead frequency, trophy, radio
    ("BCI-114-B-003", "BCI-114-B-005"),  # Griggs ↔ Idlewild: key, locksmith/archivist link
    ("BCI-114-B-001", "BCI-114-B-003"),  # Bemis ↔ Griggs: key, unlocked, isolated
]

# Known UNRELATED pair (shared words but different context)
# These should get LOW linkage_score with words in false_positives
unrelated_pairs = [
    ("BCI-114-B-001", "BCI-114-B-005"),  # Bemis ↔ Idlewild: weakest link (most different MO)
]

# ─── Run pre-filter ────────────────────────────────────────────
print("\n" + "=" * 70)
print("PRE-FILTER TEST")
print("=" * 70)
pairs = pre_filter_pairs(case_data)
print(f"Pre-filter returned {len(pairs)} pairs from {len(case_data)} cases")

# ─── Run analysis on test pairs ────────────────────────────────
print("\n" + "=" * 70)
print("KNOWN-LINKED PAIRS (should get HIGH scores)")
print("=" * 70)

for case_a, case_b in linked_pairs:
    a = next((c for c in case_data if c["case_number"] == case_a), None)
    b = next((c for c in case_data if c["case_number"] == case_b), None)
    if not a or not b:
        print(f"  SKIP: {case_a} or {case_b} not found")
        continue

    print(f"\n--- {case_a} ↔ {case_b} ---")
    result = llm_case_pair_analysis(a["text"], a["case_number"], b["text"], b["case_number"])

    print(f"  Linkage Score:    {result['linkage_score']}/100")
    print(f"  Signature:        {result['signature_similarity']} ({SIMILARITY_MAP[result['signature_similarity']]:.2f})")
    print(f"  MO:               {result['mo_similarity']} ({SIMILARITY_MAP[result['mo_similarity']]:.2f})")
    print(f"  Victimology:      {result['victimology_similarity']}")
    print(f"  Backend:          {result.get('backend', 'unknown')}")
    print(f"  Reasoning:        {result['reasoning']}")
    if result['genuine_shared_behaviors']:
        print(f"  Genuine Behaviors:")
        for b in result['genuine_shared_behaviors']:
            print(f"    ✓ {b}")
    if result['false_positive_words_ignored']:
        print(f"  False Positives Rejected:")
        for fp in result['false_positive_words_ignored']:
            print(f"    ✗ {fp}")

print("\n" + "=" * 70)
print("KNOWN-UNRELATED PAIRS (should get LOW scores)")
print("=" * 70)

for case_a, case_b in unrelated_pairs:
    a = next((c for c in case_data if c["case_number"] == case_a), None)
    b = next((c for c in case_data if c["case_number"] == case_b), None)
    if not a or not b:
        print(f"  SKIP: {case_a} or {case_b} not found")
        continue

    print(f"\n--- {case_a} ↔ {case_b} ---")
    result = llm_case_pair_analysis(a["text"], a["case_number"], b["text"], b["case_number"])

    print(f"  Linkage Score:    {result['linkage_score']}/100")
    print(f"  Signature:        {result['signature_similarity']} ({SIMILARITY_MAP[result['signature_similarity']]:.2f})")
    print(f"  MO:               {result['mo_similarity']} ({SIMILARITY_MAP[result['mo_similarity']]:.2f})")
    print(f"  Reasoning:        {result['reasoning']}")
    if result['genuine_shared_behaviors']:
        print(f"  Genuine Behaviors:")
        for beh in result['genuine_shared_behaviors']:
            print(f"    ✓ {beh}")
    if result['false_positive_words_ignored']:
        print(f"  False Positives Rejected:")
        for fp in result['false_positive_words_ignored']:
            print(f"    ✗ {fp}")

# ─── Run ALL pairwise ──────────────────────────────────────────
print("\n" + "=" * 70)
print("FULL PAIRWISE MATRIX")
print("=" * 70)

all_results = {}
for i, j in pairs:
    a = case_data[i]
    b = case_data[j]
    result = llm_case_pair_analysis(a["text"], a["case_number"], b["text"], b["case_number"])
    pair_key = f"{a['case_number']} ↔ {b['case_number']}"
    all_results[pair_key] = result
    status = "PASS" if result["linkage_score"] >= 30 else "LOW"
    print(f"  {pair_key}: {result['linkage_score']:3d}/100 [{status}] sig={result['signature_similarity']} mo={result['mo_similarity']}")

print(f"\nTotal pairs analyzed: {len(all_results)}")
high = sum(1 for r in all_results.values() if r["linkage_score"] >= 30)
low = sum(1 for r in all_results.values() if r["linkage_score"] < 30)
print(f"High linkage (>=30): {high}")
print(f"Low linkage (<30):  {low}")

# ─── Validation ────────────────────────────────────────────────
print("\n" + "=" * 70)
print("VALIDATION")
print("=" * 70)

# Check linked pairs scored higher than unrelated
linked_scores = []
for case_a, case_b in linked_pairs:
    key = f"{case_a} ↔ {case_b}"
    if key in all_results:
        linked_scores.append(all_results[key]["linkage_score"])

unlinked_scores = []
for case_a, case_b in unrelated_pairs:
    key = f"{case_a} ↔ {case_b}"
    if key in all_results:
        unlinked_scores.append(all_results[key]["linkage_score"])

avg_linked = sum(linked_scores) / len(linked_scores) if linked_scores else 0
avg_unlinked = sum(unlinked_scores) / len(unlinked_scores) if unlinked_scores else 0

print(f"Average linked score:    {avg_linked:.1f}")
print(f"Average unlinked score:  {avg_unlinked:.1f}")
if avg_linked > avg_unlinked:
    print("✓ PASS: Linked pairs score higher than unlinked pairs")
else:
    print("✗ FAIL: Linked pairs do NOT score higher than unlinked pairs")

# Check false positives were identified for weak pairs
weak_with_fp = sum(
    1 for r in all_results.values()
    if r["linkage_score"] < 30 and len(r["false_positive_words_ignored"]) > 0
)
print(f"Weak pairs with false positives identified: {weak_with_fp}/{low}")

db.close()
print("\nDone!")
