"""Saccade detection — paper-validated marker-driven rolling-window algorithm.

References
----------
  - Sledzianowski et al. (2022) — video-oculometric process pattern
  - Andersson et al. (2010)    — temporal sampling error analysis

Algorithm (marker-driven, matches paper exactly):
  1. When set_stimulus() is called (step-model Δt=0):
       a. Compute mean frame-to-frame shift from the 300 ms fixation window
          that immediately precedes the marker.
       b. Open a search window from (marker_onset + 40 ms) to
          (marker_onset + 500 ms) — the 40 ms floor is the physiological
          minimum saccadic latency; 500 ms covers the longest ~8° saccade.
  2. Inside the search window, look for a run of consecutive frames where:
       • each frame-to-frame shift > mean fixation fluctuation, AND
       • the cumulative shift since the run start ≥ 30 % of target distance,
       • run duration ≥ 50 ms.
     The first frame of that run is the saccade onset.
  3. After onset, track peak frame-shift.  Saccade ends when the current
     frame-to-frame shift drops below 30 % of the running peak.
  4. Compute latency, duration, amplitude, avg/peak velocity, gain.

Passive fallback (no stimulus set): adaptive velocity-threshold detector
so the live signal view still shows saccades outside the guided test.
"""

import numpy as np
from collections import deque
from dataclasses import dataclass
import time


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Saccade:
    start_time: float
    end_time: float
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    peak_velocity: float
    avg_velocity: float
    amplitude: float
    duration_ms: float
    direction: str
    angle_deg: float
    latency_ms: float | None = None
    gain: float | None = None
    is_correct: bool | None = None
    confidence: float = 100.0

    def to_dict(self) -> dict:
        return {
            "start_time":   self.start_time,
            "end_time":     self.end_time,
            "start_x":      round(self.start_x,  2),
            "start_y":      round(self.start_y,  2),
            "end_x":        round(self.end_x,    2),
            "end_y":        round(self.end_y,    2),
            "peak_velocity": round(self.peak_velocity, 2),
            "avg_velocity":  round(self.avg_velocity,  2),
            "amplitude":    round(self.amplitude,  2),
            "duration_ms":  round(self.duration_ms, 1),
            "direction":    self.direction,
            "angle_deg":    round(self.angle_deg, 1),
            "latency_ms":   round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "gain":         round(self.gain, 3) if self.gain is not None else None,
            "is_correct":   self.is_correct,
            "confidence":   round(self.confidence, 1),
        }


@dataclass
class Fixation:
    start_time: float
    end_time: float
    centroid_x: float
    centroid_y: float
    duration_ms: float
    dispersion: float

    def to_dict(self) -> dict:
        return {
            "start_time":  self.start_time,
            "end_time":    self.end_time,
            "centroid_x":  round(self.centroid_x, 1),
            "centroid_y":  round(self.centroid_y, 1),
            "duration_ms": round(self.duration_ms, 1),
            "dispersion":  round(self.dispersion,  2),
        }


# ─── Main detector ────────────────────────────────────────────────────────────

