"""Saccade and fixation detection using adaptive velocity-threshold algorithm."""

import numpy as np
from collections import deque
from dataclasses import dataclass, field
import time


@dataclass
class Saccade:
    """A detected saccade event."""
    start_time: float
    end_time: float
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    peak_velocity: float
    amplitude: float
    duration_ms: float
    direction: str        # cardinal: left/right/up/down
    angle_deg: float      # full angle in degrees (0=right, 90=up, CCW positive)
    latency_ms: float | None = None
    gain: float | None = None
    is_correct: bool | None = None   # for anti-saccade: was response in expected direction?

    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_x": round(self.start_x, 2),
            "start_y": round(self.start_y, 2),
            "end_x": round(self.end_x, 2),
            "end_y": round(self.end_y, 2),
            "peak_velocity": round(self.peak_velocity, 2),
            "amplitude": round(self.amplitude, 2),
            "duration_ms": round(self.duration_ms, 1),
            "direction": self.direction,
            "angle_deg": round(self.angle_deg, 1),
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "gain": round(self.gain, 3) if self.gain is not None else None,
            "is_correct": self.is_correct,
        }


@dataclass
class Fixation:
    """A detected fixation (stable gaze period between saccades)."""
    start_time: float
    end_time: float
    centroid_x: float
    centroid_y: float
    duration_ms: float
    dispersion: float   # RMS spatial spread in pixels (lower = more stable)

    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "centroid_x": round(self.centroid_x, 1),
            "centroid_y": round(self.centroid_y, 1),
            "duration_ms": round(self.duration_ms, 1),
            "dispersion": round(self.dispersion, 2),
        }


