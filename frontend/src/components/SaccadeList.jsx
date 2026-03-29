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
            <span style={{ color: dirColor(s.direction) }}>
              {s.direction}
            </span>
            <span>{s.amplitude.toFixed(1)}px</span>
            <span>{s.duration_ms.toFixed(0)}ms</span>
            <span>{s.peak_velocity.toFixed(0)}px/s</span>
            {s.latency_ms != null && (
              <span style={{ color: 'var(--accent-light)' }}>
                lat: {s.latency_ms.toFixed(0)}ms
              </span>
            )}
            {s.gain != null && (
              <span>g: {s.gain.toFixed(2)}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function dirColor(dir) {
  switch (dir) {
    case 'left': return '#f87171';
    case 'right': return '#34d399';
    case 'up': return '#60a5fa';
    case 'down': return '#fbbf24';
    default: return 'var(--text-primary)';
  }
}
