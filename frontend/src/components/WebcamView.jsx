import React, { useRef, useEffect } from 'react';

export default function WebcamView({ videoRef, videoElRef, canvasRef, faceDetected, quality, irisRef }) {
  const overlayRef = useRef(null);

  useEffect(() => {
    let rafId;
    let lastW = 0, lastH = 0;

    const loop = () => {
      const overlay = overlayRef.current;
      if (!overlay) { rafId = requestAnimationFrame(loop); return; }

      // Size the canvas to match the displayed container (CSS 100%x100%).
      const w = overlay.offsetWidth;
      const h = overlay.offsetHeight;
      if (!w || !h) { rafId = requestAnimationFrame(loop); return; }

      if (w !== lastW || h !== lastH) {
        overlay.width  = w;
        overlay.height = h;
        lastW = w; lastH = h;
      }

      const ctx = overlay.getContext('2d');
      ctx.clearRect(0, 0, w, h);

      const iris = irisRef?.current;
      if (iris) {
        const eyes = [
          { x: iris.left_x,  y: iris.left_y  },
          { x: iris.right_x, y: iris.right_y },
        ];

        // Iris radius: ~3% of frame height, clamped to reasonable px range.
        const r = Math.max(8, Math.min(22, h * 0.032));

        // Connecting line between iris centres (gaze baseline).
        const lx = iris.left_x  * w, ly = iris.left_y  * h;
        const rx = iris.right_x * w, ry = iris.right_y * h;
        ctx.beginPath();
        ctx.moveTo(lx, ly);
        ctx.lineTo(rx, ry);
        ctx.strokeStyle = 'rgba(0,255,136,0.18)';
        ctx.lineWidth = 1;
        ctx.stroke();

        eyes.forEach(({ x, y }) => {
          const cx = x * w;
          const cy = y * h;

          // Outer iris ring.
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(0,255,136,0.90)';
          ctx.lineWidth = 2;
          ctx.stroke();

          // Mid ring (limbus).
          ctx.beginPath();
          ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(0,255,136,0.40)';
          ctx.lineWidth = 1;
          ctx.stroke();

          // Pupil dot.
          ctx.beginPath();
          ctx.arc(cx, cy, r * 0.22, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(0,255,136,0.95)';
          ctx.fill();

          // Crosshair lines.
          ctx.strokeStyle = 'rgba(0,255,136,0.45)';
          ctx.lineWidth = 1;
          const g = r * 1.6;
          ctx.beginPath();
          ctx.moveTo(cx - g, cy); ctx.lineTo(cx - r * 1.05, cy);
          ctx.moveTo(cx + r * 1.05, cy); ctx.lineTo(cx + g, cy);
          ctx.moveTo(cx, cy - g); ctx.lineTo(cx, cy - r * 1.05);
          ctx.moveTo(cx, cy + r * 1.05); ctx.lineTo(cx, cy + g);
          ctx.stroke();
        });
      }

      rafId = requestAnimationFrame(loop);
    };

    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, [irisRef]);

  return (
    <div className="card">
      <div className="card-title">Camera Feed</div>
      <div className="webcam-container">
        <video ref={videoRef} playsInline muted />
        {/* Hidden canvas used only for frame capture */}
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        {/* Live iris tracking overlay */}
        <canvas ref={overlayRef} className="iris-overlay-canvas" />
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
