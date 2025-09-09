# This script is responsible for camera capture and hand tracking.
# It uses OpenCV to get video from the webcam and Mediapipe to detect
# hand landmarks. The processed data, including fingertip coordinates and
# the active command state, is written to a JSON file for Blender to read.

import cv2
import mediapipe as mp
import json
import os
import math
import time
from pathlib import Path

# --- Configuration ---
# This setup allows the script to be run from anywhere and still find the project root.
try:
    # Assumes the script is in launcher/
    PROJECT_ROOT = Path(__file__).parent.parent
except NameError:
    # Fallback for running from a different context or IDE
    PROJECT_ROOT = Path(os.path.abspath('')).parent

DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
FINGERTIPS_JSON_PATH = INPUT_DIR / "fingertips.json"

# Touch distance threshold - smaller is more precise
TOUCH_THRESHOLD = 0.035

# Gesture hold time in seconds
GESTURE_HOLD_DURATION = 0.25 # A short delay to prevent accidental activation

# Ensure the directory exists
os.makedirs(INPUT_DIR, exist_ok=True)

# --- Gesture Detection Helper ---
def get_distance(p1, p2):
    """Calculates the 3D distance between two landmark points."""
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

def is_thumb_and_finger_touching(hand_landmarks, finger_tip_id):
    """Checks if the thumb and a specified finger are close together."""
    if not hand_landmarks:
        return False
    
    thumb_tip = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.THUMB_TIP]
    finger_tip = hand_landmarks.landmark[finger_tip_id]
    
    distance = get_distance(thumb_tip, finger_tip)
    
    return distance < TOUCH_THRESHOLD

