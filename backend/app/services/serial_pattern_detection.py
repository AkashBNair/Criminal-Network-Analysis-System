"""
Serial Pattern Detection Service
=================================
Analyzes cases for behavioral patterns consistent with serial offending.
Examines MO, victimology, geography, temporal spacing, and signature behaviors.

This is a lead-generation tool — flagged patterns are candidate leads,
NOT confirmed links. All outputs require human investigator review.
"""

import re
import math
import json
import hashlib
import logging
from pathlib import Path
from collections import defaultdict
from datetime import date as date_type
from sqlalchemy.orm import Session
from app.models.models import Entity, Case, Document, EntityType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 1. DOCUMENT TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────

def _extract_case_document_text(db: Session, case_id: str) -> str:
    """Extract and concatenate all document text for a case."""
    docs = db.query(Document).filter(Document.case_id == case_id).all()
    texts = [d.content_text for d in docs if d.content_text]
    return "\n\n".join(texts)


# ─────────────────────────────────────────────────────────────
# 2. MO (Modus Operandi) EXTRACTION
# ─────────────────────────────────────────────────────────────

MO_KEYWORDS = {
    "approach": [
        "lured", "approached", "confronted", "ambush", "surprise",
        "stakeout", "followed", "watched", "targeted", "selected",
        "forced entry", "unlocked", "door", "window", "invited",
        "trusted", "known to victim",
    ],
    "control": [
        "restrained", "tied", "bound", "gagged", "blindfolded",
        "threatened", "coerced", "intimidated", "held",
        "locked", "confined", "drugged", "sedated",
    ],
    "violence": [
        "strangulation", "stabbing", "blunt force", "shooting",
        "overkill", "excessive force", "brutal", "violent",
        "beaten", "assaulted", "injuries",
    ],
    "targeting": [
        "alone", "vulnerable", "isolated", "late night",
        "after hours", "working late", "no witnesses",
        "no forced entry", "no struggle",
    ],
    "geographic": [
        "rural", "remote", "isolated", "secluded",
        "abandoned", "vacant", "detached",
    ],
    "temporal": [
        "night", "evening", "dawn", "late",
        "weekend", "holiday", "off hours",
    ],
    "organizational": [
        "syndicate", "network", "ring", "cartel", "faction",
        "courier", "mule", "stash", "safe house", "drop point",
        "cut-out", "front", "shell company", "benami",
        "phone tree", "burner", "coded language",
        "enforcer", "lieutenant", "kingpin", "financier",
        "route", "corridor", "smuggling route",
        "extortion", "protection", "racket",
    ],
    "financial": [
        "hawala", "hundi", "laundering", "proceeds",
        "circular", "round-trip", "kickback",
        "layering", "placement", "integration",
        "ghost employee", "fake invoice",
        "shell company", "dummy account",
        "cash intensive", "underreporting",
    ],
}

# Keywords that indicate specific MO dimensions
MO_DIMENSION_PATTERNS = {
    "entry_method": [
        r"forced?\s+entry", r"unlocked", r"door\s+was\s+(?:open|unlocked|ajar)",
        r"window\s+(?:open|broken|forced)", r"invited\s+in",
        r"no\s+sign\s+of\s+(?:forced\s+)?entry",
    ],
    "weapon_type": [
        r"(?:sharp|blunt)\s+(?:object|instrument|weapon)",
        r"(?:knife|gun|firearm|bat|pipe|rope|cord)",
        r"strangulation", r"asphyxiation", r"stab(?:bing|s)?",
    ],
    "time_of_crime": [
        r"(?:late|early)\s+(?:night|morning|evening)",
        r"(?:between|around|near)\s+\d{1,2}\s*(?:am|pm|AM|PM)",
        r"(?:after|before)\s+(?:midnight|dawn|sunrise|sunset)",
        r"(?:night|evening|dawn|morning)",
    ],
    "concealment": [
        r"(?:body|victim)\s+(?:found|hidden|concealed|dumped|left)",
        r"(?:cleaned|wiped|removed)\s+(?:evidence|fingerprints|traces)",
        r"staged", r"posed",
    ],
    "communication": [
        r"(?:coded|encrypted|secret)\s+(?:language|message|channel)",
        r"(?:burner|prepaid|disposable)\s+(?:phone|sim)",
        r"(?:phone|sim)\s+(?:swap|swappped|changed)",
        r"(?:via|through)\s+(?:intermediary|middleman|cut[- ]?out)",
    ],
    "financial_flow": [
        r"(?:hawala|hundi|underground\s+banking)",
        r"(?:circular|round[- ]?trip)\s+(?:transfer|transaction)",
        r"(?:launder|laundering|layering)",
        r"(?:shell|dummy|front)\s+(?:company|account|entity)",
        r"(?:benami|benamdar)",
    ],
}


