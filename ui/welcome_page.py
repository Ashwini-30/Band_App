"""
PyQt6 Welcome Page
Dashboard displaying gestures mapping with images and connection inputs.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QGridLayout, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt
from utils.theme import Theme

class WelcomePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        # Header
        header = QLabel("Multimodal Gesture Controller")
        header.setProperty("class", "Title")
        layout.addWidget(header)
        
        subtitle = QLabel("Control your workstation effortlessly. Use the physical band or demo mode keys (1-5).")
        subtitle.setProperty("class", "Subtitle")
        layout.addWidget(subtitle)
        
        # Gestures Grid
        gestures_lbl = QLabel("Active Gesture Vocabulary")
        gestures_lbl.setProperty("class", "Subtitle")
        gestures_lbl.setStyleSheet(f"color: {Theme.TEXT}; font-weight: bold;")
        layout.addWidget(gestures_lbl)
        
        grid_frame = QFrame()
        grid_frame.setProperty("class", "Card")
        grid_layout = QHBoxLayout(grid_frame)
        grid_layout.setContentsMargins(20, 20, 20, 20)
        grid_layout.setSpacing(20)
        
        gestures = [
            ("Extend", "1"), ("Flex", "2"), ("Fist_Close", "3"),
            ("Thumbs_Up", "4"), ("Thumbs_Down", "5")
        ]
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for name, key in gestures:
            card = QFrame()
            cl = QVBoxLayout(card)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Asset Image
            img_path = os.path.join(base_dir, "assets", "gestures", f"{name}.png")
            img_lbl = QLabel()
            img_lbl.setFixedSize(120, 120)
            if os.path.exists(img_path):
                pix = QPixmap(img_path).scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                img_lbl.setPixmap(pix)
            else:
                img_lbl.setText("?")
                img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img_lbl.setStyleSheet(f"background: {Theme.BORDER}; border-radius: 60px;")
            
            title = QLabel(name.replace("_", " "))
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-weight: bold; margin-top: 10px;")
            
            sub = QLabel(f"Demo Key: {key}")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setProperty("class", "Muted")
            
            cl.addWidget(img_lbl)
            cl.addWidget(title)
            cl.addWidget(sub)
            grid_layout.addWidget(card)
            
        layout.addWidget(grid_frame)
        
        # Connection Config
        conn_frame = QFrame()
        conn_frame.setProperty("class", "Card")
        conn_layout = QVBoxLayout(conn_frame)
        conn_layout.setContentsMargins(20, 20, 20, 20)
        
        clbl = QLabel("Serial Connection")
        clbl.setStyleSheet("font-weight: bold;")
        conn_layout.addWidget(clbl)
        
        form_lay = QHBoxLayout()
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("e.g. /dev/tty.usbserial...")
        self.port_input.setStyleSheet(f"padding: 8px; border: 1px solid {Theme.BORDER}; border-radius: 6px;")
        
        self.conn_btn = QPushButton("Connect")
        self.conn_btn.setProperty("class", "Primary")
        self.conn_btn.clicked.connect(self._toggle_connect)
        
        form_lay.addWidget(self.port_input)
        form_lay.addWidget(self.conn_btn)
        
        conn_layout.addLayout(form_lay)
        layout.addWidget(conn_frame)
        
        layout.addStretch()

    def _toggle_connect(self):
        if self.main.serial_running:
            self.main.disconnect_port()
            self.conn_btn.setText("Connect")
            self.conn_btn.setStyleSheet("")
        else:
            p = self.port_input.text().strip()
            if p:
                self.main.connect_port(p)
                self.conn_btn.setText("Disconnect")
                self.conn_btn.setStyleSheet(f"background-color: {Theme.DANGER};")

    def update_status(self, ev):
        if self.main.serial_running:
            self.conn_btn.setText("Disconnect")
            self.conn_btn.setStyleSheet(f"background-color: {Theme.DANGER};")
        else:
            self.conn_btn.setText("Connect")
            self.conn_btn.setStyleSheet("")
