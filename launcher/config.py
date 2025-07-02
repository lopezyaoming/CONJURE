"""
Global configuration constants and paths.
"""

import os
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BLENDER_DIR = PROJECT_ROOT / "blender"
COMFYUI_DIR = PROJECT_ROOT / "comfyui"
CGAL_DIR = PROJECT_ROOT / "cgal"

# Data paths
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
ASSETS_DIR = DATA_DIR / "assets"

# File paths
STATE_JSON = INPUT_DIR / "state.json"
FINGERTIPS_JSON = INPUT_DIR / "fingertips.json"
SCENE_BLEND = BLENDER_DIR / "scene.blend" 