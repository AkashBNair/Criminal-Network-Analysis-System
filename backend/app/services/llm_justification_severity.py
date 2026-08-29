"""
LLM Justification Severity Assessor

Replaces keyword-matching for crime_severity in threat_scoring.py.
Instead of checking if "murder" appears in justification text (which
scores "cleared of murder" identically to "confessed to murder"),
this uses Groq LLM to judge the ACTUAL implication level based on context.

Caches results per unique justification_text to avoid redundant API calls.

This is a lead-generation tool, NOT an automated accusation system.
"""
import os, re, json, logging, hashlib, time as _time

logger = logging.getLogger(__name__)

# ── API Key Loading ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass


# ── File-based Cache ─────────────────────────────────────────────

class JustificationCache:
    """Cache LLM justification assessments per unique text."""

    def __init__(self):
        self._cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data"
        )
        self._cache_path = os.path.join(self._cache_dir, "justification_cache.json")
        self._cache = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._cache_path):
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info("Justification cache loaded: %d entries", len(self._cache))
            else:
                self._cache = {}
        except Exception:
            self._cache = {}

    def _save(self):
        os.makedirs(self._cache_dir, exist_ok=True)
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, default=str)

    def _text_key(self, text: str) -> str:
        """Hash the justification text for cache key."""
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def get(self, text: str) -> dict | None:
        key = self._text_key(text)
        if key in self._cache:
            result = dict(self._cache[key])
            result["from_cache"] = True
            return result
        return None

    def put(self, text: str, result: dict):
        key = self._text_key(text)
        result["cached_at"] = _time.time()
        result["from_cache"] = False
        self._cache[key] = result
        self._save()

    def clear(self):
        self._cache = {}
        self._save()
        logger.info("Justification cache cleared")

    @property
    def size(self):
        return len(self._cache)


_cache = JustificationCache()


# ── JSON Parsing ─────────────────────────────────────────────────

def _parse_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None


# ── LLM Callers ─────────────────────────────────────────────────

def _call_groq(prompt: str) -> str | None:
    try:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return None
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("Groq justification API error: %s", e)
        return None


def _call_gemini(prompt: str) -> str | None:
    try:
        from google import genai
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            return None
        client = genai.Client(api_key=api_key)
        chat = client.chats.create(
            model="gemini-3.6-flash",
            config=genai.types.GenerateContentConfig(temperature=0, max_output_tokens=512),
        )
        return chat.send_message(prompt).text
    except Exception as e:
        logger.error("Gemini justification API error: %s", e)
        return None


# ── The Prompt ───────────────────────────────────────────────────

JUSTIFICATION_PROMPT = """You are assessing how much a piece of evidence text genuinely implicates a person in criminal activity, for an investigative threat-scoring system. This is a lead-generation aid, not a guilt determination.

PERSON: {entity_name}
EVIDENCE/JUSTIFICATION TEXT: "{justification_text}"

Determine the ACTUAL implication level toward this person based on context -- not just whether crime-related words appear. A mention of a crime where the person was cleared, only a witness, falsely accused, or merely present is NOT the same as being implicated in committing it.

Return ONLY valid JSON:
{{
  "implication_level": "none|weak|moderate|strong",
  "crime_type_if_any": "specific crime mentioned, or null",
  "severity_score": 0.0_to_1.0_float,
  "reasoning": "one sentence explanation"
}}"""


# ── Severity-to-Score Mapping (matching old keyword system) ──────
# Old system used 0.0-1.0 where:
#   0.0 = no crime keyword
#   0.3 = mild mention (fraud, theft)
#   0.5 = moderate (drug trafficking, extortion)
#   0.7 = serious (assault, robbery)
#   1.0 = extreme (murder, terrorism)

IMPLICATION_TO_SCORE = {
    "none": 0.0,
    "weak": 0.3,
    "moderate": 0.6,
    "strong": 1.0,
}


# ── Main Function ────────────────────────────────────────────────

