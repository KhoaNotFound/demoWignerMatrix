import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, ReferenceLine,
} from 'recharts';

/* ── Types ─────────────────────────────────────────────────── */
interface AlgoResult {
  algorithm: string;
  status: 'success' | 'error' | 'skipped';
  k_found?: number;
  modularity?: number;
  time_ms?: number;
  nmi?: number;
  ari?: number;
  lambda_max?: number;
  has_community?: boolean;
  error?: string;
}

interface BenchmarkData {
  status: string;
  results: AlgoResult[];
  graph_stats: { num_nodes: number; num_edges: number };
  effective_k: number;
  has_ground_truth: boolean;
  num_true_communities?: number;
  lfr_params?: { n: number; mu: number; average_degree: number };
}

interface StabilityPoint {
  noise_pct: number;
  nmi_vs_baseline?: number;
  nmi_vs_groundtruth?: number;
  lambda_max?: number;
  k_found?: number;
  status: string;
}

interface StabilityData {
  status: string;
  effective_k: number;
  baseline_lambda_max: number;
  stability_points: StabilityPoint[];
}

/* ── LFR Config ─────────────────────────────────────────────── */
interface LFRConfig { n: number; mu: number; k: number; avg_degree: number; }

/* ── Colour palette for algorithms ─────────────────────────── */
const ALGO_COLORS: Record<string, string> = {
  'Wigner Spectral (Ours)': '#3a42c8',
  'Louvain':                '#0ea5e9',
  'Label Propagation':      '#10b981',
  'Greedy Modularity':      '#f59e0b',
  'Girvan-Newman':          '#8b5cf6',
};
const getColor = (name: string) => ALGO_COLORS[name] ?? '#94a3b8';

/* ── Score badge ────────────────────────────────────────────── */
function ScoreBadge({ value, max = 1 }: { value?: number; max?: number }) {
  if (value === undefined || value === null || isNaN(value))
    return <span className="bm-score bm-score--na">N/A</span>;
  const pct = Math.round((value / max) * 100);
  const cls = pct >= 80 ? 'bm-score--high' : pct >= 50 ? 'bm-score--mid' : 'bm-score--low';
  return <span className={`bm-score ${cls}`}>{value.toFixed(3)}</span>;
}

