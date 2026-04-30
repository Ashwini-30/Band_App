"""
FMG Gesture Classifier — CNN + 5-Gesture Calibration Prior
Exact logic ported from the tkinter GUI code.
Serial format: roll,pitch,yaw,ax,ay,az,gx,gy,gz,mx,my,mz,fsr1..fsr6  (18 values)
"""

import os
import sys
import time
import queue
import threading
import numpy as np
import joblib

# ── Serial is always imported ───────────────────────────────────
import serial
import serial.tools.list_ports

# ── TensorFlow is optional ──────────────────────────────────────
try:
    from tensorflow.keras.models import load_model as keras_load
    TF_OK = True
except Exception as e:
    print(f"⚠️  TensorFlow unavailable: {e}")
    TF_OK = False

# ─────────────────────────────── CONFIG ────────────────────────
BASE            = "/Users/ashwini/Documents/codes/GestureControl/CNNModels"
MODEL_NAME      = "GRU"
CNN_MODEL_PATH  = os.path.join(BASE, f"{MODEL_NAME}_model.h5")
CNN_SCALER_PATH = os.path.join(BASE, f"{MODEL_NAME}_scaler.pkl")
CNN_LE_PATH     = os.path.join(BASE, f"{MODEL_NAME}_le.pkl")

BAUD_RATE      = 115200
WINDOW_SIZE    = 50
HISTORY        = 300
BASE_CAL_S     = 5
GEST_CAL_S     = 4
POST_OFF_COUNT = 6
MAX_GEST_SAMP  = 300

CAL_GESTURES = ["Extend", "Flex", "Fist_Close", "Thumbs_Up", "Thumbs_Down"]


# ─────────────────────────── CNN CLASSIFIER ────────────────────
# Exactly matches the CNNClassifier from the provided tkinter code.
class CNNClassifier:
    def __init__(self, model, scaler, le, proto_weight=0.35):
        self.model        = model
        self.scaler       = scaler
        self.le           = le
        self.proto_weight = proto_weight
        self.prototypes   = {}   # label -> (WINDOW_SIZE, 18) preprocessed array

    def _scale(self, buf):
        if self.scaler is not None:
            try:
                return self.scaler.transform(buf)
            except Exception:
                pass
        return (buf - buf.mean(0)) / (buf.std(0) + 1e-8)

    def _best_window(self, arr):
        """arr: (N,18) float array -> (WINDOW_SIZE,18) scaled"""
        if len(arr) < WINDOW_SIZE:
            return None
        fsr_sum = arr[:, 12:18].sum(axis=1)
        if len(arr) > WINDOW_SIZE:
            kernel = np.ones(WINDOW_SIZE) / WINDOW_SIZE
            scores = np.convolve(fsr_sum, kernel, mode="valid")
            s = int(np.argmax(scores))
        else:
            s = 0
        return self._scale(arr[s:s + WINDOW_SIZE].copy())

    def add_prototype(self, label, rows):
        arr = np.array(rows, dtype=float)
        buf = self._best_window(arr)
        if buf is None:
            return False
        if label in self.prototypes:
            self.prototypes[label] = (self.prototypes[label] + buf) / 2.0
        else:
            self.prototypes[label] = buf   # shape (WINDOW_SIZE, 18)
        return True

    def _cosine(self, a, b):
        a = a.reshape(-1); b = b.reshape(-1)
        if a.shape != b.shape:
            return 0.0
        a = a - a.mean(); b = b - b.mean()
        return max(0.0, float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)))

    def predict(self, rows):
        """Returns (best_label, best_conf, cnn_label, cnn_conf, proto_scores) or None."""
        arr = np.array(rows, dtype=float)
        buf = self._best_window(arr)
        if buf is None or self.model is None:
            return None

        preds    = self.model.predict(buf[np.newaxis], verbose=0)[0]
        idx      = int(np.argmax(preds))
        cnn_conf = float(preds[idx])
        try:
            cnn_label = str(self.le.inverse_transform([idx])[0])
        except Exception:
            cnn_label = str(idx)

        if not self.prototypes:
            return cnn_label, cnn_conf, cnn_label, cnn_conf, {}

        proto_scores = {lab: self._cosine(buf, proto)
                        for lab, proto in self.prototypes.items()}

        labels = list(self.le.classes_) if self.le else list(self.prototypes.keys())
        merged = {}
        for i, lab in enumerate(labels):
            base = float(preds[i]) if i < len(preds) else 0.0
            sim  = proto_scores.get(lab, 0.0)
            merged[lab] = base * (1 - self.proto_weight) + sim * self.proto_weight

        best_label = max(merged, key=merged.get)
        best_conf  = float(merged[best_label])
        return best_label, best_conf, cnn_label, cnn_conf, proto_scores


