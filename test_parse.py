import sys
sys.path.insert(0, 'backend')
from wigner import parse_csv_edges

print("Testing test.edges:")
edges = parse_csv_edges('test.edges')
print(edges)
