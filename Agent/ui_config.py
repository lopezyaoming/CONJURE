"""
UI Configuration for CONJURE
Central configuration file for UI styling, paths, and constants
"""

from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RUNCOMFY_DIR = PROJECT_ROOT / "runcomfy"

# Data source paths
STATE_JSON = DATA_DIR / "input" / "state.json"
FINGERTIPS_JSON = DATA_DIR / "input" / "fingertips.json"
TRANSCRIPT_DEBUG = PROJECT_ROOT / "transcript_debug.txt"
ELEVENLABS_LOG = PROJECT_ROOT / "elevenlabs_transcript_log.txt"
RUNCOMFY_STATE = RUNCOMFY_DIR / "dev_server_state.json"
UI_OUTPUT = AGENT_DIR / "ui_data.json"

# UI Configuration
class UIConfig:
    # Window settings
    WINDOW_FLAGS = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    WINDOW_ATTRIBUTES = [Qt.WA_TranslucentBackground]
    
    # Refresh intervals (in milliseconds)
    DATA_REFRESH_INTERVAL = 5000  # 5 seconds
    WORKFLOW_CHECK_INTERVAL = 1000  # 1 second
    DOTS_ANIMATION_INTERVAL = 500   # 0.5 seconds
    
    # Panel sizes
    CONVERSATION_PANEL_SIZE = (400, 300)
    STATUS_PANEL_SIZE = (300, 150)
    BRUSH_PANEL_SIZE = (250, 120)
    PROGRESS_BAR_SIZE = (600, 40)
    
    # UI positioning
    WINDOW_WIDTH = 500
    MARGIN = 40
    PANEL_SPACING = 20
    
    # Animation settings
    ANIMATION_DURATION = 500  # milliseconds
    PULSE_DURATION = 1500
    FADE_DURATION = 250
    
    # Data limits
    MAX_CONVERSATION_MESSAGES = 50
    DISPLAY_RECENT_MESSAGES = 20
    
    # Font settings
    DEFAULT_FONT_FAMILY = "Segoe UI"  # Windows
    FALLBACK_FONT_FAMILY = "Helvetica"  # Other systems
    MONOSPACE_FONT_FAMILY = "'Consolas', 'Monaco', monospace"
    
    DEFAULT_FONT_SIZE = 10
    TITLE_FONT_SIZE = 16
    SUBTITLE_FONT_SIZE = 12
    STATUS_FONT_SIZE = 14
    OVERLAY_TITLE_FONT_SIZE = 48
    OVERLAY_STAGE_FONT_SIZE = 18
    OVERLAY_NODE_FONT_SIZE = 14
    OVERLAY_TIME_FONT_SIZE = 12

# Color schemes
class Colors:
    # Background colors (RGBA)
    PANEL_BACKGROUND = "rgba(30, 30, 30, 140)"
    FRAME_BACKGROUND = "rgba(20, 20, 20, 150)"
    BUTTON_BACKGROUND = "rgba(40, 40, 40, 180)"
    BUTTON_HOVER = "rgba(60, 60, 60, 200)"
    BUTTON_PRESSED = "rgba(80, 80, 80, 220)"
    
    # Text colors
    TEXT_PRIMARY = "rgba(220, 220, 220, 180)"
    TEXT_SECONDARY = "rgba(200, 200, 200, 180)"
    TEXT_SUBTITLE = "rgba(150, 150, 150, 180)"
    TEXT_DISABLED = "rgba(120, 120, 120, 150)"
    
    # Status colors
    STATUS_RUNNING = "rgba(100, 255, 100, 200)"
    STATUS_ERROR = "rgba(255, 100, 100, 200)"
    STATUS_WARNING = "rgba(255, 255, 100, 200)"
    STATUS_IDLE = "rgba(180, 180, 180, 200)"
    
    # Conversation colors
    USER_MESSAGE = "#80c0ff"      # Light blue
    AGENT_MESSAGE = "#80ff80"     # Light green
    TIMESTAMP_COLOR = "#888"      # Gray
    
    # Progress colors
    PROGRESS_BACKGROUND = "rgba(30, 30, 30, 150)"
    PROGRESS_BORDER = "rgba(80, 80, 80, 200)"
    PROGRESS_CHUNK_START = "rgba(100, 200, 255, 200)"
    PROGRESS_CHUNK_MID = "rgba(120, 220, 255, 230)"
    PROGRESS_CHUNK_END = "rgba(100, 200, 255, 200)"
    
    # Overlay colors
    OVERLAY_BACKGROUND = "rgba(0, 0, 0, 120)"
    OVERLAY_BACKDROP = "rgba(0, 0, 0, 100)"
    OVERLAY_TEXT = "white"
    
    # Shadow colors
    SHADOW_COLOR = QColor(0, 0, 0, 150)
    SHADOW_HEAVY = QColor(0, 0, 0, 180)

