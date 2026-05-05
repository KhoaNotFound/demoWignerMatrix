import sys
sys.path.insert(0, '.')
from wigner import parse_csv_edges

print("Testing test.edges:")
edges = parse_csv_edges('../sample_data/test.edges')
print(edges)
