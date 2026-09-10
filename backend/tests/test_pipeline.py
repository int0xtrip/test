"""Tests for the core pipeline components."""

import numpy as np
import time
import pytest


def test_signal_processor():
    from app.signal.filters import GazeSignalProcessor

    proc = GazeSignalProcessor(sampling_rate=30.0)
    t = 0.0
    for i in range(100):
        x = 500 + 50 * np.sin(2 * np.pi * 0.5 * t) + np.random.randn() * 5
        y = 400 + 30 * np.cos(2 * np.pi * 0.5 * t) + np.random.randn() * 5
        result = proc.add_sample(x, y, t)
        t += 1.0 / 30

    assert "filtered_x" in result
    assert "velocity" in result
    assert "snr" in result
    assert result["snr"] > 0

    signal = proc.get_recent_signal(30)
    assert len(signal["x"]) == 30


def test_saccade_detector():
    from app.saccade.detector import SaccadeDetector

    det = SaccadeDetector(min_velocity=20, min_amplitude=5)
    t = 0.0
    dt = 1.0 / 30
    saccades_found = []

    for i in range(30):
        x = 100 + np.random.randn() * 0.5
        y = 100 + np.random.randn() * 0.5
        result = det.process_sample(x, y, 1.0, t)
        if result:
            saccades_found.append(result)
        t += dt

    positions = [(150, 100), (250, 100), (300, 100)]
    for px, py in positions:
        result = det.process_sample(px, py, 3000.0, t)
        if result:
            saccades_found.append(result)
        t += dt

    for i in range(10):
        x = 300 + np.random.randn() * 0.5
        y = 100 + np.random.randn() * 0.5
        result = det.process_sample(x, y, 1.0, t)
        if result:
            saccades_found.append(result)
        t += dt

    assert len(saccades_found) >= 1
    s = saccades_found[0]
    assert s.direction in ("left", "right")
    assert s.amplitude > 0
    assert s.duration_ms > 0

    stats = det.get_stats()
    assert stats["total_saccades"] >= 1


def test_baseline_profile(tmp_path, monkeypatch):
    import app.baseline.profile as profile_mod
    monkeypatch.setattr(profile_mod, "DATA_DIR", tmp_path)

    from app.baseline.profile import UserProfile, SessionSummary

    prof = UserProfile("test_user")
    assert prof.get_baseline()["has_baseline"] is False

    for i in range(5):
        summary = SessionSummary(
            session_id=f"s{i}",
            timestamp=time.time() + i,
            duration_seconds=60.0,
            total_saccades=20 + i,
            avg_latency_ms=200.0 + i * 5,
            avg_amplitude=50.0 + i * 2,
            avg_duration_ms=40.0 + i,
            avg_peak_velocity=300.0 + i * 10,
            avg_gain=0.95 + i * 0.01,
            avg_signal_quality=80.0,
            mode="guided",
        )
        prof.add_session(summary)

    baseline = prof.get_baseline()
    assert baseline["has_baseline"] is True
    assert baseline["sessions_count"] == 5
    assert baseline["latency_ms"]["mean"] > 0

    normal_stats = {"avg_latency_ms": 210.0, "avg_amplitude": 54.0, "avg_duration_ms": 42.0, "avg_peak_velocity": 320.0}
    dev = prof.check_deviation(normal_stats)
    assert dev["has_baseline"] is True

    abnormal_stats = {"avg_latency_ms": 500.0, "avg_amplitude": 54.0, "avg_duration_ms": 42.0, "avg_peak_velocity": 320.0}
    dev = prof.check_deviation(abnormal_stats)
    assert dev["deviation_detected"] is True


def test_quality_checker():
    from app.ml.quality_checker import QualityChecker

    qc = QualityChecker()

    frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    detection = {
        "head_yaw": 5.0, "head_pitch": 3.0,
        "left_ear": 0.3, "right_ear": 0.3,
    }
    result = qc.check(frame, detection, None)
    assert result["face_detected"] is True
    assert result["lighting_ok"] is True
    assert result["signal_quality"] > 50

    dark_frame = np.ones((480, 640, 3), dtype=np.uint8) * 20
    result = qc.check(dark_frame, None, None)
    assert result["face_detected"] is False
    assert result["lighting_ok"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
