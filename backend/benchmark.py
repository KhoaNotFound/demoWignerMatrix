"""
Benchmark Engine — Algorithm Comparison & Validation.

Provides:
  - run_all_algorithms(edges, k)       → compare Wigner vs classic algorithms
  - compute_metrics(pred, true)        → NMI, ARI
  - compute_modularity(G, communities) → Modularity Q
  - generate_lfr_benchmark(n, mu, k)   → synthetic graph with ground truth
  - stability_test(edges, k, noises)   → robustness under edge noise
"""

import time
import random
import traceback
import numpy as np
from typing import List, Tuple, Dict, Any

import networkx as nx
from networkx.algorithms import community as nx_community
from sklearn.metrics import normalized_mutual_info_score, adjusted_rand_score

# Local engine
from wigner import build_adjacency_matrix, detect_communities


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def edges_to_nx(edges: List[Tuple]) -> nx.Graph:
    G = nx.Graph()
    for u, v in edges:
        G.add_edge(str(u), str(v))
    return G


def communities_to_labels(communities, node_list: List[str]) -> List[int]:
    """Convert list-of-sets community format → per-node label list."""
    node_to_comm = {}
    for cid, comm in enumerate(communities):
        for node in comm:
            node_to_comm[str(node)] = cid
    return [node_to_comm.get(str(n), -1) for n in node_list]


def compute_modularity(G: nx.Graph, communities) -> float:
    """Compute modularity Q for a given partition."""
    try:
        return nx_community.modularity(G, communities)
    except Exception:
        return float('nan')


def compute_metrics(labels_pred: List[int], labels_true: List[int]) -> Dict[str, float]:
    """Compute NMI and ARI between predicted and ground-truth labels."""
    try:
        nmi = float(normalized_mutual_info_score(labels_true, labels_pred, average_method='arithmetic'))
        ari = float(adjusted_rand_score(labels_true, labels_pred))
    except Exception:
        nmi = ari = float('nan')
    return {'nmi': round(nmi, 4), 'ari': round(ari, 4)}


# ─────────────────────────────────────────────────────────────
#  INDIVIDUAL ALGORITHMS
# ─────────────────────────────────────────────────────────────

def run_louvain(G: nx.Graph) -> Dict[str, Any]:
    t0 = time.time()
    try:
        partition = nx_community.louvain_communities(G, seed=42)
        elapsed = time.time() - t0
        node_list = list(G.nodes())
        labels = communities_to_labels(partition, node_list)
        q = compute_modularity(G, partition)
        return {
            'algorithm': 'Louvain',
            'k_found': len(partition),
            'modularity': round(q, 4),
            'labels': labels,
            'node_list': node_list,
            'time_ms': round(elapsed * 1000, 1),
            'status': 'success',
        }
    except Exception as e:
        return {'algorithm': 'Louvain', 'status': 'error', 'error': str(e), 'time_ms': round((time.time()-t0)*1000,1)}


def run_label_propagation(G: nx.Graph) -> Dict[str, Any]:
    t0 = time.time()
    try:
        partition = list(nx_community.label_propagation_communities(G))
        elapsed = time.time() - t0
        node_list = list(G.nodes())
        labels = communities_to_labels(partition, node_list)
        q = compute_modularity(G, partition)
        return {
            'algorithm': 'Label Propagation',
            'k_found': len(partition),
            'modularity': round(q, 4),
            'labels': labels,
            'node_list': node_list,
            'time_ms': round(elapsed * 1000, 1),
            'status': 'success',
        }
    except Exception as e:
        return {'algorithm': 'Label Propagation', 'status': 'error', 'error': str(e), 'time_ms': round((time.time()-t0)*1000,1)}


