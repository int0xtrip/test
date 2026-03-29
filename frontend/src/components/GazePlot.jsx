import React, { useRef, useEffect } from 'react';

export default function GazePlot({ gazeHistory, saccades }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    const w = rect.width;
    const h = rect.height;

    // Clear
    ctx.fillStyle = '#0f1117';
    ctx.fillRect(0, 0, w, h);

    if (gazeHistory.length < 2) {
      ctx.fillStyle = '#9aa0a6';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for gaze data...', w / 2, h / 2);
      return;
    }

    const n = gazeHistory.length;
    const padding = { top: 20, bottom: 30, left: 50, right: 20 };
    const plotW = w - padding.left - padding.right;
    const plotH = h - padding.top - padding.bottom;

    // Time axis
    const tMin = gazeHistory[0].t;
    const tMax = gazeHistory[n - 1].t;
    const tRange = Math.max(tMax - tMin, 0.1);

    // Gaze X values
    const xValues = gazeHistory.map(g => g.x);
    const xMin = Math.min(...xValues);
    const xMax = Math.max(...xValues);
    const xRange = Math.max(xMax - xMin, 10);

    // Draw axes
    ctx.strokeStyle = '#2d3148';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, h - padding.bottom);
    ctx.lineTo(w - padding.right, h - padding.bottom);
    ctx.stroke();

    // Axis labels
    ctx.fillStyle = '#9aa0a6';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Time (s)', w / 2, h - 5);
    ctx.save();
    ctx.translate(12, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Gaze X', 0, 0);
    ctx.restore();

    // Helper: map data to canvas
    const mapX = (t) => padding.left + ((t - tMin) / tRange) * plotW;
    const mapY = (x) => padding.top + plotH - ((x - xMin) / xRange) * plotH;

    // Draw gaze trace
    ctx.strokeStyle = '#6c63ff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(mapX(gazeHistory[0].t), mapY(gazeHistory[0].x));
    for (let i = 1; i < n; i++) {
      ctx.lineTo(mapX(gazeHistory[i].t), mapY(gazeHistory[i].x));
    }
    ctx.stroke();

    // Mark saccades
    if (saccades && saccades.length > 0) {
      ctx.fillStyle = 'rgba(248, 113, 113, 0.4)';
      for (const s of saccades) {
        if (s.start_time >= tMin && s.start_time <= tMax) {
          const sx = mapX(s.start_time);
          const ex = mapX(s.end_time);
          const sw = Math.max(ex - sx, 3);
          ctx.fillRect(sx, padding.top, sw, plotH);
        }
      }
    }
  }, [gazeHistory, saccades]);

  return (
    <div className="card">
      <div className="card-title">Gaze X over Time</div>
      <div className="chart-container">
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      </div>
    </div>
  );
}
