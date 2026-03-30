import React, { useState, useRef, useEffect, useCallback } from 'react';

/**
 * Full-screen 5-point calibration wizard.
 *
 * For each of 5 known screen positions the user looks at a dot for ~1.5 s.
 * The current raw gaze is captured automatically then the dot advances.
 * After all 5 captures the parent sends `calibrate_apply` to the backend,
 * which fits a polynomial mapping and returns accuracy in pixels.
 *
 * Props:
 *   rawGazeRef   — React ref whose .current = { x, y } (raw normalised, updated per frame)
 *   onCapture    — (raw_x, raw_y, screen_x, screen_y) → void
 *   onApply      — () → void  (triggers backend fit)
 *   onClose      — () → void
 *   result       — null | { accuracy_px: number }  (set by parent on calibration_complete)
 */

const POINTS = [
  { label: 'Center',       x: 0.5,  y: 0.5  },
  { label: 'Top-left',     x: 0.08, y: 0.08 },
  { label: 'Top-right',    x: 0.92, y: 0.08 },
  { label: 'Bottom-left',  x: 0.08, y: 0.92 },
  { label: 'Bottom-right', x: 0.92, y: 0.92 },
];

const HOLD_MS    = 1500;   // gaze-on-target duration before capture
const FLASH_MS   = 400;    // brief "captured" flash before advancing

export default function CalibrationFlow({ rawGazeRef, onCapture, onApply, onClose, result }) {
  const [phase, setPhase]   = useState('intro');  // intro | running | applying | done
  const [step, setStep]     = useState(0);
  const [progress, setProgress] = useState(0);    // 0-1 fill ring
  const [captured, setCaptured] = useState(false);

  const timerRef    = useRef(null);
  const rafRef      = useRef(null);
  const runningRef  = useRef(false);
  const stepRef     = useRef(0);

  const clearTimers = () => {
    clearTimeout(timerRef.current);
    cancelAnimationFrame(rafRef.current);
  };

  // Animate progress ring for current step
  const animateStep = useCallback((idx) => {
    if (!runningRef.current) return;
    stepRef.current = idx;
    setStep(idx);
    setProgress(0);
    setCaptured(false);

    const start = performance.now();
    const tick = (now) => {
      if (!runningRef.current) return;
      const p = Math.min((now - start) / HOLD_MS, 1);
      setProgress(p);
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        // Capture
        const rg = rawGazeRef.current;
        const pos = POINTS[idx];
        setCaptured(true);
        if (rg && rg.x != null) {
          onCapture(rg.x, rg.y, pos.x * window.screen.width, pos.y * window.screen.height);
        }

        timerRef.current = setTimeout(() => {
          if (!runningRef.current) return;
          if (idx + 1 < POINTS.length) {
            animateStep(idx + 1);
          } else {
            setPhase('applying');
            onApply();
          }
        }, FLASH_MS);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [onCapture, onApply, rawGazeRef]);

  const startCalibration = useCallback(() => {
    runningRef.current = true;
    setPhase('running');
    animateStep(0);
  }, [animateStep]);

  // When parent sets result, move to done
  useEffect(() => {
    if (result != null) setPhase('done');
  }, [result]);

  useEffect(() => {
    return () => { clearTimers(); runningRef.current = false; };
  }, []);

  const currentPoint = POINTS[step] || POINTS[0];

  return (
    <div className="cal-overlay">
      {phase === 'intro' && (
        <div className="cal-intro">
          <h2 className="cal-title">5-Point Calibration</h2>
          <p className="cal-desc">
            A dot will appear at 5 positions on your screen.<br />
            Look directly at each dot and hold your gaze still.<br />
            It captures automatically — no clicking needed.
          </p>
          <ul className="cal-checklist">
            <li>Sit ~50-70 cm from the screen</li>
            <li>Keep your head as still as possible</li>
            <li>Look directly at each dot, not around it</li>
          </ul>
          <div className="cal-actions">
            <button className="btn btn-primary" onClick={startCalibration}>
              Start Calibration
            </button>
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {phase === 'running' && (
        <>
          <div className="cal-hint">
            Look at the dot and hold still — {step + 1} / {POINTS.length}
          </div>
          <div
            className="cal-dot-container"
            style={{
              left:  `${currentPoint.x * 100}%`,
              top:   `${currentPoint.y * 100}%`,
            }}
          >
            <ProgressRing progress={progress} captured={captured} />
          </div>
        </>
      )}

      {phase === 'applying' && (
        <div className="cal-intro">
          <p className="cal-desc">Computing calibration…</p>
        </div>
      )}

      {phase === 'done' && (
        <div className="cal-intro">
          <h2 className="cal-title">Calibration Complete</h2>
          {result?.accuracy_px != null ? (
            <p className="cal-desc">
              Average accuracy:{' '}
              <strong style={{ color: result.accuracy_px < 60 ? 'var(--success)' : result.accuracy_px < 100 ? 'var(--warning)' : 'var(--danger)' }}>
                {result.accuracy_px} px
              </strong>
              {result.accuracy_px < 60 && ' — excellent'}
              {result.accuracy_px >= 60 && result.accuracy_px < 100 && ' — acceptable'}
              {result.accuracy_px >= 100 && ' — consider recalibrating'}
            </p>
          ) : (
            <p className="cal-desc">Calibration applied.</p>
          )}
          <div className="cal-actions">
            <button className="btn btn-primary" onClick={onClose}>Start Tracking</button>
            <button className="btn btn-secondary" onClick={startCalibration}>Recalibrate</button>
          </div>
        </div>
      )}
    </div>
  );
}

function ProgressRing({ progress, captured }) {
  const r = 26;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - progress);
  const color = captured ? 'var(--success)' : 'var(--accent)';

  return (
    <div className="cal-dot-ring">
      <svg width="68" height="68" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="34" cy="34" r={r} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="5" />
        <circle
          cx="34" cy="34" r={r}
          fill="none"
          stroke={color}
          strokeWidth="5"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke 0.15s' }}
        />
      </svg>
      <div className="cal-dot-center" style={{ background: captured ? 'var(--success)' : 'white' }} />
    </div>
  );
}
