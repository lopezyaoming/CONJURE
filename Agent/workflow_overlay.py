"""
Workflow Progress Overlay for CONJURE
Semi-transparent full-screen overlay showing mesh generation progress
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Optional
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QProgressBar, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent
UI_DATA_FILE = AGENT_DIR / "ui_data.json"

class AnimatedProgressBar(QProgressBar):
    """Custom progress bar with smooth animations"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QProgressBar {
                background-color: rgba(30, 30, 30, 150);
                border: 2px solid rgba(80, 80, 80, 200);
                border-radius: 10px;
                text-align: center;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(100, 200, 255, 200),
                    stop:0.5 rgba(120, 220, 255, 230),
                    stop:1 rgba(100, 200, 255, 200)
                );
                border-radius: 8px;
                margin: 2px;
            }
        """)
        
        # Animation for smooth progress updates
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(500)  # 0.5 second animation
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        
    def setAnimatedValue(self, value):
        """Set value with smooth animation"""
        self.animation.setStartValue(self.value())
        self.animation.setEndValue(value)
        self.animation.start()

class PulsingLabel(QLabel):
    """Label with pulsing animation effect"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        
        # Opacity effect for pulsing
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        # Animation for pulsing
        self.pulse_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.pulse_animation.setDuration(1500)  # 1.5 seconds
        self.pulse_animation.setStartValue(0.5)
        self.pulse_animation.setEndValue(1.0)
        self.pulse_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse_animation.setLoopCount(-1)  # Infinite loop
        
    def start_pulsing(self):
        """Start the pulsing animation"""
        self.pulse_animation.start()
        
    def stop_pulsing(self):
        """Stop the pulsing animation"""
        self.pulse_animation.stop()
        self.opacity_effect.setOpacity(1.0)

class LoadingDotsLabel(QLabel):
    """Label with animated loading dots"""
    def __init__(self, base_text="MESH GENERATION", parent=None):
        super().__init__(parent)
        self.base_text = base_text
        self.dot_count = 0
        
        # Timer for dots animation
        self.dots_timer = QTimer()
        self.dots_timer.timeout.connect(self.update_dots)
        self.dots_timer.start(500)  # Update every 0.5 seconds
        
        self.update_dots()
        
    def update_dots(self):
        """Update the dots animation"""
        dots = "." * (self.dot_count % 4)  # 0-3 dots
        self.setText(f"{self.base_text}{dots}")
        self.dot_count += 1
        
    def stop_animation(self):
        """Stop the dots animation"""
        self.dots_timer.stop()

