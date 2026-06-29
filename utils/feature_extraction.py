"""
Feature extraction — mirrors training pipeline exactly.
"""

import numpy as np
from scipy.stats import entropy


COLUMNS = [
    "Roll", "Pitch", "Yaw",
    "Accel_X", "Accel_Y", "Accel_Z",
    "Gyro_X",  "Gyro_Y",  "Gyro_Z",
    "Mag_X",   "Mag_Y",   "Mag_Z",
    "FSR1",    "FSR2",    "FSR3",    "FSR4",    "FSR5",    "FSR6",
]

FSR_THRESHOLD = 0.5   # std-dev multiplier for rest/gesture split


def compute_stats(signal):
    signal = np.asarray(signal, dtype=float)
    return {
        "mean":    np.mean(signal),
        "std":     np.std(signal),
        "max":     np.max(signal),
        "min":     np.min(signal),
        "range":   np.ptp(signal),
        "rms":     np.sqrt(np.mean(signal ** 2)),
        "entropy": entropy(np.histogram(signal, bins=10)[0] + 1),
    }


def split_rest_gesture(df):
    fsr_cols = [c for c in df.columns if "FSR" in c]
    fsr_sum  = df[fsr_cols].sum(axis=1)
    threshold = np.mean(fsr_sum) + FSR_THRESHOLD * np.std(fsr_sum)
    active   = fsr_sum > threshold
    if np.sum(active) == 0:
        return df, df
    return df[~active], df[active]


def extract_features(df):
    import pandas as pd
    df = df.select_dtypes(include=[np.number]).copy()
    rest_df, gesture_df = split_rest_gesture(df)
    features = {}

    # FSR features
    fsr_cols    = [c for c in df.columns if "FSR" in c]
    rest_fsr    = rest_df[fsr_cols].values
    gesture_fsr = gesture_df[fsr_cols].values

    features["fsr_mean_rest"]    = np.mean(rest_fsr)
    features["fsr_mean_gesture"] = np.mean(gesture_fsr)
    features["fsr_peak"]         = np.max(gesture_fsr)
    features["fsr_delta"]        = np.mean(gesture_fsr) - np.mean(rest_fsr)
    features["fsr_active_ratio"] = (
        np.sum(gesture_fsr > np.mean(gesture_fsr)) / max(gesture_fsr.size, 1)
    )

    # IMU magnitudes
    def _mag(df_, cols):
        return np.sqrt(sum(df_[c] ** 2 for c in cols))

    acc_rest  = _mag(rest_df,    ["Accel_X", "Accel_Y", "Accel_Z"])
    acc_gest  = _mag(gesture_df, ["Accel_X", "Accel_Y", "Accel_Z"])
    gyro_rest = _mag(rest_df,    ["Gyro_X",  "Gyro_Y",  "Gyro_Z"])
    gyro_gest = _mag(gesture_df, ["Gyro_X",  "Gyro_Y",  "Gyro_Z"])

    features["acc_motion"]  = np.std(acc_gest)
    features["gyro_motion"] = np.std(gyro_gest)
    features["acc_delta"]   = np.mean(acc_gest)  - np.mean(acc_rest)
    features["gyro_delta"]  = np.mean(gyro_gest) - np.mean(gyro_rest)

    # Orientation stability
    for col in ["Roll", "Pitch", "Yaw"]:
        features[f"{col}_stability"] = np.std(gesture_df[col])
        features[f"{col}_delta"]     = np.mean(gesture_df[col]) - np.mean(rest_df[col])

    # Per-channel stats
    for col in df.columns:
        r = rest_df[col].values
        g = gesture_df[col].values
        if len(r) < 5 or len(g) < 5:
            continue
        r_stats = compute_stats(r)
        g_stats = compute_stats(g)
        for k in r_stats:
            features[f"{col}_rest_{k}"]    = r_stats[k]
            features[f"{col}_gesture_{k}"] = g_stats[k]
            features[f"{col}_delta_{k}"]   = g_stats[k] - r_stats[k]

    return features


def derive_feature_names():
    """
    Derive feature names by doing a dry-run on a dummy dataframe.
    Must match the order used during training.
    """
    import pandas as pd
    dummy = pd.DataFrame(np.random.rand(50, 18), columns=COLUMNS)
    feat  = extract_features(dummy)
    return list(feat.keys())
