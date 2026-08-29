"""Test Fix 3: LLM-based MO extraction vs keyword matching."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("GROQ_API_KEY", "")

from pathlib import Path
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("GROQ_API_KEY="):
            os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")

from app.services.serial_pattern_detection import (
    assess_mo_indicators, _heuristic_mo, _extract_mo_from_text, _mo_cache
)

# Clear MO cache so we get fresh LLM results
_mo_cache.clear()
print("MO cache cleared\n")

# Test narratives that have genuine AND misleading keywords
test_cases = [
    {
        "name": "Case A - Genuine MO (Bemis)",
        "case_number": "CASE-001",
        "case_id": "test_bemis",
        "text": (
            "Harold Bemis, age 55, was found dead in his study. "
            "The body was positioned neatly in his chair, with a brass key "
            "placed deliberately on the desk beside him. The radio was set "
            "to a frequency that had been dead for over a year. "
            "No signs of forced entry; the door was unlocked. "
            "No struggle was evident. The victim appears to have known "
            "his attacker. A single item was missing from the room."
        ),
        "expect_genuine": True,
    },
    {
        "name": "Case B - Negated keywords (no actual MO)",
        "case_number": "CASE-002",
        "case_id": "test_negated",
        "text": (
            "Investigators found NO signs of forced entry, ruling out "
            "burglary as a motive. There was NO struggle at the scene. "
            "No weapon was recovered. No drugs were found. "
            "The victim was NOT restrained. There was NO evidence of "
            "hawala or laundering. The suspect had no network connections. "
            "This was NOT an ambush. No surveillance was conducted."
        ),
        "expect_genuine": False,
    },
    {
        "name": "Case C - Mixed (some real, some negated)",
        "case_number": "CASE-003",
        "case_id": "test_mixed",
        "text": (
            "The offender gained entry through an unlocked back door. "
            "The victim was restrained with zip ties and threatened with "
            "a knife. No firearms were involved. There was no evidence "
            "of a larger syndicate or network operating. The attack "
            "appeared targeted and pre-meditated, with the offender "
            "having watched the victim for several days."
        ),
        "expect_genuine": True,
    },
]

for tc in test_cases:
    print("=" * 60)
    print(f"TEST: {tc['name']}")
    print(f"Case: {tc['case_number']}")
    print("-" * 60)

    # OLD: keyword-based heuristic
    old_result = _heuristic_mo(tc["text"])
    print("OLD (keyword matching):")
    for dim, keywords in old_result.items():
        print(f"  {dim}: {keywords}")
    if not old_result:
        print("  (empty)")

    # NEW: LLM-based
    new_result = assess_mo_indicators(tc["text"], tc["case_number"])
    print("\nNEW (LLM contextual):")
    for dim in ["approach_method", "control_method", "violence_level",
                "targeting_pattern", "organizational", "financial"]:
        val = new_result.get(dim)
        if val:
            print(f"  {dim}: {val}")
    if new_result.get("confidence"):
        print(f"  confidence: {new_result['confidence']}")
    if new_result.get("reasoning"):
        print(f"  reasoning: {new_result['reasoning']}")

    # Validation
    print()
    if old_result.get("organizational"):
        print(f"  OLD BUG: detected 'organizational' keywords: {old_result['organizational']}")
        print("  (text says NO syndicate, but keyword matching found the word)")
    else:
        print("  OLD: no organizational keywords (correct)")

    if new_result.get("organizational"):
        print(f"  NEW: organizational = {new_result['organizational']}")
        if tc["expect_genuine"] is False or "no" in tc["text"].lower().split("syndicate")[0][-30:]:
            print("  NOTE: Check if LLM correctly rejected negated context")
    else:
        print("  NEW: no organizational (correctly rejected)")

    print()

# Test cache works
print("=" * 60)
print("CACHE TEST")
print("-" * 60)
cached = _mo_cache.get("test_bemis")
print(f"Cache entry for test_bemis: {'HIT' if cached else 'MISS'}")
if cached:
    print(f"  approach_method: {cached.get('approach_method', 'N/A')}")
    print(f"  confidence: {cached.get('confidence', 'N/A')}")

# Second call should hit cache
_mo_result = _extract_mo_from_text(
    "Harold Bemis was found dead...", case_number="CASE-001", case_id="test_bemis"
)
print(f"\nSecond call with same case_id: cache result = {type(_mo_result).__name__}")
print(f"  approach_method: {_mo_result.get('approach_method', 'N/A')}")

# Test _mo_jaccard with LLM output
from app.services.serial_pattern_detection import _mo_jaccard

print("\n" + "=" * 60)
print("MO JACCARD TEST")
print("-" * 60)
mo_a = assess_mo_indicators(test_cases[0]["text"], "CASE-001")
_mo_cache.set("test_bemis", mo_a)  # ensure cached
mo_b = assess_mo_indicators(test_cases[2]["text"], "CASE-003")
score = _mo_jaccard({"test_bemis": mo_a, "test_mixed": mo_b}, "test_bemis", "test_mixed")
print(f"MO similarity (Case A vs C): {score:.3f}")
print(f"(Both have genuine MO -> should be > 0)")

mo_neg = assess_mo_indicators(test_cases[1]["text"], "CASE-002")
score_neg = _mo_jaccard({"test_bemis": mo_a, "test_negated": mo_neg}, "test_bemis", "test_negated")
print(f"MO similarity (Case A vs negated B): {score_neg:.3f}")
print(f"(B has negated keywords only -> should be LOW)")

print("\nAll Fix 3 tests complete.")
