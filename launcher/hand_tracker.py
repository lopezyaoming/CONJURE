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

# Touch distance threshold
TOUCH_THRESHOLD = 0.07 # Increased slightly for more reliable detection

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
    mp_drawing = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )

    # Initialize Webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera.")
        return

    print("Hand tracker running. Press 'q' to quit.")

    reset_gesture_start_time = None
    reset_gesture_fired = False

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

        # Prepare data for JSON
        left_hand_fingertips = None
        right_hand_fingertips = None
        right_hand_command = "none"
        left_hand_command = "none"

        # Draw the hand annotations on the image
        if results.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # Draw landmarks and connections for debugging
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                # Extract fingertip data
                fingertips = []
                for tip_id in [4, 8, 12, 16, 20]: # THUMB_TIP, INDEX_FINGER_TIP, etc.
                    lm = hand_landmarks.landmark[tip_id]
                    fingertips.append({"x": lm.x, "y": lm.y, "z": lm.z})

                # Check handedness
                handedness = results.multi_handedness[hand_idx].classification[0].label
                if handedness == "Left":
                    left_hand_fingertips = fingertips
                    # Check for reset gesture on the left hand, with a 1-second hold
                    if is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP):
                        if reset_gesture_start_time is None:
                            reset_gesture_start_time = time.time() # Start the timer

                        # Check if held for 1 second and hasn't already fired
                        if time.time() - reset_gesture_start_time >= 1.0 and not reset_gesture_fired:
                            left_hand_command = "reset_rotation"
                            reset_gesture_fired = True # Ensure it only fires once per hold
                    else:
                        # If the gesture is released, reset the timer and the fired state
                        reset_gesture_start_time = None
                        reset_gesture_fired = False
                else: # Right
                    right_hand_fingertips = fingertips
                    # Check for gestures on the right hand to determine the command
                    if is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP):
                        right_hand_command = "deform"
                    elif is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.MIDDLE_FINGER_TIP):
                        right_hand_command = "rotate_z"
                    elif is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.RING_FINGER_TIP):
                        right_hand_command = "rotate_y"
                    elif is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.PINKY_TIP):
                        right_hand_command = "rewind"

        # Prioritize left hand command (reset) over right hand commands
        command = left_hand_command if left_hand_command != "none" else right_hand_command

        # --- Structure and Write JSON ---
        output_data = {
            "command": command,
            "left_hand": {"fingertips": left_hand_fingertips} if left_hand_fingertips else None,
            "right_hand": {"fingertips": right_hand_fingertips} if right_hand_fingertips else None,
            "anchors": [],
            "rotation": 0.0,
            "rotation_speed": 0.0,
            "scale_axis": "XYZ",
            "remesh_type": "BLOCKS"
        }

        try:
            with open(FINGERTIPS_JSON_PATH, 'w') as f:
                json.dump(output_data, f, indent=2)
        except Exception as e:
            print(f"Error writing to JSON file: {e}")

        # --- Display Debugging View ---
        # Add a status text to the frame
        status_text = f"Command: {command}"
        color = (0, 255, 0) if command != "none" else (0, 0, 255)
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)
        
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