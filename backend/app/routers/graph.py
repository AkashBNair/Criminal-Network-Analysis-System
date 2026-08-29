"""
Graph Router.
Network visualization data, centrality, communities, shortest path.
Now includes case-scoped access control and multi-case analysis.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.models import User, Entity, Relationship, CaseAssignment
from app.auth import get_current_user, VIEW_ALL_CASES
from app.services.graph_analytics import (
    get_graph_data, compute_centrality, detect_communities, find_shortest_path
)
from app.models.models import EntityType, RelationshipType
from collections import defaultdict

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


def check_case_access(user: User, case_id: str, db: Session):
    """Check if user has access to a specific case."""
    if user.role in VIEW_ALL_CASES:
        return True
    assigned = db.query(CaseAssignment).filter(
        CaseAssignment.user_id == user.id,
        CaseAssignment.case_id == case_id,
    ).first()
    return assigned is not None


def get_user_case_ids(user: User, db: Session) -> List[str]:
    """Get all case IDs the user has access to."""
    if user.role in VIEW_ALL_CASES:
        from app.models.models import Case, CaseStatus
        return [c.id for c in db.query(Case).filter(Case.status != CaseStatus.ARCHIVED).all()]
    return [a.case_id for a in user.case_assignments]


class MultiCaseRequest(BaseModel):
    case_ids: List[str]
    entity_type: Optional[str] = None
    relationship_type: Optional[str] = None
    min_confidence: float = 0.0


@router.get("/{case_id}")
def get_case_graph(
    case_id: str,
    entity_type: str = Query(None),
    relationship_type: str = Query(None),
    min_confidence: float = Query(0.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Enforce case-scoped access
    if not check_case_access(current_user, case_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this case")

    graph_data = get_graph_data(
        db,
        case_id=case_id,
        entity_type_filter=entity_type,
        relationship_type_filter=relationship_type,
        min_confidence=min_confidence,
    )
    return graph_data


@router.post("/multi")
def get_multi_case_graph(
    req: MultiCaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get combined graph data for multiple selected cases.
    Only returns data for cases the current user has access to."""
    user_case_ids = get_user_case_ids(current_user, db)

    # Filter to only cases user has access to
    allowed_case_ids = [cid for cid in req.case_ids if cid in user_case_ids]
    if not allowed_case_ids:
        raise HTTPException(status_code=403, detail="No access to any of the selected cases")

    # Build combined graph across all allowed cases
    all_nodes = []
    all_edges = []
    seen_node_ids = set()
    seen_edge_ids = set()

    for case_id in allowed_case_ids:
        graph_data = get_graph_data(
            db,
            case_id=case_id,
            entity_type_filter=req.entity_type,
            relationship_type_filter=req.relationship_type,
            min_confidence=req.min_confidence,
        )
        for node in graph_data["nodes"]:
            nid = node["data"]["id"]
            if nid not in seen_node_ids:
                seen_node_ids.add(nid)
                all_nodes.append(node)
        for edge in graph_data["edges"]:
            eid = edge["data"]["id"]
            if eid not in seen_edge_ids:
                seen_edge_ids.add(eid)
                all_edges.append(edge)

    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "node_count": len(all_nodes),
        "edge_count": len(all_edges),
        "cases_included": len(allowed_case_ids),
    }


