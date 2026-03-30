import React, { useState, useRef, useEffect, useCallback } from 'react';

// Pro-saccade: look AT the target
const PROSACCADE_POSITIONS = [
  { x: 0.15, y: 0.5 }, { x: 0.85, y: 0.5 },
  { x: 0.15, y: 0.5 }, { x: 0.85, y: 0.5 },
  { x: 0.15, y: 0.5 }, { x: 0.85, y: 0.5 },
  { x: 0.5, y: 0.15 }, { x: 0.5, y: 0.85 },
  { x: 0.5, y: 0.15 }, { x: 0.5, y: 0.85 },
  { x: 0.2, y: 0.2 }, { x: 0.8, y: 0.8 },
  { x: 0.8, y: 0.2 }, { x: 0.2, y: 0.8 },
  { x: 0.3, y: 0.5 }, { x: 0.7, y: 0.5 },
  { x: 0.5, y: 0.3 }, { x: 0.5, y: 0.7 },
  { x: 0.2, y: 0.5 }, { x: 0.8, y: 0.5 },
];

// Anti-saccade: target appears on one side, look to the OPPOSITE side
const ANTISACCADE_POSITIONS = [
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left' },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left' },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left' },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left' },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left' },
  { x: 0.15, y: 0.5, expected: 'right' },
  { x: 0.85, y: 0.5, expected: 'left' },
];

// Gap paradigm timing (ms)
const FIXATION_MS = 1000;   // show fixation cross
const GAP_MS = 200;          // blank interval — increases latency sensitivity
const TARGET_MS = 1200;      // show target (user should saccade within this window)

// Random jitter to prevent anticipatory saccades
const jitter = () => Math.floor(Math.random() * 400); // 0-400ms extra fixation

export default function GuidedTest({ onStimulus, screenW, screenH, gazeX, gazeY }) {
  const [testMode, setTestMode] = useState('prosaccade');
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState('idle'); // idle | fixation | gap | target
  const [step, setStep] = useState(0);
  const [target, setTarget] = useState(null);

  const stepRef = useRef(0);
  const timerRef = useRef(null);
  const runningRef = useRef(false);

  const positions = testMode === 'antisaccade' ? ANTISACCADE_POSITIONS : PROSACCADE_POSITIONS;

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const stopTest = useCallback(() => {
    clearTimer();
    runningRef.current = false;
    setRunning(false);
    setPhase('idle');
    setTarget(null);
  }, []);

  // Each trial: fixation cross → gap → target → (advance)
  const runTrial = useCallback((idx) => {
    if (!runningRef.current || idx >= positions.length) {
      runningRef.current = false;
      setRunning(false);
      setPhase('idle');
      setTarget(null);
      return;
    }

    stepRef.current = idx;
    setStep(idx);

    // Phase 1: fixation cross
    setPhase('fixation');
    setTarget(null);

    timerRef.current = setTimeout(() => {
      if (!runningRef.current) return;

      // Phase 2: gap (blank screen — improves latency sensitivity, PD marker)
      setPhase('gap');

      timerRef.current = setTimeout(() => {
        if (!runningRef.current) return;

        // Phase 3: target appears
        const pos = positions[idx];
        setPhase('target');
        setTarget(pos);

        // Notify backend: send stimulus with expected_direction for anti-saccade
        if (onStimulus) {
          onStimulus(
            pos.x * screenW,
            pos.y * screenH,
            pos.expected || null,
          );
        }

        timerRef.current = setTimeout(() => {
          if (!runningRef.current) return;
          runTrial(idx + 1);
        }, TARGET_MS);

      }, GAP_MS);

    }, FIXATION_MS + jitter());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testMode, onStimulus, screenW, screenH]);

  const startTest = useCallback(() => {
    runningRef.current = true;
    setRunning(true);
    setStep(0);
    runTrial(0);
  }, [runTrial]);

  useEffect(() => {
    return () => clearTimer();
  }, []);

  // Map screen gaze to test-area coordinates
  const gazeInArea = gazeX != null && gazeY != null;
  const gazePctX = gazeInArea ? (gazeX / screenW) * 100 : null;
  const gazePctY = gazeInArea ? (gazeY / screenH) * 100 : null;

  return (
    <div className="card">
      <div className="card-title">Guided Saccade Test</div>

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
          ? 'Look to the OPPOSITE side from the purple dot.'
          : 'Follow the purple dot with your eyes. Keep your head still.'}
      </p>
      {testMode === 'antisaccade' && (
        <div className="antisaccade-hint">
          Anti-saccade measures frontal/prefrontal function.
          Errors (looking toward the dot) are clinically significant.
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
            Trial {step + 1} / {positions.length}
            {phase === 'fixation' && ' — fixate center'}
            {phase === 'gap' && ' — gap…'}
            {phase === 'target' && (testMode === 'antisaccade' ? ' — LOOK AWAY!' : ' — follow dot!')}
          </span>
        )}
      </div>

      {/* Test area */}
      <div className="test-area">
        {/* Fixation cross */}
        {(phase === 'fixation' || phase === 'gap') && (
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

        {/* Anti-saccade direction arrow hint */}
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
