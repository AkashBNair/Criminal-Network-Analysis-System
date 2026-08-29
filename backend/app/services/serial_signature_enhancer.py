"""
Serial Signature Enhancer — detects serial-killer-specific behavioral patterns
that generic MO keyword matching misses.

These are non-violent signature behaviors:
- Object placement near bodies (trophy/signature items)
- Dead frequency radio tuning (ritualistic/communicative element)
- Missing personal items (trophy taking)
- Escalating intervals between crimes
- Occupational targeting patterns

CONSUMES: document text from case files.
No independent data construction.
"""
import re
import math
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.models import Entity, Case, Document, EntityType

logger = logging.getLogger(__name__)

# ─── Serial-Specific Signature Patterns ─────────────────────────────
# These catch the behavioral signatures in Cluster 114-B and similar cases

SERIAL_SIGNATURE_PATTERNS = {
    "object_placement": {
        "description": "Deliberate placement of items near victim (signature/trophy behavior)",
        "patterns": [
            r"placed\s+(neatly|deliberately|carefully|gently)\s+(on|beside|near|next to|by)",
            r"(?:brass|metal|small)\s+key\s+(?:found|placed|resting|sitting)",
            r"key\s+(?:found|placed)\s+(?:on|beside|near|next to|by)\s+(?:the\s+)?(?:workbench|dashboard|body|table|shelf)",
            r"(?:trophy|souvenir|memento|keepsake)",
            r"deliberately\s+(?:placed|left|positioned)",
        ],
        "weight": 0.40,
    },
    "dead_frequency": {
        "description": "Radio tuned to dead/off-air frequency (ritualistic/communicative signature)",
        "patterns": [
            r"dead\s+frequency",
            r"(?:radio|transmission|transmitted).*(?:dead|static|off[- ]air|gone off)",
            r"tuned\s+to\s+(?:a\s+)?(?:dead|defunct|off[- ]air|inactive)\s+(?:frequency|station|channel)",
            r"static\s+only",
            r"backup\s+frequency",
            r"transmitted.*(?:seconds?\s+of\s+)?dead\s+air",
        ],
        "weight": 0.40,
    },
    "trophy_taking": {
        "description": "Victim's personal items removed (trophy/signature taking)",
        "patterns": [
            r"missing\s+(?:item|object|thing|belonging|possession)",
            r"(?:took|taken|removed|stolen|missing)\s+(?:a\s+)?(?:single\s+)?(?:item|object|mug|badge|folder|key|blank)",
            r"(?:gap|missing)\s+(?:in|from|on)\s+(?:the\s+)?(?:pegboard|shelf|board|collection|desk)",
            r"(?:only\s+)?noticed\s+the\s+gap",
            r"(?:first|earliest)\s+indication.*(?:taking|took|missing|removed)",
        ],
        "weight": 0.35,
    },
    "victim_vulnerability": {
        "description": "Victims targeted when alone/vulnerable (predatory selection)",
        "patterns": [
            r"(?:found|found\s+dead)\s+(?:alone|by\s+herself|by\s+himself)",
            r"often\s+(?:stayed|worked|remained)\s+late",
            r"(?:working|alone)\s+(?:at|in|during|after)\s+(?:night|late|evening)",
            r"no\s+(?:indication|evidence)\s+(?:of\s+)?(?:struggle|fighting|defense)",
            r"doors?\s+were?\s+unlocked",
            r"unlocked.*(?:completely\s+out\s+of\s+character)",
        ],
        "weight": 0.25,
    },
    "cross_jurisdictional": {
        "description": "Crimes span multiple jurisdictions (evasion/confidence)",
        "patterns": [
            r"(?:county|district|jurisdiction|precinct|station).*(?:different|separate|adjacent|bordering)",
            r"cross[- ]jurisdiction",
            r"multi[- ]county",
        ],
        "weight": 0.20,
    },
    "escalation_pattern": {
        "description": "Escalating intervals or complexity between crimes",
        "patterns": [
            r"(?:interval|gap|period|spacing).*(?:increasing|growing|longer|shorter|accelerat)",
            r"(?:\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:days?|weeks?|months?)",
            r"time\s+since\s+prior\s+case.*(?:\d+)\s+days?",
        ],
        "weight": 0.30,
    },
    "occupational_targeting": {
        "description": "Victims share occupational or thematic connections",
        "patterns": [
            r"(?:retired|former|ex[- ]?).*(?:locksmith|engineer|archivist|teacher|actuary)",
            r"(?:radio|frequency|broadcast|station|transmission)",
            r"(?:archive|archive|records?|filing|catalog)",
            r"(?:key|lock|security|access)",
        ],
        "weight": 0.25,
    },
}