class MOCache:
    """File-based cache for LLM MO extraction results, keyed by case_id."""

    def __init__(self):
        self.cache_dir = Path(__file__).resolve().parents[3] / "data"
        self.cache_file = self.cache_dir / "mo_cache.json"
        self.cache = self._load()

    def _load(self):
        try:
            if self.cache_file.exists():
                return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self.cache, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, case_id: str):
        return self.cache.get(case_id)

    def set(self, case_id: str, result: dict):
        self.cache[case_id] = result
        self._save()

    def clear(self):
        self.cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()

_mo_cache = MOCache()


MO_LLM_PROMPT_TEMPLATE = None  # built at module load


def _build_mo_prompt(case_number, text):
    return (
        'You are extracting genuine Modus Operandi (MO) indicators from a police case '
        'narrative, for investigative case-linkage analysis -- a lead-generation aid, '
        'not a guilt determination.\n\n'
        'CASE: ' + case_number + '\n'
        'NARRATIVE TEXT: "' + text[:4000] + '"\n\n'
        'Identify genuine MO indicators across these dimensions, based on what '
        'actually happened in this case (not incidental word mentions):\n'
        '- approach_method: how the offender approached/engaged the victim\n'
        '- control_method: how the offender controlled/restrained the victim\n'
        '- violence_level: degree and nature of violence used\n'
        '- targeting_pattern: how/why this victim was selected\n'
        '- organizational: evidence of organized group structure\n'
        '- financial: evidence of financial criminal methods\n\n'
        'For each dimension, only report an indicator if the text genuinely describes '
        'that behavior occurring -- not if a related word appears without describing '
        'an actual action taken.\n\n'
        'Return ONLY valid JSON:\n'
        '{\n'
        '  "approach_method": "<description or null>",\n'
        '  "control_method": "<description or null>",\n'
        '  "violence_level": "<description or null>",\n'
        '  "targeting_pattern": "<description or null>",\n'
        '  "organizational": "<description or null>",\n'
        '  "financial": "<description or null>",\n'
        '  "confidence": <0-100 integer>,\n'
        '  "reasoning": "<1-2 sentences>"\n'
        '}'
    )


def _call_groq_mo(text, case_number):
    """Call Groq API for MO extraction."""
    try:
        import os
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            env_path = Path(__file__).resolve().parents[3] / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GROQ_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not api_key:
            return None

        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = _build_mo_prompt(case_number, text)
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are a criminal case analyst. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("Groq MO extraction failed for %s: %s", case_number, e)
        return None


def _call_gemini_mo(text, case_number):
    """Fallback to Gemini API for MO extraction."""
    try:
        import os
        import urllib.request
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            env_path = Path(__file__).resolve().parents[3] / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not api_key:
            return None

        prompt = _build_mo_prompt(case_number, text)
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + api_key
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 800}
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("Gemini MO extraction failed for %s: %s", case_number, e)
        return None


def _heuristic_mo(text):
    """Fallback: keyword-based MO extraction when no LLM is available."""
    if not text:
        return {}
    text_lower = text.lower()
    result = {}
    for dimension, keywords in MO_KEYWORDS.items():
        matches = []
        for kw in keywords:
            if kw.lower() in text_lower:
                matches.append(kw)
        if matches:
            result[dimension] = matches
    for dimension, patterns in MO_DIMENSION_PATTERNS.items():
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, text_lower)
            if found:
                matches.extend(found[:3])
        if matches:
            result[dimension] = matches
    return result


def assess_mo_indicators(context_text: str, case_number: str) -> dict:
    """
    LLM-powered MO indicator extraction.
    Falls back to keyword heuristic if no LLM is available.
    """
    if not context_text or not context_text.strip():
        return {}

    # Try Groq first
    result = _call_groq_mo(context_text, case_number)
    if result:
        return result

    # Try Gemini fallback
    result = _call_gemini_mo(context_text, case_number)
    if result:
        return result

    # Heuristic fallback
    return _heuristic_mo(context_text)


