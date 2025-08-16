"""
CONJURE Main UI - Transparent Overlay
Displays real-time system information in a non-intrusive overlay
Based on UI.py reference with CONJURE-specific adaptations
"""

import sys
import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTextEdit, QGraphicsOpacityEffect, 
    QGraphicsDropShadowEffect, QSizePolicy, QFrame, QDesktopWidget,
    QScrollArea
)
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QTimer, QUrl, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPalette, QImage, QPixmap, QCursor, QPainter, QBrush, QFontDatabase

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent
UI_DATA_FILE = AGENT_DIR / "ui_data.json"

# Import the data generator for fallback
try:
    from ui_data_generator import UIDataGenerator
except ImportError:
    try:
        # Try with Agent path
        sys.path.insert(0, str(Path(__file__).parent))
        from ui_data_generator import UIDataGenerator
    except ImportError:
        print("Warning: Could not import ui_data_generator")
        UIDataGenerator = None

class MinimalLabel(QLabel):
    """Custom label with consistent styling"""
    def __init__(self, text="", style_type="normal", parent=None):
        super().__init__(text, parent)
        
        if style_type == "title":
            self.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 220);
                    font-size: 16px;
                    font-weight: bold;
                    padding: 5px;
                }
            """)
        elif style_type == "subtitle":
            self.setStyleSheet("""
                QLabel {
                    color: rgba(200, 200, 200, 180);
                    font-size: 12px;
                    font-weight: bold;
                    padding: 2px;
                }
            """)
        elif style_type == "status":
            self.setStyleSheet("""
                QLabel {
                    color: rgba(100, 255, 100, 200);
                    font-size: 14px;
                    font-weight: bold;
                    padding: 3px;
                }
            """)
        else:  # normal
            self.setStyleSheet("""
                QLabel {
                    color: rgba(220, 220, 220, 180);
                    font-size: 12px;
                    padding: 2px;
                }
            """)

class MinimalTextEdit(QTextEdit):
    """Custom text edit for conversation display"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: rgba(20, 20, 20, 150);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
            QScrollBar:vertical {
                background-color: rgba(40, 40, 40, 100);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(80, 80, 80, 150);
                border-radius: 4px;
            }
        """)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

class MinimalFrame(QFrame):
    """Custom frame with styling - EXACT copy from UI.py ImageFrame"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(20, 20, 20, 150);
                border: none;
                border-radius: 10px;
            }
        """)
        
        # Add drop shadow effect - EXACT copy from UI.py
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)

class ConversationPanel(MinimalFrame):
    """Panel for displaying conversation history"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 240)  # EXACT copy from UI.py ImageFrame
        
        # Create layout - EXACT copy from UI.py
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Title
        title = MinimalLabel("Conversation", "subtitle")
        layout.addWidget(title)
        
        # Conversation display
        self.conversation_text = MinimalTextEdit()
        self.conversation_text.setMaximumHeight(200)  # Adjusted for 240x240 panel
        layout.addWidget(self.conversation_text)
        
    def update_conversation(self, messages: List[Dict]):
        """Update conversation display with new messages"""
        html_content = ""
        
        for msg in messages[-20:]:  # Show last 20 messages
            timestamp = msg.get("timestamp", "")
            speaker = msg.get("speaker", "")
            message = msg.get("message", "")
            source = msg.get("source", "")
            
            # Color coding based on speaker
            if speaker == "USER":
                color = "#80c0ff"  # Light blue for user
            else:
                color = "#80ff80"  # Light green for agent
            
            html_content += f"""
            <div style="margin-bottom: 8px;">
                <span style="color: #888; font-size: 10px;">[{timestamp}]</span>
                <span style="color: {color}; font-weight: bold;">{speaker}:</span>
                <span style="color: #ddd;">{message}</span>
            </div>
            """
        
        self.conversation_text.setHtml(html_content)
        
        # Auto-scroll to bottom
        cursor = self.conversation_text.textCursor()
        cursor.movePosition(cursor.End)
        self.conversation_text.setTextCursor(cursor)