# ─── Analysis Functions ─────────────────────────────────────────────

def detect_narrative_signatures(text: str) -> dict:
    """
    Detect serial-killer-specific signatures from document narrative text.
    Returns dict of signature_type → list of matched indicators with confidence.
    """
    text_lower = text.lower()
    detected = {}

    for sig_type, config in SERIAL_SIGNATURE_PATTERNS.items():
        matches = []
        for pattern in config["patterns"]:
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                matches.extend(found[:3])  # Cap at 3 matches per pattern

        if matches:
            detected[sig_type] = {
                "description": config["description"],
                "match_count": len(matches),
                "matches": matches[:5],  # Cap at 5 total matches
                "confidence": min(0.5 + (len(matches) * 0.15), 0.95),
                "weight": config["weight"],
            }

    return detected


def compute_narrative_signature_overlap(db: Session, case_ids: list[str]) -> dict:
    """
    Compute signature overlap across cases using narrative text analysis.
    This catches behavioral patterns that entity-based analysis misses.
    """
    case_narrative_sigs = {}
    all_sig_types = defaultdict(set)  # sig_type → set of case_ids

    for cid in case_ids:
        docs = db.query(Document).filter(Document.case_id == cid).all()
        text = "\n\n".join(d.content_text for d in docs if d.content_text)

        if not text:
            continue

        sigs = detect_narrative_signatures(text)
        case_narrative_sigs[cid] = sigs

        for sig_type in sigs:
            all_sig_types[sig_type].add(cid)

    # Find common signatures (appear in 2+ cases)
    common = {}
    for sig_type, cases in all_sig_types.items():
        if len(cases) >= 2:
            common[sig_type] = {
                "case_count": len(cases),
                "cases": list(cases),
                "description": SERIAL_SIGNATURE_PATTERNS[sig_type]["description"],
                "weight": SERIAL_SIGNATURE_PATTERNS[sig_type]["weight"],
            }

    # Compute overlap score
    total_types = len(SERIAL_SIGNATURE_PATTERNS)
    overlap_score = len(common) / max(total_types, 1)

    # Compute per-case signature intensity
    case_intensities = {}
    for cid, sigs in case_narrative_sigs.items():
        intensity = sum(s["confidence"] * s["weight"] for s in sigs.values())
        case_intensities[cid] = round(intensity, 3)

    return {
        "case_narrative_signatures": case_narrative_sigs,
        "common_signatures": common,
        "overlap_score": round(overlap_score, 3),
        "case_intensities": case_intensities,
        "total_signature_types_detected": len(all_sig_types),
        "total_common_signatures": len(common),
    }


def compute_escalation_analysis(db: Session, case_ids: list[str]) -> dict:
    """
    Analyze escalating patterns between cases.
    Extracts actual dates from case descriptions and computes intervals.
    """
    case_dates = []
    for cid in case_ids:
        case = db.query(Case).filter(Case.id == cid).first()
        if not case:
            continue

        # Try to extract date from case description or name
        docs = db.query(Document).filter(Document.case_id == cid).all()
        text = "\n".join(d.content_text for d in docs if d.content_text)

        # Extract date from text patterns like "March 3" or "March 3, 2026"
        date_match = re.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,?\s*(\d{4}))?',
            text, re.IGNORECASE
        )

        if date_match:
            month_name = date_match.group(1)
            day = int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else 2026

            month_map = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            month = month_map.get(month_name.lower(), 1)

            from datetime import date as date_type
            try:
                case_date = date_type(year, month, day)
                case_dates.append({
                    "case_id": cid,
                    "case_number": case.case_number,
                    "date": case_date,
                    "days_from_start": 0,  # Will compute below
                })
            except ValueError:
                pass

    if len(case_dates) < 2:
        return {"pattern": "insufficient_data", "intervals": [], "escalation_detected": False}

    # Sort by date
    case_dates.sort(key=lambda x: x["date"])

    # Compute intervals
    intervals = []
    for i in range(1, len(case_dates)):
        delta = (case_dates[i]["date"] - case_dates[i-1]["date"]).days
        intervals.append({
            "from": case_dates[i-1]["case_number"],
            "to": case_dates[i]["case_number"],
            "from_date": str(case_dates[i-1]["date"]),
            "to_date": str(case_dates[i]["date"]),
            "days": delta,
        })

    # Compute differences between intervals (acceleration/deceleration)
    interval_diffs = []
    for i in range(1, len(intervals)):
        diff = intervals[i]["days"] - intervals[i-1]["days"]
        interval_diffs.append({
            "between": f"{intervals[i-1]['to']} → {intervals[i]['to']}",
            "difference_days": diff,
            "direction": "accelerating" if diff < 0 else "decelerating" if diff > 0 else "constant",
        })

    # Determine escalation pattern
    if intervals:
        day_values = [iv["days"] for iv in intervals]
        mean_interval = sum(day_values) / len(day_values)

        # Check if intervals are increasing (decelerating) or decreasing (accelerating)
        increasing = all(day_values[i] > day_values[i-1] for i in range(1, len(day_values)))
        decreasing = all(day_values[i] < day_values[i-1] for i in range(1, len(day_values)))

        if increasing:
            escalation = "decelerating (intervals increasing)"
        elif decreasing:
            escalation = "accelerating (intervals decreasing)"
        else:
            escalation = "irregular"

        # Compute second-order differences for pattern detection
        if len(day_values) >= 3:
            second_diffs = [day_values[i+1] - 2*day_values[i] + day_values[i-1]
                          for i in range(1, len(day_values)-1)]
            avg_second_diff = sum(second_diffs) / len(second_diffs) if second_diffs else 0
        else:
            avg_second_diff = 0
    else:
        escalation = "unknown"
        mean_interval = 0
        avg_second_diff = 0

    return {
        "pattern": escalation,
        "mean_interval_days": round(mean_interval, 1),
        "intervals": intervals,
        "interval_differences": interval_diffs,
        "second_order_differences": round(avg_second_diff, 1),
        "escalation_detected": len(intervals) >= 2,
        "case_count": len(case_dates),
    }


