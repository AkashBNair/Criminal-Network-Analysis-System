"""
Resolved Graph Service — SINGLE SOURCE OF TRUTH for graph construction.

Every downstream module (threat scoring, community detection, pattern detection,
visualization, path discovery) MUST consume the output of this module.
No module should build its own graph independently.

Pipeline: Entity Resolution → This module → All consumers

Per §3 of the Master System Prompt:
  "One entity, one record, one ID — enforced at the data layer."
  "If two modules disagree about basic facts, that is a pipeline wiring bug."
"""
import networkx as nx
import math
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.models import (
    Entity, Relationship, EntityType, RelationshipType,
    Case
)
from app.services.llm_justification_severity import assess_justification_severity

logger = logging.getLogger(__name__)


# ─── Relationship Type Weights (§4) ────────────────────────────────
# Per the master prompt's weighted graph specification:
#   High: Directs/orders, Financier, Co-accused, Communication time-correlated
#   Medium: Family/known associate
#   Low-Medium: Transactional/administrative
#   Exclude: Witness-only/victim/complainant

RELATIONSHIP_WEIGHTS = {
    RelationshipType.CO_ACCUSED: 1.0,        # High — legal & operational linkage
    RelationshipType.FINANCIAL: 0.95,         # High — structural importance
    RelationshipType.COMMUNICATION: 0.85,     # High — strongest circumstantial
    RelationshipType.OWNERSHIP: 0.9,          # High — operational control signal
    RelationshipType.LOCATION_PRESENCE: 0.7,  # Medium — co-location evidence
    RelationshipType.ASSOCIATE: 0.5,          # Medium — real but non-specific
    RelationshipType.EMPLOYMENT: 0.6,         # Low-Medium — executes, doesn't direct
    RelationshipType.FAMILY: 0.4,             # Medium — personal, not operational
}

# Crime severity keywords (boosts relationship weight)
CRIME_SEVERITY_KEYWORDS = {
    "murder": 1.0, "contract killing": 1.0, "homicide": 1.0,
    "extortion": 0.85, "blackmail": 0.85, "narcotics": 0.80,
    "ndps": 0.80, "drug": 0.80, "smuggling": 0.75,
    "counterfeit": 0.70, "cybercrime": 0.65, "fraud": 0.60,
    "hawala": 0.85, "money laundering": 0.90, "arms": 0.95,
    "weapons": 0.95, "terrorism": 1.0, "robbery": 0.80,
    "dacoity": 0.80, "kidnapping": 0.90,
}

# Witness/victim/complainant roles — EXCLUDE from centrality per §4
EXCLUDE_ROLES = {"witness", "victim", "complainant"}


class ResolvedGraph:
    """
    Canonical graph with resolved entities, typed/weighted edges, 
    and all metadata needed by downstream consumers.
    
    This is the ONLY graph object any service should consume.
    """
    def __init__(self, graph: nx.Graph, canonical_entities: dict,
                 id_to_name: dict, name_to_canonical: dict):
        self.graph = graph
        self.canonical_entities = canonical_entities  # name -> merged entity info
        self.id_to_name = id_to_name  # raw entity ID -> canonical name
        self.name_to_canonical = name_to_canonical  # canonical name -> canonical info
        self.total_nodes = graph.number_of_nodes()
        self.total_edges = graph.number_of_edges()
        all_case_ids = set()
        for info in canonical_entities.values():
            all_case_ids.update(info.get('case_ids', set()))
        self.total_cases = len(all_case_ids)

    def get_node(self, name: str) -> dict:
        """Get canonical node data by name."""
        return self.graph.nodes.get(name, {})

    def get_neighbors(self, name: str) -> list:
        """Get all neighbors of a node."""
        return list(self.graph.neighbors(name))


