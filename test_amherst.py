import sys
sys.path.insert(0, './backend/engine')
from mtx_parser import parse_mtx_file
from wigner import detect_communities
from graph_builder import build_adjacency_matrix

res = parse_mtx_file('./socfb-Amherst41.mtx')
print(f"Parsed {res['num_rows']} nodes and {len(res['edges'])} edges")

print("Running Wigner algorithm...")
graph = build_adjacency_matrix(res['edges'])
result = detect_communities(graph['adjacency'], k_clusters=2)
print(f"Community? {result['has_community']} lambda_max = {result['lambda_max']:.3f} Time={result['timings']['total']:.3f}s")