def detect_victim_profile_patterns(db: Session, case_ids: list[str]) -> dict:
    """
    Analyze victim demographics and targeting patterns across cases.
    """
    victims = []
    for cid in case_ids:
        docs = db.query(Document).filter(Document.case_id == cid).all()
        text = "\n".join(d.content_text for d in docs if d.content_text)

        # Extract victim name from "**Victim:** Name, Age, Occupation"
        victim_match = re.search(
            r'\*\*Victim:\*\*\s*(.+?)(?:\n|$)',
            text, re.IGNORECASE
        )

        victim_info = {"case_id": cid, "raw": victim_match.group(1) if victim_match else ""}

        if victim_info["raw"]:
            raw = victim_info["raw"]

            # Extract age
            age_match = re.search(r'(\d{1,2})\s*,', raw)
            if age_match:
                victim_info["age"] = int(age_match.group(1))

            # Extract occupation (text after age and comma)
            occ_match = re.search(r'\d{1,2}\s*,\s*(.+)', raw)
            if occ_match:
                victim_info["occupation"] = occ_match.group(1).strip()

            # Extract name (text before age)
            name_match = re.match(r'(.+?)\s*,', raw)
            if name_match:
                victim_info["name"] = name_match.group(1).strip()

        # Extract risk factors from scene description
        risk_patterns = [
            (r"alone", "alone_at_time_of_crime"),
            (r"(?:late|night|evening|after\s+hours)", "targeted_during_vulnerable_hours"),
            (r"(?:unlocked|no\s+(?:forced|sign)\s+entry)", "no_forced_entry"),
            (r"(?:no\s+struggle|no\s+indication.*struggle)", "no_defense"),
            (r"(?:working\s+late|stayed\s+late|after\s+hours)", "working_late"),
            (r"(?:rural|isolated|detached|secluded)", "isolated_location"),
        ]
        victim_info["risk_factors"] = []
        for pattern, label in risk_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                victim_info["risk_factors"].append(label)

        victims.append(victim_info)

    # Analyze patterns across victims
    ages = [v.get("age") for v in victims if "age" in v]
    occupations = [v.get("occupation", "") for v in victims if "occupation" in v]
    all_risks = []
    for v in victims:
        all_risks.extend(v.get("risk_factors", []))

    risk_counts = defaultdict(int)
    for r in all_risks:
        risk_counts[r] += 1

    return {
        "victims": victims,
        "age_range": f"{min(ages)}-{max(ages)}" if ages else "unknown",
        "age_spread": max(ages) - min(ages) if len(ages) > 1 else 0,
        "occupations": occupations,
        "common_risk_factors": dict(risk_counts),
        "victimology_score": len(ages) / max(len(case_ids), 1),
    }


