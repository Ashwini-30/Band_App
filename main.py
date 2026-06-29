#!/usr/bin/env python3
"""
FMG Gesture-Based Web Server
Uses plain Flask with Server-Sent Events (SSE) — no flask-socketio dependency.
Browser connects to /events stream; commands sent via POST /api/...
"""

import sys
import os
import json
import queue
import threading
import time
from flask import Flask, render_template, request, Response, jsonify

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.cnn_controller import WebGestureEngine
from utils import cv_controller

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fmg-secret'

# ── SSE broadcast queue ───────────────────────────────────────────────────────
# All background threads push events here; /events streams them to browsers.
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()

def broadcast(event: str, data: dict):
    """Push an SSE event to every connected browser."""
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)

# Give the engine and cv_controller a reference to broadcast
engine = WebGestureEngine.get()
engine.set_broadcast(broadcast)
cv_controller.set_broadcast(broadcast)

# ── SSE endpoint ─────────────────────────────────────────────────────────────

@app.route('/events')
def sse_stream():
    """Browser connects here to receive real-time events."""
    q: queue.Queue = queue.Queue(maxsize=200)
    with _sse_lock:
        _sse_clients.append(q)

    def generate():
        # Send initial connected event
        yield f"event: status\ndata: {json.dumps({'msg': 'Connected'})}\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"  # prevent proxy timeout
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no'})

# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/assets/<path:filename>')
def custom_assets(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(PROJECT_ROOT, 'assets'), filename)

# ── REST API (replaces socket.io events) ─────────────────────────────────────

@app.route('/api/ports')
def get_ports():
    try:
        import serial.tools.list_ports
        ports = [p.device for p in serial.tools.list_ports.comports()]
        return jsonify({"ports": ports})
    except Exception:
        return jsonify({"ports": []})

@app.route('/api/connect_port', methods=['POST'])
def connect_port():
    port = request.json.get('port')
    if port:
        engine.connect_port(port)
    return jsonify({"ok": True})

@app.route('/api/disconnect_port', methods=['POST'])
def disconnect_port():
    engine.disconnect_port()
    return jsonify({"ok": True})

@app.route('/api/demo_event', methods=['POST'])
def demo_event():
    gesture = request.json.get('gesture')
    if gesture:
        broadcast("gesture", {"gesture": gesture, "confidence": 1.0})
    return jsonify({"ok": True})

@app.route('/api/cv_start', methods=['POST'])
def cv_start():
    mode = request.json.get('mode', 'hand')
    if mode not in ('hand', 'eye'):
        broadcast("cv_status", {"mode": None, "error": "Unknown mode"})
        return jsonify({"ok": False})
    cv_controller.start_cv_control(mode)
    broadcast("cv_status", {"mode": mode, "running": True})
    return jsonify({"ok": True})

@app.route('/api/cv_stop', methods=['POST'])
def cv_stop():
    cv_controller.stop_cv_control()
    broadcast("cv_status", {"mode": None, "running": False})
    return jsonify({"ok": True})

@app.route('/api/cv_status')
def cv_status():
    mode = cv_controller.get_mode()
    return jsonify({"mode": mode, "running": mode is not None})

@app.route('/api/start_calibration', methods=['POST'])
def start_calibration():
    label = request.json.get('label')
    if label:
        engine.start_calibration(label)
    return jsonify({"ok": True})

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("🚀 Server starting at http://127.0.0.1:5050")
    
    # Delay model loading to let Flask finish server startup imports and prevent global import lock deadlock
    def delayed_load():
        time.sleep(3)
        engine.start_async_load()
    
    threading.Thread(target=delayed_load, daemon=True).start()
    
    app.run(host='127.0.0.1', port=5050, debug=False,
            threaded=True, use_reloader=False)

if __name__ == "__main__":
    main()