@router.get("/{case_id}/centrality")
def get_centrality(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_case_access(current_user, case_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this case")
    return compute_centrality(db, case_id)


@router.post("/multi/centrality")
def get_multi_centrality(
    req: MultiCaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get centrality across multiple selected cases."""
    user_case_ids = get_user_case_ids(current_user, db)
    allowed_case_ids = [cid for cid in req.case_ids if cid in user_case_ids]
    if not allowed_case_ids:
        raise HTTPException(status_code=403, detail="No access to any of the selected cases")

    from app.services.resolved_graph import build_resolved_graph, compute_centrality
    
    resolved = build_resolved_graph(db, allowed_case_ids)
    cent_dict = compute_centrality(resolved.graph)
    
    # Convert dict to list format matching single-case endpoint
    results = []
    for node_id, cent in cent_dict.items():
        node_data = resolved.graph.nodes.get(node_id, {})
        results.append({
            'entity_id': node_id,
            'name': node_data.get('name', node_id),
            'entity_type': 'Person',
            'canonical_id': node_data.get('canonical_id', ''),
            'degree_centrality': cent['degree_centrality'],
            'betweenness_centrality': cent['betweenness_centrality'],
            'eigenvector_centrality': cent['eigenvector_centrality'],
            'combined_score': cent['combined_score'],
            'connections': resolved.graph.degree(node_id),
            'case_ids': node_data.get('case_ids', []),
            'is_unconfirmed': node_data.get('is_unconfirmed', False),
        })
    results.sort(key=lambda x: x['combined_score'], reverse=True)
    return results


@router.get("/{case_id}/communities")
def get_communities(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_case_access(current_user, case_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this case")
    return detect_communities(db, case_id)


@router.get("/path")
def get_shortest_path(
    source: str = Query(...),
    target: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = find_shortest_path(db, source, target)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No path found between the specified entities"
        )
    return result


# ─── Location Graph Endpoints ───────────────────────────────────────────

# Approximate coordinates for Ranthpur city towers (schematic map layout)
TOWER_COORDS = {
    "RTP-T009": {"lat": 25.1800, "lng": 75.8550, "area": "Ring Road"},
    "RTP-T009B": {"lat": 25.1750, "lng": 75.8600, "area": "NH-52 Toll Plaza"},
    "RTP-T014": {"lat": 25.1820, "lng": 75.8520, "area": "Sector 9"},
    "RTP-T017": {"lat": 25.1770, "lng": 75.8480, "area": "Industrial Area"},
    "RTP-T022": {"lat": 25.1850, "lng": 75.8500, "area": "Shastri Nagar"},
    "RTP-T028": {"lat": 25.1810, "lng": 75.8570, "area": "Rajendra Marg"},
    "RTP-T031": {"lat": 25.1835, "lng": 75.8540, "area": "Nehru Colony"},
    "RTP-T045": {"lat": 25.1790, "lng": 75.8510, "area": "Sector 14"},
    "RTP-T052": {"lat": 25.1760, "lng": 75.8560, "area": "Ravindra Colony"},
    "RTP-T060": {"lat": 25.1730, "lng": 75.8590, "area": "NH-52 Escape"},
}

# Known non-location entities to exclude from location graph
EXCLUDE_LOCATION_FALSE_POSITIVES = {
    "north zone", "south zone", "processed", "contact", "unprocessed",
    "pending review", "flagged", "reviewed", "closed",
}


def is_real_location(entity: Entity) -> bool:
    """Filter out spaCy false-positive location extractions."""
    name_lower = entity.name.lower().strip()
    if name_lower in EXCLUDE_LOCATION_FALSE_POSITIVES:
        return False
    # Tower IDs are always real
    if entity.name.startswith("RTP-"):
        return True
    # Entities with address attributes are real
    attrs = entity.attributes or {}
    if "address" in attrs:
        return True
    # Entities with location-type attributes
    if attrs.get("type") in ("tower", "crime_scene", "safe_house", "meeting_point"):
        return True
    # If it looks like a proper place name (not a person name)
    # Keep locations that have multi-word addresses or are clearly places
    if any(kw in name_lower for kw in ["colony", "nagar", "sector", "market", "road", "junction", "crossing", "toll", "plaza", "industrial", "area", "godown", "shop", "hospital", "station", "bus", "park", "gate"]):
        return True
    return False


@router.get("/location/{case_id}")
def get_location_graph(
    case_id: str,
    min_confidence: float = Query(0.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get location-only graph: nodes = locations/towers, edges = co-suspect links.
    Each location node includes suspect presence info.
    """
    if not check_case_access(current_user, case_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this case")

    # Get all location entities for this case
    locations = db.query(Entity).filter(
        Entity.case_id == case_id,
        Entity.is_merged_into.is_(None),
    ).all()

    real_locations = [loc for loc in locations if is_real_location(loc)]
    location_ids = {loc.id for loc in real_locations}

    # Get all person entities for suspect presence
    persons = db.query(Entity).filter(
        Entity.case_id == case_id,
        Entity.entity_type == EntityType.PERSON,
        Entity.is_merged_into.is_(None),
    ).all()
    person_ids = {p.id: p for p in persons}

    # Get Location Presence relationships
    lp_rels = db.query(Relationship).filter(
        Relationship.case_id == case_id,
        Relationship.relationship_type == RelationshipType.LOCATION_PRESENCE,
    ).all()

    # Build suspect-presence map: location_id -> [{person, times, details}]
    suspect_presence: dict = defaultdict(list)
    for rel in lp_rels:
        src_id = rel.source_entity_id
        tgt_id = rel.target_entity_id
        person_id = None
        location_id = None
        if src_id in person_ids and tgt_id in location_ids:
            person_id = src_id
            location_id = tgt_id
        elif tgt_id in person_ids and src_id in location_ids:
            person_id = tgt_id
            location_id = src_id
        if person_id and location_id:
            suspect_presence[location_id].append({
                "person_id": person_id,
                "person_name": person_ids[person_id].name,
                "relationship_id": rel.id,
                "weight": rel.weight,
                "first_observed": str(rel.first_observed) if rel.first_observed else None,
                "last_observed": str(rel.last_observed) if rel.last_observed else None,
            })

    # Also check for Communication relationships to infer location links
    # between suspects at the same tower
    comm_rels = db.query(Relationship).filter(
        Relationship.case_id == case_id,
        Relationship.relationship_type == RelationshipType.COMMUNICATION,
    ).all()

    # Build co-location edges: if two suspects are both present at two different
    # locations, create an edge between those locations
    location_suspects: dict = defaultdict(set)  # location_id -> set of person_ids
    for loc_id, presences in suspect_presence.items():
        for p in presences:
            location_suspects[loc_id].add(p["person_id"])

    # Build edges between locations sharing suspects
    co_location_edges = []
    seen_edges = set()
    loc_list = list(location_suspects.keys())
    for i, loc_a in enumerate(loc_list):
        for loc_b in loc_list[i+1:]:
            shared = location_suspects[loc_a] & location_suspects[loc_b]
            if shared:
                edge_key = tuple(sorted([loc_a, loc_b]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    shared_names = [person_ids[pid].name for pid in shared if pid in person_ids]
                    co_location_edges.append({
                        "data": {
                            "id": f"coloc-{edge_key[0]}-{edge_key[1]}",
                            "source": edge_key[0],
                            "target": edge_key[1],
                            "label": "Co-suspect Movement",
                            "weight": len(shared),
                            "shared_suspects": shared_names,
                        }
                    })

    # Build nodes with suspect presence info
    nodes = []
    for loc in real_locations:
        presences = suspect_presence.get(loc.id, [])
        tower_info = TOWER_COORDS.get(loc.name, {})
        attrs = loc.attributes or {}
        nodes.append({
            "data": {
                "id": loc.id,
                "label": loc.name,
                "address": attrs.get("address", tower_info.get("area", "")),
                "area": tower_info.get("area", ""),
                "lat": tower_info.get("lat"),
                "lng": tower_info.get("lng"),
                "is_tower": loc.name.startswith("RTP-"),
                "suspect_count": len(presences),
                "suspects": presences,
                "case_id": loc.case_id,
                "confidence": loc.confidence_score,
            }
        })

    return {
        "nodes": nodes,
        "edges": co_location_edges,
        "node_count": len(nodes),
        "edge_count": len(co_location_edges),
    }


@router.post("/location/multi")
def get_multi_case_location_graph(
    req: MultiCaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get combined location graph across multiple selected cases."""
    user_case_ids = get_user_case_ids(current_user, db)
    allowed_case_ids = [cid for cid in req.case_ids if cid in user_case_ids]
    if not allowed_case_ids:
        raise HTTPException(status_code=403, detail="No access to any of the selected cases")

    all_nodes = []
    all_edges = []
    seen_node_ids = set()
    seen_edge_ids = set()

    for cid in allowed_case_ids:
        # Inline the location graph logic for each case
        locations = db.query(Entity).filter(
            Entity.case_id == cid,
            Entity.is_merged_into.is_(None),
        ).all()
        real_locations = [loc for loc in locations if is_real_location(loc)]
        location_ids = {loc.id for loc in real_locations}

        persons = db.query(Entity).filter(
            Entity.case_id == cid,
            Entity.entity_type == EntityType.PERSON,
            Entity.is_merged_into.is_(None),
        ).all()
        person_ids = {p.id: p for p in persons}

        lp_rels = db.query(Relationship).filter(
            Relationship.case_id == cid,
            Relationship.relationship_type == RelationshipType.LOCATION_PRESENCE,
        ).all()

        suspect_presence: dict = defaultdict(list)
        for rel in lp_rels:
            src_id, tgt_id = rel.source_entity_id, rel.target_entity_id
            if src_id in person_ids and tgt_id in location_ids:
                suspect_presence[tgt_id].append({
                    "person_id": src_id, "person_name": person_ids[src_id].name,
                    "relationship_id": rel.id, "weight": rel.weight,
                })
            elif tgt_id in person_ids and src_id in location_ids:
                suspect_presence[src_id].append({
                    "person_id": tgt_id, "person_name": person_ids[tgt_id].name,
                    "relationship_id": rel.id, "weight": rel.weight,
                })

        location_suspects: dict = defaultdict(set)
        for loc_id, presences in suspect_presence.items():
            for p in presences:
                location_suspects[loc_id].add(p["person_id"])

        loc_list = list(location_suspects.keys())
        for i, loc_a in enumerate(loc_list):
            for loc_b in loc_list[i+1:]:
                shared = location_suspects[loc_a] & location_suspects[loc_b]
                if shared:
                    edge_key = tuple(sorted([loc_a, loc_b]))
                    eid = f"coloc-{edge_key[0]}-{edge_key[1]}"
                    if eid not in seen_edge_ids:
                        seen_edge_ids.add(eid)
                        shared_names = [person_ids[pid].name for pid in shared if pid in person_ids]
                        all_edges.append({
                            "data": {
                                "id": eid, "source": edge_key[0], "target": edge_key[1],
                                "label": "Co-suspect Movement", "weight": len(shared),
                                "shared_suspects": shared_names,
                            }
                        })

        for loc in real_locations:
            if loc.id not in seen_node_ids:
                seen_node_ids.add(loc.id)
                presences = suspect_presence.get(loc.id, [])
                tower_info = TOWER_COORDS.get(loc.name, {})
                attrs = loc.attributes or {}
                all_nodes.append({
                    "data": {
                        "id": loc.id, "label": loc.name,
                        "address": attrs.get("address", tower_info.get("area", "")),
                        "area": tower_info.get("area", ""),
                        "lat": tower_info.get("lat"), "lng": tower_info.get("lng"),
                        "is_tower": loc.name.startswith("RTP-"),
                        "suspect_count": len(presences),
                        "suspects": presences, "case_id": cid,
                        "confidence": loc.confidence_score,
                    }
                })

    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "node_count": len(all_nodes),
        "edge_count": len(all_edges),
        "cases_included": len(allowed_case_ids),
    }


# ─── People-Only Graph (filtered, excludes locations) ───────────────────────

@router.get("/people/{case_id}")
def get_people_graph(
    case_id: str,
    min_confidence: float = Query(0.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get people-only graph: nodes = persons, phones, vehicles, orgs (no locations).
    Edges = relationships between people (communication, financial, co-accused, etc.)
    """
    if not check_case_access(current_user, case_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this case")

    graph_data = get_graph_data(
        db, case_id=case_id, min_confidence=min_confidence,
    )
    # Filter out Location nodes and Location Presence edges
    filtered_nodes = [n for n in graph_data["nodes"] if n["data"]["type"] != "Location"]
    node_ids = {n["data"]["id"] for n in filtered_nodes}
    filtered_edges = [
        e for e in graph_data["edges"]
        if e["data"]["source"] in node_ids and e["data"]["target"] in node_ids
        and e["data"]["label"] != "Location Presence"
    ]
    return {
        "nodes": filtered_nodes,
        "edges": filtered_edges,
        "node_count": len(filtered_nodes),
        "edge_count": len(filtered_edges),
    }


@router.post("/people/multi")
def get_multi_people_graph(
    req: MultiCaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get combined people-only graph across multiple selected cases."""
    user_case_ids = get_user_case_ids(current_user, db)
    allowed_case_ids = [cid for cid in req.case_ids if cid in user_case_ids]
    if not allowed_case_ids:
        raise HTTPException(status_code=403, detail="No access to any of the selected cases")

    all_nodes = []
    all_edges = []
    seen_node_ids = set()
    seen_edge_ids = set()

    for cid in allowed_case_ids:
        graph_data = get_graph_data(db, case_id=cid, min_confidence=req.min_confidence)
        for node in graph_data["nodes"]:
            nid = node["data"]["id"]
            if nid not in seen_node_ids and node["data"]["type"] != "Location":
                seen_node_ids.add(nid)
                all_nodes.append(node)
        for edge in graph_data["edges"]:
            eid = edge["data"]["id"]
            src = edge["data"]["source"]
            tgt = edge["data"]["target"]
            if (eid not in seen_edge_ids and src in seen_node_ids and tgt in seen_node_ids
                    and edge["data"]["label"] != "Location Presence"):
                seen_edge_ids.add(eid)
                all_edges.append(edge)

    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "node_count": len(all_nodes),
        "edge_count": len(all_edges),
        "cases_included": len(allowed_case_ids),
    }


@router.get("/stats/{case_id}")
def get_graph_stats(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_case_access(current_user, case_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this case")

    entity_count = db.query(Entity).filter(
        Entity.case_id == case_id,
        Entity.is_merged_into.is_(None),
    ).count()
    relationship_count = db.query(Relationship).filter(
        Relationship.case_id == case_id
    ).count()

    type_counts = {}
    for etype in ["Person", "Location", "Phone", "Vehicle", "Organization", "Event"]:
        count = db.query(Entity).filter(
            Entity.case_id == case_id,
            Entity.entity_type == etype,
            Entity.is_merged_into.is_(None),
        ).count()
        type_counts[etype] = count

    rel_type_counts = {}
    for rtype in ["Communication", "Financial Transaction", "Family", "Co-accused",
                   "Associate", "Employment", "Ownership", "Location Presence"]:
        count = db.query(Relationship).filter(
            Relationship.case_id == case_id,
            Relationship.relationship_type == rtype,
        ).count()
        rel_type_counts[rtype] = count

    return {
        "entity_count": entity_count,
        "relationship_count": relationship_count,
        "entity_type_counts": type_counts,
        "relationship_type_counts": rel_type_counts,
    }
