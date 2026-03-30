import React, { useState, useRef, useCallback, useEffect } from 'react';
import useWebcam from './hooks/useWebcam';
import useWebSocket from './hooks/useWebSocket';
import WebcamView from './components/WebcamView';
import GazePlot from './components/GazePlot';
import StatsPanel from './components/StatsPanel';
import SaccadeList from './components/SaccadeList';
import GuidedTest from './components/GuidedTest';
import MainSequencePlot from './components/MainSequencePlot';
import ConfidenceMeter from './components/ConfidenceMeter';
import GuidancePanel from './components/GuidancePanel';
import CalibrationFlow from './components/CalibrationFlow';

const FRAME_INTERVAL = 33;
const SCREEN_W = window.screen.width  || 1920;
const SCREEN_H = window.screen.height || 1080;

export default function App() {
  const webcam = useWebcam();
  const ws = useWebSocket();

  const [mode,           setMode]           = useState('passive');
  const [tracking,       setTracking]       = useState(false);
  const [quality,        setQuality]        = useState(null);
  const [faceDetected,   setFaceDetected]   = useState(false);
  const [gazeHistory,    setGazeHistory]    = useState([]);
  const [saccades,       setSaccades]       = useState([]);
  const [fixations,      setFixations]      = useState([]);
  const [stats,          setStats]          = useState(null);
  const [sessionSummary, setSessionSummary] = useState(null);
  const [calibrated,     setCalibrated]     = useState(false);
  const [calibrating,    setCalibrating]    = useState(false);
  const [calResult,      setCalResult]      = useState(null);
  const [confidence,     setConfidence]     = useState(null);

  const frameLoopRef = useRef(null);
  const gazeRef      = useRef({ x: null, y: null });
  // raw (pre-calibration) gaze for calibration point capture
  const rawGazeRef   = useRef({ x: null, y: null });

  // ─── WebSocket message handler ───────────────────────────────────────────

  const handleMessage = useCallback((data) => {
    if (data.type === 'session_ended') {
      setSessionSummary(data);
      return;
    }
    if (data.type === 'calibrated') {
      setCalibrated(true);
      return;
    }
    if (data.type === 'calibration_complete') {
      setCalibrated(true);
      setCalResult({ accuracy_px: data.accuracy_px });
      return;
    }
    if (data.error) return;

    if (data.quality)    setQuality(data.quality);
    setFaceDetected(!!data.face_detected);
    if (data.tracking_confidence != null) setConfidence(data.tracking_confidence);

    if (data.gaze) {
      rawGazeRef.current = { x: data.gaze.raw_x, y: data.gaze.raw_y };
      gazeRef.current    = { x: data.gaze.screen_x, y: data.gaze.screen_y };
      setGazeHistory(prev => {
        const next = [...prev, { t: data.timestamp, x: data.gaze.screen_x, y: data.gaze.screen_y }];
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

  useEffect(() => { ws.setOnMessage(handleMessage); }, [ws, handleMessage]);

  // ─── Session lifecycle ────────────────────────────────────────────────────

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
    setCalResult(null);
    setConfidence(null);
  }, [webcam, ws]);

  const stopTracking = useCallback(() => {
    clearInterval(frameLoopRef.current);
    ws.disconnect();
    webcam.stop();
    setTracking(false);
    setCalibrating(false);
  }, [webcam, ws]);

  useEffect(() => {
    if (!tracking || !ws.connected) return;
    frameLoopRef.current = setInterval(() => {
      const frame = webcam.captureFrame();
      if (frame) ws.sendFrame(frame.base64, frame.width, frame.height);
    }, FRAME_INTERVAL);
    return () => clearInterval(frameLoopRef.current);
  }, [tracking, ws.connected, webcam, ws]);

  // ─── Calibration ─────────────────────────────────────────────────────────

  const handleQuickCalibrate = useCallback(() => {
    ws.sendMessage({ type: 'calibrate_center' });
  }, [ws]);

  const handleCapturePoint = useCallback((rx, ry, sx, sy) => {
    ws.sendMessage({ type: 'calibrate_point', raw_x: rx, raw_y: ry, screen_x: sx, screen_y: sy });
  }, [ws]);

  const handleApplyCalibration = useCallback(() => {
    ws.sendMessage({ type: 'calibrate_apply' });
  }, [ws]);

  const openCalibration = useCallback(() => {
    setCalResult(null);
    setCalibrating(true);
  }, []);

  const closeCalibration = useCallback(() => {
    setCalibrating(false);
  }, []);

  // ─── Guided test ──────────────────────────────────────────────────────────

  const handleStimulus = useCallback((tx, ty, expectedDirection) => {
    ws.sendMessage({
      type: 'stimulus',
      target_x: tx,
      target_y: ty,
      ...(expectedDirection ? { expected_direction: expectedDirection } : {}),
    });
  }, [ws]);

  // ─── Export ───────────────────────────────────────────────────────────────

  const handleExport = useCallback((summary) => {
    const s = summary || sessionSummary;
    if (!s) return;

    // CSV of saccades
    const rows = (s.recent_saccades || saccades).map(sc => [
      sc.direction, sc.amplitude?.toFixed(1), sc.duration_ms?.toFixed(0),
      sc.peak_velocity?.toFixed(0), sc.latency_ms?.toFixed(0) ?? '',
      sc.gain?.toFixed(3) ?? '', sc.is_correct ?? '', sc.confidence?.toFixed(0) ?? '',
      sc.angle_deg?.toFixed(1) ?? '',
    ].join(','));
    const csv = [
      'direction,amplitude_px,duration_ms,peak_velocity_pxs,latency_ms,gain,is_correct,confidence,angle_deg',
      ...rows,
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `oculometry_session_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [sessionSummary, saccades]);

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <h1>Oculometry</h1>
          <span className="app-subtitle">Neurodegenerative Disease Eye Screening</span>
        </div>
        <div className="header-center">
          {tracking && <ConfidenceMeter confidence={confidence} />}
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

      {/* ── Welcome screen (idle) ── */}
      {!tracking && (
        <div className="welcome-screen">
          <div className="welcome-card">
            <h2 className="welcome-title">Eye Movement Analysis</h2>
            <p className="welcome-desc">
              This tool uses your webcam to measure saccadic eye movements — rapid
              gaze shifts that reveal how your brain processes visual information.
              Patterns in latency, velocity, and accuracy can be early indicators
              of neurodegenerative conditions such as Parkinson's and Alzheimer's disease.
            </p>
            <div className="setup-checklist">
              <div className="setup-title">Before starting:</div>
              <div className="setup-item">
                <span className="setup-bullet">1</span>
                Sit <strong>50–70 cm</strong> from your screen in a well-lit room
              </div>
              <div className="setup-item">
                <span className="setup-bullet">2</span>
                Make sure your face is <strong>evenly lit</strong> (avoid backlight)
              </div>
              <div className="setup-item">
                <span className="setup-bullet">3</span>
                Run the <strong>5-point calibration</strong> once connected for best accuracy
              </div>
              <div className="setup-item">
                <span className="setup-bullet">4</span>
                Try both <strong>Passive</strong> (natural) and <strong>Guided</strong> test modes
              </div>
            </div>
            <button className="btn btn-primary welcome-btn" onClick={startTracking}>
              Connect Camera &amp; Start
            </button>
          </div>
        </div>
      )}

      {/* ── Main UI (tracking) ── */}
      {tracking && (
        <div className="main-content">
          {/* Left column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <WebcamView
              videoRef={webcam.videoRef}
              canvasRef={webcam.canvasRef}
              faceDetected={faceDetected}
              quality={quality}
            />

            <GuidancePanel
              quality={quality}
              faceDetected={faceDetected}
              calibrated={calibrated}
              confidence={confidence}
              tracking={tracking}
            />

            {webcam.error && (
              <div className="card" style={{ color: 'var(--danger)', fontSize: 13 }}>
                {webcam.error}
              </div>
            )}

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

              <div className="calibration-row">
                {!calibrated ? (
                  <>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={openCalibration}
                      disabled={!faceDetected}
                    >
                      5-Point Calibrate
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={handleQuickCalibrate}
                      disabled={!faceDetected}
                      title="Look at screen center, then click"
                    >
                      Quick (center-only)
                    </button>
                  </>
                ) : (
                  <div className="calibration-status">
                    <span className="cal-ok-dot" />
                    <span>
                      Calibrated
                      {calResult?.accuracy_px != null && ` — ${calResult.accuracy_px} px accuracy`}
                    </span>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={openCalibration}
                      style={{ marginLeft: 'auto' }}
                    >
                      Recalibrate
                    </button>
                  </div>
                )}
              </div>
            </div>

            {mode === 'guided' && (
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <GazePlot gazeHistory={gazeHistory} saccades={saccades} fixations={fixations} />
            <MainSequencePlot saccades={saccades} />
            <StatsPanel stats={stats} deviation={sessionSummary?.deviation} />
            <SaccadeList saccades={saccades} />
          </div>
        </div>
      )}

      {/* ── Calibration overlay ── */}
      {calibrating && (
        <CalibrationFlow
          rawGazeRef={rawGazeRef}
          onCapture={handleCapturePoint}
          onApply={handleApplyCalibration}
          onClose={closeCalibration}
          result={calResult}
        />
      )}

      {/* ── Session summary modal ── */}
      {sessionSummary && !calibrating && (
        <div className="modal-overlay">
          <div className="card modal-card">
            <div className="card-title">Session Complete</div>
            <p style={{ fontSize: 13, marginBottom: 12, color: 'var(--text-secondary)' }}>
              Duration: {sessionSummary.duration_seconds}s &nbsp;·&nbsp;
              {sessionSummary.stats?.total_saccades ?? 0} saccades detected
            </p>
            <StatsPanel stats={sessionSummary.stats} deviation={sessionSummary.deviation} />
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button className="btn btn-primary" style={{ flex: 1 }}
                onClick={() => setSessionSummary(null)}>Close</button>
              <button className="btn btn-secondary"
                onClick={() => handleExport(sessionSummary)}>Export CSV</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
