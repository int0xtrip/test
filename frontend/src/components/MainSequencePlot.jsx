import React, { useRef, useEffect } from 'react';

/**
 * Main sequence scatter plot: peak velocity vs amplitude for each saccade.
 *
 * Healthy adults show a roughly linear relationship (the "main sequence").
 * Hypometric saccades (Parkinson's) cluster below the reference line.
 * Very slow saccades (internuclear ophthalmoplegia, ALS) deviate rightward.
 */
export default function MainSequencePlot({ saccades }) {
  const canvasRef = useRef(null);

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

    if (!saccades || saccades.length === 0) {
      ctx.fillStyle = '#9aa0a6';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No saccades yet — main sequence will appear here', w / 2, h / 2);
      return;
    }

    const pad = { top: 20, bottom: 36, left: 52, right: 16 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    const amps = saccades.map(s => s.amplitude);
    const vels = saccades.map(s => s.peak_velocity);

    const aMax = Math.max(...amps) * 1.15;
    const vMax = Math.max(...vels) * 1.15;

    const mx = a => pad.left + (a / aMax) * plotW;
    const my = v => pad.top + plotH - (v / vMax) * plotH;

    // Reference line (average main sequence slope from this session)
    if (saccades.length >= 3) {
      const slope = vels.reduce((a, b) => a + b, 0) / amps.reduce((a, b) => a + b, 0);
      ctx.strokeStyle = 'rgba(251,191,36,0.35)';
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(mx(0), my(0));
      ctx.lineTo(mx(aMax), my(slope * aMax));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Axes
    ctx.strokeStyle = '#2d3148';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left, pad.top + plotH);
    ctx.lineTo(pad.left + plotW, pad.top + plotH);
    ctx.stroke();

    // Axis labels
    ctx.fillStyle = '#9aa0a6';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Amplitude (px)', pad.left + plotW / 2, h - 4);
    ctx.save();
    ctx.translate(12, pad.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Peak velocity (px/s)', 0, 0);
    ctx.restore();

    // Tick values
    ctx.textAlign = 'right';
    ctx.font = '9px sans-serif';
    for (let i = 0; i <= 4; i++) {
      const v = (vMax / 4) * i;
      const y = my(v);
      ctx.fillText(Math.round(v), pad.left - 4, y + 3);
      ctx.strokeStyle = '#2d3148';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left - 3, y);
      ctx.stroke();
    }
    ctx.textAlign = 'center';
    for (let i = 0; i <= 4; i++) {
      const a = (aMax / 4) * i;
      const x = mx(a);
      ctx.fillText(Math.round(a), x, pad.top + plotH + 12);
    }

    // Data points — colour by direction
    const dirColor = { left: '#f87171', right: '#34d399', up: '#60a5fa', down: '#fbbf24' };
    for (const s of saccades) {
      const x = mx(s.amplitude);
      const y = my(s.peak_velocity);
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = dirColor[s.direction] || '#8b83ff';
      ctx.globalAlpha = 0.8;
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // Legend
    const legendItems = [
      ['left', '#f87171'],
      ['right', '#34d399'],
      ['up', '#60a5fa'],
      ['down', '#fbbf24'],
    ];
    let lx = pad.left;
    ctx.font = '9px sans-serif';
    for (const [label, color] of legendItems) {
      ctx.beginPath();
      ctx.arc(lx + 4, pad.top + 8, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.fillStyle = '#9aa0a6';
      ctx.textAlign = 'left';
      ctx.fillText(label, lx + 10, pad.top + 12);
      lx += 38;
    }
  }, [saccades]);

  return (
    <div className="card">
      <div className="card-title">Main Sequence</div>
      <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>
        Peak velocity vs amplitude — should be roughly linear. Low velocity for amplitude = hypometric (Parkinson's marker).
      </p>
      <div className="chart-container">
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      </div>
    </div>
  );
}