# --- Main Application Logic ---
def run_hand_tracker():
    """Initializes camera, runs Mediapipe, and writes data to JSON."""
    
    # Initialize Mediapipe
    mp_hands = mp.solutions.hands
    HAND_LANDMARKS = mp.solutions.hands.HandLandmark
    mp_drawing = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )

    # Define all gestures, their target finger, hand, and behavior
    GESTURE_MAPPING = {
        # Right Hand
        "deform":       {"finger": HAND_LANDMARKS.INDEX_FINGER_TIP, "hand": "Right", "type": "continuous"},
        "orbit":        {"finger": HAND_LANDMARKS.MIDDLE_FINGER_TIP, "hand": "Right", "type": "continuous"},
        "cycle_brush":  {"finger": HAND_LANDMARKS.RING_FINGER_TIP,   "hand": "Right", "type": "oneshot"},
        "rewind":       {"finger": HAND_LANDMARKS.PINKY_TIP,        "hand": "Right", "type": "continuous"},
        # Left Hand
        "cycle_radius":     {"finger": HAND_LANDMARKS.MIDDLE_FINGER_TIP, "hand": "Left", "type": "oneshot"},
        "cycle_primitive":  {"finger": HAND_LANDMARKS.MIDDLE_FINGER_TIP, "hand": "Left", "type": "oneshot"}, # Same gesture, context-dependent
        "confirm_placement": {"finger": HAND_LANDMARKS.RING_FINGER_TIP, "hand": "Left", "type": "oneshot"},
        "boolean_union":    {"finger": HAND_LANDMARKS.INDEX_FINGER_TIP, "hand": "Left", "type": "oneshot"},
        "boolean_difference": {"finger": HAND_LANDMARKS.PINKY_TIP, "hand": "Left", "type": "oneshot"},
    }

    # Initialize Webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera.")
        return

    print("Hand tracker running. Press 'q' to quit.")

    # State variables for the gesture detection logic
    active_gesture = "none"
    gesture_start_time = None
    fired_oneshot_gestures = set()
    last_orbit_hand_center = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Ignoring empty camera frame.")
            continue

        # Flip the frame horizontally for a later selfie-view display
        frame = cv2.flip(frame, 1)
        
        # Convert the BGR image to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process the frame and find hands
        results = hands.process(rgb_frame)

        # --- Gesture State Machine ---
        left_hand_fingertips = None
        right_hand_fingertips = None
        right_hand_landmarks_for_orbit = None
        
        # 1. Check for currently touched gestures
        potential_gesture = "none"
        if results.multi_hand_landmarks and results.multi_handedness:
            # Combine landmarks and handedness info into a single list
            hand_data = []
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                handedness_info = results.multi_handedness[i]
                hand_data.append((hand_landmarks, handedness_info))

            # Sort by handedness ("Left" comes before "Right" alphabetically)
            # This ensures we always check for left hand gestures first.
            hand_data.sort(key=lambda item: item[1].classification[0].label)
            
            # This loop now correctly prioritizes the left hand
            for hand_landmarks, handedness_info in hand_data:
                handedness = handedness_info.classification[0].label
                
                # Extract fingertips for the current hand
                fingertips = []
                for tip_id in [4, 8, 12, 16, 20]:
                    lm = hand_landmarks.landmark[tip_id]
                    fingertips.append({"x": lm.x, "y": lm.y, "z": lm.z})

                if handedness == "Left":
                    left_hand_fingertips = fingertips
                else: # Right
                    right_hand_fingertips = fingertips
                    right_hand_landmarks_for_orbit = hand_landmarks

                # Find the first matching gesture for this hand
                for gesture_name, gesture_info in GESTURE_MAPPING.items():
                    if gesture_info["hand"] == handedness:
                        if is_thumb_and_finger_touching(hand_landmarks, gesture_info["finger"]):
                            potential_gesture = gesture_name
                            break # A hand can only perform one gesture at a time
                
                # If we found a gesture, we can stop looking because of the sort priority.
                if potential_gesture != "none":
                    break

        # 2. Update state based on the potential gesture
        final_command = "none"
        if potential_gesture == active_gesture and active_gesture != "none":
            # The user is still holding the same gesture. Check if the hold duration has passed.
            if gesture_start_time is not None and (time.time() - gesture_start_time >= GESTURE_HOLD_DURATION):
                gesture_type = GESTURE_MAPPING[active_gesture]["type"]
                if gesture_type == "continuous":
                    final_command = active_gesture
                elif gesture_type == "oneshot":
                    if active_gesture not in fired_oneshot_gestures:
                        final_command = active_gesture
                        fired_oneshot_gestures.add(active_gesture)

        elif potential_gesture != "none":
            # A new gesture has been detected. Start the timer for it.
            active_gesture = potential_gesture
            gesture_start_time = time.time()
            fired_oneshot_gestures.clear() # Reset one-shot tracker
        
        else: # potential_gesture is "none"
            # No gestures are detected. Reset the state.
            active_gesture = "none"
            gesture_start_time = None
            fired_oneshot_gestures.clear()

        # --- Orbit Delta Calculation ---
        orbit_delta = {"x": 0.0, "y": 0.0}
        if final_command == "orbit" and right_hand_landmarks_for_orbit:
            thumb_tip = right_hand_landmarks_for_orbit.landmark[HAND_LANDMARKS.THUMB_TIP]
            middle_tip = right_hand_landmarks_for_orbit.landmark[HAND_LANDMARKS.MIDDLE_FINGER_TIP]
            current_orbit_hand_center = {"x": (thumb_tip.x + middle_tip.x) / 2, "y": (thumb_tip.y + middle_tip.y) / 2}

            if last_orbit_hand_center:
                orbit_delta["x"] = current_orbit_hand_center["x"] - last_orbit_hand_center["x"]
                orbit_delta["y"] = current_orbit_hand_center["y"] - last_orbit_hand_center["y"]
            
            last_orbit_hand_center = current_orbit_hand_center
        else:
            last_orbit_hand_center = None

        # Draw landmarks for debugging now that fingertips are processed
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        # --- Structure and Write JSON ---
        output_data = {
            "command": final_command,
            "left_hand": {"fingertips": left_hand_fingertips} if left_hand_fingertips else None,
            "right_hand": {"fingertips": right_hand_fingertips} if right_hand_fingertips else None,
            "orbit_delta": orbit_delta,
            "anchors": [],
            "scale_axis": "XYZ",
            "remesh_type": "BLOCKS"
        }

        try:
            with open(FINGERTIPS_JSON_PATH, 'w') as f:
                json.dump(output_data, f, indent=2)
        except Exception as e:
            print(f"Error writing to JSON file: {e}")

        # --- Display Debugging View ---
        # Display the active command being sent, and the potential command being held
        status_text = f"Command: {final_command} (Holding: {active_gesture})"
        color = (0, 255, 0) if final_command != "none" else (0, 0, 255)
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
        
        cv2.imshow('CONJURE Hand Tracker', frame)

        # Check for 'q' key to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    hands.close()
    cap.release()
    cv2.destroyAllWindows()
    print("Hand tracker stopped.")

if __name__ == "__main__":
    run_hand_tracker() 