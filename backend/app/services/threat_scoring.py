"""
Threat Scoring Service.

Computes suspect importance/threat percentage based on:
  1. Network centrality (40%) — degree, betweenness, eigenvector (weighted)
  2. Role severity (30%) — types of criminal activity using differentiated weights
  3. Cross-case presence (20%) — appearing in multiple cases multiplies threat
  4. Activity level (10%) — total weighted connections

CONSUMES: resolved_graph.py (single shared graph builder)
No independent graph construction — §0 of the Master Prompt:
  "Every stage must consume the resolved output of the previous stage."
"""
import math
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Entity, Relationship, EntityType, RelationshipType, Case
from app.services.resolved_graph import (
    build_resolved_graph, compute_centrality, ResolvedGraph,
    CRIME_SEVERITY_KEYWORDS, RELATIONSHIP_WEIGHTS
)
from app.services.llm_justification_severity import assess_justification_severity


def compute_threat_scores(db: Session, case_ids: list[str] = None) -> list[dict]:
    """
    Compute threat scores for all Person entities.
    ONE ROW PER UNIQUE PERSON (after entity resolution).
    
    Uses the canonical resolved graph — never builds its own.
    
    Per §6 of the Master Prompt:
      - Cross-case bridging is one of the highest-weighted factors
      - Show score breakdown, not just bare percentage
      - Consistency check: top by threat score ≈ top by centrality
    """
    # Build the ONE canonical resolved graph
    resolved = build_resolved_graph(db, case_ids)
    G = resolved.graph
    
    if len(G.nodes) == 0:
        return []
    
    # ── 1. Centrality (from canonical graph) ──
    centrality = compute_centrality(G)
    
    # ── 2. Role Severity ──
    person_roles = {}
    for node_id in G.nodes:
        person_roles[node_id] = {
            'total_severity': 0.0,
            'roles': [],
            'crime_keywords': set(),
            'relationship_types': set(),
        }
    
    for source_id, target_id, edata in G.edges(data=True):
        for pid in [source_id, target_id]:
            if pid not in person_roles:
                continue
            
            # Use the type weights already computed by the resolved graph
            type_weights = edata.get('type_weights', {})
            avg_type_weight = (
                sum(type_weights.values()) / len(type_weights) 
                if type_weights else 0.5
            )
            
            # Get crime severity from justifications via LLM contextual analysis
            # Replaces keyword matching — judges actual implication, not word presence
            crime_severity = 0.0
            best_severity_backend = None
            justification_assessments = []
            for just in edata.get('justifications', []):
                if not just or len(just.strip()) < 10:
                    continue
                verdict = assess_justification_severity(
                    justification_text=just,
                    entity_name=entity.name if hasattr(entity, 'name') else pid,
                )
                sev = verdict.get('severity_score', 0.0)
                if sev > crime_severity:
                    crime_severity = sev
                    best_severity_backend = verdict.get('backend', 'unknown')
                justification_assessments.append({
                    'text': just[:200],
                    'implication_level': verdict.get('implication_level', 'none'),
                    'severity_score': round(sev, 2),
                    'reasoning': verdict.get('reasoning', ''),
                    'crime_type': verdict.get('crime_type_if_any'),
                })
            
            effective_severity = (
                avg_type_weight * (0.7 + 0.3 * crime_severity) 
                if crime_severity > 0 else avg_type_weight
            )
            
            person_roles[pid]['total_severity'] += effective_severity
            person_roles[pid]['roles'].append({
                'types': list(edata.get('relationship_types', [])),
                'type_weight': round(avg_type_weight, 2),
                'crime_severity': round(crime_severity, 2) if crime_severity > 0 else None,
                'effective_severity': round(effective_severity, 2),
                'edge_weight': round(edata.get('weight', 1.0), 2),
                'justifications': edata.get('justifications', [])[:2],
                'justification_assessments': justification_assessments,
                'severity_backend': best_severity_backend,
            })
            person_roles[pid]['relationship_types'].update(edata.get('relationship_types', []))
            if crime_severity > 0:
                person_roles[pid]['crime_keywords'].add(f'llm_scored:{crime_severity:.2f}')
    
    # Normalize role severity to 0-100
    if person_roles:
        max_role = max(r['total_severity'] for r in person_roles.values()) or 1
    else:
        max_role = 1
    role_scores = {
        pid: (data['total_severity'] / max_role) * 100 
        for pid, data in person_roles.items()
    }
    
    # ── 3. Cross-case Presence (§6: highest-weighted factor) ──
    person_cases = {}
    for node_id in G.nodes:
        # Combine direct case IDs with edge case IDs
        case_set = set(G.nodes[node_id].get('case_ids', []))
        for _, _, edata in G.edges(node_id, data=True):
            case_set.update(edata.get('case_ids', []))
        person_cases[node_id] = case_set
    
    total_cases = len(set(
        r.case_id for r in db.query(Relationship).all() 
        if not case_ids or r.case_id in case_ids
    ))
    
    def cross_case_score(pid: str) -> float:
        cases = person_cases.get(pid, set())
        if len(cases) <= 1:
            return 0.0
        # Logarithmic scaling: appearing in 3 cases is significant, 
        # but 4 vs 5 matters less
        return min(100, (math.log(len(cases)) / math.log(max(total_cases, 2))) * 100)
    
    # ── 4. Activity Level ──
    activity_scores = {}
    for node_id in G.nodes:
        degree = G.degree(node_id)
        total_weight = sum(
            G.edges[node_id, n].get('weight', 1.0) 
            for n in G.neighbors(node_id)
        )
        record_count = G.nodes[node_id].get('record_count', 1)
        activity_scores[node_id] = degree * 3 + total_weight * 2 + record_count
    
    max_activity = max(activity_scores.values()) if activity_scores else 1
    activity_norm = {k: (v / max_activity) * 100 for k, v in activity_scores.items()}
    
    # ── 5. Combine Scores (§6) ──
    WEIGHTS = {
        'centrality': 0.40,
        'role_severity': 0.30,
        'cross_case': 0.20,
        'activity': 0.10,
    }
    
    results = []
    seen_names = set()  # ASSERTION: one row per unique person
    
    for node_id in G.nodes:
        canonical_info = resolved.name_to_canonical.get(node_id)
        if not canonical_info:
            continue
        
        entity = canonical_info['entity']
        
        # ASSERTION: No duplicates (§3)
        if entity.name in seen_names:
            print(f"WARNING: Duplicate name in threat output: {entity.name}")
            continue
        seen_names.add(entity.name)
        
        cent = centrality.get(node_id, {})
        centrality_component = (
            0.4 * cent.get('degree_norm', 0) +
            0.4 * cent.get('betweenness_norm', 0) +
            0.2 * cent.get('eigenvector_norm', 0)
        )
        
        threat_pct = (
            WEIGHTS['centrality'] * centrality_component +
            WEIGHTS['role_severity'] * role_scores.get(node_id, 0) +
            WEIGHTS['cross_case'] * cross_case_score(node_id) +
            WEIGHTS['activity'] * activity_norm.get(node_id, 0)
        )
        
        threat_pct = max(0, min(100, threat_pct))
        
        if threat_pct >= 80:
            threat_level = "CRITICAL"
        elif threat_pct >= 60:
            threat_level = "HIGH"
        elif threat_pct >= 40:
            threat_level = "MEDIUM"
        elif threat_pct >= 20:
            threat_level = "LOW"
        else:
            threat_level = "MINIMAL"
        
        role_data = person_roles.get(node_id, {'roles': []})
        cases_involved = list(person_cases.get(node_id, set()))
        
        # Get case numbers
        case_numbers = []
        for cid in cases_involved:
            case_obj = db.query(Case).filter(Case.id == cid).first()
            if case_obj:
                case_numbers.append(case_obj.case_number)
        
        # Check if this entity bridges communities
        is_bridge = False
        for _, _, edata in G.edges(node_id, data=True):
            if edata.get('cross_case', False):
                is_bridge = True
                break
        
        results.append({
            'entity_id': canonical_info['canonical_id'],
            'name': entity.name,
            'threat_score': round(threat_pct, 1),
            'threat_level': threat_level,
            'breakdown': {
                'centrality': round(centrality_component * WEIGHTS['centrality'], 1),
                'role_severity': round(role_scores.get(node_id, 0) * WEIGHTS['role_severity'], 1),
                'cross_case': round(cross_case_score(node_id) * WEIGHTS['cross_case'], 1),
                'activity': round(activity_norm.get(node_id, 0) * WEIGHTS['activity'], 1),
            },
            'breakdown_raw': {
                'centrality_score': round(cent.get('combined_score', 0), 4),
                'role_severity_raw': round(role_scores.get(node_id, 0), 1),
                'cross_case_count': len(cases_involved),
                'activity_raw': round(activity_norm.get(node_id, 0), 1),
            },
            'connections': G.degree(node_id),
            'weighted_degree': round(sum(
                G.edges[node_id, n].get('weight', 1.0) 
                for n in G.neighbors(node_id)
            ), 2),
            'cases_count': len(cases_involved),
            'case_numbers': case_numbers,
            'roles': role_data['roles'][:5],
            'crime_keywords': list(role_data.get('crime_keywords', set())),
            'relationship_types': list(role_data.get('relationship_types', set())),
            'attributes': canonical_info['merged_attributes'],
            'aliases': canonical_info['merged_aliases'],
            'case_id': entity.case_id,
            'resolution_status': canonical_info.get('resolution_status', 'resolved'),
            'is_unconfirmed': canonical_info.get('is_unconfirmed', False),
            'confidence_score': entity.confidence_score or 1.0,
            'is_ai_extracted': entity.is_ai_extracted,
            'record_count': canonical_info['record_count'],
            'is_cross_case_bridge': is_bridge,
        })
    
    # FINAL ASSERTION (§3): count(unique names) == count(rows)
    if len(results) != len(seen_names):
        print(f"ASSERTION FAILED: {len(results)} rows but {len(seen_names)} unique names")
    
    results.sort(key=lambda x: x['threat_score'], reverse=True)
    return results


