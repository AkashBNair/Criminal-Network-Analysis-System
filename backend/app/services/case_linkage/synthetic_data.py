"""
Case Linkage & Pattern Recognition — Synthetic Dataset Generator

Generates ~180 fake case records with realistic Indian state/district names.
Includes 4 deliberate "true" serial clusters (15-20 cases total) with
consistent signature behavior but varying surface MO — so the algorithm
has real patterns to find and an investigator can validate that it works.

ALL DATA IS SYNTHETIC / DEMO DATA — NOT REAL CASES.
"""
from __future__ import annotations

import json
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

from .data_model import (
    CaseRecord, ApproachMethod, ControlMethod, CrimeSceneOrg,
    VictimRiskLevel, CaseResolution,
)

# ── Indian geography for realistic coordinates ─────────────────────

STATES_DISTRICTS_PS = {
    "Maharashtra": [
        ("Mumbai", "Andheri PS", 19.1136, 72.8697),
        ("Mumbai", "Bandra PS", 19.0596, 72.8295),
        ("Pune", "Shivajinagar PS", 18.5308, 73.8470),
        ("Pune", "Kothrud PS", 18.5074, 73.8077),
        ("Nagpur", "Sitabuldi PS", 21.1458, 79.0882),
        ("Nagpur", "Dharampeth PS", 21.1360, 79.0613),
        ("Thane", "Thane PS", 19.1965, 72.9631),
        ("Nashik", "Nashik Road PS", 19.9975, 73.7898),
        ("Aurangabad", "City PS", 19.8762, 75.3433),
        ("Solapur", "Hotgi Road PS", 17.6599, 75.9064),
    ],
    "Rajasthan": [
        ("Jaipur", "Johri Bazaar PS", 26.9228, 75.8267),
        ("Jaipur", "Malviya Nagar PS", 26.8850, 75.8102),
        ("Jodhpur", "Sardar Market PS", 26.2909, 73.0252),
        ("Udaipur", "Hathipole PS", 24.5854, 73.7125),
        ("Kota", "Dadabari PS", 25.1825, 75.8541),
        ("Ajmer", "Dargah Bazaar PS", 26.4499, 74.6399),
    ],
    "Delhi": [
        ("Central Delhi", "Koti Circle PS", 28.6392, 77.2380),
        ("South Delhi", "Hauz Khas PS", 28.5494, 77.2001),
        ("North Delhi", "Rohini Sector PS", 28.7495, 77.0654),
        ("East Delhi", "Preet Vihar PS", 28.6428, 77.2976),
        ("West Delhi", "Janakpuri PS", 28.6216, 77.0816),
    ],
    "Uttar Pradesh": [
        ("Lucknow", "Hazratganj PS", 26.8553, 80.9462),
        ("Lucknow", "Gomti Nagar PS", 26.8525, 80.9916),
        ("Agra", "Sadar Bazaar PS", 27.1767, 78.0081),
        ("Kanpur", "Kakadeo PS", 26.4604, 80.3487),
        ("Varanasi", "Lanka PS", 25.3100, 83.0105),
        ("Noida", "Sector 20 PS", 28.5809, 77.3192),
    ],
    "Madhya Pradesh": [
        ("Bhopal", "MP Nagar PS", 23.2347, 77.4010),
        ("Indore", "Vijay Nagar PS", 22.7177, 75.8537),
        ("Gwalior", "Lashkar PS", 26.2124, 78.1772),
        ("Jabalpur", "Vijay Nagar PS", 23.1680, 79.9478),
    ],
    "Karnataka": [
        ("Bengaluru", "Koramangala PS", 12.9352, 77.6245),
        ("Bengaluru", "Whitefield PS", 12.9698, 77.7500),
        ("Mysuru", "Vani Vilas Mohalla PS", 12.3118, 76.6527),
        ("Mangaluru", "Bunder PS", 12.8694, 74.8433),
    ],
    "Tamil Nadu": [
        ("Chennai", "T. Nagar PS", 13.0407, 80.2337),
        ("Chennai", "Adyar PS", 13.0067, 80.2564),
        ("Coimbatore", "Gandhipuram PS", 11.0059, 76.9718),
        ("Madurai", "Anna Nagar PS", 9.9252, 78.1198),
    ],
    "Gujarat": [
        ("Ahmedabad", "Navrangpura PS", 23.0366, 72.5294),
        ("Ahmedabad", "Satellite PS", 23.0469, 72.5089),
        ("Surat", "Athwa Lines PS", 21.1702, 72.8311),
        ("Vadodara", "Fatehgunj PS", 22.3279, 73.1901),
    ],
    "West Bengal": [
        ("Kolkata", "Loudon Street PS", 22.5553, 88.3508),
        ("Kolkata", "Shyambazar PS", 22.6536, 88.3983),
        ("Howrah", "Howrah PS", 22.5726, 88.3639),
    ],
    "Kerala": [
        ("Thiruvananthapuram", "Palayam PS", 8.5241, 76.9366),
        ("Kochi", "Ernakulam South PS", 9.9680, 76.2875),
    ],
    "Bihar": [
        ("Patna", "Gandhi Maidan PS", 25.6110, 85.1440),
        ("Patna", "Boring Road PS", 25.6010, 85.1010),
    ],
}

