"""
Test LLM Entity Validator against real case files.
Prints each spaCy NER candidate's llm_verdict before and after gating.
"""
import sys, os, glob, logging

# Set up paths and load env BEFORE any imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

# Now import extraction
from app.services.entity_extraction import extract_entities_from_text

# Serial case files
SERIAL_DIR = r"C:\Users\naira\OneDrive\Desktop\serial"

# Test words that SHOULD be rejected
REJECT_WORDS = {"Wolf", "Three", "Single", "Details", "Investigator", "Radio"}

# Test words that SHOULD be accepted (real names)
ACCEPT_WORDS = {"Deepak Rana", "Vikram Solanki", "Ravi Shankar"}


def main():
    api_key = os.environ.get("GROQ_API_KEY", "")
    backend = "Groq LLM" if api_key else "Heuristic (no API key)"

    print("=" * 70)
    print("LLM ENTITY VALIDATOR TEST")
    print("=" * 70)
    print(f"Backend: {backend}")
    print(f"GROQ_API_KEY: {'SET (' + api_key[:8] + '...)' if api_key else 'NOT SET'}")
    print()

    case_files = sorted(glob.glob(os.path.join(SERIAL_DIR, "*.md")))
    if not case_files:
        print(f"No .md files found in {SERIAL_DIR}")
        return

    all_entities = []

    for filepath in case_files:
        case_name = os.path.basename(filepath)
        print("-" * 70)
        print(f"FILE: {case_name}")
        print("-" * 70)

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        entities = extract_entities_from_text(text, document_type="case_file")
        all_entities.extend(entities)

        persons = [e for e in entities if e.entity_type.value == "person"]
        locations = [e for e in entities if e.entity_type.value == "location"]
        orgs = [e for e in entities if e.entity_type.value == "organization"]

        print(f"  Total: {len(entities)} | Persons: {len(persons)} | Locs: {len(locations)} | Orgs: {len(orgs)}")

        if persons:
            print(f"\n  PERSONS:")
            for e in persons:
                conf = e.attributes.get("llm_confidence", "?")
                backend_e = e.attributes.get("llm_backend", "?")
                reasoning = e.attributes.get("extraction_reasoning", "")
                print(f"    + {e.name:<30} conf={conf} [{backend_e}]")
                if reasoning:
                    print(f"      -> {reasoning}")

        if locations:
            print(f"\n  LOCATIONS:")
            for e in locations:
                conf = e.attributes.get("llm_confidence", "?")
                backend_e = e.attributes.get("llm_backend", "?")
                reasoning = e.attributes.get("extraction_reasoning", "")
                print(f"    + {e.name:<30} conf={conf} [{backend_e}]")
                if reasoning:
                    print(f"      -> {reasoning}")

        if orgs:
            print(f"\n  ORGS:")
            for e in orgs:
                conf = e.attributes.get("llm_confidence", "?")
                backend_e = e.attributes.get("llm_backend", "?")
                reasoning = e.attributes.get("extraction_reasoning", "")
                print(f"    + {e.name:<30} conf={conf} [{backend_e}]")
                if reasoning:
                    print(f"      -> {reasoning}")

    # Validation
    print()
    print("=" * 70)
    print("VALIDATION CHECKS")
    print("=" * 70)

    extracted_names = {e.name for e in all_entities}

    print("\n1. FALSE POSITIVE CHECK (should be REJECTED):")
    for word in sorted(REJECT_WORDS):
        found = word in extracted_names
        status = "STILL PRESENT (BUG!)" if found else "Correctly rejected"
        print(f"   {word}: {status}")

    print("\n2. REAL NAME CHECK (should be ACCEPTED):")
    for name in sorted(ACCEPT_WORDS):
        found = name in extracted_names
        status = "Correctly accepted" if found else "MISSING"
        print(f"   {name}: {status}")

    rejected_words_found = {w for w in REJECT_WORDS if w in extracted_names}
    accepted_words_missing = {n for n in ACCEPT_WORDS if n not in extracted_names}

    print()
    print("=" * 70)
    if not rejected_words_found and not accepted_words_missing:
        print("ALL CHECKS PASSED")
    else:
        if rejected_words_found:
            print(f"FALSE POSITIVES STILL PRESENT: {rejected_words_found}")
        if accepted_words_missing:
            print(f"REAL NAMES MISSING: {accepted_words_missing}")
    print(f"Backend: {backend}")
    print(f"Total entities: {len(all_entities)}")


if __name__ == "__main__":
    main()
