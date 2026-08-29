"""
Graph Analytics Service.
Centrality analysis, community detection, shortest path using NetworkX.

CONSUMES: resolved_graph.py (single shared graph builder)
No independent graph construction — §0 of the Master Prompt.
"""
import networkx as nx
from sqlalchemy.orm import Session
from app.models.models import Entity, Relationship, EntityType, RelationshipType
from typing import Optional
from app.services.resolved_graph import (
    build_resolved_graph, compute_centrality as compute_centrality_canonical,
    detect_communities_weighted, find_strongest_path, get_graph_visualization_data,
    ResolvedGraph
)


def build_networkx_graph(db: Session, case_id: str = None) -> nx.Graph:
    """
    Build a NetworkX graph from the database entities and relationships.
    Uses the canonical resolved graph builder.
    """
    resolved = build_resolved_graph(db, [case_id] if case_id else None)
    return resolved.graph


def compute_centrality(db: Session, case_id: str = None) -> list[dict]:
    """
    Compute degree, betweenness, and eigenvector centrality for all entities.
    Uses the canonical resolved graph — never builds its own.
    """
    resolved = build_resolved_graph(db, [case_id] if case_id else None)
    G = resolved.graph
    
    if len(G.nodes) == 0:
        return []
    
    centrality = compute_centrality_canonical(G)
    
    results = []
    for node_id, cent in centrality.items():
        node_data = G.nodes[node_id]
        results.append({
            'entity_id': node_id,
            'name': node_data.get('name', node_id),
            'entity_type': 'Person',
            'canonical_id': node_data.get('canonical_id', ''),
            'case_id': node_data.get('case_id', ''),
            'degree_centrality': cent['degree_centrality'],
            'betweenness_centrality': cent['betweenness_centrality'],
            'eigenvector_centrality': cent['eigenvector_centrality'],
            'combined_score': cent['combined_score'],
            'connections': G.degree(node_id),
            'case_ids': node_data.get('case_ids', []),
            'is_unconfirmed': node_data.get('is_unconfirmed', False),
        })
    
    results.sort(key=lambda x: x['combined_score'], reverse=True)
    return results


def detect_communities(db: Session, case_id: str = None) -> list[dict]:
    """
    Detect communities/clusters using Louvain modularity-based clustering (§5).
    Includes bridge entity identification, auto-labels, and red herring flags.
    """
    resolved = build_resolved_graph(db, [case_id] if case_id else None)
    return detect_communities_weighted(resolved.graph)


def find_shortest_path(db: Session, source_id: str, target_id: str) -> Optional[dict]:
    """
    Find the STRONGEST path between two entities (§8).
    Uses weighted shortest path, not just fewest hops.
    Returns primary path plus alternatives.
    """
    resolved = build_resolved_graph(db)
    paths = find_strongest_path(resolved.graph, source_id, target_id)
    
    if not paths:
        return None
    
    return {
        'paths': paths,
        'primary_path': paths[0] if paths else None,
        'alternative_count': len(paths) - 1,
    }


def get_graph_data(db: Session, case_id: str = None,
                   entity_type_filter: str = None,
                   relationship_type_filter: str = None,
                   min_confidence: float = 0.0) -> dict:
    """
    Get graph data formatted for Cytoscape.js visualization (§9).
    Uses the resolved graph — one node per unique person, typed/weighted edges.
    """
    resolved = build_resolved_graph(db, [case_id] if case_id else None)
    return get_graph_visualization_data(
        resolved, 
        entity_type_filter=entity_type_filter,
        relationship_type_filter=relationship_type_filter,
    )