# Indian states for cross-state cases
ALL_STATES = list(STATES_DISTRICTS_PS.keys())

# Victim profiles
OCCUPATIONS = [
    "student", "shopkeeper", "daily_wager", "housewife", "driver",
    "factory_worker", "farmer", "bank_clerk", "teacher", "nurse",
    "vendor", "auto_driver", "security_guard", "cook", "sweeper",
]
GENDERS = ["male", "female"]

WEAPONS = [
    "knife", "sharp_weapon", "blunt_object", "poison", "rope",
    "firearm", "acid", None, None, None,  # many cases have no weapon
]

NARRATIVE_TEMPLATES = {
    "serial_strangler": [
        "Victim was found {disposal_detail}. Neighbors reported hearing "
        "a heated argument before midnight. The victim, a {gender} aged "
        "{age}, appeared to have been {approach_detail}. "
        "Ligature marks were visible on the neck. "
        "The scene showed signs of {scene_detail}.",
        "Body recovered from {disposal_detail}. Initial investigation "
        "suggests the {gender} victim, aged {age}, was {approach_detail}. "
        "No signs of forced entry. {scene_detail}.",
    ],
    "serial_blitz": [
        "The {gender} victim, aged {age}, was {approach_detail} near "
        "{location_detail}. Bystanders reported seeing a man in a "
        "dark jacket fleeing the scene. {scene_detail}.",
        "Attack occurred at {location_detail}. The {age}-year-old "
        "{gender} victim was {approach_detail}. {scene_detail}. "
        "CCTV footage from nearby shops is being reviewed.",
    ],
    "serial_financial": [
        "The victim, a {gender} {occupation} aged {age}, was contacted "
        "by someone posing as a bank official. Money was transferred "
        "before the victim realized the fraud. {scene_detail}.",
        "Report of financial fraud. The {gender} victim, aged {age}, "
        "{occupation}, was {approach_detail}. Total loss estimated "
        "at ₹{amount}. {scene_detail}.",
    ],
    "serial_ritual": [
        "The {gender} victim aged {age} was found at {disposal_detail}. "
        "Distinctive ritualistic markings were found on the body. "
        "{scene_detail}. Investigation is ongoing.",
        "Bodies bore unusual markings consistent with ritualistic elements. "
        "The {gender} victim, aged {age}, was {approach_detail}. "
        "{scene_detail}.",
    ],
}


def _jitter(base: float, spread: float) -> float:
    """Add random jitter to a coordinate."""
    return base + random.uniform(-spread, spread)


def _random_date(start_year: int = 2023, end_year: int = 2024) -> datetime:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days),
                             hours=random.randint(0, 23),
                             minutes=random.randint(0, 59))