def _extract_mo_from_text(text: str, case_number: str = "unknown", case_id: str = None) -> dict:
    """
    Extract MO indicators from document text.
    Uses LLM contextual analysis with file-based caching per case_id.
    Falls back to keyword matching if no LLM is available.
    """
    if not text:
        return {}

    # Check cache first
    if case_id:
        cached = _mo_cache.get(case_id)
        if cached is not None:
            logger.info("MO cache HIT for case %s", case_id)
            return cached

    # LLM extraction
    llm_result = assess_mo_indicators(text, case_number)

    if llm_result:
        # Cache the result
        if case_id:
            _mo_cache.set(case_id, llm_result)
        return llm_result

    # Heuristic fallback (no cache needed for this)
    return _heuristic_mo(text)


# ─────────────────────────────────────────────────────────────
# 3. VICTIMOLOGY EXTRACTION
# ─────────────────────────────────────────────────────────────

def _extract_victimology_from_text(text: str) -> dict:
    """Extract victimology signals from document text."""
    if not text:
        return {}

    result = {
        "age_mentions": [],
        "gender_mentions": [],
        "risk_factors": [],
        "victim_profile": [],
    }

    text_lower = text.lower()

    # Extract ages — look for patterns like "55-year-old", "age 55", "55 years"
    age_patterns = [
        r'(\d{1,2})[\s-]*(?:year[\s-]*old|yr[\s-]*old|y/?o)',
        r'(?:age|aged)\s*[:\s]*(\d{1,2})',
        r'(\d{1,2})\s*years?\s*(?:of\s+age|old)',
    ]
    for pat in age_patterns:
        for m in re.finditer(pat, text_lower):
            age = int(m.group(1))
            if 10 <= age <= 100:  # sanity range
                result["age_mentions"].append(age)

    # Extract gender indicators
    gender_terms = {
        "male": ["he", "him", "his", "male", "man", "boy", "gentleman"],
        "female": ["she", "her", "hers", "female", "woman", "girl", "lady"],
    }
    for gender, terms in gender_terms.items():
        count = sum(1 for t in terms if re.search(r'\b' + t + r'\b', text_lower))
        if count >= 2:  # Require multiple mentions to reduce false positives
            result["gender_mentions"].append(gender)

    # Extract risk factors
    risk_patterns = [
        (r"\balone\b", "alone_at_time_of_crime"),
        (r"(?:late|night|evening|after\s+hours)", "targeted_during_vulnerable_hours"),
        (r"(?:unlocked|no\s+(?:forced|sign)\s+entry)", "no_forced_entry"),
        (r"(?:no\s+struggle|no\s+indication.*struggle)", "no_defense"),
        (r"(?:working\s+late|stayed\s+late|after\s+hours)", "working_late"),
        (r"(?:rural|isolated|detached|secluded)", "isolated_location"),
        (r"(?:elderly|older|senior)", "elderly_victim"),
        (r"(?:lived\s+alone|single)", "lives_alone"),
    ]
    for pattern, label in risk_patterns:
        if re.search(pattern, text_lower):
            result["risk_factors"].append(label)

    # Victim profile extraction (e.g., "**Victim:** Name, Age, Occupation")
    victim_match = re.search(
        r'\*?\*?victim:?\*?\*?\s*(.+?)(?:\n|$)',
        text, re.IGNORECASE
    )
    if victim_match:
        result["victim_profile"].append(victim_match.group(1).strip()[:200])

    # Deduplicate ages
    result["age_mentions"] = sorted(set(result["age_mentions"]))
    result["gender_mentions"] = list(set(result["gender_mentions"]))
    result["risk_factors"] = list(set(result["risk_factors"]))

    return result


# ─────────────────────────────────────────────────────────────
# 4. SIGNATURE OVERLAP COMPUTATION
# ─────────────────────────────────────────────────────────────

SIGNATURE_TERMS = [
    # Serial killer behavioral signatures
    "overkill", "staged", "posed", "trophy", "ritualistic",
    "signature", "escalat", "pattern", "ritual",
    "placed", "deliberately", "neatly",
    "dead frequency", "static only", "off-air",
    "missing item", "gap", "took",
    "occupational", "radio", "frequency", "locksmith",
    "archivist", "key",
    # Organized crime / trafficking signatures
    "syndicate", "network", "ring", "cartel", "faction",
    "courier", "mule", "stash", "safe house", "drop point",
    "cut-out", "cutout", "front", "shell company",
    "hawala", "hundi", "layering", "placement",
    "proceeds", "laundering", "account",
    "phone tree", "burner", "swap", "coded", "coded language",
    "territory", "turf", "territorial",
    "enforcer", "lieutenant", "kingpin", "financier",
    "smuggling", "trafficking", "route", "corridor",
    "extortion", "protection", "racket",
    # Financial crime signatures
    "circular", "round-trip", "round trip", "kickback",
    "ghost employee", "fake invoice", "benami",
    " shell ", "dummy",
]


