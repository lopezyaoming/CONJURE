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

# Project paths
BASE_DIR = r"C:\CODING\VIBE\VIBE_Forming"
OPTIONS_DIR = os.path.join(BASE_DIR, "input", "options")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEXTOPT_DIR = os.path.join(BASE_DIR, "input", "COMFYINPUTS", "textOptions")
INPUT_TEXT_FILE = os.path.join(BASE_DIR, "input", "input.txt")
OPTIONS_API_SCRIPT = os.path.join(BASE_DIR, "src", "comfyworkflows", "options_API.py")
MULTIVIEW_API_SCRIPT = os.path.join(BASE_DIR, "src", "comfyworkflows", "multiview_API.py")
BLENDER_RENDER_DIR = os.path.join(BASE_DIR, "input", "COMFYINPUTS", "blenderRender")
BLENDER_SCRIPT_PATH = os.path.join(BASE_DIR, "src", "main.py")

# Common Blender installation locations to check
BLENDER_INSTALL_PATHS = [
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.5\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.4\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 2.93\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 2.92\blender.exe",
    # Add more potential paths as needed
]

# Ensure all necessary directories exist
for path in [OPTIONS_DIR, OUTPUT_DIR, TEXTOPT_DIR]:
    os.makedirs(path, exist_ok=True)

# Function to verify if a PNG file is valid
def is_valid_png(file_path):
    try:
        # Check if file exists and has content
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return False
            
        # Try to read the first 8 bytes to verify PNG signature
        with open(file_path, 'rb') as f:
            header = f.read(8)
            # Check for PNG signature (89 50 4E 47 0D 0A 1A 0A)
            return header == b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
    except Exception as e:
        print(f"Error checking PNG file {file_path}: {str(e)}")
        return False

