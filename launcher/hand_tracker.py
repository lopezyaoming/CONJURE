# This script is responsible for camera capture and hand tracking.
# It uses OpenCV to get video from the webcam and Mediapipe to detect
# hand landmarks. The processed data, including fingertip coordinates and
# the active command state, is written to a JSON file for Blender to read.

import cv2
import mediapipe as mp
import json
import os
import math
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

# Ensure the directory exists
os.makedirs(INPUT_DIR, exist_ok=True)

# --- Gesture Detection Helper ---
def is_thumb_index_touching(hand_landmarks):
    """Checks if the thumb and index fingertips are close together."""
    if not hand_landmarks:
        return False
    
    thumb_tip = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.THUMB_TIP]
    index_tip = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
    
    distance = math.sqrt(
        (thumb_tip.x - index_tip.x)**2 + 
        (thumb_tip.y - index_tip.y)**2 + 
        (thumb_tip.z - index_tip.z)**2
    )
    
    # The threshold (0.05) may need tuning depending on the camera and hand size
    return distance < 0.05

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

    deform_active = False

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
        
        # A simple approach: if any right hand is pinching, deform is active.
        deform_gesture_detected = False

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
                for tip_id in [4, 8, 12, 16, 20]:
                    lm = hand_landmarks.landmark[tip_id]
                    fingertips.append({"x": lm.x, "y": lm.y, "z": lm.z})

                # Check handedness
                handedness = results.multi_handedness[hand_idx].classification[0].label
                if handedness == "Left":
                    left_hand_fingertips = fingertips
                else: # Right
                    right_hand_fingertips = fingertips
                    # Check for deform gesture on the right hand
                    if is_thumb_index_touching(hand_landmarks):
                        deform_gesture_detected = True

        # Update deform state
        deform_active = deform_gesture_detected

        # --- Structure and Write JSON ---
        output_data = {
            "command": "deform" if deform_active else "none",
            "deform_active": deform_active,
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
        status_text = f"Deform Active: {deform_active}"
        color = (0, 255, 0) if deform_active else (0, 0, 255)
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