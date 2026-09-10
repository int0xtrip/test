"""Gaze estimation with adaptive calibration and head-pose compensation."""

import numpy as np
from collections import deque


class AdaptiveCalibration:
    """Lightweight adaptive calibration that improves over time.

    Instead of a fixed multi-point calibration, this system:
    1. Starts with a quick center-alignment (look at center of screen)
    2. Continuously refines mapping using edge-of-screen natural gaze patterns
    3. Maintains a running affine transform from raw gaze to screen coordinates
    """

    def __init__(self, screen_w: int = 1920, screen_h: int = 1080):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Affine transform params: screen = scale * raw + offset
        self.scale_x = float(screen_w)
        self.scale_y = float(screen_h)
        self.offset_x = 0.0
        self.offset_y = 0.0

        # Center reference (set during quick alignment)
        self.center_raw = None
        self.calibrated = False

        # Continuous calibration buffer
        self._buffer = deque(maxlen=500)
        self._correction_count = 0

    def set_center(self, raw_x: float, raw_y: float):
        """Quick alignment: user looks at screen center."""
        self.center_raw = (raw_x, raw_y)
        self.offset_x = self.screen_w / 2 - raw_x * self.scale_x
        self.offset_y = self.screen_h / 2 - raw_y * self.scale_y
        self.calibrated = True

    def raw_to_screen(self, raw_x: float, raw_y: float) -> tuple:
        """Convert raw gaze (0-1) to screen coordinates."""
        sx = raw_x * self.scale_x + self.offset_x
        sy = raw_y * self.scale_y + self.offset_y
        sx = max(0, min(self.screen_w, sx))
        sy = max(0, min(self.screen_h, sy))
        return (sx, sy)

    def add_correction_point(self, raw_x: float, raw_y: float, expected_x: float, expected_y: float):
        """Add a known gaze-to-screen correspondence for continuous refinement."""
        self._buffer.append((raw_x, raw_y, expected_x, expected_y))
        self._correction_count += 1

        if self._correction_count % 20 == 0 and len(self._buffer) >= 4:
            self._refit()

    def _refit(self):
        """Refit the affine transform from accumulated correction points."""
        data = np.array(list(self._buffer))
        raw = data[:, :2]
        expected = data[:, 2:]

        ones = np.ones((len(raw), 1))
        X = np.hstack([raw, ones])

        try:
            params_x, _, _, _ = np.linalg.lstsq(X, expected[:, 0], rcond=None)
            params_y, _, _, _ = np.linalg.lstsq(X, expected[:, 1], rcond=None)
            self.scale_x = params_x[0]
            self.offset_x = params_x[2]
            self.scale_y = params_y[1]
            self.offset_y = params_y[2]
        except np.linalg.LinAlgError:
            pass


class GazeEstimator:
    """Combines iris tracking with head pose compensation for robust gaze estimation."""

    def __init__(self, screen_w: int = 1920, screen_h: int = 1080):
        self.calibration = AdaptiveCalibration(screen_w, screen_h)
        self.screen_w = screen_w
        self.screen_h = screen_h

        self.head_yaw_weight = 0.3
        self.head_pitch_weight = 0.3

        self._smooth_x = None
        self._smooth_y = None
        self._alpha = 0.4

    def estimate(self, detection: dict) -> dict:
        """Estimate screen gaze position from face detection result."""
        raw_x = detection["gaze_x"]
        raw_y = detection["gaze_y"]

        compensated_x = raw_x - detection["head_yaw"] * self.head_yaw_weight / 90.0
        compensated_y = raw_y - detection["head_pitch"] * self.head_pitch_weight / 90.0

        compensated_x = np.clip(compensated_x, 0, 1)
        compensated_y = np.clip(compensated_y, 0, 1)

        screen_x, screen_y = self.calibration.raw_to_screen(compensated_x, compensated_y)

        if self._smooth_x is None:
            self._smooth_x = screen_x
            self._smooth_y = screen_y
        else:
            self._smooth_x = self._alpha * screen_x + (1 - self._alpha) * self._smooth_x
            self._smooth_y = self._alpha * screen_y + (1 - self._alpha) * self._smooth_y

        return {
            "raw_x": float(raw_x),
            "raw_y": float(raw_y),
            "compensated_x": float(compensated_x),
            "compensated_y": float(compensated_y),
            "screen_x": float(self._smooth_x),
            "screen_y": float(self._smooth_y),
            "head_yaw": detection["head_yaw"],
            "head_pitch": detection["head_pitch"],
            "head_roll": detection["head_roll"],
        }

    def set_smoothing(self, alpha: float):
        """Set smoothing factor. 0.1=very smooth, 1.0=no smoothing."""
        self._alpha = np.clip(alpha, 0.05, 1.0)
