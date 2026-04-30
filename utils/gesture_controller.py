"""
GestureController — sliding-window inference engine.
Reads serial data, classifies gestures, and puts events on a queue.
"""

import time
import pickle
import threading
import numpy as np
import pandas as pd
from collections import deque

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from utils.feature_extraction import COLUMNS, extract_features, derive_feature_names


# ─── Config ───────────────────────────────────────────────────────────────────
WINDOW_SIZE   = 50     # samples per inference window
STEP_SIZE     = 25     # hop between windows (50% overlap)
GESTURE_HOLD  = 0.6    # seconds a gesture must persist before firing
COOLDOWN      = 1.5    # seconds between consecutive same-gesture actions
BAUD_RATE     = 115200

GESTURES = ["Extend", "Flex", "Fist_Close", "Thumbs_Up", "Thumbs_Down"]


# ─── Model loader ─────────────────────────────────────────────────────────────
def load_model(model_path, scaler_path):
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)
    feature_names = derive_feature_names()
    return model, scaler, feature_names


def list_serial_ports():
    if not SERIAL_AVAILABLE:
        return []
    return [p.device for p in serial.tools.list_ports.comports()]


# ─── Controller ───────────────────────────────────────────────────────────────
class GestureController:
    """Sliding-window gesture classifier."""

    def __init__(self, model, scaler, feature_names, event_queue):
        self.model         = model
        self.scaler        = scaler
        self.feature_names = feature_names
        self.event_queue   = event_queue

        self.buffer        = deque(maxlen=WINDOW_SIZE * 2)
        self.last_gesture  = None
        self.gesture_start = 0.0
        self.last_fired    = {}
        self.step_counter  = 0

    def push_row(self, row: list):
        if len(row) != 18:
            return
        self.buffer.append(row)
        self.step_counter += 1

        if len(self.buffer) >= WINDOW_SIZE and self.step_counter >= STEP_SIZE:
            self.step_counter = 0
            self._infer()

    def _infer(self):
        window = list(self.buffer)[-WINDOW_SIZE:]
        df     = pd.DataFrame(window, columns=COLUMNS)
        try:
            feat_dict = extract_features(df)
        except Exception:
            return

        row_vec = [feat_dict.get(col, 0.0) for col in self.feature_names]
        # Use DataFrame so scaler gets feature names → silences sklearn UserWarning
        X    = pd.DataFrame([row_vec], columns=self.feature_names)
        X_sc = self.scaler.transform(X)

        gesture = self.model.predict(X_sc)[0]
        proba   = float(self.model.predict_proba(X_sc).max())

        now = time.time()
        self.event_queue.put(("prediction", gesture, proba))

        if gesture != self.last_gesture:
            self.last_gesture  = gesture
            self.gesture_start = now
            return

        if (now - self.gesture_start) < GESTURE_HOLD:
            return
        if (now - self.last_fired.get(gesture, 0)) < COOLDOWN:
            return

        self.last_fired[gesture] = now
        self.event_queue.put(("gesture", gesture, proba))


# ─── Serial reader thread ─────────────────────────────────────────────────────
def serial_reader(port, baud, controller, stop_event, event_queue):
    if not SERIAL_AVAILABLE:
        event_queue.put(("error", "pyserial not installed"))
        return
    try:
        ser = serial.Serial(port, baud, timeout=1)
        event_queue.put(("status", f"Connected: {port} @ {baud}"))
    except Exception as e:
        event_queue.put(("error", str(e)))
        return

    while not stop_event.is_set():
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) != 18:
                continue
            row = [float(x) for x in parts]
            controller.push_row(row)
        except ValueError:
            pass
        except Exception as e:
            event_queue.put(("error", f"Serial error: {e}"))
            break

    try:
        ser.close()
    except Exception:
        pass
    event_queue.put(("status", "Disconnected"))
