"""FastAPI application with WebSocket for real-time eye tracking."""

import asyncio
import base64
import json
import logging
import time
import traceback

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.pipeline import TrackingSession
from app.baseline.profile import UserProfile

logger = logging.getLogger("oculometry")
logging.basicConfig(level=logging.INFO)


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def safe_json(data: dict) -> str:
    """Serialize dict to JSON, handling numpy types."""
    return json.dumps(data, cls=NumpyEncoder)


app = FastAPI(title="Oculometry - Webcam Eye Tracking", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, TrackingSession] = {}


@app.get("/")
def root():
    return {"status": "ok", "service": "oculometry", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


class SessionConfig(BaseModel):
    user_id: str = "default"
    mode: str = "passive"
    screen_w: int = 1920
    screen_h: int = 1080


@app.post("/api/session/start")
def start_session(config: SessionConfig):
    session = TrackingSession(
        user_id=config.user_id,
        mode=config.mode,
        screen_w=config.screen_w,
        screen_h=config.screen_h,
    )
    sessions[session.session_id] = session
    return {"session_id": session.session_id, "status": "started"}


@app.post("/api/session/{session_id}/end")
def end_session(session_id: str):
    session = sessions.pop(session_id, None)
    if not session:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    summary = session.end_session()
    return summary


@app.get("/api/profile/{user_id}/baseline")
def get_baseline(user_id: str):
    profile = UserProfile(user_id)
    return profile.get_baseline()


@app.get("/api/profile/{user_id}/trend/{metric}")
def get_trend(user_id: str, metric: str):
    profile = UserProfile(user_id)
    return profile.get_trend(metric)


@app.websocket("/ws/track/{session_id}")
async def websocket_track(websocket: WebSocket, session_id: str):
    await websocket.accept()

    session = sessions.get(session_id)
    if not session:
        await websocket.send_json({"error": "Session not found"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "frame")

            if msg_type == "frame":
                frame_b64 = msg["frame"]
                frame_bytes = base64.b64decode(frame_b64)
                width = msg.get("width", 640)
                height = msg.get("height", 480)
                result = session.process_frame(frame_bytes, width, height)
                await websocket.send_text(safe_json(result))

            elif msg_type == "calibrate_center":
                session.calibrate_center(msg.get("raw_x"), msg.get("raw_y"))
                await websocket.send_text(safe_json({"type": "calibrated", "status": "ok"}))

            elif msg_type == "stimulus":
                session.set_stimulus(msg["target_x"], msg["target_y"])
                await websocket.send_text(safe_json({"type": "stimulus_ack"}))

            elif msg_type == "get_signal":
                signal = session.get_recent_signal(msg.get("n", 90))
                await websocket.send_text(safe_json({"type": "signal_data", "data": signal}))

            elif msg_type == "get_saccades":
                saccades = session.get_recent_saccades(msg.get("n", 10))
                await websocket.send_text(safe_json({"type": "saccade_data", "data": saccades}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}\n{traceback.format_exc()}")
        try:
            await websocket.send_text(safe_json({"error": str(e)}))
        except Exception:
            pass


@app.websocket("/ws/track_simple")
async def websocket_track_simple(websocket: WebSocket):
    await websocket.accept()

    session = TrackingSession()
    sid = session.session_id
    sessions[sid] = session

    await websocket.send_text(safe_json({"type": "session_created", "session_id": sid}))

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "frame")

            if msg_type == "frame":
                frame_bytes = base64.b64decode(msg["frame"])
                width = msg.get("width", 640)
                height = msg.get("height", 480)
                result = session.process_frame(frame_bytes, width, height)
                await websocket.send_text(safe_json(result))

            elif msg_type == "calibrate_center":
                session.calibrate_center(msg.get("raw_x"), msg.get("raw_y"))
                await websocket.send_text(safe_json({"type": "calibrated"}))

            elif msg_type == "stimulus":
                session.set_stimulus(msg["target_x"], msg["target_y"])
                await websocket.send_text(safe_json({"type": "stimulus_ack"}))

            elif msg_type == "end":
                summary = session.end_session()
                await websocket.send_text(safe_json({"type": "session_ended", **summary}))
                break

    except WebSocketDisconnect:
        if sid in sessions:
            sessions[sid].end_session()
            del sessions[sid]
    except Exception as e:
        logger.error(f"WebSocket error: {e}\n{traceback.format_exc()}")
        try:
            await websocket.send_text(safe_json({"error": str(e)}))
        except Exception:
            pass
