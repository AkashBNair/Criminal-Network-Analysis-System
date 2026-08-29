"""
Case Linkage & Pattern Recognition — Explanation Generator

For every flagged link between two cases, generates a human-readable
explanation that tells the investigator WHY these cases are linked.

Every claim is traceable to specific evidence. Inferences are labeled
distinctly from confirmed facts. Never outputs a bare score with no
reasoning — investigators need to know WHY, both for trust and for
legal defensibility.
"""
from __future__ import annotations


def generate_link_explanation(link: dict, case_a: dict, case_b: dict) -> dict:
    """
    Generate a full human-readable explanation for a flagged link.
    
    Returns a dict with:
      - headline: one-line summary
      - confidence_badge: "HIGH" / "MEDIUM" / "LOW"
      - sections: ordered list of explanation sections
      - disclaimer: required responsible-AI disclaimer
    """
    score = link["composite_score"]
    components = link["component_scores"]
    details = link["details"]
    geo = link["geo_temporal"]

    # Confidence classification
    if score >= 75:
        badge = "HIGH"
    elif score >= 50:
        badge = "MEDIUM"
    else:
        badge = "LOW"

    # ── Build explanation sections ──
    sections = []

    # 1. Score overview
    sections.append({
        "title": "Linkage Confidence",
        "text": (
            f"Case #{case_a.get('case_number', case_a['case_id'])} and "
            f"Case #{case_b.get('case_number', case_b['case_id'])} flagged "
            f"with confidence {score}/100."
        ),
        "type": "confirmed",
    })

    # 2. Shared signature behaviors (strongest signal)
    shared_sigs = details.get("signature_behaviors_shared", [])
    if shared_sigs:
        sig_labels = {
            "posing": "body posing",
            "trophy_taking": "trophy taking",
            "overkill": "excessive violence (overkill)",
            "staging": "crime scene staging",
            "specific_mutilation": "specific mutilation pattern",
            "ritualistic_element": "ritualistic elements",
        }
        sig_names = [sig_labels.get(s, s) for s in shared_sigs]
        sections.append({
            "title": "Shared Signature Behaviors",
            "text": (
                f"Both cases exhibit: {', '.join(sig_names)}. "
                f"Signature behaviors are psychologically stable across "
                f"a serial series — more reliable than MO, which offenders "
                f"typically adapt."
            ),
            "type": "confirmed",
            "evidence": f"Signature similarity score: {components['signature']}/100",
        })

    # 3. Overkill proximity
    overkill = details.get("overkill_proximity", 0)
    if overkill > 0.7:
        sections.append({
            "title": "Violence Level Similarity",
            "text": (
                f"Both cases show similar levels of excess violence "
                f"(overkill proximity: {overkill:.0%}). This suggests "
                f"a consistent behavioral pattern in the use of force."
            ),
            "type": "confirmed",
        })

    # 4. Victimology
    v_sim = components.get("victimology", 0)
    if v_sim > 60:
        v1_age = case_a.get("victim_age", "?")
        v2_age = case_b.get("victim_age", "?")
        v1_gen = case_a.get("victim_gender", "?")
        v2_gen = case_b.get("victim_gender", "?")
        v1_risk = case_a.get("victim_risk_level", "?")
        v2_risk = case_b.get("victim_risk_level", "?")

        sections.append({
            "title": "Similar Victimology",
            "text": (
                f"Similar victim profiles: both {v1_gen}/{v2_gen} victims, "
                f"ages {v1_age}/{v2_age}, risk levels {v1_risk}/{v2_risk}. "
                f"Consistent victim selection suggests a shared targeting pattern."
            ),
            "type": "inferred",
            "evidence": f"Victimology similarity: {v_sim}/100",
        })

    # 5. MO similarity
    mo_sim = components.get("mo", 0)
    if mo_sim > 50:
        approach_a = case_a.get("approach_method", "unknown")
        approach_b = case_b.get("approach_method", "unknown")
        control_a = case_a.get("control_method", "unknown")
        control_b = case_b.get("control_method", "unknown")

        sections.append({
            "title": "Modus Operandi Similarity",
            "text": (
                f"Approach methods: {approach_a} / {approach_b}. "
                f"Control methods: {control_a} / {control_b}. "
                f"MO can be adapted by offenders, so this is weighted lower "
                f"than signature behaviors but still provides corroborating evidence."
            ),
            "type": "inferred",
            "evidence": f"MO similarity: {mo_sim}/100",
        })

    # 6. Narrative similarity
    narr = components.get("narrative", 0)
    if narr > 60:
        sections.append({
            "title": "Narrative Similarity",
            "text": (
                f"The FIR/report texts show {narr:.0f}% similarity. "
                f"This captures linguistic patterns and contextual details "
                f"not captured by structured fields alone."
            ),
            "type": "inferred",
            "evidence": f"TF-IDF cosine similarity: {narr}/100",
        })

    # 7. Geographic-temporal context
    geo_flags = geo.get("flags", [])
    if geo_flags:
        sections.append({
            "title": "Geographic & Temporal Context",
            "text": " — ".join(geo_flags) + ".",
            "type": "contextual",
            "evidence": (
                f"Distance: {geo['distance_km']} km, "
                f"time gap: {geo['time_gap_days']} days"
            ),
        })

    # 8. Cross-state note (if applicable)
    if geo.get("cross_state"):
        sections.append({
            "title": "Cross-Jurisdictional Pattern",
            "text": (
                f"These cases are in different states "
                f"({case_a.get('state', '?')} and {case_b.get('state', '?')}). "
                f"Cross-state patterns are flagged because serial offenders "
                f"often cross jurisdictional boundaries specifically to evade "
                f"detection. This does NOT suppress the linkage score."
            ),
            "type": "contextual",
        })

    # ── Headline ──
    headline = (
        f"Cases {case_a.get('case_id', '?')} and {case_b.get('case_id', '?')} "
        f"flagged (confidence: {score}/100)"
    )

    # ── Disclaimer ──
    disclaimer = (
        "This analysis identifies statistical patterns for investigative lead "
        "generation only. It does NOT determine guilt and must NOT be used as "
        "sole grounds for suspicion or arrest. All flagged links require human "
        "investigator review before any action is taken."
    )

    return {
        "headline": headline,
        "confidence_score": score,
        "confidence_badge": badge,
        "sections": sections,
        "disclaimer": disclaimer,
        "component_breakdown": components,
        "human_review_required": True,  # CANNOT be disabled
    }


