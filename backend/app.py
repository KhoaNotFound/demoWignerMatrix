"""
app.py — Server FastAPI cho Hệ thống phát hiện cộng đồng Wigner Matrix
Phiên bản này chỉ chứa các thành phần cốt lõi nhất, được viết rõ ràng để dễ đọc và bảo trì.
"""

import os
import time
import shutil
import random
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh, LinearOperator
from sklearn.cluster import KMeans
from typing import List, Tuple, Dict, Any
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ==============================================================================
# CẤU HÌNH HỆ THỐNG
# ==============================================================================

MAX_NODES = 10_000
MAX_VIS_EDGES = 10_000
BBP_THRESHOLD = 2.05 # Ngưỡng BBP để xác định có cấu trúc cộng đồng hay không
ALLOWED_EXTENSIONS = {"csv", "mtx", "txt", "edges", "nodes", "graph"}

# Thư mục chứa file tải lên tạm thời
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Khởi tạo ứng dụng FastAPI
app = FastAPI(title="Wigner Matrix API (Core Engine)")

# Cấu hình CORS để Frontend (React/Vite) có thể gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# HÀM HỖ TRỢ ĐỌC FILE (FILE PARSING)
# ==============================================================================

def get_file_extension(filename: str) -> str:
    """Lấy đuôi file (chữ thường)."""
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""

def parse_file_to_edges(filepath: str) -> List[Tuple[str, str]]:
    """
    Đọc file văn bản và trích xuất danh sách các cạnh (edges) của đồ thị.
    Hỗ trợ đọc các định dạng phổ biến: CSV, TXT, MTX (Matrix Market), EDGES.
    
    Quy tắc xử lý:
    - Bỏ qua các dòng trống và dòng ghi chú (bắt đầu bằng '#' hoặc '%').
    - Tự động nhận diện dấu phân cách là dấu phẩy (',') hoặc khoảng trắng (' ').
    - Bỏ qua các dòng tiêu đề (header) thường gặp.
    - Không lấy các cạnh tự vòng (self-loops: u == v).
    """
    edges = []
    headers_to_skip = {"source", "target", "node1", "node2", "id1", "id2"}
    is_mtx_format = filepath.endswith('.mtx')
    mtx_size_line_parsed = False
    
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as file:
        for line in file:
            line = line.strip()
            
            # Bỏ qua dòng trống hoặc dòng ghi chú
            if not line or line.startswith(("#", "%")):
                continue
                
            # Phân tách dòng thành các phần tử (dùng phẩy hoặc khoảng trắng)
            parts = line.split(",") if "," in line else line.split()
            
            # Một cạnh cần ít nhất 2 node (đỉnh)
            if len(parts) < 2: 
                continue
                
            # Đối với file MTX, dòng dữ liệu đầu tiên (không phải comment) là kích thước ma trận
            if is_mtx_format and not mtx_size_line_parsed and len(parts) >= 3:
                mtx_size_line_parsed = True
                continue
                
            u, v = parts[0].strip(), parts[1].strip()
            
            # Bỏ qua dòng header nếu vô tình đọc phải
            if u.lower() in headers_to_skip or v.lower() in headers_to_skip: 
                continue
                
            # Thêm cạnh vào danh sách nếu 2 node hợp lệ và khác nhau
            if u and v and u != v:
                edges.append((u, v))
                
    # Sử dụng set để loại bỏ các cạnh trùng lặp (vì đồ thị là vô hướng và không trọng số)
    unique_edges = list(set(edges))
    return unique_edges


# ==============================================================================
# HÀM XỬ LÝ ĐỒ THỊ VÀ THUẬT TOÁN WIGNER
# ==============================================================================

