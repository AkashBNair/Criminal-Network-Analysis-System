"""
Case Linkage & Pattern Recognition — Similarity & Scoring Engine

Computes pairwise similarity between case records using multiple signals,
then combines them into a weighted composite "linkage confidence score".

Signals:
  a) Structured Feature Similarity — categorical + numeric field matching
  b) Narrative Text Similarity — TF-IDF cosine similarity on FIR text
  c) Geographic-Temporal Signal — haversine distance + time gap
     (NOT used to suppress scores — cross-state patterns are flagged
     as contextual info rather than penalized)

Composite weights are configurable constants, not hardcoded magic numbers.

IMPORTANT: This is a lead-generation tool, NOT an automated accusation
system. All outputs are labeled "candidate leads" — never "matches".
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
import numpy as np

from .data_model import (
    WEIGHT_SIGNATURE, WEIGHT_NARRATIVE, WEIGHT_VICTIMOLOGY, WEIGHT_MO,
    ApproachMethod, ControlMethod, CrimeSceneOrg, VictimRiskLevel,
)


# ── Haversine Distance ────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in km."""
    R = 6371.0  # Earth radius in km
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lng2 - lng1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Structured Feature Similarity ─────────────────────────────────

def _categorical_match(a: str, b: str) -> float:
    """Exact match → 1.0, mismatch → 0.0."""
    return 1.0 if a == b else 0.0


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard index for multi-value fields."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _numeric_distance(a: float, b: float, max_range: float) -> float:
    """Normalized distance → similarity. 0 = identical, 1 = maximally different."""
    return 1.0 - min(abs(a - b) / max_range, 1.0)


def _victimology_similarity(c1: dict, c2: dict) -> float:
    """
    Victimology similarity (20% of composite).
    Compares: age proximity, gender match, occupation similarity,
    risk level match, and victim type similarity.
    """
    scores = []

    # Age proximity (if both present)
    if c1.get("victim_age") and c2.get("victim_age"):
        scores.append(_numeric_distance(c1["victim_age"], c2["victim_age"], 50.0))
    else:
        scores.append(0.5)  # neutral if missing

    # Gender match
    if c1.get("victim_gender") and c2.get("victim_gender"):
        scores.append(_categorical_match(c1["victim_gender"], c2["victim_gender"]))
    else:
        scores.append(0.5)

    # Occupation similarity (exact or shared word)
    occ1 = (c1.get("victim_occupation") or "").lower()
    occ2 = (c2.get("victim_occupation") or "").lower()
    if occ1 and occ2:
        if occ1 == occ2:
            scores.append(1.0)
        elif occ1.split()[0] == occ2.split()[0]:
            scores.append(0.5)
        else:
            scores.append(0.0)
    else:
        scores.append(0.5)

    # Risk level match
    scores.append(_categorical_match(
        c1.get("victim_risk_level", "low"),
        c2.get("victim_risk_level", "low"),
    ))

    return sum(scores) / len(scores) if scores else 0.0


def _mo_similarity(c1: dict, c2: dict) -> float:
    """
    MO/Approach similarity (15% of composite).
    Compares: approach method, control method, weapon type,
    crime scene organization.
    """
    scores = [
        _categorical_match(c1.get("approach_method", ""), c2.get("approach_method", "")),
        _categorical_match(c1.get("control_method", ""), c2.get("control_method", "")),
        _categorical_match(c1.get("crime_scene_organization", ""), c2.get("crime_scene_organization", "")),
    ]

    # Weapon similarity
    w1 = c1.get("weapon_type") or ""
    w2 = c2.get("weapon_type") or ""
    if w1 and w2:
        scores.append(_categorical_match(w1, w2))
    else:
        scores.append(0.5)

    return sum(scores) / len(scores) if scores else 0.0


