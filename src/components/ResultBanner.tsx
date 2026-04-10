import { CheckCircle2, AlertCircle, Clock, Cpu, BarChart3, Network } from 'lucide-react';

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

interface ResultBannerProps {
  hasCommunity: boolean;
  lambdaMax: number;
  graphStats: GraphStats;
  timings: Timings;
  visualizationNote?: string | null;
}

export default function ResultBanner({ 
  hasCommunity, 
  lambdaMax, 
  graphStats,
  timings,
  visualizationNote,
}: ResultBannerProps) {
  const formatTime = (seconds?: number) => {
    if (seconds === undefined) return '—';
    if (seconds < 0.001) return '<1ms';
    if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
    return `${seconds.toFixed(2)}s`;
  };

  return (
    <div className="result-section">
      {/* Main Status */}
      <div className={`status-banner ${hasCommunity ? 'status-banner--success' : 'status-banner--warning'}`}>
        <div className="status-banner-icon">
          {hasCommunity ? (
            <CheckCircle2 size={32} />
          ) : (
            <AlertCircle size={32} />
          )}
        </div>
        <div className="status-banner-content">
          <h3 className="status-banner-title">
            {hasCommunity ? 'Communities Detected!' : 'No Communities Found'}
          </h3>
          <p className="status-banner-text">
            {hasCommunity
              ? `The largest eigenvalue (λ_max = ${lambdaMax.toFixed(4)}) exceeded the Wigner semicircle bound (2.0). The network has been successfully clustered.`
              : `The largest eigenvalue (λ_max = ${lambdaMax.toFixed(4)}) is within the Wigner semicircle bound. The network connections appear to be pure noise.`
            }
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <Network size={20} className="stat-card-icon" />
          <div className="stat-card-content">
            <span className="stat-card-value">{graphStats.num_nodes.toLocaleString()}</span>
            <span className="stat-card-label">Nodes</span>
          </div>
        </div>
        <div className="stat-card">
          <BarChart3 size={20} className="stat-card-icon" />
          <div className="stat-card-content">
            <span className="stat-card-value">{graphStats.num_edges.toLocaleString()}</span>
            <span className="stat-card-label">Edges</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-card-icon stat-card-icon--text">ρ</span>
          <div className="stat-card-content">
            <span className="stat-card-value">{(graphStats.density * 100).toFixed(2)}%</span>
            <span className="stat-card-label">Density</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-card-icon stat-card-icon--text">λ</span>
          <div className="stat-card-content">
            <span className="stat-card-value">{lambdaMax.toFixed(4)}</span>
            <span className="stat-card-label">λ_max</span>
          </div>
        </div>
        <div className="stat-card">
          <Clock size={20} className="stat-card-icon" />
          <div className="stat-card-content">
            <span className="stat-card-value">{formatTime(timings.total)}</span>
            <span className="stat-card-label">Total Time</span>
          </div>
        </div>
        <div className="stat-card">
          <Cpu size={20} className="stat-card-icon" />
          <div className="stat-card-content">
            <span className="stat-card-value stat-card-value--small">{timings.backend || 'CPU'}</span>
            <span className="stat-card-label">Backend</span>
          </div>
        </div>
      </div>

      {visualizationNote && (
        <div className="vis-note">
          <span>ℹ️</span>
          <span>{visualizationNote}</span>
        </div>
      )}
    </div>
  );
}