class StatusPanel(MinimalFrame):
    """Panel for displaying current command and status"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 240)  # EXACT copy from UI.py ImageFrame
        
        # Create layout - EXACT copy from UI.py
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Title
        title = MinimalLabel("System Status", "subtitle")
        layout.addWidget(title)
        
        # Current phase
        self.phase_label = MinimalLabel("Phase: I", "status")
        layout.addWidget(self.phase_label)
        
        # Current command
        self.command_label = MinimalLabel("Command: idle", "normal")
        layout.addWidget(self.command_label)
        
        # Status
        self.status_label = MinimalLabel("Status: running", "normal")
        layout.addWidget(self.status_label)
        
        # Timestamp
        self.timestamp_label = MinimalLabel("", "normal")
        layout.addWidget(self.timestamp_label)
        
    def update_status(self, command_data: Dict):
        """Update status display with new command data"""
        command = command_data.get("command", "idle")
        status = command_data.get("status", "unknown")
        phase = command_data.get("phase", "I")
        timestamp = command_data.get("timestamp", "")
        
        self.phase_label.setText(f"Phase: {phase}")
        self.command_label.setText(f"Command: {command}")
        self.status_label.setText(f"Status: {status}")
        self.timestamp_label.setText(f"Updated: {timestamp}")
        
        # Color coding based on status
        if status == "running":
            color = "rgba(100, 255, 100, 200)"
        elif status == "error":
            color = "rgba(255, 100, 100, 200)"
        else:
            color = "rgba(255, 255, 100, 200)"
            
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 14px;
                font-weight: bold;
                padding: 3px;
            }}
        """)

