"""
LLM Entity Validator
Uses Groq API (or Gemini fallback) to validate whether a spaCy NER candidate
is a genuine named entity or a false-positive generic word misclassified as PERSON.

Inserted as a gate AFTER regex/structural/entity_type_classifier checks in
entity_extraction.py, ONLY for spaCy NER section (section 6).

This is a lead-generation tool, NOT an automated accusation system.
"""
import os, re, json, logging

logger = logging.getLogger(__name__)

# ── API Key Loading ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass


# ── LLM Call: Groq (primary) → Gemini (fallback) ────────────────

def _call_groq_for_validation(prompt: str) -> str | None:
    """Call Groq API for entity validation."""
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
        logger.error("Groq validation API error: %s", e)
        return None


def _call_gemini_for_validation(prompt: str) -> str | None:
    """Call Gemini API for entity validation (fallback)."""
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
        logger.error("Gemini validation API error: %s", e)
        return None


def _parse_json_response(raw: str) -> dict | None:
    """Parse JSON from LLM response, handling markdown fences and truncation."""
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
        logger.warning("Failed to parse validation JSON: %s", text[:200])
        return None


# ── The Validation Prompt ───────────────────────────────────────

VALIDATION_PROMPT = """You are validating whether an extracted string is a genuine named entity worth tracking in a criminal case investigation system, or a false-positive extraction error from an NER model.

EXTRACTED CANDIDATE: "{candidate_name}"
GUESSED TYPE: {entity_type_guess}
CONTEXT (sentence where this was found):
"{surrounding_context}"

Determine if this is a genuine, specific, trackable entity -- a real person's name, OR a nickname/alias CLEARLY used to refer to a specific individual in this context -- versus a false positive: a generic word, common noun, number word, animal/object reference used descriptively (not as someone's alias), or a misclassified fragment.

Reject unless context explicitly supports it being used AS A NAME for a specific person (e.g. "the man known as Wolf" = genuine; "wearing a wolf mask" or just "Wolf" with no supporting context = false positive). When in doubt with weak/ambiguous context, REJECT rather than accept -- false negatives here are safer than false positives feeding into suspect scoring.

Return ONLY valid JSON:
{{
  "is_genuine_entity": true_or_false,
  "confidence": 0_to_100_integer,
  "reasoning": "one_sentence_explanation"
}}"""


# ── High-confidence terms that skip LLM (no API call needed) ────
# These are clearly genuine based on structural patterns or known-good context.
# We skip the LLM call for these to save API quota.
_ALWAYS_ACCEPT = {
    # Already validated by entity_type_classifier / regex layers
}

# ── Terms that are ALWAYS rejected (no LLM needed) ──────────────
# These are clearly false-positive spaCy misclassifications.
_ALWAYS_REJECT = {
    # number words that spaCy sometimes labels as PERSON
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty",
    "seventy", "eighty", "ninety", "hundred", "thousand", "million", "billion",
    # common English words spaCy misclassifies
    "the", "this", "that", "these", "those", "which", "where", "when", "how",
}


