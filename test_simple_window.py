#!/usr/bin/env python3
"""
Very simple Qt window test
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class SimpleTestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIMPLE TEST WINDOW")
        self.setGeometry(100, 100, 400, 300)
        
        # Make it stay on top and visible
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        # Simple layout
        layout = QVBoxLayout()
        
        label = QLabel("🔥 SIMPLE TEST WINDOW 🔥")
        label.setStyleSheet("""
            QLabel {
                background-color: red;
                color: white;
                font-size: 24px;
                padding: 20px;
                border: 3px solid yellow;
            }
        """)
        label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(label)
        self.setLayout(layout)
        
        print(f"📍 Simple window created at: {self.geometry()}")

def test_simple_window():
    """Test basic Qt window visibility"""
    app = QApplication(sys.argv)
    
    window = SimpleTestWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    
    print("🔍 Simple window should be visible now!")
    print("   Close it or press Ctrl+C to continue...")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    test_simple_window()
