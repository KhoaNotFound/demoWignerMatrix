"""
Wigner Matrix Community Detection Engine.

Uses Random Matrix Theory (BBP phase transition) to detect communities.
Supports GPU acceleration via CuPy when available.
"""

import time
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh
from sklearn.cluster import KMeans
from typing import Dict, Any, Optional

# Try to import CuPy for GPU acceleration
_USE_GPU = False
try:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        import cupy as cp
        import cupyx.scipy.sparse as cp_sparse
        import cupyx.scipy.sparse.linalg as cp_linalg
    # Test that GPU actually works
    _test = cp.array([1.0, 2.0])
    del _test
    _USE_GPU = True
    print(f"[Engine] CuPy detected — GPU acceleration ENABLED (CUDA {cp.cuda.runtime.runtimeGetVersion()})")
except Exception:
    print("[Engine] CuPy not available — falling back to CPU (scipy)")


def detect_communities(
    adjacency: sparse.csr_matrix,
    k_clusters: int = 2,
    num_eigenvalues: int = 50,
    force_cpu: bool = False,
) -> Dict[str, Any]:
    """
    Perform Wigner-based community detection.
    
    Args:
        adjacency: Sparse adjacency matrix (symmetric, N×N)
        k_clusters: Number of communities to detect
        num_eigenvalues: Number of eigenvalues to compute for histogram
        force_cpu: If True, skip GPU even if available
    
    Returns:
        dict with detection results
    """
    N = adjacency.shape[0]
    use_gpu = _USE_GPU and not force_cpu
    
    timings = {}
    t_start = time.time()
    
    # -----------------------------------------------------------
    # 1. Compute graph statistics
    # -----------------------------------------------------------
    nnz = adjacency.nnz
    num_edges = nnz // 2  # symmetric matrix, each edge counted twice
    possible_edges = N * (N - 1) / 2
    p_avg = num_edges / possible_edges if possible_edges > 0 else 0
    
    if p_avg == 0 or p_avg >= 1:
        return {
            'status': 'error',
            'error': 'Graph is either empty or fully connected. Cannot detect communities.',
        }
    
    # -----------------------------------------------------------
    # 2. Wigner Transformation: W = (A - p_avg) / sqrt(N * p * (1-p))
    # -----------------------------------------------------------
    t0 = time.time()
    variance = p_avg * (1 - p_avg)
    denominator = np.sqrt(N * variance)
    
    if use_gpu:
        try:
            A_gpu = cp_sparse.csr_matrix(adjacency.astype(np.float64))
            
            # W = (A - p_avg * J_offdiag) / denominator
            # For sparse: subtract p_avg from non-zero entries, then handle zeros
            # More efficient: W_ij = (A_ij - p_avg) / denom for i≠j, W_ii = 0
            # Since A is sparse and p_avg is small, we work with the full Wigner matrix
            # But for large N, we need a smarter approach
            
            # For sparse computation: W = (A - p_avg) / denom (element-wise on non-zeros)
            # The off-diagonal zeros contribute -p_avg/denom each
            # This is a dense operation... for truly large matrices we'd use LinearOperator
            
            # For matrices up to ~5000, dense GPU is still fast
            if N <= 5000:
                A_dense_gpu = A_gpu.toarray()
                # Create mask for off-diagonal
                diag_mask = cp.eye(N, dtype=cp.float64)
                W_gpu = (A_dense_gpu - p_avg * (1 - diag_mask)) / denominator
                W_gpu = W_gpu * (1 - diag_mask)  # Zero diagonal
                
                timings['wigner_transform'] = time.time() - t0
                
                # Eigenvalue decomposition on GPU
                t0 = time.time()
                eigenvalues_gpu, eigenvectors_gpu = cp.linalg.eigh(W_gpu)
                eigenvalues = cp.asnumpy(eigenvalues_gpu)
                eigenvectors = cp.asnumpy(eigenvectors_gpu)
                    
                timings['eigenvalue_decomposition'] = time.time() - t0
                timings['backend'] = 'GPU (CuPy/CUDA)'
            else:
                raise MemoryError("Matrix too large for dense GPU, falling back to CPU sparse")
                
        except Exception as e:
            print(f"[Engine] GPU computation failed: {e}, falling back to CPU")
            use_gpu = False
    
    if not use_gpu:
        # CPU path with scipy sparse
        t0 = time.time()
        
        if N <= 3000:
            # Dense path for moderate matrices — vectorized
            A_dense = adjacency.toarray().astype(np.float64)
            W = (A_dense - p_avg) / denominator
            np.fill_diagonal(W, 0)  # W_ii = 0
            
            timings['wigner_transform'] = time.time() - t0
            
            t0 = time.time()
            eigenvalues, eigenvectors = np.linalg.eigh(W)
            
            timings['eigenvalue_decomposition'] = time.time() - t0
        else:
            # Sparse path for very large matrices
            # Use shift-invert for top eigenvalues
            timings['wigner_transform'] = time.time() - t0
            
            t0 = time.time()
            k_eig = min(num_eigenvalues, N - 2)
            
            # Build sparse Wigner matrix (only store non-zero-ish entries)
            W_sparse = (adjacency.astype(np.float64) - p_avg * (sparse.csr_matrix(np.ones((N, N))) - sparse.eye(N))) / denominator
            # Zero out diagonal
            W_sparse.setdiag(0)
            W_sparse.eliminate_zeros()
            
            eigenvalues, eigenvectors = eigsh(W_sparse, k=k_eig, which='BE')
            eigenvalues = np.sort(eigenvalues)
            
            timings['eigenvalue_decomposition'] = time.time() - t0
        
        timings['backend'] = 'CPU (scipy/numpy)'
    
    # -----------------------------------------------------------
    # 3. BBP Phase Transition Test
    # -----------------------------------------------------------
    sorted_eigenvalues = np.sort(eigenvalues)
    lambda_max = float(sorted_eigenvalues[-1])
    threshold = 2.05
    has_community = lambda_max > threshold
    
    # Auto-detect K via BBP theory (outliers count)
    if k_clusters <= 0:
        num_outliers = np.sum(sorted_eigenvalues > threshold)
        # If there's 1 outlier, K=2 (due to rank-1 mean subtraction)
        k_clusters = max(2, int(num_outliers) + 1)
        k_clusters = min(k_clusters, N // 2)
    
    # -----------------------------------------------------------
    # 4. Spectral Clustering (if communities detected)
    # -----------------------------------------------------------
    t0 = time.time()
    labels = np.zeros(N, dtype=int)
    
    if has_community and eigenvectors is not None:
        # Use top-k eigenvectors for K-Means
        top_k_indices = np.argsort(eigenvalues)[-k_clusters:]
        X = eigenvectors[:, top_k_indices]
        
        # Normalize rows
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms[norms == 0] = 1
        X_normalized = X / norms
        
        kmeans = KMeans(n_clusters=k_clusters, n_init=10, random_state=42)
        labels = kmeans.fit_predict(X_normalized)
    
    timings['clustering'] = time.time() - t0
    timings['total'] = time.time() - t_start
    
    return {
        'status': 'success',
        'has_community': bool(has_community),
        'lambda_max': lambda_max,
        'eigenvalues': sorted_eigenvalues.tolist(),
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