def _generate_narrative(cluster_type: str, record: dict) -> str:
    """Generate a realistic FIR-style narrative text."""
    templates = NARRATIVE_TEMPLATES.get(cluster_type, NARRATIVE_TEMPLATES["serial_strangler"])
    template = random.choice(templates)

    disposal_detail = "an abandoned area nearby"
    if record.get("disposal_lat"):
        disposal_detail = "a remote location approximately 5 km from the incident site"

    approach_map = {
        "con": "lured under false pretenses",
        "blitz": "suddenly attacked without warning",
        "surprise": "caught off guard from behind",
        "ambush": "ambushed at a quiet location",
    }
    approach_detail = approach_map.get(record["approach_method"], "attacked")

    scene_map = {
        "organized": "Minimal evidence left behind suggesting careful planning",
        "disorganized": "Significant disorder at the scene with scattered evidence",
        "mixed": "Some evidence of planning but also signs of hasty departure",
    }
    scene_detail = scene_map.get(record["crime_scene_organization"])

    location_detail = f"{record['district']}, {record['state']}"
    amount = random.randint(50000, 500000)

    return template.format(
        disposal_detail=disposal_detail,
        gender=record["victim_gender"],
        age=record["victim_age"],
        approach_detail=approach_detail,
        scene_detail=scene_detail,
        location_detail=location_detail,
        occupation=record.get("victim_occupation", "service worker"),
        amount=f"{amount:,}",
    )


def _generate_serial_cluster(
    cluster_id: int,
    cluster_type: str,
    n_cases: int,
    base_state: str,
    base_lat: float,
    base_lng: float,
) -> list[dict]:
    """
    Generate a cluster of n_cases that form a serial pattern.

    Each cluster has CONSISTENT signature behaviors but VARYING surface MO,
    simulating how a real serial offender adapts their approach while
    retaining psychological signature.
    """
    # Signature behaviors are FIXED within a cluster (psychologically stable)
    cluster_signatures = {
        1: ["posing", "staging", "overkill"],           # strangler cluster
        2: ["overkill", "specific_mutilation"],           # blitz attack cluster
        3: ["trophy_taking", "staging"],                  # financial fraud cluster
        4: ["ritualistic_element", "posing"],             # ritual cluster
    }
    signatures = cluster_signatures.get(cluster_id, ["staging"])

    cases = []
    state_info = STATES_DISTRICTS_PS[base_state]

    for i in range(n_cases):
        # Vary MO within cluster (offender adapts approach)
        approach = random.choice(list(ApproachMethod))
        control = random.choice(list(ControlMethod))
        weapon = random.choice(WEAPONS)
        scene_org = random.choice(list(CrimeSceneOrg))

        # Vary location slightly (offender moves within a region)
        # But stays in the same state to simulate intra-state serial pattern
        district_info = random.choice(state_info)
        lat = _jitter(base_lat, 0.15)
        lng = _jitter(base_lng, 0.15)

        # Occasionally cross into adjacent state (cross-jurisdictional)
        disposal_lat, disposal_lng = None, None
        if random.random() < 0.2:
            # Body/evidence found in different district
            other_district = random.choice(state_info)
            disposal_lat = other_district[2] + random.uniform(-0.05, 0.05)
            disposal_lng = other_district[3] + random.uniform(-0.05, 0.05)

        age = random.randint(18, 55)
        gender = random.choice(GENDERS)
        occupation = random.choice(OCCUPATIONS)

        # Overkill score varies but stays elevated within cluster
        overkill = random.randint(5, 10) if cluster_id != 3 else random.randint(0, 2)

        dt = _random_date(2023, 2024)

        record = {
            "case_id": f"SYN-{base_state[:2].upper()}-{cluster_id}-{i+1:03d}",
            "case_number": f"FIR/{dt.year}/{base_state[:2].upper()}/{random.randint(1000,9999)}",
            "date_time": dt.isoformat(),
            "state": base_state,
            "district": district_info[0],
            "police_station": district_info[1],
            "location_lat": lat,
            "location_lng": lng,
            "disposal_lat": disposal_lat,
            "disposal_lng": disposal_lng,
            "victim_age": age,
            "victim_gender": gender,
            "victim_occupation": occupation,
            "victim_risk_level": random.choice(["low", "high"]),
            "approach_method": approach.value,
            "control_method": control.value,
            "weapon_type": weapon,
            "crime_scene_organization": scene_org.value,
            "signature_behaviors": signatures,
            "overkill_score": overkill,
            "staging_present": "staging" in signatures,
            "narrative_text": "",  # filled below
            "status": random.choice(["unsolved", "unsolved", "unsolved", "solved"]),
        }
        record["narrative_text"] = _generate_narrative(cluster_type, record)
        cases.append(record)

    return cases


