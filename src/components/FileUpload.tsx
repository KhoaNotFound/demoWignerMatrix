import React, { useCallback, useState } from 'react';
import { Upload, FileText, Loader2, X } from 'lucide-react';

interface FileUploadProps {
  onAnalyze: (files: File[], kClusters: number) => void;
  loading: boolean;
  error: string | null;
}

export default function FileUpload({ onAnalyze, loading, error }: FileUploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [kClusters, setKClusters] = useState<number>(0);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFiles(Array.from(e.dataTransfer.files));
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles(Array.from(e.target.files));
    }
  };

  const removeFile = (indexToRemove: number) => {
    setFiles(files.filter((_, index) => index !== indexToRemove));
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  const getFileIcon = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    if (ext === 'mtx') return '🔢';
    if (ext === 'edges' || ext === 'nodes') return '🕸️';
    if (ext === 'csv') return '📊';
    return '📄';
  };

  return (
    <div className="upload-card">
      <h2 className="upload-title">
        <Upload className="upload-title-icon" />
        Upload Network Data
      </h2>
      <p className="upload-subtitle">
        Supports single files (<code>.csv</code>, <code>.mtx</code>) or multiple (<code>.edges</code> & <code>.nodes</code>)
      </p>

      <div
        className={`drop-zone ${dragActive ? 'drop-zone--active' : ''} ${files.length > 0 ? 'drop-zone--has-file' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        {files.length === 0 ? (
          <label className="drop-zone-label">
            <div className="drop-zone-icon-wrapper">
              <Upload className="drop-zone-icon" />
            </div>
            <p className="drop-zone-text">
              <span className="drop-zone-text-bold">Click to choose files</span> or drag & drop here
            </p>
            <p className="drop-zone-hint">CSV • MTX • EDGES • NODES</p>
            <input
              type="file"
              className="drop-zone-input"
              accept=".csv,.mtx,.txt,.edges,.nodes"
              multiple
              onChange={handleFileChange}
            />
          </label>
        ) : (
          <div className="file-preview" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {files.map((file, index) => (
              <div className="file-preview-info" key={index}>
                <span className="file-preview-icon">{getFileIcon(file.name)}</span>
                <div className="file-preview-details">
                  <span className="file-preview-name">{file.name}</span>
                  <span className="file-preview-size">{formatSize(file.size)}</span>
                </div>
                <button className="file-preview-remove" onClick={() => removeFile(index)} title="Remove file">
                  <X size={16} />
                </button>
              </div>
            ))}
            <label className="analyze-button" style={{ marginTop: '0.5rem', background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
              Add more files
              <input type="file" className="drop-zone-input" accept=".csv,.mtx,.txt,.edges,.nodes" multiple onChange={(e) => {
                if (e.target.files) setFiles([...files, ...Array.from(e.target.files)]);
              }} />
            </label>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem' }}>
        <label htmlFor="kClusters" style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          Communities (K):
        </label>
        <select
          id="kClusters"
          value={kClusters}
          onChange={(e) => setKClusters(parseInt(e.target.value))}
          style={{
            padding: '0.5rem',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '1rem',
          }}
        >
          <option value={0}>Auto-detect (Wigner BBP Theory)</option>
          <option value={2}>2 Communities</option>
          <option value={3}>3 Communities</option>
          <option value={4}>4 Communities</option>
          <option value={5}>5 Communities</option>
          <option value={8}>8 Communities</option>
        </select>
      </div>

      <button
        className="analyze-button"
        onClick={() => files.length > 0 && onAnalyze(files, kClusters)}
        disabled={files.length === 0 || loading}
      >
        {loading ? (
          <>
            <Loader2 className="analyze-button-spinner" />
            Analyzing...
          </>
        ) : (
          <>
            <FileText size={18} />
            Analyze Network
          </>
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
