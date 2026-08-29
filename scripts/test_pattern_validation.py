"""
Validation Checklist Test Script for Pattern Detection.
Tests all scenarios specified in the system prompt.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.database import SessionLocal
from app.services.pattern_detection import (
    detect_communication_bursts,
    detect_financial_patterns,
    detect_co_location_patterns,
    detect_cross_case_patterns,
    generate_investigative_brief,
    verify_graph_connectivity,
)
from app.services.threat_scoring import compute_threat_scores
from app.models.models import Entity, Relationship, Alert, EntityType, RelationshipType


def test_communication_burst_with_event():
    """Test 1: Burst correlated with incident (should be HIGH priority)."""
    print("\n" + "="*60)
    print("TEST 1: Communication Burst with Event Correlation")
    print("="*60)
    
    db = SessionLocal()
    alerts = detect_communication_bursts(db)
    
    print(f"\n  Total communication burst alerts: {len(alerts)}")
    for alert in alerts:
        print(f"\n  Alert: {alert.title}")
        print(f"    Severity: {alert.severity}")
        print(f"    Confidence: {alert.supporting_evidence.get('confidence', 'N/A')}")
        print(f"    Explanation: {alert.supporting_evidence.get('explanation', 'N/A')}")
        
        # Check if event correlation is present
        event_corr = alert.supporting_evidence.get('event_correlation', {})
        if event_corr.get('correlated'):
            print(f"    ✓ EVENT CORRELATED: {event_corr.get('event_type')}")
        else:
            print(f"    - No event correlation (expected for some alerts)")
    
    db.close()


def test_financial_patterns():
    """Test 2: Financial transfer with mismatched purpose."""
    print("\n" + "="*60)
    print("TEST 2: Financial Pattern Detection")
    print("="*60)
    
    db = SessionLocal()
    alerts = detect_financial_patterns(db)
    
    print(f"\n  Total financial pattern alerts: {len(alerts)}")
    for alert in alerts:
        print(f"\n  Alert: {alert.title}")
        print(f"    Severity: {alert.severity}")
        print(f"    Type: {alert.alert_type.value}")
        print(f"    Explanation: {alert.supporting_evidence.get('explanation', 'N/A')}")
        
        # Check for structuring or circular flows
        if 'structuring' in alert.title.lower():
            print(f"    ✓ STRUCTURING DETECTED")
        elif 'circular' in alert.title.lower():
            print(f"    ✓ CIRCULAR FLOW DETECTED")
    
    db.close()


def test_cross_case_entities():
    """Test 3: Cross-case entity sharing (highest-value pattern)."""
    print("\n" + "="*60)
    print("TEST 3: Cross-Case Pattern Detection")
    print("="*60)
    
    db = SessionLocal()
    alerts = detect_cross_case_patterns(db)
    
    print(f"\n  Total cross-case alerts: {len(alerts)}")
    
    # Group by type
    by_type = {}
    for alert in alerts:
        t = alert.alert_type.value
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(alert)
    
    for alert_type, type_alerts in by_type.items():
        print(f"\n  {alert_type}: {len(type_alerts)} alerts")
        for alert in type_alerts[:3]:  # Show first 3
            print(f"    - {alert.title}")
            print(f"      Severity: {alert.severity}")
            print(f"      Confidence: {alert.supporting_evidence.get('confidence', 'N/A')}")
    
    db.close()


def test_investigative_brief():
    """Test 4: Investigative brief generation."""
    print("\n" + "="*60)
    print("TEST 4: Investigative Brief Generation")
    print("="*60)
    
    db = SessionLocal()
    
    # Get threat scores to find top entities
    scores = compute_threat_scores(db)
    
    if scores:
        top_entity = scores[0]
        print(f"\n  Generating brief for: {top_entity['name']}")
        print(f"    Threat Score: {top_entity['threat_score']}%")
        print(f"    Threat Level: {top_entity['threat_level']}")
        
        brief = generate_investigative_brief(db, top_entity['entity_id'], top_entity)
        
        print(f"\n  BRIEF NARRATIVE:")
        print(f"    {brief.get('narrative', 'N/A')}")
        
        print(f"\n  EVIDENCE SUMMARY:")
        confirmed = brief.get('evidence_summary', {}).get('confirmed', [])
        inferred = brief.get('evidence_summary', {}).get('inferred', [])
        
        print(f"    Confirmed relationships: {len(confirmed)}")
        for r in confirmed[:3]:
            print(f"      - {r['type']}: {r['connected_to']} ({r['connected_type']})")
        
        print(f"    Inferred relationships: {len(inferred)}")
        for r in inferred[:3]:
            print(f"      - {r['type']}: {r['connected_to']} (confidence: {r['confidence']:.2f})")
            print(f"        WARNING: {r.get('warning', 'N/A')}")
        
        unresolved = brief.get('unresolved_threads', [])
        if unresolved:
            print(f"\n  UNRESOLVED THREADS:")
            for thread in unresolved:
                print(f"    - {thread}")
    
    db.close()


def test_graph_connectivity():
    """Test 5: Graph connectivity verification."""
    print("\n" + "="*60)
    print("TEST 5: Graph Connectivity Verification")
    print("="*60)
    
    db = SessionLocal()
    result = verify_graph_connectivity(db)
    
    print(f"\n  Connected: {result['connected']}")
    print(f"  Components: {result['components']}")
    print(f"  Largest component: {result['largest_component']} nodes")
    print(f"  Total nodes: {result['total_nodes']}")
    
    duplicates = result.get('duplicates_across_components', {})
    if duplicates:
        print(f"\n  DUPLICATES ACROSS COMPONENTS: {len(duplicates)}")
        for name, info in list(duplicates.items())[:3]:
            print(f"    - {name}: found in {len(info['component_ids'])} components")
    else:
        print(f"\n  ✓ No duplicate entities across components")
    
    print(f"\n  Message: {result['message']}")
    
    db.close()


def test_confidence_levels():
    """Test 6: Confidence levels and evidence classification."""
    print("\n" + "="*60)
    print("TEST 6: Confidence Levels & Evidence Classification")
    print("="*60)
    
    db = SessionLocal()
    
    # Check alerts for confidence levels
    alerts = db.query(Alert).all()
    
    confirmed = []
    statistical = []
    unexplained = []
    
    for alert in alerts:
        evidence = alert.supporting_evidence or {}
        confidence = evidence.get('confidence', 'unknown')
        
        if confidence == 'confirmed':
            confirmed.append(alert)
        elif confidence == 'statistically_unusual':
            statistical.append(alert)
        elif confidence == 'unexplained':
            unexplained.append(alert)
    
    print(f"\n  Total alerts: {len(alerts)}")
    print(f"  Confirmed patterns: {len(confirmed)}")
    print(f"  Statistically unusual: {len(statistical)}")
    print(f"  Unexplained: {len(unexplained)}")
    
    # Check for explanations
    alerts_with_explanations = sum(
        1 for a in alerts 
        if (a.supporting_evidence or {}).get('explanation')
    )
    print(f"\n  Alerts with explanations: {alerts_with_explanations}/{len(alerts)}")
    
    # Check for source records
    alerts_with_sources = sum(
        1 for a in alerts 
        if (a.supporting_evidence or {}).get('source_records')
    )
    print(f"  Alerts with source records: {alerts_with_sources}/{len(alerts)}")
    
    db.close()


if __name__ == "__main__":
    print("Running Pattern Detection Validation Checklist...")
    print("="*60)
    
    try:
        test_communication_burst_with_event()
        test_financial_patterns()
        test_cross_case_entities()
        test_investigative_brief()
        test_graph_connectivity()
        test_confidence_levels()
        
        print("\n" + "="*60)
        print("ALL VALIDATION TESTS COMPLETED")
        print("="*60)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
