import React from 'react';

// Clinical reference ranges for adult saccades (approximate, from literature)
// Source: Leigh & Zee "The Neurology of Eye Movements", Munoz et al., etc.
const RANGES = {
  avg_latency_ms: {
    label: 'Avg Latency',
    unit: 'ms',
    format: v => `${v}`,
    // Normal: 150-250ms   Slow (possible PD/AD): >300ms   Anticipatory: <80ms
    color: v => v == null ? null : v < 80 ? 'danger' : v <= 250 ? 'success' : v <= 350 ? 'warning' : 'danger',
    hint: 'Normal: 150–250 ms. >300 ms may indicate Parkinson\'s or Alzheimer\'s.',
  },
  avg_amplitude: {
    label: 'Avg Amplitude',
    unit: 'px',
    format: v => v.toFixed(1),
    color: () => null,  // context-dependent (screen size / distance unknown)
    hint: 'Saccade size in pixels.',
  },
  avg_duration_ms: {
    label: 'Avg Duration',
    unit: 'ms',
    format: v => `${v}`,
    // Normal: 20-100ms   Prolonged: >120ms
    color: v => v == null ? null : v <= 100 ? 'success' : v <= 150 ? 'warning' : 'danger',
    hint: 'Normal: 20–100 ms. Prolonged saccades may indicate cerebellar or brainstem pathology.',
  },
  avg_peak_velocity: {
    label: 'Peak Velocity',
    unit: 'px/s',
    format: v => v.toFixed(0),
    color: () => null,
    hint: 'Peak speed. Should scale linearly with amplitude (see Main Sequence).',
  },
  avg_gain: {
    label: 'Avg Gain',
    unit: '',
    format: v => v.toFixed(2),
    // Normal: 0.85-1.15   Hypometric (PD): <0.75   Hypermetric: >1.2
    color: v => v == null ? null : (v >= 0.85 && v <= 1.15) ? 'success' : (v >= 0.7 && v <= 1.25) ? 'warning' : 'danger',
    hint: 'Saccade accuracy. Normal: 0.85–1.15. Consistently low (<0.75) = hypometric — key Parkinson\'s sign.',
  },
  main_sequence_ratio: {
    label: 'Main Sequence',
    unit: 'v/a',
    format: v => v.toFixed(1),
    color: () => null,
    hint: 'Peak velocity ÷ amplitude ratio. Should be consistent across saccades.',
  },
  antisaccade_error_rate: {
    label: 'Anti-sacc. Errors',
    unit: '%',
    format: v => `${(v * 100).toFixed(0)}`,
    // Normal: <15%   Elevated (frontal dysfunction): >25%
    color: v => v == null ? null : v <= 0.15 ? 'success' : v <= 0.25 ? 'warning' : 'danger',
    hint: 'Errors (looking toward target) during anti-saccade test. >25% suggests frontal/prefrontal dysfunction.',
  },
};

export default function StatsPanel({ stats, deviation }) {
  if (!stats) return null;

  return (
    <div className="card">
      <div className="card-title">Session Statistics</div>
      <div className="stats-grid">
        <StatItem
          label="Saccades"
          value={stats.total_saccades || 0}
          hint="Total saccades detected this session."
        />
        {Object.entries(RANGES).map(([key, cfg]) => {
          const v = stats[key];
          if (v == null) return null;
          return (
            <StatItem
              key={key}
              label={cfg.label}
              value={cfg.format(v)}
              unit={cfg.unit}
              colorClass={cfg.color(v)}
              hint={cfg.hint}
            />
          );
        })}
        {stats.total_fixations > 0 && (
          <StatItem
            label="Fixations"
            value={stats.total_fixations}
            hint={`${stats.avg_fixation_ms != null ? `Avg ${stats.avg_fixation_ms} ms` : ''}`}
          />
        )}
      </div>

      {deviation && deviation.deviation_detected && (
        <div className="deviation-alert">
          <strong style={{ color: 'var(--warning)' }}>Baseline Deviation Detected</strong>
          <ul style={{ marginTop: 6, paddingLeft: 16 }}>
            {deviation.deviations.map((d, i) => (
              <li key={i} style={{ marginBottom: 2 }}>
                <strong>{d.metric}</strong>: {d.current}{' '}
                <span style={{ color: 'var(--text-secondary)' }}>
                  ({d.direction} than baseline {d.baseline_mean}, z={d.z_score})
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StatItem({ label, value, unit, colorClass, hint }) {
  const valueColor = colorClass === 'success'
    ? 'var(--success)'
    : colorClass === 'warning'
      ? 'var(--warning)'
      : colorClass === 'danger'
        ? 'var(--danger)'
        : 'var(--accent-light)';

  return (
    <div className="stat-item" title={hint || ''}>
      <div className="stat-value" style={{ color: valueColor }}>
        {value}
        {unit && <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 2 }}>{unit}</span>}
      </div>
      <div className="stat-label">{label}</div>
      {colorClass && (
        <div className={`stat-range-dot ${colorClass}`} />
      )}
    </div>
  );
}
