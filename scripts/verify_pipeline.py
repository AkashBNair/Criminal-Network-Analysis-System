"""
Pipeline Verification Script — audits all 6 stages of serial pattern detection.
Run: cd backend && python verify_pipeline.py
"""
import os
import sys
import json
import logging

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.models.models import Case, Document, Entity
from app.database import SessionLocal
from app.services.serial_pattern_detection import (
    _extract_case_document_text,
    _extract_mo_from_text,
    _extract_victimology_from_text,
    _compute_signature_overlap,
    _identify_serial_clusters,
    detect_serial_patterns,
)

# Set up logging for _identify_serial_clusters
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logger = logging.getLogger("app.services.serial_pattern_detection")
logger.setLevel(logging.INFO)

db = SessionLocal()

print("=" * 70)
print("STAGE 1: DB Data Check (Documents & Entities)")
print("=" * 70)

cases = db.query(Case).all()
if not cases:
    print("NO CASES IN DATABASE. Ingest case files first.")
    db.close()
    sys.exit(1)

for case in cases:
    docs = db.query(Document).filter(Document.case_id == case.id).all()
    entities = db.query(Entity).filter(Entity.case_id == case.id).all()
    print(f"\nCase {case.case_number} ({case.name}):")
    print(f"  Documents: {len(docs)}, Entities: {len(entities)}")
    for doc in docs:
        content = doc.content_text
        content_preview = (content[:80] + "...") if content else "NULL/EMPTY"
        has_text = "YES" if content and len(content.strip()) > 10 else "EMPTY/NULL"
        print(f"  Doc: {doc.filename} | content_text: {has_text} | len={len(content) if content else 0}")
        if content and len(content) > 0:
            print(f"    Preview: {content_preview}")

print("\n" + "=" * 70)
print("STAGE 2: Entity Extraction Sample")
print("=" * 70)

for case in cases:
    entities = db.query(Entity).filter(
        Entity.case_id == case.id, Entity.is_ai_extracted == True
    ).limit(5).all()
    print(f"\nCase {case.case_number} — AI Extracted Entities:")
    if not entities:
        print("  NONE FOUND!")
    for e in entities:
        print(f"  - [{e.entity_type.value}] {e.name} (confidence: {e.confidence_score:.2f})")

print("\n" + "=" * 70)
print("STAGE 3: MO and Victimology Extraction")
print("=" * 70)

mo_empty_count = 0
vict_empty_count = 0

for case in cases:
    text = _extract_case_document_text(db, case.id)
    if not text or len(text.strip()) < 10:
        print(f"\nCase {case.case_number}: NO TEXT (or too short)")
        mo_empty_count += 1
        vict_empty_count += 1
        continue

    mo = _extract_mo_from_text(text)
    vict = _extract_victimology_from_text(text)

    mo_dims = list(mo.keys())
    vict_dims = {k: v for k, v in vict.items() if v}

    print(f"\nCase {case.case_number}:")
    print(f"  Text length: {len(text)} chars")
    print(f"  MO dimensions found: {mo_dims if mo_dims else 'EMPTY'}")
    if mo:
        for dim, matches in mo.items():
            print(f"    {dim}: {matches[:5]}")
    else:
        mo_empty_count += 1

    print(f"  Victimology: {vict_dims if vict_dims else 'EMPTY'}")
    if not vict.get("age_mentions") and not vict.get("gender_mentions") and not vict.get("risk_factors"):
        vict_empty_count += 1

print(f"\n  SUMMARY: {mo_empty_count}/{len(cases)} cases with empty MO, {vict_empty_count}/{len(cases)} with empty victimology")

print("\n" + "=" * 70)
print("STAGE 4: Signature Overlap")
print("=" * 70)

case_ids = [c.id for c in cases]
try:
    case_texts = {cid: _extract_case_document_text(db, cid) for cid in case_ids}
    sig_output = _compute_signature_overlap(db, case_ids, case_texts)

    print(f"Average overlap: {sig_output['avg_overlap']}")
    print(f"Common terms across ALL cases: {sig_output['common_terms_all_cases']}")
    print(f"\nPer-case signature terms:")
    for cid, sig_data in sig_output["case_signatures"].items():
        case = db.query(Case).filter(Case.id == cid).first()
        cn = case.case_number if case else cid
        terms = sig_data["signature_terms"]
        intensity = sig_data["intensity"]
        print(f"  {cn}: {len(terms)} terms, intensity={intensity}")
        if terms:
            print(f"    Terms: {terms[:10]}")
        else:
            print(f"    NO signature terms found!")
