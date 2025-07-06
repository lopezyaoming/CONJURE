"""
Central configuration file for the CONJURE Blender addon.
Contains all constants, file paths, and tuning parameters.
"""

from pathlib import Path
import bpy

# --- CORE FILE PATHS ---
# This is the corrected path calculation. It traverses up four levels
# from this config file to find the main 'CONJURE' project root.
# (config.py -> conjure -> addons -> scripts -> CONJURE)
try:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
except NameError:
    # Fallback for running directly in Blender's text editor, though this is not the intended workflow.
    PROJECT_ROOT = Path(bpy.data.filepath).parent.parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
FINGERTIPS_JSON_PATH = DATA_DIR / "input" / "fingertips.json"
DEFORM_OBJ_NAME = "Mesh"  # The name of the mesh we will manipulate
GESTURE_CAMERA_NAME = "GestureCamera" # The camera used for perspective-based mapping


# --- INTERACTION ---
HIDE_GRACE_PERIOD_FRAMES = 5    # How many frames to wait before hiding a missing finger marker.
REFRESH_RATE_SECONDS = 1 / 30  # Target 30 updates per second.
MAX_HISTORY_STEPS = 150        # The number of undo steps to store in memory.
BRUSH_TYPES = ['PINCH', 'GRAB', 'SMOOTH', 'INFLATE', 'FLATTEN'] # The available deformation brushes


# --- MAPPING & VISUALS ---
HAND_SCALE_X = 10.0
HAND_SCALE_Y = 10.0
HAND_SCALE_Z = 10.0
MARKER_OUT_OF_VIEW_LOCATION = (1000, 1000, 1000)
MARKER_SURFACE_OFFSET = 0.05
SMOOTHING_FACTOR = 0.3


# --- CAMERA ORBIT ---
ORBIT_SENSITIVITY = 400.0
ORBIT_SMOOTHING_FACTOR = 0.25


# --- BRUSH SETTINGS ---
RADIUS_LEVELS = [
    {'name': 'small',  'finger': 3.0, 'grab': 1.5, 'flatten': 0.375, 'inflate': 0.75},
    {'name': 'medium', 'finger': 3.0, 'grab': 1.5, 'flatten': 0.75,  'inflate': 1.5},
    {'name': 'large',  'finger': 3.0, 'grab': 3.0, 'flatten': 3.0,   'inflate': 6.0}
]
MAX_DISPLACEMENT_PER_FRAME = 0.25
DEFORM_TIMESTEP = 0.05
FINGER_FORCE_STRENGTH = 0.09
GRAB_FORCE_STRENGTH = 10
SMOOTH_FORCE_STRENGTH = 1.75
INFLATE_FORCE_STRENGTH = 0.15
FLATTEN_FORCE_STRENGTH = 1.5


# --- PHYSICS & VOLUME ---
USE_VELOCITY_FORCES = True
VELOCITY_DAMPING_FACTOR = 0.80
MASS_COHESION_FACTOR = 0.62
VOLUME_LOWER_LIMIT = 0.8
VOLUME_UPPER_LIMIT = 1.2 