# Oculometry - Webcam-Based Eye Tracking

Real-time eye tracking and saccade analysis using a standard webcam. Privacy-first, all processing runs locally.

## Architecture

```
Frontend (React + Vite)        Backend (FastAPI + Python)
┌─────────────────────┐       ┌──────────────────────────────┐
│ Webcam capture       │       │ ML Pipeline                  │
│ WebSocket client     │◄─────►│  ├─ Face Detection (MediaPipe)│
│ Real-time UI         │  WS   │  ├─ Iris Tracking            │
│ Gaze visualization   │       │  ├─ Head Pose (solvePnP)     │
│ Guided test mode     │       │  └─ Gaze Estimation          │
│ Stats dashboard      │       │ Signal Processing            │
└─────────────────────┘       │  ├─ Butterworth Filter       │
                               │  ├─ Noise/SNR Estimation     │
                               │  └─ Adaptive Smoothing       │
                               │ Saccade Detection            │
                               │  ├─ Adaptive Threshold       │
                               │  ├─ Velocity-based           │
                               │  └─ Latency/Gain/Amplitude   │
                               │ Baseline Profile System      │
                               └──────────────────────────────┘
```

## Data Flow

```
Camera Frame (JPEG) → WebSocket → Face Detection → Iris Tracking →
Head Pose Compensation → Gaze Estimation → Butterworth Filter →
Velocity Computation → Saccade Detection → Metrics → Frontend
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Webcam

### Setup

```bash
chmod +x setup.sh
./setup.sh
```

### Run

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python run.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:3000**

## Features

### Modes

1. **Passive Mode** - Tracks gaze during normal screen use. Detects natural saccades without requiring explicit tests.

2. **Guided Test Mode** - Displays target dots that move across the screen. Measures saccade latency, gain, amplitude in response to stimuli.

### Adaptive Calibration

- Quick center alignment (optional, one click)
- Continuous calibration refinement over time
- No forced multi-point calibration required
- Head pose compensation built-in

### Environment Quality Monitoring

Real-time feedback on:
- Face detection status
- Lighting conditions
- Head position/alignment
- FPS performance
- Signal quality score (0-100%)

### Personal Baseline System

- Stores metrics locally in `~/.oculometry/profiles/`
- Builds baseline across sessions
- Detects significant deviations (z-score > 2.0)
- Tracks trends over time

### Saccade Metrics

| Metric | Description |
|--------|-------------|
| Latency | Time from stimulus to saccade onset (guided mode) |
| Amplitude | Distance of eye movement (pixels) |
| Duration | Saccade duration (ms) |
| Peak Velocity | Maximum velocity during saccade (px/s) |
| Gain | Ratio of actual vs target amplitude |
| Direction | left/right/up/down |

### Privacy

- All processing runs locally (Python + browser)
- No cloud services, no data upload
- Video frames never stored to disk
- Profile data stored locally only

## Testing

### Run Backend Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

### Manual Testing with Webcam

1. Start the system (see Quick Start)
2. Allow camera access when prompted
3. Position your face in the oval guide
4. Check quality indicators are green
5. Try passive mode first - move your eyes left/right rapidly
6. Switch to guided mode - follow the target dot
7. Check the stats panel for saccade metrics
8. Stop tracking to see the session summary

### Expected Behavior

- **Face detection**: Green indicator when face is visible and centered
- **Gaze plot**: Shows horizontal gaze position over time as a blue trace
- **Saccade detection**: Red highlights on the gaze plot when saccades are detected
- **Latency**: In guided mode, expect 150-300ms saccade latency to stimulus
- **Signal quality**: Should be 60-90% in good conditions

### Example Scenarios

| Scenario | Expected |
|----------|----------|
| Look left then right quickly | Saccade detected, ~100-200px amplitude |
| Follow guided test targets | Latency ~200ms, gain ~0.9-1.1 |
| Blink | Brief face quality dip, recovers immediately |
| Turn head sideways | Head position warning, signal quality drops |
| Poor lighting | Lighting warning, lower signal quality |

## Project Structure

```
oculometry/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, WebSocket endpoints
│   │   ├── pipeline.py          # Orchestrates ML → signal → saccade
│   │   ├── ml/
│   │   │   ├── face_detector.py # MediaPipe face mesh + iris
│   │   │   ├── gaze_estimator.py# Adaptive calibration + gaze
│   │   │   └── quality_checker.py# Environment quality assessment
│   │   ├── signal/
│   │   │   └── filters.py       # Butterworth filter, noise/SNR
│   │   ├── saccade/
│   │   │   └── detector.py      # Adaptive threshold saccade detection
│   │   └── baseline/
│   │       └── profile.py       # User baseline + deviation detection
│   ├── tests/
│   │   └── test_pipeline.py
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main application
│   │   ├── main.jsx             # Entry point
│   │   ├── components/
│   │   │   ├── WebcamView.jsx   # Camera feed + quality indicators
│   │   │   ├── GazePlot.jsx     # Real-time gaze visualization
│   │   │   ├── StatsPanel.jsx   # Session statistics
│   │   │   ├── SaccadeList.jsx  # Detected saccade events
│   │   │   └── GuidedTest.jsx   # Guided saccade test UI
│   │   ├── hooks/
│   │   │   ├── useWebcam.js     # Webcam access hook
│   │   │   └── useWebSocket.js  # WebSocket connection hook
│   │   └── styles/
│   │       └── global.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── setup.sh
└── README.md
```

## Future Improvements

- **Higher accuracy gaze**: Train a small CNN/transformer on gaze estimation datasets (MPIIGaze, GazeCapture)
- **60 FPS support**: Optimize pipeline for higher frame rates with GPU acceleration
- **Smooth pursuit detection**: Detect slow tracking eye movements in addition to saccades
- **Microsaccade detection**: Higher temporal resolution for microsaccade analysis
- **Multi-monitor support**: Calibration across multiple displays
- **Export data**: CSV/JSON export for research analysis
- **Electron wrapper**: Package as a standalone desktop app
- **ONNX model**: Replace MediaPipe with a custom ONNX model for better performance
- **Pupil dilation tracking**: Add pupil size tracking for cognitive load estimation
- **Vergence tracking**: Binocular vergence for depth-of-focus estimation

## Technical Notes

### Saccade Detection Algorithm

Uses adaptive velocity thresholding:
1. During fixation, accumulates velocity statistics (rolling window)
2. Threshold = mean + k * std (k=3.0 by default)
3. Onset: velocity exceeds threshold
4. Offset: velocity drops below 70% of threshold
5. Validates: min duration (15ms), min amplitude (10px), max duration (200ms)

### Head Pose Compensation

Uses cv2.solvePnP with 6 facial landmarks mapped to a generic 3D face model. The resulting yaw/pitch angles are used to compensate iris-based gaze estimates, reducing error from head rotation.

### Signal Quality Score

Composite score (0-100) based on:
- Face detection (30 pts)
- Lighting adequacy (20 pts)
- Head alignment (20 pts)
- FPS performance (15 pts)
- Eye openness / iris visibility (15 pts)
