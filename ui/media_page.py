"""
PyQt6 Media Page
Uses QWebEngineView for a real embedded YouTube video.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGraphicsOpacityEffect, QSizePolicy
)
from PyQt6.QtCore import Qt, QUrl, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWebEngineWidgets import QWebEngineView
from utils.theme import Theme
from utils.gesture_engine import GestureEngine

class MediaPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.engine = GestureEngine.get()
        self._init_ui()
        self.is_playing = False
        self.volume = 50

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # QWebEngineView
        self.webview = QWebEngineView()
        # Rickroll or similar test video
        video_url = "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&controls=0&mute=1"
        self.webview.setUrl(QUrl(video_url))
        layout.addWidget(self.webview)
        
        # Floating Overlay for Gesture Action
        self.overlay = QLabel(self)
        self.overlay.setStyleSheet(f"""
            background-color: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 20px 40px;
            border-radius: 16px;
            font-size: 28px;
            font-weight: bold;
        """)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.hide()
        
        # Opacity animation
        self.op_eff = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(self.op_eff)
        self.anim = QPropertyAnimation(self.op_eff, b"opacity")
        self.anim.setDuration(1200)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim.finished.connect(self.overlay.hide)

    def on_show(self):
        self.engine.set_active_listener(self._on_gesture)

    def _on_gesture(self, event):
        if event[0] != "gesture": return
        g = event[1]
        
        action = ""
        icon = ""
        
        if g == "Thumbs_Up":
            action = "Play"
            icon = "▶️"
            self.is_playing = True
        elif g == "Thumbs_Down":
            action = "Pause"
            icon = "⏸️"
            self.is_playing = False
        elif g == "Extend":
            self.volume = min(100, self.volume + 10)
            action = f"Volume Up {self.volume}%"
            icon = "🔊"
        elif g == "Flex":
            self.volume = max(0, self.volume - 10)
            action = f"Volume Down {self.volume}%"
            icon = "🔉"
        elif g == "Fist_Close":
            action = "Mute Toggle"
            icon = "🔇"
            
        if action:
            self._show_overlay(f"{icon}  {action}")
            # If using JS we could inject js here:
            # self.webview.page().runJavaScript("document.getElementsByTagName('video')[0].paused ? document.getElementsByTagName('video')[0].play() : document.getElementsByTagName('video')[0].pause();")

    def _show_overlay(self, msg):
        self.overlay.setText(msg)
        self.overlay.adjustSize()
        # Center in the view
        vw = self.width()
        vh = self.height()
        ow = self.overlay.width()
        oh = self.overlay.height()
        self.overlay.move((vw - ow) // 2, vh - 150)
        
        self.overlay.show()
        self.anim.stop()
        self.op_eff.setOpacity(1.0)
        self.anim.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay.isVisible():
            vw = self.width()
            vh = self.height()
            ow = self.overlay.width()
            oh = self.overlay.height()
            self.overlay.move((vw - ow) // 2, vh - 150)