def validate_entity_candidate(candidate_name: str, entity_type_guess: str,
                               surrounding_context: str) -> dict:
    """
    Use LLM to validate whether an extracted entity candidate is genuine.

    Returns:
        {
            "is_genuine_entity": bool,
            "confidence": int (0-100),
            "reasoning": str,
            "backend": str ("groq" | "gemini" | "rejected")
        }
    """
    name_lower = candidate_name.lower().strip()

    # ── Fast-path: always reject clearly false positives ─────────
    if name_lower in _ALWAYS_REJECT:
        logger.info("Entity REJECTED (hardcoded): %s", candidate_name)
        return {
            "is_genuine_entity": False,
            "confidence": 95,
            "reasoning": "Common word/number misclassified by NER model",
            "backend": "rule",
        }

    # ── Short single-word names (potential false positives) ──────
    # Words like "Wolf", "Three" that spaCy often misclassifies.
    # These MUST go through LLM validation.
    # Multi-word names (2+ words) are more likely genuine (e.g. "Deepak Rana")

    # ── Check if any LLM API key is available ───────────────────
    api_key = os.environ.get("GROQ_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        # No LLM available — use heuristic gate
        return _heuristic_validation(candidate_name, entity_type_guess, surrounding_context)

    # ── Call LLM for contextual validation ──────────────────────
    prompt = VALIDATION_PROMPT.replace("{candidate_name}", candidate_name).replace(
        "{entity_type_guess}", entity_type_guess
    ).replace("{surrounding_context}", surrounding_context[:500])

    # Try Groq first (faster, more generous)
    raw = _call_groq_for_validation(prompt)
    backend = "groq"

    # Fallback to Gemini
    if not raw:
        raw = _call_gemini_for_validation(prompt)
        backend = "gemini"

    # Fallback to heuristic if no LLM available
    if not raw:
        return _heuristic_validation(candidate_name, entity_type_guess, surrounding_context)

    # ── Parse response ──────────────────────────────────────────
    result = _parse_json_response(raw)
    if result is None:
        # Parse failure — reject to be safe
        logger.warning("Entity validation parse failure for '%s', raw: %s", candidate_name, raw[:200])
        return {
            "is_genuine_entity": False,
            "confidence": 0,
            "reasoning": f"LLM parse failure — rejected as precaution. Raw: {raw[:100]}",
            "backend": f"{backend}_parse_error",
        }

    # ── Normalize result ────────────────────────────────────────
    is_genuine = result.get("is_genuine_entity", False)
    if isinstance(is_genuine, str):
        is_genuine = is_genuine.lower() in ("true", "yes", "1")
    confidence = max(0, min(100, int(result.get("confidence", 0))))
    reasoning = str(result.get("reasoning", "No reasoning provided"))

    logger.info("Entity %s '%s': genuine=%s confidence=%d — %s [%s]",
                "ACCEPTED" if is_genuine else "REJECTED",
                candidate_name, is_genuine, confidence, reasoning, backend)

    return {
        "is_genuine_entity": is_genuine,
        "confidence": confidence,
        "reasoning": reasoning,
        "backend": backend,
    }


def _heuristic_validation(candidate_name: str, entity_type_guess: str,
                           surrounding_context: str) -> dict:
    """
    Heuristic fallback when no LLM API key is available.
    Uses pattern-based rules to reject obvious false positives.
    """
    name = candidate_name.strip()
    name_lower = name.lower()
    ctx = surrounding_context.lower() if surrounding_context else ""

    # ── Reject pure number words ────────────────────────────────
    number_words = {
        "zero", "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
        "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
        "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    }
    if name_lower in number_words:
        return {
            "is_genuine_entity": False,
            "confidence": 90,
            "reasoning": f"Number word '{name}' misclassified as entity — rejected by heuristic",
            "backend": "heuristic",
        }

    # ── Reject single common English words used descriptively ────
    common_descriptors = {
        "single", "total", "details", "detail", "investigator", "file",
        "field", "type", "number", "page", "report", "summary",
        "section", "chapter", "part", "system", "network", "group",
        "team", "unit", "board", "council", "commission", "agency",
        "authority", "office", "department", "division", "branch",
        "section", "unit", "cell", "team", "cell", "group",
        "radio", "station", "frequency", "signal", "channel",
        "channel", "wave", "broadcast", "transmission", "wireless",
    }
    if name_lower in common_descriptors:
        # Check if it's used as a name in context
        name_as_name = re.search(
            rf'\b(?:known|called|referred|named|alias)\s+(?:as\s+)?{re.escape(name_lower)}\b',
            ctx
        )
        if not name_as_name:
            return {
                "is_genuine_entity": False,
                "confidence": 85,
                "reasoning": f"'{name}' is a common descriptor, not a name in this context",
                "backend": "heuristic",
            }

    # ── Reject very short single words (1-2 chars) ──────────────
    if len(name) <= 2 and entity_type_guess == "PERSON":
        return {
            "is_genuine_entity": False,
            "confidence": 80,
            "reasoning": f"'{name}' too short to be a person name",
            "backend": "heuristic",
        }

    # ── Accept multi-word names (2+ words) — likely genuine ─────
    words = name.split()
    if len(words) >= 2 and entity_type_guess == "PERSON":
        # Multi-word person names are almost always genuine
        return {
            "is_genuine_entity": True,
            "confidence": 85,
            "reasoning": f"Multi-word name '{name}' likely genuine person reference",
            "backend": "heuristic",
        }

    # ── Accept names that appear with title/context markers ──────
    title_markers = [
        r'\b(?:mr|mrs|ms|dr|inspector|si|dsp|ssp|ig|sp|dgp|constable|sub[\s-]?inspector)\b',
        r'\b(?:accused|suspect|witness|victim|informant|arrested|detained)\b',
        r'\b(?:son\s+of|daughter\s+of|wife\s+of|husband\s+of|father\s+of|mother\s+of)\b',
        r'\b(?:known\s+as|called|referred\s+as|alias|aka)\b',
    ]
    for pattern in title_markers:
        if re.search(pattern, ctx):
            return {
                "is_genuine_entity": True,
                "confidence": 75,
                "reasoning": f"'{name}' appears with title/context marker — likely genuine",
                "backend": "heuristic",
            }

    # ── Default: accept with moderate confidence ────────────────
    # If it passed all denylists and entity_type_classifier, give it the benefit
    return {
        "is_genuine_entity": True,
        "confidence": 60,
        "reasoning": f"Passed structural validation — no heuristic reason to reject",
        "backend": "heuristic",
    }
