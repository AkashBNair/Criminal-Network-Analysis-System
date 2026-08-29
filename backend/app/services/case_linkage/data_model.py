"""
Case Linkage & Pattern Recognition — Data Model

Structured schema for CCTNS-style case records.
Designed for India-focused crime analysis; fields chosen to capture
behavioral signature, MO, victimology, and geographic-temporal context.

IMPORTANT: This is a lead-generation tool, NOT an automated accusation
system. All outputs are labeled "candidate leads" — never "matches" or
"identified suspect".
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# ── Enums ──────────────────────────────────────────────────────────

class ApproachMethod(str, enum.Enum):
    CON = "con"
    BLITZ = "blitz"
    SURPRISE = "surprise"
    AMBUSH = "ambush"
    OTHER = "other"


class ControlMethod(str, enum.Enum):
    WEAPON = "weapon"
    RESTRAINTS = "restraints"
    THREAT = "threat"
    NONE = "none"
    OTHER = "other"


class CrimeSceneOrg(str, enum.Enum):
    ORGANIZED = "organized"
    DISORGANIZED = "disorganized"
    MIXED = "mixed"


class VictimRiskLevel(str, enum.Enum):
    LOW = "low"
    HIGH = "high"


class CaseResolution(str, enum.Enum):
    UNSOLVED = "unsolved"
    SOLVED = "solved"
    SUSPECT_NAMED = "suspect_named"


# ── Data Model ─────────────────────────────────────────────────────

@dataclass
class CaseRecord:
    """Single criminal case record in CCTNS-style schema."""

    # Identity
    case_id: str
    case_number: str  # FIR number

    # Temporal
    date_time: datetime

    # Geographic — incident
    state: str
    district: str
    police_station: str
    location_lat: float
    location_lng: float

    # Geographic — disposal (optional, if body/evidence found elsewhere)
    disposal_lat: Optional[float] = None
    disposal_lng: Optional[float] = None

    # Victimology
    victim_age: Optional[int] = None
    victim_gender: Optional[str] = None
    victim_occupation: Optional[str] = None
    victim_risk_level: VictimRiskLevel = VictimRiskLevel.LOW

    # Modus Operandi
    approach_method: ApproachMethod = ApproachMethod.OTHER
    control_method: ControlMethod = ControlMethod.OTHER
    weapon_type: Optional[str] = None

    # Crime scene
    crime_scene_organization: CrimeSceneOrg = CrimeSceneOrg.MIXED

    # Behavioral signature — the most psychologically stable signals
    # across a serial series (more stable than MO, which offenders adapt)
    signature_behaviors: list[str] = field(default_factory=list)
    overkill_score: int = 0  # 0–10, degree of excess violence
    staging_present: bool = False

    # Unstructured
    narrative_text: str = ""

    # Status
    status: CaseResolution = CaseResolution.UNSOLVED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date_time"] = self.date_time.isoformat()
        d["approach_method"] = self.approach_method.value
        d["control_method"] = self.control_method.value
        d["crime_scene_organization"] = self.crime_scene_organization.value
        d["victim_risk_level"] = self.victim_risk_level.value
        d["status"] = self.status.value
        return d


# ── Config Constants ───────────────────────────────────────────────

# Weights for composite linkage score
# Rationale:
#   - Signature behaviors (40%): psychologically most stable across a
#     serial series; offenders adapt MO but retain signature
#   - Narrative similarity (25%): catches nuance in unstructured text
#     not captured by discrete fields
#   - Victimology (20%): consistent victim selection is a core
#     behavioral link signal
#   - MO/Approach (15%): most adaptable by offender, hence lowest weight

WEIGHT_SIGNATURE = 0.40
WEIGHT_NARRATIVE = 0.25
WEIGHT_VICTIMOLOGY = 0.20
WEIGHT_MO = 0.15

# Clustering
LINKAGE_THRESHOLD = 60  # minimum composite score (0-100) to create edge
DBSCAN_EPS = 0.45       # DBSCAN epsilon on normalized feature vectors
DBSCAN_MIN_SAMPLES = 2

# Responsible AI
HUMAN_REVIEW_REQUIRED = True  # CANNOT be disabled in UI

# Sensitive fields explicitly excluded from all scoring
EXCLUDED_FIELDS = ["religion", "caste", "ethnicity", "community"]
