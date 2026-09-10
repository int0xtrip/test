import React, { useState, useRef, useEffect, useCallback } from 'react';

const TEST_POSITIONS = [
  // Horizontal saccade test: alternating left-right
  { x: 0.2, y: 0.5 }, { x: 0.8, y: 0.5 },
  { x: 0.2, y: 0.5 }, { x: 0.8, y: 0.5 },
  { x: 0.2, y: 0.5 }, { x: 0.8, y: 0.5 },
  // Vertical
  { x: 0.5, y: 0.2 }, { x: 0.5, y: 0.8 },
  { x: 0.5, y: 0.2 }, { x: 0.5, y: 0.8 },
  // Diagonal
  { x: 0.2, y: 0.2 }, { x: 0.8, y: 0.8 },
  { x: 0.8, y: 0.2 }, { x: 0.2, y: 0.8 },
  // Random
  { x: 0.3, y: 0.3 }, { x: 0.7, y: 0.6 },
  { x: 0.5, y: 0.2 }, { x: 0.4, y: 0.7 },
  { x: 0.8, y: 0.4 }, { x: 0.2, y: 0.6 },
];

const STIMULUS_INTERVAL_MS = 1500;

export default function GuidedTest({ onStimulus, screenW, screenH, gazeX, gazeY }) {
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [target, setTarget] = useState(null);
  const timerRef = useRef(null);
  const areaRef = useRef(null);

  const startTest = useCallback(() => {
    setRunning(true);
    setStep(0);
    showTarget(0);
  }, []);

  const stopTest = useCallback(() => {
    setRunning(false);
    clearTimeout(timerRef.current);
    setTarget(null);
  }, []);

  const showTarget = useCallback((idx) => {
    if (idx >= TEST_POSITIONS.length) {
      setRunning(false);
      setTarget(null);
      return;
    }

    const pos = TEST_POSITIONS[idx];
    setTarget(pos);
    setStep(idx);

    // Notify backend of stimulus
    if (onStimulus) {
      onStimulus(pos.x * screenW, pos.y * screenH);
    }

    timerRef.current = setTimeout(() => {
      showTarget(idx + 1);
    }, STIMULUS_INTERVAL_MS);
  }, [onStimulus, screenW, screenH]);

  useEffect(() => {
    return () => clearTimeout(timerRef.current);
  }, []);

  return (
    <div className="card">
      <div className="card-title">Guided Saccade Test</div>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
        Follow the target dot with your eyes as it moves. Keep your head still.
      </p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {!running ? (
          <button className="btn btn-primary" onClick={startTest}>Start Test</button>
        ) : (
          <button className="btn btn-danger" onClick={stopTest}>Stop Test</button>
        )}
        {running && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', alignSelf: 'center' }}>
            Step {step + 1} / {TEST_POSITIONS.length}
          </span>
        )}
      </div>

      <div className="test-area" ref={areaRef}>
        {target && (
          <div className="test-target" style={{
            left: `${target.x * 100}%`,
            top: `${target.y * 100}%`,
          }} />
        )}
        {gazeX != null && gazeY != null && (
          <div className="gaze-cursor" style={{
            left: `${(gazeX / screenW) * 100}%`,
            top: `${(gazeY / screenH) * 100}%`,
          }} />
        )}
      </div>
    </div>
  );
}
