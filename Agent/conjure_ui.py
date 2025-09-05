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
                    font-size: 10px;
                    font-weight: bold;
                    padding: 4px;
                }
            """)
        elif style_type == "subtitle":
            self.setStyleSheet("""
                QLabel {
                    color: rgba(200, 200, 200, 180);
                    font-size: 8px;
                    font-weight: bold;
                    padding: 2px;
                }
            """)
        elif style_type == "status":
            self.setStyleSheet("""
                QLabel {
                    color: rgba(100, 255, 100, 200);
                    font-size: 9px;
                    font-weight: bold;
                    padding: 3px;
                }
            """)
        else:  # normal
            self.setStyleSheet("""
                QLabel {
                    color: rgba(220, 220, 220, 180);
                    font-size: 8px;
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
                background-color: rgba(20, 20, 20, 200);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 6px;
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
                background-color: rgba(20, 20, 20, 200);
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

class PromptDisplayPanel(MinimalFrame):
    """Panel for displaying current FLUX prompt - PHASE 3 REDESIGN"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(1200, 75)  # Half as tall: 150/2 = 75
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Prompt display (no title, more space for text)
        self.prompt_text = MinimalTextEdit()
        self.prompt_text.setMaximumHeight(65)  # Adjusted for smaller 75px panel
        self.prompt_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(30, 30, 30, 200);
                border: 2px solid rgba(80, 80, 80, 150);
                border-radius: 12px;
                color: #80c0ff;
                font-size: 9px;
                font-family: Arial;
                padding: 15px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.prompt_text)
        
    def update_prompt(self, prompt_text: str):
        """Update prompt display with current userPrompt.txt content"""
        if not prompt_text:
            self.prompt_text.setPlainText("No prompt available")
            return
        
        # Display the actual prompt being used for generation
        # Remove the technical photography setup for cleaner display
        display_prompt = prompt_text
        if "Shown in a three-quarter view" in display_prompt:
            display_prompt = display_prompt.split("Shown in a three-quarter view")[0].strip()
        
        # Limit length for display
        if len(display_prompt) > 450:  # Increased from 300 to 450 for wider box
            display_prompt = display_prompt[:450] + "..."
        
        # Set plain text for clean display with styled HTML
        html_content = f"""
        <div style="color: #80c0ff; font-size: 9px; line-height: 1.5; text-align: center;">
            {display_prompt.replace(chr(10), '<br>')}
        </div>
        """
        self.prompt_text.setHtml(html_content)

class StatusPanel(MinimalFrame):
    """Panel for displaying current command and status"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(195, 78)  # 35% smaller: 300*0.65=195, 120*0.65=78
        
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

class BrushIconsPanel(MinimalFrame):
    """Left column panel for brush icons - PHASE 3 REDESIGN"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(78, 390)  # 35% smaller: 120*0.65=78, 600*0.65=390
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 13, 10, 13)  # 35% smaller: 15*0.65=10, 20*0.65=13
        layout.setSpacing(13)  # 35% smaller: 20*0.65=13
        layout.setAlignment(Qt.AlignCenter)  # Center the icons vertically
        
        # Load brush icons from the brush icons folder
        self.brush_icons = {}
        self.active_brush = "DRAW"  # Default active brush (first in system list)
        
        # Create brush icon buttons
        brush_types = ["DRAW", "GRAB", "SMOOTH", "INFLATE", "FLATTEN"]
        for brush_type in brush_types:
            button = self.create_brush_button(brush_type)
            layout.addWidget(button)
            self.brush_icons[brush_type] = button
        
        # Remove stretch - icons are now centered
        
        # Update active brush styling
        self.update_active_brush(self.active_brush)
    
    def create_brush_button(self, brush_type):
        """Create a brush icon button"""
        button = QPushButton()
        button.setFixedSize(59, 59)  # 35% smaller: 90*0.65=59
        button.setToolTip(brush_type)
        
        # Map brush types to icon filenames
        icon_mapping = {
            "GRAB": "grab.png",
            "FLATTEN": "flatten.png", 
            "INFLATE": "inflate.png",
            "SMOOTH": "soften.png",  # SMOOTH uses soften icon
            "DRAW": None             # DRAW will use text fallback
        }
        
        # Try to load the brush icon
        icon_filename = icon_mapping.get(brush_type, f"{brush_type.lower()}.png")
        
        if icon_filename:  # Only try to load if we have a filename
            icon_path = Path(__file__).parent.parent / "blender" / "assets" / "brush icons" / icon_filename
            
            if icon_path.exists():
                from PyQt5.QtGui import QIcon, QPixmap
                pixmap = QPixmap(str(icon_path))
                icon = QIcon(pixmap)
                button.setIcon(icon)
                button.setIconSize(button.size() - QSize(10, 10))  # Smaller icon padding: 15*0.65=10
            else:
                # Fallback to text if icon file doesn't exist
                button.setText(brush_type[:3])
        else:
            # Use text fallback when no icon filename specified
            button.setText(brush_type[:3])
        
        # Add click handler to make button functional
        button.clicked.connect(lambda: self.on_brush_clicked(brush_type))
        
        # Base styling for brush buttons
        button.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 150);
                border: 2px solid rgba(80, 80, 80, 100);
                border-radius: 30px;
                color: white;
                font-size: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 180);
                border: 2px solid rgba(100, 100, 100, 150);
            }
        """)
        
        return button
    
    def on_brush_clicked(self, brush_type):
        """Handle brush button clicks"""
        # Update the active brush immediately
        self.update_active_brush(brush_type)
        
        # Also update the fingertips.json file to persist the selection
        try:
            from pathlib import Path
            import json
            fingertips_path = Path(__file__).parent.parent / "data" / "input" / "fingertips.json"
            if fingertips_path.exists():
                with open(fingertips_path, 'r', encoding='utf-8') as f:
                    fingertip_data = json.load(f)
                fingertip_data["command"] = brush_type
                with open(fingertips_path, 'w', encoding='utf-8') as f:
                    json.dump(fingertip_data, f, indent=2)
                
        except Exception as e:
            print(f"Error updating fingertips.json: {e}")
    
    def update_active_brush(self, brush_type):
        """Update which brush icon is highlighted as active"""
        self.active_brush = brush_type
        
        for brush_name, button in self.brush_icons.items():
            if brush_name == brush_type:
                # Active brush styling
                button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(80, 160, 255, 200);
                        border: 3px solid rgba(120, 180, 255, 255);
                        border-radius: 30px;
                        color: white;
                        font-size: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: rgba(100, 180, 255, 220);
                        border: 3px solid rgba(140, 200, 255, 255);
                    }
                """)
            else:
                # Inactive brush styling
                button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(40, 40, 40, 150);
                        border: 2px solid rgba(80, 80, 80, 100);
                        border-radius: 30px;
                        color: white;
                        font-size: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: rgba(60, 60, 60, 180);
                        border: 2px solid rgba(100, 100, 100, 150);
                    }
                """)