def run_greedy_modularity(G: nx.Graph) -> Dict[str, Any]:
    t0 = time.time()
    try:
        partition = list(nx_community.greedy_modularity_communities(G))
        elapsed = time.time() - t0
        node_list = list(G.nodes())
        labels = communities_to_labels(partition, node_list)
        q = compute_modularity(G, partition)
        return {
            'algorithm': 'Greedy Modularity',
            'k_found': len(partition),
            'modularity': round(q, 4),
            'labels': labels,
            'node_list': node_list,
            'time_ms': round(elapsed * 1000, 1),
            'status': 'success',
        }
    except Exception as e:
        return {'algorithm': 'Greedy Modularity', 'status': 'error', 'error': str(e), 'time_ms': round((time.time()-t0)*1000,1)}


def run_girvan_newman(G: nx.Graph, k: int) -> Dict[str, Any]:
    """Girvan-Newman: cut until k communities (capped for performance)."""
    t0 = time.time()
    try:
        if G.number_of_nodes() > 150:
            return {
                'algorithm': 'Girvan-Newman',
                'status': 'skipped',
                'error': 'Skipped: graph too large (>150 nodes) — O(N³) complexity.',
                'time_ms': 0,
            }
        comp = nx_community.girvan_newman(G)
        target_k = max(2, k)
        partition = None
        for communities in comp:
            partition = list(communities)
            if len(partition) >= target_k:
                break
        elapsed = time.time() - t0
        node_list = list(G.nodes())
        labels = communities_to_labels(partition, node_list)
        q = compute_modularity(G, partition)
        return {
            'algorithm': 'Girvan-Newman',
            'k_found': len(partition),
            'modularity': round(q, 4),
            'labels': labels,
            'node_list': node_list,
            'time_ms': round(elapsed * 1000, 1),
            'status': 'success',
        }
    except Exception as e:
        return {'algorithm': 'Girvan-Newman', 'status': 'error', 'error': str(e), 'time_ms': round((time.time()-t0)*1000,1)}


def run_wigner(edges: List[Tuple], k: int, G: nx.Graph) -> Dict[str, Any]:
    t0 = time.time()
    try:
        graph = build_adjacency_matrix(edges)
        result = detect_communities(graph['adjacency'], k_clusters=k)
        elapsed = time.time() - t0

        if result['status'] == 'error':
            return {'algorithm': 'Wigner Spectral (Ours)', 'status': 'error', 'error': result.get('error'), 'time_ms': round(elapsed*1000,1)}

        labels = result['labels']
        node_ids = graph['node_ids']
        k_found = result['k_clusters']

        # Build communities as sets for modularity computation
        comm_map: Dict[int, set] = {}
        for i, lbl in enumerate(labels):
            comm_map.setdefault(lbl, set()).add(str(node_ids[i]))
        communities = list(comm_map.values())
        q = compute_modularity(G, communities)

        return {
            'algorithm': 'Wigner Spectral (Ours)',
            'k_found': k_found,
            'modularity': round(q, 4) if not np.isnan(q) else None,
            'lambda_max': round(result['lambda_max'], 4),
            'has_community': result['has_community'],
            'labels': labels,
            'node_list': [str(n) for n in node_ids],
            'time_ms': round(elapsed * 1000, 1),
            'status': 'success',
        }
    except Exception as e:
        traceback.print_exc()
        return {'algorithm': 'Wigner Spectral (Ours)', 'status': 'error', 'error': str(e), 'time_ms': round((time.time()-t0)*1000,1)}


# ─────────────────────────────────────────────────────────────
#  MAIN COMPARISON RUNNER
# ─────────────────────────────────────────────────────────────

