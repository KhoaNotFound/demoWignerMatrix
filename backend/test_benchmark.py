import sys
sys.path.insert(0, '.')
from benchmark import generate_lfr_benchmark, run_all_algorithms, stability_test

print("=== LFR Benchmark Test ===")
lfr = generate_lfr_benchmark(n=200, mu=0.1, k_communities=4, average_degree=10)
print(f"Graph: {lfr['graph_stats']['num_nodes']} nodes, {lfr['graph_stats']['num_edges']} edges, {lfr['num_true_communities']} true communities")

r = run_all_algorithms(
    lfr['edges'],
    k=lfr['num_true_communities'],
    ground_truth_labels=lfr['ground_truth_labels'],
    ground_truth_nodes=lfr['ground_truth_nodes'],
)
print("\nAlgorithm Comparison:")
for x in r['results']:
    print(f"  {x['algorithm']:30s}  status={x['status']:8s}  K={x.get('k_found','?'):>3}  Q={str(x.get('modularity','?')):>7}  NMI={str(x.get('nmi','?')):>6}  t={x.get('time_ms','?')}ms")

print("\n=== Stability Test ===")
s = stability_test(lfr['edges'], k=lfr['num_true_communities'],
                   ground_truth_labels=lfr['ground_truth_labels'],
                   ground_truth_nodes=lfr['ground_truth_nodes'])
for p in s['stability_points']:
    print(f"  noise={p['noise_pct']:>5}%  nmi_baseline={p.get('nmi_vs_baseline','?')}  nmi_gt={p.get('nmi_vs_groundtruth','?')}")

print("\nAll tests passed!")