def build_resolved_graph(
    db: Session, 
    case_ids: list[str] = None,
    include_witnesses: bool = False,
) -> ResolvedGraph:
    """
    Build the ONE canonical resolved graph.
    
    Steps:
    1. Entity Resolution: merge entities by name with corroborating evidence
    2. Relationship Mapping: redirect all relationships to canonical IDs
    3. Weighted Edge Construction: apply differentiated weights per §4
    4. Witness/Victim Exclusion: optionally exclude from centrality per §4
    
    Args:
        db: Database session
        case_ids: If provided, restrict to these cases (for case-scoped access)
        include_witnesses: If False (default), exclude witness/victim/complainant edges
    
    Returns:
        ResolvedGraph with one node per unique person, weighted typed edges
    """
    logger.info("[RESOLVED_GRAPH] Building canonical resolved graph")
    
    # ── Step 1: Entity Resolution ──
    # Group all Person entities by normalized name
    entity_query = db.query(Entity).filter(
        Entity.entity_type == EntityType.PERSON,
        Entity.is_merged_into.is_(None),
    )
    if case_ids:
        entity_query = entity_query.filter(Entity.case_id.in_(case_ids))
    
    all_persons = entity_query.all()
    logger.info(f"[RESOLVED_GRAPH] Found {len(all_persons)} person entity records")
    
    # Group by normalized name (§3: one entity, one record, one ID)
    name_groups = defaultdict(list)
    for person in all_persons:
        normalized = person.name.lower().strip()
        name_groups[normalized].append(person)
    
    # Build canonical entities: one per unique person
    canonical_entities = {}
    id_to_name = {}  # raw DB entity ID -> canonical name
    name_to_canonical = {}
    
    for normalized_name, group in name_groups.items():
        # Use first record as canonical (or best-confidence)
        canonical_entity = max(group, key=lambda e: e.confidence_score or 0)
        
        # Merge all attributes from all case-records
        merged_attributes = {}
        merged_aliases = set()
        all_case_ids = set()
        all_source_docs = set()
        
        for entity in group:
            attrs = entity.attributes or {}
            for k, v in attrs.items():
                if k not in merged_attributes:
                    merged_attributes[k] = v
                elif isinstance(merged_attributes[k], list) and isinstance(v, list):
                    merged_attributes[k] = list(set(merged_attributes[k] + v))
            for alias in (entity.aliases or []):
                merged_aliases.add(alias)
            all_case_ids.add(entity.case_id)
            if entity.source_document_id:
                all_source_docs.add(entity.source_document_id)
        
        # Check for unresolved/unconfirmed status per §3
        resolution_status = merged_attributes.get('resolution_status', 'resolved')
        is_unconfirmed = resolution_status == 'unresolved' or (
            canonical_entity.confidence_score and canonical_entity.confidence_score < 0.6
        )
        
        canonical_name = canonical_entity.name  # Use the actual name, not normalized
        canonical_entities[canonical_name] = {
            'canonical_id': canonical_entity.id,
            'all_ids': [e.id for e in group],
            'case_ids': all_case_ids,
            'entity': canonical_entity,
            'merged_attributes': merged_attributes,
            'merged_aliases': list(merged_aliases),
            'record_count': len(group),
            'source_documents': list(all_source_docs),
            'is_unconfirmed': is_unconfirmed,
            'resolution_status': resolution_status,
        }
        
        # Map all raw IDs to this canonical name
        for entity in group:
            id_to_name[entity.id] = canonical_name
        name_to_canonical[canonical_name] = canonical_entities[canonical_name]
    
    logger.info(f"[RESOLVED_GRAPH] Resolved to {len(canonical_entities)} unique persons")
    
    # ── Step 2: Build Weighted Graph ──
    G = nx.Graph()
    
    for canonical_name, info in canonical_entities.items():
        entity = info['entity']
        G.add_node(
            canonical_name,
            canonical_id=info['canonical_id'],
            all_ids=info['all_ids'],
            case_ids=list(info['case_ids']),
            name=entity.name,
            attributes=info['merged_attributes'],
            aliases=info['merged_aliases'],
            record_count=info['record_count'],
            confidence=entity.confidence_score,
            is_unconfirmed=info['is_unconfirmed'],
            resolution_status=info['resolution_status'],
            source_documents=info['source_documents'],
            entity_type='Person',
        )
    
    # ── Step 3: Map Relationships to Canonical Edges ──
    rel_query = db.query(Relationship)
    if case_ids:
        rel_query = rel_query.filter(Relationship.case_id.in_(case_ids))
    all_relationships = rel_query.all()
    
    logger.info(f"[RESOLVED_GRAPH] Processing {len(all_relationships)} relationships")
    
    # Aggregate relationships between canonical entities
    edge_data = defaultdict(lambda: {
        'weight': 0.0,
        'type_weights': defaultdict(float),
        'type_counts': defaultdict(int),
        'justifications': [],
        'case_ids': set(),
        'relationship_ids': [],
        'relationship_types': set(),
        'first_observed': None,
        'last_observed': None,
        'is_ai_generated': False,
        'evidence_sources': [],  # Specific records behind this edge
    })
    
    skipped_witness = 0
    skipped_self_loop = 0
    skipped_unmapped = 0
    
    for rel in all_relationships:
        # Map to canonical names
        src_name = id_to_name.get(rel.source_entity_id)
        tgt_name = id_to_name.get(rel.target_entity_id)
        
        if not src_name or not tgt_name:
            skipped_unmapped += 1
            continue
        if src_name == tgt_name:
            skipped_self_loop += 1
            continue
        
        # Exclude witness/victim/complainant per §4
        if not include_witnesses:
            justification = (rel.justification or "").lower()
            if any(skip in justification for skip in EXCLUDE_ROLES):
                skipped_witness += 1
                continue
        
        # Normalize edge key (undirected)
        edge_key = tuple(sorted([src_name, tgt_name]))
        
        # Get base type weight
        type_weight = RELATIONSHIP_WEIGHTS.get(rel.relationship_type, 0.3)
        
        # Apply crime severity boost from justification text via LLM
        # Replaces keyword matching - judges actual implication, not word presence
        justification = (rel.justification or "").strip()
        crime_boost = 0.0
        severity_backend = None
        if justification and len(justification) > 10:
            # Get entity names for context
            src_ent = db.query(Entity).filter(Entity.id == rel.source_entity_id).first()
            tgt_ent = db.query(Entity).filter(Entity.id == rel.target_entity_id).first()
            entity_label = ", ".join(filter(None, [
                src_ent.name if src_ent else None,
                tgt_ent.name if tgt_ent else None,
            ])) or "unknown"
            
            verdict = assess_justification_severity(
                justification_text=justification,
                entity_name=entity_label,
            )
            sev = verdict.get("severity_score", 0.0)
            # Map 0-1 severity to 0-0.2 crime_boost (matching old range)
            crime_boost = sev * 0.2
            severity_backend = verdict.get("backend", "unknown")
        
        raw_weight = rel.weight or 1.0
        final_weight = type_weight * (1 + crime_boost) * raw_weight
        
        data = edge_data[edge_key]
        data['weight'] += final_weight
        data['type_weights'][rel.relationship_type.value] += final_weight
        data['type_counts'][rel.relationship_type.value] += 1
        data['relationship_types'].add(rel.relationship_type.value)
        data['case_ids'].add(rel.case_id)
        data['relationship_ids'].append(rel.id)
        data['is_ai_generated'] = data['is_ai_generated'] or rel.is_ai_generated
        
        # Evidence trail per §7: cite specific records
        evidence_entry = {
            'relationship_id': rel.id,
            'type': rel.relationship_type.value,
            'weight': rel.weight,
            'justification': rel.justification or '',
            'case_id': rel.case_id,
            'is_ai_generated': rel.is_ai_generated,
            'confidence': rel.confidence_score,
            'severity_backend': severity_backend,
        }
        data['evidence_sources'].append(evidence_entry)
        
        if justification:
            data['justifications'].append(justification)
        
        # Track temporal bounds
        if rel.first_observed:
            if data['first_observed'] is None or rel.first_observed < data['first_observed']:
                data['first_observed'] = rel.first_observed
        if rel.last_observed:
            if data['last_observed'] is None or rel.last_observed > data['last_observed']:
                data['last_observed'] = rel.last_observed
    
    # Add edges to graph
    for edge_key, data in edge_data.items():
        # Determine primary relationship type (highest-weight)
        primary_type = max(data['type_weights'].items(), key=lambda x: x[1])[0] if data['type_weights'] else 'Associate'
        
        G.add_edge(
            edge_key[0],
            edge_key[1],
            weight=data['weight'],
            relationship_types=list(data['relationship_types']),
            primary_relationship_type=primary_type,
            type_weights=dict(data['type_weights']),
            type_counts=dict(data['type_counts']),
            relationship_count=len(data['relationship_ids']),
            case_ids=list(data['case_ids']),
            justifications=data['justifications'][:5],
            evidence_sources=data['evidence_sources'][:10],
            first_observed=data['first_observed'],
            last_observed=data['last_observed'],
            is_ai_generated=data['is_ai_generated'],
            cross_case=len(data['case_ids']) > 1,
        )
    
    logger.info(
        f"[RESOLVED_GRAPH] Built graph: {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges "
        f"(skipped: {skipped_witness} witness, {skipped_self_loop} self-loop, "
        f"{skipped_unmapped} unmapped)"
    )
    
    return ResolvedGraph(
        graph=G,
        canonical_entities=canonical_entities,
        id_to_name=id_to_name,
        name_to_canonical=name_to_canonical,
    )


