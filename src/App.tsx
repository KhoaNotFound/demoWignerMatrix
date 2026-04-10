import { useState } from 'react';
import FileUpload from './components/FileUpload';
import ResultBanner from './components/ResultBanner';
import EigenvalueChart from './components/EigenvalueChart';
import NetworkGraph3D from './components/NetworkGraph3D';
import NetworkGraph2D from './components/NetworkGraph2D';

interface GraphNode {
  id: string;
  label: number;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface GraphStats {
  num_nodes: number;
  num_edges: number;
  density: number;
  avg_degree: number;
}

interface Timings {
  wigner_transform?: number;
  eigenvalue_decomposition?: number;
  clustering?: number;
  total?: number;
  backend?: string;
}

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
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [is3DMode, setIs3DMode] = useState(true);

  const handleAnalyze = async (files: File[], kClusters: number) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      files.forEach(file => {
        formData.append('file', file);
      });
      formData.append('k', kClusters.toString());

      const response = await fetch('/api/detect', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to process graph');
      }

      setResult(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred while analyzing the network.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="app-container">
        {/* Header */}
        <header className="app-header">
          <div className="app-header-badge">Random Matrix Theory</div>
          <h1 className="app-title">
            <span className="app-title-icon">◈</span>
            Wigner Matrix Community Detection
          </h1>
          <p className="app-subtitle">
            Upload a network dataset to analyze its community structure using the BBP phase transition.
            Supports <code>.csv</code> edge lists and <code>.mtx</code> Matrix Market files.
          </p>
        </header>

        {/* Upload Section */}
        <FileUpload
          onAnalyze={handleAnalyze}
          loading={loading}
          error={error}
        />

        {/* Results */}
        {result && (
          <div className="results-wrapper">
            <ResultBanner
              hasCommunity={result.has_community}
              lambdaMax={result.lambda_max}
              graphStats={result.graph_stats}
              timings={result.timings}
              visualizationNote={result.visualization_note}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', background: 'var(--bg-secondary)', padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--border)', fontWeight: 600, color: 'var(--text-primary)', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
                <span>2D</span>
                <div style={{ position: 'relative', width: '40px', height: '22px', background: is3DMode ? '#4f46e5' : '#cbd5e1', borderRadius: '12px', transition: '0.3s' }}>
                  <div style={{ position: 'absolute', top: '3px', left: is3DMode ? '21px' : '3px', width: '16px', height: '16px', background: 'white', borderRadius: '50%', transition: '0.3s' }} />
                </div>
                <span>3D</span>
                <input 
                  type="checkbox" 
                  checked={is3DMode} 
                  onChange={(e) => setIs3DMode(e.target.checked)} 
                  style={{ display: 'none' }}
                />
              </label>
            </div>

            <div className="viz-grid">
              <EigenvalueChart
                eigenvalues={result.eigenvalues}
                lambdaMax={result.lambda_max}
                hasCommunity={result.has_community}
              />
              {is3DMode ? (
                <NetworkGraph3D
                  nodes={result.nodes}
                  edges={result.edges}
                  hasCommunity={result.has_community}
                />
              ) : (
                <NetworkGraph2D
                  nodes={result.nodes}
                  edges={result.edges}
                  hasCommunity={result.has_community}
                />
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="app-footer">
          <p>Powered by Random Matrix Theory — Wigner Semicircle Law & BBP Phase Transition</p>
        </footer>
      </div>
    </div>
  );
}