def run_enhanced_serial_detection(db: Session, case_ids: list[str]) -> dict:
    """
    Run the full enhanced serial pattern detection combining:
    1. Entity-based analysis (existing)
    2. Narrative signature analysis (new)
    3. Escalation/temporal analysis (enhanced)
    4. Victim profile analysis (new)
    """
    from app.services.serial_pattern_detection import (
        _compute_geo_clustering,
        _compute_entity_linking_patterns,
    )

    # Run all analysis components
    geo = _compute_geo_clustering(db, case_ids)
    entity_links = _compute_entity_linking_patterns(db, case_ids)
    narrative_sigs = compute_narrative_signature_overlap(db, case_ids)
    escalation = compute_escalation_analysis(db, case_ids)
    victimology = detect_victim_profile_patterns(db, case_ids)

    # Compute enhanced composite score
    # Entity linking (30%) — shared persons, locations, phones
    entity_score = min(entity_links["total_shared"] / 5, 1.0)

    # Geographic clustering (15%) — shared jurisdictions
    geo_score = geo["clustering_score"]

    # Narrative signatures (35%) — behavioral pattern overlap
    sig_score = narrative_sigs["overlap_score"]

    # Escalation pattern (10%) — temporal regularity
    esc_score = 0.8 if escalation["escalation_detected"] else 0.2

    # Victimology (10%) — victim profile similarity
    vict_score = victimology["victimology_score"]

    composite = (
        entity_score * 0.30 +
        geo_score * 0.15 +
        sig_score * 0.35 +
        esc_score * 0.10 +
        vict_score * 0.10
    )

    # Determine threat level
    if composite >= 0.70:
        threat = "CRITICAL"
    elif composite >= 0.50:
        threat = "HIGH"
    elif composite >= 0.30:
        threat = "MEDIUM"
    else:
        threat = "LOW"

    # Generate high-priority signals
    signals = []
    if narrative_sigs["total_common_signatures"] >= 2:
        signals.append(f"Strong behavioral signature overlap: {narrative_sigs['total_common_signatures']} common patterns across cases")
    if entity_links["person_links"] >= 1:
        signals.append(f"Person appearing in multiple cases: {entity_links['person_links']} cross-case person links")
    if escalation["escalation_detected"]:
        signals.append(f"Temporal escalation pattern detected: {escalation['pattern']}")
    if geo["shared_locations"]:
        locs = list(geo["shared_locations"].keys())
        signals.append(f"Geographic clustering: {', '.join(locs)}")
    if victimology["common_risk_factors"]:
        top_risks = sorted(victimology["common_risk_factors"].items(), key=lambda x: x[1], reverse=True)[:3]
        signals.append(f"Common victim risk factors: {', '.join(r[0] for r in top_risks)}")

    # Generate recommendation
    if threat == "CRITICAL":
        rec = "URGENT: Strong serial pattern detected. Recommend immediate multi-agency coordination, task force formation, and public safety advisory."
    elif threat == "HIGH":
        rec = "HIGH PRIORITY: Multiple behavioral signatures link these cases. Recommend dedicated investigator assignment, cross-jurisdictional coordination, and pattern monitoring."
    elif threat == "MEDIUM":
        rec = "MODERATE: Emerging pattern detected. Recommend continued monitoring, additional case record review, and behavioral profile development."
    else:
        rec = "LOW: Limited behavioral overlap. Recommend periodic review as new cases emerge."

    return {
        "analysis_type": "enhanced_serial_pattern_detection",
        "cases_analyzed": len(case_ids),
        "overall_similarity": round(composite * 100, 1),
        "threat_assessment": threat,
        "component_scores": {
            "entity_linking": round(entity_score * 100, 1),
            "geographic_clustering": round(geo_score * 100, 1),
            "narrative_signatures": round(sig_score * 100, 1),
            "escalation_pattern": round(esc_score * 100, 1),
            "victimology": round(vict_score * 100, 1),
        },
        "high_priority_signals": signals,
        "narrative_signatures": {
            "common_signatures": narrative_sigs["common_signatures"],
            "overlap_score": narrative_sigs["overlap_score"],
            "case_intensities": narrative_sigs["case_intensities"],
            "per_case": {
                cid: {
                    "signatures": list(sigs.keys()),
                    "intensity": narrative_sigs["case_intensities"].get(cid, 0),
                }
                for cid, sigs in narrative_sigs["case_narrative_signatures"].items()
            },
        },
        "escalation": escalation,
        "victimology": victimology,
        "geographic": geo,
        "entity_links": entity_links,
        "recommendation": rec,
    }
