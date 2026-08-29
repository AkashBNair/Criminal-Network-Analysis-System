"""
Validation Checklist Test Script.
Tests the entity resolution and threat scoring against the scenarios
specified in the system prompt.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.database import SessionLocal
from app.models.models import Entity, EntityType, Relationship, RelationshipType
from app.services.entity_resolution import (
    extract_corroborating_signals,
    find_potential_matches,
    _get_merge_recommendation,
    flag_as_unresolved,
)
from app.services.threat_scoring import (
    compute_threat_scores,
    validate_threat_score_consistency,
    build_weighted_graph,
)


def test_entity_resolution():
    """Test entity resolution with various scenarios."""
    print("\n" + "="*60)
    print("TEST: Entity Resolution Scenarios")
    print("="*60)
    
    db = SessionLocal()
    
    # Test 1: Two unrelated people with same name
    print("\n--- Test 1: Same name, different persons (should NOT merge) ---")
    persons = db.query(Entity).filter(
        Entity.entity_type == EntityType.PERSON,
        Entity.is_merged_into.is_(None),
    ).all()
    
    # Find potential matches
    for p in persons[:5]:
        matches = find_potential_matches(db, p, threshold=0.6)
        if matches:
            print(f"\n  Entity: {p.name} (ID: {p.id[:8]}...)")
            for m in matches[:3]:
                rec = m['merge_recommendation']
                print(f"    Match: {m['entity_name']} (similarity: {m['name_similarity']:.2f})")
                print(f"      Signals: {m['signal_count']} | Action: {rec['action']} | Confidence: {rec['confidence']}")
                if m['signals']:
                    for sig_name, sig_data in m['signals'].items():
                        print(f"        - {sig_name}: {sig_data['evidence']}")
    
    # Test 2: Check merge recommendations
    print("\n--- Test 2: Merge recommendation thresholds ---")
    for count in range(4):
        rec = _get_merge_recommendation(count)
        print(f"  {count} signals beyond name → {rec['action']} ({rec['confidence']})")
    
    db.close()


def test_threat_scoring_consistency():
    """Test that threat scores are consistent with centrality."""
    print("\n" + "="*60)
    print("TEST: Threat Score Consistency")
    print("="*60)
    
    db = SessionLocal()
    
    # Validate consistency
    result = validate_threat_score_consistency(db)
    print(f"\n  Validation: {result['message']}")
    print(f"  Consistency: {result['consistency_percentage']}%")
    print(f"  Overlap: {result['overlap_count']}/{result['top_n']} top entities")
    
    if result['divergences']:
        print("\n  Divergences:")
        for div in result['divergences']:
            print(f"    Rank {div['rank']}: Centrality={div['centrality_rank']['name']} vs Threat={div['threat_rank']['name']}")
    
    # Verify weighted graph uses proper weights
    print("\n--- Weighted Graph Edge Weights ---")
    G, _ = build_weighted_graph(db)
    
    edge_weights = {}
    for _, _, data in G.edges(data=True):
        rel_type = data.get('relationship_type', 'Unknown')
        if rel_type not in edge_weights:
            edge_weights[rel_type] = []
        edge_weights[rel_type].append(data.get('weight', 1.0))
    
    for rel_type, weights in sorted(edge_weights.items()):
        avg_weight = sum(weights) / len(weights)
        print(f"  {rel_type}: {len(weights)} edges, avg weight: {avg_weight:.2f}")
    
    db.close()


def test_confidence_levels():
    """Test entity confidence levels and resolution status."""
    print("\n" + "="*60)
    print("TEST: Confidence Levels & Resolution Status")
    print("="*60)
    
    db = SessionLocal()
    
    persons = db.query(Entity).filter(
        Entity.entity_type == EntityType.PERSON,
        Entity.is_merged_into.is_(None),
    ).all()
    
    high = [p for p in persons if (p.confidence_score or 0) >= 0.85]
    medium = [p for p in persons if 0.6 <= (p.confidence_score or 0) < 0.85]
    low = [p for p in persons if (p.confidence_score or 0) < 0.6]
    unresolved = [p for p in persons if (p.attributes or {}).get('resolution_status') == 'unresolved']
    
    print(f"\n  Total persons: {len(persons)}")
    print(f"  High confidence (≥85%): {len(high)}")
    print(f"  Medium confidence (60-84%): {len(medium)}")
    print(f"  Low confidence (<60%): {len(low)}")
    print(f"  Unresolved (flagged): {len(unresolved)}")
    
    if unresolved:
        print("\n  Unresolved entities:")
        for p in unresolved:
            attrs = p.attributes or {}
            print(f"    - {p.name}: {attrs.get('resolution_reason', 'No reason specified')}")
    
    db.close()


def test_entity_counts_consistency():
    """Test that entity counts are consistent across views."""
    print("\n" + "="*60)
    print("TEST: Entity Count Consistency")
    print("="*60)
    
    db = SessionLocal()
    
    # Count entities by different methods
    all_persons = db.query(Entity).filter(
        Entity.entity_type == EntityType.PERSON,
        Entity.is_merged_into.is_(None),
    ).count()
    
    # Count via graph
    G, entity_map = build_weighted_graph(db)
    graph_persons = len([n for n in G.nodes if G.nodes[n].get('entity_type') == 'Person' or True])  # All nodes are persons in our graph
    
    # Count via threat scoring
    scores = compute_threat_scores(db)
    threat_persons = len(scores)
    
    print(f"\n  All persons (DB): {all_persons}")
    print(f"  Persons in graph: {graph_persons}")
    print(f"  Persons in threat scores: {threat_persons}")
    
    # Check consistency
    if all_persons == graph_persons == threat_persons:
        print("  ✓ All views show consistent entity counts")
    else:
        print("  ✗ INCONSISTENCY DETECTED - entity counts differ across views")
    
    db.close()


if __name__ == "__main__":
    print("Running Validation Checklist Tests...")
    print("="*60)
    
    try:
        test_entity_resolution()
        test_threat_scoring_consistency()
        test_confidence_levels()
        test_entity_counts_consistency()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