def build_sparse_adjacency_matrix(edges: List[Tuple[str, str]]) -> Dict[str, Any]:
    """
    Từ danh sách các cạnh, xây dựng ma trận kề thưa (sparse adjacency matrix).
    Sử dụng định dạng CSR của scipy.sparse để tối ưu bộ nhớ cho đồ thị lớn.
    """
    # Bước 1: Tập hợp tất cả các đỉnh (nodes) duy nhất
    node_set = set()
    for u, v in edges:
        node_set.add(u)
        node_set.add(v)

    # Sắp xếp các đỉnh: số trước, chữ sau để danh sách trông logic hơn
    node_ids = sorted(node_set, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
    
    # Tạo từ điển ánh xạ từ Tên đỉnh (string) -> Chỉ số (integer, từ 0 đến N-1)
    node_to_idx = {node: idx for idx, node in enumerate(node_ids)}
    num_nodes = len(node_ids)

    # Bước 2: Khởi tạo danh sách hàng (rows) và cột (cols) cho ma trận
    rows = []
    cols = []
    seen_edges = set()
    
    for u, v in edges:
        idx_u = node_to_idx[u]
        idx_v = node_to_idx[v]
        
        # Đảm bảo mỗi cạnh chỉ xử lý 1 lần, không quan tâm thứ tự u, v (đồ thị vô hướng)
        edge_key = (min(idx_u, idx_v), max(idx_u, idx_v))
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            # Thêm cả 2 chiều (u->v và v->u) để tạo ma trận đối xứng
            rows.extend([idx_u, idx_v])
            cols.extend([idx_v, idx_u])

    num_unique_edges = len(seen_edges)
    
    # Bước 3: Tạo ma trận CSR (tất cả trọng số cạnh là 1.0)
    data = np.ones(len(rows), dtype=np.float64)
    adjacency_matrix = sparse.csr_matrix((data, (rows, cols)), shape=(num_nodes, num_nodes))

    return {
        "adjacency": adjacency_matrix,
        "node_ids": node_ids,
        "num_nodes": num_nodes,
        "num_edges": num_unique_edges,
    }


def compute_wigner_eigenvalues_sparse(
    adjacency: sparse.csr_matrix, 
    p_avg: float
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Thực hiện phép biến đổi Wigner và tính toán trị riêng/vectơ riêng.
    LUÔN SỬ DỤNG PHƯƠNG PHÁP SPARSE (Ma trận thưa - matrix-free) để tiết kiệm RAM.
    
    Công thức Wigner: W = (A - p_avg * (J - I)) / sqrt(N * p_avg * (1 - p_avg))
    Trong đó:
    - A là ma trận kề (Adjacency matrix)
    - J là ma trận toàn số 1
    - I là ma trận đơn vị
    """
    num_nodes = adjacency.shape[0]
    
    # Tính mẫu số chung (phương sai)
    variance = p_avg * (1.0 - p_avg)
    denominator = np.sqrt(num_nodes * variance)

    # Chuyển A sang float64 để tính toán chính xác
    A_float64 = adjacency.astype(np.float64)

    def wigner_matrix_vector_product(v: np.ndarray) -> np.ndarray:
        """
        Hàm thực hiện phép nhân ma trận W với vectơ v (W * v) MÀ KHÔNG CẦN TẠO MA TRẬN W.
        Đây là kỹ thuật "matrix-free" rất quan trọng cho đồ thị lớn.
        
        W * v = [ A*v - p_avg * (J-I)*v ] / denominator
              = [ A*v - p_avg * (sum(v)*1 - v) ] / denominator
        """
        # A * v (Nhân ma trận thưa với vectơ)
        A_v = A_float64 @ v
        
        # (J - I) * v
        # Nhân ma trận toàn số 1 (J) với v chính là lấy tổng của v, rồi gán cho mọi phần tử.
        # Trừ đi I*v chính là trừ đi v.
        sum_v = v.sum()
        J_minus_I_v = np.full(num_nodes, sum_v, dtype=np.float64) - v
        
        # Ráp vào công thức Wigner
        return (A_v - p_avg * J_minus_I_v) / denominator

    # Khai báo toán tử tuyến tính để Scipy sử dụng
    W_operator = LinearOperator(
        shape=(num_nodes, num_nodes), 
        matvec=wigner_matrix_vector_product, 
        rmatvec=wigner_matrix_vector_product, 
        dtype=np.float64
    )
    
    # Chỉ tính tối đa 50 trị riêng lớn nhất (với đồ thị rất nhỏ thì lấy N-2)
    k_eigenvalues = min(50, num_nodes - 2)
    
    # Đo thời gian tính toán
    t0 = time.perf_counter()
    
    # eigsh là hàm chuyên dùng cho ma trận đối xứng thưa. 'BE' nghĩa là lấy từ 2 đầu (Both Ends).
    eigenvalues, eigenvectors = eigsh(W_operator, k=k_eigenvalues, which='BE')
    
    # Sắp xếp trị riêng theo thứ tự tăng dần
    sort_indices = np.argsort(eigenvalues)
    eigenvalues = eigenvalues[sort_indices]
    eigenvectors = eigenvectors[:, sort_indices]
    
    computation_time = time.perf_counter() - t0
    
    return eigenvalues, eigenvectors, computation_time


def auto_detect_k_using_bbp(eigenvalues: np.ndarray) -> int:
    """
    Sử dụng định lý chuyển pha BBP (BBP Phase Transition) để tự động
    xác định số lượng cộng đồng (K).
    
    Tất cả các trị riêng lớn hơn ngưỡng BBP_THRESHOLD (~2.0) được xem là 
    "tín hiệu" của cấu trúc cộng đồng.
    """
    num_outliers = int(np.sum(eigenvalues > BBP_THRESHOLD))
    # K luôn >= 2. Nếu có 3 trị riêng vượt ngưỡng thì K = 3+1 = 4.
    k_clusters = num_outliers + 1
    return max(2, k_clusters)


def perform_spectral_clustering(
    eigenvectors: np.ndarray, 
    k_clusters: int
) -> List[int]:
    """
    Phân cụm đồ thị bằng thuật toán K-Means trên không gian vectơ riêng (Spectral Clustering).
    """
    # Lấy k_clusters vectơ riêng ứng với các trị riêng LỚN NHẤT (nằm ở cuối mảng)
    top_k_eigenvectors = eigenvectors[:, -k_clusters:]
    
    # Chuẩn hóa độ dài của mỗi hàng (mỗi node) về 1 (L2 normalization)
    # Đây là bước chuẩn bị dữ liệu tiêu chuẩn cho K-Means trong Spectral Clustering
    row_norms = np.linalg.norm(top_k_eigenvectors, axis=1, keepdims=True)
    # Tránh chia cho 0
    row_norms[row_norms == 0] = 1.0
    normalized_X = top_k_eigenvectors / row_norms
    
    # Chạy K-Means
    kmeans = KMeans(n_clusters=k_clusters, n_init=10, random_state=42)
    labels = kmeans.fit_predict(normalized_X)
    
    return labels.tolist()


def detect_communities_pipeline(edges: List[Tuple[str, str]]) -> Dict[str, Any]:
    """
    Hàm pipeline tổng hợp: 
    1. Dựng ma trận -> 2. Tính Wigner & Eigenvalues -> 3. Phân cụm (K-Means).
    """
    start_time = time.perf_counter()
    timings = {}

    # 1. Dựng ma trận kề
    graph_data = build_sparse_adjacency_matrix(edges)
    adjacency = graph_data["adjacency"]
    num_nodes = graph_data["num_nodes"]
    num_edges = graph_data["num_edges"]
    node_ids = graph_data["node_ids"]

    # Kiểm tra tính hợp lệ
    max_possible_edges = num_nodes * (num_nodes - 1) / 2
    p_avg = num_edges / max_possible_edges if max_possible_edges > 0 else 0.0

    if p_avg == 0.0 or p_avg >= 1.0:
        return {"status": "error", "error": "Đồ thị rỗng hoặc kết nối toàn phần (fully connected). Không thể phân cụm."}

    # 2. Phép biến đổi Wigner và tính trị riêng (Luôn dùng Sparse)
    eigenvalues, eigenvectors, eig_time = compute_wigner_eigenvalues_sparse(adjacency, p_avg)
    timings["eigenvalue_decomposition"] = eig_time
    timings["backend"] = "Sparse Matrix-Free (SciPy eigsh)"

    # Lấy trị riêng lớn nhất để kiểm tra điều kiện BBP
    lambda_max = float(eigenvalues[-1])
    has_community = lambda_max > BBP_THRESHOLD

    # 3. Tự động xác định số lượng cụm K (Mặc định dùng BBP)
    k_clusters = auto_detect_k_using_bbp(eigenvalues)
    # Không để K vượt quá một nửa số lượng node
    k_clusters = min(k_clusters, num_nodes // 2)

    # 4. Phân cụm Spectral K-Means
    t_kmeans = time.perf_counter()
    labels = [0] * num_nodes # Khởi tạo nhãn mặc định là 0 (cùng 1 cụm)
    
    if has_community and eigenvectors is not None:
        labels = perform_spectral_clustering(eigenvectors, k_clusters)
        
    timings["clustering"] = time.perf_counter() - t_kmeans
    timings["total"] = time.perf_counter() - start_time

    return {
        "status": "success",
        "has_community": bool(has_community),
        "lambda_max": lambda_max,
        "eigenvalues": eigenvalues.tolist(),
        "labels": labels,
        "k_clusters": k_clusters,
        "node_ids": node_ids,
        "adjacency": adjacency,
        "graph_stats": {
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "density": float(p_avg),
            "avg_degree": float(2 * num_edges / num_nodes) if num_nodes > 0 else 0.0,
        },
        "timings": timings
    }


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.get("/api/health")
async def health_check():
    """Kiểm tra trạng thái server."""
    return {"status": "ok", "max_nodes": MAX_NODES}


@app.post("/api/detect")
async def detect_communities_endpoint(file: List[UploadFile] = File(...)):
    """
    Endpoint chính: Nhận file đồ thị tải lên và trả về kết quả phân cụm cộng đồng.
    Không nhận tham số 'k' nữa, luôn dùng BBP để tự động tính.
    """
    edges = []
    
    # Xử lý tất cả các file tải lên
    for upload in file:
        fname = upload.filename or ""
        ext = get_file_extension(fname)
        
        if ext not in ALLOWED_EXTENSIONS:
            continue
            
        # Lưu file tạm thời
        dest_path = os.path.join(UPLOAD_DIR, os.path.basename(fname))
        with open(dest_path, "wb") as out_file:
            shutil.copyfileobj(upload.file, out_file)
            
        # Đọc dữ liệu và thêm vào danh sách edges tổng
        parsed_edges = parse_file_to_edges(dest_path)
        edges.extend(parsed_edges)
        
        # Xóa file tạm sau khi đã đọc xong
        os.remove(dest_path)
        
    if not edges:
        raise HTTPException(status_code=400, detail="Không tìm thấy cạnh hợp lệ nào trong file tải lên.")

    # Kiểm tra giới hạn số node
    unique_nodes = set()
    for u, v in edges:
        unique_nodes.add(u)
        unique_nodes.add(v)
        
    num_unique_nodes = len(unique_nodes)
    if num_unique_nodes > MAX_NODES:
        raise HTTPException(status_code=400, detail=f"Quá nhiều đỉnh ({num_unique_nodes}). Giới hạn: {MAX_NODES}")
    if num_unique_nodes < 3:
        raise HTTPException(status_code=400, detail="Quá ít đỉnh. Cần ít nhất 3 đỉnh để xử lý.")

    # Thực thi thuật toán
    result = detect_communities_pipeline(edges)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))

    # Chuẩn bị dữ liệu trả về cho Frontend
    node_ids = result["node_ids"]
    labels = result["labels"]
    
    nodes_out = [{"id": str(node_ids[i]), "label": int(labels[i])} for i in range(num_unique_nodes)]

    # Chỉ lấy các cạnh ở nửa tam giác trên (upper triangle) để tránh trùng lặp khi vẽ (i < j)
    adj_matrix = result["adjacency"].tocoo()
    edge_list = [(int(i), int(j)) for i, j in zip(adj_matrix.row, adj_matrix.col) if i < j]
    
    # Nếu có quá nhiều cạnh, chọn ngẫu nhiên một phần để trình duyệt vẽ không bị lag
    vis_note = None
    if len(edge_list) > MAX_VIS_EDGES:
        random.seed(42)
        edge_list = random.sample(edge_list, MAX_VIS_EDGES)
        vis_note = f"Chỉ hiển thị {MAX_VIS_EDGES:,} / {result['graph_stats']['num_edges']:,} cạnh để tối ưu hiệu suất vẽ."

    edges_out = [{"source": str(node_ids[i]), "target": str(node_ids[j])} for i, j in edge_list]

    return JSONResponse(content={
        "status": "success",
        "has_community": result["has_community"],
        "lambda_max": result["lambda_max"],
        "eigenvalues": result["eigenvalues"],
        "nodes": nodes_out,
        "edges": edges_out,
        "graph_stats": result["graph_stats"],
        "timings": result["timings"],
        "visualization_note": vis_note
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