def generate_cluster_explanation(cluster: dict, cases: list[dict]) -> dict:
    """
    Generate a summary explanation for an entire cluster of linked cases.
    """
    case_map = {c["case_id"]: c for c in cases}

    member_details = []
    for m in cluster["members"]:
        cid = m["case_id"]
        c = case_map.get(cid, {})
        member_details.append({
            "case_id": cid,
            "case_number": c.get("case_number", ""),
            "state": c.get("state", ""),
            "district": c.get("district", ""),
            "date_time": c.get("date_time", ""),
            "signature_behaviors": c.get("signature_behaviors", []),
            "victim_age": c.get("victim_age"),
            "victim_gender": c.get("victim_gender"),
        })

    # Identify the consistent thread
    all_sigs = set()
    for m in member_details:
        all_sigs.update(m["signature_behaviors"])

    sig_labels = {
        "posing": "body posing",
        "trophy_taking": "trophy taking",
        "overkill": "excessive violence",
        "staging": "scene staging",
        "specific_mutilation": "mutilation pattern",
        "ritualistic_element": "ritualistic elements",
    }
    sig_names = [sig_labels.get(s, s) for s in sorted(all_sigs)]

    # Victim demographics
    ages = [m["victim_age"] for m in member_details if m.get("victim_age")]
    genders = [m["victim_gender"] for m in member_details if m.get("victim_gender")]

    explanation_parts = []
    if sig_names:
        explanation_parts.append(
            f"Consistent signature behaviors across {cluster['member_count']} cases: "
            f"{', '.join(sig_names)}."
        )
    if ages:
        explanation_parts.append(
            f"Victim ages range from {min(ages)} to {max(ages)}."
        )
    if genders:
        from collections import Counter
        gender_counts = Counter(genders)
        gender_str = ", ".join(f"{g}: {n}" for g, n in gender_counts.most_common())
        explanation_parts.append(f"Victim gender distribution: {gender_str}.")

    if cluster.get("cross_state"):
        explanation_parts.append(
            f"Cross-state pattern spanning: {', '.join(cluster['states'])}."
        )

    return {
        "cluster_id": cluster["cluster_id"],
        "label": cluster["label"],
        "member_count": cluster["member_count"],
        "avg_confidence": cluster["avg_confidence"],
        "max_confidence": cluster["max_confidence"],
        "summary": " ".join(explanation_parts) if explanation_parts else "Linked cases identified.",
        "members": member_details,
        "shared_signatures": cluster.get("shared_signatures", []),
        "cross_state": cluster.get("cross_state", False),
        "states": cluster.get("states", []),
        "disclaimer": (
            "This analysis identifies statistical patterns for investigative lead "
            "generation only. It does NOT determine guilt and must NOT be used as "
            "sole grounds for suspicion or arrest."
        ),
    }
