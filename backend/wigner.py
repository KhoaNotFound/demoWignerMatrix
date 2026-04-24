"""
Wigner Matrix Community Detection — All-in-one engine.

Handles:
  - Parsing: .mtx (Matrix Market), .csv/.txt/.edges (edge lists), .nodes/.graph
  - Graph construction (sparse adjacency matrix)
  - Wigner transformation + eigenvalue decomposition (CPU / NumPy + SciPy)
  - BBP Phase Transition test
  - Spectral clustering (K-Means on top-k eigenvectors)
"""

import os
import time
import random
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh
from sklearn.cluster import KMeans
from typing import List, Tuple, Dict, Any, Union


# ─────────────────────────────────────────────────────────────
#  PARSERS
# ─────────────────────────────────────────────────────────────

def parse_mtx_file(filepath: str) -> Dict[str, Any]:
    """
    Parse a Matrix Market (.mtx) file and extract edges.
    More robust: handles missing headers, BOMs, and arbitrary comments.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    edges = []
    format_info = {'object': 'matrix', 'format': 'coordinate', 'field': 'pattern', 'symmetry': 'general'}
    num_rows = num_cols = num_entries = 0
    size_parsed = False

    with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith('%'):
                upper = line.upper()
                if upper.startswith('%%MATRIXMARKET') or upper.startswith('%MATRIXMARKET'):
                    parts = line.split()
                    if len(parts) >= 5:
                        format_info = {
                            'object': parts[1].lower(),
                            'format': parts[2].lower(),
                            'field': parts[3].lower(),
                            'symmetry': parts[4].lower(),
                        }
                continue

            # First non-comment line is the size line
            if not size_parsed:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        num_rows, num_cols, num_entries = int(parts[0]), int(parts[1]), int(parts[2])
                    except ValueError:
                        pass
                size_parsed = True
                continue

            # Data lines
            parts = line.split()
            if len(parts) >= 2:
                r, c = parts[0].strip(), parts[1].strip()
                if r and c and r != c:
                    edges.append((r, c))

    # Deduplicate
    edges = list(set(edges))
    return {
        'edges': edges,
        'num_rows': num_rows,
        'num_cols': num_cols,
        'num_entries': num_entries,
        'format_info': format_info,
    }


def parse_csv_edges(filepath: str) -> List[Tuple[str, str]]:
    """
    Parse CSV / edge-list files (.csv, .txt, .edges).
    Accepts comma, space, or tab-separated; skips comment lines (#, %).
    """
    edges = []
    with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('%'):
                continue
            
            parts = line.split(',') if ',' in line else line.split()
            if len(parts) >= 2:
                src, tgt = parts[0].strip(), parts[1].strip()
                # Skip header-like lines heuristically if they don't look like IDs
                if src.lower() in ('source', 'node1', 'id1') or tgt.lower() in ('target', 'node2', 'id2'):
                    continue
                if src and tgt and src != tgt:
                    edges.append((src, tgt))
    
    return list(set(edges))


def parse_nodes_edges_files(
    edges_filepath: str,
    nodes_filepath: str | None = None
) -> List[Tuple[str, str]]:
    """
    Parse networkrepository-style .edges (and optionally .nodes) files.
    The .edges file is treated as a plain edge list.
    """
    return parse_csv_edges(edges_filepath)


def parse_graph_file(filepath: str) -> List[Tuple[str, str]]:
    """
    Parse a generic .graph file (edge list variant).
    Tries to detect format automatically.
    """
    return parse_csv_edges(filepath)


# ─────────────────────────────────────────────────────────────
#  GRAPH BUILDER
# ─────────────────────────────────────────────────────────────

def build_adjacency_matrix(
    edges: List[Tuple[Union[int, str], Union[int, str]]]
) -> Dict[str, Any]:
    """
    Build a sparse symmetric adjacency matrix from an edge list.
    Returns dict: adjacency, node_ids, node_to_idx, num_nodes, num_edges.
    """
    node_set: set = set()
    for u, v in edges:
        node_set.add(u)
        node_set.add(v)

    node_ids = sorted(node_set, key=lambda x: (isinstance(x, str), x))
    node_to_idx = {node: idx for idx, node in enumerate(node_ids)}
    N = len(node_ids)

    rows, cols = [], []
    seen: set = set()
    for u, v in edges:
        i, j = node_to_idx[u], node_to_idx[v]
        if i == j:
            continue
        key = (min(i, j), max(i, j))
        if key not in seen:
            seen.add(key)
            rows.extend([i, j])
            cols.extend([j, i])

    num_edges = len(seen)
    data = np.ones(len(rows), dtype=np.float64)
    adjacency = sparse.csr_matrix((data, (rows, cols)), shape=(N, N))

    possible = N * (N - 1) / 2
    return {
        'adjacency': adjacency,
        'node_ids': node_ids,
        'node_to_idx': node_to_idx,
        'num_nodes': N,
        'num_edges': num_edges,
        'density': num_edges / possible if possible > 0 else 0,
    }


# ─────────────────────────────────────────────────────────────
#  WIGNER DETECTION ENGINE  (CPU-only)
# ─────────────────────────────────────────────────────────────

def detect_communities(
    adjacency: sparse.csr_matrix,
    k_clusters: int = 2,
    num_eigenvalues: int = 50,
) -> Dict[str, Any]:
    """
    Wigner-based community detection via BBP Phase Transition.

    Steps:
      1. Compute graph statistics (p_avg)
      2. Wigner transform: W = (A - p_avg) / sqrt(N * p * (1-p))
      3. Eigenvalue decomposition (dense for N<=3000, sparse eigsh otherwise)
      4. BBP test: lambda_max > 2.0 → community structure exists
      5. Spectral K-Means clustering on top-k eigenvectors
    """
    N = adjacency.shape[0]
    t_start = time.time()
    timings: Dict[str, Any] = {}

    # 1. Graph stats
    nnz = adjacency.nnz
    num_edges = nnz // 2
    possible = N * (N - 1) / 2
    p_avg = num_edges / possible if possible > 0 else 0

    if p_avg == 0 or p_avg >= 1:
        return {
            'status': 'error',
            'error': 'Graph is empty or fully connected — cannot detect communities.',
        }

    # 2. Wigner transform
    t0 = time.time()
    variance = p_avg * (1 - p_avg)
    denom = np.sqrt(N * variance)
    eigenvectors = None

    if N <= 3000:
        A = adjacency.toarray().astype(np.float64)
        W = (A - p_avg) / denom
        np.fill_diagonal(W, 0.0)
        timings['wigner_transform'] = time.time() - t0

        t0 = time.time()
        eigenvalues, eigenvectors = np.linalg.eigh(W)
        timings['eigenvalue_decomposition'] = time.time() - t0
    else:
        # Sparse / matrix-free path for large graphs (N > 3000)
        # W·v = (A·v - p_avg*(J - I)·v) / denom
        #      = (A·v - p_avg*(sum(v)*1 - v)) / denom
        # This never allocates an N×N dense matrix.
        timings['wigner_transform'] = time.time() - t0
        t0 = time.time()
        k_eig = min(num_eigenvalues, N - 2)

        from scipy.sparse.linalg import LinearOperator
        A_f64 = adjacency.astype(np.float64)

        def _matvec(v: np.ndarray) -> np.ndarray:
            # Wigner matrix-vector product (symmetric, zero diagonal)
            Av = A_f64 @ v
            # (J - I) @ v = sum(v)*ones - v
            Jv = np.full(N, v.sum(), dtype=np.float64) - v
            return (Av - p_avg * Jv) / denom

        W_op = LinearOperator((N, N), matvec=_matvec, rmatvec=_matvec, dtype=np.float64)
        eigenvalues, eigenvectors = eigsh(W_op, k=k_eig, which='BE')
        eigenvalues = np.sort(eigenvalues)
        timings['eigenvalue_decomposition'] = time.time() - t0

    timings['backend'] = 'CPU (NumPy/SciPy)'

    # 3. BBP Phase Transition
    sorted_eig = np.sort(eigenvalues)
    lambda_max = float(sorted_eig[-1])
    threshold = 2.05
    has_community = lambda_max > threshold

    # Auto-detect K
    if k_clusters <= 0:
        num_outliers = int(np.sum(sorted_eig > threshold))
        k_clusters = max(2, num_outliers + 1)
        k_clusters = min(k_clusters, N // 2)

    # 4. Spectral K-Means
    t0 = time.time()
    labels = np.zeros(N, dtype=int)
    if has_community and eigenvectors is not None:
        top_k = np.argsort(eigenvalues)[-k_clusters:]
        X = eigenvectors[:, top_k]
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms[norms == 0] = 1
        X = X / norms
        labels = KMeans(n_clusters=k_clusters, n_init=10, random_state=42).fit_predict(X)
    timings['clustering'] = time.time() - t0
    timings['total'] = time.time() - t_start

    return {
        'status': 'success',
        'has_community': bool(has_community),
        'lambda_max': lambda_max,
        'eigenvalues': sorted_eig.tolist(),
        'labels': labels.tolist(),
        'k_clusters': k_clusters,
        'graph_stats': {
            'num_nodes': N,
            'num_edges': num_edges,
            'density': float(p_avg),
            'avg_degree': float(2 * num_edges / N) if N > 0 else 0,
        },
        'timings': timings,
    }
