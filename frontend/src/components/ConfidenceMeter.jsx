import React from 'react';

/**
 * Real-time tracking confidence meter — always visible in the header.
 * Colour goes red → amber → green as confidence improves.
 */
export default function ConfidenceMeter({ confidence }) {
  if (confidence == null) return null;

  const pct = Math.round(confidence);
  const color = pct >= 70 ? 'var(--success)' : pct >= 45 ? 'var(--warning)' : 'var(--danger)';
  const label = pct >= 70 ? 'Good' : pct >= 45 ? 'Fair' : 'Poor';

  return (
    <div className="confidence-meter">
      <span className="confidence-label">Signal</span>
      <div className="confidence-track">
        <div
          className="confidence-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="confidence-pct" style={{ color }}>{pct}%</span>
      <span className="confidence-qual" style={{ color }}>{label}</span>
    </div>
  );
}
