"""
Graph builder - constructs sparse adjacency matrices from edge lists.
"""

import numpy as np
from scipy import sparse
from typing import List, Tuple, Dict, Any, Union


def build_adjacency_matrix(
    edges: List[Tuple[Union[int, str], Union[int, str]]]
) -> Dict[str, Any]:
    """
    Build a sparse adjacency matrix from an edge list.
    
    Args:
        edges: List of (source, target) tuples. 
               Can be integer (0-indexed) or string node IDs.
    
    Returns:
        dict with keys:
            - adjacency: scipy.sparse.csr_matrix (symmetric)
            - node_ids: list of original node IDs (ordered)
            - node_to_idx: dict mapping node ID → matrix index
            - num_nodes: int
            - num_edges: int (unique undirected edges)
            - density: float
    """
    # Collect unique nodes
    node_set = set()
    for u, v in edges:
        node_set.add(u)
        node_set.add(v)
    
    node_ids = sorted(node_set, key=lambda x: (isinstance(x, str), x))
    node_to_idx = {node: idx for idx, node in enumerate(node_ids)}
    N = len(node_ids)
    
    # Build sparse matrix
    rows = []
    cols = []
    seen = set()
    
    for u, v in edges:
        i = node_to_idx[u]
        j = node_to_idx[v]
        
        if i == j:
            continue  # Skip self-loops
        
        edge_key = (min(i, j), max(i, j))
        if edge_key not in seen:
            seen.add(edge_key)
            rows.extend([i, j])
            cols.extend([j, i])
    
    num_edges = len(seen)
    
    data = np.ones(len(rows), dtype=np.float64)
    adjacency = sparse.csr_matrix((data, (rows, cols)), shape=(N, N))
    
    # Calculate density
    possible_edges = N * (N - 1) / 2
    density = num_edges / possible_edges if possible_edges > 0 else 0
    
    return {
        'adjacency': adjacency,
        'node_ids': node_ids,
        'node_to_idx': node_to_idx,
        'num_nodes': N,
        'num_edges': num_edges,
        'density': density,
    }
