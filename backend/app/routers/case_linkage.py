"""
Case Linkage & Pattern Recognition - API Router
FastAPI endpoints for /cases, /clusters, /case/{id}/links
"""
import json
import os
from fastapi import APIRouter, HTTPException, Query

from ..services.case_linkage.scoring import compute_all_pairwise_scores, build_narrative_index
from ..services.case_linkage.clustering import build_similarity_graph, find_clusters, dbscan_cross_check
from ..services.case_linkage.explainer import generate_link_explanation, generate_cluster_explanation

router = APIRouter(prefix="/api/case-linkage", tags=["Case Linkage"])

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "case_linkage", "cases.json")

# Cache
_cases = None
_links = None
_clusters = None


def _load_data():
    global _cases, _links, _clusters
    if _cases is not None:
        return _cases, _links, _clusters

    with open(DATA_PATH) as f:
        raw = json.load(f)
    _cases = raw["cases"]

    # Compute pairwise scores (this also builds the narrative index)
    print(f"Computing pairwise scores for {len(_cases)} cases...")
    _links = compute_all_pairwise_scores(_cases, min_score=30.0)
    print(f"Found {_links.__len__()} links above threshold")

    # Build clusters from the similarity graph
    graph = build_similarity_graph(_links, threshold=60)
    _clusters = find_clusters(graph, _cases)
    print(f"Found {_clusters.__len__()} clusters")

    return _cases, _links, _clusters


@router.on_event("startup")
def precompute():
    """Precompute all scores and clusters on startup."""
    _load_data()


@router.get("/cases")
def get_cases(
    state: str = Query(None),
    district: str = Query(None),
    status: str = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    cases, _, _ = _load_data()
    results = cases
    if state:
        results = [c for c in results if c.get("state", "").lower() == state.lower()]
    if district:
        results = [c for c in results if c.get("district", "").lower() == district.lower()]
    if status:
        results = [c for c in results if c.get("status") == status]
    return {"total": len(results), "cases": results[:limit]}


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    cases, _, _ = _load_data()
    for c in cases:
        if c["case_id"] == case_id:
            return c
    raise HTTPException(404, detail=f"Case {case_id} not found")


@router.get("/clusters")
def get_clusters(min_confidence: float = Query(None)):
    _, _, clusters = _load_data()
    results = clusters
    if min_confidence is not None:
        results = [c for c in results if c["avg_confidence"] >= min_confidence]

    # Generate explanations for each cluster
    cases, _, _ = _load_data()
    enriched = []
    for cl in results:
        explanation = generate_cluster_explanation(cl, cases)
        enriched.append({**cl, "explanation": explanation})

    return {"total": len(enriched), "clusters": enriched}


@router.get("/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: int):
    _, _, clusters = _load_data()
    cases, _, _ = _load_data()
    for cl in clusters:
        if cl["cluster_id"] == cluster_id:
            explanation = generate_cluster_explanation(cl, cases)
            return {**cl, "explanation": explanation}
    raise HTTPException(404, detail=f"Cluster {cluster_id} not found")


@router.get("/case/{case_id}/links")
def get_case_links(case_id: str, min_score: float = Query(50.0)):
    cases, links, _ = _load_data()
    case_map = {c["case_id"]: c for c in cases}
    if case_id not in case_map:
        raise HTTPException(404, detail=f"Case {case_id} not found")

    linked = []
    for link in links:
        if link["case_a"] == case_id or link["case_b"] == case_id:
            if link["composite_score"] >= min_score:
                # Generate explanation
                other_id = link["case_b"] if link["case_a"] == case_id else link["case_a"]
                other = case_map.get(other_id, {})
                explanation = generate_link_explanation(link, case_map[case_id], other)
                linked.append({**link, "explanation": explanation})

    linked.sort(key=lambda x: x["composite_score"], reverse=True)
    return {"case_id": case_id, "total_links": len(linked), "links": linked}


@router.get("/stats")
def get_stats():
    cases, links, clusters = _load_data()
    high = [c for c in clusters if c["avg_confidence"] >= 75]
    med = [c for c in clusters if 50 <= c["avg_confidence"] < 75]
    low = [c for c in clusters if c["avg_confidence"] < 50]
    return {
        "total_cases": len(cases),
        "total_clusters": len(clusters),
        "total_links": len(links),
        "high_confidence_clusters": len(high),
        "medium_confidence_clusters": len(med),
        "low_confidence_clusters": len(low),
        "unsolved_cases": len([c for c in cases if c.get("status") == "unsolved"]),
        "human_review_required": True,
    }