class WorkflowProgressOverlay(QWidget):
    """Semi-transparent full-screen overlay for workflow progress"""
    
    # Signal emitted when overlay should be hidden
    hide_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set window flags for overlay
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # Makes it not appear in taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Make it full screen
        self.showFullScreen()
        
        # Initialize UI
        self.init_ui()
        
        # Timer for checking progress
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_workflow_status)
        self.check_timer.start(1000)  # Check every second
        
        # Track if workflow is complete
        self.workflow_complete = False
        
    def init_ui(self):
        """Initialize the overlay UI"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create central container
        center_widget = QWidget()
        center_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 120);
            }
        """)
        
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(50, 50, 50, 50)
        center_layout.setSpacing(30)
        center_layout.setAlignment(Qt.AlignCenter)
        
        # Main title with loading dots
        self.title_label = LoadingDotsLabel("MESH GENERATION")
        self.title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 48px;
                font-weight: bold;
                font-family: 'Arial', sans-serif;
                text-align: center;
            }
        """)
        self.title_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.title_label)
        
        # Progress bar
        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setFixedSize(600, 40)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        center_layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        
        # Current stage label
        self.stage_label = PulsingLabel("Initializing...")
        self.stage_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 200, 220);
                font-size: 18px;
                font-weight: normal;
                text-align: center;
            }
        """)
        self.stage_label.setAlignment(Qt.AlignCenter)
        self.stage_label.start_pulsing()
        center_layout.addWidget(self.stage_label)
        
        # Current node label
        self.node_label = QLabel("Starting workflow...")
        self.node_label.setStyleSheet("""
            QLabel {
                color: rgba(150, 150, 150, 180);
                font-size: 14px;
                text-align: center;
            }
        """)
        self.node_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.node_label)
        
        # Time remaining label
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("""
            QLabel {
                color: rgba(180, 180, 180, 160);
                font-size: 12px;
                text-align: center;
            }
        """)
        self.time_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.time_label)
        
        # Add some spacing
        center_layout.addSpacing(50)
        
        # Instructions label
        instructions = QLabel("Please wait while your mesh is being generated...\nPress ESC to cancel")
        instructions.setStyleSheet("""
            QLabel {
                color: rgba(120, 120, 120, 150);
                font-size: 12px;
                text-align: center;
            }
        """)
        instructions.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(instructions)
        
        # Set the center widget
        main_layout.addWidget(center_widget)
        
    def paintEvent(self, event):
        """Custom paint event for semi-transparent background"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent background
        brush = QBrush(QColor(0, 0, 0, 100))
        painter.fillRect(self.rect(), brush)
        
        super().paintEvent(event)
    
    def load_workflow_data(self) -> Optional[Dict]:
        """Load workflow progress data"""
        try:
            if UI_DATA_FILE.exists():
                with open(UI_DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("workflow_progress", {})
            return None
        except Exception as e:
            print(f"Error loading workflow data: {e}")
            return None
    
    def check_workflow_status(self):
        """Check if workflow is still active and update progress"""
        workflow_data = self.load_workflow_data()
        
        if not workflow_data:
            # No data available, keep showing overlay but with default state
            self.update_progress(0, "Waiting for workflow data...", "Checking status", "")
            return
        
        # Check if workflow is still active
        is_active = workflow_data.get("active", False)
        
        if not is_active and not self.workflow_complete:
            # Workflow finished
            self.workflow_complete = True
            self.show_completion()
            return
        elif not is_active:
            # Already completed, hide overlay
            self.hide_overlay()
            return
        
        # Update progress display
        progress = workflow_data.get("overall_progress", 0)
        stage = workflow_data.get("current_stage", "Processing")
        node = workflow_data.get("current_node", "Unknown")
        time_remaining = workflow_data.get("estimated_time_remaining", "")
        
        self.update_progress(progress, stage, node, time_remaining)
    
    def update_progress(self, progress: float, stage: str, node: str, time_remaining: str):
        """Update the progress display"""
        # Update progress bar with animation
        self.progress_bar.setAnimatedValue(int(progress))
        
        # Update labels
        self.stage_label.setText(stage)
        self.node_label.setText(f"Current: {node}")
        
        if time_remaining and time_remaining != "N/A":
            self.time_label.setText(f"Estimated time remaining: {time_remaining}")
        else:
            self.time_label.setText("")
    
    def show_completion(self):
        """Show completion animation"""
        # Stop dots animation and show completion
        self.title_label.stop_animation()
        self.title_label.setText("MESH GENERATION COMPLETE!")
        
        # Stop pulsing
        self.stage_label.stop_pulsing()
        self.stage_label.setText("Generation successful")
        
        # Set progress to 100%
        self.progress_bar.setAnimatedValue(100)
        
        # Update other labels
        self.node_label.setText("Workflow completed")
        self.time_label.setText("Ready to proceed")
        
        # Hide after 3 seconds
        QTimer.singleShot(3000, self.hide_overlay)
    
    def hide_overlay(self):
        """Hide the overlay"""
        self.check_timer.stop()
        self.hide()
        self.hide_requested.emit()
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            # Cancel workflow (could add cancellation logic here)
            self.hide_overlay()
        super().keyPressEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse clicks (ignore to prevent closing accidentally)"""
        # Do nothing - prevents accidental closing
        pass

class WorkflowOverlayManager:
    """Manager for the workflow overlay"""
    def __init__(self):
        self.overlay = None
        self.app = None
        
    def show_overlay(self):
        """Show the workflow overlay"""
        if not self.app:
            # Create application if not exists
            if not QApplication.instance():
                self.app = QApplication(sys.argv)
            else:
                self.app = QApplication.instance()
        
        if not self.overlay:
            self.overlay = WorkflowProgressOverlay()
            self.overlay.hide_requested.connect(self.hide_overlay)
        
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        
    def hide_overlay(self):
        """Hide the workflow overlay"""
        if self.overlay:
            self.overlay.hide()
    
    def is_visible(self) -> bool:
        """Check if overlay is currently visible"""
        return self.overlay and self.overlay.isVisible()

def main():
    """Main function for standalone testing"""
    app = QApplication(sys.argv)
    
    # Set application attributes
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    # Create and show overlay
    overlay = WorkflowProgressOverlay()
    overlay.show()
    
    # Test progress updates
    def test_progress():
        import random
        progress = random.randint(0, 100)
        stages = ["FLUX Generation", "Depth Processing", "Mesh Creation", "Cleanup"]
        nodes = ["KSampler", "DepthProcessor", "MeshGenerator", "Finalizer"]
        
        stage = stages[progress // 25] if progress < 100 else "Complete"
        node = nodes[progress // 25] if progress < 100 else "Done"
        
        overlay.update_progress(progress, stage, node, f"{120 - progress}s")
        
        if progress >= 100:
            QTimer.singleShot(2000, overlay.show_completion)
    
    # Test timer
    test_timer = QTimer()
    test_timer.timeout.connect(test_progress)
    test_timer.start(2000)  # Update every 2 seconds
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
