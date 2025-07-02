import cv2
import time
import threading
import numpy as np
import json
import os
import math
import logging
# import sounddevice as sd
# import whisper
import mediapipe as mp
from pathlib import Path
import sys
import subprocess
import socket
import urllib.request
import urllib.error
import shutil

# ----------------------------- #
#       CONFIGURATION           #
# ----------------------------- #

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')

OUTPUT_JSON = "C:/CODING/VIBE/VIBE_Massing/output/live_hand_data.json"
VOICE_TXT = "C:/CODING/VIBE/VIBE_Massing/output/voice_transcription3.txt"

GESTURE_HOLD_TIME = 1.0
ANCHOR_HOLD_TIME = 1.0
CLEAR_HOLD_TIME = 1.0
TOGGLE_COOLDOWN = 2.0  # Increased from 1.0 to 2.0 seconds for remesh cycling
right_fist_start_time = None  # Track right fist hold time for render
deform_mode_active = False  # Track if deform mode is currently active

# === Updated color palette for a more minimal VIBE aesthetic ===
# Blacks: #161613 → (22, 22, 19)
# Whites: #EBEBEB → (235, 235, 235)
FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_COLOR = (235, 235, 235)  # #EBEBEB
TEXT_SCALE = 0.7
TEXT_THICKNESS = 2

UI_BACKGROUND = (22, 22, 19)  # #161613
UI_ACCENT = (235, 235, 235)  # monochrome look
UI_HIGHLIGHT = (180, 180, 180)
UI_SECONDARY = (120, 120, 120)
UI_BORDER = (80, 80, 80)
UI_SHADOW = (0, 0, 0)

LEFT_HAND_COLOR = (235, 255, 5)  # bright white
RIGHT_HAND_COLOR = (235, 255, 5)  # a bit darker
ANCHOR_COLOR = (235, 235, 235)

REMESH_TYPES = ["Blocks", "Smooth", "Sharp", "Voxel", "NONE"]

# New global to hold the latest voice transcription
# latest_transcription = ""

gesture_tool_map = {
    "pinch_expand": "sculpt.dynamic_topology_toggle",
    "three_finger_swipe": "mesh.looptools_bridge",
    "clockwise_rotation": "object.shade_smooth",
    # More mappings based on user preferences
}

TEXT_SELECTOR_DIRECTORY = r"C:\CODING\VIBE\VIBE_Massing\input\COMFYINPUTS\textOptions"
text_selector_mode = False


# ----------------------------- #
#       FUNCTION DEFINITIONS    #
# ----------------------------- #

