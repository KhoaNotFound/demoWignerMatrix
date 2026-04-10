"""
Flask API server for Wigner Matrix Community Detection.

Endpoints:
    POST /api/detect - Upload file (CSV/MTX) and run community detection
    GET  /api/health - Health check
"""

import os
import sys
import json
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Add parent directory for engine imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.mtx_parser import parse_mtx_file, parse_csv_edges
from engine.graph_builder import build_adjacency_matrix
from engine.wigner import detect_communities

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

ALLOWED_EXTENSIONS = {'csv', 'mtx', 'txt', 'edges', 'nodes'}
MAX_NODES = 10000  # Maximum nodes for processing

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    from engine.wigner import _USE_GPU
    return jsonify({
        'status': 'ok',
        'gpu_available': _USE_GPU,
        'max_nodes': MAX_NODES,
    })


@app.route('/api/detect', methods=['POST'])
def detect():
    """
    Upload a file and run community detection.
    
    Accepts:
        - multipart/form-data with 'file' field
        - Optional query param: k (number of clusters, default 2)
    
    Returns JSON with detection results.
    """
    try:
        # --- Check file upload ---
        files = request.files.getlist('file')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files uploaded'}), 400
            
        # Find primary graph file (mtx, csv, txt, or edges)
        primary_file = None
        for f in files:
            ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
            if ext in {'mtx', 'csv', 'txt', 'edges'}:
                primary_file = f
                break
                
        if not primary_file:
            return jsonify({
                'error': f'No valid graph file found. Allowed extensions: .mtx, .csv, .edges, .txt'
            }), 400
        
        # Get parameters
        k_clusters = int(request.form.get('k', 2))
        
        # Save uploaded file
        filename = secure_filename(primary_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        primary_file.save(filepath)
        
        try:
            # --- Parse file ---
            ext = filename.rsplit('.', 1)[1].lower()
            
            if ext == 'mtx':
                parsed = parse_mtx_file(filepath)
                edges = parsed['edges']
                file_info = {
                    'type': 'mtx',
                    'format_info': parsed['format_info'],
                    'declared_size': f"{parsed['num_rows']}×{parsed['num_cols']}",
                    'declared_entries': parsed['num_entries'],
                }
            else:
                # CSV or TXT
                edges = parse_csv_edges(filepath)
                file_info = {
                    'type': 'csv',
                    'raw_edges': len(edges),
                }
            
            if len(edges) == 0:
                return jsonify({'error': 'No valid edges found in file.'}), 400
            
            # --- Build adjacency matrix ---
            graph_data = build_adjacency_matrix(edges)
            N = graph_data['num_nodes']
            
            if N > MAX_NODES:
                return jsonify({
                    'error': f'Too many nodes ({N}). Maximum supported: {MAX_NODES}. '
                             f'Please use a smaller dataset.'
                }), 400
            
            if N < 3:
                return jsonify({
                    'error': f'Too few nodes ({N}). Need at least 3 nodes.'
                }), 400
            
            # --- Run Wigner detection ---
            result = detect_communities(
                adjacency=graph_data['adjacency'],
                k_clusters=k_clusters,
            )
            
            if result['status'] == 'error':
                return jsonify({'error': result.get('error', 'Detection failed')}), 400
            
            # --- Format response ---
            node_ids = graph_data['node_ids']
            labels = result['labels']
            
            # Build nodes array for frontend
            nodes = [
                {'id': str(node_ids[i]), 'label': int(labels[i])}
                for i in range(N)
            ]
            
            # Build edges array for frontend (limit for large graphs)
            # For visualization, sample edges if too many
            total_edges = graph_data['num_edges']
            edge_set = set()
            adj = graph_data['adjacency']
            coo = adj.tocoo()
            
            for i, j in zip(coo.row, coo.col):
                if i < j:  # Only upper triangle
                    edge_set.add((i, j))
            
            max_vis_edges = 10000
            edge_list = list(edge_set)
            if len(edge_list) > max_vis_edges:
                # Sample edges for visualization
                import random
                random.seed(42)
                edge_list = random.sample(edge_list, max_vis_edges)
            
            graph_edges = [
                {'source': str(node_ids[i]), 'target': str(node_ids[j])}
                for i, j in edge_list
            ]
            
            response = {
                'status': 'success',
                'has_community': result['has_community'],
                'lambda_max': result['lambda_max'],
                'eigenvalues': result['eigenvalues'],
                'nodes': nodes,
                'edges': graph_edges,
                'graph_stats': result['graph_stats'],
                'timings': result['timings'],
                'file_info': file_info,
                'visualization_note': (
                    f'Showing {len(graph_edges)} of {total_edges} edges for performance.'
                    if len(edge_list) < total_edges else None
                ),
            }
            
            return jsonify(response)
        
        finally:
            # Clean up uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("  Wigner Matrix Community Detection — Backend API")
    print("=" * 60)
    
    from engine.wigner import _USE_GPU
    if _USE_GPU:
        import cupy as cp
        dev = cp.cuda.Device(0)
        print(f"  GPU: {dev.attributes}")
    else:
        print("  GPU: Not available (using CPU)")
    
    print(f"  Max nodes: {MAX_NODES}")
    print(f"  Upload folder: {UPLOAD_FOLDER}")
    print("=" * 60)
    
    # Run without debug mode to avoid reloader issues with CuPy
    app.run(host='0.0.0.0', port=5000, debug=False)
