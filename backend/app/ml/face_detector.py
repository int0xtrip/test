"""Face detection and landmark extraction using MediaPipe."""

import os
import urllib.request
import numpy as np


# MediaPipe FaceMesh landmark indices for key regions
LEFT_EYE_IDX = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE_IDX = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
LEFT_IRIS_IDX = [468, 469, 470, 471, 472]
RIGHT_IRIS_IDX = [473, 474, 475, 476, 477]
NOSE_TIP_IDX = 1
CHIN_IDX = 152
LEFT_EYE_OUTER = 33
RIGHT_EYE_OUTER = 263
LEFT_EYE_INNER = 133
RIGHT_EYE_INNER = 362
FOREHEAD_IDX = 10

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")


def _ensure_model():
    """Download the face landmarker model if not present."""
    if os.path.exists(MODEL_PATH):
        return
    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"Downloading face landmarker model to {MODEL_PATH}...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Download complete.")


def _has_solutions_api():
    """Check if the legacy mp.solutions API is available."""
    try:
        import mediapipe as mp
        _ = mp.solutions.face_mesh
        return True
    except AttributeError:
        return False


class FaceDetector:
    """Detects face, extracts landmarks, iris positions, and head pose."""

    def __init__(self, max_faces: int = 1, refine_landmarks: bool = True):
        self._use_tasks_api = not _has_solutions_api()

        if self._use_tasks_api:
            self._init_tasks_api(max_faces)
        else:
            self._init_solutions_api(max_faces, refine_landmarks)

    def _init_solutions_api(self, max_faces, refine_landmarks):
        """Initialize using the legacy mp.solutions API."""
        import mediapipe as mp
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def _init_tasks_api(self, max_faces):
        """Initialize using the new mediapipe tasks API."""
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        _ensure_model()

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=max_faces,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)

    def process_frame(self, frame_rgb: np.ndarray) -> dict | None:
        """Process a single RGB frame. Returns detection result or None."""
        if self._use_tasks_api:
            return self._process_tasks(frame_rgb)
        else:
            return self._process_solutions(frame_rgb)

    def _process_solutions(self, frame_rgb: np.ndarray) -> dict | None:
        """Process frame using legacy solutions API."""
        h, w, _ = frame_rgb.shape
        results = self.face_mesh.process(frame_rgb)

        if not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0]
        pts = np.array([(lm.x * w, lm.y * h, lm.z * w) for lm in landmarks.landmark])
        return self._extract_features(pts, w, h)

    def _process_tasks(self, frame_rgb: np.ndarray) -> dict | None:
        """Process frame using new tasks API."""
        import mediapipe as mp

        h, w, _ = frame_rgb.shape
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self.landmarker.detect(mp_image)

        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]
        pts = np.array([(lm.x * w, lm.y * h, lm.z * w) for lm in landmarks])
        return self._extract_features(pts, w, h)

    def _extract_features(self, pts: np.ndarray, w: int, h: int) -> dict | None:
        """Extract gaze, iris, head pose features from landmark points."""
        if len(pts) < 478:
            # Need iris landmarks (indices 468-477)
            return None

        left_eye = pts[LEFT_EYE_IDX]
        right_eye = pts[RIGHT_EYE_IDX]
        left_iris = pts[LEFT_IRIS_IDX]
        right_iris = pts[RIGHT_IRIS_IDX]

        left_iris_center = left_iris.mean(axis=0)
        right_iris_center = right_iris.mean(axis=0)

        left_eye_center = left_eye.mean(axis=0)
        right_eye_center = right_eye.mean(axis=0)

        # Relative iris position within eye bounding box (normalized 0-1)
        left_iris_rel = self._iris_relative_position(left_eye, left_iris_center)
        right_iris_rel = self._iris_relative_position(right_eye, right_iris_center)

        # Average gaze direction (normalized)
        gaze_x = (left_iris_rel[0] + right_iris_rel[0]) / 2.0
        gaze_y = (left_iris_rel[1] + right_iris_rel[1]) / 2.0

        head_pose = self._estimate_head_pose(pts, w, h)

        # Eye aspect ratio for blink detection
        left_ear = self._eye_aspect_ratio(pts, LEFT_EYE_IDX)
        right_ear = self._eye_aspect_ratio(pts, RIGHT_EYE_IDX)

        return {
            "landmarks": pts,
            "left_eye": left_eye,
            "right_eye": right_eye,
            "left_iris_center": left_iris_center,
            "right_iris_center": right_iris_center,
            "left_eye_center": left_eye_center,
            "right_eye_center": right_eye_center,
            "left_iris_rel": left_iris_rel,
            "right_iris_rel": right_iris_rel,
            "gaze_x": float(gaze_x),
            "gaze_y": float(gaze_y),
            "head_yaw": float(head_pose[0]),
            "head_pitch": float(head_pose[1]),
            "head_roll": float(head_pose[2]),
            "left_ear": float(left_ear),
            "right_ear": float(right_ear),
            "face_detected": True,
        }

    def _iris_relative_position(self, eye_pts: np.ndarray, iris_center: np.ndarray) -> tuple:
        """Compute iris position relative to eye bounding box (0-1 range)."""
        eye_min = eye_pts[:, :2].min(axis=0)
        eye_max = eye_pts[:, :2].max(axis=0)
        eye_range = eye_max - eye_min
        eye_range = np.maximum(eye_range, 1e-6)

        rel = (iris_center[:2] - eye_min) / eye_range
        return (float(np.clip(rel[0], 0, 1)), float(np.clip(rel[1], 0, 1)))

    def _estimate_head_pose(self, pts: np.ndarray, w: int, h: int) -> tuple:
        """Estimate head pose (yaw, pitch, roll) from landmarks using solvePnP."""
        import cv2

        model_points = np.array([
            (0.0, 0.0, 0.0),
            (0.0, -330.0, -65.0),
            (-225.0, 170.0, -135.0),
            (225.0, 170.0, -135.0),
            (-150.0, -150.0, -125.0),
            (150.0, -150.0, -125.0),
        ], dtype=np.float64)

        image_points = np.array([
            pts[NOSE_TIP_IDX][:2],
            pts[CHIN_IDX][:2],
            pts[LEFT_EYE_OUTER][:2],
            pts[RIGHT_EYE_OUTER][:2],
            pts[61][:2],
            pts[291][:2],
        ], dtype=np.float64)

        focal_length = w
        center = (w / 2, h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        success, rotation_vector, _ = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs
        )
        if not success:
            return (0.0, 0.0, 0.0)

        rotation_mat, _ = cv2.Rodrigues(rotation_vector)
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_mat)

        return (angles[1], angles[0], angles[2])

    def _eye_aspect_ratio(self, pts: np.ndarray, eye_idx: list) -> float:
        """Compute Eye Aspect Ratio (EAR) for blink detection."""
        p = pts[eye_idx]
        v1 = np.linalg.norm(p[1] - p[5])
        v2 = np.linalg.norm(p[2] - p[4])
        h1 = np.linalg.norm(p[0] - p[3])
        if h1 < 1e-6:
            return 0.0
        return (v1 + v2) / (2.0 * h1)

    def close(self):
        if self._use_tasks_api:
            self.landmarker.close()
        else:
            self.face_mesh.close()
