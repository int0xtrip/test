import React from 'react';

export default function WebcamView({ videoRef, canvasRef, faceDetected, quality }) {
  return (
    <div className="card">
      <div className="card-title">Camera Feed</div>
      <div className="webcam-container">
        <video ref={videoRef} playsInline muted />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        <div className={`face-guide ${faceDetected ? 'detected' : ''}`} />
      </div>
      <QualityBar quality={quality} />
    </div>
  );
}

function QualityBar({ quality }) {
  if (!quality) return null;

  const signalColor = quality.signal_quality > 70 ? 'var(--success)' :
    quality.signal_quality > 40 ? 'var(--warning)' : 'var(--danger)';

  return (
    <>
      <div className="quality-bar">
        <QualityIndicator label="Face" ok={quality.face_detected} />
        <QualityIndicator label="Lighting" ok={quality.lighting_ok} warn={!quality.lighting_ok && quality.face_detected} />
        <QualityIndicator label="Position" ok={quality.head_position_ok} />
        <QualityIndicator label={`FPS: ${quality.fps}`} ok={quality.fps_ok} />
        <QualityIndicator label={`Signal: ${quality.signal_quality}%`} ok={quality.signal_quality > 60} warn={quality.signal_quality > 30} />
      </div>
      <div className="signal-meter">
        <div className="signal-meter-fill" style={{
          width: `${quality.signal_quality || 0}%`,
          background: signalColor,
        }} />
      </div>
      {!quality.face_detected && (
        <p style={{ fontSize: 12, color: 'var(--warning)', marginTop: 8 }}>
          Position your face within the oval guide
        </p>
      )}
      {quality.face_detected && !quality.head_position_ok && (
        <p style={{ fontSize: 12, color: 'var(--warning)', marginTop: 8 }}>
          {quality.head_msg}
        </p>
      )}
      {quality.face_detected && !quality.lighting_ok && (
        <p style={{ fontSize: 12, color: 'var(--warning)', marginTop: 8 }}>
          {quality.lighting_msg}
        </p>
      )}
    </>
  );
}

function QualityIndicator({ label, ok, warn }) {
  const cls = ok ? 'ok' : warn ? 'warn' : '';
  return (
    <div className="quality-indicator">
      <div className={`quality-dot ${cls}`} />
      <span>{label}</span>
    </div>
  );
}