def structured_similarity(c1: dict, c2: dict) -> dict:
    """
    Compute structured feature similarity between two cases.
    Returns individual signal scores and a combined structured score.

    Signature behaviors are weighted HIGHER than MO because signature
    is psychologically more stable across a serial series — offenders
    adapt their approach (MO) but retain their signature.
    """
    # Signature similarity (40% weight — psychologically most stable)
    sig1 = set(c1.get("signature_behaviors", []))
    sig2 = set(c2.get("signature_behaviors", []))
    sig_sim = _jaccard_similarity(sig1, sig2)

    # Overkill score similarity
    ok1 = c1.get("overkill_score", 0)
    ok2 = c2.get("overkill_score", 0)
    overkill_sim = _numeric_distance(ok1, ok2, 10.0)

    # Combined signature: Jaccard of behaviors + overkill proximity
    signature_score = (sig_sim * 0.7 + overkill_sim * 0.3)

    # Victimology (20%)
    victimology_score = _victimology_similarity(c1, c2)

    # MO (15%)
    mo_score = _mo_similarity(c1, c2)

    return {
        "signature_similarity": round(signature_score, 4),
        "signature_behaviors_shared": list(sig1 & sig2),
        "overkill_proximity": round(overkill_sim, 4),
        "victimology_similarity": round(victimology_score, 4),
        "mo_similarity": round(mo_score, 4),
    }


# ── Narrative Text Similarity ─────────────────────────────────────

# TF-IDF vectorizer — shared across calls for efficiency
_tfidf_vectorizer: Optional[TfidfVectorizer] = None
_narrative_matrix: Optional[np.ndarray] = None
_narrative_case_ids: Optional[list[str]] = None


def build_narrative_index(cases: list[dict]) -> None:
    """
    Build TF-IDF index over all case narratives.
    Call once before computing pairwise narrative similarity.
    """
    global _tfidf_vectorizer, _narrative_matrix, _narrative_case_ids

    _narrative_case_ids = [c["case_id"] for c in cases]
    narratives = [c.get("narrative_text", "") for c in cases]

    _tfidf_vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    _narrative_matrix = _tfidf_vectorizer.fit_transform(narratives)


def narrative_similarity_batch(
    case_ids: list[str],
) -> dict[tuple[str, str], float]:
    """
    Compute pairwise narrative similarity for all pairs in case_ids.
    Returns dict mapping (id_a, id_b) → similarity score.
    """
    if _narrative_matrix is None or _narrative_case_ids is None:
        raise RuntimeError("Call build_narrative_index() first")

    id_to_idx = {cid: i for i, cid in enumerate(_narrative_case_ids)}
    indices = [id_to_idx[cid] for cid in case_ids if cid in id_to_idx]

    if len(indices) < 2:
        return {}

    subset = _narrative_matrix[indices]
    sim_matrix = sklearn_cosine(subset, subset)

    results = {}
    for i in range(len(indices)):
        for j in range(i + 1, len(indices)):
            score = float(sim_matrix[i, j])
            results[(case_ids[i], case_ids[j])] = round(score, 4)

    return results


def narrative_similarity_single(c1_id: str, c2_id: str) -> float:
    """Get narrative similarity for a single pair."""
    if _narrative_matrix is None or _narrative_case_ids is None:
        raise RuntimeError("Call build_narrative_index() first")

    id_to_idx = {cid: i for i, cid in enumerate(_narrative_case_ids)}
    if c1_id not in id_to_idx or c2_id not in id_to_idx:
        return 0.0

    i, j = id_to_idx[c1_id], id_to_idx[c2_id]
    subset = _narrative_matrix[[i, j]]
    sim = sklearn_cosine(subset, subset)
    return round(float(sim[0, 1]), 4)


# ── Geographic-Temporal Signal ────────────────────────────────────