def _compute_signature_overlap(db: Session, case_ids: list, case_texts: dict) -> dict:
    """
    Compute behavioral signature overlap across cases.
    Returns per-case signature terms and cross-case overlap metrics.
    """
    case_signatures = {}
    all_terms_by_case = {}

    for cid in case_ids:
        text = case_texts.get(cid, "")
        if not text:
            case_signatures[cid] = {"signature_terms": [], "intensity": 0.0}
            continue

        text_lower = text.lower()
        matched_terms = []
        for term in SIGNATURE_TERMS:
            if term in text_lower:
                matched_terms.append(term)

        # Compute intensity as fraction of signature terms found
        intensity = len(matched_terms) / max(len(SIGNATURE_TERMS), 1)
        case_signatures[cid] = {
            "signature_terms": matched_terms,
            "intensity": round(intensity, 3),
        }
        all_terms_by_case[cid] = set(matched_terms)

    # Cross-case overlap matrix
    pairwise_overlap = {}
    for i, cid1 in enumerate(case_ids):
        for j, cid2 in enumerate(case_ids):
            if i >= j:
                continue
            set1 = all_terms_by_case.get(cid1, set())
            set2 = all_terms_by_case.get(cid2, set())
            union = set1 | set2
            intersection = set1 & set2
            overlap = len(intersection) / len(union) if union else 0.0
            pairwise_overlap[(cid1, cid2)] = {
                "overlap": round(overlap, 3),
                "shared_terms": list(intersection),
                "shared_count": len(intersection),
            }

    # Overall overlap score (average of all pairwise overlaps)
    if pairwise_overlap:
        avg_overlap = sum(p["overlap"] for p in pairwise_overlap.values()) / len(pairwise_overlap)
    else:
        avg_overlap = 0.0

    # Common terms across ALL cases
    if case_ids:
        common_all = all_terms_by_case.get(case_ids[0], set())
        for cid in case_ids[1:]:
            common_all = common_all & all_terms_by_case.get(cid, set())
    else:
        common_all = set()

    return {
        "case_signatures": case_signatures,
        "pairwise_overlap": pairwise_overlap,
        "avg_overlap": round(avg_overlap, 3),
        "common_terms_all_cases": list(common_all),
        "total_cases": len(case_ids),
    }


# ─────────────────────────────────────────────────────────────
# 5. GEOGRAPHIC CLUSTERING
# ─────────────────────────────────────────────────────────────

def _compute_geo_clustering(db: Session, case_ids: list) -> dict:
    """
    Compute geographic clustering — shared locations across cases.
    """
    location_cases = defaultdict(set)  # location_name → set of case_ids
    case_locations = {}  # case_id → set of location names

    for cid in case_ids:
        locations = db.query(Entity).filter(
            Entity.case_id == cid,
            Entity.entity_type == EntityType.LOCATION,
            Entity.is_merged_into.is_(None),
        ).all()
        loc_names = {e.name.lower().strip() for e in locations}
        case_locations[cid] = loc_names
        for loc in loc_names:
            location_cases[loc].add(cid)

    # Find locations that appear in multiple cases
    shared_locations = {
        loc: list(cases)
        for loc, cases in location_cases.items()
        if len(cases) >= 2
    }

    # Compute clustering score
    total_possible_pairs = len(case_ids) * (len(case_ids) - 1) / 2 if len(case_ids) > 1 else 1
    pairs_with_shared = 0
    for cid1_idx, cid1 in enumerate(case_ids):
        for cid2 in case_ids[cid1_idx + 1:]:
            shared = case_locations.get(cid1, set()) & case_locations.get(cid2, set())
            if shared:
                pairs_with_shared += 1

    clustering_score = pairs_with_shared / total_possible_pairs if total_possible_pairs > 0 else 0.0

    return {
        "shared_locations": shared_locations,
        "clustering_score": round(clustering_score, 3),
        "total_shared_locations": len(shared_locations),
        "case_locations": {cid: list(locs) for cid, locs in case_locations.items()},
    }


# ─────────────────────────────────────────────────────────────
# 6. ENTITY LINKING PATTERNS
# ─────────────────────────────────────────────────────────────

