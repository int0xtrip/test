"""Environment quality assessment: lighting, face position, FPS, signal quality.

Paper-aligned quality metrics (Sledzianowski et al. 2022):
  - SNR   = |mean(gaze_x)| / std(gaze_x)  ≤ 3.5  (lower = noisier)
  - Periodogram average ≥ 0.02  (higher = more signal power)
  - Mean luminance > 120
  - Dominant colour RGB > 90
  - FPS > 23
  - Head distance 55–80 cm (estimated from inter-ocular distance)
"""

import numpy as np
from collections import deque
import time

try:
    from scipy.signal import periodogram as scipy_periodogram
    _SCIPY_OK = True
except ImportError:
    _SCIPY_OK = False


class QualityChecker:

    HEAD_YAW_MAX        = 25.0
    HEAD_PITCH_MAX      = 20.0
    EAR_BLINK_THRESHOLD = 0.20
    MIN_FPS             = 23          # paper threshold
    LUMINANCE_MIN       = 120         # paper: mean RGB > 120
    DOMINANT_RGB_MIN    = 90          # paper: avg dominant RGB > 90
    SNR_MAX             = 3.5         # paper: SNR ≤ 3.5
    PERIODOGRAM_MIN     = 0.02        # paper: periodogram avg ≥ 0.02
    IPD_MM              = 63.0        # average human inter-pupillary distance
    DIST_MIN_CM         = 55
    DIST_MAX_CM         = 80

    def __init__(self):
        self._fps_times    = deque(maxlen=60)
        self._lum_history  = deque(maxlen=30)
        self._sq_history   = deque(maxlen=60)
        # Rolling gaze-x buffer for signal quality metrics (paper uses calibration
        # signal; here we accumulate continuously and recompute periodically)
        self._gaze_x_buf: deque[float] = deque(maxlen=150)   # ~5 s at 30 fps
        self._signal_metrics_cache: dict = {}
        self._signal_metrics_ts: float = 0.0

    # ── Main entry ──────────────────────────────────────────────────────────────

    def check(self, frame_rgb: np.ndarray, detection: dict | None,
              gaze_x: float | None = None) -> dict:
        now = time.time()
        self._fps_times.append(now)

        fps = ((len(self._fps_times) - 1) /
               max(self._fps_times[-1] - self._fps_times[0], 1e-6)
               if len(self._fps_times) >= 2 else 0.0)

        # ── Luminance (paper: mean RGB > 120) ─────────────────────────────────
        luminance = float(np.mean(frame_rgb))
        self._lum_history.append(luminance)
        avg_lum = float(np.mean(self._lum_history))

        # Approximate dominant colour as mean of brightest quintile of pixels
        gray = frame_rgb.mean(axis=2)
        q80  = float(np.percentile(gray, 80))
        dominant_rgb = float(np.mean(frame_rgb[gray >= q80]))

        lighting_ok = avg_lum > self.LUMINANCE_MIN and dominant_rgb > self.DOMINANT_RGB_MIN
        if avg_lum <= self.LUMINANCE_MIN:
            lighting_msg = "Too dark — increase room lighting"
        elif avg_lum >= 230:
            lighting_msg = "Too bright — avoid direct light behind camera"
        else:
            lighting_msg = "Good"

        # ── Face / head pose ──────────────────────────────────────────────────
        face_ok  = detection is not None
        head_ok  = True
        head_msg = "Good"
        blink    = False
        dist_info: dict = {}

        if detection:
            yaw   = abs(detection.get("head_yaw",   0) or 0)
            pitch = abs(detection.get("head_pitch", 0) or 0)
            if yaw > self.HEAD_YAW_MAX:
                head_ok  = False
                head_msg = "Turn head to face camera"
            elif pitch > self.HEAD_PITCH_MAX:
                head_ok  = False
                head_msg = "Level your head (tilt)"

            avg_ear = (detection["left_ear"] + detection["right_ear"]) / 2.0
            blink   = avg_ear < self.EAR_BLINK_THRESHOLD

            dist_info = self._estimate_distance(detection, frame_rgb.shape[1])

        # ── Gaze signal quality (paper SNR + periodogram) ─────────────────────
        if gaze_x is not None:
            self._gaze_x_buf.append(gaze_x)

        # Recompute signal metrics at most every 2 s to avoid overhead
        if now - self._signal_metrics_ts > 2.0 and len(self._gaze_x_buf) >= 30:
            self._signal_metrics_cache = self._compute_signal_metrics()
            self._signal_metrics_ts = now

        sm = self._signal_metrics_cache

        # ── Composite signal quality score (0-100) ────────────────────────────
        sq = self._composite_score(face_ok, lighting_ok, head_ok, fps,
                                   detection, sm)
        self._sq_history.append(sq)

        distance_ok = dist_info.get("distance_ok", True)

        return {
            "fps":              round(fps, 1),
            "fps_ok":           fps >= self.MIN_FPS,
            "luminance":        round(avg_lum, 1),
            "dominant_rgb":     round(dominant_rgb, 1),
            "lighting_ok":      lighting_ok,
            "lighting_msg":     lighting_msg,
            "face_detected":    face_ok,
            "head_position_ok": head_ok,
            "head_msg":         head_msg,
            "blink_detected":   blink,
            "distance_cm":      dist_info.get("est_cm"),
            "distance_ok":      distance_ok,
            "distance_msg":     dist_info.get("distance_msg", ""),
            "signal_snr":       sm.get("snr"),
            "signal_snr_ok":    sm.get("snr_ok"),
            "periodogram_avg":  sm.get("periodogram_avg"),
            "periodogram_ok":   sm.get("periodogram_ok"),
            "signal_quality":   round(sq, 1),
            "signal_quality_avg": round(float(np.mean(self._sq_history)), 1),
            "overall_ok":       (face_ok and lighting_ok and head_ok
                                 and fps >= self.MIN_FPS and distance_ok),
        }

    # ── Paper signal metrics ───────────────────────────────────────────────────

    def _compute_signal_metrics(self) -> dict:
        arr = np.array(self._gaze_x_buf, dtype=float)

        # SNR = |mean| / std  (paper definition).  Lower = noisier.
        std = float(np.std(arr))
        if std < 1e-6:
            snr = 99.0   # perfectly still — excellent
        else:
            snr = float(abs(np.mean(arr))) / std

        snr_ok = snr <= self.SNR_MAX

        # Periodogram (boxcar window, density scaling, constant detrend)
        if _SCIPY_OK and len(arr) >= 8:
            try:
                _, psd = scipy_periodogram(arr, window='boxcar',
                                           scaling='density', detrend='constant')
                period_avg = float(np.mean(psd))
            except Exception:
                period_avg = 0.0
        else:
            period_avg = 0.0

        period_ok = period_avg >= self.PERIODOGRAM_MIN

        return {
            "snr":            round(snr, 3),
            "snr_ok":         snr_ok,
            "periodogram_avg": round(period_avg, 5),
            "periodogram_ok": period_ok,
        }

    # ── Head distance estimation ───────────────────────────────────────────────

    def _estimate_distance(self, detection: dict, frame_w: int) -> dict:
        try:
            left  = np.array(detection["left_eye_center"][:2])
            right = np.array(detection["right_eye_center"][:2])
            iod_px = float(np.linalg.norm(right - left))
        except Exception:
            return {"distance_ok": True, "distance_msg": "", "est_cm": None}

        if iod_px < 1:
            return {"distance_ok": True, "distance_msg": "", "est_cm": None}

        # focal_approx ≈ frame_w  (standard for ~90° diagonal FOV webcams)
        est_mm = self.IPD_MM * float(frame_w) / iod_px
        est_cm = int(round(est_mm / 10.0))

        if est_cm < 40:
            msg = "Way too close — move back to 55–80 cm"
            ok  = False
        elif est_cm < self.DIST_MIN_CM:
            msg = f"Too close (~{est_cm} cm) — move back"
            ok  = False
        elif est_cm > 120:
            msg = "Way too far — move closer to 55–80 cm"
            ok  = False
        elif est_cm > self.DIST_MAX_CM:
            msg = f"Too far (~{est_cm} cm) — move closer"
            ok  = False
        else:
            msg = f"Good distance (~{est_cm} cm)"
            ok  = True

        return {"distance_ok": ok, "distance_msg": msg, "est_cm": est_cm}

    # ── Composite score ───────────────────────────────────────────────────────

    def _composite_score(self, face_ok, lighting_ok, head_ok, fps,
                         detection, sm) -> float:
        if not face_ok:
            return 0.0
        score = 30.0
        score += 20.0 if lighting_ok else 5.0
        score += 15.0 if head_ok     else 0.0
        score += min(fps / self.MIN_FPS, 1.0) * 15.0
        if detection:
            avg_ear = (detection["left_ear"] + detection["right_ear"]) / 2.0
            score  += 10.0 if avg_ear > 0.25 else (5.0 if avg_ear > 0.15 else 0.0)
        if sm.get("snr_ok"):
            score += 5.0
        if sm.get("periodogram_ok"):
            score += 5.0
        return min(score, 100.0)