def compute_centrality(G: nx.Graph) -> dict:
    """
    Compute weighted centrality on the resolved graph.
    Returns dict: node_name -> {degree, betweenness, eigenvector, combined}
    """
    if len(G.nodes) == 0:
        return {}
    
    degree_cent = nx.degree_centrality(G)
    betweenness_cent = nx.betweenness_centrality(G, weight='weight')
    try:
        eigenvector_cent = nx.eigenvector_centrality(G, max_iter=1000, weight='weight')
    except nx.PowerIterationFailedConvergence:
        eigenvector_cent = {node: 0.0 for node in G.nodes}
    
    def normalize(vals: dict) -> dict:
        if not vals:
            return {}
        max_v = max(vals.values()) if vals else 1
        min_v = min(vals.values()) if vals else 0
        rng = max_v - min_v if max_v != min_v else 1
        return {k: ((v - min_v) / rng) * 100 for k, v in vals.items()}
    
    degree_norm = normalize(degree_cent)
    betweenness_norm = normalize(betweenness_cent)
    eigenvector_norm = normalize(eigenvector_cent)
    
    results = {}
    for node_id in G.nodes:
        combined = (
            0.4 * degree_cent.get(node_id, 0) +
            0.4 * betweenness_cent.get(node_id, 0) +
            0.2 * eigenvector_cent.get(node_id, 0)
        )
        results[node_id] = {
            'degree_centrality': round(degree_cent.get(node_id, 0), 4),
            'betweenness_centrality': round(betweenness_cent.get(node_id, 0), 4),
            'eigenvector_centrality': round(eigenvector_cent.get(node_id, 0), 4),
            'combined_score': round(combined, 4),
            'degree_norm': degree_norm.get(node_id, 0),
            'betweenness_norm': betweenness_norm.get(node_id, 0),
            'eigenvector_norm': eigenvector_norm.get(node_id, 0),
        }
    
    return results


