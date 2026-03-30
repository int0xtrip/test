import React from 'react';

export default function SaccadeList({ saccades }) {
  if (!saccades || saccades.length === 0) {
    return (
      <div className="card">
        <div className="card-title">Detected Saccades</div>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          No saccades detected yet. Move your eyes around or start a guided test.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-title">Detected Saccades ({saccades.length})</div>
      <div className="saccade-list">
        {[...saccades].reverse().map((s, i) => (
          <div key={i} className="saccade-item">
            <span style={{ color: dirColor(s.direction), minWidth: 36 }}>
              {dirArrow(s.direction)}
            </span>
            <span>{s.amplitude.toFixed(0)}<span style={{ color: 'var(--text-secondary)', fontSize: 10 }}>px</span></span>
            <span>{s.duration_ms.toFixed(0)}<span style={{ color: 'var(--text-secondary)', fontSize: 10 }}>ms</span></span>
            <span>{s.peak_velocity.toFixed(0)}<span style={{ color: 'var(--text-secondary)', fontSize: 10 }}>px/s</span></span>
            {s.latency_ms != null && (
              <span style={{ color: latencyColor(s.latency_ms) }}>
                {s.latency_ms.toFixed(0)}<span style={{ color: 'var(--text-secondary)', fontSize: 10 }}>ms</span>
              </span>
            )}
            {s.gain != null && (
              <span style={{ color: gainColor(s.gain) }}>
                g{s.gain.toFixed(2)}
              </span>
            )}
            {s.is_correct != null && (
              <span style={{ color: s.is_correct ? 'var(--success)' : 'var(--danger)', fontWeight: 700 }}>
                {s.is_correct ? '✓' : '✗'}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function dirColor(dir) {
  switch (dir) {
    case 'left':  return '#f87171';
    case 'right': return '#34d399';
    case 'up':    return '#60a5fa';
    case 'down':  return '#fbbf24';
    default:      return 'var(--text-primary)';
  }
}

function dirArrow(dir) {
  switch (dir) {
    case 'left':  return '←';
    case 'right': return '→';
    case 'up':    return '↑';
    case 'down':  return '↓';
    default:      return dir;
  }
}

function latencyColor(ms) {
  if (ms < 80 || ms > 350) return 'var(--danger)';
  if (ms > 250) return 'var(--warning)';
  return 'var(--accent-light)';
}

function gainColor(g) {
  if (g >= 0.85 && g <= 1.15) return 'var(--success)';
  if (g >= 0.7 && g <= 1.25) return 'var(--warning)';
  return 'var(--danger)';
}
