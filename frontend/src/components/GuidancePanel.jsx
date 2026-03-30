import React from 'react';

/**
 * Context-aware guidance panel shown below the webcam.
 * Prioritises the most important issue so the user knows what to fix first.
 */
export default function GuidancePanel({ quality, faceDetected, calibrated, confidence, tracking }) {
  if (!tracking) return null;

  const tips = [];

  if (!faceDetected) {
    tips.push({ level: 'error', text: 'No face detected — position yourself in the oval guide' });
  } else {
    if (quality?.lighting_ok === false) {
      tips.push({ level: 'warn', text: quality.lighting_msg || 'Improve lighting — face a bright light source' });
    }
    if (quality?.head_position_ok === false) {
      tips.push({ level: 'warn', text: quality.head_msg || 'Face the camera directly and stay centred' });
    }
    if (quality?.fps_ok === false) {
      tips.push({ level: 'warn', text: `FPS low (${Math.round(quality.fps || 0)}) — close other applications` });
    }
    if (quality?.blink_detected) {
      tips.push({ level: 'info', text: 'Blink detected — data paused momentarily' });
    }
    if (!calibrated) {
      tips.push({ level: 'info', text: 'Run 5-point calibration for best accuracy' });
    } else if (confidence != null && confidence < 50) {
      tips.push({ level: 'warn', text: 'Low confidence — try re-calibrating or improve lighting' });
    } else if (confidence != null && confidence >= 70) {
      tips.push({ level: 'ok', text: 'Tracking is good' });
    }
  }

  // Show only the highest-priority tip to avoid clutter
  const shown = tips.slice(0, 2);
  if (shown.length === 0) return null;

  return (
    <div className="guidance-panel">
      {shown.map((tip, i) => (
        <div key={i} className={`guidance-tip tip-${tip.level}`}>
          <span className="guidance-icon">{levelIcon(tip.level)}</span>
          <span>{tip.text}</span>
        </div>
      ))}
    </div>
  );
}

function levelIcon(level) {
  switch (level) {
    case 'error': return '✕';
    case 'warn':  return '!';
    case 'info':  return 'i';
    case 'ok':    return '✓';
    default:      return '·';
  }
}
