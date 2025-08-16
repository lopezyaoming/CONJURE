"""
CONJURE UI - Direct copy from UI.py reference
Minimal modifications to work with CONJURE data instead of VIBE data
"""

import sys
import os
import json
import subprocess
import time
import threading
import random
import shutil
import io
import socket
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QGraphicsOpacityEffect, 
    QGraphicsDropShadowEffect, QSizePolicy, QFrame, QDesktopWidget, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QTimer, QUrl, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPalette, QImage, QPixmap, QCursor, QPainter, QBrush, QFontDatabase

# Project paths - ADAPTED FOR CONJURE
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
AGENT_DIR = BASE_DIR / "Agent"
UI_DATA_FILE = AGENT_DIR / "ui_data.json"

# Import data generator
sys.path.insert(0, str(AGENT_DIR))
try:
    from ui_data_generator import UIDataGenerator
except ImportError:
    UIDataGenerator = None

# Custom button style - EXACT COPY FROM UI.py
class MinimalButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 180);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 200);
            }
            QPushButton:pressed {
                background-color: rgba(80, 80, 80, 220);
            }
        """)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

# Custom text input - EXACT COPY FROM UI.py
class MinimalLineEdit(QLineEdit):
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 30, 150);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: rgba(40, 40, 40, 180);
            }
        """)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

# Brush icon widget for top toolbar
class BrushIcon(QLabel):
    def __init__(self, brush_name, icon_path, parent=None):
        super().__init__(parent)
        self.brush_name = brush_name
        self.icon_path = icon_path
        self.is_active = False
        
        # Set up icon appearance
        self.setFixedSize(60, 60)
        self.setAlignment(Qt.AlignCenter)
        
        # Load and set the icon
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            # Scale the icon to fit
            scaled_pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
        
        # Set initial style (inactive)
        self.update_style()
        
        # Add drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)
    
    def set_active(self, active):
        """Set whether this brush is active"""
        self.is_active = active
        self.update_style()
    
    def update_style(self):
        """Update the visual style based on active state"""
        if self.is_active:
            # Bigger size and white frame when active
            self.setFixedSize(80, 80)  # Bigger when active
            # Reload and rescale the pixmap to the new size
            pixmap = QPixmap(self.icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(65, 65, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.setPixmap(scaled_pixmap)
                
            self.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    border: 3px solid rgba(255, 255, 255, 255);
                    border-radius: 12px;
                    padding: 8px;
                }
            """)
        else:
            # Normal size and 50% transparency when inactive
            self.setFixedSize(60, 60)  # Normal size
            # Reload and rescale the pixmap to the normal size
            pixmap = QPixmap(self.icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.setPixmap(scaled_pixmap)
                
            self.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    border: 1px solid rgba(255, 255, 255, 50);
                    border-radius: 8px;
                    padding: 5px;
                    opacity: 0.5;
                }
            """)