class SaccadeDetector:
    """Marker-driven rolling-window saccade detector (paper algorithm)."""

    # --- Tuneable constants (paper-derived) ---
    MIN_LATENCY_S      = 0.040   # 40 ms
    MAX_LATENCY_S      = 0.500   # 500 ms
    MIN_SACCADE_MS     = 50.0    # minimum run duration for onset confirmation
    FIXATION_WINDOW_S  = 0.300   # 300 ms control window
    ONSET_SHIFT_RATIO  = 0.30    # cumulative shift must be ≥ 30 % of target dist
    END_SHIFT_RATIO    = 0.30    # frame shift < 30 % of peak → saccade end
    # Passive-mode velocity threshold fallback
    PASSIVE_MIN_VEL    = 30.0
    PASSIVE_MAX_DUR_MS = 200.0
    PASSIVE_MIN_DUR_MS = 15.0
    PASSIVE_MIN_AMP    = 10.0

    def __init__(self):
        # Rolling gaze buffer — enough for ~10 s at 30 fps
        self._buf_x: deque[float] = deque(maxlen=300)
        self._buf_y: deque[float] = deque(maxlen=300)
        self._buf_t: deque[float] = deque(maxlen=300)

        # --- Marker-driven state ---
        self._stimulus_onset_t:  float | None = None
        self._stimulus_target_x: float | None = None
        self._stimulus_target_y: float | None = None
        self._stimulus_expected: str   | None = None

        self._fix_center_x:       float = 0.0
        self._mean_fix_fluctuation: float = 30.0  # px between frames
        self._target_distance:    float = 1.0

        # Search / saccade tracking
        self._state: str = "idle"   # idle | search | saccade
        self._search_end_t:    float = 0.0

        # Candidate onset (need 50 ms run to confirm)
        self._cand_t:   float | None = None
        self._cand_x:   float = 0.0

        # Active saccade tracking
        self._sacc_onset_t: float = 0.0
        self._sacc_onset_x: float = 0.0
        self._sacc_onset_y: float = 0.0
        self._sacc_xs:      list[float] = []
        self._sacc_ts:      list[float] = []
        self._sacc_peak_frame_shift: float = 0.0

        # Passive-mode state
        self._passive_in_sacc: bool = False
        self._passive_sacc_start_t: float = 0.0
        self._passive_sacc_start_x: float = 0.0
        self._passive_sacc_start_y: float = 0.0
        self._passive_peak_vel:     float = 0.0
        self._passive_fix_vels:     deque[float] = deque(maxlen=60)
        self._passive_threshold:    float = self.PASSIVE_MIN_VEL

        # Fixation tracking
        self._fix_start_t:   float | None = None
        self._fix_samples:   list = []

        self.saccades:  list[Saccade]  = []
        self.fixations: list[Fixation] = []
        self._max_history = 200

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_stimulus(self, target_x: float, target_y: float,
                     expected_direction: str | None = None):
        """Step-model stimulus onset (fixation disappears, target appears simultaneously)."""
        now = time.time()
        self._stimulus_onset_t  = now
        self._stimulus_target_x = target_x
        self._stimulus_target_y = target_y
        self._stimulus_expected = expected_direction

        # --- 300 ms fixation reference window ---
        cutoff = now - self.FIXATION_WINDOW_S
        pre_xs = [x for x, t in zip(self._buf_x, self._buf_t) if t >= cutoff]
        pre_ts = [t for t in self._buf_t if t >= cutoff]

        if len(pre_xs) >= 3:
            self._fix_center_x = float(np.mean(pre_xs))
            shifts = [abs(pre_xs[i] - pre_xs[i-1]) for i in range(1, len(pre_xs))]
            self._mean_fix_fluctuation = float(np.mean(shifts)) if shifts else 15.0
        else:
            self._fix_center_x = float(self._buf_x[-1]) if self._buf_x else target_x
            self._mean_fix_fluctuation = 15.0

        self._target_distance = max(
            abs(target_x - self._fix_center_x), 50.0   # floor at 50 px
        )

        self._state = "search"
        self._search_end_t = now + self.MAX_LATENCY_S
        self._cand_t = None

        # Close any open fixation
        self._close_and_store_fixation(now)

    def clear_stimulus(self):
        self._stimulus_onset_t  = None
        self._stimulus_target_x = None
        self._stimulus_target_y = None
        self._stimulus_expected = None
        self._state = "idle"

    def process_sample(self, filtered_x: float, filtered_y: float,
                       velocity: float, timestamp: float,
                       snr: float = 60.0) -> "Saccade | None":
        """Process one gaze sample. Returns a completed Saccade when one ends."""
        self._buf_x.append(filtered_x)
        self._buf_y.append(filtered_y)
        self._buf_t.append(timestamp)

        if self._state in ("search", "saccade"):
            return self._process_marker_driven(filtered_x, filtered_y, timestamp)
        else:
            return self._process_passive(filtered_x, filtered_y, velocity, timestamp, snr)

    # ── Marker-driven detection (paper algorithm) ──────────────────────────────

    def _process_marker_driven(self, x: float, y: float, t: float) -> "Saccade | None":
        if len(self._buf_x) < 2:
            return None

        frame_shift = abs(x - list(self._buf_x)[-2])  # |x[n] - x[n-1]|

        # ── SEARCH phase ───────────────────────────────────────────────────────
        if self._state == "search":
            onset_min_t = self._stimulus_onset_t + self.MIN_LATENCY_S

            if t < onset_min_t:
                return None  # still within minimum latency dead zone

            if t > self._search_end_t:
                # Trial failed — no saccade found in time
                self._state = "idle"
                return None

            if frame_shift > self._mean_fix_fluctuation:
                if self._cand_t is None:
                    # Start of a potential saccade run
                    self._cand_t = t
                    self._cand_x = x
                else:
                    run_duration_ms  = (t - self._cand_t) * 1000.0
                    cumulative_shift = abs(x - self._cand_x)

                    if (run_duration_ms  >= self.MIN_SACCADE_MS and
                            cumulative_shift >= self.ONSET_SHIFT_RATIO * self._target_distance):
                        # Saccade confirmed — onset is at candidate start
                        self._state = "saccade"
                        self._sacc_onset_t = self._cand_t
                        self._sacc_onset_x = self._cand_x
                        self._sacc_onset_y = float(list(self._buf_y)[-1])  # approx
                        self._sacc_xs = [x]
                        self._sacc_ts = [t]
                        self._sacc_peak_frame_shift = frame_shift
                        self._cand_t = None
            else:
                # Movement stopped — reset candidate run
                self._cand_t = None

            return None

        # ── IN-SACCADE phase ───────────────────────────────────────────────────
        if self._state == "saccade":
            self._sacc_xs.append(x)
            self._sacc_ts.append(t)
            self._sacc_peak_frame_shift = max(self._sacc_peak_frame_shift, frame_shift)

            # End condition: frame shift < 30 % of running peak
            if (frame_shift < self.END_SHIFT_RATIO * self._sacc_peak_frame_shift
                    and len(self._sacc_xs) >= 3):
                return self._finalize_saccade(x, y, t)

            # Timeout guard (shouldn't happen often, but prevents stuck state)
            if (t - self._sacc_onset_t) * 1000.0 > 500.0:
                return self._finalize_saccade(x, y, t)

        return None

    def _finalize_saccade(self, end_x: float, end_y: float,
                          end_t: float) -> "Saccade | None":
        self._state = "idle"

        duration_ms = (end_t - self._sacc_onset_t) * 1000.0
        dx = end_x - self._sacc_onset_x
        dy = end_y - self._sacc_onset_y
        amplitude = float(np.sqrt(dx**2 + dy**2))

        if amplitude < 5.0 or duration_ms < 10.0:
            return None

        # Velocity from consecutive filtered positions
        xs, ts = np.array(self._sacc_xs), np.array(self._sacc_ts)
        if len(xs) >= 2:
            dts = np.diff(ts)
            dts = np.where(dts < 1e-6, 1e-6, dts)
            frame_vels = np.abs(np.diff(xs)) / dts  # px/s
            peak_vel = float(frame_vels.max())
            avg_vel  = float(frame_vels.mean())
        else:
            peak_vel = amplitude / max(duration_ms / 1000.0, 1e-3)
            avg_vel  = peak_vel

        latency_ms: float | None = None
        gain:       float | None = None
        is_correct: bool  | None = None

        if self._stimulus_onset_t is not None:
            raw_lat = (self._sacc_onset_t - self._stimulus_onset_t) * 1000.0
            if self.MIN_LATENCY_S * 1000 <= raw_lat <= self.MAX_LATENCY_S * 1000:
                latency_ms = raw_lat

            if self._stimulus_target_x is not None:
                tdist = abs(self._stimulus_target_x - self._sacc_onset_x)
                if tdist > 1e-3:
                    gain = amplitude / tdist

            direction = _cardinal(dx, dy)
            if self._stimulus_expected is not None:
                is_correct = (direction == self._stimulus_expected)

        direction = _cardinal(dx, dy)
        angle_deg = float(np.degrees(np.arctan2(-dy, dx)))

        saccade = Saccade(
            start_time=self._sacc_onset_t,
            end_time=end_t,
            start_x=self._sacc_onset_x,
            start_y=self._sacc_onset_y,
            end_x=end_x,
            end_y=end_y,
            peak_velocity=peak_vel,
            avg_velocity=avg_vel,
            amplitude=amplitude,
            duration_ms=duration_ms,
            direction=direction,
            angle_deg=angle_deg,
            latency_ms=latency_ms,
            gain=gain,
            is_correct=is_correct,
            confidence=_saccade_confidence(duration_ms, amplitude, peak_vel),
        )
        self.saccades.append(saccade)
        if len(self.saccades) > self._max_history:
            self.saccades.pop(0)

        # Begin tracking next fixation
        self._fix_start_t  = end_t
        self._fix_samples  = [(end_x, end_y, end_t)]

        # Clear stimulus so passive mode resumes until next trial
        self._stimulus_onset_t = None

        return saccade

    # ── Passive velocity-threshold detection ───────────────────────────────────

    def _process_passive(self, x: float, y: float, velocity: float,
                         t: float, snr: float) -> "Saccade | None":
        detected: Saccade | None = None

        if not self._passive_in_sacc:
            self._passive_fix_vels.append(velocity)
            self._update_passive_threshold()

            if velocity > self._passive_threshold:
                self._passive_in_sacc = True
                self._passive_sacc_start_t = t
                self._passive_sacc_start_x = x
                self._passive_sacc_start_y = y
                self._passive_peak_vel = velocity
                self._close_and_store_fixation(t)
                self._fix_start_t = None
                self._fix_samples = []
            else:
                if self._fix_start_t is None:
                    self._fix_start_t = t
                self._fix_samples.append((x, y, t))
        else:
            self._passive_peak_vel = max(self._passive_peak_vel, velocity)
            dur_ms = (t - self._passive_sacc_start_t) * 1000.0

            if (velocity < self._passive_threshold * 0.7
                    or dur_ms > self.PASSIVE_MAX_DUR_MS):
                self._passive_in_sacc = False
                dx = x - self._passive_sacc_start_x
                dy = y - self._passive_sacc_start_y
                amplitude = float(np.sqrt(dx**2 + dy**2))

                if dur_ms >= self.PASSIVE_MIN_DUR_MS and amplitude >= self.PASSIVE_MIN_AMP:
                    direction = _cardinal(dx, dy)
                    saccade = Saccade(
                        start_time=self._passive_sacc_start_t,
                        end_time=t,
                        start_x=self._passive_sacc_start_x,
                        start_y=self._passive_sacc_start_y,
                        end_x=x, end_y=y,
                        peak_velocity=self._passive_peak_vel,
                        avg_velocity=self._passive_peak_vel * 0.7,
                        amplitude=amplitude,
                        duration_ms=dur_ms,
                        direction=direction,
                        angle_deg=float(np.degrees(np.arctan2(-dy, dx))),
                        confidence=_saccade_confidence(dur_ms, amplitude, self._passive_peak_vel),
                    )
                    self.saccades.append(saccade)
                    if len(self.saccades) > self._max_history:
                        self.saccades.pop(0)
                    detected = saccade

                self._fix_start_t = t
                self._fix_samples = [(x, y, t)]

        return detected

    def _update_passive_threshold(self):
        if len(self._passive_fix_vels) >= 10:
            arr = np.array(self._passive_fix_vels)
            self._passive_threshold = max(
                float(arr.mean() + 3.0 * arr.std()),
                self.PASSIVE_MIN_VEL,
            )

    # ── Fixation helpers ───────────────────────────────────────────────────────

    def _close_and_store_fixation(self, end_t: float):
        if not self._fix_samples or self._fix_start_t is None:
            return
        dur_ms = (end_t - self._fix_start_t) * 1000.0
        if dur_ms < 80.0:
            return
        pts = np.array([(x, y) for x, y, _ in self._fix_samples])
        centroid = pts.mean(axis=0)
        dispersion = float(np.sqrt(np.mean(np.sum((pts - centroid) ** 2, axis=1))))
        fix = Fixation(
            start_time=self._fix_start_t,
            end_time=end_t,
            centroid_x=float(centroid[0]),
            centroid_y=float(centroid[1]),
            duration_ms=dur_ms,
            dispersion=dispersion,
        )
        self.fixations.append(fix)
        if len(self.fixations) > self._max_history:
            self.fixations.pop(0)
        self._fix_start_t = None
        self._fix_samples = []

    # ── Statistics ─────────────────────────────────────────────────────────────

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

        latencies  = [s.latency_ms for s in self.saccades if s.latency_ms is not None]
        gains      = [s.gain       for s in self.saccades if s.gain       is not None]
        amplitudes = [s.amplitude  for s in self.saccades]
        velocities = [s.peak_velocity for s in self.saccades]
        durations  = [s.duration_ms   for s in self.saccades]

        ms_ratio: float | None = None
        if len(amplitudes) >= 3:
            amp_arr = np.array(amplitudes)
            vel_arr = np.array(velocities)
            if amp_arr.mean() > 1e-6:
                ms_ratio = round(float(vel_arr.mean() / amp_arr.mean()), 2)

        antisacc = [s for s in self.saccades if s.is_correct is not None]
        asacc_err: float | None = None
        if antisacc:
            errors = sum(1 for s in antisacc if s.is_correct is False)
            asacc_err = round(errors / len(antisacc), 3)

        avg_fix: float | None = None
        if self.fixations:
            avg_fix = round(float(np.mean([f.duration_ms for f in self.fixations])), 1)

        return {
            "total_saccades":        len(self.saccades),
            "avg_latency_ms":        round(float(np.mean(latencies)), 1) if latencies else None,
            "avg_amplitude":         round(float(np.mean(amplitudes)), 2),
            "avg_duration_ms":       round(float(np.mean(durations)),  1),
            "avg_peak_velocity":     round(float(np.mean(velocities)), 2),
            "avg_gain":              round(float(np.mean(gains)), 3)    if gains      else None,
            "main_sequence_ratio":   ms_ratio,
            "antisaccade_error_rate": asacc_err,
            "total_fixations":       len(self.fixations),
            "avg_fixation_ms":       avg_fix,
        }

    def get_recent_saccades(self, n: int = 10) -> list[dict]:
        return [s.to_dict() for s in self.saccades[-n:]]

    def get_recent_fixations(self, n: int = 20) -> list[dict]:
        return [f.to_dict() for f in self.fixations[-n:]]

    def reset(self):
        self.saccades.clear()
        self.fixations.clear()
        self._passive_fix_vels.clear()
        self._passive_in_sacc = False
        self._fix_start_t = None
        self._fix_samples = []
        self.clear_stimulus()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cardinal(dx: float, dy: float) -> str:
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "down" if dy >= 0 else "up"


def _saccade_confidence(duration_ms: float, amplitude: float,
                        peak_velocity: float) -> float:
    conf = 100.0
    if duration_ms < 20 or duration_ms > 500:
        conf -= 25
    elif duration_ms < 30 or duration_ms > 200:
        conf -= 10
    if amplitude < 15:
        conf -= 20
    elif amplitude < 30:
        conf -= 8
    if peak_velocity < 40:
        conf -= 20
    elif peak_velocity < 80:
        conf -= 8
    return max(0.0, min(100.0, conf))
