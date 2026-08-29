"""
Case Linkage & Pattern Recognition — Clustering

Builds a similarity graph from pairwise scores, then identifies clusters
of potentially linked cases using:
  1. Connected components on the thresholded similarity graph
  2. DBSCAN clustering on composite feature vectors (cross-check)

Outputs: list of clusters with member case_ids and average confidence.
"""
from __future__ import annotations

import networkx as nx
import numpy as np
from sklearn.cluster import DBSCAN
from collections import defaultdict

from .data_model import LINKAGE_THRESHOLD, DBSCAN_EPS, DBSCAN_MIN_SAMPLES


def build_similarity_graph(links: list[dict], threshold: float = LINKAGE_THRESHOLD) -> nx.Graph:
    """
    Build a graph where nodes = cases, edges = case pairs above threshold.
    Edge weight = composite_score.
    """
    G = nx.Graph()

    for link in links:
        if link["composite_score"] >= threshold:
            G.add_edge(
                link["case_a"],
                link["case_b"],
                weight=link["composite_score"],
                link_data=link,
            )

    return G


def find_clusters(graph: nx.Graph, cases: list[dict]) -> list[dict]:
    """
    Find connected components in the similarity graph.
    Each component is a cluster of potentially linked cases.
    """
    clusters = []

    for i, component in enumerate(nx.connected_components(graph)):
        subgraph = graph.subgraph(component)

        # Average intra-cluster confidence
        weights = [d["weight"] for _, _, d in subgraph.edges(data=True)]
        avg_confidence = sum(weights) / len(weights) if weights else 0.0

        # Find the strongest internal link as the "anchor"
        if weights:
            anchor_edge = max(subgraph.edges(data=True), key=lambda x: x[2]["weight"])
            anchor_link = anchor_edge[2]["link_data"]
        else:
            anchor_link = None

        # Get case details
        case_map = {c["case_id"]: c for c in cases}
        members = []
        for cid in component:
            if cid in case_map:
                c = case_map[cid]
                members.append({
                    "case_id": cid,
                    "case_number": c.get("case_number", ""),
                    "state": c.get("state", ""),
                    "district": c.get("district", ""),
                    "date_time": c.get("date_time", ""),
                })

        # Check if cluster spans multiple states
        states = set(m["state"] for m in members)
        cross_state = len(states) > 1

        # Determine cluster label from shared signatures
        shared_sigs = anchor_link["details"]["signature_behaviors_shared"] if anchor_link else []
        label = _generate_cluster_label(shared_sigs, cross_state, states)

        clusters.append({
            "cluster_id": i + 1,
            "label": label,
            "member_count": len(component),
            "members": sorted(members, key=lambda m: m["date_time"]),
            "avg_confidence": round(avg_confidence, 1),
            "max_confidence": round(max(weights), 1) if weights else 0.0,
            "cross_state": cross_state,
            "states": list(states),
            "shared_signatures": shared_sigs,
            "anchor_link": anchor_link,
        })

    clusters.sort(key=lambda c: c["avg_confidence"], reverse=True)
    return clusters


def dbscan_cross_check(
    cases: list[dict],
    links: list[dict],
    eps: float = DBSCAN_EPS,
    min_samples: int = DBSCAN_MIN_SAMPLES,
) -> list[dict]:
    """
    Cross-check clustering using DBSCAN on composite feature vectors.
    Uses the same scoring components as the main engine but in vector form.
    """
    if len(cases) < min_samples:
        return []

    # Build feature vectors from each case's structured fields
    case_ids = [c["case_id"] for c in cases]
    features = []

    for c in cases:
        sigs = set(c.get("signature_behaviors", []))
        all_sigs = {"posing", "trophy_taking", "overkill", "staging",
                     "specific_mutilation", "ritualistic_element"}
        sig_vec = [1.0 if s in sigs else 0.0 for s in sorted(all_sigs)]

        # Numeric features
        features.append(sig_vec + [
            c.get("overkill_score", 0) / 10.0,
            1.0 if c.get("staging_present") else 0.0,
            {"con": 0, "blitz": 0.25, "surprise": 0.5, "ambush": 0.75, "other": 1.0}.get(c.get("approach_method", ""), 1.0),
            {"weapon": 0, "restraints": 0.33, "threat": 0.66, "none": 1.0, "other": 0.5}.get(c.get("control_method", ""), 0.5),
            {"organized": 0, "disorganized": 0.5, "mixed": 0.25}.get(c.get("crime_scene_organization", ""), 0.5),
            (c.get("victim_age", 30)) / 70.0,
            1.0 if c.get("victim_gender") == "male" else 0.0,
        ])

    X = np.array(features)

    db = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean")
    labels = db.fit_predict(X)

    # Group by cluster label (ignore -1 = noise)
    clusters_dict = defaultdict(list)
    for idx, label in enumerate(labels):
        if label != -1:
            clusters_dict[label].append(case_ids[idx])

    dbscan_clusters = []
    for label, member_ids in sorted(clusters_dict.items()):
        dbscan_clusters.append({
            "dbscan_cluster_id": int(label),
            "member_count": len(member_ids),
            "member_ids": member_ids,
        })

    return dbscan_clusters


def _generate_cluster_label(
    shared_sigs: list[str],
    cross_state: bool,
    states: set[str],
) -> str:
    """Generate a human-readable label for a cluster."""
    sig_labels = {
        "posing": "Body Posing",
        "trophy_taking": "Trophy Taking",
        "overkill": "Excessive Violence",
        "staging": "Scene Staging",
        "specific_mutilation": "Mutilation Pattern",
        "ritualistic_element": "Ritualistic Elements",
    }

    sig_names = [sig_labels.get(s, s) for s in shared_sigs[:3]]

    if not sig_names:
        base = "Linked Cases"
    elif len(sig_names) == 1:
        base = f"Pattern: {sig_names[0]}"
    else:
        base = f"Pattern: {' + '.join(sig_names)}"

    if cross_state:
        base += f" (Cross-State: {', '.join(sorted(states))})"
    else:
        state = list(states)[0] if states else "Unknown"
        base += f" ({state})"

    return base
