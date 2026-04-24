import React, { useCallback, useState } from 'react';
import { Upload, FileText, Loader2, X } from 'lucide-react';

interface Props {
  onAnalyze: (files: File[], kClusters: number) => void;
  loading: boolean;
  error: string | null;
}

const ACCEPTED = '.csv,.mtx,.txt,.edges,.nodes,.graph';

function formatSize(bytes: number) {
  if (bytes < 1024)    return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase();
  if (ext === 'mtx')               return '🔢';
  if (ext === 'edges' || ext === 'nodes') return '🕸️';
  if (ext === 'graph')             return '📐';
  if (ext === 'csv')               return '📊';
  return '📄';
}

export default function FileUpload({ onAnalyze, loading, error }: Props) {
  const [files,     setFiles]     = useState<File[]>([]);
  const [kClusters, setKClusters] = useState<number>(0);
  const [drag,      setDrag]      = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    setDrag(e.type === 'dragenter' || e.type === 'dragover');
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    setDrag(false);
    if (e.dataTransfer.files.length > 0)
      setFiles(Array.from(e.dataTransfer.files));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) setFiles(Array.from(e.target.files));
  };

  const addFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length)
      setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
  };

  const remove = (i: number) => setFiles(f => f.filter((_, idx) => idx !== i));

  return (
    <div className="upload-card">
      <h2 className="upload-title">
        <Upload className="upload-title-icon" />
        Upload Network Data
      </h2>
      <p className="upload-subtitle">
        Single file&nbsp;<code>.csv</code>&nbsp;<code>.mtx</code>&nbsp;<code>.graph</code>
        &nbsp;— or multi-file&nbsp;<code>.edges</code>&nbsp;+&nbsp;<code>.nodes</code>
      </p>

      {/* Drop zone */}
      <div
        className={`drop-zone ${drag ? 'drop-zone--active' : ''} ${files.length ? 'drop-zone--has-file' : ''}`}
        onDragEnter={handleDrag} onDragLeave={handleDrag}
        onDragOver={handleDrag}  onDrop={handleDrop}
      >
        {files.length === 0 ? (
          <label className="drop-zone-label">
            <div className="drop-zone-icon-wrapper">
              <Upload className="drop-zone-icon" />
            </div>
            <p className="drop-zone-text">
              <span className="drop-zone-text-bold">Click to choose</span> or drag &amp; drop
            </p>
            <p className="drop-zone-hint">CSV · MTX · EDGES · NODES · GRAPH</p>
            <input type="file" className="drop-zone-input" accept={ACCEPTED} multiple onChange={handleChange} />
          </label>
        ) : (
          <div className="file-preview" style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {files.map((f, i) => (
              <div className="file-preview-info" key={i}>
                <span className="file-preview-icon">{fileIcon(f.name)}</span>
                <div className="file-preview-details">
                  <span className="file-preview-name">{f.name}</span>
                  <span className="file-preview-size">{formatSize(f.size)}</span>
                </div>
                <button className="file-preview-remove" onClick={() => remove(i)} title="Remove">
                  <X size={15} />
                </button>
              </div>
            ))}
            <label className="analyze-button" style={{ marginTop: '0.4rem', background: 'var(--bg-muted)', color: 'var(--text)', border: '1px solid var(--border)', boxShadow: 'none' }}>
              Add more files
              <input type="file" className="drop-zone-input" accept={ACCEPTED} multiple onChange={addFiles} />
            </label>
          </div>
        )}
      </div>

      {/* K selector */}
      <div className="k-selector-row">
        <label htmlFor="kClusters" className="k-selector-label">Communities (K):</label>
        <select
          id="kClusters"
          className="k-selector"
          value={kClusters}
          onChange={e => setKClusters(parseInt(e.target.value))}
        >
          <option value={0}>Auto-detect (BBP Theory)</option>
          <option value={2}>2 Communities</option>
          <option value={3}>3 Communities</option>
          <option value={4}>4 Communities</option>
          <option value={5}>5 Communities</option>
          <option value={8}>8 Communities</option>
        </select>
      </div>

      {/* Analyze button */}
      <button
        className="analyze-button"
        onClick={() => files.length && onAnalyze(files, kClusters)}
        disabled={files.length === 0 || loading}
      >
        {loading ? (
          <><Loader2 className="analyze-button-spinner" /> Analyzing…</>
        ) : (
          <><FileText size={17} /> Analyze Network</>
        )}
      </button>

      {error && (
        <div className="upload-error">
          <span className="upload-error-icon">⚠️</span>
          <p>{error}</p>
        </div>
      )}
    </div>
  );
}
