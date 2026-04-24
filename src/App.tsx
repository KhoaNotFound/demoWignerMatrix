import { useState } from 'react';
import FileUpload from './components/FileUpload';
import ResultBanner from './components/ResultBanner';
import EigenvalueChart from './components/EigenvalueChart';
import NetworkGraph from './components/NetworkGraph';

interface GraphNode  { id: string; label: number; }
interface GraphEdge  { source: string; target: string; }
interface GraphStats { num_nodes: number; num_edges: number; density: number; avg_degree: number; }
interface Timings    { wigner_transform?: number; eigenvalue_decomposition?: number; clustering?: number; total?: number; backend?: string; }

interface DetectionResult {
  status: string;
  has_community: boolean;
  lambda_max: number;
  eigenvalues: number[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  graph_stats: GraphStats;
  timings: Timings;
  visualization_note?: string | null;
}

export default function App() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const [result,  setResult]  = useState<DetectionResult | null>(null);

  const handleAnalyze = async (files: File[], kClusters: number) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const form = new FormData();
      files.forEach(f => form.append('file', f));
      form.append('k', kClusters.toString());

      const res  = await fetch('/api/detect', { method: 'POST', body: form });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || 'Failed to process graph');
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="app-container">

        {/* ── Header ─────────────────────────────────────────── */}
        <header className="app-header">
          <div className="app-header-badge">Random Matrix Theory</div>
          <h1 className="app-title">
            <span className="app-title-icon">◈</span>
            Wigner Matrix Community Detection
          </h1>
          <p className="app-subtitle">
            Upload a network dataset to analyze its community structure via the BBP phase
            transition. Supports&nbsp;
            <code>.csv</code>&nbsp;·&nbsp;<code>.mtx</code>&nbsp;·&nbsp;
            <code>.edges</code>&nbsp;·&nbsp;<code>.nodes</code>&nbsp;·&nbsp;<code>.graph</code>
          </p>
        </header>

        {/* ── Upload ─────────────────────────────────────────── */}
        <FileUpload onAnalyze={handleAnalyze} loading={loading} error={error} />

        {/* ── Results ────────────────────────────────────────── */}
        {result && (
          <div className="results-wrapper">
            <ResultBanner
              hasCommunity={result.has_community}
              lambdaMax={result.lambda_max}
              graphStats={result.graph_stats}
              timings={result.timings}
              visualizationNote={result.visualization_note}
            />

            <div className="viz-grid">
              <EigenvalueChart
                eigenvalues={result.eigenvalues}
                lambdaMax={result.lambda_max}
                hasCommunity={result.has_community}
              />
              <NetworkGraph
                nodes={result.nodes}
                edges={result.edges}
                hasCommunity={result.has_community}
              />
            </div>
          </div>
        )}

        {/* ── Footer ─────────────────────────────────────────── */}
        <footer className="app-footer">
          <p>Wigner Semicircle Law · BBP Phase Transition · Spectral Clustering</p>
        </footer>
      </div>
    </div>
  );
}