/* ── Main component ─────────────────────────────────────────── */
export default function BenchmarkPanel() {
  const [mode, setMode]               = useState<'lfr' | 'file'>('lfr');
  const [lfr, setLfr]                 = useState<LFRConfig>({ n: 200, mu: 0.1, k: 4, avg_degree: 10 });
  const [files, setFiles]             = useState<File[]>([]);
  const [kClusters, setKClusters]     = useState(0);

  const [loading, setLoading]         = useState(false);
  const [stabLoading, setStabLoading] = useState(false);
  const [error, setError]             = useState<string | null>(null);

  const [benchData, setBenchData]     = useState<BenchmarkData | null>(null);
  const [stabData, setStabData]       = useState<StabilityData | null>(null);

  /* ── Run benchmark ── */
  const runBenchmark = async () => {
    setLoading(true); setError(null); setBenchData(null); setStabData(null);
    try {
      let res: Response;
      if (mode === 'lfr') {
        res = await fetch('/api/benchmark', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: 'lfr', ...lfr }),
        });
      } else {
        const form = new FormData();
        files.forEach(f => form.append('file', f));
        form.append('k', kClusters.toString());
        res = await fetch('/api/benchmark', { method: 'POST', body: form });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Benchmark failed');
      setBenchData(data);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  /* ── Run stability ── */
  const runStability = async () => {
    setStabLoading(true); setError(null); setStabData(null);
    try {
      let res: Response;
      if (mode === 'lfr') {
        res = await fetch('/api/stability', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: 'lfr', ...lfr }),
        });
      } else {
        const form = new FormData();
        files.forEach(f => form.append('file', f));
        form.append('k', kClusters.toString());
        res = await fetch('/api/stability', { method: 'POST', body: form });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Stability test failed');
      setStabData(data);
    } catch (e: any) { setError(e.message); }
    finally { setStabLoading(false); }
  };

  /* ── Bar chart data ── */
  const barData = benchData?.results
    .filter(r => r.status === 'success' && r.modularity !== undefined)
    .map(r => ({ name: r.algorithm.replace(' (Ours)', ' ★'), modularity: r.modularity })) ?? [];

  const timeData = benchData?.results
    .filter(r => r.status === 'success' && r.time_ms !== undefined)
    .map(r => ({ name: r.algorithm.replace(' (Ours)', ' ★'), time_ms: r.time_ms })) ?? [];

  /* ── Stability chart data ── */
  const stabChartData = stabData?.stability_points
    .filter(p => p.status === 'success')
    .map(p => ({
      noise: `${p.noise_pct}%`,
      'NMI vs Baseline': p.nmi_vs_baseline,
      'NMI vs Ground Truth': p.nmi_vs_groundtruth,
      'λ_max': p.lambda_max,
    })) ?? [];

  return (
    <div className="bm-panel">
      {/* ── Header ── */}
      <div className="bm-header">
        <div className="bm-header-left">
          <span className="bm-header-icon">⚖</span>
          <div>
            <h2 className="bm-title">So Sánh & Kiểm Chứng Thuật Toán</h2>
            <p className="bm-subtitle">
              Đánh giá Wigner Spectral so với Louvain, Label Propagation, Greedy Modularity
              bằng các chỉ số khoa học: <strong>NMI</strong>, <strong>ARI</strong>, <strong>Modularity Q</strong>
            </p>
          </div>
        </div>
      </div>

      {/* ── Mode selector ── */}
      <div className="bm-mode-row">
        <button
          className={`bm-mode-btn ${mode === 'lfr' ? 'bm-mode-btn--active' : ''}`}
          onClick={() => setMode('lfr')}
          id="bm-mode-lfr"
        >
          🧪 LFR Benchmark (có Ground Truth)
        </button>
        <button
          className={`bm-mode-btn ${mode === 'file' ? 'bm-mode-btn--active' : ''}`}
          onClick={() => setMode('file')}
          id="bm-mode-file"
        >
          📂 Upload Dataset Thực
        </button>
      </div>

      {/* ── Config ── */}
      <div className="bm-config-card">
        {mode === 'lfr' ? (
          <div className="bm-lfr-config">
            <div className="bm-info-box">
              <span className="bm-info-icon">ℹ</span>
              <span><strong>LFR Benchmark</strong> là đồ thị tổng hợp chuẩn trong nghiên cứu, với cộng đồng đã biết trước (<em>ground truth</em>). Giúp đo NMI và ARI chính xác.</span>
            </div>
            <div className="bm-lfr-grid">
              <div className="bm-field">
                <label className="bm-field-label">Số nút (n)</label>
                <input id="lfr-n" type="number" className="bm-input" value={lfr.n} min={50} max={1000}
                  onChange={e => setLfr(p => ({ ...p, n: +e.target.value }))} />
              </div>
              <div className="bm-field">
                <label className="bm-field-label">Mixing μ <span className="bm-hint">(0=rõ, 0.5=mờ)</span></label>
                <input id="lfr-mu" type="number" className="bm-input" value={lfr.mu} min={0.01} max={0.7} step={0.05}
                  onChange={e => setLfr(p => ({ ...p, mu: +e.target.value }))} />
              </div>
              <div className="bm-field">
                <label className="bm-field-label">Số cộng đồng (k)</label>
                <input id="lfr-k" type="number" className="bm-input" value={lfr.k} min={2} max={20}
                  onChange={e => setLfr(p => ({ ...p, k: +e.target.value }))} />
              </div>
              <div className="bm-field">
                <label className="bm-field-label">Bậc trung bình</label>
                <input id="lfr-deg" type="number" className="bm-input" value={lfr.avg_degree} min={5} max={50}
                  onChange={e => setLfr(p => ({ ...p, avg_degree: +e.target.value }))} />
              </div>
            </div>
          </div>
        ) : (
          <div className="bm-file-config">
            <label className="bm-field-label">Upload file mạng (.csv / .edges / .mtx)</label>
            <input id="bm-file-input" type="file" multiple accept=".csv,.edges,.mtx,.txt,.graph,.nodes"
              className="bm-file-input"
              onChange={e => setFiles(Array.from(e.target.files ?? []))} />
            {files.length > 0 && (
              <div className="bm-file-list">
                {files.map(f => <span key={f.name} className="bm-file-tag">📄 {f.name}</span>)}
              </div>
            )}
            <div className="bm-field" style={{ marginTop: '0.8rem' }}>
              <label className="bm-field-label">Số cộng đồng k (0 = tự động)</label>
              <input id="bm-k-input" type="number" className="bm-input" value={kClusters} min={0} max={50}
                onChange={e => setKClusters(+e.target.value)} />
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="bm-action-row">
          <button id="bm-run-btn" className="bm-btn bm-btn--primary" onClick={runBenchmark} disabled={loading || stabLoading}>
            {loading ? <span className="bm-spinner" /> : '▶'}
            {loading ? 'Đang so sánh…' : 'Chạy So Sánh Thuật Toán'}
          </button>
          <button id="bm-stab-btn" className="bm-btn bm-btn--secondary" onClick={runStability} disabled={loading || stabLoading}>
            {stabLoading ? <span className="bm-spinner" /> : '⚡'}
            {stabLoading ? 'Đang kiểm tra…' : 'Kiểm Tra Độ Ổn Định'}
          </button>
        </div>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="bm-error">
          <span>⚠</span> {error}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════
          BENCHMARK RESULTS
      ══════════════════════════════════════════════════════ */}
      {benchData && (
        <div className="bm-results">

          {/* Summary bar */}
          <div className="bm-summary">
            <div className="bm-summary-stat">
              <span className="bm-summary-val">{benchData.graph_stats.num_nodes.toLocaleString()}</span>
              <span className="bm-summary-lbl">Nút</span>
            </div>
            <div className="bm-summary-div" />
            <div className="bm-summary-stat">
              <span className="bm-summary-val">{benchData.graph_stats.num_edges.toLocaleString()}</span>
              <span className="bm-summary-lbl">Cạnh</span>
            </div>
            {benchData.has_ground_truth && (
              <>
                <div className="bm-summary-div" />
                <div className="bm-summary-stat">
                  <span className="bm-summary-val">{benchData.num_true_communities}</span>
                  <span className="bm-summary-lbl">Cộng đồng thực</span>
                </div>
                <div className="bm-summary-div" />
                <div className="bm-summary-stat">
                  <span className="bm-summary-val">{benchData.lfr_params?.mu}</span>
                  <span className="bm-summary-lbl">Mixing μ</span>
                </div>
              </>
            )}
          </div>

          {/* ── Comparison table ── */}
          <div className="bm-section">
            <h3 className="bm-section-title">📊 Bảng So Sánh Thuật Toán</h3>
            {benchData.has_ground_truth && (
              <p className="bm-section-note">
                NMI và ARI được tính so với <strong>ground truth</strong> thực của LFR. Giá trị gần 1.0 = phát hiện chính xác.
              </p>
            )}
            <div className="bm-table-wrapper">
              <table className="bm-table">
                <thead>
                  <tr>
                    <th>Thuật toán</th>
                    <th>K tìm được</th>
                    <th>Modularity Q ↑</th>
                    {benchData.has_ground_truth && <><th>NMI ↑</th><th>ARI ↑</th></>}
                    <th>Thời gian (ms) ↓</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {benchData.results.map(r => (
                    <tr key={r.algorithm} className={r.algorithm.includes('Wigner') ? 'bm-row--highlight' : ''}>
                      <td>
                        <div className="bm-algo-name">
                          <span className="bm-algo-dot" style={{ background: getColor(r.algorithm) }} />
                          {r.algorithm}
                          {r.algorithm.includes('Wigner') && <span className="bm-our-badge">OUR MODEL</span>}
                        </div>
                      </td>
                      <td className="bm-td-mono">{r.status === 'success' ? r.k_found : '—'}</td>
                      <td><ScoreBadge value={r.modularity} /></td>
                      {benchData.has_ground_truth && (
                        <><td><ScoreBadge value={r.nmi} /></td><td><ScoreBadge value={r.ari} /></td></>
                      )}
                      <td className="bm-td-mono">{r.status === 'success' ? `${r.time_ms}ms` : '—'}</td>
                      <td>
                        {r.status === 'success' && <span className="bm-status bm-status--ok">✓ OK</span>}
                        {r.status === 'error' && <span className="bm-status bm-status--err" title={r.error}>✗ Lỗi</span>}
                        {r.status === 'skipped' && <span className="bm-status bm-status--skip" title={r.error}>⊘ Bỏ qua</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Charts row ── */}
          <div className="bm-charts-row">
            {/* Modularity bar */}
            <div className="bm-chart-card">
              <h3 className="bm-section-title">Modularity Q theo thuật toán</h3>
              <p className="bm-section-note">Giá trị cao hơn = phân cụm tốt hơn (0→1)</p>
              <div className="bm-chart-wrap">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={barData} margin={{ top: 8, right: 16, left: -10, bottom: 60 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" interval={0} />
                    <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => v.toFixed(4)} />
                    <Bar dataKey="modularity" radius={[3, 3, 0, 0]}
                      fill="#3a42c8"
                      label={{ position: 'top', fontSize: 10, formatter: (v: number) => v?.toFixed(3) }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Time bar */}
            <div className="bm-chart-card">
              <h3 className="bm-section-title">Thời gian chạy (ms)</h3>
              <p className="bm-section-note">Thấp hơn = nhanh hơn</p>
              <div className="bm-chart-wrap">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={timeData} margin={{ top: 8, right: 16, left: -10, bottom: 60 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" interval={0} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => `${v} ms`} />
                    <Bar dataKey="time_ms" radius={[3, 3, 0, 0]} fill="#0ea5e9"
                      label={{ position: 'top', fontSize: 10, formatter: (v: number) => `${v}ms` }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Wigner-specific insight */}
          {benchData.results.find(r => r.algorithm.includes('Wigner') && r.status === 'success') && (() => {
            const w = benchData.results.find(r => r.algorithm.includes('Wigner'))!;
            return (
              <div className="bm-insight">
                <div className="bm-insight-icon">◈</div>
                <div className="bm-insight-content">
                  <div className="bm-insight-title">Kết quả Wigner Spectral</div>
                  <div className="bm-insight-body">
                    λ_max = <strong>{w.lambda_max?.toFixed(4)}</strong>
                    {w.has_community
                      ? <> &gt; 2.0 → <span className="bm-tag-signal">Phát hiện cộng đồng (BBP Signal)</span></>
                      : <> ≤ 2.0 → <span className="bm-tag-noise">Không có cấu trúc cộng đồng (BBP Noise)</span></>}
                    {' '}· K = <strong>{w.k_found}</strong>
                    {' '}· Modularity = <strong>{w.modularity?.toFixed(4)}</strong>
                    {w.nmi !== undefined && <> · NMI = <strong>{w.nmi?.toFixed(4)}</strong></>}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════
          STABILITY RESULTS
      ══════════════════════════════════════════════════════ */}
      {stabData && (
        <div className="bm-results">
          <div className="bm-section">
            <h3 className="bm-section-title">⚡ Kiểm Tra Độ Ổn Định (Robustness)</h3>
            <p className="bm-section-note">
              Thêm nhiễu (xáo trộn cạnh) vào đồ thị và kiểm tra Wigner có vẫn phát hiện đúng cộng đồng không.
              NMI gần 1.0 = kết quả ổn định, không bị ảnh hưởng bởi nhiễu.
            </p>
            <div className="bm-stab-stats">
              <div className="bm-summary-stat">
                <span className="bm-summary-val">{stabData.effective_k}</span>
                <span className="bm-summary-lbl">K cộng đồng</span>
              </div>
              <div className="bm-summary-div" />
              <div className="bm-summary-stat">
                <span className="bm-summary-val">{stabData.baseline_lambda_max.toFixed(3)}</span>
                <span className="bm-summary-lbl">λ_max baseline</span>
              </div>
            </div>
            <div className="bm-chart-wrap" style={{ marginTop: '1rem' }}>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={stabChartData} margin={{ top: 8, right: 24, left: -10, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="noise" tick={{ fontSize: 12 }} label={{ value: 'Noise Level', position: 'insideBottom', offset: -4, fontSize: 12 }} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} label={{ value: 'NMI', angle: -90, position: 'insideLeft', fontSize: 12 }} />
                  <Tooltip />
                  <Legend verticalAlign="top" />
                  <ReferenceLine y={0.8} stroke="#dc2626" strokeDasharray="4 4" label={{ value: 'Threshold 0.8', fill: '#dc2626', fontSize: 11 }} />
                  <Line type="monotone" dataKey="NMI vs Baseline" stroke="#3a42c8" strokeWidth={2.5} dot={{ r: 4 }} />
                  {stabChartData.some(d => d['NMI vs Ground Truth'] !== undefined && d['NMI vs Ground Truth'] !== null) && (
                    <Line type="monotone" dataKey="NMI vs Ground Truth" stroke="#10b981" strokeWidth={2.5} dot={{ r: 4 }} />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Stability table */}
            <div className="bm-table-wrapper" style={{ marginTop: '1rem' }}>
              <table className="bm-table">
                <thead>
                  <tr>
                    <th>Noise</th>
                    <th>K tìm được</th>
                    <th>λ_max</th>
                    <th>NMI vs Baseline ↑</th>
                    {stabData.stability_points.some(p => p.nmi_vs_groundtruth !== null && p.nmi_vs_groundtruth !== undefined) && (
                      <th>NMI vs Ground Truth ↑</th>
                    )}
                    <th>Phát hiện</th>
                  </tr>
                </thead>
                <tbody>
                  {stabData.stability_points.map(p => (
                    <tr key={p.noise_pct} className={p.noise_pct === 0 ? 'bm-row--highlight' : ''}>
                      <td className="bm-td-mono">{p.noise_pct}%{p.noise_pct === 0 ? ' (baseline)' : ''}</td>
                      <td className="bm-td-mono">{p.status === 'success' ? p.k_found : '—'}</td>
                      <td className="bm-td-mono">{p.status === 'success' ? p.lambda_max?.toFixed(4) : '—'}</td>
                      <td><ScoreBadge value={p.nmi_vs_baseline} /></td>
                      {stabData.stability_points.some(pp => pp.nmi_vs_groundtruth !== null && pp.nmi_vs_groundtruth !== undefined) && (
                        <td><ScoreBadge value={p.nmi_vs_groundtruth ?? undefined} /></td>
                      )}
                      <td>
                        {p.status === 'success'
                          ? (p.has_community
                            ? <span className="bm-tag-signal">✓ Phát hiện</span>
                            : <span className="bm-tag-noise">✗ Không phát hiện</span>)
                          : <span className="bm-status bm-status--err">{p.error}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