def detect_communities_weighted(G: nx.Graph) -> list[dict]:
    """
    Community detection using Louvain (modularity-based) clustering per §5.
    
    Returns list of communities with:
    - community_id
    - members with membership strength
    - bridge entities connecting to other communities
    - auto-label based on dominant case/offense
    - red_herring flags for single-edge incidental connections
    """
    if len(G.nodes) == 0:
        return []
    
    try:
        # Louvain / greedy modularity clustering on weighted graph
        communities = nx.community.louvain_communities(G, weight='weight', resolution=1.0)
    except Exception:
        try:
            communities = nx.community.greedy_modularity_communities(G, weight='weight')
        except Exception:
            communities = [frozenset(c) for c in nx.connected_components(G)]
    
    # Build community membership map
    node_community = {}
    for i, community in enumerate(communities):
        for node in community:
            node_community[node] = i
    
    # Identify bridge entities (§5: "connecting two communities structurally")
    bridge_entities = set()
    for u, v in G.edges():
        cu = node_community.get(u)
        cv = node_community.get(v)
        if cu is not None and cv is not None and cu != cv:
            bridge_entities.add(u)
            bridge_entities.add(v)
    
    # Detect cross-case bridges (highest-value per §6)
    cross_case_bridges = set()
    for node in G.nodes:
        if node in bridge_entities:
            node_data = G.nodes[node]
            # Check if this node's edges span multiple cases
            all_cases = set(node_data.get('case_ids', []))
            for neighbor in G.neighbors(node):
                all_cases.update(G.edges[node, neighbor].get('case_ids', []))
            if len(all_cases) > 1:
                cross_case_bridges.add(node)
    
    # Build community results
    results = []
    for i, community in enumerate(communities):
        members = []
        internal_edges = G.subgraph(community).number_of_edges()
        
        for node in community:
            node_data = G.nodes[node]
            degree = G.degree(node)
            
            # Red herring detection (§5): single-edge incidental connections
            is_red_herring = (
                degree == 1 and 
                node not in bridge_entities and
                len(node_data.get('case_ids', [])) <= 1
            )
            
            # Membership strength: ratio of internal to total edges
            internal_to_node = sum(
                1 for n in G.neighbors(node) if n in community
            )
            membership_strength = internal_to_node / max(degree, 1)
            
            members.append({
                'name': node,
                'canonical_id': node_data.get('canonical_id', ''),
                'connections': degree,
                'is_bridge': node in bridge_entities,
                'is_cross_case_bridge': node in cross_case_bridges,
                'is_red_herring': is_red_herring,
                'membership_strength': round(membership_strength, 2),
                'case_ids': node_data.get('case_ids', []),
                'attributes': node_data.get('attributes', {}),
            })
        
        members.sort(key=lambda x: (-x['is_bridge'], -x['connections']))
        
        # Auto-label cluster by dominant case or offense type (§5)
        all_case_ids = set()
        for node in community:
            all_case_ids.update(G.nodes[node].get('case_ids', []))
        
        # Auto-label from edge evidence (already assessed by LLM in build phase)
        all_crime_keywords = set()
        for node in community:
            for _, _, edata in G.edges(node, data=True):
                for ev in edata.get('evidence_sources', []):
                    if ev.get('severity_backend'):
                        # LLM-assisted evidence exists; extract crime type from justification
                        just = (ev.get('justification', '')).lower()
                        for kw in ['murder', 'extortion', 'narcotics', 'fraud', 'robbery']:
                            if kw in just:
                                all_crime_keywords.add(kw)
        
        auto_label = f"Group {i+1}"
        if all_crime_keywords:
            auto_label = f"{'/'.join(list(all_crime_keywords)[:2]).title()} Network"
        
        results.append({
            'community_id': i,
            'size': len(community),
            'members': members,
            'internal_edges': internal_edges,
            'cross_case_bridges': list(cross_case_bridges & community),
            'bridge_entities': list(bridge_entities & community),
            'red_herring_count': sum(1 for m in members if m['is_red_herring']),
            'auto_label': auto_label,
            'case_ids': list(all_case_ids),
            'crime_keywords': list(all_crime_keywords),
        })
    
    results.sort(key=lambda x: x['size'], reverse=True)
    return results


