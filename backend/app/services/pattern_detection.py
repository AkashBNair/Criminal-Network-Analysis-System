"""
Pattern Detection Module.
Re-exports from v2 for backward compatibility.
"""
from app.services.pattern_detection_v2 import (
    detect_communication_bursts,
    detect_financial_patterns,
    detect_cross_case_patterns,
    detect_co_location_patterns,
    detect_burner_numbers,
    run_all_detections,
    ensure_detection_rules,
    extract_social_media_entities,
    generate_investigative_brief,
    verify_graph_connectivity,
)
