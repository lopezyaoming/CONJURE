#!/usr/bin/env python3
"""
Debug test for UI overlay visibility issues
"""

import sys
import time
from pathlib import Path

# Ensure we can import from Agent directory
sys.path.insert(0, str(Path(__file__).parent / "Agent"))

from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFrame, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

class DebugOverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        print("🔧 Creating debug overlay window...")
        
        # Test different window flag combinations
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Force window properties
        self.setWindowTitle("CONJURE UI DEBUG OVERLAY")
        
        # Create a very visible test UI
        self.init_debug_ui()
        
        # Make it fullscreen
        self.showFullScreen()
        
        # Force visibility
        self.raise_()
        self.activateWindow()
        self.show()
        
        print(f"🖥️  Debug window created:")
        print(f"   Geometry: {self.geometry()}")
        print(f"   Visible: {self.isVisible()}")
        print(f"   Minimized: {self.isMinimized()}")
        print(f"   WindowFlags: {self.windowFlags()}")
        
        # Timer to keep it on top
        self.top_timer = QTimer(self)
        self.top_timer.timeout.connect(self.force_on_top)
        self.top_timer.start(1000)
        
    def init_debug_ui(self):
        """Create a very obvious test UI"""
        # Create central widget
        central_widget = QFrame()
        central_widget.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 0, 0, 100);  /* Semi-transparent red */
                border: 5px solid yellow;
            }
        """)
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(50, 50, 50, 50)
        
        # Add very visible test elements
        title_label = QLabel("🚨 CONJURE UI DEBUG OVERLAY 🚨")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(255, 0, 0, 200);
                font-size: 48px;
                font-weight: bold;
                padding: 20px;
                border: 3px solid yellow;
                border-radius: 10px;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Add status info
        status_label = QLabel("If you can see this, the UI overlay is working!")
        status_label.setStyleSheet("""
            QLabel {
                color: yellow;
                background-color: rgba(0, 0, 255, 150);
                font-size: 24px;
                padding: 15px;
                border: 2px solid white;
            }
        """)
        status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_label)
        
        # Add position info
        pos_label = QLabel(f"Window Position: {self.pos()}\nWindow Size: {self.size()}")
        pos_label.setStyleSheet("""
            QLabel {
                color: black;
                background-color: rgba(255, 255, 0, 200);
                font-size: 18px;
                padding: 10px;
            }
        """)
        layout.addWidget(pos_label)
        
        # Add corners test - put boxes in all 4 corners
        self.add_corner_indicators()
        
    def add_corner_indicators(self):
        """Add colored boxes in all corners to test positioning"""
        corner_size = 100
        
        # Top-left corner
        tl_corner = QLabel("TOP LEFT")
        tl_corner.setParent(self)
        tl_corner.setGeometry(0, 0, corner_size, corner_size)
        tl_corner.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        tl_corner.setAlignment(Qt.AlignCenter)
        tl_corner.show()
        
        # Top-right corner  
        tr_corner = QLabel("TOP RIGHT")
        tr_corner.setParent(self)
        tr_corner.setGeometry(self.width() - corner_size, 0, corner_size, corner_size)
        tr_corner.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        tr_corner.setAlignment(Qt.AlignCenter)
        tr_corner.show()
        
        # Bottom-left corner
        bl_corner = QLabel("BOTTOM LEFT")
        bl_corner.setParent(self)
        bl_corner.setGeometry(0, self.height() - corner_size, corner_size, corner_size)
        bl_corner.setStyleSheet("background-color: blue; color: white; font-weight: bold;")
        bl_corner.setAlignment(Qt.AlignCenter)
        bl_corner.show()
        
        # Bottom-right corner
        br_corner = QLabel("BOTTOM RIGHT")
        br_corner.setParent(self)
        br_corner.setGeometry(self.width() - corner_size, self.height() - corner_size, corner_size, corner_size)
        br_corner.setStyleSheet("background-color: purple; color: white; font-weight: bold;")
        br_corner.setAlignment(Qt.AlignCenter)
        br_corner.show()
        
    def force_on_top(self):
        """Aggressively force window to stay on top"""
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        self.show()
        print(f"🔄 Forcing on top - Visible: {self.isVisible()}, Pos: {self.pos()}")

def test_ui_overlay():
    """Test the UI overlay in isolation"""
    print("🧪 Testing UI overlay visibility...")
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Set high DPI attributes
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    except:
        pass
    
    print(f"📱 Primary screen geometry: {app.primaryScreen().geometry()}")
    print(f"📱 Available screens: {len(app.screens())}")
    for i, screen in enumerate(app.screens()):
        print(f"   Screen {i}: {screen.geometry()}")
    
    # Create debug window
    window = DebugOverlayWindow()
    
    print("🎯 Debug overlay should now be visible on screen!")
    print("   - Look for a red semi-transparent overlay with yellow border")
    print("   - Check all corners for colored boxes")
    print("   - Press Ctrl+C to close")
    
    # Run for 30 seconds then auto-close
    def auto_close():
        print("⏰ Auto-closing debug overlay...")
        app.quit()
    
    auto_close_timer = QTimer()
    auto_close_timer.timeout.connect(auto_close)
    auto_close_timer.start(30000)  # 30 seconds
    
    # Run the app
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("👋 Debug overlay closed by user")

if __name__ == "__main__":
    test_ui_overlay()
