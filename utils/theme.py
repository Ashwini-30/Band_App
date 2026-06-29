"""
PyQt6 Theme Management
Defines modern Light Theme stylesheets and color palettes.
"""
from PyQt6.QtGui import QColor

class Theme:
    # Modern Light Theme Colors
    BG = "#F7F9FC"
    CARD = "#FFFFFF"
    CARD_HOVER = "#F0F4F8"
    NAV_BG = "#FFFFFF"
    
    PRIMARY = "#3B82F6"      # Modern blue
    PRIMARY_HOVER = "#2563EB"
    PRIMARY_LIGHT = "#EFF6FF"
    
    SUCCESS = "#10B981"
    DANGER = "#EF4444"
    WARNING = "#F59E0B"
    INFO = "#6366F1"
    
    TEXT = "#111827"
    MUTED = "#6B7280"
    BORDER = "#E5E7EB"

    @classmethod
    def get_color(cls, color_name: str) -> QColor:
        return QColor(getattr(cls, color_name.upper()))

    @classmethod
    def get_stylesheet(cls):
        """Returns the global application stylesheet."""
        return f"""
            QMainWindow, QWidget#MainContainer {{
                background-color: {cls.BG};
            }}
            
            /* Frames and Cards */
            QFrame#NavFrame {{
                background-color: {cls.NAV_BG};
                border-bottom: 1px solid {cls.BORDER};
            }}
            
            QFrame.Card {{
                background-color: {cls.CARD};
                border: 1px solid {cls.BORDER};
                border-radius: 12px;
            }}
            QFrame.Card:hover {{
                background-color: {cls.CARD_HOVER};
            }}
            
            /* Labels */
            QLabel {{
                color: {cls.TEXT};
                font-family: 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            }}
            QLabel.Muted {{
                color: {cls.MUTED};
            }}
            QLabel.Title {{
                font-size: 24px;
                font-weight: bold;
                color: {cls.TEXT};
            }}
            QLabel.Subtitle {{
                font-size: 16px;
                font-weight: 500;
                color: {cls.MUTED};
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: {cls.CARD};
                color: {cls.TEXT};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-family: 'SF Pro Display', sans-serif;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {cls.CARD_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {cls.BORDER};
            }}
            
            QPushButton.Primary {{
                background-color: {cls.PRIMARY};
                color: white;
                border: none;
            }}
            QPushButton.Primary:hover {{
                background-color: {cls.PRIMARY_HOVER};
            }}
            
            /* Nav Buttons */
            QPushButton.NavBtn {{
                background-color: transparent;
                color: {cls.MUTED};
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 10px 16px;
            }}
            QPushButton.NavBtn:hover {{
                background-color: {cls.BG};
                color: {cls.TEXT};
            }}
            QPushButton.NavBtn:checked {{
                background-color: {cls.PRIMARY_LIGHT};
                color: {cls.PRIMARY};
                font-weight: bold;
            }}
            
            /* ScrollBars */
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.BORDER};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {cls.MUTED};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """
