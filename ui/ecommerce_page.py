"""
PyQt6 E-commerce Page
Airport Suitcase Spinner Carousel in 3D perspective using QPropertyAnimation.
"""
import math
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QColor, QFont
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from utils.theme import Theme
from utils.gesture_engine import GestureEngine

class ProductCard(QFrame):
    def __init__(self, idx, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.setProperty("class", "Card")
        self.setStyleSheet(f"background-color: {Theme.CARD}; border-radius: 15px;")
        
        layout = QVBoxLayout(self)
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img_path = os.path.join(base_dir, "assets", "products", f"prod_{idx+1}.png")
        if os.path.exists(img_path):
            pix = QPixmap(img_path).scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.img_lbl.setPixmap(pix)
            
        self.title_lbl = QLabel(f"Premium Item {idx+1}")
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.price_lbl = QLabel(f"${99 + idx*50}.00")
        self.price_lbl.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold;")
        self.price_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.img_lbl)
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.price_lbl)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 10)
        self.setGraphicsEffect(shadow)

class EcommercePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.engine = GestureEngine.get()
        
        self.num_items = 5
        self.current_angle = 0
        self.target_angle = 0
        self.cards = []
        
        self.cart_items = []
        self.wish_items = []
        
        self._init_ui()
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self._animate_spin)
        self.anim_timer.start(16)

    def _init_ui(self):
        # We need absolute positioning for 3D spin effect
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Top Bar
        top_bar = QHBoxLayout()
        header = QLabel("Shop")
        header.setProperty("class", "Title")
        self.cart_btn = QPushButton("🛒 Cart: 0")
        self.cart_btn.setProperty("class", "Primary")
        
        self.wish_btn = QPushButton("❤️ Wishlist: 0")
        
        top_bar.addWidget(header)
        top_bar.addStretch()
        top_bar.addWidget(self.wish_btn)
        top_bar.addWidget(self.cart_btn)
        self.layout.addLayout(top_bar)
        
        # Frame Container for Absolute Positioned Cards
        self.container = QFrame()
        self.container.setStyleSheet(f"background-color: {Theme.BG};")
        self.layout.addWidget(self.container, 1) # Take remaining space
        
        # Action Label
        self.action_lbl = QLabel("")
        self.action_lbl.setStyleSheet(f"color: {Theme.PRIMARY}; font-size: 20px; font-weight: bold; background: white; padding: 10px; border-radius: 10px;")
        self.action_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.action_lbl.hide()
        
        for i in range(self.num_items):
            card = ProductCard(i, self.container)
            card.resize(200, 250)
            self.cards.append(card)

    def on_show(self):
        self.engine.set_active_listener(self._on_gesture)
        
    def _on_gesture(self, event):
        if event[0] != "gesture": return
        g = event[1]
        
        if g == "Extend":
            self.target_angle -= 360 / self.num_items
        elif g == "Flex":
            self.target_angle += 360 / self.num_items
        elif g == "Thumbs_Up":
            self._add_wishlist()
        elif g == "Thumbs_Down":
            self._dislike()
        elif g == "Fist_Close":
            self._add_cart()
            
    def _add_cart(self):
        self.cart_items.append("Item")
        self.cart_btn.setText(f"🛒 Cart: {len(self.cart_items)}")
        self._show_action("Added to Cart 🛒", Theme.PRIMARY)
        
    def _add_wishlist(self):
        self.wish_items.append("Item")
        self.wish_btn.setText(f"❤️ Wishlist: {len(self.wish_items)}")
        self._show_action("Added to Wishlist ❤️", Theme.SUCCESS)
        
    def _dislike(self):
        self._show_action("Disliked 👎", Theme.DANGER)
        # Auto skip to next
        self.target_angle -= 360 / self.num_items

    def _show_action(self, text, color):
        self.action_lbl.setText(text)
        self.action_lbl.setStyleSheet(f"color: white; font-size: 20px; font-weight: bold; background: {color}; padding: 10px; border-radius: 10px;")
        self.action_lbl.setParent(self)
        self.action_lbl.move(self.width()//2 - 100, 80)
        self.action_lbl.show()
        self.action_lbl.raise_()
        QTimer.singleShot(1500, self.action_lbl.hide)

    def _animate_spin(self):
        # Smooth interpolation
        self.current_angle += (self.target_angle - self.current_angle) * 0.1
        
        cw, ch = self.container.width(), self.container.height()
        cx, cy = cw // 2, ch // 2
        
        rx, ry = cw * 0.35, ch * 0.15 # Ellipse radii
        
        for i, card in enumerate(self.cards):
            angle_deg = self.current_angle + i * (360 / self.num_items)
            rad = math.radians(angle_deg)
            
            # X and Y on ellipse
            x = cx + rx * math.sin(rad)
            y = cy + ry * math.cos(rad)
            
            # Scale based on Y (depth)
            # Front is max y, Back is min y
            y_norm = (math.cos(rad) + 1) / 2 # 0 (back) to 1 (front)
            scale = 0.5 + 0.5 * y_norm
            
            cw_scaled, ch_scaled = int(200 * scale), int(250 * scale)
            card.setGeometry(int(x - cw_scaled/2), int(y - ch_scaled/2), cw_scaled, ch_scaled)
            
            # Z-order hack (Qt uses widget order, so raise_ front widget)
            # Higher y_norm should be brought to front. 
            card.setProperty("depth", y_norm)
            
        # Re-order widgets by depth
        sorted_cards = sorted(self.cards, key=lambda c: c.property("depth"))
        for c in sorted_cards:
            c.raise_()