class BrushPanel(MinimalFrame):
    """Panel for displaying brush/tool information"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 240)  # EXACT copy from UI.py ImageFrame
        
        # Create layout - EXACT copy from UI.py
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Title
        title = MinimalLabel("Active Brush", "subtitle")
        layout.addWidget(title)
        
        # Brush info
        self.command_label = MinimalLabel("Tool: idle", "normal")
        layout.addWidget(self.command_label)
        
        self.hand_label = MinimalLabel("Hand: none", "normal")
        layout.addWidget(self.hand_label)
        
        self.fingertips_label = MinimalLabel("Fingertips: 0", "normal")
        layout.addWidget(self.fingertips_label)
        
    def update_brush(self, brush_data: Dict):
        """Update brush display with new data"""
        command = brush_data.get("active_command", "idle")
        hand = brush_data.get("active_hand", "none")
        fingertips = brush_data.get("fingertip_count", 0)
        
        self.command_label.setText(f"Tool: {command}")
        self.hand_label.setText(f"Hand: {hand or 'none'}")
        self.fingertips_label.setText(f"Fingertips: {fingertips}")

class ConjureMainWindow(QMainWindow):
    """Main transparent overlay window"""
    def __init__(self):
        super().__init__()
        
        # Set window flags for transparency and always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Initialize data generator if available
        self.data_generator = UIDataGenerator() if UIDataGenerator else None
        
        # Set up the UI
        self.init_ui()
        
        # Set up timer for periodic refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Load initial data
        self.refresh_data()
        
        # Make fullscreen - EXACT copy from UI.py
        self.showFullScreen()
        
    def init_ui(self):
        """Initialize the user interface - using UI.py reference layout"""
        # Window configuration  
        self.setWindowTitle("CONJURE UI Overlay")
        
        # Create central widget with transparent background
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Create main layout - EXACT copy from UI.py
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)  # Reduced spacing like UI.py
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Add discrete terminate button in top-left corner - EXACT copy from UI.py
        terminate_button = QPushButton("×")
        terminate_button.setFixedSize(26, 26)
        terminate_button.clicked.connect(self.close)
        terminate_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 150);
                color: rgba(220, 220, 220, 180);
                border: none;
                border-radius: 13px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(80, 40, 40, 180);
                color: white;
            }
        """)
        
        # Position the terminate button in the top-left corner - EXACT copy from UI.py
        terminate_button.setParent(self)
        terminate_button.move(15, 15)
        
        # Create panels container - vertical orientation like UI.py
        panels_container = QWidget()
        panels_layout = QVBoxLayout(panels_container)
        panels_layout.setSpacing(30)  # Reduced vertical spacing like UI.py
        panels_layout.setAlignment(Qt.AlignCenter)
        
        # Create UI panels
        self.status_panel = StatusPanel()
        panels_layout.addWidget(self.status_panel, alignment=Qt.AlignCenter)
        
        self.conversation_panel = ConversationPanel()
        panels_layout.addWidget(self.conversation_panel, alignment=Qt.AlignCenter)
        
        self.brush_panel = BrushPanel()
        panels_layout.addWidget(self.brush_panel, alignment=Qt.AlignCenter)
        
        # Create a container widget to position panels on the right - EXACT copy from UI.py
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.addStretch(4)  # Increased to push content more to the right
        right_layout.addWidget(panels_container)
        right_layout.setContentsMargins(0, 0, 20, 0)  # Add right margin to keep a bit of space from edge
        main_layout.addWidget(right_container)
        
        # Small space after panels - EXACT copy from UI.py
        main_layout.addSpacing(20)  # Small spacing instead of large stretch
        
        # Status bar for showing messages - EXACT copy from UI.py
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            color: rgba(200, 200, 200, 150);
            font-size: 12px;
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Add a stretcher to push everything up from the bottom - EXACT copy from UI.py
        main_layout.addStretch(1)
        
        # Close button in top-right corner - EXACT copy from UI.py
        close_button = QPushButton("×")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 180);
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 180);
            }
        """)
        
        # Position the close button in the top-right corner - EXACT copy from UI.py
        close_button.setParent(self)
        close_button.move(self.width() - 40, 10)
        

    
    def load_ui_data(self) -> Optional[Dict]:
        """Load UI data from JSON file or generate if needed"""
        try:
            # Try to load from file first
            if UI_DATA_FILE.exists():
                with open(UI_DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # If file doesn't exist and we have generator, create it
            elif self.data_generator:
                print("UI data file not found, generating...")
                ui_data = self.data_generator.generate_ui_json()
                self.data_generator.save_ui_data(ui_data)
                
                # Try loading again
                if UI_DATA_FILE.exists():
                    with open(UI_DATA_FILE, 'r', encoding='utf-8') as f:
                        return json.load(f)
            
            return None
            
        except Exception as e:
            print(f"Error loading UI data: {e}")
            return None
    
    def refresh_data(self):
        """Refresh all UI panels with latest data"""
        ui_data = self.load_ui_data()
        
        if not ui_data:
            print("No UI data available")
            return
        
        try:
            # Update conversation panel
            if "conversation" in ui_data:
                self.conversation_panel.update_conversation(ui_data["conversation"])
            
            # Update status panel
            if "current_command" in ui_data:
                self.status_panel.update_status(ui_data["current_command"])
            
            # Update brush panel
            if "brush_info" in ui_data:
                self.brush_panel.update_brush(ui_data["brush_info"])
                
        except Exception as e:
            print(f"Error updating UI: {e}")
    
    def mousePressEvent(self, event):
        """Enable window dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """Handle window dragging"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def resizeEvent(self, event):
        """Reposition close button when window is resized"""
        # Find and reposition close button
        close_buttons = [child for child in self.children() 
                         if isinstance(child, QPushButton) and child.text() == "×"]
        
        if close_buttons:
            close_buttons[0].move(self.width() - 40, 10)
            
        super().resizeEvent(event)
        
    def keyPressEvent(self, event):
        """Handle key press events"""
        # Exit with Escape key
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)

class ConjureUI(QApplication):
    """Main application class"""
    def __init__(self, argv):
        super().__init__(argv)
        
        # Set application attributes
        self.setAttribute(Qt.AA_EnableHighDpiScaling)
        self.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        
        # Use system font
        font = QFont("Segoe UI" if sys.platform == "win32" else "Helvetica")
        font.setPointSize(10)
        self.setFont(font)
        
        # Create main window
        self.main_window = ConjureMainWindow()
        
    def run(self):
        """Run the application"""
        self.main_window.show()
        return self.exec_()

def main():
    """Main function"""
    app = ConjureUI(sys.argv)
    sys.exit(app.run())

if __name__ == "__main__":
    main()