def _generate_random_cases(n: int) -> list[dict]:
    """Generate n random unlinked cases to serve as background noise."""
    cases = []
    all_states = list(STATES_DISTRICTS_PS.keys())

    for i in range(n):
        state = random.choice(all_states)
        district_info = random.choice(STATES_DISTRICTS_PS[state])
        dt = _random_date(2023, 2024)

        age = random.randint(18, 65)
        gender = random.choice(GENDERS)
        occupation = random.choice(OCCUPATIONS)
        approach = random.choice(list(ApproachMethod))
        control = random.choice(list(ControlMethod))
        weapon = random.choice(WEAPONS)
        scene_org = random.choice(list(CrimeSceneOrg))
        sig_count = random.randint(0, 1)

        # Random signatures (no consistent pattern across random cases)
        possible_sigs = [
            "posing", "trophy_taking", "overkill", "staging",
            "specific_mutilation", "ritualistic_element",
        ]
        signatures = random.sample(possible_sigs, sig_count)

        lat = district_info[2] + random.uniform(-0.05, 0.05)
        lng = district_info[3] + random.uniform(-0.05, 0.05)

        disposal_lat, disposal_lng = None, None
        if random.random() < 0.1:
            disposal_lat = lat + random.uniform(-0.1, 0.1)
            disposal_lng = lng + random.uniform(-0.1, 0.1)

        record = {
            "case_id": f"SYN-{state[:2].upper()}-R-{i+1:03d}",
            "case_number": f"FIR/{dt.year}/{state[:2].upper()}/{random.randint(1000,9999)}",
            "date_time": dt.isoformat(),
            "state": state,
            "district": district_info[0],
            "police_station": district_info[1],
            "location_lat": lat,
            "location_lng": lng,
            "disposal_lat": disposal_lat,
            "disposal_lng": disposal_lng,
            "victim_age": age,
            "victim_gender": gender,
            "victim_occupation": occupation,
            "victim_risk_level": random.choice(["low", "high"]),
            "approach_method": approach.value,
            "control_method": control.value,
            "weapon_type": weapon,
            "crime_scene_organization": scene_org.value,
            "signature_behaviors": signatures,
            "overkill_score": random.randint(0, 10),
            "staging_present": "staging" in signatures,
            "narrative_text": "",
            "status": random.choice(["unsolved", "solved", "suspect_named"]),
        }

        # Generic narrative for random cases
        record["narrative_text"] = (
            f"Incident reported at {district_info[1]}, {district_info[0]}, {state}. "
            f"The {gender} victim, aged {age}, {occupation}, was "
            f"{'attacked' if approach.value != 'con' else 'approached'} "
            f"{'with a weapon' if weapon else 'without visible weapon'}. "
            f"The crime scene appeared {scene_org.value}. "
            f"{'Investigation is ongoing.' if record['status'] == 'unsolved' else 'Case is under investigation.'}"
        )
        cases.append(record)

    return cases