# Style templates
class Styles:
    # Base panel style
    PANEL_BASE = f"""
        QFrame {{
            background-color: {Colors.PANEL_BACKGROUND};
            border: none;
            border-radius: 8px;
        }}
    """
    
    # Button styles
    BUTTON_BASE = f"""
        QPushButton {{
            background-color: {Colors.BUTTON_BACKGROUND};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: {UIConfig.DEFAULT_FONT_SIZE}px;
        }}
        QPushButton:hover {{
            background-color: {Colors.BUTTON_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Colors.BUTTON_PRESSED};
        }}
    """
    
    # Close button
    CLOSE_BUTTON = f"""
        QPushButton {{
            background-color: {Colors.BUTTON_BACKGROUND};
            color: white;
            border: none;
            border-radius: 15px;
            font-size: 20px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: rgba(255, 0, 0, 180);
        }}
    """
    
    # Text edit for conversation
    TEXT_EDIT = f"""
        QTextEdit {{
            background-color: {Colors.FRAME_BACKGROUND};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px;
            font-size: 11px;
            font-family: {UIConfig.MONOSPACE_FONT_FAMILY};
        }}
        QScrollBar:vertical {{
            background-color: rgba(40, 40, 40, 100);
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background-color: rgba(80, 80, 80, 150);
            border-radius: 4px;
        }}
    """
    
    # Label styles
    LABEL_TITLE = f"""
        QLabel {{
            color: rgba(255, 255, 255, 220);
            font-size: {UIConfig.TITLE_FONT_SIZE}px;
            font-weight: bold;
            padding: 5px;
        }}
    """
    
    LABEL_SUBTITLE = f"""
        QLabel {{
            color: {Colors.TEXT_SECONDARY};
            font-size: {UIConfig.SUBTITLE_FONT_SIZE}px;
            font-weight: bold;
            padding: 2px;
        }}
    """
    
    LABEL_NORMAL = f"""
        QLabel {{
            color: {Colors.TEXT_PRIMARY};
            font-size: {UIConfig.DEFAULT_FONT_SIZE}px;
            padding: 2px;
        }}
    """
    
    LABEL_STATUS = f"""
        QLabel {{
            color: {Colors.STATUS_RUNNING};
            font-size: {UIConfig.STATUS_FONT_SIZE}px;
            font-weight: bold;
            padding: 3px;
        }}
    """
    
    # Progress bar style
    PROGRESS_BAR = f"""
        QProgressBar {{
            background-color: {Colors.PROGRESS_BACKGROUND};
            border: 2px solid {Colors.PROGRESS_BORDER};
            border-radius: 10px;
            text-align: center;
            color: white;
            font-size: {UIConfig.STATUS_FONT_SIZE}px;
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {Colors.PROGRESS_CHUNK_START},
                stop:0.5 {Colors.PROGRESS_CHUNK_MID},
                stop:1 {Colors.PROGRESS_CHUNK_END}
            );
            border-radius: 8px;
            margin: 2px;
        }}
    """
    
    # Overlay styles
    OVERLAY_TITLE = f"""
        QLabel {{
            color: {Colors.OVERLAY_TEXT};
            font-size: {UIConfig.OVERLAY_TITLE_FONT_SIZE}px;
            font-weight: bold;
            font-family: 'Arial', sans-serif;
            text-align: center;
        }}
    """
    
    OVERLAY_STAGE = f"""
        QLabel {{
            color: rgba(200, 200, 200, 220);
            font-size: {UIConfig.OVERLAY_STAGE_FONT_SIZE}px;
            font-weight: normal;
            text-align: center;
        }}
    """
    
    OVERLAY_NODE = f"""
        QLabel {{
            color: rgba(150, 150, 150, 180);
            font-size: {UIConfig.OVERLAY_NODE_FONT_SIZE}px;
            text-align: center;
        }}
    """
    
    OVERLAY_TIME = f"""
        QLabel {{
            color: rgba(180, 180, 180, 160);
            font-size: {UIConfig.OVERLAY_TIME_FONT_SIZE}px;
            text-align: center;
        }}
    """

