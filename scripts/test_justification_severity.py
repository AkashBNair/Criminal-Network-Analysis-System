"""
Test LLM Justification Severity Assessor.

Tests the key bug: keyword matching scores "cleared of murder" identically
to "confessed to murder" — the LLM should correctly distinguish them.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app.services.llm_justification_severity import (
    assess_justification_severity, _cache
)

# ── Test Cases ───────────────────────────────────────────────────
# Format: (entity_name, justification_text, expected_level, description)
TEST_CASES = [
    # CASES THAT SHOULD SCORE HIGH (person genuinely implicated)
    (
        "Vikram Solanki",
        "Suspect Vikram Solanki confessed to orchestrating the narcotics "
        "distribution network, providing detailed accounts of supply routes "
        "and financial transactions.",
        "strong",
        "Confessed involvement — should score HIGH",
    ),
    (
        "Ravi Shankar",
        "Witness testimony confirms Ravi Shankar was present at the scene "
        "and actively participated in the assault on the victim.",
        "moderate",
        "Witness confirms active participation — should score MODERATE-HIGH",
    ),
    (
        "Deepak Rana",
        "Financial records show Deepak Rana received proceeds from the "
        "extortion operation, with Rs 4.5 lakh transferred to his account "
        "over a 3-month period.",
        "moderate",
        "Financial evidence of involvement — should score MODERATE",
    ),

    # CASES THAT SHOULD SCORE LOW (person cleared/negated)
    (
        "Amit Sharma",
        "Suspect Amit Sharma was CLEARED of all murder allegations after "
        "providing a verified alibi confirmed by three independent witnesses.",
        "none",
        "Cleared of murder — should score LOW despite keyword 'murder'",
    ),
    (
        "Priya Verma",
        "The witness falsely accused Priya Verma of drug trafficking, but "
        "subsequent investigation revealed she had no involvement and was "
        "misidentified.",
        "none",
        "Falsely accused — should score LOW despite keyword 'trafficking'",
    ),
    (
        "Rajesh Kumar",
        "Although Rajesh Kumar was present at the location during the "
        "robbery, evidence shows he was merely a bystander with no "
        "involvement in the crime.",
        "none",
        "Merely present — should score LOW despite keyword 'robbery'",
    ),

    # EDGE CASES
    (
        "Unknown Subject",
        "The investigation is ongoing and no specific individuals have "
        "been identified as suspects at this time.",
        "none",
        "No suspects identified — should score NONE",
    ),
    (
        "Suresh Patel",
        "Suresh Patel was questioned as a material witness regarding the "
        "theft incident but was not charged.",
        "weak",
        "Witness only, not charged — should score LOW",
    ),
]


def main():
    api_key = os.environ.get("GROQ_API_KEY", "")
    backend = "Groq LLM" if api_key else "Heuristic (no API key)"
    print("=" * 70)
    print("LLM JUSTIFICATION SEVERITY TEST")
    print("=" * 70)
    print(f"Backend: {backend}")
    print(f"GROQ_API_KEY: {'SET' if api_key else 'NOT SET'}")
    print(f"Cache entries before test: {_cache.size}")
    print()

    results = []
    for entity_name, justification, expected_level, description in TEST_CASES:
        print("-" * 70)
        print(f"TEST: {description}")
        print(f"Person: {entity_name}")
        print(f"Text: {justification[:120]}...")
        print()

        verdict = assess_justification_severity(justification, entity_name)

        severity = verdict["severity_score"]
        level = verdict["implication_level"]
        reasoning = verdict["reasoning"]
        backend_used = verdict["backend"]

        level_correct = (level == expected_level)
        status = "PASS" if level_correct else "FAIL"

        print(f"  Expected level:  {expected_level}")
        print(f"  Actual level:    {level}")
        print(f"  Severity score:  {severity:.2f}")
        print(f"  Crime type:      {verdict.get('crime_type_if_any', 'N/A')}")
        print(f"  Reasoning:       {reasoning}")
        print(f"  Backend:         {backend_used}")
        print(f"  Status:          [{status}]")

        results.append({
            "entity": entity_name,
            "expected": expected_level,
            "actual": level,
            "severity": severity,
            "status": status,
            "backend": backend_used,
        })
        print()

    # ── Summary ─────────────────────────────────────────────────
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print()

    # ── Key comparison: old vs new for the critical bug ─────────
    print("KEY COMPARISON: Old keyword matching vs New LLM assessment")
    print("-" * 70)
    print("  OLD behavior (keyword matching):")
    print("    'Cleared of murder allegations' -> severity=1.0 (murder keyword)")
    print("    'Confessed to murder'           -> severity=1.0 (murder keyword)")
    print("    BUG: Both scored identically!")
    print()
    print("  NEW behavior (LLM contextual):")

    for i, r in enumerate(results):
        just_text = TEST_CASES[i][1].lower()
        if "cleared" in just_text:
            print(f"    'Cleared of murder'  -> severity={r['severity']:.2f} ({r['actual']})")
        if "confessed" in just_text:
            print(f"    'Confessed to murder' -> severity={r['severity']:.2f} ({r['actual']})")

    print()
    if all(r["status"] == "PASS" for r in results):
        print("ALL TESTS PASSED - LLM correctly distinguishes context")
    else:
        failed = [r for r in results if r["status"] == "FAIL"]
        for f in failed:
            print(f"FAIL: {f['entity']} — expected {f['expected']}, got {f['actual']}")

    print(f"\nCache entries after test: {_cache.size}")


if __name__ == "__main__":
    main()
