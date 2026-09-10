import React from 'react';

export default function StatsPanel({ stats, deviation }) {
  if (!stats) return null;

  return (
    <div className="card">
      <div className="card-title">Session Statistics</div>
      <div className="stats-grid">
        <StatItem label="Saccades" value={stats.total_saccades || 0} />
        <StatItem
          label="Avg Latency"
          value={stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : '--'}
        />
        <StatItem
          label="Avg Amplitude"
          value={stats.avg_amplitude != null ? stats.avg_amplitude.toFixed(1) : '--'}
          unit="px"
        />
        <StatItem
          label="Avg Duration"
          value={stats.avg_duration_ms != null ? `${stats.avg_duration_ms}ms` : '--'}
        />
        <StatItem
          label="Avg Peak Vel."
          value={stats.avg_peak_velocity != null ? stats.avg_peak_velocity.toFixed(0) : '--'}
          unit="px/s"
        />
        <StatItem
          label="Avg Gain"
          value={stats.avg_gain != null ? stats.avg_gain.toFixed(3) : '--'}
        />
      </div>

      {deviation && deviation.deviation_detected && (
        <div style={{
          marginTop: 12,
          padding: '10px 12px',
          background: 'rgba(251, 191, 36, 0.1)',
          border: '1px solid rgba(251, 191, 36, 0.3)',
          borderRadius: 8,
          fontSize: 12,
        }}>
          <strong style={{ color: 'var(--warning)' }}>Baseline Deviation Detected</strong>
          <ul style={{ marginTop: 6, paddingLeft: 16 }}>
            {deviation.deviations.map((d, i) => (
              <li key={i}>
                {d.metric}: {d.current} ({d.direction} than baseline {d.baseline_mean}, z={d.z_score})
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StatItem({ label, value, unit }) {
  return (
    <div className="stat-item">
      <div className="stat-value">
        {value}
        {unit && <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}> {unit}</span>}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