def validate_threat_score_consistency(db: Session, case_ids: list[str] = None) -> dict:
    """
    Validate that threat scores are consistent with centrality rankings (§6).
    "The top-ranked entity by threat score and the top-ranked entity by graph 
    centrality should not sharply diverge."
    """
    resolved = build_resolved_graph(db, case_ids)
    G = resolved.graph
    
    if len(G.nodes) == 0:
        return {'valid': True, 'message': 'No data to validate'}
    
    centrality = compute_centrality(G)
    threat_results = compute_threat_scores(db, case_ids)
    
    # Rank by centrality
    centrality_ranked = sorted(
        centrality.items(), 
        key=lambda x: x[1]['combined_score'], 
        reverse=True
    )
    
    # Rank by threat score
    threat_ranked = [(r['entity_id'], r['threat_score'], r['name']) for r in threat_results]
    
    # Map centrality names to entity IDs
    name_to_eid = {}
    for name in G.nodes:
        info = resolved.name_to_canonical.get(name)
        if info:
            name_to_eid[name] = info['canonical_id']
    
    top_n = min(5, len(centrality_ranked))
    centrality_top_ids = set()
    for i in range(top_n):
        if i < len(centrality_ranked):
            name = centrality_ranked[i][0]
            eid = name_to_eid.get(name, name)
            centrality_top_ids.add(eid)
    
    threat_top_ids = set(r[0] for r in threat_ranked[:top_n])
    
    overlap = len(centrality_top_ids & threat_top_ids)
    consistency_pct = (overlap / top_n) * 100 if top_n > 0 else 100
    
    divergences = []
    for i in range(top_n):
        if i < len(centrality_ranked) and i < len(threat_ranked):
            c_name = centrality_ranked[i][0]
            c_eid = name_to_eid.get(c_name, c_name)
            t_eid, t_score, t_name = threat_ranked[i]
            if c_eid != t_eid:
                divergences.append({
                    'rank': i + 1,
                    'centrality_rank': {'entity_id': c_eid, 'name': c_name},
                    'threat_rank': {'entity_id': t_eid, 'name': t_name, 'score': t_score},
                })
    
    return {
        'valid': consistency_pct >= 60,
        'consistency_percentage': round(consistency_pct, 1),
        'top_n': top_n,
        'overlap_count': overlap,
        'divergences': divergences,
        'message': (
            f"Threat scores {'are' if consistency_pct >= 60 else 'are NOT'} consistent "
            f"with centrality rankings ({consistency_pct:.0f}% overlap in top {top_n})"
        ),
    }


def get_person_threat_detail(db: Session, entity_id: str) -> dict | None:
    """Get detailed threat score breakdown for a specific person."""
    all_scores = compute_threat_scores(db)
    for s in all_scores:
        if s['entity_id'] == entity_id:
            return s
    return None