def _compute_entity_linking_patterns(db: Session, case_ids: list) -> dict:
    """
    Compute entity-based cross-case linking patterns.
    Counts shared persons, phones, vehicles, organizations across cases.
    """
    case_entities = {}  # case_id → {entity_type → [names]}
    entity_case_map = defaultdict(lambda: defaultdict(set))  # entity_name → {case_ids by type}

    for cid in case_ids:
        entities = db.query(Entity).filter(
            Entity.case_id == cid,
            Entity.is_merged_into.is_(None),
        ).all()
        by_type = defaultdict(list)
        for e in entities:
            by_type[e.entity_type.value].append(e.name)
            entity_case_map[e.name.lower().strip()][e.entity_type.value].add(cid)
        case_entities[cid] = dict(by_type)

    # Find cross-case links
    person_links = 0
    phone_links = 0
    vehicle_links = 0
    total_shared = 0

    for name, type_cases in entity_case_map.items():
        for etype, cids in type_cases.items():
            if len(cids) >= 2:
                total_shared += 1
                if etype == "Person":
                    person_links += 1
                elif etype == "Phone":
                    phone_links += 1
                elif etype == "Vehicle":
                    vehicle_links += 1

    return {
        "person_links": person_links,
        "phone_links": phone_links,
        "vehicle_links": vehicle_links,
        "total_shared": total_shared,
        "entity_case_map": {
            name: {etype: list(cids) for etype, cids in type_cases.items()}
            for name, type_cases in entity_case_map.items()
            if any(len(c) >= 2 for c in type_cases.values())
        },
    }


# ─────────────────────────────────────────────────────────────
# 7. CLUSTERING — NEW COMPOSITE SCORING
# ─────────────────────────────────────────────────────────────

def _jaccard(set_a: set, set_b: set) -> float:
    """Simple Jaccard similarity, safe for empty sets."""
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _signature_jaccard(case_signatures: dict, cid1: str, cid2: str) -> float:
    """
    Compare signature_terms between two cases. This is the STRONGEST
    serial-offender signal because signature behavior tends to persist
    even when MO evolves.
    """
    sig1 = set(case_signatures.get(cid1, {}).get("signature_terms", []))
    sig2 = set(case_signatures.get(cid2, {}).get("signature_terms", []))
    return _jaccard(sig1, sig2)


