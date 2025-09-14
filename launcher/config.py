"""
Global configuration constants and paths.
"""

import os
from pathlib import Path

# Generation Mode Configuration
GENERATION_MODE = "local"  # Can be "local" (huggingface), "local_comfyui", "serverless", "cloud", or "cloud_legacy"

# RunComfy Serverless Configuration
RUNCOMFY_API_TOKEN = os.getenv("RUNCOMFY_API_TOKEN", "78356331-a9ec-49c2-a412-59140b32b9b3")
RUNCOMFY_USER_ID = os.getenv("RUNCOMFY_USER_ID", "0cb54d51-f01e-48e1-ae7b-28d1c21bc947")
RUNCOMFY_DEPLOYMENT_ID = os.getenv("RUNCOMFY_DEPLOYMENT_ID", "dfcf38cd-0a09-4637-a067-5059dc9e444e")
RUNCOMFY_DEFAULT_STEPS_FLUX = int(os.getenv("RUNCOMFY_DEFAULT_STEPS_FLUX", "20"))  # From workflow JSON
RUNCOMFY_DEFAULT_STEPS_PARTPACKER = int(os.getenv("RUNCOMFY_DEFAULT_STEPS_PARTPACKER", "50"))  # From workflow JSON
RUNCOMFY_COST_TRACKING = os.getenv("RUNCOMFY_COST_TRACKING", "true").lower() == "true"

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

# --- PATHS ---
# The absolute path to the Blender executable.
# This must be set correctly for your system.
BLENDER_EXECUTABLE_PATH = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"

# NOTE: This path is an educated guess based on error logs.
# If your ComfyUI installation is elsewhere, please update this path.
COMFYUI_ROOT_PATH = Path("C:/ComfyUI/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI")
COMFYUI_OUTPUT_PATH = COMFYUI_ROOT_PATH / "output"
COMFYUI_CONJURE_OUTPUT_PATH = COMFYUI_OUTPUT_PATH / "CONJURE" 