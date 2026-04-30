"""
GestureEngine — singleton event bus.
Pages subscribe to gesture events. The active page receives fired gestures.
Demo mode: press keys 1-5 to simulate gestures without the hardware.
"""

import queue
import threading
import time

GESTURES = ["Extend", "Flex", "Fist_Close", "Thumbs_Up", "Thumbs_Down"]

# key → gesture for demo mode
DEMO_KEYS = {
    "1": "Extend",
    "2": "Flex",
    "3": "Fist_Close",
    "4": "Thumbs_Up",
    "5": "Thumbs_Down",
}

GESTURE_META = {
    "Thumbs_Up":   ("👍", "#00d4aa"),
    "Thumbs_Down": ("👎", "#ff6b6b"),
    "Fist_Close":  ("✊", "#ffd700"),
    "Extend":      ("🖐", "#74b9ff"),
    "Flex":        ("🤏", "#a29bfe"),
}


class GestureEngine:
    """
    Singleton.
    The main app wires the serial controller → this engine.
    Pages subscribe via register_listener().
    """

    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = GestureEngine()
        return cls._instance

    def __init__(self):
        # queue fed by controller / demo
        self.raw_queue       = queue.Queue()
        # currently active listener callback: fn(event_type, gesture, extra)
        self._listener       = None
        self._listener_lock  = threading.Lock()

        # status callbacks (always called)
        self._status_cbs     = []

        # last known prediction
        self.last_gesture    = "—"
        self.last_confidence = "—"

        # connection state
        self.connected       = False
        self.demo_mode       = False

        self._running        = True
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop, daemon=True
        )
        self._dispatch_thread.start()

    # ── Registration ──────────────────────────────────────────────────────────
    def set_active_listener(self, fn):
        """Only one page is active at a time."""
        with self._listener_lock:
            self._listener = fn

    def add_status_callback(self, fn):
        """Called for ('status', msg) and ('error', msg) events always."""
        self._status_cbs.append(fn)

    # ── Feed from serial controller ───────────────────────────────────────────
    def feed(self, event: tuple):
        self.raw_queue.put(event)

    # ── Demo mode simulation ──────────────────────────────────────────────────
    def simulate_gesture(self, gesture: str):
        """Inject a gesture as if it came from the band."""
        if gesture in GESTURES:
            self.raw_queue.put(("gesture", gesture, 1.0))

    # ── Internal dispatch ─────────────────────────────────────────────────────
    def _dispatch_loop(self):
        while self._running:
            try:
                event = self.raw_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            kind = event[0]

            if kind == "prediction":
                _, gesture, conf = event
                self.last_gesture    = gesture
                self.last_confidence = conf
                # broadcast prediction to active page
                with self._listener_lock:
                    if self._listener:
                        try:
                            self._listener(("prediction", gesture, conf))
                        except Exception:
                            pass

            elif kind == "gesture":
                _, gesture, conf = event
                self.last_gesture    = gesture
                self.last_confidence = conf
                with self._listener_lock:
                    if self._listener:
                        try:
                            self._listener(("gesture", gesture, conf))
                        except Exception:
                            pass

            elif kind in ("status", "error"):
                self.connected = (kind == "status" and "Connected" in event[1])
                for cb in self._status_cbs:
                    try:
                        cb(event)
                    except Exception:
                        pass

    def stop(self):
        self._running = False
