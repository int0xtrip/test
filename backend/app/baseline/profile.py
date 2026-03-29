"""Personal baseline system: stores and tracks user metrics over sessions."""

import json
import os
import time
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict


DATA_DIR = Path.home() / ".oculometry" / "profiles"


@dataclass
class SessionSummary:
    session_id: str
    timestamp: float
    duration_seconds: float
    total_saccades: int
    avg_latency_ms: float | None
    avg_amplitude: float
    avg_duration_ms: float
    avg_peak_velocity: float
    avg_gain: float | None
    avg_signal_quality: float
    mode: str


class UserProfile:
    """Manages a user's baseline profile built over multiple sessions."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.profile_dir = DATA_DIR / user_id
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.sessions: list[SessionSummary] = []
        self._load()

    def _load(self):
        path = self.profile_dir / "sessions.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            self.sessions = [SessionSummary(**s) for s in data]

    def _save(self):
        path = self.profile_dir / "sessions.json"
        with open(path, "w") as f:
            json.dump([asdict(s) for s in self.sessions], f, indent=2)

    def add_session(self, summary: SessionSummary):
        self.sessions.append(summary)
        self._save()

    def get_baseline(self) -> dict:
        if not self.sessions:
            return {"has_baseline": False, "sessions_count": 0}

        latencies = [s.avg_latency_ms for s in self.sessions if s.avg_latency_ms is not None]
        amplitudes = [s.avg_amplitude for s in self.sessions]
        durations = [s.avg_duration_ms for s in self.sessions]
        velocities = [s.avg_peak_velocity for s in self.sessions]
        gains = [s.avg_gain for s in self.sessions if s.avg_gain is not None]

        def stats(arr):
            if not arr:
                return None
            return {"mean": round(float(np.mean(arr)), 2), "std": round(float(np.std(arr)), 2)}

        return {
            "has_baseline": True,
            "sessions_count": len(self.sessions),
            "first_session": self.sessions[0].timestamp,
            "last_session": self.sessions[-1].timestamp,
            "latency_ms": stats(latencies),
            "amplitude": stats(amplitudes),
            "duration_ms": stats(durations),
            "peak_velocity": stats(velocities),
            "gain": stats(gains),
        }

    def check_deviation(self, current_stats: dict) -> dict:
        baseline = self.get_baseline()
        if not baseline["has_baseline"] or baseline["sessions_count"] < 3:
            return {"has_baseline": False, "deviations": []}

        deviations = []

        def check_metric(name, current_val, baseline_stats):
            if current_val is None or baseline_stats is None:
                return
            mean = baseline_stats["mean"]
            std = baseline_stats["std"]
            if std < 1e-6:
                return
            z_score = (current_val - mean) / std
            if abs(z_score) > 2.0:
                direction = "higher" if z_score > 0 else "lower"
                deviations.append({
                    "metric": name,
                    "current": round(current_val, 2),
                    "baseline_mean": mean,
                    "baseline_std": std,
                    "z_score": round(z_score, 2),
                    "direction": direction,
                })

        check_metric("latency_ms", current_stats.get("avg_latency_ms"), baseline.get("latency_ms"))
        check_metric("amplitude", current_stats.get("avg_amplitude"), baseline.get("amplitude"))
        check_metric("duration_ms", current_stats.get("avg_duration_ms"), baseline.get("duration_ms"))
        check_metric("peak_velocity", current_stats.get("avg_peak_velocity"), baseline.get("peak_velocity"))

        return {
            "has_baseline": True,
            "deviations": deviations,
            "deviation_detected": len(deviations) > 0,
        }

    def get_trend(self, metric: str = "avg_latency_ms", last_n: int = 20) -> dict:
        recent = self.sessions[-last_n:]
        values = []
        timestamps = []
        for s in recent:
            val = getattr(s, metric, None)
            if val is not None:
                values.append(val)
                timestamps.append(s.timestamp)

        if len(values) < 2:
            return {"metric": metric, "trend": "insufficient_data", "values": values}

        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        slope = coeffs[0]

        if abs(slope) < np.std(values) * 0.1:
            trend = "stable"
        elif slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return {
            "metric": metric,
            "trend": trend,
            "slope": round(float(slope), 4),
            "values": [round(v, 2) for v in values],
            "timestamps": timestamps,
        }
