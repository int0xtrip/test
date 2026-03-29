"""Saccade detection using velocity-threshold + adaptive windowing."""

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
    direction: str
    latency_ms: float | None = None
    gain: float | None = None

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
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "gain": round(self.gain, 3) if self.gain is not None else None,
        }


class SaccadeDetector:
    """Detects saccades from gaze velocity signal using adaptive thresholds."""

    def __init__(
        self,
        velocity_threshold_factor: float = 3.0,
        min_velocity: float = 30.0,
        min_duration_ms: float = 15.0,
        max_duration_ms: float = 200.0,
        min_amplitude: float = 10.0,
        fixation_window: int = 60,
    ):
        self.velocity_threshold_factor = velocity_threshold_factor
        self.min_velocity = min_velocity
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        self.min_amplitude = min_amplitude

        self._fixation_velocities = deque(maxlen=fixation_window)
        self._adaptive_threshold = min_velocity

        self._in_saccade = False
        self._saccade_start_time = 0.0
        self._saccade_start_x = 0.0
        self._saccade_start_y = 0.0
        self._saccade_peak_velocity = 0.0
        self._saccade_samples = []

        self.saccades: list[Saccade] = []
        self._max_history = 200

        self._stimulus_time: float | None = None
        self._stimulus_target_x: float | None = None
        self._stimulus_target_y: float | None = None

    def process_sample(self, filtered_x: float, filtered_y: float,
                       velocity: float, timestamp: float) -> Saccade | None:
        """Process one gaze sample and return a Saccade if one just ended."""
        detected = None

        if not self._in_saccade:
            self._fixation_velocities.append(velocity)
            self._update_threshold()

            if velocity > self._adaptive_threshold:
                self._in_saccade = True
                self._saccade_start_time = timestamp
                self._saccade_start_x = filtered_x
                self._saccade_start_y = filtered_y
                self._saccade_peak_velocity = velocity
                self._saccade_samples = [(filtered_x, filtered_y, velocity, timestamp)]
        else:
            self._saccade_samples.append((filtered_x, filtered_y, velocity, timestamp))
            self._saccade_peak_velocity = max(self._saccade_peak_velocity, velocity)

            duration_ms = (timestamp - self._saccade_start_time) * 1000

            if velocity < self._adaptive_threshold * 0.7 or duration_ms > self.max_duration_ms:
                self._in_saccade = False

                end_x = filtered_x
                end_y = filtered_y

                dx = end_x - self._saccade_start_x
                dy = end_y - self._saccade_start_y
                amplitude = np.sqrt(dx**2 + dy**2)

                if duration_ms >= self.min_duration_ms and amplitude >= self.min_amplitude:
                    if abs(dx) > abs(dy):
                        direction = "right" if dx > 0 else "left"
                    else:
                        direction = "down" if dy > 0 else "up"

                    latency = None
                    gain = None
                    if self._stimulus_time is not None:
                        latency = (self._saccade_start_time - self._stimulus_time) * 1000
                        if latency < 0 or latency > 1000:
                            latency = None
                        elif self._stimulus_target_x is not None:
                            target_dx = self._stimulus_target_x - self._saccade_start_x
                            target_dy = self._stimulus_target_y - self._saccade_start_y
                            target_amp = np.sqrt(target_dx**2 + target_dy**2)
                            if target_amp > 1e-6:
                                gain = amplitude / target_amp

                    saccade = Saccade(
                        start_time=self._saccade_start_time,
                        end_time=timestamp,
                        start_x=self._saccade_start_x,
                        start_y=self._saccade_start_y,
                        end_x=end_x,
                        end_y=end_y,
                        peak_velocity=self._saccade_peak_velocity,
                        amplitude=amplitude,
                        duration_ms=duration_ms,
                        direction=direction,
                        latency_ms=latency,
                        gain=gain,
                    )
                    self.saccades.append(saccade)
                    if len(self.saccades) > self._max_history:
                        self.saccades.pop(0)
                    detected = saccade

        return detected

    def set_stimulus(self, target_x: float, target_y: float):
        """Record when a stimulus (target) appears for latency measurement."""
        self._stimulus_time = time.time()
        self._stimulus_target_x = target_x
        self._stimulus_target_y = target_y

    def clear_stimulus(self):
        self._stimulus_time = None
        self._stimulus_target_x = None
        self._stimulus_target_y = None

    def _update_threshold(self):
        if len(self._fixation_velocities) >= 10:
            arr = np.array(self._fixation_velocities)
            mean_v = np.mean(arr)
            std_v = np.std(arr)
            self._adaptive_threshold = max(
                mean_v + self.velocity_threshold_factor * std_v,
                self.min_velocity,
            )

    def get_stats(self) -> dict:
        if not self.saccades:
            return {
                "total_saccades": 0,
                "avg_latency_ms": None,
                "avg_amplitude": None,
                "avg_duration_ms": None,
                "avg_peak_velocity": None,
                "avg_gain": None,
            }

        latencies = [s.latency_ms for s in self.saccades if s.latency_ms is not None]
        gains = [s.gain for s in self.saccades if s.gain is not None]

        return {
            "total_saccades": len(self.saccades),
            "avg_latency_ms": round(float(np.mean(latencies)), 1) if latencies else None,
            "avg_amplitude": round(float(np.mean([s.amplitude for s in self.saccades])), 2),
            "avg_duration_ms": round(float(np.mean([s.duration_ms for s in self.saccades])), 1),
            "avg_peak_velocity": round(float(np.mean([s.peak_velocity for s in self.saccades])), 2),
            "avg_gain": round(float(np.mean(gains)), 3) if gains else None,
        }

    def get_recent_saccades(self, n: int = 10) -> list[dict]:
        return [s.to_dict() for s in self.saccades[-n:]]

    def reset(self):
        self.saccades.clear()
        self._fixation_velocities.clear()
        self._in_saccade = False
        self.clear_stimulus()