def run_all_algorithms(
    edges: List[Tuple],
    k: int = 0,
    ground_truth_labels: List[int] | None = None,
    ground_truth_nodes: List[str] | None = None,
    include_girvan_newman: bool = True,
) -> Dict[str, Any]:
    """
    Run Wigner + Louvain + LabelProp + Greedy (+ optionally Girvan-Newman)
    on the same edge list. Returns structured comparison table.
    """
    G = edges_to_nx(edges)
    N = G.number_of_nodes()
    E = G.number_of_edges()

    results = []

    # 1. Wigner (ours) — run first to get auto-detected K
    wigner_res = run_wigner(edges, k, G)
    results.append(wigner_res)

    # Use Wigner's K for classic algorithms if k=0 (auto)
    effective_k = k if k > 0 else (wigner_res.get('k_found', 2) if wigner_res['status'] == 'success' else 2)

    # 2. Louvain
    results.append(run_louvain(G))

    # 3. Label Propagation
    results.append(run_label_propagation(G))

    # 4. Greedy Modularity
    results.append(run_greedy_modularity(G))

    # 5. Girvan-Newman (optional, skips large graphs)
    if include_girvan_newman:
        results.append(run_girvan_newman(G, effective_k))

    # ── Ground-truth metrics ──────────────────────────────────
    if ground_truth_labels is not None and ground_truth_nodes is not None:
        gt_map = {str(n): int(l) for n, l in zip(ground_truth_nodes, ground_truth_labels)}
        for res in results:
            if res['status'] != 'success' or 'node_list' not in res:
                continue
            pred = [res['labels'][i] for i in range(len(res['node_list']))]
            true = [gt_map.get(str(res['node_list'][i]), -1) for i in range(len(res['node_list']))]
            metrics = compute_metrics(pred, true)
            res['nmi'] = metrics['nmi']
            res['ari'] = metrics['ari']

    return {
        'status': 'success',
        'graph_stats': {'num_nodes': N, 'num_edges': E},
        'results': results,
        'effective_k': effective_k,
    }


