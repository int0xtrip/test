import React, { useRef, useEffect, useState } from 'react';

const TABS = ['Traces', 'Scan Path'];

export default function GazePlot({ gazeHistory, saccades, fixations }) {
  const canvasRef = useRef(null);
  const [tab, setTab] = useState('Traces');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;

    ctx.fillStyle = '#0f1117';
    ctx.fillRect(0, 0, w, h);

    if (tab === 'Traces') drawTraces(ctx, w, h, gazeHistory, saccades);
    else drawScanPath(ctx, w, h, gazeHistory, saccades, fixations);
  }, [gazeHistory, saccades, fixations, tab]);

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>Gaze Visualisation</div>
        <div className="tab-selector">
          {TABS.map(t => (
            <button
              key={t}
              className={`tab-btn${tab === t ? ' active' : ''}`}
              onClick={() => setTab(t)}
            >{t}</button>
          ))}
        </div>
      </div>
      <div className="chart-container">
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      </div>
    </div>
  );
}

// ─── Traces view: X (blue) and Y (orange) over time ──────────────────────────

function drawTraces(ctx, w, h, gazeHistory, saccades) {
  if (!gazeHistory || gazeHistory.length < 2) {
    placeholder(ctx, w, h, 'Waiting for gaze data…');
    return;
  }

  const n = gazeHistory.length;
  const pad = { top: 16, bottom: 24, left: 48, right: 12 };
  const halfH = (h - pad.top - pad.bottom) / 2;
  const plotW = w - pad.left - pad.right;

  const tMin = gazeHistory[0].t;
  const tMax = gazeHistory[n - 1].t;
  const tRange = Math.max(tMax - tMin, 0.1);

  const xVals = gazeHistory.map(g => g.x);
  const yVals = gazeHistory.map(g => g.y);
  const xMin = Math.min(...xVals), xMax = Math.max(...xVals);
  const yMin = Math.min(...yVals), yMax = Math.max(...yVals);
  const xRange = Math.max(xMax - xMin, 10);
  const yRange = Math.max(yMax - yMin, 10);

  const mapT = t => pad.left + ((t - tMin) / tRange) * plotW;

  // Saccade region highlights (both panels)
  if (saccades) {
    ctx.fillStyle = 'rgba(248,113,113,0.18)';
    for (const s of saccades) {
      if (s.start_time >= tMin && s.start_time <= tMax) {
        const sx = mapT(s.start_time);
        const ex = mapT(s.end_time);
        const sw = Math.max(ex - sx, 2);
        ctx.fillRect(sx, pad.top, sw, halfH * 2);
      }
    }
  }

  // Divider
  const midY = pad.top + halfH;
  ctx.strokeStyle = '#2d3148';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(pad.left, midY);
  ctx.lineTo(w - pad.right, midY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Axes
  ctx.strokeStyle = '#2d3148';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, midY);
  ctx.moveTo(pad.left, midY); ctx.lineTo(pad.left, pad.top + halfH * 2);
  ctx.stroke();

  // Labels
  ctx.fillStyle = '#9aa0a6';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('X', 4, pad.top + 12);
  ctx.fillText('Y', 4, midY + 12);

  ctx.textAlign = 'center';
  ctx.fillText('Time (s)', w / 2, h - 4);

  // X trace (blue)
  drawLine(ctx, gazeHistory, tMin, tRange, plotW, pad.left,
    v => pad.top + halfH - ((v - xMin) / xRange) * (halfH - 4),
    g => g.x, '#6c63ff');

  // Y trace (orange)
  drawLine(ctx, gazeHistory, tMin, tRange, plotW, pad.left,
    v => midY + halfH - 4 - ((v - yMin) / yRange) * (halfH - 4),
    g => g.y, '#fb923c');

  // Legend
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'left';
  dot(ctx, w - 80, pad.top + 10, '#6c63ff'); ctx.fillStyle = '#9aa0a6'; ctx.fillText('Gaze X', w - 72, pad.top + 14);
  dot(ctx, w - 80, midY + 10, '#fb923c');   ctx.fillStyle = '#9aa0a6'; ctx.fillText('Gaze Y', w - 72, midY + 14);
}

function drawLine(ctx, data, tMin, tRange, plotW, padLeft, mapV, getV, color) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  const mapT = t => padLeft + ((t - tMin) / tRange) * plotW;
  ctx.moveTo(mapT(data[0].t), mapV(getV(data[0])));
  for (let i = 1; i < data.length; i++) {
    ctx.lineTo(mapT(data[i].t), mapV(getV(data[i])));
  }
  ctx.stroke();
}

// ─── Scan path view: 2D gaze path ────────────────────────────────────────────

function drawScanPath(ctx, w, h, gazeHistory, saccades, fixations) {
  if (!gazeHistory || gazeHistory.length < 2) {
    placeholder(ctx, w, h, 'Waiting for gaze data…');
    return;
  }

  const pad = 32;
  const plotW = w - pad * 2;
  const plotH = h - pad * 2;

  // Find bounding box of gaze data for auto-scaling
  const xs = gazeHistory.map(g => g.x);
  const ys = gazeHistory.map(g => g.y);
  let xMin = Math.min(...xs), xMax = Math.max(...xs);
  let yMin = Math.min(...ys), yMax = Math.max(...ys);
  const margin = 60;
  xMin -= margin; xMax += margin; yMin -= margin; yMax += margin;
  const xRange = Math.max(xMax - xMin, 1);
  const yRange = Math.max(yMax - yMin, 1);

  const mx = x => pad + ((x - xMin) / xRange) * plotW;
  const my = y => pad + ((y - yMin) / yRange) * plotH;

  // Gaze path (faded trail)
  const n = gazeHistory.length;
  for (let i = 1; i < n; i++) {
    const alpha = 0.15 + 0.55 * (i / n);
    ctx.strokeStyle = `rgba(108,99,255,${alpha})`;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(mx(gazeHistory[i - 1].x), my(gazeHistory[i - 1].y));
    ctx.lineTo(mx(gazeHistory[i].x), my(gazeHistory[i].y));
    ctx.stroke();
  }

  // Fixation circles (size ∝ duration)
  if (fixations && fixations.length > 0) {
    for (const f of fixations) {
      const r = Math.min(3 + f.duration_ms / 80, 22);
      ctx.beginPath();
      ctx.arc(mx(f.centroid_x), my(f.centroid_y), r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(52,211,153,0.25)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(52,211,153,0.7)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  // Current gaze dot
  const last = gazeHistory[n - 1];
  ctx.beginPath();
  ctx.arc(mx(last.x), my(last.y), 5, 0, Math.PI * 2);
  ctx.fillStyle = '#f87171';
  ctx.fill();

  // Legend
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'left';
  dot(ctx, pad, h - 14, '#6c63ff'); ctx.fillStyle = '#9aa0a6'; ctx.fillText('Gaze path', pad + 8, h - 10);
  dot(ctx, pad + 80, h - 14, '#34d399'); ctx.fillStyle = '#9aa0a6'; ctx.fillText('Fixations', pad + 88, h - 10);
  dot(ctx, pad + 158, h - 14, '#f87171'); ctx.fillStyle = '#9aa0a6'; ctx.fillText('Current', pad + 166, h - 10);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function placeholder(ctx, w, h, text) {
  ctx.fillStyle = '#9aa0a6';
  ctx.font = '13px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(text, w / 2, h / 2);
}

function dot(ctx, x, y, color) {
  ctx.beginPath();
  ctx.arc(x, y, 4, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}