def geo_temporal_signal(c1: dict, c2: dict) -> dict:
    """
    Compute geographic and temporal context between two cases.

    IMPORTANT: Large distances and time gaps do NOT suppress the linkage
    score. Serial offenders often cross state lines specifically to
    evade jurisdictional linkage, and cooling-off periods are irregular.
    Instead, we surface this as contextual flags for the investigator.
    """
    # Haversine distance
    dist_km = haversine_km(
        c1["location_lat"], c1["location_lng"],
        c2["location_lat"], c2["location_lng"],
    )

    # Time gap
    dt1 = datetime.fromisoformat(c1["date_time"])
    dt2 = datetime.fromisoformat(c2["date_time"])
    time_gap_days = abs((dt2 - dt1).days)

    # Cross-state detection
    cross_state = c1["state"] != c2["state"]
    cross_district = (c1["district"] != c2["district"]) and not cross_state

    # Contextual flags (informational, NOT score-suppressing)
    flags = []
    if cross_state:
        flags.append(f"Cross-state pattern ({c1['state']} ↔ {c2['state']})")
    elif cross_district:
        flags.append(f"Cross-district pattern ({c1['district']} ↔ {c2['district']})")

    if time_gap_days <= 30:
        flags.append(f"Closely timed ({time_gap_days} days apart)")
    elif time_gap_days <= 90:
        flags.append(f"Within quarter ({time_gap_days} days apart)")

    if dist_km <= 50:
        flags.append(f"Geographically close ({dist_km:.0f} km)")
    elif dist_km <= 200:
        flags.append(f"Regional proximity ({dist_km:.0f} km)")

    return {
        "distance_km": round(dist_km, 1),
        "time_gap_days": time_gap_days,
        "cross_state": cross_state,
        "cross_district": cross_district,
        "flags": flags,
    }


# ── Composite Score ───────────────────────────────────────────────

def compute_linkage_score(c1: dict, c2: dict) -> dict:
    """
    Compute the full linkage confidence score (0-100) between two cases.

    Returns a dict with:
      - composite_score: final 0-100 score
      - component_scores: individual signal breakdowns
      - geo_temporal: geographic/temporal context
      - weights_used: the weights applied
    """
    structured = structured_similarity(c1, c2)

    # Narrative similarity from pre-built index
    narr_sim = narrative_similarity_single(c1["case_id"], c2["case_id"])

    # Geo-temporal (contextual only, does not affect score)
    geo = geo_temporal_signal(c1, c2)

    # Weighted composite (all signals normalized to 0-1)
    composite = (
        structured["signature_similarity"] * WEIGHT_SIGNATURE +
        narr_sim * WEIGHT_NARRATIVE +
        structured["victimology_similarity"] * WEIGHT_VICTIMOLOGY +
        structured["mo_similarity"] * WEIGHT_MO
    )

    # Scale to 0-100
    composite_100 = round(composite * 100, 1)

    return {
        "composite_score": composite_100,
        "component_scores": {
            "signature": round(structured["signature_similarity"] * 100, 1),
            "narrative": round(narr_sim * 100, 1),
            "victimology": round(structured["victimology_similarity"] * 100, 1),
            "mo": round(structured["mo_similarity"] * 100, 1),
        },
        "details": {
            "signature_behaviors_shared": structured["signature_behaviors_shared"],
            "overkill_proximity": structured["overkill_proximity"],
        },
        "geo_temporal": geo,
        "weights_used": {
            "signature": WEIGHT_SIGNATURE,
            "narrative": WEIGHT_NARRATIVE,
            "victimology": WEIGHT_VICTIMOLOGY,
            "mo": WEIGHT_MO,
        },
    }


def compute_all_pairwise_scores(
    cases: list[dict],
    min_score: float = 0.0,
) -> list[dict]:
    """
    Compute linkage scores for all case pairs above min_score.
    Returns list of link records sorted by score descending.

    For large datasets, consider batching or pre-filtering.
    """
    # Build narrative index
    build_narrative_index(cases)

    links = []
    n = len(cases)
    case_dict = {c["case_id"]: c for c in cases}

    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = cases[i], cases[j]
            result = compute_linkage_score(c1, c2)

            if result["composite_score"] >= min_score:
                links.append({
                    "case_a": c1["case_id"],
                    "case_b": c2["case_id"],
                    "case_a_number": c1.get("case_number", ""),
                    "case_b_number": c2.get("case_number", ""),
                    "case_a_state": c1.get("state", ""),
                    "case_b_state": c2.get("state", ""),
                    "composite_score": result["composite_score"],
                    "component_scores": result["component_scores"],
                    "details": result["details"],
                    "geo_temporal": result["geo_temporal"],
                    "weights_used": result["weights_used"],
                })

    links.sort(key=lambda x: x["composite_score"], reverse=True)
    return links