def generate_dataset(output_dir: str | Path | None = None) -> dict:
    """
    Generate the full synthetic dataset:
    - 4 serial clusters (4-5 cases each, 18 total)
    - ~160 random unlinked cases
    - Total: ~178 cases

    Returns the dataset as a dict. If output_dir is provided, also
    writes cases.json to that directory.

    WARNING: ALL DATA IS SYNTHETIC / DEMO DATA — NOT REAL CASES.
    """
    random.seed(42)  # Reproducible for demos

    all_cases = []

    # ── Cluster 1: Serial strangler, Maharashtra ──
    cluster1 = _generate_serial_cluster(
        cluster_id=1,
        cluster_type="serial_strangler",
        n_cases=5,
        base_state="Maharashtra",
        base_lat=19.0760,
        base_lng=72.8777,
    )
    all_cases.extend(cluster1)

    # ── Cluster 2: Serial blitz attacker, Rajasthan ──
    cluster2 = _generate_serial_cluster(
        cluster_id=2,
        cluster_type="serial_blitz",
        n_cases=5,
        base_state="Rajasthan",
        base_lat=26.9124,
        base_lng=75.7873,
    )
    all_cases.extend(cluster2)

    # ── Cluster 3: Serial financial fraud, Delhi + UP ──
    cluster3 = _generate_serial_cluster(
        cluster_id=3,
        cluster_type="serial_financial",
        n_cases=5,
        base_state="Delhi",
        base_lat=28.6139,
        base_lng=77.2090,
    )
    # Add a cross-state member to cluster 3
    cross_state_case = _generate_serial_cluster(
        cluster_id=3,
        cluster_type="serial_financial",
        n_cases=1,
        base_state="Uttar Pradesh",
        base_lat=26.8467,
        base_lng=80.9462,
    )
    cross_state_case[0]["case_id"] = "SYN-UP-3-006"
    cross_state_case[0]["narrative_text"] = (
        "The victim, a female bank clerk aged 29, was contacted by someone "
        "posing as a senior bank official. She was asked to verify her "
        "account details via a link. ₹2,85,000 was transferred before "
        "she realized the fraud. Pattern matches similar cases in Delhi. "
        "Crime scene appeared organized — no physical evidence left behind."
    )
    all_cases.extend(cross_state_case)

    # ── Cluster 4: Serial ritual, MP + Chhattisgarh border ──
    cluster4 = _generate_serial_cluster(
        cluster_id=4,
        cluster_type="serial_ritual",
        n_cases=4,
        base_state="Madhya Pradesh",
        base_lat=23.2599,
        base_lng=77.4126,
    )
    all_cases.extend(cluster4)

    # ── Background noise: 155 random unlinked cases ──
    random_cases = _generate_random_cases(155)
    all_cases.extend(random_cases)

    dataset = {
        "metadata": {
            "description": "SYNTHETIC / DEMO DATA — NOT REAL CASES",
            "total_cases": len(all_cases),
            "serial_clusters": {
                "cluster_1": {
                    "type": "serial_strangler",
                    "state": "Maharashtra",
                    "cases": [c["case_id"] for c in cluster1],
                    "signature": ["posing", "staging", "overkill"],
                },
                "cluster_2": {
                    "type": "serial_blitz",
                    "state": "Rajasthan",
                    "cases": [c["case_id"] for c in cluster2],
                    "signature": ["overkill", "specific_mutilation"],
                },
                "cluster_3": {
                    "type": "serial_financial",
                    "states": ["Delhi", "Uttar Pradesh"],
                    "cases": [c["case_id"] for c in cluster3 + cross_state_case],
                    "signature": ["trophy_taking", "staging"],
                },
                "cluster_4": {
                    "type": "serial_ritual",
                    "state": "Madhya Pradesh",
                    "cases": [c["case_id"] for c in cluster4],
                    "signature": ["ritualistic_element", "posing"],
                },
            },
            "note": "Deliberate true clusters included for algorithm validation",
        },
        "cases": all_cases,
    }

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "cases.json", "w") as f:
            json.dump(dataset, f, indent=2)

    return dataset


if __name__ == "__main__":
    out = Path(__file__).parent.parent.parent.parent / "data" / "case_linkage"
    dataset = generate_dataset(out)
    print(f"Generated {dataset['metadata']['total_cases']} cases")
    print(f"  Serial clusters: {len(dataset['metadata']['serial_clusters'])}")
    print(f"  Output: {out / 'cases.json'}")
