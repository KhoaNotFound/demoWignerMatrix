"""
Flask API server — Wigner Matrix Community Detection.

Endpoints:
    POST /api/detect  — Upload dataset file(s) and run detection
    GET  /api/health  — Health check
"""

import os
import sys

import random
import traceback
from typing import Dict
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Engine (single file, same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wigner import (
    parse_mtx_file,
    parse_csv_edges,
    parse_nodes_edges_files,
    parse_graph_file,
    build_adjacency_matrix,
    detect_communities,
)

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

ALLOWED_EXTENSIONS = {'csv', 'mtx', 'txt', 'edges', 'nodes', 'graph'}
MAX_NODES = 10_000
MAX_VIS_EDGES = 10_000


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_EXTENSIONS


def ext(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


# ─────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'max_nodes': MAX_NODES})


# ─────────────────────────────────────────────────────────────
@app.route('/api/detect', methods=['POST'])
def detect():
    try:
        files = request.files.getlist('file')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files uploaded.'}), 400

        # Save all uploaded files
        saved: Dict[str, str] = {}
        for f in files:
            if f.filename and allowed_file(f.filename):
                fname = secure_filename(f.filename)
                fpath = os.path.join(UPLOAD_FOLDER, fname)
                f.save(fpath)
                saved[ext(fname)] = fpath

        if not saved:
            return jsonify({'error': 'No valid files found. Supported: .csv .mtx .edges .nodes .graph .txt'}), 400

        k_clusters = int(request.form.get('k', 0))  # 0 = auto-detect via BBP

        try:
            # ── Parse ──────────────────────────────────────────
            file_info: dict = {}

            if 'mtx' in saved:
                try:
                    parsed = parse_mtx_file(saved['mtx'])
                    edges = parsed['edges']
                    file_info = {
                        'type': 'mtx',
                        'format': parsed['format_info'],
                        'declared_size': f"{parsed['num_rows']}×{parsed['num_cols']}",
                        'declared_entries': parsed['num_entries'],
                    }
                except Exception:
                    # Fallback to general CSV parser
                    edges = parse_csv_edges(saved['mtx'])
                    file_info = {'type': 'mtx (fallback)', 'raw_edges': len(edges)}

            elif 'edges' in saved:
                nodes_path = saved.get('nodes')
                edges = parse_nodes_edges_files(saved['edges'], nodes_path)
                file_info = {'type': 'edges', 'raw_edges': len(edges)}

            elif 'graph' in saved:
                edges = parse_graph_file(saved['graph'])
                file_info = {'type': 'graph', 'raw_edges': len(edges)}

            else:
                # csv / txt / fallback
                key = next(iter(saved))
                edges = parse_csv_edges(saved[key])
                file_info = {'type': key, 'raw_edges': len(edges)}

            if len(edges) == 0:
                return jsonify({'error': 'No valid edges found in the uploaded file(s).'}), 400

            # ── Build adjacency ─────────────────────────────────
            graph = build_adjacency_matrix(edges)
            N = graph['num_nodes']

            if N > MAX_NODES:
                return jsonify({'error': f'Too many nodes ({N}). Maximum: {MAX_NODES}.'}), 400
            if N < 3:
                return jsonify({'error': f'Too few nodes ({N}). Need at least 3.'}), 400

            # ── Run Wigner detection ────────────────────────────
            result = detect_communities(graph['adjacency'], k_clusters=k_clusters)

            if result['status'] == 'error':
                return jsonify({'error': result.get('error', 'Detection failed.')}), 400

            # ── Build response ──────────────────────────────────
            node_ids = graph['node_ids']
            labels   = result['labels']
            nodes_out = [{'id': str(node_ids[i]), 'label': int(labels[i])} for i in range(N)]

            # Collect upper-triangle edges for visualisation
            adj = graph['adjacency'].tocoo()
            edge_set = {(int(i), int(j)) for i, j in zip(adj.row, adj.col) if i < j}
            edge_list = list(edge_set)
            if len(edge_list) > MAX_VIS_EDGES:
                random.seed(42)
                edge_list = random.sample(edge_list, MAX_VIS_EDGES)

            edges_out = [
                {'source': str(node_ids[i]), 'target': str(node_ids[j])}
                for i, j in edge_list
            ]

            total_edges = graph['num_edges']
            return jsonify({
                'status': 'success',
                'has_community': result['has_community'],
                'lambda_max': result['lambda_max'],
                'eigenvalues': result['eigenvalues'],
                'nodes': nodes_out,
                'edges': edges_out,
                'graph_stats': result['graph_stats'],
                'timings': result['timings'],
                'file_info': file_info,
                'visualization_note': (
                    f'Showing {len(edges_out)} of {total_edges} edges for performance.'
                    if len(edges_out) < total_edges else None
                ),
            })

        finally:
            # Clean up saved files
            for fpath in saved.values():
                if os.path.exists(fpath):
                    os.remove(fpath)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 55)
    print("  Wigner Matrix Community Detection — API Server")
    print("  Formats: .csv  .mtx  .edges  .nodes  .graph  .txt")
    print(f"  Max nodes : {MAX_NODES:,}")
    print(f"  Upload dir: {UPLOAD_FOLDER}")
    print("=" * 55)
    app.run(host='0.0.0.0', port=5000, debug=True)