def assess_justification_severity(justification_text: str,
                                   entity_name: str) -> dict:
    """
    Use LLM to assess how strongly a justification text implicates
    a person in criminal activity.

    Returns:
        {
            "implication_level": "none|weak|moderate|strong",
            "crime_type_if_any": str | None,
            "severity_score": float (0.0-1.0),
            "reasoning": str,
            "backend": str ("groq" | "gemini" | "heuristic" | "cache")
        }
    """
    if not justification_text or len(justification_text.strip()) < 10:
        return {
            "implication_level": "none",
            "crime_type_if_any": None,
            "severity_score": 0.0,
            "reasoning": "Justification text too short to assess",
            "backend": "short_circuit",
        }

    # ── Check cache first ───────────────────────────────────────
    cached = _cache.get(justification_text)
    if cached:
        cached["backend"] = "cache"
        return cached

    # ── Check if any LLM API key is available ───────────────────
    api_key = os.environ.get("GROQ_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        result = _heuristic_assessment(justification_text, entity_name)
        _cache.put(justification_text, result)
        return result

    # ── Call LLM ────────────────────────────────────────────────
    prompt = JUSTIFICATION_PROMPT.replace(
        "{entity_name}", entity_name
    ).replace(
        "{justification_text}", justification_text[:2000]
    )

    raw = _call_groq(prompt)
    backend = "groq"

    if not raw:
        raw = _call_gemini(prompt)
        backend = "gemini"

    if not raw:
        result = _heuristic_assessment(justification_text, entity_name)
        _cache.put(justification_text, result)
        return result

    # ── Parse response ──────────────────────────────────────────
    parsed = _parse_json(raw)
    if parsed is None:
        logger.warning("Justification parse failure for '%s': %s",
                       justification_text[:80], raw[:200])
        result = {
            "implication_level": "none",
            "crime_type_if_any": None,
            "severity_score": 0.0,
            "reasoning": f"LLM parse failure — defaulting to 0. Raw: {raw[:100]}",
            "backend": f"{backend}_parse_error",
        }
        _cache.put(justification_text, result)
        return result

    # ── Normalize ───────────────────────────────────────────────
    implication = parsed.get("implication_level", "none").lower()
    if implication not in IMPLICATION_TO_SCORE:
        implication = "none"

    severity_score = parsed.get("severity_score", IMPLICATION_TO_SCORE.get(implication, 0.0))
    try:
        severity_score = max(0.0, min(1.0, float(severity_score)))
    except (TypeError, ValueError):
        severity_score = IMPLICATION_TO_SCORE.get(implication, 0.0)

    crime_type = parsed.get("crime_type_if_any")
    if crime_type and crime_type.lower() in ("null", "none", "n/a", ""):
        crime_type = None

    reasoning = str(parsed.get("reasoning", "No reasoning"))

    result = {
        "implication_level": implication,
        "crime_type_if_any": crime_type,
        "severity_score": severity_score,
        "reasoning": reasoning,
        "backend": backend,
    }

    logger.info("Justification assessed: severity=%.2f level=%s [%s] — %s",
                severity_score, implication, backend, reasoning[:80])

    _cache.put(justification_text, result)
    return result


def _heuristic_assessment(text: str, entity_name: str) -> dict:
    """
    Heuristic fallback when no LLM API key is available.
    Uses context-aware keyword matching with negation detection.
    """
    text_lower = text.lower()
    entity_lower = entity_name.lower()

    # ── Negation/ clearance patterns ────────────────────────────
    negation_patterns = [
        r'\bcleared?\b', r'\bexonerated\b', r'\bacquitted\b',
        r'\bfalse(?:ly)?\s+accus', r'\bwrongfully\s+accus',
        r'\bnot\s+implicated\b', r'\bno\s+evidence\b',
        r'\bdismissed\b', r'\bexonerat', r'\binnocent\b',
        r'\bnot\s+charged\b', r'\bdropped\s+charges?\b',
        r'\bwitness(?:es)?\s+(?:only|merely|just)\b',
        r'\bpresent\s+at\b', r'\bmerely\s+present\b',
        r'\bnot\s+involved\b', r'\bno\s+involvement\b',
    ]
    is_negated = any(re.search(p, text_lower) for p in negation_patterns)

    # ── Implication patterns ────────────────────────────────────
    CRIME_SEVERITY = {
        'murder': 1.0, 'homicide': 1.0, 'kill': 0.9, 'killed': 0.9,
        'terrorism': 1.0, 'terror': 1.0,
        'rape': 0.9, 'sexual assault': 0.85,
        'arson': 0.8, 'bomb': 0.85,
        'robbery': 0.7, 'armed robbery': 0.8, 'dacoity': 0.75,
        'assault': 0.7, 'gbh': 0.7, 'grievous': 0.7,
        'kidnapping': 0.75, 'abduction': 0.7,
        'drug': 0.5, 'ndps': 0.5, 'narcotics': 0.5, 'trafficking': 0.5,
        'smuggling': 0.5, 'possession': 0.4,
        'extortion': 0.5, 'blackmail': 0.5, 'ransom': 0.5,
        'fraud': 0.3, 'cheating': 0.3, 'forgery': 0.3,
        'theft': 0.3, 'burglary': 0.3, 'stealing': 0.3,
        'money laundering': 0.4, 'hawala': 0.4,
        'corruption': 0.3, 'bribery': 0.3,
        'illegal': 0.3, 'unlawful': 0.3,
    }

    matched_severity = 0.0
    matched_crime = None
    for keyword, severity in CRIME_SEVERITY.items():
        if keyword in text_lower:
            if severity > matched_severity:
                matched_severity = severity
                matched_crime = keyword

    # ── Apply negation discount ─────────────────────────────────
    if is_negated and matched_severity > 0:
        # Person was cleared/negated — reduce severity dramatically
        adjusted = matched_severity * 0.15
        implication = "weak" if adjusted > 0.05 else "none"
        return {
            "implication_level": implication,
            "crime_type_if_any": matched_crime,
            "severity_score": round(adjusted, 2),
            "reasoning": f"Crime keyword '{matched_crime}' present but context indicates clearance/negation",
            "backend": "heuristic_negation",
        }

    if matched_severity > 0:
        if matched_severity >= 0.7:
            implication = "strong"
        elif matched_severity >= 0.4:
            implication = "moderate"
        else:
            implication = "weak"
        return {
            "implication_level": implication,
            "crime_type_if_any": matched_crime,
            "severity_score": round(matched_severity, 2),
            "reasoning": f"Crime keyword '{matched_severity}' matched in justification text",
            "backend": "heuristic",
        }

    return {
        "implication_level": "none",
        "crime_type_if_any": None,
        "severity_score": 0.0,
        "reasoning": "No crime-related keywords found in justification",
        "backend": "heuristic",
    }
