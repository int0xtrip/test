"""Environment quality assessment: lighting, face position, FPS, signal quality."""

import numpy as np
from collections import deque
import time


class QualityChecker:
    """Checks and reports environment quality for reliable eye tracking."""

    BRIGHTNESS_LOW = 60
    BRIGHTNESS_HIGH = 220
    HEAD_YAW_MAX = 25.0
    HEAD_PITCH_MAX = 20.0
    EAR_BLINK_THRESHOLD = 0.2
    MIN_FPS = 20

    def __init__(self):
        self._fps_times = deque(maxlen=60)
        self._brightness_history = deque(maxlen=30)
        self._signal_quality_history = deque(maxlen=60)

    def check(self, frame_rgb: np.ndarray, detection: dict | None, gaze: dict | None) -> dict:
        """Run all quality checks and return a report."""
        now = time.time()
        self._fps_times.append(now)

        if len(self._fps_times) >= 2:
            elapsed = self._fps_times[-1] - self._fps_times[0]
            fps = (len(self._fps_times) - 1) / max(elapsed, 1e-6)
        else:
            fps = 0.0

        gray = np.mean(frame_rgb)
        self._brightness_history.append(gray)
        avg_brightness = np.mean(self._brightness_history)

        lighting_ok = self.BRIGHTNESS_LOW < avg_brightness < self.BRIGHTNESS_HIGH
        if avg_brightness <= self.BRIGHTNESS_LOW:
            lighting_msg = "Too dark - increase lighting"
        elif avg_brightness >= self.BRIGHTNESS_HIGH:
            lighting_msg = "Too bright - reduce lighting or glare"
        else:
            lighting_msg = "Good"

        face_ok = detection is not None
        head_ok = True
        head_msg = "Good"
        blink = False

        if detection:
            if abs(detection["head_yaw"]) > self.HEAD_YAW_MAX:
                head_ok = False
                head_msg = "Turn head to face camera"
            elif abs(detection["head_pitch"]) > self.HEAD_PITCH_MAX:
                head_ok = False
                head_msg = "Adjust head tilt"

            avg_ear = (detection["left_ear"] + detection["right_ear"]) / 2
            blink = avg_ear < self.EAR_BLINK_THRESHOLD

        signal_score = self._compute_signal_quality(detection, gaze, fps, lighting_ok, head_ok)
        self._signal_quality_history.append(signal_score)

        return {
            "fps": round(fps, 1),
            "fps_ok": fps >= self.MIN_FPS,
            "brightness": round(float(avg_brightness), 1),
            "lighting_ok": lighting_ok,
            "lighting_msg": lighting_msg,
            "face_detected": face_ok,
            "head_position_ok": head_ok,
            "head_msg": head_msg,
            "blink_detected": blink,
            "signal_quality": round(signal_score, 1),
            "signal_quality_avg": round(float(np.mean(self._signal_quality_history)), 1),
            "overall_ok": face_ok and lighting_ok and head_ok and fps >= self.MIN_FPS,
        }

    def _compute_signal_quality(
        self, detection: dict | None, gaze: dict | None, fps: float,
        lighting_ok: bool, head_ok: bool
    ) -> float:
        score = 0.0
        if detection is None:
            return 0.0

        score += 30.0

        if lighting_ok:
            score += 20.0
        else:
            score += 5.0

        if head_ok:
            score += 20.0
        else:
            yaw_penalty = min(abs(detection["head_yaw"]) / 45.0, 1.0) * 15
            score += max(20.0 - yaw_penalty, 0)

        fps_ratio = min(fps / 30.0, 1.0)
        score += fps_ratio * 15.0

        avg_ear = (detection["left_ear"] + detection["right_ear"]) / 2
        if avg_ear > 0.25:
            score += 15.0
        elif avg_ear > 0.15:
            score += 8.0

        return min(score, 100.0)