def find_strongest_path(G: nx.Graph, source: str, target: str, top_n: int = 3) -> list[dict]:
    """
    Find the path with strongest cumulative relationship significance (§8).
    NOT simply fewest hops — weighted shortest path.
    
    Also surfaces top N alternative paths when similar-strength paths exist.
    """
    if source not in G or target not in G:
        return []
    
    try:
        # Weighted shortest path (inverse weight = strongest path)
        path = nx.shortest_path(G, source=source, target=target, weight='weight')
    except nx.NetworkXNoPath:
        return []
    
    # Build path details with evidence
    path_details = []
    cumulative_weight = 0.0
    for i, node_id in enumerate(path):
        node_data = G.nodes[node_id]
        edge_info = None
        if i > 0:
            prev_node = path[i - 1]
            edge_data = G.edges[prev_node, node_id]
            edge_weight = edge_data.get('weight', 1.0)
            cumulative_weight += edge_weight
            edge_info = {
                'relationship_types': edge_data.get('relationship_types', []),
                'primary_type': edge_data.get('primary_relationship_type', ''),
                'weight': round(edge_weight, 2),
                'justifications': edge_data.get('justifications', []),
                'evidence_sources': edge_data.get('evidence_sources', [])[:3],
                'cross_case': edge_data.get('cross_case', False),
                'case_ids': edge_data.get('case_ids', []),
                'confidence': max(
                    (e.get('confidence', 0) for e in edge_data.get('evidence_sources', [])),
                    default=1.0
                ),
            }
        
        path_details.append({
            'name': node_id,
            'canonical_id': node_data.get('canonical_id', ''),
            'hop_number': i,
            'case_ids': node_data.get('case_ids', []),
            'edge_to_next': edge_info,
            'is_unconfirmed': node_data.get('is_unconfirmed', False),
        })
    
    result = [{
        'path_length': len(path) - 1,
        'hops': len(path) - 1,
        'cumulative_weight': round(cumulative_weight, 2),
        'path': path_details,
        'is_primary': True,
    }]
    
    # Find alternative paths (§8: "Surface top 2-3 alternative paths")
    try:
        all_simple_paths = list(nx.all_simple_paths(G, source, target, cutoff=len(path) + 2))
        # Score each path by cumulative weight
        scored_paths = []
        for alt_path in all_simple_paths:
            if alt_path == path:
                continue
            alt_weight = 0.0
            for j in range(1, len(alt_path)):
                alt_weight += G.edges[alt_path[j-1], alt_path[j]].get('weight', 1.0)
            scored_paths.append((alt_path, alt_weight))
        
        scored_paths.sort(key=lambda x: x[1], reverse=True)
        
        for alt_path, alt_weight in scored_paths[:top_n - 1]:
            alt_details = []
            for j, node_id in enumerate(alt_path):
                node_data = G.nodes[node_id]
                edge_info = None
                if j > 0:
                    prev_node = alt_path[j - 1]
                    edge_data = G.edges[prev_node, node_id]
                    edge_info = {
                        'relationship_types': edge_data.get('relationship_types', []),
                        'primary_type': edge_data.get('primary_relationship_type', ''),
                        'weight': round(edge_data.get('weight', 1.0), 2),
                        'justifications': edge_data.get('justifications', []),
                        'evidence_sources': edge_data.get('evidence_sources', [])[:3],
                        'cross_case': edge_data.get('cross_case', False),
                    }
                alt_details.append({
                    'name': node_id,
                    'canonical_id': node_data.get('canonical_id', ''),
                    'hop_number': j,
                    'edge_to_next': edge_info,
                })
            
            result.append({
                'path_length': len(alt_path) - 1,
                'hops': len(alt_path) - 1,
                'cumulative_weight': round(alt_weight, 2),
                'path': alt_details,
                'is_primary': False,
            })
    except Exception:
        pass  # Alternative path search is best-effort
    
    return result


