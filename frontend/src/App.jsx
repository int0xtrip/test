import React, { useState, useRef, useCallback, useEffect } from 'react';
import useWebcam from './hooks/useWebcam';
import useWebSocket from './hooks/useWebSocket';
import WebcamView from './components/WebcamView';
import GazePlot from './components/GazePlot';
import StatsPanel from './components/StatsPanel';
import SaccadeList from './components/SaccadeList';
import GuidedTest from './components/GuidedTest';
import MainSequencePlot from './components/MainSequencePlot';

const FRAME_INTERVAL = 33; // ~30 fps
const SCREEN_W = window.screen.width || 1920;
const SCREEN_H = window.screen.height || 1080;

export default function App() {
  const webcam = useWebcam();
  const ws = useWebSocket();

  const [mode, setMode] = useState('passive'); // 'passive' | 'guided'
  const [tracking, setTracking] = useState(false);
  const [quality, setQuality] = useState(null);
  const [faceDetected, setFaceDetected] = useState(false);
  const [gazeHistory, setGazeHistory] = useState([]);
  const [saccades, setSaccades] = useState([]);
  const [fixations, setFixations] = useState([]);
  const [stats, setStats] = useState(null);
  const [sessionSummary, setSessionSummary] = useState(null);
  const [calibrated, setCalibrated] = useState(false);

  const frameLoopRef = useRef(null);
  const gazeRef = useRef({ x: null, y: null });

  const handleMessage = useCallback((data) => {
    if (data.type === 'session_ended') {
      setSessionSummary(data);
      return;
    }
    if (data.type === 'calibrated') {
      setCalibrated(true);
      return;
    }
    if (data.error) return;

    if (data.quality) setQuality(data.quality);
    setFaceDetected(!!data.face_detected);

    if (data.gaze) {
      gazeRef.current = { x: data.gaze.screen_x, y: data.gaze.screen_y };
      setGazeHistory(prev => {
        const next = [...prev, {
          t: data.timestamp,
          x: data.gaze.screen_x,
          y: data.gaze.screen_y,
        }];
        return next.length > 120 ? next.slice(-120) : next;
      });
    }

    if (data.saccade) {
      setSaccades(prev => {
        const next = [...prev, data.saccade];
        return next.length > 50 ? next.slice(-50) : next;
      });
    }

    if (data.fixation) {
      setFixations(prev => {
        const next = [...prev, data.fixation];
        return next.length > 80 ? next.slice(-80) : next;
      });
    }

    if (data.stats) setStats(data.stats);
  }, []);

  useEffect(() => {
    ws.setOnMessage(handleMessage);
  }, [ws, handleMessage]);

  const startTracking = useCallback(async () => {
    await webcam.start();
    await ws.connect();
    setTracking(true);
    setSessionSummary(null);
    setGazeHistory([]);
    setSaccades([]);
    setFixations([]);
    setStats(null);
    setCalibrated(false);
  }, [webcam, ws]);

  const stopTracking = useCallback(() => {
    clearInterval(frameLoopRef.current);
    ws.disconnect();
    webcam.stop();
    setTracking(false);
  }, [webcam, ws]);

  useEffect(() => {
    if (!tracking || !ws.connected) return;
    frameLoopRef.current = setInterval(() => {
      const frame = webcam.captureFrame();
      if (frame) ws.sendFrame(frame.base64, frame.width, frame.height);
    }, FRAME_INTERVAL);
    return () => clearInterval(frameLoopRef.current);
  }, [tracking, ws.connected, webcam, ws]);

  const handleCalibrate = useCallback(() => {
    ws.sendMessage({ type: 'calibrate_center' });
  }, [ws]);

  // Pro-saccade: no expected direction. Anti-saccade: expected_direction sent.
  const handleStimulus = useCallback((tx, ty, expectedDirection) => {
    ws.sendMessage({
      type: 'stimulus',
      target_x: tx,
      target_y: ty,
      ...(expectedDirection ? { expected_direction: expectedDirection } : {}),
    });
  }, [ws]);

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1>Oculometry</h1>
          <span className="app-subtitle">Eye Movement Analysis</span>
        </div>
        <div className="header-right">
          <span className="privacy-badge">All processing local</span>
          {tracking ? (
            <button className="btn btn-danger" onClick={stopTracking}>Stop</button>
          ) : (
            <button className="btn btn-primary" onClick={startTracking}>Start Tracking</button>
          )}
        </div>
      </header>

      <div className="main-content">
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <WebcamView
            videoRef={webcam.videoRef}
            canvasRef={webcam.canvasRef}
            faceDetected={faceDetected}
            quality={quality}
          />

          {webcam.error && (
            <div className="card" style={{ color: 'var(--danger)' }}>{webcam.error}</div>
          )}

          {tracking && (
            <div className="card">
              <div className="card-title">Controls</div>
              <div className="mode-selector">
                <button
                  className={`mode-btn${mode === 'passive' ? ' active' : ''}`}
                  onClick={() => setMode('passive')}
                >Passive</button>
                <button
                  className={`mode-btn${mode === 'guided' ? ' active' : ''}`}
                  onClick={() => setMode('guided')}
                >Guided Test</button>
              </div>

              {!calibrated && faceDetected && (
                <div style={{ marginBottom: 12 }}>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Look at the center of your screen, then click calibrate.
                  </p>
                  <button className="btn btn-secondary" onClick={handleCalibrate}>
                    Quick Calibrate
                  </button>
                </div>
              )}
              {calibrated && (
                <p style={{ fontSize: 12, color: 'var(--success)' }}>
                  Calibrated ✓
                </p>
              )}
            </div>
          )}

          {tracking && mode === 'guided' && (
            <GuidedTest
              onStimulus={handleStimulus}
              screenW={SCREEN_W}
              screenH={SCREEN_H}
              gazeX={gazeRef.current.x}
              gazeY={gazeRef.current.y}
            />
          )}
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <GazePlot gazeHistory={gazeHistory} saccades={saccades} fixations={fixations} />
          <MainSequencePlot saccades={saccades} />
          <StatsPanel stats={stats} deviation={sessionSummary?.deviation} />
          <SaccadeList saccades={saccades} />
        </div>
      </div>

      {/* Session summary modal */}
      {sessionSummary && (
        <div className="modal-overlay">
          <div className="card modal-card">
            <div className="card-title">Session Complete</div>
            <p style={{ fontSize: 13, marginBottom: 12, color: 'var(--text-secondary)' }}>
              Duration: {sessionSummary.duration_seconds}s
            </p>
            <StatsPanel stats={sessionSummary.stats} deviation={sessionSummary.deviation} />
            <button
              className="btn btn-primary"
              style={{ marginTop: 16, width: '100%' }}
              onClick={() => setSessionSummary(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