class ConjureMainWindow(QMainWindow):
    """Main transparent overlay window"""
    def __init__(self):
        super().__init__()
        
        # Set window flags for transparency and always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # This helps keep it on top
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Make sure the window is visible and on top
        self.raise_()
        self.activateWindow()
        
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
        
        # Create main layout - PHASE 3 REDESIGN to match mockup
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(26, 26, 26, 26)  # 35% smaller: 40*0.65=26
        main_layout.setSpacing(13)  # 35% smaller: 20*0.65=13
        
        # Add discrete terminate button in top-left corner
        terminate_button = QPushButton("× CONJURE UI")
        terminate_button.setFixedSize(120, 30)
        terminate_button.clicked.connect(self.close)
        terminate_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 60, 60, 220);
                color: rgba(255, 255, 255, 255);
                border: 2px solid rgba(100, 100, 100, 255);
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(100, 60, 60, 240);
                color: white;
            }
        """)
        
        # Position the terminate button in the top-left corner
        terminate_button.setParent(self)
        terminate_button.move(15, 15)
        
        # Create main horizontal layout: brush icons (left) + content area (right)
        main_horizontal = QHBoxLayout()
        main_horizontal.setSpacing(26)  # 35% smaller: 40*0.65=26
        
        # Left column: Brush icons panel
        self.brush_icons_panel = BrushIconsPanel()
        main_horizontal.addWidget(self.brush_icons_panel, alignment=Qt.AlignTop)
        
        # Right area: Content layout (status top-right, prompt bottom-center)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(26)  # 35% smaller: 40*0.65=26
        
        # Top section: Status panel in top-right corner
        top_section = QHBoxLayout()
        top_section.addStretch()  # Push status to the right
        self.status_panel = StatusPanel()
        self.status_panel.setFixedSize(300, 120)  # Bigger status panel
        top_section.addWidget(self.status_panel)
        content_layout.addLayout(top_section)
        
        # Middle section: Expandable space for 3D viewport (empty space)
        content_layout.addStretch()
        
        # Bottom section: Prompt display in center-bottom
        bottom_section = QHBoxLayout()
        bottom_section.addStretch()  # Center the prompt horizontally
        self.prompt_panel = PromptDisplayPanel()
        bottom_section.addWidget(self.prompt_panel)
        bottom_section.addStretch()  # Center the prompt horizontally
        content_layout.addLayout(bottom_section)
        
        # Add content area to main horizontal layout
        main_horizontal.addLayout(content_layout)
        
        # Add the complete horizontal layout to main layout
        main_layout.addLayout(main_horizontal)
        
        # Remove old brush panel since we now have brush icons panel
        # self.brush_panel = BrushPanel()  # Removed - replaced with icons
        
        # Status label (hidden by default)
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        
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
        """Refresh all UI panels with latest data - PHASE 3 SIMPLIFICATION"""
        print("DEBUG: refresh_data() called")
        ui_data = self.load_ui_data()
        
        try:
            # PHASE 3: Update prompt panel with current userPrompt.txt
            prompt_text = self.load_current_prompt()
            self.prompt_panel.update_prompt(prompt_text)
            
            # Update status panel
            if ui_data and "current_command" in ui_data:
                self.status_panel.update_status(ui_data["current_command"])
            else:
                # Show generation status based on Phase 2 continuous loop
                import time
                current_time = int(time.time())
                cycle_position = current_time % 30
                if cycle_position < 5:
                    status = "🔄 Generating mesh..."
                elif cycle_position < 25:
                    status = f"⏳ Next generation in {30 - cycle_position}s"
                else:
                    status = "🔄 Preparing generation..."
                self.status_panel.update_status(status)
            
            # Update brush icons panel with active brush
            # Read the actual current brush from Blender via fingertips.json
            try:
                from pathlib import Path
                fingertips_path = Path(__file__).parent.parent / "data" / "input" / "fingertips.json"
                print(f"DEBUG: Reading from {fingertips_path}")
                if fingertips_path.exists():
                    import json
                    with open(fingertips_path, 'r', encoding='utf-8') as f:
                        fingertip_data = json.load(f)
                    
                    print(f"DEBUG: Loaded fingertip data: {fingertip_data}")
                    
                    # Read the actual active brush from Blender
                    active_brush = fingertip_data.get("active_brush", "DRAW")
                    print(f"DEBUG: Active brush from file: {active_brush}")
                    
                    # Map system brush names to UI brush names if needed
                    brush_mapping = {
                        "DRAW": "DRAW",
                        "GRAB": "GRAB", 
                        "SMOOTH": "SMOOTH",
                        "INFLATE": "INFLATE",
                        "FLATTEN": "FLATTEN",
                    }
                    mapped_brush = brush_mapping.get(active_brush.upper(), active_brush.upper())
                    print(f"DEBUG: Mapped brush: {mapped_brush}")
                    print(f"DEBUG: Available UI brushes: {list(self.brush_icons_panel.brush_icons.keys())}")
                    
                    if mapped_brush in self.brush_icons_panel.brush_icons:
                        print(f"DEBUG: Updating UI to show {mapped_brush} as active")
                        self.brush_icons_panel.update_active_brush(mapped_brush)
                    else:
                        print(f"DEBUG: Brush {mapped_brush} not found in UI brushes")
                else:
                    print(f"DEBUG: Fingertips file does not exist")
                    
            except Exception as e:
                print(f"DEBUG: Error reading brush info: {e}")
                # Default to DRAW if we can't read brush info
                self.brush_icons_panel.update_active_brush("DRAW")
                
        except Exception as e:
            print(f"Error updating UI: {e}")
    
    def load_current_prompt(self):
        """Load current prompt from userPrompt.txt for Phase 3"""
        try:
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent / "data" / "generated_text" / "userPrompt.txt"
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            else:
                return "No prompt file found"
        except Exception as e:
            return f"Error loading prompt: {e}"
    
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
        # Set application attributes BEFORE calling super().__init__
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        
        super().__init__(argv)
        
        # Set high DPI policy
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
