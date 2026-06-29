"""
FMG Gesture Classifier — ExtraTrees + GRU + Calibration Prototypes
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

# TensorFlow is imported lazily inside WebGestureEngine._load_model_async()
# after Flask server starts to avoid thread deadlock and slow server startup.


# ─────────────────────────────── CONFIG ────────────────────────
BASE            = "/Users/ashwini/Documents/codes/GestureControl/CNNModels"
MODEL_NAME      = "GRU"
CNN_MODEL_PATH  = os.path.join(BASE, f"{MODEL_NAME}_model.h5")
CNN_SCALER_PATH = os.path.join(BASE, f"{MODEL_NAME}_scaler.pkl")
CNN_LE_PATH     = os.path.join(BASE, f"{MODEL_NAME}_le.pkl")

# ── ExtraTrees PKL paths (primary classifier — no TF dependency) ──
PROJECT_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET_MODEL_PATH   = os.path.join(PROJECT_ROOT, "extra_trees_model.pkl")
ET_SCALER_PATH  = os.path.join(PROJECT_ROOT, "scalers.pkl")

BAUD_RATE      = 115200
WINDOW_SIZE    = 30   # Reduced from 50 → tighter window for low-amplitude Flex/Extend
HISTORY        = 300
BASE_CAL_S     = 5
GEST_CAL_S     = 4
POST_OFF_COUNT = 6
MAX_GEST_SAMP  = 300

# ── Adaptive window parameters (chosen by opening-frame FSR amplitude) ──
# Fist_Close has the highest amplitude → longest window.
# Thumbs_Up/Down are moderate → medium window.
# Flex/Extend are low-amplitude → shortest window so they close fast and
# don't accumulate noise that looks like Thumbs_Up.
#
# Tiers are selected by comparing opening fsr_sum to calibrated thresholds:
#   HIGH  : fsr_sum > thr_on_sum * HIGH_AMP_RATIO   → Fist_Close tier
#   MED   : fsr_sum > thr_on_sum * MED_AMP_RATIO    → Thumbs tier
#   LOW   : everything below                         → Flex/Extend tier
HIGH_AMP_RATIO  = 2.0   # Lowered from 2.5 → Fist_Close stays HIGH more reliably
MED_AMP_RATIO   = 1.3   # Lowered from 1.5 → Thumbs correctly land in MED, not LOW

# (post_off_count, max_gest_samp) per tier
WIN_PARAMS_HIGH = (10, 300)   # Fist_Close — longest
WIN_PARAMS_MED  = (6,  150)   # Thumbs_Up / Thumbs_Down — medium
WIN_PARAMS_LOW  = (3,   60)   # Flex / Extend — very short, closes fast

# Calibration prototype weight — how much real-time calib data influences result
# 0.0 = fully rely on model, 1.0 = fully rely on prototypes
PROTO_WEIGHT   = 0.60

CAL_GESTURES = ["Extend", "Flex", "Fist_Close", "Thumbs_Up", "Thumbs_Down"]

# Feature column order — MUST match the training pipeline exactly
# Training used FSR_1..FSR_6 (with underscore), not FSR1..FSR6
_COLUMNS = [
    "Roll", "Pitch", "Yaw",
    "Accel_X", "Accel_Y", "Accel_Z",
    "Gyro_X",  "Gyro_Y",  "Gyro_Z",
    "Mag_X",   "Mag_Y",   "Mag_Z",
    "FSR_1",   "FSR_2",   "FSR_3",   "FSR_4",   "FSR_5",   "FSR_6",
]


def _extract_features_from_array(arr: np.ndarray) -> np.ndarray:
    """
    Compute the 393 hand-crafted features from a (N, 18) numpy array.
    Mirrors the training feature_extraction pipeline exactly.
    Returns a 1-D feature vector, or None on failure.
    """
    try:
        import pandas as pd
        from scipy.stats import entropy as sp_entropy

        df = pd.DataFrame(arr, columns=_COLUMNS)

        # ── rest / gesture split ────────────────────────────────
        fsr_cols = [c for c in df.columns if c.startswith("FSR")]
        fsr_sum  = df[fsr_cols].sum(axis=1)
        threshold = np.mean(fsr_sum) + 0.5 * np.std(fsr_sum)
        active    = fsr_sum > threshold
        rest_df    = df[~active] if np.sum(~active) > 0 else df.iloc[:5]
        gesture_df = df[active]  if np.sum(active)  > 0 else df.iloc[5:]

        def _stats(signal):
            s = np.asarray(signal, dtype=float)
            hist, _ = np.histogram(s, bins=10)
            return {
                "mean":    float(np.mean(s)),
                "std":     float(np.std(s)),
                "max":     float(np.max(s)),
                "min":     float(np.min(s)),
                "range":   float(np.ptp(s)),
                "rms":     float(np.sqrt(np.mean(s ** 2))),
                "entropy": float(sp_entropy(hist + 1)),
            }

        features = {}

        # FSR features
        rest_fsr    = rest_df[fsr_cols].values
        gesture_fsr = gesture_df[fsr_cols].values
        features["fsr_mean_rest"]    = float(np.mean(rest_fsr))
        features["fsr_mean_gesture"] = float(np.mean(gesture_fsr))
        features["fsr_peak"]         = float(np.max(gesture_fsr))
        features["fsr_delta"]        = float(np.mean(gesture_fsr) - np.mean(rest_fsr))
        features["fsr_active_ratio"] = float(
            np.sum(gesture_fsr > np.mean(gesture_fsr)) / max(gesture_fsr.size, 1)
        )

        # IMU magnitudes
        def _mag(df_, cols):
            return np.sqrt(sum(df_[c].values ** 2 for c in cols))

        acc_rest  = _mag(rest_df,    ["Accel_X", "Accel_Y", "Accel_Z"])
        acc_gest  = _mag(gesture_df, ["Accel_X", "Accel_Y", "Accel_Z"])
        gyro_rest = _mag(rest_df,    ["Gyro_X",  "Gyro_Y",  "Gyro_Z"])
        gyro_gest = _mag(gesture_df, ["Gyro_X",  "Gyro_Y",  "Gyro_Z"])

        features["acc_motion"]  = float(np.std(acc_gest))
        features["gyro_motion"] = float(np.std(gyro_gest))
        features["acc_delta"]   = float(np.mean(acc_gest)  - np.mean(acc_rest))
        features["gyro_delta"]  = float(np.mean(gyro_gest) - np.mean(gyro_rest))

        # Orientation stability
        for col in ["Roll", "Pitch", "Yaw"]:
            features[f"{col}_stability"] = float(np.std(gesture_df[col].values))
            features[f"{col}_delta"]     = float(
                np.mean(gesture_df[col].values) - np.mean(rest_df[col].values)
            )

        # Per-channel stats
        for col in df.columns:
            r = rest_df[col].values
            g = gesture_df[col].values
            if len(r) < 5 or len(g) < 5:
                continue
            r_stats = _stats(r)
            g_stats = _stats(g)
            for k in r_stats:
                features[f"{col}_rest_{k}"]    = r_stats[k]
                features[f"{col}_gesture_{k}"] = g_stats[k]
                features[f"{col}_delta_{k}"]   = g_stats[k] - r_stats[k]

        return np.array(list(features.values()), dtype=float), list(features.keys())
    except Exception as e:
        print(f"[feature_extraction] error: {e}", flush=True)
        return None, None


# ─────────────────────────── GESTURE CLASSIFIER ────────────────
class CNNClassifier:
    """
    Hybrid gesture classifier:
      • Primary:    ExtraTreesClassifier (extra_trees_model.pkl) — always available
      • Secondary:  GRU/TF model (optional, loaded async)
      • Calibration: cosine-similarity prototypes with high weight (PROTO_WEIGHT)

    When prototypes are available they strongly influence the result, giving
    the real-time calibration data high priority over the pre-trained model.
    """

    def __init__(self, model, scaler, le, proto_weight=PROTO_WEIGHT):
        # GRU/TF model (may stay None if TF deadlocks — that is OK)
        self.model        = model
        self.scaler       = scaler      # GRU scaler (18-feature StandardScaler)
        self.le           = le          # GRU LabelEncoder

        self.proto_weight = proto_weight

        # ExtraTrees (primary, loaded in __init__ — no TF needed)
        self.et_model     = None        # ExtraTreesClassifier
        self.et_scaler    = None        # StandardScaler(393 features)
        self.et_classes   = None        # list of class names
        self._load_et()

        # Calibration prototypes: label -> (WINDOW_SIZE, 18) raw array (shape/cosine)
        self.prototypes   = {}

        # Amplitude profiles: label -> {"mean": (6,), "std": (6,), "sum_mean": float, "sum_std": float}
        # Captures per-channel FSR amplitude ranges during calibration.
        # This is the PRIMARY discriminator for gestures with different pressure levels
        # (e.g. Fist_Close has max amplitude on all channels; Thumbs_Up does not).
        self.amp_profiles = {}

    # ── ExtraTrees loader ──────────────────────────────────────
    def _load_et(self):
        """Load ExtraTrees model synchronously — no TF, always safe."""
        try:
            self.et_model   = joblib.load(ET_MODEL_PATH)
            self.et_classes = list(self.et_model.classes_)
            print(f"✅ ExtraTrees loaded  classes={self.et_classes}", flush=True)
        except Exception as e:
            print(f"⚠️  ExtraTrees load failed: {e}", flush=True)
        try:
            self.et_scaler = joblib.load(ET_SCALER_PATH)
            print("✅ ET scaler loaded", flush=True)
        except Exception as e:
            print(f"⚠️  ET scaler load failed: {e}", flush=True)

    # ── Window selection (GRU path) ────────────────────────────
    def _gru_scale(self, buf):
        """Scale a (WINDOW_SIZE, 18) buffer using GRU scaler."""
        if self.scaler is not None:
            try:
                return self.scaler.transform(buf)
            except Exception:
                pass
        return (buf - buf.mean(0)) / (buf.std(0) + 1e-8)

    def _best_window(self, arr):
        """arr: (N,18) float array -> (WINDOW_SIZE,18) scaled, best FSR window.
        If fewer than WINDOW_SIZE rows are present, pad with the first row so
        short Flex/Extend bursts still produce a valid window.
        """
        if len(arr) == 0:
            return None
        # Pad short buffers by repeating the first row
        if len(arr) < WINDOW_SIZE:
            pad = np.tile(arr[0], (WINDOW_SIZE - len(arr), 1))
            arr = np.vstack([pad, arr])
        fsr_sum = arr[:, 12:18].sum(axis=1)
        if len(arr) > WINDOW_SIZE:
            kernel = np.ones(WINDOW_SIZE) / WINDOW_SIZE
            scores = np.convolve(fsr_sum, kernel, mode="valid")
            s = int(np.argmax(scores))
        else:
            s = 0
        return self._gru_scale(arr[s:s + WINDOW_SIZE].copy())

    # ── Prototype management ───────────────────────────────────
    def _raw_window(self, arr):
        """
        Select the best WINDOW_SIZE rows by FSR activity (same as _best_window
        but returns the RAW unscaled data — preserves DC offsets so cosine
        similarity captures the absolute FSR pattern, not just its shape).
        If fewer than WINDOW_SIZE rows, pads with the first row so short
        Flex/Extend bursts are not dropped.
        """
        if len(arr) == 0:
            return None
        # Pad short buffers
        if len(arr) < WINDOW_SIZE:
            pad = np.tile(arr[0], (WINDOW_SIZE - len(arr), 1))
            arr = np.vstack([pad, arr])
        fsr_sum = arr[:, 12:18].sum(axis=1)
        if len(arr) > WINDOW_SIZE:
            kernel = np.ones(WINDOW_SIZE) / WINDOW_SIZE
            scores = np.convolve(fsr_sum, kernel, mode="valid")
            s = int(np.argmax(scores))
        else:
            s = 0
        return arr[s:s + WINDOW_SIZE].copy()   # raw, unscaled

    def _build_amp_profile(self, arr: np.ndarray) -> dict:
        """
        Build an amplitude profile from a raw (N, 18) array.
        Focuses on FSR channels (cols 12-17).
        Returns a dict with per-channel mean/std and total-sum mean/std.
        Uses the peak-activity window (top 50% of frames by FSR sum) so that
        rest frames don't dilute the gesture's true amplitude.
        """
        fsr = arr[:, 12:18]          # (N, 6)
        fsr_sum = fsr.sum(axis=1)    # (N,)

        # Use only the active frames (top 50% by FSR sum) for amplitude stats
        thresh = np.percentile(fsr_sum, 50)
        active = fsr[fsr_sum >= thresh]  # (M, 6)
        if len(active) < 5:
            active = fsr

        ch_mean = active.mean(axis=0)   # (6,)
        ch_std  = active.std(axis=0) + 1e-6   # (6,)
        s_mean  = float(active.sum(axis=1).mean())
        s_std   = float(active.sum(axis=1).std()) + 1e-6
        return {"mean": ch_mean, "std": ch_std,
                "sum_mean": s_mean, "sum_std": s_std}

    def add_prototype(self, label, rows):
        """Store a calibration prototype + amplitude profile for label."""
        arr = np.array(rows, dtype=float)
        raw = self._raw_window(arr)
        if raw is None:
            return False

        # ── Shape prototype (cosine) ──────────────────────────
        if label in self.prototypes:
            self.prototypes[label] = (self.prototypes[label] + raw) / 2.0
        else:
            self.prototypes[label] = raw   # shape (WINDOW_SIZE, 18), raw

        # ── Amplitude profile (Gaussian amplitude matching) ───
        profile = self._build_amp_profile(arr)
        if label in self.amp_profiles:
            # Running average to keep profile fresh across multiple recordings
            old = self.amp_profiles[label]
            self.amp_profiles[label] = {
                "mean":     (old["mean"]     + profile["mean"])     / 2.0,
                "std":      (old["std"]      + profile["std"])      / 2.0,
                "sum_mean": (old["sum_mean"] + profile["sum_mean"]) / 2.0,
                "sum_std":  (old["sum_std"]  + profile["sum_std"])  / 2.0,
            }
        else:
            self.amp_profiles[label] = profile

        print(f"[amp_profile] {label}: sum_mean={profile['sum_mean']:.1f}  "
              f"ch_mean={np.round(profile['mean'], 1).tolist()}", flush=True)
        return True

    def _amp_score(self, arr: np.ndarray, profile: dict) -> float:
        """
        Gaussian amplitude-match score: how well the live FSR amplitude
        matches a calibrated gesture's amplitude profile.

        For each FSR channel i:
            score_i = exp(-0.5 * ((x_i - mu_i) / sigma_i)^2)
        Final = geometric mean of per-channel scores × total-sum score.

        Range: (0, 1]. Higher = better amplitude match.
        """
        fsr = arr[:, 12:18]        # (N, 6)
        fsr_sum = fsr.sum(axis=1)  # (N,)

        # Use active frames (top 50%) for fair comparison
        thresh = np.percentile(fsr_sum, 50)
        active = fsr[fsr_sum >= thresh]
        if len(active) < 3:
            active = fsr

        live_ch_mean = active.mean(axis=0)          # (6,)
        live_sum     = float(active.sum(axis=1).mean())

        mu    = profile["mean"]       # (6,)
        sigma = profile["std"]        # (6,)

        # Per-channel Gaussian score
        # Use sigma * 1.2 (tighter than before) so Flex vs Thumbs_Up
        # amplitude differences are penalised more sharply.
        z_ch     = (live_ch_mean - mu) / (sigma * 1.2)
        ch_score = np.exp(-0.5 * z_ch ** 2)              # (6,) in (0,1]
        geo_mean = float(np.prod(ch_score) ** (1.0 / 6))

        # Total-sum Gaussian score (tighter tolerance too)
        z_sum    = (live_sum - profile["sum_mean"]) / (profile["sum_std"] * 1.2)
        sum_score = float(np.exp(-0.5 * z_sum ** 2))

        # Combine: 55% total-sum (primary amplitude discriminator) + 45% per-channel pattern
        return 0.55 * sum_score + 0.45 * geo_mean

    def _cosine(self, a, b):
        """Mean-centered cosine similarity clamped to [0, 1]."""
        a = a.reshape(-1); b = b.reshape(-1)
        if a.shape != b.shape:
            return 0.0
        a = a - a.mean(); b = b - b.mean()
        return max(0.0, float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)))

    # ── ExtraTrees prediction ──────────────────────────────────
    def _et_predict(self, arr: np.ndarray):
        """
        Run ExtraTrees on arr (N,18).
        Returns (label_str, prob_dict) or None.
        """
        if self.et_model is None:
            return None
        feat_vec, feat_names = _extract_features_from_array(arr)
        if feat_vec is None:
            return None
        try:
            import pandas as pd
            if self.et_scaler is not None:
                # Use a named DataFrame so scaler matches training pipeline exactly
                feat_df  = pd.DataFrame([feat_vec], columns=feat_names)
                feat_vec = self.et_scaler.transform(feat_df)[0]
            proba = self.et_model.predict_proba(feat_vec.reshape(1, -1))[0]
            classes = self.et_classes
            idx   = int(np.argmax(proba))
            label = str(classes[idx])
            prob_dict = {str(c): float(p) for c, p in zip(classes, proba)}
            return label, prob_dict
        except Exception as e:
            print(f"[ET predict] error: {e}", flush=True)
            return None

    # ── Main predict ───────────────────────────────────────────
    def predict(self, rows):
        """
        Returns (best_label, best_conf, model_label, model_conf, proto_scores) or None.

        Fusion strategy:
          1. ExtraTrees probability dict  (always attempted)
          2. GRU/TF probability dict      (attempted if model loaded)
          3. Merge (1) and (2) -> base_scores
          4. Calibration scores (amplitude + cosine) -> cal_scores
             - Amplitude score: Gaussian match of live FSR amplitudes vs
               calibrated per-channel mean/std  (primary discriminator)
             - Cosine score:    shape similarity of FSR time-series pattern
             - Combined: 75% amplitude + 25% cosine (amplitude dominates
               to correctly separate Fist_Close/Thumbs_Up & Flex/Extend)
          5. Final = base_scores * (1 - proto_weight) + cal_scores * proto_weight
             (proto_weight = 0.70 when calibration data present)
          6. Argmax -> best_label, best_conf
        """
        arr = np.array(rows, dtype=float)
        buf = self._best_window(arr)   # (WINDOW_SIZE,18) or None

        # ── Step 1: ExtraTrees ─────────────────────────────────
        et_result = self._et_predict(arr)

        # ── Step 2: GRU/TF (optional) ─────────────────────────
        gru_probs = None
        gru_label = None
        gru_conf  = 0.0
        if buf is not None and self.model is not None:
            try:
                preds = self.model.predict(buf[np.newaxis], verbose=0)[0]
                g_idx = int(np.argmax(preds))
                gru_conf = float(preds[g_idx])
                try:
                    gru_label = str(self.le.inverse_transform([g_idx])[0])
                except Exception:
                    gru_label = str(g_idx)
                if self.le is not None:
                    gru_probs = {str(c): float(p) for c, p in zip(self.le.classes_, preds)}
            except Exception as e:
                print(f"[GRU predict] error: {e}", flush=True)

        # ── Need at least one model or prototypes ──────────────
        all_labels = list(CAL_GESTURES)

        if et_result is None and gru_probs is None and not self.prototypes:
            return None

        # ── Step 3: Merge ET + GRU into base_scores ───────────
        base_scores = {lab: 0.0 for lab in all_labels}

        if et_result is not None:
            et_label, et_probs = et_result
            # If GRU is also available, weight 70% ET + 30% GRU; otherwise ET alone
            gru_weight = 0.3 if gru_probs else 0.0
            et_weight  = 1.0 - gru_weight
            for lab in all_labels:
                base_scores[lab] += et_probs.get(lab, 0.0) * et_weight
            if gru_probs:
                for lab in all_labels:
                    base_scores[lab] += gru_probs.get(lab, 0.0) * gru_weight
            model_label = et_label
            model_conf  = et_probs.get(et_label, 0.0)
        elif gru_probs:
            for lab in all_labels:
                base_scores[lab] = gru_probs.get(lab, 0.0)
            model_label = gru_label
            model_conf  = gru_conf
        else:
            # No model at all — will rely purely on calibration scores
            model_label = None
            model_conf  = 0.0

        # ── Step 4: Calibration scores (amplitude + cosine) ───
        #
        # We compute TWO scores per calibrated gesture:
        #   a) amp_score  — Gaussian match on FSR amplitude ranges (captures
        #                    the key difference: Fist_Close has ALL channels
        #                    at max; Thumbs_Up does NOT; Flex vs Extend have
        #                    distinct per-channel pressure patterns)
        #   b) cos_score  — shape/timing cosine similarity (secondary)
        #
        # Final calibration score = 75% amp + 25% cosine
        # This is then normalised to [0,1] across gestures so it can be
        # fused fairly with the model's probability distribution.
        # ──────────────────────────────────────────────────────
        cal_scores  = {}   # combined amplitude+cosine per gesture
        proto_scores = {}  # exposed as cosine-only for UI display
        raw_win = self._raw_window(arr)
        if raw_win is None and len(arr) >= WINDOW_SIZE:
            raw_win = arr[-WINDOW_SIZE:]

        have_cal = bool(self.prototypes or self.amp_profiles)

        if have_cal and raw_win is not None:
            for lab in all_labels:
                cos_s = 0.0
                amp_s = 0.0

                if lab in self.prototypes:
                    cos_s = self._cosine(raw_win, self.prototypes[lab])

                if lab in self.amp_profiles:
                    amp_s = self._amp_score(arr, self.amp_profiles[lab])
                elif lab in self.prototypes:
                    # Fallback: build an on-the-fly amplitude score from
                    # the stored prototype window if amp_profiles wasn't saved
                    tmp_profile = self._build_amp_profile(self.prototypes[lab])
                    amp_s = self._amp_score(arr, tmp_profile)

                # 75% amplitude (primary) + 25% cosine shape (secondary)
                cal_scores[lab]  = 0.75 * amp_s + 0.25 * cos_s
                proto_scores[lab] = cos_s   # for UI display only

            # Normalise cal_scores to sum=1 (makes fusion with base_scores fair)
            total = sum(cal_scores.values()) + 1e-8
            cal_scores = {lab: v / total for lab, v in cal_scores.items()}

            # Log amplitude diagnostics so user can see what's happening
            amp_str = "  ".join(
                f"{lab}={cal_scores[lab]:.3f}" for lab in all_labels
                if lab in cal_scores
            )
            print(f"[cal_scores] {amp_str}", flush=True)

        # ── Step 5: Fuse base + calibration scores ─────────────
        have_proto = bool(cal_scores)
        # Give calibration data strong priority (0.70) when present,
        # so that the real-time amplitude info can override a confused model.
        pw = 0.70 if have_proto else 0.0

        merged = {}
        for lab in all_labels:
            base = base_scores.get(lab, 0.0)
            cal  = cal_scores.get(lab, 0.0)
            merged[lab] = base * (1.0 - pw) + cal * pw

        # If no model at all — rely entirely on calibration scores
        if model_label is None and have_proto:
            merged = {lab: cal_scores.get(lab, 0.0) for lab in all_labels}

        best_label = max(merged, key=merged.get)
        best_conf  = float(merged[best_label])

        return best_label, best_conf, (model_label or best_label), model_conf, proto_scores


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
        self._broadcast = None  # callable(event, data)

        # Initialise classifier with no model; model loads async in background
        self.clf      = CNNClassifier(None, None, None, proto_weight=PROTO_WEIGHT)
        self.model_ok = False

        # Model loader thread is started manually via start_async_load() after Flask server starts.

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
        # Adaptive per-window parameters (set when window opens)
        self._win_post_off   = POST_OFF_COUNT
        self._win_max_samp   = MAX_GEST_SAMP

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

    def start_async_load(self):
        """Start background model loader thread after server starts."""
        _loader = threading.Thread(target=self._load_model_async, daemon=True, name="tf-loader")
        _loader.start()

    def _load_model_async(self):
        """Load TensorFlow model in a background thread to avoid blocking startup."""
        try:
            from tensorflow.keras.models import load_model as keras_load
            tf_ok = True
        except Exception as e:
            print(f"⚠️  TensorFlow unavailable: {e}", flush=True)
            tf_ok = False

        cnn_model = cnn_scaler = cnn_le = None
        if tf_ok:
            try:
                cnn_model = keras_load(CNN_MODEL_PATH)
                print(f"✅ Model loaded [{MODEL_NAME}]", flush=True)
            except Exception as e:
                print(f"[CNN] Standard load failed ({e}), building custom sequential architecture...", flush=True)
                try:
                    from tensorflow.keras.models import Sequential
                    from tensorflow.keras.layers import GRU, Dropout, Dense
                    from tensorflow.keras.regularizers import l2
                    
                    cnn_model = Sequential([
                        GRU(128, return_sequences=True, reset_after=True, input_shape=(50, 18), name="gru"),
                        Dropout(0.3, name="dropout"),
                        GRU(64, return_sequences=False, reset_after=True, name="gru_1"),
                        Dropout(0.3, name="dropout_1"),
                        Dense(64, activation="relu", kernel_regularizer=l2(0.0001), name="dense"),
                        Dense(5, activation="softmax", name="dense_1")
                    ])
                    cnn_model.load_weights(CNN_MODEL_PATH)
                    print(f"✅ Model loaded [{MODEL_NAME}] via sequential weights fallback", flush=True)
                except Exception as e2:
                    print(f"⚠️  Model fallback failed: {e2}", flush=True)
        try:
            cnn_scaler = joblib.load(CNN_SCALER_PATH)
            print("✅ Scaler loaded", flush=True)
        except Exception as e:
            print(f"⚠️  Scaler: {e}", flush=True)
        try:
            cnn_le = joblib.load(CNN_LE_PATH)
            print(f"✅ LabelEncoder: {list(cnn_le.classes_)}", flush=True)
        except Exception as e:
            print(f"⚠️  LabelEncoder: {e}", flush=True)

        # Update classifier atomically once ready
        self.clf.model    = cnn_model
        self.clf.scaler   = cnn_scaler
        self.clf.le       = cnn_le
        self.model_ok     = cnn_model is not None
        print("✅ Gesture engine ready", flush=True)

    def _init_runtime_state(self):
        pass  # state initialized directly in __init__


    def set_broadcast(self, fn):
        self._broadcast = fn

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
            # Lower threshold so Flex/Extend (low amplitude) still open windows.
            # 1.5σ above rest mean is enough to detect a light finger movement.
            self.thr_on_sum  = mu + 1.5 * sig
            self.thr_off_sum = mu + 0.5 * sig
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

                # ── Adaptive window parameters based on opening amplitude ──
                # Compare opening fsr_sum to multiples of thr_on_sum to decide tier.
                # Fist_Close → very high sum → longest window
                # Thumbs_Up/Down → moderate → medium window
                # Flex/Extend → barely above threshold → short window
                ratio = fsr_sum / max(self.thr_on_sum, 1.0)
                if ratio >= HIGH_AMP_RATIO:
                    self._win_post_off, self._win_max_samp = WIN_PARAMS_HIGH
                    tier = "HIGH(Fist)"
                elif ratio >= MED_AMP_RATIO:
                    self._win_post_off, self._win_max_samp = WIN_PARAMS_MED
                    tier = "MED(Thumbs)"
                else:
                    self._win_post_off, self._win_max_samp = WIN_PARAMS_LOW
                    tier = "LOW(Flex/Ext)"

                self._emit("window_event", {"type": "open", "sum": fsr_sum})
                self._emit("log", {"msg": f"Window OPEN  sum={fsr_sum:.2f}  ratio={ratio:.2f}  tier={tier}  post_off={self._win_post_off}  max={self._win_max_samp}"})
        else:
            self._gest_buf.append(vals)
            self._off_count = self._off_count + 1 if fsr_sum < self.thr_off_sum else 0

            close = (
                # Allow closing with fewer samples than WINDOW_SIZE for LOW tier
                # (Flex/Extend) — padding will fill the gap in _raw_window/_best_window
                (self._off_count >= self._win_post_off and len(self._gest_buf) >= max(10, WINDOW_SIZE // 2))
                or len(self._gest_buf) >= self._win_max_samp
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
                        "proto_scores": {k: float(pv) for k, pv in proto_sc.items()},
                    })
                    log_msg = f"→ {label}  final={conf:.2f}  CNN={cnn_label}:{cnn_conf:.2f}"
                    self._emit("log", {"msg": log_msg})
                    self._emit("window_event", {"type": "idle"})
                else:
                    self._emit("window_event", {"type": "idle"})

    # ── helper ──────────────────────────────────────────────
    def _emit(self, event, data):
        if self._broadcast:
            try:
                self._broadcast(event, data)
            except Exception:
                pass
