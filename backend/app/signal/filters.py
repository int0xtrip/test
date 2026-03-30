"""Signal processing: filtering, noise estimation, and velocity for gaze signals."""

import numpy as np
from scipy.signal import butter, sosfilt
from collections import deque


class GazeSignalProcessor:
    """Processes raw gaze signal: filtering, velocity estimation, noise analysis.

    Two-track design:
    - Filtered position (8 Hz Butterworth) for smooth display and fixation detection.
    - Raw velocity (3-point central difference) for saccade detection — avoids the
      velocity attenuation caused by low-pass filtering fast transients.
    """

    def __init__(self, sampling_rate: float = 30.0, buffer_size: int = 300):
        self.sampling_rate = sampling_rate
        self.buffer_size = buffer_size

        self.x_buffer = deque(maxlen=buffer_size)
        self.y_buffer = deque(maxlen=buffer_size)
        self.t_buffer = deque(maxlen=buffer_size)

        # Short window of raw samples for velocity (central difference needs only ~5)
        self._raw_x = deque(maxlen=5)
        self._raw_y = deque(maxlen=5)
        self._raw_t = deque(maxlen=5)

        self._design_filter(cutoff=8.0)
        self._noise_window = deque(maxlen=60)

    def _design_filter(self, cutoff: float):
        """Design a 2nd-order Butterworth low-pass filter for position smoothing."""
        nyquist = self.sampling_rate / 2.0
        if cutoff >= nyquist:
            cutoff = nyquist * 0.8
        self._sos = butter(2, cutoff / nyquist, btype='low', output='sos')

    def _compute_raw_velocity(self) -> tuple[float, float, float]:
        """Velocity from raw gaze via 3-point central difference.

        Using raw positions rather than filtered positions preserves the fast
        transients of saccades.  A single-frame difference amplifies noise, so
        we span two frames: v[n] = (raw[n] – raw[n-2]) / (t[n] – t[n-2]).
        """
        n = len(self._raw_t)
        if n < 3:
            if n < 2:
                return 0.0, 0.0, 0.0
            xs = list(self._raw_x)
            ys = list(self._raw_y)
            ts = list(self._raw_t)
            dt = ts[-1] - ts[-2]
            if dt <= 0:
                return 0.0, 0.0, 0.0
            vx = (xs[-1] - xs[-2]) / dt
            vy = (ys[-1] - ys[-2]) / dt
            return float(vx), float(vy), float(np.sqrt(vx**2 + vy**2))

        xs = list(self._raw_x)
        ys = list(self._raw_y)
        ts = list(self._raw_t)
        dt = ts[-1] - ts[-3]
        if dt <= 0:
            return 0.0, 0.0, 0.0
        vx = (xs[-1] - xs[-3]) / dt
        vy = (ys[-1] - ys[-3]) / dt
        return float(vx), float(vy), float(np.sqrt(vx**2 + vy**2))

    def add_sample(self, x: float, y: float, timestamp: float) -> dict:
        """Add a gaze sample and return processed signal metrics."""
        self.x_buffer.append(x)
        self.y_buffer.append(y)
        self.t_buffer.append(timestamp)
        self._raw_x.append(x)
        self._raw_y.append(y)
        self._raw_t.append(timestamp)

        n = len(self.x_buffer)

        if n < 5:
            return {
                "filtered_x": x,
                "filtered_y": y,
                "velocity_x": 0.0,
                "velocity_y": 0.0,
                "velocity": 0.0,
                "snr": 0.0,
                "noise_level": 0.0,
                "timestamp": timestamp,
            }

        x_arr = np.array(self.x_buffer)
        y_arr = np.array(self.y_buffer)

        # Symmetric padding to reduce edge effects
        pad_len = min(n - 1, 12)
        if pad_len > 0:
            x_padded = np.concatenate([x_arr[:pad_len][::-1], x_arr])
            y_padded = np.concatenate([y_arr[:pad_len][::-1], y_arr])
            fx = sosfilt(self._sos, x_padded)[pad_len:]
            fy = sosfilt(self._sos, y_padded)[pad_len:]
        else:
            fx = sosfilt(self._sos, x_arr)
            fy = sosfilt(self._sos, y_arr)

        filtered_x = float(fx[-1])
        filtered_y = float(fy[-1])

        # Raw velocity for saccade detection (not attenuated by low-pass filter)
        vx, vy, velocity = self._compute_raw_velocity()

        # Noise = deviation of raw from filtered (smooth signal)
        noise_mag = float(np.sqrt((x - filtered_x)**2 + (y - filtered_y)**2))
        self._noise_window.append(noise_mag)
        noise_level = float(np.std(self._noise_window)) if len(self._noise_window) > 5 else 0.0

        signal_power = filtered_x**2 + filtered_y**2
        noise_power = noise_level**2
        if noise_power > 1e-10:
            snr = 10.0 * np.log10(max(signal_power, 1e-10) / noise_power)
        else:
            snr = 60.0

        return {
            "filtered_x": filtered_x,
            "filtered_y": filtered_y,
            "velocity_x": vx,
            "velocity_y": vy,
            "velocity": velocity,
            "snr": float(np.clip(snr, 0, 60)),
            "noise_level": noise_level,
            "timestamp": timestamp,
        }

    def get_recent_signal(self, n_samples: int = 90) -> dict:
        """Return recent raw gaze positions for visualisation."""
        n = min(n_samples, len(self.x_buffer))
        if n < 2:
            return {"x": [], "y": [], "t": []}
        x_arr = np.array(list(self.x_buffer))[-n:]
        y_arr = np.array(list(self.y_buffer))[-n:]
        t_arr = np.array(list(self.t_buffer))[-n:]
        return {"x": x_arr.tolist(), "y": y_arr.tolist(), "t": t_arr.tolist()}

    def update_sampling_rate(self, new_rate: float):
        """Update sampling rate and redesign filter."""
        if new_rate > 5:
            self.sampling_rate = new_rate
            self._design_filter(cutoff=min(8.0, new_rate / 2 * 0.8))

    def reset(self):
        self.x_buffer.clear()
        self.y_buffer.clear()
        self.t_buffer.clear()
        self._raw_x.clear()
        self._raw_y.clear()
        self._raw_t.clear()
        self._noise_window.clear()
