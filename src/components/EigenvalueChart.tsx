import { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

interface EigenvalueChartProps {
  eigenvalues: number[];
  lambdaMax: number;
  hasCommunity: boolean;
}

export default function EigenvalueChart({ eigenvalues, lambdaMax, hasCommunity }: EigenvalueChartProps) {
  const histogramData = useMemo(() => {
    if (!eigenvalues || eigenvalues.length === 0) return [];

    const bins = 60;
    const min = Math.min(...eigenvalues);
    const max = Math.max(...eigenvalues);
    const step = (max - min) / bins;

    if (step === 0) return [];

    const histogram = new Array(bins).fill(0).map((_, i) => ({
      name: (min + (i + 0.5) * step).toFixed(2),
      count: 0,
      binStart: min + i * step,
      binEnd: min + (i + 1) * step,
    }));

    eigenvalues.forEach(val => {
      const binIndex = Math.min(Math.floor((val - min) / step), bins - 1);
      if (binIndex >= 0 && histogram[binIndex]) {
        histogram[binIndex].count++;
      }
    });

    return histogram;
  }, [eigenvalues]);

  // Wigner semicircle theoretical curve (normalized)
  const maxCount = Math.max(...histogramData.map(d => d.count), 1);

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">Eigenvalue Spectrum</h3>
        <span className={`chart-badge ${hasCommunity ? 'chart-badge--signal' : 'chart-badge--noise'}`}>
          {hasCommunity ? '🔴 Signal Detected' : '🟢 Pure Noise'}
        </span>
      </div>
      <p className="chart-subtitle">
        BBP Phase Transition — Wigner Semicircle Law
      </p>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={histogramData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10, fill: '#64748b' }}
              tickMargin={8}
              axisLine={{ stroke: '#cbd5e1' }}
              interval={Math.floor(histogramData.length / 8)}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={{ stroke: '#cbd5e1' }}
            />
            <Tooltip
              cursor={{ fill: 'rgba(99, 102, 241, 0.08)' }}
              contentStyle={{
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                background: '#ffffff',
                color: '#0f172a',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
              }}
              labelStyle={{ color: '#475569', marginBottom: '4px' }}
            />
            <ReferenceLine
              x="2.00"
              stroke="#ef4444"
              strokeDasharray="6 4"
              strokeWidth={2}
              label={{
                position: 'top',
                value: 'Wigner Bound (2.0)',
                fill: '#ef4444',
                fontSize: 11,
                fontWeight: 600,
              }}
            />
            {hasCommunity && (
              <ReferenceLine
                x={lambdaMax.toFixed(2)}
                stroke="#10b981"
                strokeDasharray="6 4"
                strokeWidth={2}
                label={{
                  position: 'top',
                  value: `λ_max = ${lambdaMax.toFixed(2)}`,
                  fill: '#10b981',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
            )}
            <Bar dataKey="count" fill="#4f46e5" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="chart-footer">
        The bulk of eigenvalues form a semicircle distribution. If λ_max &gt; 2.0, it breaks out of the bulk, indicating community structure.
      </p>
    </div>
  );
}