# Worker thread for running scripts
class ScriptRunner(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self, script_path, working_dir=None):
        super().__init__()
        self.script_path = script_path
        self.working_dir = working_dir or os.path.dirname(script_path)
        
    def run(self):
        try:
            self.progress.emit("Running script...")
            
            # Start the process
            process = subprocess.Popen(
                [sys.executable, self.script_path], 
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor output
            while process.poll() is None:
                stdout_line = process.stdout.readline()
                if stdout_line:
                    self.progress.emit(stdout_line.strip())
                
            # Get any remaining output
            stdout, stderr = process.communicate()
            if stdout:
                self.progress.emit(stdout.strip())
                
            if process.returncode == 0:
                self.finished.emit(True, "Script completed successfully")
            else:
                self.finished.emit(False, f"Script failed: {stderr}")
                
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

# Custom BlenderRenderThread for executing Blender in the background
class BlenderRenderThread(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self, script_path, blender_path="blender"):
        super().__init__()
        self.script_path = script_path
        self.blender_path = blender_path
        
    def run(self):
        try:
            self.progress.emit("Starting Blender render...")
            
            # Start the Blender process
            process = subprocess.Popen(
                [self.blender_path, "--background", "--python", self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor output
            while process.poll() is None:
                stdout_line = process.stdout.readline()
                if stdout_line:
                    self.progress.emit(stdout_line.strip())
                
            # Get any remaining output
            stdout, stderr = process.communicate()
            if stdout:
                self.progress.emit(stdout.strip())
                
            if process.returncode == 0:
                self.finished.emit(True, "Blender render completed successfully")
            else:
                self.finished.emit(False, f"Blender render failed: {stderr}")
                
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

# Custom button style
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

# Custom text input
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

# Custom frame for displaying images
class ImageFrame(QFrame):
    doubleClicked = pyqtSignal(str)
    
    def __init__(self, option="", parent=None):
        super().__init__(parent)
        self.option = option
        self.image_path = ""
        self.pixmap = None
        
        # Set up frame appearance
        self.setFixedSize(240, 240)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(20, 20, 20, 150);
                border: none;
                border-radius: 10px;
            }
        """)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Create image label
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.image_label)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)
        
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.option)
        super().mouseDoubleClickEvent(event)
        
    def load_image(self, image_path):
        # First verify that the image path exists and is a valid PNG
        if not os.path.exists(image_path):
            print(f"Image path does not exist: {image_path}")
            return False
            
        # Verify PNG integrity
        if not is_valid_png(image_path):
            print(f"Invalid PNG file: {image_path}")
            return False
            
        try:
            self.image_path = image_path
            
            # Try to load the image with error handling
            for attempt in range(3):  # Try up to 3 times
                try:
                    self.pixmap = QPixmap(image_path)
                    if not self.pixmap.isNull():
                        self.image_label.setPixmap(self.pixmap.scaled(
                            220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        ))
                        return True
                    else:
                        # If pixmap is null, wait a moment and try again
                        time.sleep(0.5)
                except Exception as e:
                    print(f"Error loading image (attempt {attempt+1}): {str(e)}")
                    time.sleep(0.5)  # Wait before retry
            
            # If we got here, all attempts failed
            return False
        except Exception as e:
            print(f"Critical error loading image {image_path}: {str(e)}")
            return False

# Main window class
class TransparentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window flags for transparency and always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set up the UI
        self.init_ui()
        
        # Set up timer for periodic image refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_images)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Load initial images
        self.load_images()
        
        # Make fullscreen
        self.showFullScreen()
        
    def init_ui(self):
        # Window configuration
        self.setWindowTitle("VIBE UI Overlay")
        
        # Create central widget with transparent background
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)  # Reduced spacing
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Add discrete terminate button in top-left corner
        terminate_button = MinimalButton("×")
        terminate_button.setFixedSize(26, 26)
        terminate_button.clicked.connect(self.terminate_script)
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
        
        # Position the terminate button in the top-left corner
        terminate_button.setParent(self)
        terminate_button.move(15, 15)
        
        # Create images container - vertical orientation
        images_container = QWidget()
        images_layout = QVBoxLayout(images_container)
        images_layout.setSpacing(30)  # Reduced vertical spacing
        images_layout.setAlignment(Qt.AlignCenter)
        
        # Create image frames
        self.image_frames = {}
        for option in ["A", "B", "C"]:
            frame = ImageFrame(option)
            frame.doubleClicked.connect(self.select_option)
            self.image_frames[option] = frame
            images_layout.addWidget(frame, alignment=Qt.AlignCenter)
        
        # Create a container widget to position images on the right
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.addStretch(4)  # Increased to push content more to the right
        right_layout.addWidget(images_container)
        right_layout.setContentsMargins(0, 0, 20, 0)  # Add right margin to keep a bit of space from edge
        main_layout.addWidget(right_container)
        
        # Create prompt input area in the middle (after images but before stretcher)
        prompt_container = QWidget()
        prompt_layout = QHBoxLayout(prompt_container)
        prompt_layout.setContentsMargins(50, 10, 50, 10)
        
        self.prompt_input = MinimalLineEdit(placeholder="prompt:")
        self.prompt_input.setFixedWidth(500)
        # Connect Enter key press to submit
        self.prompt_input.returnPressed.connect(self.submit_prompt)
        prompt_layout.addWidget(self.prompt_input, alignment=Qt.AlignCenter)
        
        # Submit button
        self.submit_btn = MinimalButton("Generate")
        self.submit_btn.clicked.connect(self.submit_prompt)
        prompt_layout.addWidget(self.submit_btn)
        
        # Add remesh toggle button
        self.remesh_btn = MinimalButton("Remesh (1)")
        self.remesh_btn.clicked.connect(self.toggle_remesh)
        # Set a checkable button that can be toggled on/off
        self.remesh_btn.setCheckable(True)
        self.remesh_btn.setChecked(False)
        prompt_layout.addWidget(self.remesh_btn)
        
        # Add prompt container with horizontal centering
        prompt_wrapper = QWidget()
        prompt_wrapper_layout = QHBoxLayout(prompt_wrapper)
        prompt_wrapper_layout.addStretch(1)
        prompt_wrapper_layout.addWidget(prompt_container)
        prompt_wrapper_layout.addStretch(1)
        main_layout.addWidget(prompt_wrapper)
        
        # Small space after prompt
        main_layout.addSpacing(20)  # Small spacing instead of large stretch
        
        # Status bar for showing messages
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            color: rgba(200, 200, 200, 150);
            font-size: 12px;
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Add a stretcher to push everything up from the bottom
        main_layout.addStretch(1)
        
        # Close button in top-right corner
        close_button = MinimalButton("×")
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
        
        # Position the close button in the top-right corner
        close_button.setParent(self)
        close_button.move(self.width() - 40, 10)
        
    def load_images(self):
        """Load or refresh the option images"""
        successful_loads = 0
        print("------- Starting image refresh -------")
        
        # Check remesh state file for stage updates
        self.check_remesh_state()
        
        for option in ["A", "B", "C"]:
            try:
                image_path = os.path.join(OPTIONS_DIR, f"{option}.png")
                print(f"Checking image {option}.png at {image_path}")
                
                # Check if file exists first (most basic check)
                if not os.path.exists(image_path):
                    print(f"Image {option}.png does not exist")
                    self.status_label.setText(f"Image {option}.png not found")
                    continue
                    
                # Check file size before validation
                file_size = os.path.getsize(image_path)
                if file_size == 0:
                    print(f"Image {option}.png exists but is empty (0 bytes)")
                    self.status_label.setText(f"Image {option}.png exists but is empty")
                    continue
                    
                print(f"Image {option}.png exists with size {file_size} bytes")
                
                # Wait a moment in case file is still being written
                time.sleep(0.1)
                
                # Try to load the image even if PNG validation fails
                try:
                    # First try direct loading to see if it works without validation
                    self.pixmap = QPixmap(image_path)
                    if not self.pixmap.isNull():
                        print(f"Successfully loaded {option}.png directly")
                        self.image_frames[option].load_image(image_path)
                        successful_loads += 1
                        continue
                except Exception as e:
                    print(f"Direct loading of {option}.png failed: {str(e)}")
                
                # Try using our validation and loading approach as backup
                if not is_valid_png(image_path):
                    print(f"Image {option}.png failed PNG validation")
                    
                    # Try to find a backup or alternative file
                    alt_path = os.path.join(OPTIONS_DIR, f"{option}_backup.png")
                    if os.path.exists(alt_path) and is_valid_png(alt_path):
                        print(f"Using backup image for {option}")
                        image_path = alt_path
                    else:
                        # Try loading with more lenient approach
                        if self.try_load_image_lenient(option, image_path):
                            successful_loads += 1
                        continue
                
                # Try to load the image
                if self.image_frames[option].load_image(image_path):
                    print(f"Successfully loaded {option}.png via normal method")
                    successful_loads += 1
                else:
                    self.status_label.setText(f"Failed to load image {option}.png")
                    print(f"Failed to load {option}.png via normal method")
            except Exception as e:
                print(f"Exception loading {option}.png: {str(e)}")
                self.status_label.setText(f"Error loading {option}.png: {str(e)}")
                
        print(f"Successfully loaded {successful_loads} images")
        if successful_loads > 0:
            self.status_label.setText(f"Loaded {successful_loads} images successfully")
            
    def try_load_image_lenient(self, option, image_path):
        """Try to load image even if validation fails"""
        try:
            # Make a direct pixmap load attempt with no validation
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Directly set the pixmap to the image frame
                self.image_frames[option].image_path = image_path
                self.image_frames[option].pixmap = pixmap
                self.image_frames[option].image_label.setPixmap(pixmap.scaled(
                    220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation
                ))
                print(f"Successfully loaded {option}.png with lenient method")
                return True
        except Exception as e:
            print(f"Lenient loading also failed for {option}.png: {str(e)}")
        return False
        
    def select_option(self, option):
        """Handle option selection - double click"""
        try:
            # First check if ComfyUI is running
            if not check_comfyui_running():
                self.show_error_dialog(
                    "ComfyUI Not Running", 
                    "ComfyUI server is not running.",
                    "Please start ComfyUI and try again."
                )
                return
                
            # Check if workflow files exist
            missing_files = verify_comfyui_workflows()
            if missing_files:
                self.show_error_dialog(
                    "Missing Workflow Files",
                    "The following workflow files are missing:",
                    "\n".join(missing_files)
                )
                return
                
            # Save selection to output directory
            with open(os.path.join(OUTPUT_DIR, "selected_option.txt"), "w") as f:
                f.write(f"Selected Option: {option}\n")
                f.write(f"Timestamp: {time.time()}\n")
                
            # Copy text prompt - try simple naming format first, then fall back to older format
            simple_source_file = os.path.join(TEXTOPT_DIR, f"{option}.txt")
            legacy_source_file = os.path.join(TEXTOPT_DIR, f"{option}_0001.txt")
            target_file = os.path.join(TEXTOPT_DIR, "prompt.txt")
            
            # Ensure the destination directory exists
            try:
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                print(f"Ensured directory exists: {os.path.dirname(target_file)}")
            except Exception as e:
                self.status_label.setText(f"Error creating directory: {str(e)}")
                print(f"Error creating directory for prompt.txt: {str(e)}")
                return
            
            # Function to force file system to recognize new content
            def force_file_update(file_path, content):
                try:
                    # First delete the file if it exists (forces file change notification)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"Deleted existing file: {file_path}")
                    
                    # Write the content to a new file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # Get file size for confirmation
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        print(f"Created new file: {file_path} (size: {file_size} bytes)")
                        return True, file_size
                    else:
                        print(f"Failed to create file: {file_path}")
                        return False, 0
                except Exception as e:
                    print(f"Error updating file {file_path}: {str(e)}")
                    return False, 0
                
            if os.path.exists(simple_source_file):
                # Use the simple naming format file
                try:
                    # Read content from source
                    with open(simple_source_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Force update the target file
                    success, file_size = force_file_update(target_file, content)
                    
                    if success:
                        self.status_label.setText(f"Selected option {option} and applied its prompt")
                        print(f"Applied prompt from {simple_source_file} to {target_file} (size: {file_size} bytes)")
                    else:
                        self.status_label.setText(f"Error applying prompt from option {option}")
                except Exception as e:
                    self.status_label.setText(f"Error copying prompt: {str(e)}")
                    print(f"Error processing from {simple_source_file} to {target_file}: {str(e)}")
            elif os.path.exists(legacy_source_file):
                # Fall back to the legacy naming format file
                try:
                    # Read content from source
                    with open(legacy_source_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Force update the target file
                    success, file_size = force_file_update(target_file, content)
                    
                    if success:
                        self.status_label.setText(f"Selected option {option} and applied its prompt")
                        print(f"Applied prompt from {legacy_source_file} to {target_file} (size: {file_size} bytes)")
                    else:
                        self.status_label.setText(f"Error applying prompt from option {option}")
                except Exception as e:
                    self.status_label.setText(f"Error copying prompt: {str(e)}")
                    print(f"Error processing from {legacy_source_file} to {target_file}: {str(e)}")
            else:
                self.status_label.setText(f"Selected option {option} but prompt file not found")
                print(f"Prompt file not found for option {option} (checked {simple_source_file} and {legacy_source_file})")
                
            # Create a highlight effect for the selected image
            for opt, frame in self.image_frames.items():
                if opt == option:
                    frame.setStyleSheet("""
                        QFrame {
                            background-color: rgba(40, 40, 40, 200);
                            border: 2px solid rgba(100, 200, 255, 200);
                            border-radius: 10px;
                        }
                    """)
                else:
                    frame.setStyleSheet("""
                        QFrame {
                            background-color: rgba(20, 20, 20, 150);
                            border: none;
                            border-radius: 10px;
                        }
                    """)
                    
            # Run the multiview_API script to generate and import the mesh
            self.status_label.setText(f"Selected option {option}. Running multiview workflow...")
            
            # Create worker thread for multiview API
            self.multiview_worker = ScriptRunner(MULTIVIEW_API_SCRIPT)
            self.multiview_worker.progress.connect(self.update_status)
            self.multiview_worker.finished.connect(self.handle_multiview_completion)
            self.multiview_worker.start()
                    
        except Exception as e:
            self.status_label.setText(f"Error selecting option: {str(e)}")
            
    def submit_prompt(self):
        """Submit a new prompt and generate images"""
        prompt = self.prompt_input.text().strip()
        if not prompt:
            self.status_label.setText("Please enter a prompt first")
            return
            
        try:
            # Check if ComfyUI is running first
            if not check_comfyui_running():
                self.show_error_dialog(
                    "ComfyUI Not Running", 
                    "ComfyUI server is not running.",
                    "Please start ComfyUI and try again."
                )
                return
                
            # Check if workflow files exist
            missing_files = verify_comfyui_workflows()
            if missing_files:
                self.show_error_dialog(
                    "Missing Workflow Files",
                    "The following workflow files are missing:",
                    "\n".join(missing_files)
                )
                return
                
            # Write prompt to input.txt
            with open(INPUT_TEXT_FILE, "w", encoding="utf-8") as f:
                f.write(prompt)
                
            # Change the status and button
            self.status_label.setText("Triggering Blender render...")
            self.submit_btn.setEnabled(False)
            self.submit_btn.setText("Processing...")
            
            # First run the render_multiview function from main.py using a background thread
            self.trigger_blender_render()
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Generate")
            
    def trigger_blender_render(self):
        """Trigger Blender to render the 4 views needed for ComfyUI"""
        try:
            # First make sure the render directory exists
            os.makedirs(BLENDER_RENDER_DIR, exist_ok=True)
            
            # Create a Python script to run in the current Blender instance
            # Instead of trying to find and run a separate Blender instance,
            # we'll create a script that can be executed by the main.py in the currently running Blender
            
            # First, create a simple file that flags the UI is requesting a render
            render_request_path = os.path.join(BASE_DIR, "render_request.txt")
            with open(render_request_path, "w") as f:
                f.write(f"Request time: {time.time()}\n")
                f.write(f"Target dir: {BLENDER_RENDER_DIR}\n")
                
            self.status_label.setText("Waiting for Blender to render views...")
            
            # Poll for completion by checking for a "render_complete.txt" file
            # or checking if the expected images exist
            render_complete = False
            timeout = time.time() + 60  # 1 minute timeout
            
            # Create worker to check for render completion
            self.check_render_timer = QTimer(self)
            self.check_render_timer.timeout.connect(self.check_render_progress)
            self.check_render_timer.start(1000)  # Check every second
            
            # Mark the render as in progress
            self.render_in_progress = True
            self.render_start_time = time.time()
                
        except Exception as e:
            print(f"Error in trigger_blender_render: {str(e)}")
            self.status_label.setText(f"Render error: {str(e)}")
            # If rendering fails, continue with option generation anyway
            self.start_options_generation()
    
    def check_render_progress(self):
        """Check if the Blender render has completed"""
        try:
            # Check for a completion file
            render_complete_path = os.path.join(BASE_DIR, "render_complete.txt")
            
            if os.path.exists(render_complete_path):
                # Render is explicitly marked as complete
                with open(render_complete_path, "r") as f:
                    status = f.read().strip()
                
                # Delete the completion file
                os.remove(render_complete_path)
                
                # Stop the timer
                self.check_render_timer.stop()
                
                if "SUCCESS" in status:
                    self.status_label.setText("Blender render completed successfully. Generating options...")
                    self.handle_render_completion(True, "Render completed")
                else:
                    self.status_label.setText(f"Blender render issue: {status}. Generating options anyway...")
                    self.handle_render_completion(False, status)
                
                return
                
            # Check if the expected images exist and are recent
            expected_images = [
                os.path.join(BLENDER_RENDER_DIR, "0.png"),
                os.path.join(BLENDER_RENDER_DIR, "front.png"),
                os.path.join(BLENDER_RENDER_DIR, "right.png"),
                os.path.join(BLENDER_RENDER_DIR, "back.png"),
                os.path.join(BLENDER_RENDER_DIR, "left.png")
            ]
            
            # Count how many images exist and were modified after our render started
            valid_images = 0
            for img_path in expected_images:
                if os.path.exists(img_path):
                    # Check if the image was modified after our render started
                    mod_time = os.path.getmtime(img_path)
                    if mod_time > self.render_start_time:
                        valid_images += 1
                        
            # Update status
            if valid_images > 0:
                self.status_label.setText(f"Rendering: {valid_images}/5 views completed...")
                        
            # If all 5 images exist and were recently modified, consider render complete
            if valid_images >= 5:
                self.check_render_timer.stop()
                self.status_label.setText("Blender render completed. Generating options...")
                self.handle_render_completion(True, "Render completed based on image detection")
                return
                
            # Check for timeout
            if time.time() > self.render_start_time + 60:  # 1 minute timeout
                self.check_render_timer.stop()
                self.status_label.setText("Render timeout. Generating options anyway...")
                self.handle_render_completion(False, "Render timeout")
                return
                
        except Exception as e:
            print(f"Error checking render progress: {str(e)}")
            self.check_render_timer.stop()
            self.status_label.setText(f"Error checking render: {str(e)}. Generating options...")
            self.handle_render_completion(False, f"Error: {str(e)}")

    def handle_render_completion(self, success, message):
        """Handle the completion of the Blender render"""
        # Clean up any temporary files
        try:
            render_request_path = os.path.join(BASE_DIR, "render_request.txt")
            if os.path.exists(render_request_path):
                os.remove(render_request_path)
        except Exception as e:
            print(f"Error removing temporary files: {str(e)}")
            
        # Start the options generation process
        self.start_options_generation()
        
    def start_options_generation(self):
        """Start the options generation process after rendering"""
        try:
            # Create worker thread for options API
            self.worker = ScriptRunner(OPTIONS_API_SCRIPT)
            self.worker.progress.connect(self.update_status)
            self.worker.finished.connect(self.handle_completion)
            self.worker.start()
        except Exception as e:
            self.status_label.setText(f"Error starting options generation: {str(e)}")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Generate")
        
    def update_status(self, message):
        """Update status with script progress"""
        self.status_label.setText(message)
        
    def handle_completion(self, success, message):
        """Handle script completion"""
        if success:
            self.status_label.setText("Generation complete! Loading new images...")
            # Force file system refresh and wait a moment to ensure files are fully written
            time.sleep(1)
            
            # Initial image load
            self.load_images()
            
            # Set up a retry timer to attempt loading images again after a delay
            # This helps with race conditions where files might not be fully written yet
            self.retry_timer = QTimer(self)
            self.retry_timer.setSingleShot(True)
            self.retry_timer.timeout.connect(self.retry_load_images)
            self.retry_timer.start(2000)  # Try again after 2 seconds
        else:
            self.status_label.setText(f"Error: {message}")
            
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Generate")
        
    def retry_load_images(self):
        """Retry loading images after a delay"""
        print("Retrying image load after delay...")
        self.status_label.setText("Retrying image load...")
        self.load_images()
        
        # Set up one more retry if needed
        if hasattr(self, 'retry_count'):
            self.retry_count += 1
        else:
            self.retry_count = 1
            
        # Try up to 3 times
        if self.retry_count < 3:
            self.retry_timer.start(2000)  # Try again after 2 more seconds
        else:
            self.retry_count = 0
        
    def handle_multiview_completion(self, success, message):
        """Handle multiview script completion"""
        if success:
            self.status_label.setText("3D model generated successfully. Triggering import...")
            
            # Now that the model has been generated, trigger the Blender import
            self.trigger_blender_import()
        else:
            error_msg = message.strip()
            self.status_label.setText(f"Error generating 3D model: {error_msg}")
            
            # Show a more detailed error dialog
            self.show_error_dialog(
                "3D Model Generation Failed", 
                "Failed to generate the 3D model.",
                f"Error details: {error_msg}\n\n" +
                "Possible causes:\n" +
                "- ComfyUI is not running\n" +
                "- The workflow file is missing or corrupted\n" +
                "- The 3D generation nodes are not configured correctly\n" +
                "- ComfyUI encountered an error during processing"
            )
    
    def trigger_blender_import(self):
        """Trigger Blender to import the generated mesh"""
        try:
            # Create a file that signals Blender to import the model
            import_request_path = os.path.join(BASE_DIR, "import_request.txt")
            with open(import_request_path, "w") as f:
                f.write(f"Request time: {time.time()}\n")
                f.write(f"Model path: {os.path.join(BASE_DIR, 'output', 'generated', 'Models', 'current_mesh.glb')}\n")
                
            self.status_label.setText("Waiting for Blender to import the model...")
            
            # Create a timer to check for import completion
            self.check_import_timer = QTimer(self)
            self.check_import_timer.timeout.connect(self.check_import_progress)
            self.check_import_timer.start(1000)  # Check every second
            
            # Mark the import as in progress
            self.import_in_progress = True
            self.import_start_time = time.time()
                
        except Exception as e:
            print(f"Error triggering Blender import: {str(e)}")
            self.status_label.setText(f"Error triggering import: {str(e)}")
    
    def check_import_progress(self):
        """Check if the Blender import has completed"""
        try:
            # Check for a completion file
            import_complete_path = os.path.join(BASE_DIR, "import_complete.txt")
            
            if os.path.exists(import_complete_path):
                # Import is explicitly marked as complete
                with open(import_complete_path, "r") as f:
                    status = f.read().strip()
                
                # Delete the completion file
                os.remove(import_complete_path)
                
                # Stop the timer
                self.check_import_timer.stop()
                
                if "SUCCESS" in status:
                    self.status_label.setText("3D model imported successfully!")
                else:
                    self.status_label.setText(f"Import issue: {status}")
                
                return
                
            # Check for timeout
            if time.time() > self.import_start_time + 60:  # 1 minute timeout
                self.check_import_timer.stop()
                self.status_label.setText("Import timeout. Please check Blender console.")
                return
                
        except Exception as e:
            print(f"Error checking import progress: {str(e)}")
            self.check_import_timer.stop()
            self.status_label.setText(f"Error checking import: {str(e)}")

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
        """Reposition buttons when window is resized"""
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
        """Handle key press events"""
        # Exit fullscreen with Escape key
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def terminate_script(self):
        """Terminate both UI and main processes"""
        try:
            # Show confirmation dialog
            reply = self.show_confirmation_dialog(
                "Terminate Script", 
                "Are you sure you want to terminate all processes?",
                "This will close both the UI and any running background processes."
            )
            
            if reply:
                self.status_label.setText("Terminating all processes...")
                
                # Try to kill any running worker processes
                try:
                    if hasattr(self, 'worker') and self.worker.isRunning():
                        self.worker.terminate()
                        self.worker.wait()
                        
                    if hasattr(self, 'multiview_worker') and self.multiview_worker.isRunning():
                        self.multiview_worker.terminate()
                        self.multiview_worker.wait()
                except Exception as e:
                    print(f"Error terminating worker threads: {str(e)}")
                
                # Exit the application with code 0
                QApplication.quit()
                
                # For cases where QApplication.quit() doesn't work
                import os
                os._exit(0)
        except Exception as e:
            self.status_label.setText(f"Error terminating: {str(e)}")
    
    def show_confirmation_dialog(self, title, message, detail=""):
        """Show a confirmation dialog and return True if confirmed"""
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        if detail:
            msg_box.setInformativeText(detail)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        
        # Style the message box
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

    def show_error_dialog(self, title, message, detail=""):
        """Show an error dialog with details"""
        from PyQt5.QtWidgets import QMessageBox
        
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(message)
        if detail:
            msg_box.setInformativeText(detail)
        
        # Style the message box
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
        
        msg_box.exec_()

    def toggle_remesh(self):
        """Toggle the remesh button"""
        # Get the current state
        is_enabled = self.remesh_btn.isChecked()
        
        # Toggle visual state of the button
        if is_enabled:
            # Button is now checked (enabled)
            self.remesh_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(100, 40, 40, 180);
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(120, 50, 50, 200);
                }
                QPushButton:pressed {
                    background-color: rgba(140, 60, 60, 220);
                }
            """)
            
            # Add a drop shadow effect for the enabled state
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(255, 0, 0, 150))
            shadow.setOffset(2, 2)
            self.remesh_btn.setGraphicsEffect(shadow)
        else:
            # Button is now unchecked (disabled)
            self.remesh_btn.setStyleSheet("""
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
            
            # Reset the shadow effect
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 150))
            shadow.setOffset(2, 2)
            self.remesh_btn.setGraphicsEffect(shadow)
        
        # Get the current stage from the button text
        current_text = self.remesh_btn.text()
        current_stage = 1
        
        if "(" in current_text and ")" in current_text:
            stage_text = current_text.split("(")[1].split(")")[0]
            try:
                current_stage = int(stage_text)
            except ValueError:
                current_stage = 1
        
        # Create a remesh_state.txt file to communicate with Blender
        remesh_state_path = os.path.join(BASE_DIR, "remesh_state.txt")
        
        try:
            with open(remesh_state_path, "w") as f:
                f.write(f"enabled={is_enabled}\n")
                f.write(f"stage={current_stage}\n")
                f.write(f"type=SHARP\n")  # Default type, can be changed in Blender UI
                f.write(f"timestamp={time.time()}\n")
            
            self.status_label.setText(f"Remesh {'enabled' if is_enabled else 'disabled'} - Will apply stage {current_stage} on next import")
            print(f"Saved remesh state: enabled={is_enabled}, stage={current_stage}")
            
        except Exception as e:
            self.status_label.setText(f"Error setting remesh state: {str(e)}")
            print(f"Error saving remesh state: {str(e)}")
        
        # If a new mesh is imported when remesh is enabled, the stage will advance
        # We'll update our button text when we detect a stage change in Blender via
        # checking the remesh_state.txt file periodically in self.load_images()

    def check_remesh_state(self):
        """Check and update remesh state from Blender"""
        remesh_state_path = os.path.join(BASE_DIR, "remesh_state.txt")
        
        try:
            if not os.path.exists(remesh_state_path):
                # Create default state file if it doesn't exist
                with open(remesh_state_path, "w") as f:
                    f.write("enabled=False\n")
                    f.write("stage=1\n")
                    f.write("type=SHARP\n")
                    f.write(f"timestamp={time.time()}\n")
                return
            
            # Read the state file
            stage = 1
            enabled = False
            
            with open(remesh_state_path, "r") as f:
                for line in f:
                    if line.startswith("stage="):
                        try:
                            stage = int(line.strip().split("=")[1])
                        except:
                            stage = 1
                    elif line.startswith("enabled="):
                        enabled_text = line.strip().split("=")[1].lower()
                        enabled = enabled_text == "true"
            
            # Update the button text and state
            if hasattr(self, 'remesh_btn'):
                self.remesh_btn.setText(f"Remesh ({stage})")
                self.remesh_btn.setChecked(enabled)
                
                # Update the button style based on the enabled state
                if enabled:
                    self.remesh_btn.setStyleSheet("""
                        QPushButton {
                            background-color: rgba(100, 40, 40, 180);
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 8px 16px;
                            font-size: 14px;
                        }
                        QPushButton:hover {
                            background-color: rgba(120, 50, 50, 200);
                        }
                        QPushButton:pressed {
                            background-color: rgba(140, 60, 60, 220);
                        }
                    """)
                else:
                    self.remesh_btn.setStyleSheet("""
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
                
        except Exception as e:
            print(f"Error checking remesh state: {str(e)}")

def find_blender_executable():
    """Find the Blender executable path"""
    # First try the PATH environment variable
    try:
        # Check if blender is in the PATH
        process = subprocess.run(["blender", "--version"], 
                                capture_output=True, text=True, check=False)
        if process.returncode == 0:
            return "blender"  # Blender is in PATH
    except:
        pass
    
    # Then try common installation directories
    for path in BLENDER_INSTALL_PATHS:
        if os.path.exists(path):
            return path
    
    # Finally try to find Blender in Program Files
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    for root, dirs, files in os.walk(program_files):
        if "blender.exe" in files:
            return os.path.join(root, "blender.exe")
            
    # Not found
    return None

def check_comfyui_running():
    """Check if ComfyUI server is running"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        # ComfyUI default port is 8188
        result = sock.connect_ex(('127.0.0.1', 8188))
        sock.close()
        return result == 0  # Return True if port is open
    except Exception as e:
        print(f"Error checking ComfyUI: {str(e)}")
        return False

def verify_comfyui_workflows():
    """Verify that the ComfyUI workflow files exist"""
    workflow_files = {
        "Options": os.path.join(BASE_DIR, "src", "comfyworkflows", "VIBEOptions.json"),
        "MultiView": os.path.join(BASE_DIR, "src", "comfyworkflows", "VIBEMultiView.json")
    }
    
    missing = []
    for name, path in workflow_files.items():
        if not os.path.exists(path):
            missing.append(f"{name} workflow ({path})")
    
    return missing

# Run the application
if __name__ == "__main__":
    # Set application attributes
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    
    # Use a system font instead of requiring Roboto
    font = QFont("Segoe UI" if sys.platform == "win32" else "Helvetica")
    font.setPointSize(10)
    app.setFont(font)
    
    window = TransparentWindow()
    window.show()
    
    sys.exit(app.exec_()) 