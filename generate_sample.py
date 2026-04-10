import numpy as np

def generate_wigner_mtx(filename, n_nodes=800, p=0.1, k=2):
    # Create simple blockmodel
    np.random.seed(42)
    # Background completely random edges
    edges = set()
    for i in range(n_nodes):
        for j in range(i+1, n_nodes):
            if np.random.rand() < p:
                edges.add((i, j))
                
    # Add communities implicitly
    comm_size = n_nodes // k
    p_in = p + 0.15 # Stronger within community
    for c in range(k):
        start = c * comm_size
        end = min((c+1) * comm_size, n_nodes)
        for i in range(start, end):
            for j in range(i+1, end):
                if np.random.rand() < p_in:
                    edges.add((i, j))
                    
    with open(filename, 'w') as f:
        f.write("%%MatrixMarket matrix coordinate pattern symmetric\n")
        f.write(f"% Generated Wigner Dataset with {k} communities\n")
        f.write(f"{n_nodes} {n_nodes} {len(edges)}\n")
        for u, v in edges:
            f.write(f"{u+1} {v+1}\n")
    print(f"Saved {filename} with {n_nodes} nodes and {len(edges)} edges")

generate_wigner_mtx('sample_graph_communities.mtx', 1500, 0.02, 3)
