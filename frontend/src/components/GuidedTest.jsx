import React, { useState, useRef, useEffect, useCallback } from 'react';

// 10 reflexive saccade trials — horizontal only, alternating left/right
// Targets at 15% and 85% of screen width (~8° visual angle at normal viewing distance)
const PROSACCADE_TRIALS = [
  { x: 0.85, y: 0.5 }, { x: 0.15, y: 0.5 },
  { x: 0.85, y: 0.5 }, { x: 0.15, y: 0.5 },
  { x: 0.15, y: 0.5 }, { x: 0.85, y: 0.5 },
  { x: 0.15, y: 0.5 }, { x: 0.85, y: 0.5 },
  { x: 0.85, y: 0.5 }, { x: 0.15, y: 0.5 },
];

// Anti-saccade: target appears, look to the OPPOSITE side
const ANTISACCADE_TRIALS = [
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left'  },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left'  },
  { x: 0.85, y: 0.5, expected: 'left'  },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left'  },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left'  },
];

// Step model (Δt = 0): fixation disappears at exact moment target appears.
// This maximises latency differences between healthy and PD subjects.
// Fixation duration: uniform random 1000–2000 ms (paper-specified range).
const TARGET_MS = 1200;  // target visible window (saccade expected within this)
const fixationMs = () => Math.floor(Math.random() * 1000) + 1000;  // 1000–2000 ms

export default function GuidedTest({ onStimulus, screenW, screenH, gazeX, gazeY }) {
  const [testMode, setTestMode] = useState('prosaccade');
  const [running,  setRunning]  = useState(false);
  const [phase,    setPhase]    = useState('idle');   // idle | fixation | target
  const [step,     setStep]     = useState(0);
  const [target,   setTarget]   = useState(null);

  const timerRef   = useRef(null);
  const runningRef = useRef(false);

  const trials = testMode === 'antisaccade' ? ANTISACCADE_TRIALS : PROSACCADE_TRIALS;

  const clearTimer = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
  };

  const stopTest = useCallback(() => {
    clearTimer();
    runningRef.current = false;
    setRunning(false);
    setPhase('idle');
    setTarget(null);
  }, []);

  // Step-model trial: fixation → (simultaneous: fixation off + target on) → next trial
  const runTrial = useCallback((idx) => {
    if (!runningRef.current || idx >= trials.length) {
      runningRef.current = false;
      setRunning(false);
      setPhase('idle');
      setTarget(null);
      return;
    }

    setStep(idx);

    // Phase 1: show fixation cross only (no target)
    setPhase('fixation');
    setTarget(null);

    timerRef.current = setTimeout(() => {
      if (!runningRef.current) return;

      // Phase 2 (Δt=0): fixation cross disappears, target appears simultaneously
      const trial = trials[idx];
      setPhase('target');
      setTarget(trial);

      // Notify backend of stimulus onset — triggers marker-driven search window
      if (onStimulus) {
        onStimulus(
          trial.x * screenW,
          trial.y * screenH,
          trial.expected || null,
        );
      }

      // After target window, advance to next trial
      timerRef.current = setTimeout(() => {
        if (!runningRef.current) return;
        runTrial(idx + 1);
      }, TARGET_MS);

    }, fixationMs());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testMode, onStimulus, screenW, screenH]);

  const startTest = useCallback(() => {
    runningRef.current = true;
    setRunning(true);
    setStep(0);
    runTrial(0);
  }, [runTrial]);

  useEffect(() => () => clearTimer(), []);

  const gazeInArea = gazeX != null && gazeY != null;
  const gazePctX   = gazeInArea ? (gazeX / screenW) * 100 : null;
  const gazePctY   = gazeInArea ? (gazeY / screenH) * 100 : null;

  return (
    <div className="card">
      <div className="card-title">Reflexive Saccade Test</div>

      {/* Mode selector */}
      {!running && (
        <div className="mode-selector" style={{ marginBottom: 12 }}>
          <button
            className={`mode-btn${testMode === 'prosaccade' ? ' active' : ''}`}
            onClick={() => setTestMode('prosaccade')}
          >
            Pro-saccade
          </button>
          <button
            className={`mode-btn${testMode === 'antisaccade' ? ' active' : ''}`}
            onClick={() => setTestMode('antisaccade')}
          >
            Anti-saccade
          </button>
        </div>
      )}

      {/* Instructions */}
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 10 }}>
        {testMode === 'antisaccade'
          ? 'When the dot appears, look to the OPPOSITE side. Keep head still.'
          : 'When the dot appears, look at it immediately. Keep head still.'}
      </p>
      {testMode === 'antisaccade' && (
        <div className="antisaccade-hint">
          Anti-saccade errors (looking toward the dot) reflect frontal/prefrontal function.
          Elevated error rates correlate with cognitive impairment.
        </div>
      )}

      {/* Controls */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        {!running ? (
          <button className="btn btn-primary" onClick={startTest}>Start Test</button>
        ) : (
          <button className="btn btn-danger" onClick={stopTest}>Stop</button>
        )}
        {running && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', alignSelf: 'center' }}>
            Trial {step + 1} / {trials.length}
            {phase === 'fixation' && ' — fixate center cross'}
            {phase === 'target' && (testMode === 'antisaccade' ? ' — LOOK OPPOSITE!' : ' — look at dot!')}
          </span>
        )}
      </div>

      {/* Test area */}
      <div className="test-area">
        {/* Fixation cross — shown only during fixation phase (step model: disappears with target) */}
        {phase === 'fixation' && (
          <div className="fixation-cross">
            <div className="fixation-h" />
            <div className="fixation-v" />
          </div>
        )}

        {/* Target dot */}
        {target && phase === 'target' && (
          <div
            className="test-target"
            style={{ left: `${target.x * 100}%`, top: `${target.y * 100}%` }}
          />
        )}

        {/* Anti-saccade direction arrow */}
        {target && phase === 'target' && testMode === 'antisaccade' && (
          <div
            className="antisaccade-arrow"
            style={{
              left: target.x < 0.5 ? '75%' : '25%',
              top: `${target.y * 100}%`,
            }}
          >
            {target.x < 0.5 ? '→' : '←'}
          </div>
        )}

        {/* Gaze cursor */}
        {gazePctX != null && (
          <div
            className="gaze-cursor"
            style={{ left: `${gazePctX}%`, top: `${gazePctY}%` }}
          />
        )}
      </div>
    </div>
  );
}