except Exception as e:
    print(f"ERROR in _compute_signature_overlap: {e}")
    import traceback
    traceback.print_exc()
    sig_output = {"case_signatures": {}, "avg_overlap": 0, "pairwise_overlap": {}}

print("\n" + "=" * 70)
print("STAGE 5: Composite Clustering Scoring")
print("=" * 70)

try:
    similarity_input = {"components": {"signatures": sig_output}}
    clusters = _identify_serial_clusters(db, case_ids, similarity_input)
    print(f"Clusters identified: {len(clusters)}")
    for cl in clusters:
        print(f"\n  {cl['cluster_id']}: {cl['case_count']} cases, avg_similarity={cl['avg_similarity']}")
        for cd in cl["cases"]:
            print(f"    - {cd['case_number']}: {cd['case_name']}")
        if cl.get("pairwise_scores"):
            for ps in cl["pairwise_scores"]:
                print(f"    Pair {ps['cases']}: composite={ps['composite']} "
                      f"(sig={ps['signature']}, mo={ps['mo']}, vict={ps['victimology']}, ent={ps['entity']})")
        print(f"    Explanation: {cl['explanation'][:200]}")
except Exception as e:
    print(f"ERROR in _identify_serial_clusters: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("STAGE 6: End-to-End Validation (known-linked cases)")
print("=" * 70)

# Check pairwise score distribution
if len(case_ids) >= 2:
    pairwise = {}
    for i, cid1 in enumerate(case_ids):
        for j, cid2 in enumerate(case_ids):
            if i >= j:
                continue
            text1 = _extract_case_document_text(db, cid1)
            text2 = _extract_case_document_text(db, cid2)
            mo1 = _extract_mo_from_text(text1) if text1 else {}
            mo2 = _extract_mo_from_text(text2) if text2 else {}
            v1 = _extract_victimology_from_text(text1) if text1 else {}
            v2 = _extract_victimology_from_text(text2) if text2 else {}
            sigs = sig_output.get("case_signatures", {})

            from app.services.serial_pattern_detection import (
                _signature_jaccard, _mo_jaccard, _victimology_similarity, _jaccard
            )
            sig_s = _signature_jaccard(sigs, cid1, cid2)
            mo_s = _mo_jaccard(mo_by_case={cid1: mo1, cid2: mo2}, cid1=cid1, cid2=cid2)
            v_s = _victimology_similarity(vict_by_case={cid1: v1, cid2: v2}, cid1=cid1, cid2=cid2)

            e1 = {e.name.lower().strip() for e in db.query(Entity).filter(
                Entity.case_id == cid1, Entity.is_merged_into.is_(None)).all()}
            e2 = {e.name.lower().strip() for e in db.query(Entity).filter(
                Entity.case_id == cid2, Entity.is_merged_into.is_(None)).all()}
            ent_s = _jaccard(e1, e2)

            composite = sig_s * 0.40 + mo_s * 0.25 + v_s * 0.20 + ent_s * 0.15

            case1 = db.query(Case).filter(Case.id == cid1).first()
            case2 = db.query(Case).filter(Case.id == cid2).first()
            cn1 = case1.case_number if case1 else cid1
            cn2 = case2.case_number if case2 else cid2

            print(f"\n  {cn1} <-> {cn2}:")
            print(f"    Signature:  {sig_s:.3f} (terms in common)")
            print(f"    MO:         {mo_s:.3f}")
            print(f"    Victimology:{v_s:.3f}")
            print(f"    Entity:     {ent_s:.3f}")
            print(f"    COMPOSITE:  {composite:.3f} {'PASS >= 0.25' if composite >= 0.25 else 'BELOW THRESHOLD'}")

            pairwise[(cid1, cid2)] = composite

    if pairwise:
        scores = list(pairwise.values())
        print(f"\n  Score distribution: min={min(scores):.3f} max={max(scores):.3f} mean={sum(scores)/len(scores):.3f}")
        passing = sum(1 for s in scores if s >= 0.25)
        print(f"  Pairs above threshold: {passing}/{len(scores)}")

db.close()
print("\n" + "=" * 70)
print("PIPELINE AUDIT COMPLETE")
print("=" * 70)
