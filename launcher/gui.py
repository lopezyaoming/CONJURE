import sys
import os
import json
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap, QFont, QFontDatabase

# --- Configuration ---
# Use relative paths to ensure the application is portable
# Assumes the script is run from the CONJURE workspace root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE_PATH = os.path.join(ROOT_DIR, "data", "input", "state.json")
OPTIONS_DIR = os.path.join(ROOT_DIR, "data", "generated_images", "imageOPTIONS")
FONT_NAME = "Helvetica Neue"

# --- Main UI Components ---

class ImageFrame(QWidget):
    """A widget to display a single concept image with a border."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(341, 341) # Aspect ratio 1:1, allows for padding

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10) # Padding for the glow effect
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True)
        layout.addWidget(self.image_label)
        
        self.setStyleSheet("""
            ImageFrame {
                background-color: rgba(30, 30, 30, 0.2);
                border-radius: 15px;
                border: 2px solid transparent;
            }
        """)

    def load_image(self, image_path):
        """Loads an image if it's valid, otherwise clears the label."""
        if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap)
                return
        self.image_label.clear()

    def set_highlight(self, highlighted: bool):
        """Sets the visual highlight state of the frame."""
        if highlighted:
            self.setStyleSheet("""
                ImageFrame {
                    background-color: rgba(40, 40, 40, 0.3);
                    border-radius: 15px;
                    border: 2px solid rgba(255, 255, 255, 0.8);
                }
            """)
        else:
            self.setStyleSheet("""
                ImageFrame {
                    background-color: rgba(30, 30, 30, 0.2);
                    border-radius: 15px;
                    border: 2px solid transparent;
                }
            """)

class OptionSelector(QWidget):
    """A transient container for the three concept image frames."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False) # Hidden by default
        
        layout = QHBoxLayout(self)
        layout.setSpacing(40)
        self.setLayout(layout)

        self.option_frames = {
            1: ImageFrame(self),
            2: ImageFrame(self),
            3: ImageFrame(self)
        }
        
        layout.addWidget(self.option_frames[1])
        layout.addWidget(self.option_frames[2])
        layout.addWidget(self.option_frames[3])
    
    def update_options(self, ui_state: dict):
        """Updates visibility, images, and highlights based on state.json."""
        is_visible = ui_state.get("view") == "SHOWING_OPTIONS"
        self.setVisible(is_visible)

        if is_visible:
            selected_option = ui_state.get("selected_option")
            for i in range(1, 4):
                image_path = os.path.join(OPTIONS_DIR, f"OP{i}.png")
                self.option_frames[i].load_image(image_path)
                self.option_frames[i].set_highlight(i == selected_option)

class DialogBar(QWidget):
    """A floating, glassmorphic container for agent dialogue."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Not a bar anymore, so no fixed height. Give it a max width.
        self.setMaximumWidth(800)
        self.setObjectName("DialogBar")

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 20, 25, 15)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)

        # --- Dialogue Area ---
        self.user_transcript_label = QLabel("")
        self.user_transcript_label.setObjectName("UserTranscript")
        self.user_transcript_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_transcript_label.setWordWrap(True)

        self.agent_response_label = QLabel("Initializing...")
        self.agent_response_label.setObjectName("AgentResponse")
        self.agent_response_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.agent_response_label.setWordWrap(True)

        main_layout.addWidget(self.user_transcript_label)
        main_layout.addWidget(self.agent_response_label)
        main_layout.addStretch(1) # Pushes footer to the bottom of the box

        # --- Footer Area ---
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("...")
        self.status_label.setObjectName("StatusLabel")

        calliope_label = QLabel("CALLIOPE")
        calliope_label.setObjectName("CalliopeLabel")

        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(calliope_label)

        main_layout.addLayout(footer_layout)


    def update_dialogue(self, dialogue_state: dict):
        """Updates the text based on the dialogue state."""
        self.user_transcript_label.setText(dialogue_state.get("user_transcript", ""))
        self.agent_response_label.setText(dialogue_state.get("agent_response", "..."))
        self.status_label.setText(dialogue_state.get("status", "..."))


class TransparentWindow(QMainWindow):
    """The main application window."""
    def __init__(self):
        super().__init__()
        self.last_state = {}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.init_ui()
        self.init_state_polling()
        self.showFullScreen()
        
    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Layout construction ---
        main_layout.addStretch(1) # Pushes the option selector down a bit
        
        self.option_selector = OptionSelector(self)
        selector_layout = QHBoxLayout()
        selector_layout.addStretch(1)
        selector_layout.addWidget(self.option_selector)
        selector_layout.addStretch(1)
        main_layout.addLayout(selector_layout)

        main_layout.addStretch(2) # Pushes the dialog bar down
        
        self.dialog_bar = DialogBar(self)
        # Wrap dialog bar in a centering layout
        dialog_layout = QHBoxLayout()
        dialog_layout.addStretch(1)
        dialog_layout.addWidget(self.dialog_bar)
        dialog_layout.addStretch(1)
        main_layout.addLayout(dialog_layout)

        main_layout.addStretch(1) # Space below the dialog bar (ratio 2:1 pushes it 1/3 from bottom)
        
    def init_state_polling(self):
        self.state_poll_timer = QTimer(self)
        self.state_poll_timer.timeout.connect(self.poll_state_file)
        self.state_poll_timer.start(250) # Poll 4 times per second

    def poll_state_file(self):
        try:
            if not os.path.exists(STATE_FILE_PATH):
                self.dialog_bar.agent_response_label.setText("Waiting for state.json...")
                return

            with open(STATE_FILE_PATH, 'r') as f:
                current_state = json.load(f)

            if current_state != self.last_state:
                self.last_state = current_state
                ui_state = current_state.get("ui", {})
                
                # Update components based on the new state
                self.option_selector.update_options(ui_state)
                self.dialog_bar.update_dialogue(ui_state.get("dialogue", {}))

        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading state file: {e}")
            self.dialog_bar.agent_response_label.setText("Error reading state.json")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def keyPressEvent(self, event):
        """Handle key press events to close the application."""
        if event.key() == Qt.Key.Key_Escape:
            print("Escape key pressed. Closing application.")
            self.close()

# --- Application Entry Point ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set default font
    font = QFont(FONT_NAME)
    font.setWeight(QFont.Weight.Bold) # Set default weight to Bold
    app.setFont(font)
    
    # --- High-Contrast Opaque Stylesheet ---
    app.setStyleSheet(f"""
        QMainWindow {{
            background-color: transparent;
        }}
        #UserTranscript {{
            font-size: 20px;
            color: white;
            font-weight: 700;
        }}
        #AgentResponse {{
            font-size: 24px;
            color: white;
            font-weight: 700;
        }}
        #StatusLabel {{
            font-size: 14px;
            color: white;
            font-weight: 700;
        }}
        #CalliopeLabel {{
            font-size: 14px;
            color: white;
            font-weight: 700;
            border: 1px solid white;
            border-radius: 4px;
            padding: 2px 8px;
        }}
        #DialogBar {{
             background-color: #1b1b1b;
             border: none;
             border-radius: 18px;
        }}
    """)
    
    window = TransparentWindow()
    window.show()
    sys.exit(app.exec()) 