def get_graph_visualization_data(resolved: ResolvedGraph, 
                                  entity_type_filter: str = None,
                                  relationship_type_filter: str = None) -> dict:
    """
    Get graph data formatted for Cytoscape.js visualization (§9).
    Uses the resolved graph — one node per unique person, typed/weighted edges.
    
    Node encoding:
    - Size based on centrality (key players visually prominent)
    - Color by entity type (person, phone, vehicle, organization)
    - Distinct glow for cross-case bridges
    
    Edge encoding:
    - Line style/color by relationship type
    - Thickness by weight (weighted edges)
    """
    G = resolved.graph
    
    # Compute centrality for node sizing
    centrality = compute_centrality(G)
    
    # Find cross-case bridges for visual distinction
    cross_case_nodes = set()
    for node in G.nodes:
        if len(G.nodes[node].get('case_ids', [])) > 1:
            cross_case_nodes.add(node)
        for _, _, edata in G.edges(node, data=True):
            if edata.get('cross_case', False):
                cross_case_nodes.add(node)
                break
    
    nodes = []
    for node_name in G.nodes:
        node_data = G.nodes[node_name]
        cent = centrality.get(node_name, {})
        
        # Node size: based on combined centrality score
        cent_score = cent.get('combined_score', 0)
        base_size = 20
        max_size = 60
        size = base_size + (cent_score / 100) * (max_size - base_size)
        
        # Boost size for cross-case bridges (§9: "key players visually prominent")
        if node_name in cross_case_nodes:
            size *= 1.3
        
        nodes.append({
            'data': {
                'id': node_name,
                'label': node_name,
                'type': 'Person',
                'confidence': node_data.get('confidence', 1.0),
                'is_ai': False,
                'attributes': node_data.get('attributes', {}),
                'case_ids': node_data.get('case_ids', []),
                'canonical_id': node_data.get('canonical_id', ''),
                'aliases': node_data.get('aliases', []),
                'record_count': node_data.get('record_count', 1),
                'is_unconfirmed': node_data.get('is_unconfirmed', False),
                'resolution_status': node_data.get('resolution_status', 'resolved'),
                # Visualization properties
                'size': round(size, 1),
                'is_cross_case_bridge': node_name in cross_case_nodes,
                'centrality_score': cent_score,
            }
        })
    
    edges = []
    for u, v, edata in G.edges(data=True):
        # Edge type encoding
        rel_types = edata.get('relationship_types', [])
        primary_type = edata.get('primary_relationship_type', 'Associate')
        weight = edata.get('weight', 1.0)
        is_cross_case = edata.get('cross_case', False)
        
        # Filter if requested
        if relationship_type_filter and relationship_type_filter not in rel_types:
            continue
        
        # Edge thickness by weight
        thickness = max(1, min(6, weight * 2))
        
        edges.append({
            'data': {
                'id': f"edge-{u}-{v}",
                'source': u,
                'target': v,
                'label': primary_type,
                'weight': round(weight, 2),
                'relationship_types': rel_types,
                'type_weights': edata.get('type_weights', {}),
                'case_ids': edata.get('case_ids', []),
                'is_cross_case': is_cross_case,
                'justifications': edata.get('justifications', []),
                'evidence_count': edata.get('relationship_count', 0),
                'confidence': max(
                    (e.get('confidence', 0) for e in edata.get('evidence_sources', [])),
                    default=1.0
                ),
                # Visualization properties
                'thickness': round(thickness, 1),
                'is_cross_case_edge': is_cross_case,
            }
        })
    
    return {
        'nodes': nodes,
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges),
        'cross_case_bridges': list(cross_case_nodes),
    }
