"""
Matrix Market (.mtx) file parser.

Supports:
- coordinate format (sparse)
- pattern / real / integer / complex field types
- symmetric / general / skew-symmetric / hermitian symmetry
- 1-indexed → 0-indexed conversion
"""

import os
from typing import List, Tuple, Dict, Any


def parse_mtx_file(filepath: str) -> Dict[str, Any]:
    """
    Parse a Matrix Market file and extract edges.
    
    Returns:
        dict with keys:
            - edges: List of (source, target) tuples (0-indexed)
            - num_rows: int
            - num_cols: int
            - num_entries: int (as declared in file)
            - format_info: dict with object, format, field, symmetry
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    edges = []
    format_info = {}
    num_rows = 0
    num_cols = 0
    num_entries = 0
    header_parsed = False
    size_parsed = False
    
    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Parse header line (first line)
            if line_num == 1:
                upper_line = line.upper()
                if not upper_line.startswith('%%MATRIXMARKET') and not upper_line.startswith('%MATRIXMARKET'):
                    raise ValueError(
                        f"Invalid MTX file: missing MatrixMarket header. "
                        f"Got: '{line[:50]}...'"
                    )
                parts = line.split()
                if len(parts) < 5:
                    # Some files have minimal headers
                    format_info = {
                        'object': parts[1] if len(parts) > 1 else 'matrix',
                        'format': parts[2] if len(parts) > 2 else 'coordinate',
                        'field': parts[3] if len(parts) > 3 else 'pattern',
                        'symmetry': parts[4] if len(parts) > 4 else 'general',
                    }
                else:
                    format_info = {
                        'object': parts[1].lower(),
                        'format': parts[2].lower(),
                        'field': parts[3].lower(),
                        'symmetry': parts[4].lower(),
                    }
                header_parsed = True
                
                if format_info['format'] != 'coordinate':
                    raise ValueError(
                        f"Only 'coordinate' format is supported for graph data. "
                        f"Got: '{format_info['format']}'"
                    )
                continue
            
            # Skip comment lines
            if line.startswith('%'):
                continue
            
            # Parse size line (first non-comment line after header)
            if header_parsed and not size_parsed:
                parts = line.split()
                if len(parts) < 3:
                    raise ValueError(
                        f"Invalid size line at line {line_num}: expected 'rows cols entries', "
                        f"got '{line}'"
                    )
                num_rows = int(parts[0])
                num_cols = int(parts[1])
                num_entries = int(parts[2])
                size_parsed = True
                continue
            
            # Parse data lines
            if size_parsed:
                parts = line.split()
                if len(parts) < 2:
                    continue
                
                # Convert from 1-indexed to 0-indexed
                row = int(parts[0]) - 1
                col = int(parts[1]) - 1
                
                # Skip self-loops
                if row == col:
                    continue
                
                # Add edge
                edges.append((row, col))
                
                # If symmetric, add reverse edge (only lower triangle is stored)
                if format_info.get('symmetry') in ('symmetric', 'hermitian'):
                    if row != col:
                        edges.append((col, row))
    
    if not header_parsed:
        raise ValueError("Failed to parse MTX header")
    
    if not size_parsed:
        raise ValueError("Failed to parse MTX size line")
    
    # Deduplicate edges
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
    Parse a CSV or Edge list format that can be separated by commas, spaces, or tabs.
    Expects at least 2 columns (source, target).
    Handles files with or without headers, and ignores comment lines.
    """
    edges = []
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        
    if not lines:
        return edges
        
    start_idx = 0
    
    # Sniff header: If the first line cannot be split into at least two items including a number,
    # or explicitly contains string titles like 'source', 'id', skip it.
    first_line_parts = lines[0].strip().replace(',', ' ').split()
    if len(first_line_parts) >= 2:
        # Check if they are non-numeric strings
        if not (first_line_parts[0].replace('.', '').replace('-', '').isdigit() and 
                first_line_parts[1].replace('.', '').replace('-', '').isdigit()):
            start_idx = 1
            
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        
        # Skip empty lines or known comment formats
        if not line or line.startswith('#') or line.startswith('%'):
            continue
            
        # Split logic: prefer comma, fallback to generic whitespace
        if ',' in line:
            parts = line.split(',')
        else:
            parts = line.split()
            
        if len(parts) >= 2:
            source = parts[0].strip()
            target = parts[1].strip()
            if source and target:
                edges.append((source, target))
                
    return edges