# Phase mappings
class PhaseInfo:
    PHASE_NAMES = {
        "I": "Phase I - Primitive Creation",
        "II": "Phase II - Mesh Generation", 
        "III": "Phase III - Refinement",
        "IV": "Phase IV - Finalization"
    }
    
    PHASE_COLORS = {
        "I": Colors.STATUS_IDLE,
        "II": Colors.STATUS_RUNNING,
        "III": Colors.STATUS_WARNING,
        "IV": Colors.STATUS_RUNNING
    }

# Command mappings
class CommandInfo:
    COMMAND_DISPLAY_NAMES = {
        "idle": "System Idle",
        "spawn_primitive": "Creating Primitive",
        "generate_flux_mesh": "Generating Mesh",
        "fuse_mesh": "Fusing Mesh Segments",
        "segment_selection": "Segment Selection Mode",
        "select_concept": "Concept Selection",
        "deform": "Mesh Deformation",
        "scale": "Mesh Scaling",
        "rotate": "Mesh Rotation"
    }
    
    COMMAND_COLORS = {
        "idle": Colors.STATUS_IDLE,
        "spawn_primitive": Colors.STATUS_RUNNING,
        "generate_flux_mesh": Colors.STATUS_RUNNING,
        "fuse_mesh": Colors.STATUS_RUNNING,
        "segment_selection": Colors.STATUS_WARNING,
        "select_concept": Colors.STATUS_WARNING,
        "deform": Colors.STATUS_RUNNING,
        "scale": Colors.STATUS_RUNNING,
        "rotate": Colors.STATUS_RUNNING
    }

# Workflow stage mappings
class WorkflowStages:
    STAGE_DISPLAY_NAMES = {
        "Initializing": "Initializing Workflow",
        "FLUX Generation": "Generating with FLUX",
        "Depth Processing": "Processing Depth Map",
        "Mesh Creation": "Creating 3D Mesh",
        "Cleanup": "Finalizing Result",
        "Complete": "Generation Complete"
    }
    
    # Default stages for progress estimation
    DEFAULT_STAGES = [
        {"name": "Initializing", "weight": 0.1},
        {"name": "FLUX Generation", "weight": 0.4},
        {"name": "Depth Processing", "weight": 0.2},
        {"name": "Mesh Creation", "weight": 0.2},
        {"name": "Cleanup", "weight": 0.1}
    ]

# File monitoring
class FileMonitoring:
    # Files to monitor for changes
    MONITORED_FILES = [
        STATE_JSON,
        FINGERTIPS_JSON,
        TRANSCRIPT_DEBUG,
        ELEVENLABS_LOG,
        RUNCOMFY_STATE
    ]
    
    # Debounce time for file changes (seconds)
    FILE_CHANGE_DEBOUNCE = 0.5
    
    # Maximum file sizes to read (in bytes)
    MAX_LOG_FILE_SIZE = 1024 * 1024  # 1MB
    MAX_JSON_FILE_SIZE = 1024 * 100   # 100KB
