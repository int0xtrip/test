"""Signal processing: smoothing, filtering, noise estimation for gaze signals."""

import numpy as np
from scipy.signal import butter, sosfilt
from collections import deque


class GazeSignalProcessor:
    """Processes raw gaze signal: filtering, smoothing, noise estimation."""

    def __init__(self, sampling_rate: float = 30.0, buffer_size: int = 300):
        self.sampling_rate = sampling_rate
        self.buffer_size = buffer_size

        self.x_buffer = deque(maxlen=buffer_size)
        self.y_buffer = deque(maxlen=buffer_size)
        self.t_buffer = deque(maxlen=buffer_size)

        self._design_filter(cutoff=6.0)
        self._noise_window = deque(maxlen=60)

    def _design_filter(self, cutoff: float):
        """Design a Butterworth low-pass filter."""
        nyquist = self.sampling_rate / 2.0
        if cutoff >= nyquist:
            cutoff = nyquist * 0.8
        self._sos = butter(2, cutoff / nyquist, btype='low', output='sos')

    def add_sample(self, x: float, y: float, timestamp: float) -> dict:
        """Add a new gaze sample and return processed signal."""
        self.x_buffer.append(x)
        self.y_buffer.append(y)
        self.t_buffer.append(timestamp)

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

        if n >= 2:
            dt = self.t_buffer[-1] - self.t_buffer[-2]
            if dt > 0:
                vx = (fx[-1] - fx[-2]) / dt
                vy = (fy[-1] - fy[-2]) / dt
            else:
                vx, vy = 0.0, 0.0
        else:
            vx, vy = 0.0, 0.0

        velocity = float(np.sqrt(vx**2 + vy**2))

        noise_x = x - filtered_x
        noise_y = y - filtered_y
        noise_mag = np.sqrt(noise_x**2 + noise_y**2)
        self._noise_window.append(noise_mag)

        noise_level = float(np.std(self._noise_window)) if len(self._noise_window) > 5 else 0.0

        signal_power = filtered_x**2 + filtered_y**2
        noise_power = noise_level**2
        if noise_power > 1e-10:
            snr = 10 * np.log10(max(signal_power, 1e-10) / noise_power)
        else:
            snr = 60.0

        return {
            "filtered_x": filtered_x,
            "filtered_y": filtered_y,
            "velocity_x": float(vx),
            "velocity_y": float(vy),
            "velocity": velocity,
            "snr": float(np.clip(snr, 0, 60)),
            "noise_level": noise_level,
            "timestamp": timestamp,
        }

    def get_recent_signal(self, n_samples: int = 90) -> dict:
        """Get recent filtered signal for visualization."""
        n = min(n_samples, len(self.x_buffer))
        if n < 2:
            return {"x": [], "y": [], "t": []}

        x_arr = np.array(list(self.x_buffer))[-n:]
        y_arr = np.array(list(self.y_buffer))[-n:]
        t_arr = np.array(list(self.t_buffer))[-n:]

        return {
            "x": x_arr.tolist(),
            "y": y_arr.tolist(),
            "t": t_arr.tolist(),
        }

    def update_sampling_rate(self, new_rate: float):
        """Update sampling rate and redesign filter."""
        if new_rate > 5:
            self.sampling_rate = new_rate
            self._design_filter(cutoff=min(6.0, new_rate / 2 * 0.8))

    def reset(self):
        self.x_buffer.clear()
        self.y_buffer.clear()
        self.t_buffer.clear()
        self._noise_window.clear()
