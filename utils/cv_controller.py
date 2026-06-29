"""
CV Cursor Controller
====================
Launches hand_control.py or eye_control.py as a subprocess.
This avoids macOS threading issues with cv2/mediapipe imports.
"""

import os
import sys
import threading
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_PYTHON = os.path.join(_ROOT, 'venv', 'bin', 'python3')

_proc = None
_current_mode = None
_lock = threading.Lock()
_broadcast = None


def set_broadcast(fn):
    global _broadcast
    _broadcast = fn


def start_cv_control(mode: str) -> bool:
    global _proc, _current_mode
    if mode not in ('hand', 'eye'):
        _emit_cv_status(None, False, error=f"Unknown mode: {mode}")
        return False

    script = os.path.join(_HERE, f'{mode}_control.py')

    with _lock:
        if _current_mode == mode and _proc and _proc.poll() is None:
            return True
        _stop_existing()
        try:
            _proc = subprocess.Popen(
                [_PYTHON, script],
                cwd=_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            _current_mode = mode
            _emit_cv_status(mode, True)
            print(f"[CV] Launched {mode} control (pid={_proc.pid})", flush=True)

            def _watch(proc, watch_mode):
                try:
                    for line in proc.stdout:
                        print(f"[CV-{watch_mode}] {line}", end='', flush=True)
                except Exception:
                    pass
                
                global _current_mode
                with _lock:
                    if _current_mode == watch_mode and _proc == proc:
                        _current_mode = None
                        _emit_cv_status(None, False)
                        
            threading.Thread(target=_watch, args=(_proc, mode), daemon=True).start()
            return True
        except Exception as e:
            print(f"[CV] Failed to launch {mode}: {e}", flush=True)
            _emit_cv_status(None, False, error=str(e))
            return False


def stop_cv_control() -> None:
    global _current_mode
    with _lock:
        _stop_existing()
        _current_mode = None


def get_mode() -> str | None:
    return _current_mode


def _stop_existing():
    global _proc
    if _proc and _proc.poll() is None:
        print(f"[CV] Stopping pid={_proc.pid}", flush=True)
        _proc.terminate()
        try:
            _proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None


def _emit_cv_status(mode, running, error=None):
    if _broadcast:
        payload = {'mode': mode, 'running': running}
        if error:
            payload['error'] = error
        try:
            _broadcast('cv_status', payload)
        except Exception:
            pass
