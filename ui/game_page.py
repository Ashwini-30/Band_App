"""
PyQt6 Game Page
Subway Surfers-style endless runner using QPainter for perspective drawing.
"""
import math
import random
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from utils.theme import Theme
from utils.gesture_engine import GestureEngine

class GamePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.engine = GestureEngine.get()
        
        self.score = 0
        self.speed = 10
        self.is_game_over = False
        self.lanes = [-1.0, 0.0, 1.0] # Left, Center, Right in logical coords
        self.current_lane = 1
        
        self.obj_z = [] # list of dicts: {'lane': int, 'z': z_dist}
        self.player_y_offset = 0
        self.player_is_jumping = False
        self.player_is_sliding = False
        
        # Powerups
        self.boost_active = False
        self.boost_timer = 0
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._game_loop)
        
        self._init_ui()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        self.score_lbl = QLabel("Score: 0")
        self.score_lbl.setProperty("class", "Title")
        self.score_lbl.setStyleSheet("color: white; background: rgba(0,0,0,100); padding: 10px; border-radius: 10px;")
        self.layout.addWidget(self.score_lbl, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.layout.addStretch()
        
        self.msg_lbl = QLabel("Draw a 'Thumbs Up' to Start")
        self.msg_lbl.setProperty("class", "Title")
        self.msg_lbl.setStyleSheet("color: white; background: rgba(0,0,0,150); padding: 20px; border-radius: 12px;")
        self.layout.addWidget(self.msg_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch()

    def on_show(self):
        self.engine.set_active_listener(self._on_gesture)
        if not self.timer.isActive():
            self.msg_lbl.show()

    def _on_gesture(self, event):
        if event[0] != "gesture": return
        g = event[1]
        
        if not self.timer.isActive() or self.is_game_over:
            if g == "Thumbs_Up":
                self._restart_game()
            return
            
        if g == "Extend":
            if self.current_lane < 2: self.current_lane += 1
        elif g == "Flex":
            if self.current_lane > 0: self.current_lane -= 1
        elif g == "Thumbs_Up" and not self.player_is_jumping:
            self._jump()
        elif g == "Thumbs_Down":
            self._slide()
        elif g == "Fist_Close":
            self._boost()

    def _restart_game(self):
        self.score = 0
        self.speed = 8
        self.obj_z = []
        self.current_lane = 1
        self.is_game_over = False
        self.msg_lbl.hide()
        self.boost_active = False
        self.timer.start(30) # ~30 FPS

    def _jump(self):
        self.player_is_jumping = True
        self.jump_t = 0
        
    def _slide(self):
        self.player_is_sliding = True
        QTimer.singleShot(1000, lambda: setattr(self, 'player_is_sliding', False))
        
    def _boost(self):
        self.boost_active = True
        self.speed = 20
        QTimer.singleShot(2000, self._end_boost)
        
    def _end_boost(self):
        self.boost_active = False
        self.speed = 8 + (self.score / 1000)

    def _game_loop(self):
        w, h = self.width(), self.height()
        
        # Advance objects
        for obj in self.obj_z:
            obj['z'] -= self.speed
            
        self.obj_z = [o for o in self.obj_z if o['z'] > 0]
        
        # Spawn
        if random.random() < 0.05:
            self.obj_z.append({'lane': random.randint(0, 2), 'z': 1000})
            
        # Collision
        for obj in self.obj_z:
            if obj['z'] < 50 and obj['lane'] == self.current_lane:
                if self.boost_active:
                    pass # Invincible
                elif self.player_is_jumping:
                    pass # Jumped over
                else:
                    self._game_over()
                    
        # Update score
        self.score += int(self.speed / 2)
        self.speed += 0.005 # gradual increase
        
        # Jump logic
        if self.player_is_jumping:
            self.jump_t += 1
            # Parabola
            self.player_y_offset = (self.jump_t * (20 - self.jump_t)) * 2
            if self.jump_t > 20:
                self.player_is_jumping = False
                self.player_y_offset = 0
                
        self.score_lbl.setText(f"Score: {self.score}")
        self.update() # trigger paintEvent

    def _game_over(self):
        self.is_game_over = True
        self.timer.stop()
        self.msg_lbl.setText(f"GAME OVER\nScore: {self.score}\nThumbs Up to Restart")
        self.msg_lbl.show()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 - 50 # Vanishing point
        
        # Draw Sky/Horizon
        sky_grad = QColor("#87CEEB") # Light blue
        painter.fillRect(0, 0, int(w), int(cy), sky_grad)
        
        # Draw Ground
        ground_grad = QColor(Theme.BG)
        painter.fillRect(0, int(cy), int(w), int(h - cy), ground_grad)
        
        # Draw Lanes (Lines from vanishing point to bottom)
        painter.setPen(QPen(QColor(Theme.BORDER), 2))
        for x_offset in [-1.5, -0.5, 0.5, 1.5]:
            bot_x = cx + (x_offset * w * 2)
            painter.drawLine(int(cx), int(cy), int(bot_x), int(h))
            
        # Helper projection function
        def persp(lx, lz):
            scale = 500 / max(lz, 1)
            px = cx + (lx * scale * 200)
            py = cy + (scale * 200) # simpler projection
            return px, py, scale
            
        # Draw objects
        # Sort by Z descending
        objs = sorted(self.obj_z, key=lambda o: o['z'], reverse=True)
        for obj in objs:
            lx = self.lanes[obj['lane']]
            px, py, scale = persp(lx, obj['z'])
            
            ow = 40 * scale
            oh = 80 * scale
            
            # Obstacle
            painter.setBrush(QBrush(QColor(Theme.DANGER)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(px - ow/2, py - oh, ow, oh))
            
        # Draw Player
        if not self.is_game_over:
            lx = self.lanes[self.current_lane]
            px, py, scale = persp(lx, 50)
            
            py -= self.player_y_offset
            
            ow = 60 * scale
            oh = (40 if self.player_is_sliding else 120) * scale
            
            if self.boost_active:
                painter.setBrush(QBrush(QColor(Theme.WARNING)))
                # Draw aura
                painter.setPen(QPen(QColor(Theme.WARNING), 4))
                painter.drawEllipse(QPointF(px, py - oh/2), ow*1.5, oh*1.2)
            else:
                painter.setBrush(QBrush(QColor(Theme.PRIMARY)))
                
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(px - ow/2, py - oh, ow, oh), 10, 10)
