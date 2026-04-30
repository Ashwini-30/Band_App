#!/usr/bin/env python3
"""
FMG Gesture-Based Web Server
Runs a Flask-SocketIO app serving the modern web frontend and pushing gesture events.
"""


import sys
import os
import argparse
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.cnn_controller import WebGestureEngine

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fmg-secret'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

engine = WebGestureEngine.get()
engine.set_socketio(socketio)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/assets/<path:filename>')
def custom_assets(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(PROJECT_ROOT, 'assets'), filename)

@app.route('/api/ports')
def get_ports():
    try:
        import serial.tools.list_ports
        ports = [p.device for p in serial.tools.list_ports.comports()]
        return {"ports": ports}
    except Exception as e:
        return {"ports": []}

@socketio.on('connect')
def handle_connect():
    print("Client connected")
    socketio.emit("status", {"msg": "Connected" if engine.connected else "Disconnected (Demo Mode Available)"})

@socketio.on('demo_event')
def handle_demo_event(data):
    gesture = data.get('gesture')
    if gesture:
        socketio.emit("gesture", {"gesture": gesture, "confidence": 1.0})

@socketio.on('connect_port')
def handle_connect_port(data):
    port = data.get('port')
    if port:
        engine.connect_port(port)

@socketio.on('disconnect_port')
def handle_disconnect_port():
    engine.disconnect_port()

@socketio.on('start_calibration')
def handle_start_cal(data):
    label = data.get('label')
    if label:
        engine.start_calibration(label)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=None)
    args = parser.parse_args()
    
    if args.port:
        threading.Timer(1.0, lambda: handle_connect_port({'port': args.port})).start()

    print("🚀 Server starting at http://127.0.0.1:5050")
    socketio.run(app, host='127.0.0.1', port=5050, debug=True, use_reloader=False)

if __name__ == "__main__":
    main()