def draw_hold_progress(frame: np.ndarray, x: int, y: int, start_time: float, hold_time: float,
                       label: str = "Hold", color: tuple = UI_ACCENT) -> None:
    if start_time is None:
        return
    now = time.time()
    elapsed = now - start_time
    progress = min(elapsed / hold_time, 1.0)
    radius = 25
    center = (x, y)
    cv2.circle(frame, center, radius, UI_SECONDARY, 2)
    if progress < 1.0:
        angle = int(360 * progress)
        start_angle = -90
        end_angle = start_angle + angle
        axes = (radius - 2, radius - 2)
        cv2.ellipse(frame, center, axes, 0, start_angle, end_angle, color, -1)
        percent_text = f"{int(progress * 100)}%"
        text_size = cv2.getTextSize(percent_text, FONT, 0.5, 1)[0]
        cv2.putText(frame, percent_text, (center[0] - text_size[0] // 2, center[1] + 5),
                    FONT, 0.5, TEXT_COLOR, 1)
    else:
        cv2.circle(frame, center, radius - 2, color, -1)
        checkmark_points = np.array([
            [center[0] - 10, center[1]],
            [center[0] - 3, center[1] + 7],
            [center[0] + 10, center[1] - 7]
        ], np.int32)
        cv2.polylines(frame, [checkmark_points], False, UI_BACKGROUND, 2)
    label_size = cv2.getTextSize(label, FONT, 0.5, 1)[0]
    cv2.putText(frame, label, (center[0] - label_size[0] // 2, center[1] - radius - 7),
                FONT, 0.5, color, 1)


def get_fingertips_from_landmarks(hand_landmarks) -> list:
    indices = [4, 8, 12, 16, 20]
    fingertips = []
    try:
        if hand_landmarks and hasattr(hand_landmarks, 'landmark'):
            for idx in indices:
                if idx < len(hand_landmarks.landmark):
                    landmark = hand_landmarks.landmark[idx]
                    if hasattr(landmark, 'x') and hasattr(landmark, 'y') and hasattr(landmark, 'z'):
                        fingertips.append({"x": float(landmark.x),
                                           "y": float(landmark.y),
                                           "z": float(landmark.z)})
                    else:
                        fingertips.append({"x": 0.5, "y": 0.5, "z": 0.0})
                else:
                    fingertips.append({"x": 0.5, "y": 0.5, "z": 0.0})
        return fingertips
    except Exception as e:
        logging.error(f"Error extracting fingertips: {e}")
        return [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(5)]


def get_finger_positions(hand_landmarks) -> dict:
    if not hand_landmarks:
        return None
    fingers = {
        "thumb": [hand_landmarks.landmark[1], hand_landmarks.landmark[2],
                  hand_landmarks.landmark[3], hand_landmarks.landmark[4]],
        "index": [hand_landmarks.landmark[5], hand_landmarks.landmark[6],
                  hand_landmarks.landmark[7], hand_landmarks.landmark[8]],
        "middle": [hand_landmarks.landmark[9], hand_landmarks.landmark[10],
                   hand_landmarks.landmark[11], hand_landmarks.landmark[12]],
        "ring": [hand_landmarks.landmark[13], hand_landmarks.landmark[14],
                 hand_landmarks.landmark[15], hand_landmarks.landmark[16]],
        "pinky": [hand_landmarks.landmark[17], hand_landmarks.landmark[18],
                  hand_landmarks.landmark[19], hand_landmarks.landmark[20]],
        "wrist": hand_landmarks.landmark[0]
    }
    return fingers


def is_thumb_pinky_touching(fingers: dict) -> bool:
    if not fingers:
        return False
    thumb_tip = fingers["thumb"][3]
    pinky_tip = fingers["pinky"][3]
    distance = np.sqrt((thumb_tip.x - pinky_tip.x) ** 2 +
                       (thumb_tip.y - pinky_tip.y) ** 2 +
                       (thumb_tip.z - pinky_tip.z) ** 2)
    return distance < 0.05


def is_thumb_index_touching(fingers: dict) -> bool:
    if not fingers:
        return False
    thumb_tip = fingers["thumb"][3]
    index_tip = fingers["index"][3]
    distance = np.sqrt((thumb_tip.x - index_tip.x) ** 2 +
                       (thumb_tip.y - index_tip.y) ** 2 +
                       (thumb_tip.z - index_tip.z) ** 2)
    return distance < 0.05


def is_thumb_middle_touching(fingers: dict) -> bool:
    if not fingers:
        return False
    thumb_tip = fingers["thumb"][3]
    middle_tip = fingers["middle"][3]
    distance = np.sqrt((thumb_tip.x - middle_tip.x) ** 2 +
                       (thumb_tip.y - middle_tip.y) ** 2 +
                       (thumb_tip.z - middle_tip.z) ** 2)
    result = distance < 0.08
    if result:
        logging.debug(f"Thumb-middle finger touching detected! Distance: {distance:.4f}")
    return result


def is_thumb_ring_touching(fingers: dict) -> bool:
    if not fingers:
        return False
    thumb_tip = fingers["thumb"][3]
    ring_tip = fingers["ring"][3]
    distance = np.sqrt((thumb_tip.x - ring_tip.x) ** 2 +
                       (thumb_tip.y - ring_tip.y) ** 2 +
                       (thumb_tip.z - ring_tip.z) ** 2)
    return distance < 0.05


def is_closed_fist(fingers: dict) -> bool:
    if not fingers:
        return False
    for finger_name in ["index", "middle", "ring", "pinky"]:
        base_knuckle = fingers[finger_name][0]
        fingertip = fingers[finger_name][3]
        if not (fingertip.y > base_knuckle.y):
            return False
    return True


def get_fingers_pointing_up(fingers: dict) -> bool:
    if not fingers:
        return False
    wrist = fingers["wrist"]
    for finger_name in ["index", "middle", "ring", "pinky"]:
        fingertip = fingers[finger_name][3]
        base = fingers[finger_name][0]
        if fingertip.y > wrist.y or fingertip.y > base.y:
            return False
    return True


def calculate_wrist_rotation(fingers: dict) -> float:
    if not fingers:
        return 0.0
    wrist = fingers["wrist"]
    middle_mcp = fingers["middle"][0]
    dx = middle_mcp.x - wrist.x
    dy = middle_mcp.y - wrist.y
    angle = np.degrees(np.arctan2(dy, dx))
    return angle


def calculate_rotation_speed(wrist_angle: float) -> float:
    neutral_zone = 5.0
    max_angle = 40.0
    max_speed = 45.0
    if abs(wrist_angle) < neutral_zone:
        return 0.0
    if wrist_angle > 0:
        normalized = min((wrist_angle - neutral_zone) / (max_angle - neutral_zone), 1.0)
    else:
        normalized = max((wrist_angle + neutral_zone) / (max_angle - neutral_zone), -1.0)
    return normalized * max_speed


def determine_scale_axis(fingers: dict) -> str:
    if not fingers:
        return "XYZ"
    wrist = fingers["wrist"]
    middle_tip = fingers["middle"][3]
    dx = middle_tip.x - wrist.x
    dy = middle_tip.y - wrist.y
    dz = middle_tip.z - wrist.z
    abs_dx, abs_dy, abs_dz = abs(dx), abs(dy), abs(dz)
    max_d = max(abs_dx, abs_dy, abs_dz)
    if max_d < 0.1:
        return "XYZ"
    if abs_dx == max_d:
        return "X"
    elif abs_dy == max_d:
        return "Y"
    else:
        return "Z"


def pad_fingertips(fingertips: list, target_count: int = 5, default: dict = None) -> list:
    if not fingertips:
        if default:
            return [default.copy() for _ in range(target_count)]
        return [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(target_count)]
    fingertips_copy = [tip.copy() if isinstance(tip, dict) else {"x": 0.5, "y": 0.5, "z": 0.0}
                       for tip in fingertips]
    if len(fingertips_copy) < target_count:
        last_item = fingertips_copy[-1] if fingertips_copy else {"x": 0.5, "y": 0.5, "z": 0.0}
        padding = [last_item.copy() for _ in range(target_count - len(fingertips_copy))]
        return fingertips_copy + padding
    return fingertips_copy[:target_count]


def draw_hand_boundary(frame: np.ndarray, hand_landmarks, hand_type: str) -> None:
    if not hand_landmarks:
        return
    h, w, _ = frame.shape
    points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
    hull = cv2.convexHull(np.array(points))
    color = RIGHT_HAND_COLOR if hand_type == "Right" else LEFT_HAND_COLOR
    cv2.drawContours(frame, [hull], 0, color, 2)
    x_min = min(x for x, _ in points)
    y_min = max(min(y for _, y in points) - 15, 15)
    label_text = f"{hand_type} Hand"
    text_size = cv2.getTextSize(label_text, FONT, TEXT_SCALE, TEXT_THICKNESS)[0]
    cv2.putText(frame, label_text, (x_min, y_min), FONT, TEXT_SCALE, color, TEXT_THICKNESS)


def create_ui_overlay(frame: np.ndarray) -> None:
    h, w = frame.shape[:2]
    overlay_height = 60
    cv2.rectangle(frame, (0, 0), (w, overlay_height), UI_BACKGROUND, -1)
    title = "VIBE"
    title_size = cv2.getTextSize(title, FONT, 1.2, 3)[0]
    title_x = 20
    title_y = overlay_height // 2 + title_size[1] // 2 - 4
    cv2.putText(frame, title, (title_x, title_y), FONT, 1.2, UI_ACCENT, 3)

    # Add current remesh type to UI
    remesh_type = REMESH_TYPES[current_remesh_index]
    remesh_text = f"Remesh: {remesh_type}"
    remesh_size = cv2.getTextSize(remesh_text, FONT, 0.7, 2)[0]
    remesh_x = w - remesh_size[0] - 20
    cv2.putText(frame, remesh_text, (remesh_x, title_y), FONT, 0.7, UI_ACCENT, 2)


def update_anchor_position(position: dict) -> None:
    global current_anchor, anchor_in_progress
    current_anchor = position
    anchor_in_progress = position is not None


def add_anchor_to_list(anchor: dict) -> None:
    global anchors
    if anchor is not None:
        anchors.append(anchor.copy())
        logging.debug(f"Added anchor at ({anchor['x']:.2f}, {anchor['y']:.2f}, {anchor['z']:.2f})")


def clear_anchors() -> None:
    global current_anchor, anchor_in_progress, anchors
    anchors.clear()
    current_anchor = None
    anchor_in_progress = False
    logging.debug("Cleared all anchors")


def cycle_remesh_type() -> str:
    global current_remesh_index, remesh_last_toggle_time
    now = time.time()
    time_since_last = now - remesh_last_toggle_time
    logging.debug(f"Cycle remesh called - time since last toggle: {time_since_last:.2f}s, cooldown: {TOGGLE_COOLDOWN}s")
    
    if time_since_last < TOGGLE_COOLDOWN:
        logging.debug(f"Skipping remesh cycle - cooldown active ({TOGGLE_COOLDOWN-time_since_last:.2f}s remaining)")
        return REMESH_TYPES[current_remesh_index]
        
    current_remesh_index = (current_remesh_index + 1) % len(REMESH_TYPES)
    remesh_last_toggle_time = now
    new_type = REMESH_TYPES[current_remesh_index]
    logging.debug(f"Remesh type switched to: {new_type} (index {current_remesh_index})")
    return new_type


def draw_remesh_notification(frame, remesh_type):
    """Draw a temporary notification for remesh type change"""
    h, w = frame.shape[:2]
    notification_text = f"REMESH TYPE: {remesh_type.upper()}"
    
    # Get text size
    text_size = cv2.getTextSize(notification_text, FONT, 1.2, 3)[0]
    
    # Create background for notification
    padding = 30
    box_width = text_size[0] + padding * 2
    box_height = text_size[1] + padding * 1.5
    box_x = (w - box_width) // 2
    box_y = h // 3
    
    # Draw semi-transparent background with border
    overlay = frame.copy()
    # Draw outer border
    cv2.rectangle(overlay, 
                 (int(box_x-3), int(box_y-3)), 
                 (int(box_x + box_width+3), int(box_y + box_height+3)), 
                 UI_HIGHLIGHT, -1)
    # Draw inner background
    cv2.rectangle(overlay, 
                 (int(box_x), int(box_y)), 
                 (int(box_x + box_width), int(box_y + box_height)), 
                 UI_BACKGROUND, -1)
    cv2.addWeighted(overlay, 0.9, frame, 0.1, 0, frame)
    
    # Draw text
    text_x = int(box_x + padding)
    text_y = int(box_y + text_size[1] + padding // 2)
    cv2.putText(frame, notification_text, (text_x, text_y), FONT, 1.2, UI_ACCENT, 3)


def check_voice_commands() -> str:
    # Commenting out voice command processing
    return ""
    
    # global global_command, latest_transcription
    # try:
    #     if os.path.exists(VOICE_TXT):
    #         with open(VOICE_TXT, "r") as f:
    #             lines = f.readlines()
    #             if not lines:
    #                 return ""
    #             last_line = lines[-1].strip().lower()
    #             voice_command = ""
    #             
    #             if "rotate" in last_line or "turn" in last_line:
    #                 global_command = "rotate"
    #                 logging.info("Voice command detected: ROTATE")
    #             elif "deform" in last_line or "sculpt" in last_line:
    #                 global_command = "deform"
    #                 logging.info("Voice command detected: DEFORM")
    #             elif "scale" in last_line or "resize" in last_line:
    #                 # Check for precise scaling commands like "scale x to 2.5"
    #                 if "to" in last_line and any(axis in last_line for axis in ["x", "y", "z"]):
    #                     global_command = "none"  # Don't change mode
    #                     voice_command = last_line  # Pass the whole command for parsing
    #                     logging.info(f"Voice command detected: PRECISE SCALE - {last_line}")
    #                 else:
    #                     global_command = "scale"
    #                     logging.info("Voice command detected: SCALE")
    #             elif "create" in last_line or "add cube" in last_line:
    #                 global_command = "create"
    #                 logging.info("Voice command detected: CREATE")
    #             elif "anchor" in last_line:
    #                 global_command = "anchor"
    #                 logging.info("Voice command detected: ANCHOR")
    #             elif "remesh" in last_line:
    #                 cycle_remesh_type()
    #                 logging.info("Voice command detected: REMESH CYCLE")
    #             elif "dynamic topology" in last_line or "dyntopo" in last_line:
    #                 global_command = "dyntopo"
    #                 logging.info("Voice command detected: DYNAMIC TOPOLOGY")
    #             elif "boolean" in last_line:
    #                 global_command = "boolean"
    #                 if "union" in last_line:
    #                     voice_command = "union"
    #                 elif "difference" in last_line or "subtract" in last_line:
    #                     voice_command = "difference"
    #                 elif "intersect" in last_line:
    #                     voice_command = "intersect"
    #                 logging.info(f"Voice command detected: BOOLEAN {voice_command.upper()}")
    #             elif "material" in last_line or "assign material" in last_line:
    #                 global_command = "material"
    #                 logging.info("Voice command detected: MATERIAL")
    #             elif "bridge" in last_line and "edge" in last_line:
    #                 voice_command = "bridge edges"
    #                 logging.info("Voice command detected: BRIDGE EDGES")
    #             elif "smooth" in last_line and "edge" in last_line:
    #                 voice_command = "smooth edges"
    #                 logging.info("Voice command detected: SMOOTH EDGES")
    #             elif "extrude" in last_line:
    #                 voice_command = "extrude"
    #                 logging.info("Voice command detected: EXTRUDE")
    #             elif "inset" in last_line:
    #                 voice_command = "inset"
    #                 logging.info("Voice command detected: INSET")
    #             elif "snap" in last_line:
    #                 voice_command = "enable snapping"
    #                 logging.info("Voice command detected: ENABLE SNAPPING")
    #             elif "stop" in last_line or "cancel" in last_line or "reset" in last_line:
    #                 global_command = "none"
    #                 logging.info("Voice command detected: STOP")
    #             
    #             # Store the voice command for use in the JSON data
    #             latest_transcription = last_line
    #             return voice_command
    #             
    #         with open(VOICE_TXT, "w"):
    #             pass
    # except Exception as e:
    #     logging.error(f"Error processing voice commands: {e}")
    # return ""


def is_left_and_right_pinky_touching(left_fingers, right_fingers):
    if not left_fingers or not right_fingers:
        return False
    try:
        left_pinky_tip = left_fingers["pinky"][3]
        right_pinky_tip = right_fingers["pinky"][3]
        distance = np.sqrt((left_pinky_tip.x - right_pinky_tip.x) ** 2 +
                           (left_pinky_tip.y - right_pinky_tip.y) ** 2 +
                           (left_pinky_tip.z - right_pinky_tip.z) ** 2)
        return distance < 0.08
    except:
        return False


def apply_sculpt_brush(mesh_obj, fingertips, brush_type="GRAB"):
    """Map finger movements to sculpt brushes directly"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def toggle_dyntopo(mesh_obj, detail_size=12):
    """Enable/disable dynamic topology for adaptive detail"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def multi_select_objects(fingertips_left, fingertips_right):
    """Select multiple objects with bimanual gestures"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def apply_boolean(obj_a, obj_b, operation="UNION"):
    """Apply boolean operations between objects"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def assign_material_to_selection(material_index):
    """Assign materials based on finger position or voice command"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def enable_snapping(snap_type="INCREMENT"):
    """Toggle different snapping modes with gestures"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def precise_scale(obj, axis, value):
    """Apply precise numerical scaling based on voice commands"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def extrude_selection(direction, distance):
    """Extrude selected faces in specified direction"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def smooth_edge_flow():
    """Apply edge flow smoothing to selected edges"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def activate_hardops_tool(tool_name):
    """Activate Hard Ops tools through gestures"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def adjust_mesh_complexity(detail_level):
    """Dynamically adjust mesh complexity based on system performance"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def optimized_deform(finger_pos, mesh_obj, use_octree=True):
    """Use spatial partitioning for faster vertex selection"""
    # This function is only a placeholder in UI
    # Implementation requires bpy which is only available in Blender
    pass


def copy_text_file(source_file: str, target_file: str) -> None:
    """Copy the contents of source file to target file"""
    try:
        source_path = os.path.join(TEXT_SELECTOR_DIRECTORY, source_file)
        target_path = os.path.join(TEXT_SELECTOR_DIRECTORY, target_file)
        
        if not os.path.exists(source_path):
            logging.error(f"Source file not found: {source_path}")
            return
            
        with open(source_path, 'r', encoding='utf-8') as source:
            content = source.read()
            
        with open(target_path, 'w', encoding='utf-8') as target:
            target.write(content)
            
        logging.info(f"Successfully copied {source_file} to {target_file}")
    except Exception as e:
        logging.error(f"Error copying file: {e}")


def render_multiview():
    """
    Initiates the rendering process for multiview images.
    This is a placeholder that would trigger the rendering in Blender.
    Since we can't use bpy directly in ui.py, this function will:
    1. Export a command to the JSON file to indicate a render should happen
    2. Wait for the render to complete by checking for output images
    
    Returns:
        bool: True if rendering was successful, False otherwise
    """
    try:
        logging.info("Requesting multiview render...")
        
        # Signal to Blender that a render is needed via the hand data JSON
        data = {
            "command": "render_multiview",
            "timestamp": time.time()
        }
        
        render_command_path = os.path.join(os.path.dirname(OUTPUT_JSON), "render_command.json")
        with open(render_command_path, "w") as f:
            json.dump(data, f)
        
        # Wait for render to complete - check for marker file or output images
        render_output_dir = os.path.join(os.path.dirname(OUTPUT_JSON), "render_output")
        render_complete_marker = os.path.join(render_output_dir, "render_complete.txt")
        
        # Wait up to 60 seconds for the render to complete
        timeout = time.time() + 60
        while time.time() < timeout:
            if os.path.exists(render_complete_marker):
                logging.info("Render completed successfully")
                return True
                
            # Check if expected output images exist
            expected_images = [
                os.path.join(render_output_dir, f"view_{i}.png") for i in range(1, 5)
            ]
            if all(os.path.exists(img) for img in expected_images):
                logging.info("Found all expected render outputs")
                return True
                
            time.sleep(0.5)
            
        logging.error("Render timed out waiting for completion")
        return False
        
    except Exception as e:
        logging.error(f"Error in render_multiview: {e}")
        return False


def test_comfyui_connection():
    """
    Tests if ComfyUI server is available and running.
    Returns True if connection is successful.
    """
    # First check if port 8188 is open
    try:
        logging.info("Testing ComfyUI server connection...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('127.0.0.1', 8188))
        sock.close()
        
        if result != 0:
            logging.error("Port 8188 is not open. ComfyUI server doesn't appear to be running")
            return False
            
        # If port is open, try a simple GET request
        logging.info("Port check passed, testing HTTP connection...")
        response = urllib.request.urlopen("http://127.0.0.1:8188/")
        if response.status == 200:
            logging.info("ComfyUI server is running and responding to HTTP requests")
            return True
        else:
            logging.error(f"ComfyUI server returned unexpected status: {response.status}")
            return False
            
    except socket.error as e:
        logging.error(f"Socket error testing ComfyUI connection: {e}")
        return False
    except urllib.error.URLError as e:
        logging.error(f"URL error testing ComfyUI connection: {e}")
        return False
    except Exception as e:
        logging.error(f"Unknown error testing ComfyUI connection: {e}")
        return False


def process_multiview_mesh():
    """
    Orchestrates the complete workflow:
    1. Renders images from Blender
    2. Uses multiview_API.py to generate a mesh
    3. Imports the mesh back to Blender as deformingMesh with remesh
    """
    global _render_in_progress
    try:
        logging.info("=== STARTING MULTIVIEW MESH WORKFLOW ===")
        
        # First test ComfyUI connection
        if not test_comfyui_connection():
            logging.error("ComfyUI server is not available. Make sure it's running before continuing.")
            _render_in_progress = False
            return False
        
        # Step 1: Render images from Blender
        logging.info("Step 1: Starting multi-view render process")
        render_success = render_multiview()
        if not render_success:
            logging.error("Failed to render multi-view images")
            _render_in_progress = False  # Reset flag on failure
            return False

        # Step 2: Generate mesh using multiview_API.py - SIMPLIFIED APPROACH
        logging.info("Step 2: Starting mesh generation process with ComfyUI")
        
        # Find the multiview_API.py script
        script_found = False
        possible_paths = [
            # Try several potential locations
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "comfyworkflows", "multiview_API.py"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "comfyworkflows", "multiview_API.py"),
            "C:\\CODING\\VIBE\\VIBE_Massing\\src\\comfyworkflows\\multiview_API.py",
            "C:\\CODING\\VIBE\\VIBE_Massing\\comfyworkflows\\multiview_API.py"
        ]
        
        multiview_script = None
        for path in possible_paths:
            logging.info(f"Checking for script at: {path}")
            if os.path.exists(path):
                multiview_script = path
                script_found = True
                logging.info(f"Found multiview script at: {path}")
                break
                
        if not script_found:
            logging.error("Could not find multiview_API.py script in any expected location")
            _render_in_progress = False
            return False
            
        # Check if the JSON file exists in the same directory
        json_path = os.path.join(os.path.dirname(multiview_script), "multiview.json")
        if not os.path.exists(json_path):
            logging.error(f"Required JSON file not found: {json_path}")
            _render_in_progress = False
            return False
            
        logging.info(f"Found required JSON file at: {json_path}")
        
        # Change to the comfyworkflows directory for execution
        original_dir = os.getcwd()
        script_dir = os.path.dirname(multiview_script)
        os.chdir(script_dir)
        logging.info(f"Changed directory to: {script_dir}")
        
        # Run the script directly using the system's Python - APPROACH 1: subprocess
        cmd = f"python \"{os.path.basename(multiview_script)}\""
        logging.info(f"Executing: {cmd} in directory {script_dir}")
        
        success = False
        
        # First try subprocess
        try:
            import subprocess
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            logging.info(f"Subprocess return code: {result.returncode}")
            logging.info(f"Subprocess output: {result.stdout}")
            
            if result.returncode == 0:
                logging.info("Mesh generation process completed successfully with subprocess")
                success = True
            else:
                logging.error(f"Subprocess error: {result.stderr}")
        except Exception as e:
            logging.error(f"Error running subprocess command: {e}")
            
        # If subprocess failed, try os.system as fallback
        if not success:
            logging.info("Trying alternative execution method with os.system")
            try:
                return_code = os.system(cmd)
                logging.info(f"os.system return code: {return_code}")
                
                if return_code == 0:
                    logging.info("Mesh generation process completed successfully with os.system")
                    success = True
                else:
                    logging.error(f"os.system execution failed with code: {return_code}")
            except Exception as e:
                logging.error(f"Error using os.system: {e}")
        
        # Change back to original directory
        os.chdir(original_dir)
        logging.info(f"Changed back to original directory: {original_dir}")
                
        if not success:
            logging.error("All execution methods failed")
            _render_in_progress = False
            return False

        # Step 3: Import mesh back to Blender
        logging.info("Step 3: Requesting Blender to import the generated mesh")
        target_mesh_path = os.path.join("C:\\CODING\\VIBE\\VIBE_Massing\\output\\generated\\Models", "current_mesh.glb")
        logging.info(f"Looking for generated mesh at: {target_mesh_path}")
        
        if not os.path.exists(target_mesh_path):
            logging.error(f"Generated mesh not found at {target_mesh_path}")
            _render_in_progress = False  # Reset flag on failure
            return False

        # Signal to Blender to import the mesh and replace the existing deformingMesh
        import_command = {
            "command": "import_mesh",
            "mesh_path": target_mesh_path,
            "remesh_type": REMESH_TYPES[current_remesh_index],
            "timestamp": time.time()
        }
        
        import_command_path = os.path.join(os.path.dirname(OUTPUT_JSON), "import_command.json")
        with open(import_command_path, "w") as f:
            json.dump(import_command, f)
            
        logging.info(f"Requested mesh import with remesh type: {REMESH_TYPES[current_remesh_index]}")
        logging.info("=== MULTIVIEW MESH WORKFLOW COMPLETED SUCCESSFULLY ===")
        _render_in_progress = False  # Reset flag on success
        return True

    except Exception as e:
        logging.error(f"Error in process_multiview_mesh: {e}")
        import traceback
        logging.error(traceback.format_exc())
        _render_in_progress = False  # Reset flag on exception
        return False


def run_multiview_api_directly():
    """
    Direct approach to run multiview_API.py with hardcoded paths.
    No fancy error handling or extra steps.
    """
    global _render_in_progress
    
    try:
        logging.info("RUNNING MULTIVIEW API DIRECTLY")
        
        # Create session directory with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_output_dir = "C:\\CODING\\VIBE\\VIBE_Massing\\output\\generated\\Models"
        session_dir = os.path.join(base_output_dir, f"session_{timestamp}")
        
        # Create directory if it doesn't exist
        os.makedirs(session_dir, exist_ok=True)
        logging.info(f"Created session directory: {session_dir}")
        
        # Find the next available iteration number
        iteration = 0
        while os.path.exists(os.path.join(session_dir, f"iteration_{iteration:03d}.glb")):
            iteration += 1
        
        iteration_filename = f"iteration_{iteration:03d}.glb"
        target_path = os.path.join(session_dir, iteration_filename)
        logging.info(f"Will save as iteration: {iteration_filename}")
        
        # Hardcoded absolute path to the script
        script_path = "C:\\CODING\\VIBE\\VIBE_Massing\\src\\comfyworkflows\\multiview_API.py"
        
        # Get the full path to the Python executable
        python_executable = sys.executable
        logging.info(f"Using Python executable: {python_executable}")
        
        # Temporarily modify the target output in a copy of the script
        temp_script_path = os.path.join(os.path.dirname(script_path), "temp_multiview_API.py")
        with open(script_path, 'r') as src_file:
            content = src_file.read()
            
        # Replace the TARGET_OUTPUT line
        modified_content = content.replace(
            'TARGET_OUTPUT = "C:\\\\CODING\\\\VIBE\\\\VIBE_Massing\\\\output\\\\generated\\\\Models"',
            f'TARGET_OUTPUT = "{session_dir}"'
        )
        
        # Also change current_mesh.glb to our iteration filename
        modified_content = modified_content.replace(
            'target_path = os.path.join(target_dir, "current_mesh.glb")',
            f'target_path = os.path.join(target_dir, "{iteration_filename}")'
        )
        
        with open(temp_script_path, 'w') as dest_file:
            dest_file.write(modified_content)
        
        logging.info(f"Created temporary script with modified output path: {temp_script_path}")
        
        # Use subprocess.run instead of os.system to handle paths with spaces properly
        logging.info(f"Running modified script with subprocess.run: {temp_script_path}")
        result = subprocess.run([python_executable, temp_script_path], 
                               capture_output=True, 
                               text=True,
                               check=False)
        
        logging.info(f"Return code: {result.returncode}")
        logging.info(f"Output: {result.stdout}")
        
        if result.returncode != 0:
            logging.error(f"Error output: {result.stderr}")
            
        # Clean up temp script
        try:
            os.remove(temp_script_path)
            logging.info("Removed temporary script")
        except:
            logging.warning("Could not remove temporary script")
            
        # Also copy the file to current_mesh.glb for compatibility
        if os.path.exists(target_path):
            standard_path = os.path.join(base_output_dir, "current_mesh.glb")
            try:
                shutil.copy2(target_path, standard_path)
                logging.info(f"Copied mesh to standard path: {standard_path}")
            except Exception as e:
                logging.error(f"Error copying to standard path: {e}")
        
        # Signal to Blender to import the mesh and replace the existing deformingMesh
        import_command = {
            "command": "import_mesh",
            "mesh_path": target_path,
            "remesh_type": REMESH_TYPES[current_remesh_index],
            "timestamp": time.time(),
            "session_dir": session_dir,
            "iteration": iteration,
            "collection_settings": {
                "name": "VIBE_Renders",
                "hide_viewport": True,
                "hide_render": True,
                "instance_name": f"Render_{iteration:03d}"
            }
        }
        
        import_command_path = os.path.join(os.path.dirname(OUTPUT_JSON), "import_command.json")
        with open(import_command_path, "w") as f:
            json.dump(import_command, f)
            
        logging.info(f"Requested mesh import with special collection handling")
        
    except Exception as e:
        logging.error(f"Error in run_multiview_api_directly: {e}")
        import traceback
        logging.error(traceback.format_exc())
    finally:
        # Reset render flag
        _render_in_progress = False
        logging.info("Execution completed")


# ----------------------------- #
#       GLOBAL STATE            #
# ----------------------------- #

global_command = "none"
current_gesture = "none"
last_detected_gesture = "none"
gesture_start_time = None
command_set_time = 0
_render_in_progress = False  # New global variable to track render status

left_hand_landmarks = None
right_hand_landmarks = None
left_fingertips = None
right_fingertips = None
left_fingers = None
right_fingers = None

anchors = []
anchor_in_progress = False
current_anchor = None
anchor_gesture_start_time = None
anchor_creation_confirmed = False

left_fist_held_start = None
right_deform_start_time = None
right_rotate_start_time = None
right_scale_start_time = None
right_create_start_time = None
left_remesh_start_time = None

scale_axis = "XYZ"
scale_value = 1.0
last_scale_time = 0

rotation_reference = None
rotation_value = 0.0
rotation_speed = 0.0

current_remesh_index = 0
remesh_last_toggle_time = time.time()  # Initialize to current time

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

hands = mp_hands.Hands(static_image_mode=False,
                       max_num_hands=2,
                       min_detection_confidence=0.7,
                       min_tracking_confidence=0.5)

# Commenting out Whisper model loading
# logging.info("Loading Whisper model for voice transcription...")
# voice_model = whisper.load_model("base")


# def record_and_transcribe_voice() -> None:
#     global latest_transcription
#     fs = 16000
#     if not os.path.exists(VOICE_TXT):
#         with open(VOICE_TXT, "w") as f:
#             pass
#     last_transcription = ""
#     while True:
#         audio = sd.rec(int(5 * fs), samplerate=fs, channels=1, dtype='float32')
#         sd.wait()
#         audio = audio.flatten()
#         try:
#             result = voice_model.transcribe(audio, fp16=False, language="en")
#             text = result.get("text", "").strip()
#             if text and text != last_transcription:
#                 with open(VOICE_TXT, "a") as f:
#                     f.write(text + "\n")
#                 latest_transcription = text
#                 logging.info(f"Voice transcription: {text}")
#                 last_transcription = text
#         except Exception as e:
#             logging.error(f"Voice transcription error: {e}")


# Commenting out voice thread start
# voice_thread = threading.Thread(target=record_and_transcribe_voice, daemon=True)
# voice_thread.start()


# ----------------------------- #
#           MAIN LOOP           #
# ----------------------------- #

def main() -> None:
    global global_command, current_gesture, last_detected_gesture, gesture_start_time, command_set_time
    global left_hand_landmarks, right_hand_landmarks, left_fingertips, right_fingertips, left_fingers, right_fingers
    global anchor_gesture_start_time, anchor_creation_confirmed, anchor_in_progress, current_anchor
    global left_fist_held_start, right_deform_start_time, rotation_reference, rotation_value, rotation_speed
    global right_rotate_start_time, right_scale_start_time, right_create_start_time, left_remesh_start_time
    global scale_axis, scale_value, current_remesh_index, right_fist_start_time, deform_mode_active
    global remesh_last_toggle_time, text_selector_mode

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    native_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    native_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cv2.namedWindow("VIBE - Hand Gesture Control", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("VIBE - Hand Gesture Control", native_width, native_height)
    logging.info(f"Using camera resolution: {native_width}x{native_height}")

    logging.info("Running hand gesture recognition. Press 'q' to quit...")
    last_frame_time = time.time()

    while True:
        current_time = time.time()
        delta_time = current_time - last_frame_time
        last_frame_time = current_time

        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        create_ui_overlay(frame)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        # Reset per-frame variables
        left_hand_landmarks = None
        right_hand_landmarks = None
        left_fingertips = None
        right_fingertips = None
        left_fingers = None
        right_fingers = None
        current_gesture = "none"

        if results.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                hand_label = "Left"
                if (results.multi_handedness and len(results.multi_handedness) > hand_idx):
                    handedness = results.multi_handedness[hand_idx].classification[0]
                    hand_label = handedness.label
                color = (RIGHT_HAND_COLOR if hand_label == "Right" else LEFT_HAND_COLOR)
                drawing_spec = mp_drawing.DrawingSpec(color=(color[2], color[1], color[0]),
                                                      thickness=3, circle_radius=4)
                connection_spec = mp_drawing.DrawingSpec(color=(color[2], color[1], color[0]),
                                                         thickness=2)
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                                          drawing_spec, connection_spec)
                draw_hand_boundary(frame, hand_landmarks, hand_label)
                finger_positions = get_finger_positions(hand_landmarks)
                if hand_label == "Left":
                    left_hand_landmarks = hand_landmarks
                    left_fingertips = get_fingertips_from_landmarks(hand_landmarks)
                    left_fingers = finger_positions
                else:
                    right_hand_landmarks = hand_landmarks
                    right_fingertips = get_fingertips_from_landmarks(hand_landmarks)
                    right_fingers = finger_positions

        now = time.time()
        # Comment out periodic voice command checking
        # if now % 2 < 0.1:
        #    check_voice_commands()

        # -----------------------------
        #   GESTURE DETECTION
        # -----------------------------
        if right_fingers:
            # Deform
            if is_thumb_index_touching(right_fingers):
                if right_deform_start_time is None:
                    right_deform_start_time = now
                if now - right_deform_start_time >= GESTURE_HOLD_TIME:
                    if now - command_set_time >= TOGGLE_COOLDOWN:
                        if global_command != "deform":
                            global_command = "deform"
                            deform_mode_active = True
                            logging.debug("Deform mode ACTIVATED")
                        else:
                            deform_mode_active = not deform_mode_active
                            logging.debug(f"Deform mode {'ACTIVATED' if deform_mode_active else 'DEACTIVATED'}")
                        command_set_time = now
                current_gesture = "deform"
            else:
                right_deform_start_time = None

            # Rotate
            if is_thumb_middle_touching(right_fingers):
                if right_rotate_start_time is None:
                    right_rotate_start_time = now
                if now - right_rotate_start_time >= GESTURE_HOLD_TIME:
                    if global_command != "rotate" and now - command_set_time >= TOGGLE_COOLDOWN:
                        global_command = "rotate"
                        command_set_time = now
                        logging.debug("Mode set to: ROTATE")
                current_gesture = "rotate"
                if global_command == "rotate":
                    current_rotation = calculate_wrist_rotation(right_fingers)
                    if rotation_reference is None:
                        rotation_reference = current_rotation
                    rotation_diff = current_rotation - rotation_reference
                    if rotation_diff > 180:
                        rotation_diff -= 360
                    elif rotation_diff < -180:
                        rotation_diff += 360
                    rotation_speed = calculate_rotation_speed(rotation_diff)
                    if rotation_speed != 0:
                        rotation_value += rotation_speed * delta_time
            else:
                right_rotate_start_time = None

            # Scale
            if is_thumb_ring_touching(right_fingers):
                if right_scale_start_time is None:
                    right_scale_start_time = now
                if now - right_scale_start_time >= GESTURE_HOLD_TIME:
                    if global_command != "scale" and now - command_set_time >= TOGGLE_COOLDOWN:
                        global_command = "scale"
                        scale_axis = determine_scale_axis(right_fingers)
                        command_set_time = now
                        logging.debug(f"Mode set to: SCALE (axis: {scale_axis})")
                current_gesture = "scale"
            else:
                right_scale_start_time = None

            # Create
            if is_thumb_pinky_touching(right_fingers):
                if right_create_start_time is None:
                    right_create_start_time = now
                if now - right_create_start_time >= GESTURE_HOLD_TIME:
                    if global_command != "create" and now - command_set_time >= TOGGLE_COOLDOWN:
                        global_command = "create"
                        command_set_time = now
                        logging.debug("Mode set to: CREATE")
                current_gesture = "create"
            else:
                right_create_start_time = None

            if is_closed_fist(right_fingers):
                if right_fist_start_time is None:
                    right_fist_start_time = now
                if now - right_fist_start_time >= GESTURE_HOLD_TIME:
                    if global_command != "render" and now - command_set_time >= TOGGLE_COOLDOWN:
                        global_command = "render"
                        command_set_time = now
                        logging.debug("Mode set to: RENDER")
                current_gesture = "render"
            else:
                right_fist_start_time = None

        if left_fingers:
            try:
                # Anchor
                if is_thumb_index_touching(left_fingers):
                    if last_detected_gesture != "anchor":
                        anchor_gesture_start_time = now
                    if now - anchor_gesture_start_time >= GESTURE_HOLD_TIME:
                        if global_command != "anchor" and now - command_set_time >= TOGGLE_COOLDOWN:
                            global_command = "anchor"
                            command_set_time = now
                            logging.debug("Mode set to: ANCHOR")
                    current_gesture = "anchor"
                    thumb_tip = left_fingers["thumb"][3]
                    index_tip = left_fingers["index"][3]
                    anchor_position = {"x": (thumb_tip.x + index_tip.x) / 2,
                                       "y": (thumb_tip.y + index_tip.y) / 2,
                                       "z": (thumb_tip.z + index_tip.z) / 2}
                    if global_command == "anchor":
                        update_anchor_position(anchor_position)
                else:
                    if anchor_gesture_start_time is not None:
                        anchor_gesture_start_time = None
                        logging.debug("Left hand anchor gesture released")
                    if global_command == "anchor" and current_anchor:
                        add_anchor_to_list(current_anchor)
                        update_anchor_position(None)
                        logging.debug("Anchor finalized")

                # Remesh - improved detection and feedback
                if is_thumb_middle_touching(left_fingers):
                    logging.debug(f"Left hand remesh gesture detected - thumb and middle finger touch")
                    if left_remesh_start_time is None:
                        left_remesh_start_time = now
                        logging.debug("Left hand remesh gesture detected, started timing")
                    elif now - left_remesh_start_time >= GESTURE_HOLD_TIME:
                        logging.debug(f"Remesh gesture held for {now - left_remesh_start_time:.2f} seconds, cycling remesh type")
                        new_type = cycle_remesh_type()  # This will handle the cooldown internally
                        logging.info(f"Cycled remesh type to: {new_type}")
                        left_remesh_start_time = now  # Reset timer after cycling
                    current_gesture = "remesh"
                else:
                    left_remesh_start_time = None

                if is_closed_fist(left_fingers):
                    if left_fist_held_start is None:
                        left_fist_held_start = now
                        logging.debug("Left hand clear gesture detected, started timing")
                    elif now - left_fist_held_start >= CLEAR_HOLD_TIME:
                        if anchors:
                            logging.debug("Clearing anchors due to closed fist gesture.")
                            clear_anchors()
                            left_fist_held_start = now
                else:
                    left_fist_held_start = None

            except Exception as e:
                logging.error(f"Error in left hand gesture processing: {e}")
                anchor_in_progress = False

        last_detected_gesture = current_gesture

        if left_fingers and right_fingers and is_left_and_right_pinky_touching(left_fingers, right_fingers):
            if now - command_set_time >= TOGGLE_COOLDOWN:
                if global_command != "none":
                    logging.debug(f"Disabling mode {global_command} with pinky-to-pinky gesture")
                    global_command = "none"
                    command_set_time = now

        # -----------------------------
        #   Top UI Text
        # -----------------------------
        active_label = f"ACTIVE MODE: {global_command.upper()}" if global_command != "none" else "NO ACTIVE MODE"
        text_size = cv2.getTextSize(active_label, FONT, 0.7, 2)[0]
        text_x = (native_width // 2) - (text_size[0] // 2)
        cv2.putText(frame, active_label, (text_x, 40), FONT, 0.7, TEXT_COLOR, 2)

        # Comment out bottom UI band for voice transcription
        # -----------------------------
        #   Bottom UI Band for Voice Transcription
        # -----------------------------
        # # Get the latest transcription text (global variable updated by voice thread)
        # trans_text = latest_transcription
        # # Use a slightly larger font for transcription (e.g. scale 0.8)
        # (trans_w, trans_h), _ = cv2.getTextSize(trans_text, FONT, 0.8, 2)
        # band_height = trans_h + 10  # thin band with a small margin
        # info_bar_y = native_height - band_height
        # cv2.rectangle(frame, (0, info_bar_y), (native_width, native_height), UI_BACKGROUND, -1)
        # text_x_center = (native_width - trans_w) // 2
        # text_y = info_bar_y + trans_h + 5
        # cv2.putText(frame, trans_text, (text_x_center, text_y), FONT, 0.8, UI_ACCENT, 2)

        # -----------------------------
        #   Anchors and Progress Indicators
        # -----------------------------
        for i, anchor in enumerate(anchors):
            anchor_x = int(anchor["x"] * native_width)
            anchor_y = int(anchor["y"] * native_height)
            cv2.circle(frame, (anchor_x, anchor_y), 10, UI_SHADOW, -1)
            cv2.circle(frame, (anchor_x, anchor_y), 8, ANCHOR_COLOR, -1)
            cv2.putText(frame, f"A{i + 1}", (anchor_x + 12, anchor_y + 5), FONT, 0.5, ANCHOR_COLOR, 2)

        if anchor_in_progress and current_anchor:
            anchor_x = int(current_anchor["x"] * native_width)
            anchor_y = int(current_anchor["y"] * native_height)
            pulse = 2 + int(abs(math.sin(time.time() * 5)) * 3)
            cv2.circle(frame, (anchor_x, anchor_y), 14 + pulse, UI_SHADOW, -1)
            cv2.circle(frame, (anchor_x, anchor_y), 12 + pulse, UI_HIGHLIGHT, -1)
            cv2.putText(frame, "New", (anchor_x + 15, anchor_y + 5), FONT, 0.5, UI_HIGHLIGHT, 2)

        if right_fist_start_time is not None:
            draw_hold_progress(frame, native_width - 50, 250, right_fist_start_time, GESTURE_HOLD_TIME,
                               "Render", (50, 200, 50))
        if gesture_start_time is not None and current_gesture != "none":
            draw_hold_progress(frame, native_width - 50, 150, gesture_start_time, GESTURE_HOLD_TIME,
                               current_gesture.capitalize(), UI_ACCENT)
        if anchor_gesture_start_time is not None and not anchor_creation_confirmed:
            draw_hold_progress(frame, 70, native_height - 120, anchor_gesture_start_time, ANCHOR_HOLD_TIME,
                               "Anchor", ANCHOR_COLOR)
        if left_remesh_start_time is not None:
            draw_hold_progress(frame, 70, native_height - 180, left_remesh_start_time, GESTURE_HOLD_TIME,
                               "Remesh", UI_HIGHLIGHT)
        if left_fist_held_start is not None:
            draw_hold_progress(frame, 150, native_height - 120, left_fist_held_start, CLEAR_HOLD_TIME,
                               "Clear", (200, 50, 50))

        try:
            export_anchors = [anchor.copy() for anchor in anchors if anchor]
            if anchor_in_progress and current_anchor:
                export_anchors.append(current_anchor.copy())
            padded_left = pad_fingertips(left_fingertips) if left_fingertips else None
            padded_right = pad_fingertips(right_fingertips) if right_fingertips else None
            
            # Comment out voice command checking
            # voice_command = check_voice_commands()
            voice_command = ""
            
            data = {
                "command": global_command,
                "deform_active": deform_mode_active,
                "left_hand": {"fingertips": padded_left} if padded_left else None,
                "right_hand": {"fingertips": padded_right} if padded_right else None,
                "anchors": export_anchors,
                "rotation": float(rotation_value) if global_command == "rotate" else 0.0,
                "rotation_speed": float(rotation_speed) if global_command == "rotate" else 0.0,
                "scale_axis": scale_axis if global_command == "scale" else "XYZ",
                "remesh_type": REMESH_TYPES[current_remesh_index],
                "voice_command": voice_command,
                "transcription": ""  # Empty string instead of latest_transcription
            }
            with open(OUTPUT_JSON, "w") as f:
                json.dump(data, f, indent=2)
            
            # NEW ADDITION: DIRECTLY call the API on fist gesture (render command)
            global _render_in_progress
            if global_command == "render" and not _render_in_progress:
                logging.info("FIST GESTURE DETECTED - DIRECTLY CALLING MULTIVIEW API")
                _render_in_progress = True
                # Use a simple thread to run the script directly
                threading.Thread(target=run_multiview_api_directly, daemon=True).start()
                # Reset the render command after starting the process
                global_command = "none"
                command_set_time = now
                logging.debug("Render process started, command reset to 'none'")
            elif global_command == "render" and _render_in_progress:
                logging.debug("Render already in progress, ignoring command")
            
        except Exception as e:
            logging.error(f"Error during data export: {e}")

        # Add notification for remesh type change if it recently changed
        if current_time - remesh_last_toggle_time < 2.0:  # Increased from 1.5 to 2.0 seconds
            draw_remesh_notification(frame, REMESH_TYPES[current_remesh_index])

        cv2.imshow("VIBE - Hand Gesture Control", frame)
        
        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # Check for both 'q' and ESC
            logging.info("Exit key pressed. Terminating.")
            break
        elif key == ord('r'):  # Add 'r' key for remesh cycling
            new_type = cycle_remesh_type()
            logging.info(f"Manual remesh type change with 'r' key: {new_type}")
        elif key == ord('t'):  # Toggle text selector mode
            text_selector_mode = not text_selector_mode
            logging.info(f"Text selector mode {'activated' if text_selector_mode else 'deactivated'}")
        elif key == ord('v'):  # Manual trigger for multiview mesh process
            logging.info("Manual trigger: Starting multiview mesh generation process")
            threading.Thread(target=process_multiview_mesh, daemon=True).start()
        elif key == ord('x'):  # Test ComfyUI connection
            if test_comfyui_connection():
                logging.info("ComfyUI connection test: SUCCESS")
            else:
                logging.error("ComfyUI connection test: FAILED")
        elif text_selector_mode:  # Handle text selection keys when in text selector mode
            if key == ord('a'):
                copy_text_file('A_0001.txt', 'prompt.txt')
            elif key == ord('b'):
                copy_text_file('B_0001.txt', 'prompt.txt')
            elif key == ord('c'):
                copy_text_file('C_0001.txt', 'prompt.txt')

        # Add text selector mode indicator to the UI
        if text_selector_mode:
            mode_text = "TEXT SELECTOR MODE ACTIVE"
            text_size = cv2.getTextSize(mode_text, FONT, 0.7, 2)[0]
            text_x = (native_width // 2) - (text_size[0] // 2)
            cv2.putText(frame, mode_text, (text_x, 80), FONT, 0.7, (0, 255, 0), 2)

    cap.release()
    cv2.destroyAllWindows()
    logging.info("Hand gesture recognition script finished.")


if __name__ == "__main__":
    main()
