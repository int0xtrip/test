import React from 'react';

// Clinical reference ranges — calibrated to published webcam-oculometry data
// (Sledzianowski et al. 2022; Nij Bijvank et al. 2018; Fischer & Ramsperger 1984)
//
// LATENCY is the most reliable parameter at 30 fps (temporal error ~16 ms).
// VELOCITY is severely attenuated at 30 fps — treat as relative indicator only.
// Healthy adults (horizontal ~8° RS):  latency 190–200 ms upper limit
// PD stage 1 threshold:                >260 ms
// PD stage 2 threshold:                >308 ms
const RANGES = {
  avg_latency_ms: {
    label: 'Avg Latency',
    unit: 'ms',
    format: v => `${Math.round(v)}`,
    // <80 ms: anticipatory (invalid)
    // 80–250 ms: normal healthy range
    // 250–260 ms: borderline
    // >260 ms: PD range (stage 1 threshold)
    // >308 ms: advanced PD range
    color: v => v == null ? null
      : v < 80    ? 'danger'
      : v <= 250  ? 'success'
      : v <= 260  ? 'warning'
      : 'danger',
    hint: 'PRIMARY METRIC. Normal healthy: 80–250 ms. >260 ms = Parkinson\'s stage 1 threshold. >308 ms = stage 2. Error ~16 ms at 30 fps.',
  },
  avg_gain: {
    label: 'Avg Gain',
    unit: '',
    format: v => v.toFixed(2),
    // Paper results: healthy webcam ~1.12–1.16 (slight overshoot), reference ~0.98
    // Hypometric (<0.80): consistent undershoot — Parkinson's marker
    // Hypermetric (>1.30): cerebellar
    color: v => v == null ? null
      : (v >= 0.80 && v <= 1.30) ? 'success'
      : (v >= 0.70 && v <= 1.40) ? 'warning'
      : 'danger',
    hint: 'Saccade accuracy (amplitude / target distance). Webcam norm ~0.98–1.16. Consistently <0.80 suggests hypometric saccades (Parkinson\'s sign).',
  },
  avg_amplitude: {
    label: 'Avg Amplitude',
    unit: 'px',
    format: v => v.toFixed(0),
    color: () => null,
    hint: 'Saccade size in pixels. Context-dependent on screen size and viewing distance.',
  },
  avg_duration_ms: {
    label: 'Avg Duration',
    unit: 'ms',
    format: v => `${Math.round(v)}`,
    color: v => v == null ? null : v <= 120 ? 'success' : v <= 180 ? 'warning' : 'danger',
    hint: 'Normal: 30–120 ms for ~8° saccades. Prolonged duration may reflect slow saccades.',
  },
  avg_peak_velocity: {
    label: 'Peak Velocity',
    unit: 'px/s',
    format: v => v.toFixed(0),
    color: () => null,
    hint: 'UNRELIABLE at <30 fps — severely attenuated by temporal sampling error. Use latency and gain for clinical assessment.',
  },
  main_sequence_ratio: {
    label: 'Main Sequence',
    unit: 'v/a',
    format: v => v.toFixed(1),
    color: () => null,
    hint: 'Peak velocity ÷ amplitude. Should be consistent across trials. Relative metric — do not compare absolute values across devices.',
  },
  antisaccade_error_rate: {
    label: 'Anti-sacc. Errors',
    unit: '%',
    format: v => `${(v * 100).toFixed(0)}`,
    // Normal healthy: <20%   Cognitive impairment marker: >25%
    color: v => v == null ? null : v <= 0.20 ? 'success' : v <= 0.30 ? 'warning' : 'danger',
    hint: 'Errors during anti-saccade (looking toward target instead of away). >25% suggests prefrontal/frontal dysfunction — Alzheimer\'s and PD marker.',
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