# Conversation display widget
class ConversationBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up frame appearance - much thinner than before
        self.setFixedHeight(120)  # Much smaller height
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(20, 20, 20, 160);
                border: none;
                border-radius: 15px;
            }
        """)
        
        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(20)
        
        # AI text (left side)
        self.ai_label = QLabel("AI: Welcome to CONJURE")
        self.ai_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.ai_label.setStyleSheet("""
            QLabel {
                background: transparent; 
                color: rgba(255, 255, 255, 255);
                font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
                font-size: 14px;
                font-weight: 400;
                padding: 10px;
            }
        """)
        self.ai_label.setWordWrap(True)
        
        # User text (right side)
        self.user_label = QLabel("User: ...")
        self.user_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.user_label.setStyleSheet("""
            QLabel {
                background: transparent; 
                color: rgba(255, 255, 255, 255);
                font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
                font-size: 14px;
                font-weight: 400;
                padding: 10px;
            }
        """)
        self.user_label.setWordWrap(True)
        
        # Add to layout
        layout.addWidget(self.ai_label, 1)  # Give AI side more space
        layout.addWidget(self.user_label, 1)  # Give user side equal space
        
        # Add drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)
    
    def update_conversation(self, ai_text="", user_text=""):
        """Update the conversation display"""
        if ai_text:
            self.ai_label.setText(f"AI: {ai_text}")
        if user_text:
            self.user_label.setText(f"User: {user_text}")

# Workflow popup for mesh generation
class WorkflowPopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up popup appearance
        self.setFixedSize(300, 150)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 40, 200);
                border: 2px solid rgba(100, 100, 100, 180);
                border-radius: 15px;
            }
        """)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)
        
        # Title
        title_label = QLabel("Mesh Generation")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 255);
                font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
                font-size: 16px;
                font-weight: 500;
                background: transparent;
            }
        """)
        
        # Status
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 255);
                font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
                font-size: 12px;
                font-weight: 400;
                background: transparent;
            }
        """)
        
        # Progress indicator (simple text for now)
        self.progress_label = QLabel("●●●")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 255);
                font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
                font-size: 14px;
                font-weight: 400;
                background: transparent;
            }
        """)
        
        layout.addWidget(title_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_label)
        
        # Add drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 10)
        self.setGraphicsEffect(shadow)
        
        # Initially hidden
        self.hide()
    
    def show_workflow(self, status="Processing..."):
        """Show the workflow popup with given status"""
        self.status_label.setText(status)
        self.show()
        
        # Center on parent
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(
                parent_rect.center().x() - self.width() // 2,
                parent_rect.center().y() - self.height() // 2
            )
    
    def hide_workflow(self):
        """Hide the workflow popup"""
        self.hide()

# Main window class - DIRECT COPY FROM UI.py WITH MINIMAL CHANGES
class TransparentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window flags for transparency and always on top - ENHANCED FOR BLENDER
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # This helps keep it above other app windows
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Ensure it's always at the top level
        self.raise_()
        self.activateWindow()
        
        # Data generator
        self.data_generator = UIDataGenerator() if UIDataGenerator else None
        
        # Set up the UI
        self.init_ui()
        
        # Set up timer for periodic refresh - EXACT COPY FROM UI.py
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_data)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Additional timer to ensure window stays on top (more aggressive)
        self.top_timer = QTimer(self)
        self.top_timer.timeout.connect(self.ensure_on_top)
        self.top_timer.start(1000)  # Every 1 second for better visibility
        
        # Load initial data
        self.load_data()
        
        # Make fullscreen - EXACT COPY FROM UI.py
        self.showFullScreen()
        
        # Force window to be visible and on top
        print("CONJURE UI window created and showing...")
        self.ensure_on_top()
        print(f"UI window geometry: {self.geometry()}")
        print(f"UI window visible: {self.isVisible()}")
        print(f"UI window flags: {self.windowFlags()}")
        
    def init_ui(self):
        # Window configuration - EXACT COPY FROM UI.py
        self.setWindowTitle("CONJURE UI Overlay")
        
        # Create central widget with transparent background - EXACT COPY FROM UI.py
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Create main layout - REDESIGNED FOR NEW UI
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(0)  # No spacing between elements
        
        # Add discrete terminate button in top-left corner - EXACT COPY FROM UI.py
        terminate_button = MinimalButton("×")
        terminate_button.setFixedSize(26, 26)
        terminate_button.clicked.connect(self.shutdown_conjure_system)  # Use shutdown method
        terminate_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 150);
                color: rgba(220, 220, 220, 180);
                border: none;
                border-radius: 13px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 200);
                color: rgba(255, 255, 255, 220);
            }
        """)
        
        # Position the terminate button in the top-left corner - EXACT COPY FROM UI.py
        terminate_button.setParent(self)
        terminate_button.move(15, 15)
        
        # TOP SECTION: Brush icons toolbar
        brush_toolbar = QWidget()
        brush_layout = QHBoxLayout(brush_toolbar)
        brush_layout.setContentsMargins(0, 20, 0, 20)
        brush_layout.setSpacing(15)
        brush_layout.setAlignment(Qt.AlignCenter)
        
        # Create brush icons
        self.brush_icons = {}
        brush_names = ["grab", "flatten", "inflate", "soften"]
        base_path = Path(__file__).parent.parent / "blender" / "assets" / "brush icons"
        
        for brush_name in brush_names:
            icon_path = base_path / f"{brush_name}.png"
            if icon_path.exists():
                brush_icon = BrushIcon(brush_name, str(icon_path))
                self.brush_icons[brush_name] = brush_icon
                brush_layout.addWidget(brush_icon)
        
        # Set all brushes to inactive initially (50% transparency)
        for brush_icon in self.brush_icons.values():
            brush_icon.set_active(False)
        
        # MIDDLE SECTION: Large spacer to push conversation bar to bottom (4K monitor)
        spacer_top = QWidget()
        spacer_top.setFixedHeight(1000)  # Much larger spacer for 4K monitor
        
        # BOTTOM SECTION: Conversation bar
        self.conversation_bar = ConversationBar()
        
        # WORKFLOW POPUP: Create but don't add to layout (it's positioned absolutely)
        self.workflow_popup = WorkflowPopup(central_widget)
        
        # Add sections to main layout
        main_layout.addWidget(brush_toolbar, alignment=Qt.AlignTop | Qt.AlignCenter)
        main_layout.addWidget(spacer_top)
        main_layout.addWidget(self.conversation_bar, alignment=Qt.AlignBottom | Qt.AlignCenter)
        main_layout.addStretch()  # Bottom stretch
        

        
    def ensure_on_top(self):
        """Ensure the window stays on top of all other windows"""
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        self.show()  # Force show in case it gets hidden
    
    def shutdown_conjure_system(self):
        """Shutdown the entire CONJURE system via shutdown file"""
        try:
            import sys
            import os
            import time
            from pathlib import Path
            
            print("🛑 CONJURE UI: Shutting down entire system...")
            
            # Create a shutdown signal file that main.py monitors
            try:
                # Calculate project root more reliably
                current_file = Path(__file__).resolve()
                print(f"🔍 Current file: {current_file}")
                
                # Go up from Agent/conjure_ui_direct.py to project root
                project_root = current_file.parent.parent
                print(f"🔍 Project root: {project_root}")
                
                shutdown_file = project_root / "shutdown_signal.txt"
                print(f"🔍 Shutdown file path: {shutdown_file}")
                
                with open(shutdown_file, 'w') as f:
                    f.write("UI_SHUTDOWN_REQUEST\n")
                    f.write(f"timestamp={time.time()}\n")
                    f.write("source=UI_OVERLAY\n")
                
                print(f"✅ CONJURE system shutdown signal file created at: {shutdown_file}")
                
                # Verify the file was created
                if shutdown_file.exists():
                    print("✅ Shutdown file verified to exist")
                else:
                    print("❌ Shutdown file was not created successfully")
                
                # Also try API call as backup
                try:
                    import requests
                    response = requests.post("http://127.0.0.1:8000/shutdown", timeout=2)
                    if response.status_code == 200:
                        print("✅ API shutdown signal also sent")
                except:
                    print("⚠️ API shutdown call failed, relying on file signal")
                
            except Exception as e:
                print(f"⚠️ Could not create shutdown signal file: {e}")
            
            # Close the UI window
            self.close()
            
            # Exit the UI process
            sys.exit(0)
            
        except Exception as e:
            print(f"❌ Error during system shutdown: {e}")
            # Fallback: just close the UI
            self.close()
    
    def load_data(self):
        """Load CONJURE data for the new UI layout"""
        try:
            if self.data_generator:
                # Generate fresh UI data
                ui_data = self.data_generator.generate_ui_json()
                self.data_generator.save_ui_data(ui_data)
                
                # Update conversation bar
                ai_text = ""
                user_text = ""
                
                if ui_data.conversation:
                    # Get the most recent messages
                    for msg in reversed(ui_data.conversation[-5:]):  # Last 5 messages
                        if msg.speaker == "AGENT" and not ai_text:
                            ai_text = msg.message[:150]  # Longer text for conversation
                        elif msg.speaker == "USER" and not user_text:
                            user_text = msg.message[:150]  # Longer text for conversation
                        
                        if ai_text and user_text:
                            break
                
                self.conversation_bar.update_conversation(ai_text, user_text)
                
                # Update active brush based on current tool and activity
                current_brush = ui_data.brush_info.active_command.lower()
                is_actively_deforming = (ui_data.brush_info.fingertip_count > 0 and 
                                        ui_data.brush_info.active_hand is not None)
                
                for brush_name, brush_icon in self.brush_icons.items():
                    # Only show as active if brush matches AND user is actively deforming
                    is_active = (brush_name == current_brush and is_actively_deforming)
                    brush_icon.set_active(is_active)
                
                # Handle workflow popup for mesh generation
                if ui_data.workflow_progress.active:
                    status_text = f"{ui_data.workflow_progress.current_stage}"
                    if ui_data.workflow_progress.overall_progress > 0:
                        status_text += f" ({ui_data.workflow_progress.overall_progress:.0f}%)"
                    self.workflow_popup.show_workflow(status_text)
                else:
                    self.workflow_popup.hide_workflow()
                    
            else:
                # Fallback when no data generator
                self.conversation_bar.update_conversation("System: Data generator unavailable", "")
                
        except Exception as e:
            print(f"Error loading CONJURE data: {e}")
            self.conversation_bar.update_conversation(f"Error: {str(e)}", "")

    def mousePressEvent(self, event):
        """Enable window dragging - EXACT COPY FROM UI.py"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """Handle window dragging - EXACT COPY FROM UI.py"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def resizeEvent(self, event):
        """Reposition buttons when window is resized - EXACT COPY FROM UI.py"""
        # Find and reposition close button
        close_buttons = [child for child in self.children() 
                         if isinstance(child, MinimalButton) and child.text() == "×" 
                         and child.width() == 30]  # Match the close button by size
        
        # Find and reposition terminate button
        terminate_buttons = [child for child in self.children() 
                            if isinstance(child, MinimalButton) and child.text() == "×" 
                            and child.width() == 26]  # Match the terminate button by size
        
        if close_buttons:
            close_buttons[0].move(self.width() - 40, 10)
            
        if terminate_buttons:
            terminate_buttons[0].move(15, 15)
            
        super().resizeEvent(event)
        
    def keyPressEvent(self, event):
        """Handle key press events - EXACT COPY FROM UI.py"""
        # Exit fullscreen with Escape key
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def terminate_script(self):
        """Terminate UI - ADAPTED FROM UI.py"""
        try:
            # Show confirmation dialog
            reply = self.show_confirmation_dialog(
                "Close CONJURE UI", 
                "Are you sure you want to close the CONJURE UI?",
                "This will close the UI overlay but CONJURE will continue running."
            )
            
            if reply:
                self.status_label.setText("Closing CONJURE UI...")
                QApplication.quit()
                
        except Exception as e:
            self.status_label.setText(f"Error closing: {str(e)}")
    
    def show_confirmation_dialog(self, title, message, detail=""):
        """Show a confirmation dialog and return True if confirmed - EXACT COPY FROM UI.py"""
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        if detail:
            msg_box.setInformativeText(detail)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        
        # Style the message box - EXACT COPY FROM UI.py
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #333333;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #555555;
                color: #ffffff;
                border: 1px solid #777777;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        
        # Return True if user clicked Yes
        return msg_box.exec_() == QMessageBox.Yes

# Run the application - EXACT COPY FROM UI.py
if __name__ == "__main__":
    # Set application attributes - EXACT COPY FROM UI.py
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    
    # Use a system font instead of requiring Roboto - EXACT COPY FROM UI.py
    font = QFont("Segoe UI" if sys.platform == "win32" else "Helvetica")
    font.setPointSize(10)
    app.setFont(font)
    
    window = TransparentWindow()
    # CRITICAL: Use show() not showFullScreen() like original UI.py when run as script!
    window.show()
    
    sys.exit(app.exec_())