def _string_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two free-text descriptions."""
    if not a or not b:
        return 0.0
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    # Remove stop words
    stops = {"the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at", "by", "is", "was", "were", "that", "this", "from", "which", "not", "no", "none"}
    words_a -= stops
    words_b -= stops
    return _jaccard(words_a, words_b)


def _mo_jaccard(mo_by_case: dict, cid1: str, cid2: str) -> float:
    """
    Compare MO indicators across all dimensions between two cases.
    Handles both old keyword-list format and new LLM structured format.
    """
    mo1 = mo_by_case.get(cid1, {})
    mo2 = mo_by_case.get(cid2, {})

    # Filter out metadata keys added by LLM extraction
    skip_keys = {"confidence", "reasoning"}
    dims = (set(mo1.keys()) | set(mo2.keys())) - skip_keys

    if not dims:
        return 0.0

    scores = []
    for dim in dims:
        v1 = mo1.get(dim)
        v2 = mo2.get(dim)

        # Handle null/None
        if v1 is None and v2 is None:
            continue
        if v1 is None or v2 is None:
            scores.append(0.0)
            continue

        # New LLM format: values are strings (descriptions)
        if isinstance(v1, str) and isinstance(v2, str):
            scores.append(_string_similarity(v1, v2))
        # Old keyword format: values are lists of matched keywords
        elif isinstance(v1, list) and isinstance(v2, list):
            scores.append(_jaccard(set(v1), set(v2)))
        else:
            scores.append(0.0)

    return sum(scores) / len(scores) if scores else 0.0


def _victimology_similarity(vict_by_case: dict, cid1: str, cid2: str) -> float:
    """
    Compare victimology signals: age-range overlap, gender match,
    shared risk factors. Returns 0-1 composite.
    """
    v1 = vict_by_case.get(cid1, {})
    v2 = vict_by_case.get(cid2, {})

    sub_scores = []

    # Age similarity
    ages1 = v1.get("age_mentions", [])
    ages2 = v2.get("age_mentions", [])
    if ages1 and ages2:
        avg1 = sum(ages1) / len(ages1)
        avg2 = sum(ages2) / len(ages2)
        diff = abs(avg1 - avg2)
        age_score = max(0.0, 1.0 - diff / 15.0)
        sub_scores.append(age_score)

    # Gender match
    g1 = set(v1.get("gender_mentions", []))
    g2 = set(v2.get("gender_mentions", []))
    if g1 and g2:
        sub_scores.append(1.0 if g1 == g2 else 0.0)

    # Risk factor overlap
    r1 = set(v1.get("risk_factors", []))
    r2 = set(v2.get("risk_factors", []))
    if r1 or r2:
        sub_scores.append(_jaccard(r1, r2))

    return sum(sub_scores) / len(sub_scores) if sub_scores else 0.0


def _identify_serial_clusters(db, case_ids: list, similarity: dict) -> list:
    """
    Identify clusters of cases that may be linked as serial offenses,
    using a COMPOSITE behavioral score (signature + MO + victimology +
    shared entities) rather than shared entities alone.

    Serial offenders typically do NOT share named entities across cases
    (different victims, different locations) — they share behavioral
    SIGNATURE. Entity overlap is kept as one signal but is no longer
    the sole driver.
    """
    components = similarity.get("components", {})
    case_signatures = components.get("signatures", {}).get("case_signatures", {})

    # Pull MO + victimology per case (LLM-based, cached per case)
    mo_by_case = {}
    vict_by_case = {}
    for cid in case_ids:
        text = _extract_case_document_text(db, cid)
        case_obj = db.query(Case).filter(Case.id == cid).first()
        cnum = case_obj.case_number if case_obj else cid
        mo_by_case[cid] = _extract_mo_from_text(text, case_number=cnum, case_id=cid) if text else {}
        vict_by_case[cid] = _extract_victimology_from_text(text) if text else {}

    # Shared named entities
    case_entity_sets = {}
    for cid in case_ids:
        entities = db.query(Entity).filter(
            Entity.case_id == cid, Entity.is_merged_into.is_(None)
        ).all()
        case_entity_sets[cid] = {e.name.lower().strip() for e in entities}

    W_SIGNATURE = 0.40
    W_MO = 0.25
    W_VICTIMOLOGY = 0.20
    W_ENTITY = 0.15

    pairwise = {}
    all_scores_debug = []

    for i, cid1 in enumerate(case_ids):
        for j, cid2 in enumerate(case_ids):
            if i >= j:
                continue

            sig_score = _signature_jaccard(case_signatures, cid1, cid2)
            mo_score = _mo_jaccard(mo_by_case, cid1, cid2)
            vict_score = _victimology_similarity(vict_by_case, cid1, cid2)

            set1 = case_entity_sets.get(cid1, set())
            set2 = case_entity_sets.get(cid2, set())
            entity_score = _jaccard(set1, set2)

            composite = (
                sig_score * W_SIGNATURE
                + mo_score * W_MO
                + vict_score * W_VICTIMOLOGY
                + entity_score * W_ENTITY
            )

            pairwise[(cid1, cid2)] = {
                "composite": round(composite, 3),
                "signature_score": round(sig_score, 3),
                "mo_score": round(mo_score, 3),
                "victimology_score": round(vict_score, 3),
                "entity_score": round(entity_score, 3),
                "shared_names": list(set1 & set2)[:5],
            }
            all_scores_debug.append(composite)

    if all_scores_debug:
        logger.info(
            "Pairwise composite scores: min=%.3f max=%.3f mean=%.3f n=%d",
            min(all_scores_debug), max(all_scores_debug),
            sum(all_scores_debug) / len(all_scores_debug),
            len(all_scores_debug),
        )

    threshold = 0.25
    clusters = []
    visited = set()

    for cid in case_ids:
        if cid in visited:
            continue
        cluster = [cid]
        visited.add(cid)

        for (c1, c2), data in pairwise.items():
            if c1 in cluster and c2 not in visited and data["composite"] >= threshold:
                cluster.append(c2)
                visited.add(c2)
            elif c2 in cluster and c1 not in visited and data["composite"] >= threshold:
                cluster.append(c1)
                visited.add(c1)

        if len(cluster) >= 2:
            case_details = []
            for cid_ in cluster:
                case = db.query(Case).filter(Case.id == cid_).first()
                if case:
                    case_details.append({
                        "case_id": cid_,
                        "case_number": case.case_number,
                        "case_name": case.name,
                    })

            shared_signature_terms = set(
                case_signatures.get(cluster[0], {}).get("signature_terms", [])
            )
            for cid_ in cluster[1:]:
                shared_signature_terms &= set(
                    case_signatures.get(cid_, {}).get("signature_terms", [])
                )

            shared_entities = set(case_entity_sets.get(cluster[0], set()))
            for cid_ in cluster[1:]:
                shared_entities &= case_entity_sets.get(cid_, set())

            pair_scores = [
                pairwise[(c1, c2)]["composite"]
                for c1 in cluster for c2 in cluster
                if (c1, c2) in pairwise
            ]
            avg_similarity = round(
                sum(pair_scores) / len(pair_scores), 3
            ) if pair_scores else 0.0

            clusters.append({
                "cluster_id": f"cluster_{len(clusters) + 1}",
                "case_count": len(cluster),
                "cases": case_details,
                "shared_signature_terms": list(shared_signature_terms),
                "shared_entities": list(shared_entities)[:10],
                "avg_similarity": avg_similarity,
                "pairwise_scores": [
                    {
                        "cases": [c1, c2],
                        "composite": pairwise[(c1, c2)]["composite"],
                        "signature": pairwise[(c1, c2)]["signature_score"],
                        "mo": pairwise[(c1, c2)]["mo_score"],
                        "victimology": pairwise[(c1, c2)]["victimology_score"],
                        "entity": pairwise[(c1, c2)]["entity_score"],
                    }
                    for c1, c2 in pairwise if c1 in cluster and c2 in cluster
                ],
                "explanation": _build_cluster_explanation(
                    cluster, pairwise, shared_signature_terms, shared_entities
                ),
            })

    clusters.sort(key=lambda x: x["avg_similarity"], reverse=True)
    return clusters


def _build_cluster_explanation(cluster, pairwise, shared_signature_terms, shared_entities) -> str:
    """Human-readable explanation for why these cases were clustered."""
    parts = [f"{len(cluster)} cases flagged as a potential serial cluster."]

    if shared_signature_terms:
        parts.append(
            f"Shared signature behaviors: {', '.join(sorted(shared_signature_terms))}."
        )
    if shared_entities:
        parts.append(
            f"Shared named entities across all cases: {', '.join(sorted(shared_entities))}."
        )
    if not shared_signature_terms and not shared_entities:
        parts.append(
            "No universally shared signature/entity across ALL cases in cluster — "
            "link is driven by pairwise MO/victimology similarity. Review individual "
            "pair scores before treating this as a strong lead."
        )

    parts.append(
        "This is a candidate lead only. Requires human investigator review — "
        "not a determination of guilt or confirmed linkage."
    )
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────
# 8. TEMPORAL / ESCALATION ANALYSIS
# ─────────────────────────────────────────────────────────────

def _compute_temporal_patterns(db: Session, case_ids: list) -> dict:
    """
    Compute temporal spacing and escalation patterns between cases.
    """
    case_dates = []
    for cid in case_ids:
        case = db.query(Case).filter(Case.id == cid).first()
        if not case:
            continue

        docs = db.query(Document).filter(Document.case_id == cid).all()
        text = "\n".join(d.content_text for d in docs if d.content_text)

        # Extract date from text
        date_match = re.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s+(\d{1,2})(?:,?\s*(\d{4}))?',
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
            try:
                case_date = date_type(year, month, day)
                case_dates.append({
                    "case_id": cid,
                    "case_number": case.case_number,
                    "date": case_date,
                })
            except ValueError:
                pass

    if len(case_dates) < 2:
        return {
            "pattern": "insufficient_data",
            "intervals": [],
            "escalation_detected": False,
            "mean_interval_days": 0,
        }

    case_dates.sort(key=lambda x: x["date"])

    intervals = []
    for i in range(1, len(case_dates)):
        delta = (case_dates[i]["date"] - case_dates[i - 1]["date"]).days
        intervals.append({
            "from": case_dates[i - 1]["case_number"],
            "to": case_dates[i]["case_number"],
            "from_date": str(case_dates[i - 1]["date"]),
            "to_date": str(case_dates[i]["date"]),
            "days": delta,
        })

    day_values = [iv["days"] for iv in intervals]
    mean_interval = sum(day_values) / len(day_values)

    increasing = all(day_values[i] > day_values[i - 1] for i in range(1, len(day_values)))
    decreasing = all(day_values[i] < day_values[i - 1] for i in range(1, len(day_values)))

    if increasing:
        escalation = "decelerating (intervals increasing)"
    elif decreasing:
        escalation = "accelerating (intervals decreasing)"
    else:
        escalation = "irregular"

    return {
        "pattern": escalation,
        "mean_interval_days": round(mean_interval, 1),
        "intervals": intervals,
        "escalation_detected": len(intervals) >= 2,
        "case_count": len(case_dates),
    }


# ─────────────────────────────────────────────────────────────
# 9. MAIN DETECTION ENTRY POINT
# ─────────────────────────────────────────────────────────────

def detect_serial_patterns(db: Session, case_ids: list) -> dict:
    """
    Main entry point: run all serial pattern detection components
    and return a combined analysis.
    """
    if not case_ids:
        return {"error": "No cases provided"}

    # Extract text for all cases
    case_texts = {cid: _extract_case_document_text(db, cid) for cid in case_ids}

    # 1. Signature overlap
    signatures = _compute_signature_overlap(db, case_ids, case_texts)

    # 2. Geographic clustering
    geo = _compute_geo_clustering(db, case_ids)

    # 3. Entity linking
    entity_links = _compute_entity_linking_patterns(db, case_ids)

    # 4. Temporal patterns
    temporal = _compute_temporal_patterns(db, case_ids)

    # 5. MO extraction per case (LLM-based, cached)
    mo_by_case = {}
    for cid, text in case_texts.items():
        case_obj = db.query(Case).filter(Case.id == cid).first()
        cnum = case_obj.case_number if case_obj else cid
        mo_by_case[cid] = _extract_mo_from_text(text, case_number=cnum, case_id=cid)

    # 6. Victimology per case
    vict_by_case = {cid: _extract_victimology_from_text(text) for cid, text in case_texts.items()}

    # Build similarity dict for clustering
    similarity = {"components": {"signatures": signatures}}

    # 7. Composite clustering
    clusters = _identify_serial_clusters(db, case_ids, similarity)

    # Compute overall similarity score
    entity_score = min(entity_links["total_shared"] / max(len(case_ids), 1), 1.0)
    geo_score = geo["clustering_score"]
    sig_score = signatures["avg_overlap"]
    esc_score = 0.8 if temporal["escalation_detected"] else 0.2

    composite = (
        entity_score * 0.30
        + geo_score * 0.15
        + sig_score * 0.35
        + esc_score * 0.10
    )

    if composite >= 0.70:
        threat = "CRITICAL"
    elif composite >= 0.50:
        threat = "HIGH"
    elif composite >= 0.30:
        threat = "MEDIUM"
    else:
        threat = "LOW"

    return {
        "cases_analyzed": len(case_ids),
        "overall_similarity": round(composite * 100, 1),
        "threat_assessment": threat,
        "component_scores": {
            "entity_linking": round(entity_score * 100, 1),
            "geographic_clustering": round(geo_score * 100, 1),
            "narrative_signatures": round(sig_score * 100, 1),
            "escalation_pattern": round(esc_score * 100, 1),
        },
        "signatures": signatures,
        "geographic": geo,
        "entity_links": entity_links,
        "temporal": temporal,
        "mo_by_case": mo_by_case,
        "victims": vict_by_case,
        "clusters": clusters,
    }


# ─────────────────────────────────────────────────────────────
# 10. LLM-POWERED PAIRWISE ANALYSIS
# ─────────────────────────────────────────────────────────────

def run_llm_pairwise_analysis(db, case_ids: list) -> dict:
    """
    Run LLM-powered behavioral linkage analysis across all case pairs.
    Returns pairwise results with reasoning and false-positive tracking.
    """
    from app.services.llm_linkage_analysis import llm_case_pair_analysis, pre_filter_pairs, SIMILARITY_MAP

    # Build case data for pre-filter
    case_data = []
    for cid in case_ids:
        case = db.query(Case).filter(Case.id == cid).first()
        text = _extract_case_document_text(db, cid)
        case_data.append({
            "case_id": cid,
            "case_number": case.case_number if case else cid,
            "name": case.name if case else "",
            "text": text or "",
            "date_str": None,  # Could extract from case metadata
        })

    # Pre-filter
    pairs = pre_filter_pairs(case_data)
    logger.info("LLM analysis: %d pairs to analyze", len(pairs))

    # Run analysis on each pair
    results = {}
    for i, j in pairs:
        a = case_data[i]
        b = case_data[j]
        result = llm_case_pair_analysis(
            a["text"], a["case_number"],
            b["text"], b["case_number"],
        )
        pair_key = f"{a['case_number']}|{b['case_number']}"
        results[pair_key] = result

    return {
        "pair_results": results,
        "total_pairs": len(pairs),
        "cases_analyzed": len(case_ids),
    }
