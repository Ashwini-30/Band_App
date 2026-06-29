#!/usr/bin/env bash
# Start the Band App server using the local venv (has Flask, OpenCV, MediaPipe, TF, etc.)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/venv/bin/activate"

echo "Starting FMG Smart Control Server with Python 3.10 and TensorFlow..."
python main.py
