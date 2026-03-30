"""Main pipeline orchestrator: ties ML, signal processing, and saccade detection together."""

import numpy as np
import time
import uuid
import cv2

from app.ml.face_detector import FaceDetector
from app.ml.gaze_estimator import GazeEstimator
from app.ml.quality_checker import QualityChecker
from app.signal.filters import GazeSignalProcessor
from app.saccade.detector import SaccadeDetector
from app.baseline.profile import UserProfile, SessionSummary


class TrackingSession:
    """A single tracking session that processes frames end-to-end."""

    def __init__(self, user_id: str = "default", mode: str = "passive",
                 screen_w: int = 1920, screen_h: int = 1080):
        self.session_id = str(uuid.uuid4())[:8]
        self.user_id = user_id
        self.mode = mode
        self.start_time = time.time()

        self.face_detector = FaceDetector()
        self.gaze_estimator = GazeEstimator(screen_w, screen_h)
        self.quality_checker = QualityChecker()
        self.signal_processor = GazeSignalProcessor()
        self.saccade_detector = SaccadeDetector()
        self.user_profile = UserProfile(user_id)

        self.frame_count = 0

    def process_frame(self, frame_bytes: bytes, width: int, height: int) -> dict:
        timestamp = time.time()
        self.frame_count += 1

        frame_rgb = self._decode_frame(frame_bytes, width, height)
        if frame_rgb is None:
            return {"error": "Failed to decode frame", "frame": self.frame_count}

        detection = self.face_detector.process_frame(frame_rgb)
        quality = self.quality_checker.check(frame_rgb, detection, None)

        if detection is None:
            return {
                "frame": self.frame_count,
                "timestamp": timestamp,
                "face_detected": False,
                "quality": quality,
                "gaze": None,
                "signal": None,
                "saccade": None,
                "fixation": None,
                "stats": self.saccade_detector.get_stats(),
            }

        h_fr, w_fr = frame_rgb.shape[:2]
        gaze = self.gaze_estimator.estimate(detection)
        signal = self.signal_processor.add_sample(
            gaze["screen_x"], gaze["screen_y"], timestamp
        )
        saccade_event = self.saccade_detector.process_sample(
            signal["filtered_x"], signal["filtered_y"],
            signal["velocity"], timestamp,
            snr=signal.get("snr", 60.0),
        )

        if quality["fps"] > 5:
            self.signal_processor.update_sampling_rate(quality["fps"])

        tracking_confidence = self._compute_tracking_confidence(quality, signal)

        # Include the most recently completed fixation in the response when
        # a new saccade has just been detected (fixation just ended).
        recent_fix = None
        if saccade_event and self.saccade_detector.fixations:
            recent_fix = self.saccade_detector.fixations[-1].to_dict()

        return {
            "frame": self.frame_count,
            "timestamp": timestamp,
            "face_detected": True,
            "quality": quality,
            "gaze": {
                "raw_x": gaze["raw_x"],
                "raw_y": gaze["raw_y"],
                "screen_x": gaze["screen_x"],
                "screen_y": gaze["screen_y"],
                "head_yaw": gaze["head_yaw"],
                "head_pitch": gaze["head_pitch"],
            },
            "iris": {
                "left_x":  float(detection["left_iris_center"][0])  / w_fr,
                "left_y":  float(detection["left_iris_center"][1])  / h_fr,
                "right_x": float(detection["right_iris_center"][0]) / w_fr,
                "right_y": float(detection["right_iris_center"][1]) / h_fr,
            },
            "signal": {
                "filtered_x": signal["filtered_x"],
                "filtered_y": signal["filtered_y"],
                "velocity": signal["velocity"],
                "snr": signal["snr"],
                "noise_level": signal["noise_level"],
            },
            "saccade": saccade_event.to_dict() if saccade_event else None,
            "fixation": recent_fix,
            "stats": self.saccade_detector.get_stats(),
            "tracking_confidence": tracking_confidence,
        }

    def add_calibration_point(self, raw_x: float, raw_y: float,
                              screen_x: float, screen_y: float):
        self.gaze_estimator.calibration.add_point(raw_x, raw_y, screen_x, screen_y)

    def apply_calibration(self) -> float:
        """Fit polynomial calibration from staged points. Returns RMS accuracy in px."""
        return self.gaze_estimator.calibration.fit()

    def set_stimulus(self, target_x: float, target_y: float,
                     expected_direction: str | None = None):
        self.saccade_detector.set_stimulus(target_x, target_y, expected_direction)

    def calibrate_center(self, raw_x: float = None, raw_y: float = None):
        if raw_x is not None:
            self.gaze_estimator.calibration.set_center(raw_x, raw_y)

    def get_recent_signal(self, n: int = 90) -> dict:
        return self.signal_processor.get_recent_signal(n)

    def get_recent_saccades(self, n: int = 10) -> list:
        return self.saccade_detector.get_recent_saccades(n)

    def get_recent_fixations(self, n: int = 20) -> list:
        return self.saccade_detector.get_recent_fixations(n)

    def end_session(self) -> dict:
        duration = time.time() - self.start_time
        stats = self.saccade_detector.get_stats()

        summary = SessionSummary(
            session_id=self.session_id,
            timestamp=self.start_time,
            duration_seconds=round(duration, 1),
            total_saccades=stats["total_saccades"],
            avg_latency_ms=stats["avg_latency_ms"],
            avg_amplitude=stats["avg_amplitude"] or 0,
            avg_duration_ms=stats["avg_duration_ms"] or 0,
            avg_peak_velocity=stats["avg_peak_velocity"] or 0,
            avg_gain=stats["avg_gain"],
            avg_signal_quality=0,
            mode=self.mode,
        )
        self.user_profile.add_session(summary)

        baseline = self.user_profile.get_baseline()
        deviation = self.user_profile.check_deviation(stats)

        self.face_detector.close()

        return {
            "session_id": self.session_id,
            "duration_seconds": round(duration, 1),
            "stats": stats,
            "baseline": baseline,
            "deviation": deviation,
            "recent_saccades": self.get_recent_saccades(20),
            "recent_fixations": self.get_recent_fixations(20),
        }

    def _compute_tracking_confidence(self, quality: dict, signal: dict) -> float:
        """Estimate how trustworthy the current gaze estimate is (0-100)."""
        if not quality.get("face_detected", False):
            return 0.0
        conf = 100.0
        if quality.get("blink_detected"):
            conf -= 20.0
        yaw = abs(quality.get("head_yaw", 0) or 0)
        if yaw > 25:
            conf -= 20.0
        elif yaw > 15:
            conf -= 10.0
        fps = quality.get("fps", 30) or 30
        if fps < 20:
            conf -= 15.0
        elif fps < 25:
            conf -= 8.0
        sq = quality.get("signal_quality") or 0
        if sq < 40:
            conf -= 20.0
        elif sq < 60:
            conf -= 10.0
        snr = signal.get("snr", 60) if signal else 60
        if snr < 15:
            conf -= 12.0
        elif snr < 25:
            conf -= 6.0
        if not self.gaze_estimator.calibration.calibrated:
            conf -= 15.0
        return round(max(0.0, min(100.0, conf)), 1)

    def _decode_frame(self, frame_bytes: bytes, width: int, height: int) -> np.ndarray | None:
        try:
            arr = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            expected_rgba = width * height * 4
            expected_rgb = width * height * 3
            if len(frame_bytes) == expected_rgba:
                frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(height, width, 4)
                return frame[:, :, :3]
            elif len(frame_bytes) == expected_rgb:
                return np.frombuffer(frame_bytes, dtype=np.uint8).reshape(height, width, 3)
        except Exception:
            return None
        return None