class SaccadeDetector:
    """Detects saccades and fixations from a gaze velocity signal.

    Algorithm:
    - Adaptive velocity threshold: mean(fixation_vel) + factor * std(fixation_vel)
    - Saccade onset:  velocity > threshold
    - Saccade offset: velocity < 0.7 * threshold  OR  duration > max_duration_ms
    - Saccade valid:  duration >= min_duration_ms  AND  amplitude >= min_amplitude
    - Fixation:       gap between saccades, duration >= min_fixation_ms
    """

    def __init__(
        self,
        velocity_threshold_factor: float = 3.0,
        min_velocity: float = 30.0,
        min_duration_ms: float = 15.0,
        max_duration_ms: float = 200.0,
        min_amplitude: float = 10.0,
        min_fixation_ms: float = 80.0,
        fixation_window: int = 60,
    ):
        self.velocity_threshold_factor = velocity_threshold_factor
        self.min_velocity = min_velocity
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        self.min_amplitude = min_amplitude
        self.min_fixation_ms = min_fixation_ms

        self._fixation_velocities = deque(maxlen=fixation_window)
        self._adaptive_threshold = min_velocity

        # Saccade tracking state
        self._in_saccade = False
        self._saccade_start_time = 0.0
        self._saccade_start_x = 0.0
        self._saccade_start_y = 0.0
        self._saccade_peak_velocity = 0.0

        # Fixation tracking state
        self._fix_start_time: float | None = None
        self._fix_samples: list = []   # [(x, y, t), ...]

        self.saccades: list[Saccade] = []
        self.fixations: list[Fixation] = []
        self._max_history = 200

        # Stimulus state
        self._stimulus_time: float | None = None
        self._stimulus_target_x: float | None = None
        self._stimulus_target_y: float | None = None
        self._stimulus_expected_direction: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_sample(
        self,
        filtered_x: float,
        filtered_y: float,
        velocity: float,
        timestamp: float,
    ) -> Saccade | None:
        """Process one gaze sample. Returns a completed Saccade if one just ended."""
        detected: Saccade | None = None

        if not self._in_saccade:
            # Accumulate fixation velocities to keep threshold adaptive
            self._fixation_velocities.append(velocity)
            self._update_threshold()

            if velocity > self._adaptive_threshold:
                # --- Saccade onset ---
                self._in_saccade = True
                self._saccade_start_time = timestamp
                self._saccade_start_x = filtered_x
                self._saccade_start_y = filtered_y
                self._saccade_peak_velocity = velocity

                # Close any open fixation
                if self._fix_start_time is not None:
                    detected_fix = self._close_fixation(timestamp)
                    if detected_fix:
                        self.fixations.append(detected_fix)
                        if len(self.fixations) > self._max_history:
                            self.fixations.pop(0)
                self._fix_start_time = None
                self._fix_samples = []
            else:
                # --- Inside fixation ---
                if self._fix_start_time is None:
                    self._fix_start_time = timestamp
                self._fix_samples.append((filtered_x, filtered_y, timestamp))
        else:
            self._saccade_peak_velocity = max(self._saccade_peak_velocity, velocity)
            duration_ms = (timestamp - self._saccade_start_time) * 1000.0

            if velocity < self._adaptive_threshold * 0.7 or duration_ms > self.max_duration_ms:
                # --- Saccade offset ---
                self._in_saccade = False

                dx = filtered_x - self._saccade_start_x
                dy = filtered_y - self._saccade_start_y
                amplitude = float(np.sqrt(dx**2 + dy**2))

                if duration_ms >= self.min_duration_ms and amplitude >= self.min_amplitude:
                    direction = _cardinal(dx, dy)
                    # angle: 0=right, 90=up (screen Y flipped so negate dy)
                    angle_deg = float(np.degrees(np.arctan2(-dy, dx)))

                    latency: float | None = None
                    gain: float | None = None
                    is_correct: bool | None = None

                    if self._stimulus_time is not None:
                        raw_latency = (self._saccade_start_time - self._stimulus_time) * 1000.0
                        if 50.0 <= raw_latency <= 1000.0:
                            latency = raw_latency

                            if self._stimulus_target_x is not None:
                                tdx = self._stimulus_target_x - self._saccade_start_x
                                tdy = self._stimulus_target_y - self._saccade_start_y
                                target_amp = float(np.sqrt(tdx**2 + tdy**2))
                                if target_amp > 1e-6:
                                    gain = amplitude / target_amp

                            if self._stimulus_expected_direction is not None:
                                is_correct = (direction == self._stimulus_expected_direction)

                    saccade = Saccade(
                        start_time=self._saccade_start_time,
                        end_time=timestamp,
                        start_x=self._saccade_start_x,
                        start_y=self._saccade_start_y,
                        end_x=filtered_x,
                        end_y=filtered_y,
                        peak_velocity=self._saccade_peak_velocity,
                        amplitude=amplitude,
                        duration_ms=duration_ms,
                        direction=direction,
                        angle_deg=angle_deg,
                        latency_ms=latency,
                        gain=gain,
                        is_correct=is_correct,
                    )
                    self.saccades.append(saccade)
                    if len(self.saccades) > self._max_history:
                        self.saccades.pop(0)
                    detected = saccade

                # Start tracking next fixation immediately after saccade offset
                self._fix_start_time = timestamp
                self._fix_samples = [(filtered_x, filtered_y, timestamp)]

        return detected

    def set_stimulus(
        self,
        target_x: float,
        target_y: float,
        expected_direction: str | None = None,
    ):
        """Record a stimulus onset for latency / gain / correctness computation.

        expected_direction: the correct gaze direction for an anti-saccade trial
        ('left', 'right', 'up', 'down').  None for pro-saccade (no correctness check).
        """
        self._stimulus_time = time.time()
        self._stimulus_target_x = target_x
        self._stimulus_target_y = target_y
        self._stimulus_expected_direction = expected_direction

    def clear_stimulus(self):
        self._stimulus_time = None
        self._stimulus_target_x = None
        self._stimulus_target_y = None
        self._stimulus_expected_direction = None

    def get_stats(self) -> dict:
        if not self.saccades:
            return {
                "total_saccades": 0,
                "avg_latency_ms": None,
                "avg_amplitude": None,
                "avg_duration_ms": None,
                "avg_peak_velocity": None,
                "avg_gain": None,
                "main_sequence_ratio": None,
                "antisaccade_error_rate": None,
                "total_fixations": len(self.fixations),
                "avg_fixation_ms": None,
            }

        latencies = [s.latency_ms for s in self.saccades if s.latency_ms is not None]
        gains = [s.gain for s in self.saccades if s.gain is not None]
        amplitudes = [s.amplitude for s in self.saccades]
        velocities = [s.peak_velocity for s in self.saccades]
        durations = [s.duration_ms for s in self.saccades]

        # Main sequence ratio: slope of peak velocity vs amplitude (px/s per px)
        # Healthy adults: roughly linear; deviations suggest pathology.
        ms_ratio: float | None = None
        if len(amplitudes) >= 3:
            amp_arr = np.array(amplitudes)
            vel_arr = np.array(velocities)
            if amp_arr.mean() > 1e-6:
                ms_ratio = round(float(vel_arr.mean() / amp_arr.mean()), 2)

        # Anti-saccade error rate
        antisacc = [s for s in self.saccades if s.is_correct is not None]
        asacc_err: float | None = None
        if antisacc:
            errors = sum(1 for s in antisacc if s.is_correct is False)
            asacc_err = round(errors / len(antisacc), 3)

        # Fixation stats
        avg_fix: float | None = None
        if self.fixations:
            avg_fix = round(float(np.mean([f.duration_ms for f in self.fixations])), 1)

        return {
            "total_saccades": len(self.saccades),
            "avg_latency_ms": round(float(np.mean(latencies)), 1) if latencies else None,
            "avg_amplitude": round(float(np.mean(amplitudes)), 2),
            "avg_duration_ms": round(float(np.mean(durations)), 1),
            "avg_peak_velocity": round(float(np.mean(velocities)), 2),
            "avg_gain": round(float(np.mean(gains)), 3) if gains else None,
            "main_sequence_ratio": ms_ratio,
            "antisaccade_error_rate": asacc_err,
            "total_fixations": len(self.fixations),
            "avg_fixation_ms": avg_fix,
        }

    def get_recent_saccades(self, n: int = 10) -> list[dict]:
        return [s.to_dict() for s in self.saccades[-n:]]

    def get_recent_fixations(self, n: int = 20) -> list[dict]:
        return [f.to_dict() for f in self.fixations[-n:]]

    def reset(self):
        self.saccades.clear()
        self.fixations.clear()
        self._fixation_velocities.clear()
        self._in_saccade = False
        self._fix_start_time = None
        self._fix_samples = []
        self.clear_stimulus()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_threshold(self):
        if len(self._fixation_velocities) >= 10:
            arr = np.array(self._fixation_velocities)
            self._adaptive_threshold = max(
                float(arr.mean() + self.velocity_threshold_factor * arr.std()),
                self.min_velocity,
            )

    def _close_fixation(self, end_time: float) -> Fixation | None:
        if not self._fix_samples or self._fix_start_time is None:
            return None
        duration_ms = (end_time - self._fix_start_time) * 1000.0
        if duration_ms < self.min_fixation_ms:
            return None
        pts = np.array([(x, y) for x, y, _ in self._fix_samples])
        centroid = pts.mean(axis=0)
        dispersion = float(np.sqrt(np.mean(np.sum((pts - centroid) ** 2, axis=1))))
        return Fixation(
            start_time=self._fix_start_time,
            end_time=end_time,
            centroid_x=float(centroid[0]),
            centroid_y=float(centroid[1]),
            duration_ms=duration_ms,
            dispersion=dispersion,
        )


def _cardinal(dx: float, dy: float) -> str:
    """Return the dominant cardinal direction of a displacement vector."""
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "down" if dy >= 0 else "up"
