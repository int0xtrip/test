"""Gaze estimation with polynomial calibration and head-pose compensation."""

import numpy as np
from collections import deque


def _poly_features(raw: np.ndarray) -> np.ndarray:
    """Build 2nd-order polynomial feature matrix from Nx2 raw gaze input.

    Features: [1, rx, ry, rx*ry, rx², ry²]
    This gives 6 degrees of freedom — enough for full perspective-like distortion
    while remaining well-conditioned with as few as 4 calibration points.
    """
    rx = raw[:, 0]
    ry = raw[:, 1]
    return np.column_stack([
        np.ones(len(raw)),
        rx, ry,
        rx * ry,
        rx ** 2, ry ** 2,
    ])


class PolynomialCalibration:
    """Multi-point gaze calibration with 2nd-order polynomial mapping.

    Single-point fallback:
        set_center(raw_x, raw_y) — aligns gaze center with screen center.
        Uses a simple affine (scale + offset) transform.

    Multi-point (recommended):
        add_point(raw_x, raw_y, screen_x, screen_y) × N
        fit() — fits polynomial, returns RMS residual in pixels.
        With ≥ 5 well-spread points the transform handles optical distortions
        and off-axis monitor geometry.
    """

    def __init__(self, screen_w: int = 1920, screen_h: int = 1080):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.calibrated = False
        self.accuracy_px: float | None = None

        # Affine fallback (used before any calibration)
        self._scale_x = float(screen_w)
        self._scale_y = float(screen_h)
        self._offset_x = 0.0
        self._offset_y = 0.0

        # Polynomial params (set after multi-point fit)
        self._poly_x: np.ndarray | None = None
        self._poly_y: np.ndarray | None = None

        # Pending calibration points
        self._pending: list[tuple] = []   # [(raw_x, raw_y, sx, sy), ...]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_center(self, raw_x: float, raw_y: float):
        """Quick single-point alignment: user looks at screen center."""
        self._offset_x = self.screen_w / 2.0 - raw_x * self._scale_x
        self._offset_y = self.screen_h / 2.0 - raw_y * self._scale_y
        self.calibrated = True

    def add_point(self, raw_x: float, raw_y: float, screen_x: float, screen_y: float):
        """Stage a calibration correspondence point."""
        self._pending.append((raw_x, raw_y, screen_x, screen_y))

    def fit(self) -> float:
        """Fit polynomial mapping from staged points.

        Returns RMS residual in pixels (lower is better; < 50px is good for
        a webcam-based system).  On failure returns float('inf').
        """
        pts = self._pending[:]
        self._pending = []   # consumed

        if len(pts) < 3:
            return float('inf')

        data = np.array(pts, dtype=float)
        raw = data[:, :2]
        sx = data[:, 2]
        sy = data[:, 3]

        X = _poly_features(raw)
        try:
            px, _, _, _ = np.linalg.lstsq(X, sx, rcond=None)
            py, _, _, _ = np.linalg.lstsq(X, sy, rcond=None)
        except np.linalg.LinAlgError:
            return float('inf')

        pred_x = X @ px
        pred_y = X @ py
        residuals = np.sqrt((pred_x - sx) ** 2 + (pred_y - sy) ** 2)
        accuracy = float(np.mean(residuals))

        self._poly_x = px
        self._poly_y = py
        self.calibrated = True
        self.accuracy_px = round(accuracy, 1)
        return accuracy

    def clear_pending(self):
        """Discard staged points (e.g. if calibration is cancelled)."""
        self._pending = []

    def raw_to_screen(self, raw_x: float, raw_y: float) -> tuple:
        """Map raw normalised gaze (0-1) to screen pixel coordinates."""
        if self._poly_x is not None:
            feat = _poly_features(np.array([[raw_x, raw_y]]))
            sx = float(feat @ self._poly_x)
            sy = float(feat @ self._poly_y)
        else:
            sx = raw_x * self._scale_x + self._offset_x
            sy = raw_y * self._scale_y + self._offset_y

        sx = float(np.clip(sx, 0, self.screen_w))
        sy = float(np.clip(sy, 0, self.screen_h))
        return (sx, sy)


class GazeEstimator:
    """Combines iris tracking with head-pose compensation for gaze estimation."""

    def __init__(self, screen_w: int = 1920, screen_h: int = 1080):
        self.calibration = PolynomialCalibration(screen_w, screen_h)
        self.screen_w = screen_w
        self.screen_h = screen_h

        self.head_yaw_weight = 0.3
        self.head_pitch_weight = 0.3

        self._smooth_x: float | None = None
        self._smooth_y: float | None = None
        self._alpha = 0.4   # EMA smoothing factor

    def estimate(self, detection: dict) -> dict:
        """Return gaze estimate dict from a face-detection result."""
        raw_x = detection["gaze_x"]
        raw_y = detection["gaze_y"]

        # Head-pose compensation: subtract the rotational offset
        comp_x = float(np.clip(raw_x - detection["head_yaw"]   * self.head_yaw_weight   / 90.0, 0, 1))
        comp_y = float(np.clip(raw_y - detection["head_pitch"] * self.head_pitch_weight / 90.0, 0, 1))

        screen_x, screen_y = self.calibration.raw_to_screen(comp_x, comp_y)

        if self._smooth_x is None:
            self._smooth_x, self._smooth_y = screen_x, screen_y
        else:
            self._smooth_x = self._alpha * screen_x + (1.0 - self._alpha) * self._smooth_x
            self._smooth_y = self._alpha * screen_y + (1.0 - self._alpha) * self._smooth_y

        return {
            "raw_x": float(raw_x),
            "raw_y": float(raw_y),
            "compensated_x": comp_x,
            "compensated_y": comp_y,
            "screen_x": float(self._smooth_x),
            "screen_y": float(self._smooth_y),
            "head_yaw":   detection["head_yaw"],
            "head_pitch": detection["head_pitch"],
            "head_roll":  detection["head_roll"],
        }

    def set_smoothing(self, alpha: float):
        self._alpha = float(np.clip(alpha, 0.05, 1.0))