# ─────────────────────────────────────────────────────────────
#  LFR BENCHMARK GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_lfr_benchmark(
    n: int = 200,
    mu: float = 0.1,
    k_communities: int = 4,
    average_degree: int = 10,
    max_degree: int = 50,
    min_community: int | None = None,
) -> Dict[str, Any]:
    """
    Generate an LFR benchmark graph with ground-truth communities.
    mu = mixing parameter (0 = perfect communities, 1 = random).
    Returns edges + ground_truth_labels.
    """
    if min_community is None:
        min_community = max(10, n // (k_communities * 2))

    try:
        G = nx.LFR_benchmark_graph(
            n=n,
            tau1=3,
            tau2=1.5,
            mu=mu,
            average_degree=average_degree,
            max_degree=max_degree,
            min_community=min_community,
            seed=42,
            max_iters=500,
        )
    except Exception as e:
        print(f"LFR generation failed ({e}), falling back to Stochastic Block Model...")
        # Fallback to Stochastic Block Model
        sizes = [n // k_communities] * k_communities
        sizes[-1] += n - sum(sizes)
        
        # p_in > p_out depending on mu
        # average_degree = p_in * (n/k) + p_out * (n - n/k)
        # We can approximate
        p_in = min(1.0, (1 - mu) * average_degree / (n / k_communities))
        p_out = min(1.0, mu * average_degree / (n - n / k_communities))
        
        probs = np.full((k_communities, k_communities), p_out)
        np.fill_diagonal(probs, p_in)
        
        G = nx.stochastic_block_model(sizes, probs.tolist(), seed=42)
        
        # Add 'community' attribute as frozenset to match LFR output
        current_node = 0
        for i, size in enumerate(sizes):
            for _ in range(size):
                G.nodes[current_node]['community'] = frozenset([i])
                current_node += 1

    edges = [(str(u), str(v)) for u, v in G.edges()]
    node_list = sorted(G.nodes())

    # Ground truth from node attribute 'community'
    ground_truth_nodes = [str(n) for n in node_list]
    # Each node has a frozenset of communities it belongs to — use min as label
    raw_communities = [G.nodes[n]['community'] for n in node_list]
    # Map frozensets to integer labels
    comm_to_id: Dict = {}
    ground_truth_labels = []
    cid = 0
    for fc in raw_communities:
        key = frozenset(fc)
        if key not in comm_to_id:
            comm_to_id[key] = cid
            cid += 1
        ground_truth_labels.append(comm_to_id[key])

    num_true_communities = len(comm_to_id)

    return {
        'edges': edges,
        'ground_truth_labels': ground_truth_labels,
        'ground_truth_nodes': ground_truth_nodes,
        'num_true_communities': num_true_communities,
        'graph_stats': {
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'mu': mu,
            'average_degree': average_degree,
        },
    }


# ─────────────────────────────────────────────────────────────
#  STABILITY / ROBUSTNESS TEST
# ─────────────────────────────────────────────────────────────

def add_noise_to_edges(edges: List[Tuple], noise_ratio: float, seed: int = 42) -> List[Tuple]:
    """
    Add noise to an edge list:
      - Remove `noise_ratio` fraction of existing edges
      - Add equal number of random edges
    """
    rng = random.Random(seed)
    all_nodes = list({n for e in edges for n in e})
    N = len(all_nodes)

    num_noise = max(1, int(len(edges) * noise_ratio))
    edge_list = list(edges)

    # Remove random edges
    rng.shuffle(edge_list)
    edge_list = edge_list[num_noise:]  # drop first `num_noise`

    # Add random edges
    edge_set = set(map(frozenset, edge_list))
    added = 0
    attempts = 0
    while added < num_noise and attempts < num_noise * 20:
        u, v = rng.choice(all_nodes), rng.choice(all_nodes)
        key = frozenset([u, v])
        if u != v and key not in edge_set:
            edge_set.add(key)
            edge_list.append((u, v))
            added += 1
        attempts += 1

    return edge_list


def stability_test(
    edges: List[Tuple],
    k: int = 0,
    noise_levels: List[float] | None = None,
    ground_truth_labels: List[int] | None = None,
    ground_truth_nodes: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Test Wigner stability by adding increasing levels of noise.
    Returns per-noise-level results for NMI, k_found, lambda_max.
    """
    if noise_levels is None:
        noise_levels = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

    # Baseline: run on clean graph to get reference labels
    base_graph = build_adjacency_matrix(edges)
    base_result = detect_communities(base_graph['adjacency'], k_clusters=k)

    if base_result['status'] == 'error':
        return {'status': 'error', 'error': base_result.get('error')}

    baseline_labels = base_result['labels']
    baseline_nodes  = [str(n) for n in base_graph['node_ids']]
    effective_k = base_result['k_clusters']

    stability_points = []

    for noise in noise_levels:
        try:
            noisy_edges = add_noise_to_edges(edges, noise, seed=42)
            g = build_adjacency_matrix(noisy_edges)
            res = detect_communities(g['adjacency'], k_clusters=effective_k)

            if res['status'] == 'error':
                stability_points.append({
                    'noise_pct': round(noise * 100, 1),
                    'status': 'error',
                    'error': res.get('error'),
                })
                continue

            pred_labels = res['labels']
            pred_nodes  = [str(n) for n in g['node_ids']]

            # NMI vs baseline (self-consistency)
            pred_map = {n: l for n, l in zip(pred_nodes, pred_labels)}
            base_true = [pred_map.get(n, -1) for n in baseline_nodes]
            self_nmi  = float(normalized_mutual_info_score(baseline_labels, base_true, average_method='arithmetic'))

            # NMI vs ground truth (if provided)
            gt_nmi = None
            if ground_truth_labels is not None and ground_truth_nodes is not None:
                gt_map = {str(n): int(l) for n, l in zip(ground_truth_nodes, ground_truth_labels)}
                true = [gt_map.get(n, -1) for n in pred_nodes]
                gt_nmi = float(normalized_mutual_info_score(true, pred_labels, average_method='arithmetic'))

            stability_points.append({
                'noise_pct': round(noise * 100, 1),
                'k_found': res['k_clusters'],
                'lambda_max': round(res['lambda_max'], 4),
                'has_community': res['has_community'],
                'nmi_vs_baseline': round(self_nmi, 4),
                'nmi_vs_groundtruth': round(gt_nmi, 4) if gt_nmi is not None else None,
                'status': 'success',
            })
        except Exception as e:
            stability_points.append({
                'noise_pct': round(noise * 100, 1),
                'status': 'error',
                'error': str(e),
            })

    return {
        'status': 'success',
        'effective_k': effective_k,
        'baseline_lambda_max': round(base_result['lambda_max'], 4),
        'stability_points': stability_points,
    }
