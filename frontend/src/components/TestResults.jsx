import React from 'react';

/**
 * Post-test results screen — shows clinical interpretation of the 10-trial
 * reflexive saccade test against published PD/healthy thresholds.
 *
 * Key references (Sledzianowski et al. 2022; Fischer & Ramsperger 1984):
 *   Healthy latency upper limit : ~250 ms
 *   PD stage-1 threshold        : >260 ms
 *   PD stage-2 threshold        : >308 ms
 *   Temporal error at 30 fps    : ~16.6 ms  (Anderson et al. 2010)
 */
export default function TestResults({ stats, saccades, onClose, onExport }) {
  if (!stats) return null;

  const lat   = stats.avg_latency_ms;
  const gain  = stats.avg_gain;
  const asErr = stats.antisaccade_error_rate;
  const total = stats.total_saccades;

  const latResult = interpretLatency(lat);
  const gainResult = interpretGain(gain);
  const asResult  = interpretAntiSaccade(asErr);

  const overallLevel = worstLevel([latResult?.level, gainResult?.level, asResult?.level]);

  return (
    <div className="modal-overlay">
      <div className="card modal-card results-card">
        <div className="card-title">Test Results</div>
        <p className="results-meta">
          {total} saccade{total !== 1 ? 's' : ''} detected
          {stats.avg_duration_ms ? ` · avg duration ${Math.round(stats.avg_duration_ms)} ms` : ''}
        </p>

        {/* Primary metric: latency */}
        <div className={`result-block result-${latResult?.level || 'neutral'}`}>
          <div className="result-label">Saccadic Latency (primary metric)</div>
          <div className="result-value">
            {lat != null ? `${Math.round(lat)} ms` : '—'}
          </div>
          <div className="result-interp">{latResult?.text || 'Not enough data'}</div>
          <div className="result-ref">
            Normal healthy: 80–250 ms &nbsp;·&nbsp; PD stage 1: &gt;260 ms &nbsp;·&nbsp; PD stage 2: &gt;308 ms
          </div>
        </div>

        {/* Gain */}
        {gain != null && (
          <div className={`result-block result-${gainResult?.level || 'neutral'}`}>
            <div className="result-label">Saccade Gain (accuracy)</div>
            <div className="result-value">{gain.toFixed(2)}</div>
            <div className="result-interp">{gainResult?.text}</div>
            <div className="result-ref">Normal range: 0.80–1.30 &nbsp;·&nbsp; Hypometric (&lt;0.80) = PD sign</div>
          </div>
        )}

        {/* Anti-saccade error rate */}
        {asErr != null && (
          <div className={`result-block result-${asResult?.level || 'neutral'}`}>
            <div className="result-label">Anti-saccade Error Rate</div>
            <div className="result-value">{(asErr * 100).toFixed(0)}%</div>
            <div className="result-interp">{asResult?.text}</div>
            <div className="result-ref">Normal: &lt;20% &nbsp;·&nbsp; Prefrontal/cognitive impairment sign: &gt;25%</div>
          </div>
        )}

        {/* Overall interpretation */}
        <div className={`overall-interp overall-${overallLevel}`}>
          {overallText(overallLevel, lat)}
        </div>

        {/* Sampling error note */}
        <div className="results-note">
          Note: at 30 fps, temporal sampling error is ~17 ms — latency values are reliable
          for PD screening (PD vs healthy gap is 60–110 ms). Velocity measurements are not
          reliable at this frame rate. This tool is for screening only — not a clinical diagnosis.
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={onClose}>
            Close
          </button>
          <button className="btn btn-secondary" onClick={onExport}>
            Export CSV
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Interpretation helpers ────────────────────────────────────────────────────

function interpretLatency(lat) {
  if (lat == null) return null;
  if (lat < 80)   return { level: 'warn',    text: 'Anticipatory saccades detected — may indicate test validity issues. Results should be interpreted cautiously.' };
  if (lat <= 250) return { level: 'normal',  text: 'Within normal healthy range.' };
  if (lat <= 260) return { level: 'warn',    text: 'Borderline — slightly above healthy upper limit. Sampling error (~17 ms) may account for this.' };
  if (lat <= 308) return { level: 'concern', text: 'Above healthy range. Consistent with published PD stage-1 latency threshold (>260 ms).' };
  return           { level: 'concern', text: 'Significantly elevated. Consistent with PD stage-2 latency threshold (>308 ms). Specialist review recommended.' };
}

function interpretGain(gain) {
  if (gain == null) return null;
  if (gain < 0.70) return { level: 'concern', text: 'Severely hypometric — persistent undershoot. Strong Parkinson\'s motor sign.' };
  if (gain < 0.80) return { level: 'concern', text: 'Hypometric saccades — consistent undershoot. May indicate bradykinesia (Parkinson\'s).' };
  if (gain > 1.40) return { level: 'warn',    text: 'Hypermetric — consistent overshoot. May indicate cerebellar involvement.' };
  if (gain > 1.30) return { level: 'warn',    text: 'Mildly hypermetric — slight overshoot. Webcam systems typically show gain ~1.1–1.2.' };
  return            { level: 'normal',  text: 'Within normal range for webcam-based measurement.' };
}

function interpretAntiSaccade(rate) {
  if (rate == null) return null;
  if (rate <= 0.20) return { level: 'normal',  text: 'Normal inhibitory control — frontal lobe function appears intact.' };
  if (rate <= 0.30) return { level: 'warn',    text: 'Mildly elevated error rate — borderline inhibitory control.' };
  return             { level: 'concern', text: 'Elevated error rate. Associated with prefrontal dysfunction, cognitive impairment, Alzheimer\'s and Parkinson\'s disease.' };
}

function worstLevel(levels) {
  if (levels.includes('concern')) return 'concern';
  if (levels.includes('warn'))    return 'warn';
  if (levels.includes('normal'))  return 'normal';
  return 'neutral';
}

function overallText(level, lat) {
  switch (level) {
    case 'normal':
      return 'All measured parameters are within normal range. No indicators of neurodegenerative changes detected in this session.';
    case 'warn':
      return `Results show borderline values (latency ${lat != null ? Math.round(lat) + ' ms' : '—'}). Consider repeating the test on multiple occasions before drawing conclusions. Environmental factors (lighting, camera FPS, head position) affect accuracy.`;
    case 'concern':
      return `One or more parameters fall outside normal range. This is a screening result only — not a diagnosis. Please consult a neurologist or specialist for a full clinical assessment if concerned.`;
    default:
      return 'Not enough trials completed to generate a reliable interpretation.';
  }
}