# ────────────────────────── SERIAL READER ──────────────────────
class SerialReader:
    def __init__(self, port, baud, q):
        self.q     = q
        self._stop = threading.Event()
        self._t    = threading.Thread(target=self._run, args=(port, baud), daemon=True)

    def start(self): self._t.start()
    def stop(self):  self._stop.set()

    def _run(self, port, baud):
        try:
            ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2)
            ser.reset_input_buffer()
            self.q.put(("status", f"Connected: {port} @ {baud}"))
        except Exception as e:
            self.q.put(("error", str(e)))
            return
        while not self._stop.is_set():
            try:
                line  = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) != 18:
                    continue
                self.q.put(("data", [float(x) for x in parts]))
            except Exception:
                continue
        ser.close()


# ────────────────────────── WEB GESTURE ENGINE ─────────────────
class WebGestureEngine:
    """
    Web-facing version of GestureUI logic.
    Runs a background polling thread; emits SocketIO events to the browser.
    """
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.socketio = None

        # ── load model ──
        cnn_model = cnn_scaler = cnn_le = None
        try:
            cnn_model = keras_load(CNN_MODEL_PATH)
            print(f"✅ Model loaded [{MODEL_NAME}]")
        except Exception as e:
            print(f"⚠️  Model: {e}")
        try:
            cnn_scaler = joblib.load(CNN_SCALER_PATH)
            print("✅ Scaler loaded")
        except Exception as e:
            print(f"⚠️  Scaler: {e}")
        try:
            cnn_le = joblib.load(CNN_LE_PATH)
            print(f"✅ LabelEncoder: {list(cnn_le.classes_)}")
        except Exception as e:
            print(f"⚠️  LabelEncoder: {e}")

        self.clf       = CNNClassifier(cnn_model, cnn_scaler, cnn_le, proto_weight=0.35)
        self.model_ok  = cnn_model is not None

        # ── runtime state (mirrors GestureUI.__init__) ──
        self.q          = queue.Queue()
        self.reader     = None
        self.connected  = False
        self._running   = True

        self.calibrating  = False
        self.calib_mode   = "base"
        self.calib_buf    = []
        self.base_buf     = []
        self.calibrated   = False
        self.baseline_fsr = np.zeros(6)
        self.thr_on_sum   = 0.0
        self.thr_off_sum  = 0.0
        self.proto_count  = {g: 0 for g in CAL_GESTURES}

        self.sample_n        = 0
        self.latest_fsr      = np.zeros(6)
        self.latest_rpy      = [0.0, 0.0, 0.0]
        self._gest_active    = False
        self._gest_buf       = []
        self._off_count      = 0
        self._span_start_abs = None
        self._span_end_abs   = None

        # calibration timer state
        self._cal_t0       = 0.0
        self._cal_duration = 0.0
        self._cal_timer_t  = None   # threading.Timer for finish

        # Start background polling thread
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        # Start calibration progress ticker thread
        self._cal_tick_thread = threading.Thread(target=self._cal_tick_loop, daemon=True)
        self._cal_tick_thread.start()

    def set_socketio(self, sio):
        self.socketio = sio

    # ── connection ──────────────────────────────────────────────
    def connect_port(self, port):
        if self.connected:
            return
        self.q = queue.Queue()
        self.reader = SerialReader(port, BAUD_RATE, self.q)
        self.reader.start()
        self.connected = True
        self._emit("log", {"msg": f"Connecting → {port}"})

    def disconnect_port(self):
        if not self.connected:
            return
        if self.reader:
            self.reader.stop()
        self.connected = False
        self._emit("status", {"msg": "Disconnected"})
        self._emit("log",    {"msg": "Disconnected"})

    def get_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    # ── calibration ─────────────────────────────────────────────
    def start_calibration(self, label):
        if self.calibrating:
            return
        self.calibrating = True
        self.calib_mode  = label
        if label == "base":
            self.base_buf = []
            duration = BASE_CAL_S
        else:
            self.calib_buf = []
            duration = GEST_CAL_S

        self._cal_t0       = time.time()
        self._cal_duration = duration

        self._emit("log", {"msg": f"⏺  Recording {label}..."})
        self._emit("calibration_start", {"mode": label, "duration": duration})

        # Cancel old timer if any
        if self._cal_timer_t and self._cal_timer_t.is_alive():
            self._cal_timer_t.cancel()
        self._cal_timer_t = threading.Timer(duration, self._finish_cal)
        self._cal_timer_t.start()

    def _cal_tick_loop(self):
        """Emits progress updates every 100ms while calibrating."""
        while self._running:
            if self.calibrating and self._cal_duration > 0:
                elapsed = time.time() - self._cal_t0
                pct     = min(100.0, elapsed / self._cal_duration * 100.0)
                rem     = max(0, int(self._cal_duration - elapsed))
                self._emit("calibration_progress", {
                    "mode":     self.calib_mode,
                    "pct":      pct,
                    "rem":      rem,
                    "duration": self._cal_duration,
                })
            time.sleep(0.10)

    def _finish_cal(self):
        self.calibrating = False

        if self.calib_mode == "base":
            arr = np.array(self.base_buf)
            if len(arr) < 10:
                self._emit("log", {"msg": "⚠ Too few samples — retry baseline"})
                self._emit("calibration_done", {"mode": "base", "error": "too_few_samples"})
                return

            fsr  = arr[:, 12:18]
            self.baseline_fsr = np.mean(fsr, axis=0)
            sums = fsr.sum(axis=1)
            mu   = float(sums.mean())
            sig  = float(sums.std()) + 1e-6
            self.thr_on_sum  = mu + 3.0 * sig
            self.thr_off_sum = mu + 1.0 * sig
            self.calibrated  = True

            msg = f"Baseline done — on>{self.thr_on_sum:.1f}  off<{self.thr_off_sum:.1f}"
            self._emit("log", {"msg": msg})
            self._emit("calibration_done", {
                "mode":         "base",
                "thr_on":       self.thr_on_sum,
                "thr_off":      self.thr_off_sum,
                "baseline_fsr": self.baseline_fsr.tolist(),
                "mu":           mu,
                "sig":          sig,
            })
            return

        # ── gesture prototype ──
        label = self.calib_mode
        ok    = self.clf.add_prototype(label, self.calib_buf)
        if not ok:
            self._emit("log", {"msg": f"⚠ Too few samples for {label}"})
            self._emit("calibration_done", {"mode": label, "error": "too_few_samples"})
            return

        self.proto_count[label] += 1
        msg = f"Prototype → {label}  ({len(self.calib_buf)} samples, set #{self.proto_count[label]})"
        self._emit("log", {"msg": msg})
        self._emit("calibration_done", {
            "mode":     label,
            "count":    self.proto_count[label],
            "all_done": all(self.proto_count[g] > 0 for g in CAL_GESTURES),
        })

    # ── background poll loop (mirrors GestureUI._poll) ──────────
    def _poll_loop(self):
        while self._running:
            batch_data = []
            for _ in range(80):
                if self.q.empty():
                    break
                try:
                    kind, payload = self.q.get_nowait()
                except queue.Empty:
                    break

                if kind == "status":
                    self._emit("status", {"msg": payload})
                    self._emit("log",    {"msg": payload})
                elif kind == "error":
                    self._emit("log",    {"msg": f"ERROR: {payload}"})
                    self._emit("status", {"msg": f"Error: {payload}"})
                    self.connected = False
                elif kind == "data":
                    self._process(payload)
                    batch_data.append(payload)

            if batch_data:
                self._emit("stream_data", {
                    "data":       batch_data,
                    "calibrated": self.calibrated,
                    "thr_on":     self.thr_on_sum,
                    "thr_off":    self.thr_off_sum,
                })

            time.sleep(0.03)

    # ── process one incoming row (mirrors GestureUI._process) ────
    def _process(self, vals):
        v       = np.array(vals, dtype=float)
        fsr     = v[12:18]
        fsr_sum = float(fsr.sum())

        # feed calibration buffers
        if self.calibrating:
            if self.calib_mode == "base":
                self.base_buf.append(vals)
            else:
                self.calib_buf.append(vals)

        # update latest readings
        self.latest_fsr = fsr.copy()
        self.latest_rpy = [float(v[0]), float(v[1]), float(v[2])]
        self.sample_n  += 1

        if not self.calibrated:
            return

        # emit live FSR sum info
        self._emit("fsr_sum", {
            "sum":     fsr_sum,
            "thr_on":  self.thr_on_sum,
            "thr_off": self.thr_off_sum,
        })

        # ── windowing state machine (exactly matches tkinter code) ──
        if not self._gest_active:
            if fsr_sum > self.thr_on_sum:
                self._gest_active    = True
                self._gest_buf       = [vals]
                self._off_count      = 0
                self._span_start_abs = self.sample_n
                self._span_end_abs   = None
                self._emit("window_event", {"type": "open", "sum": fsr_sum})
                self._emit("log", {"msg": f"Window OPEN  sum={fsr_sum:.2f}"})
        else:
            self._gest_buf.append(vals)
            self._off_count = self._off_count + 1 if fsr_sum < self.thr_off_sum else 0

            close = (
                (self._off_count >= POST_OFF_COUNT and len(self._gest_buf) >= WINDOW_SIZE)
                or len(self._gest_buf) >= MAX_GEST_SAMP
            )

            if close:
                win_copy          = list(self._gest_buf)
                self._gest_active = False
                self._gest_buf    = []
                self._off_count   = 0
                self._span_end_abs = self.sample_n
                self._emit("window_event", {"type": "classifying"})

                try:
                    result = self.clf.predict(win_copy)
                except Exception as e:
                    self._emit("log", {"msg": f"Predict error: {e}"})
                    result = None

                if result:
                    label, conf, cnn_label, cnn_conf, proto_sc = result
                    # ── emit gesture → triggers handleGesture on ALL pages ──
                    self._emit("gesture", {
                        "gesture":    label,
                        "confidence": conf,
                        "cnn_label":  cnn_label,
                        "cnn_conf":   cnn_conf,
                        "proto_scores": {k: float(v) for k, v in proto_sc.items()},
                    })
                    log_msg = f"→ {label}  final={conf:.2f}  CNN={cnn_label}:{cnn_conf:.2f}"
                    self._emit("log", {"msg": log_msg})
                    self._emit("window_event", {"type": "idle"})
                else:
                    self._emit("window_event", {"type": "idle"})

    # ── helper ──────────────────────────────────────────────────
    def _emit(self, event, data):
        if self.socketio:
            try:
                self.socketio.emit(event, data)
            except Exception:
                pass
