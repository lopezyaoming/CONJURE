# This script is responsible for camera capture and hand tracking.
# It uses OpenCV to get video from the webcam and Mediapipe to detect
# hand landmarks. The processed data, including fingertip coordinates and
# the active command state, is written to a JSON file for Blender to read.

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2
import json
import os
import math
import time
from pathlib import Path

# Global variable to store the latest gesture recognition result
latest_result = None

# --- Configuration ---
# This setup allows the script to be run from anywhere and still find the project root.
try:
    # Assumes the script is in launcher/
    PROJECT_ROOT = Path(__file__).parent.parent
except NameError:
    # Fallback for running from a different context or IDE
    PROJECT_ROOT = Path(os.path.abspath(''))

DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
FINGERTIPS_JSON_PATH = INPUT_DIR / "fingertips.json"
GESTURE_MODEL_PATH = DATA_DIR / "gesture_recognizer.task"

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
    
    thumb_tip = hand_landmarks[mp.solutions.hands.HandLandmark.THUMB_TIP]
    finger_tip = hand_landmarks[finger_tip_id]
    
    distance = get_distance(thumb_tip, finger_tip)
    
    return distance < TOUCH_THRESHOLD

# --- Result Callback ---
def print_result(result: vision.GestureRecognizerResult, output_image: mp.Image, timestamp_ms: int):
    """A callback function to receive and process the gesture recognition result."""
    global latest_result
    latest_result = result


# --- Main Application Logic ---
def run_hand_tracker():
    """Initializes camera, runs Mediapipe, and writes data to JSON."""
    
    # --- Recognizer Initialization ---
    base_options = python.BaseOptions(model_asset_path=str(GESTURE_MODEL_PATH))
    options = vision.GestureRecognizerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.LIVE_STREAM,
        num_hands=2,
        result_callback=print_result
    )
    recognizer = vision.GestureRecognizer.create_from_options(options)

    # Initialize Webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera.")
        return

    print("Hand tracker running. Press 'q' to quit.")

    frame_timestamp_ms = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Ignoring empty camera frame.")
            continue

        # Flip the frame horizontally for a later selfie-view display
        frame = cv2.flip(frame, 1)
        
        # Convert the BGR image to RGB and create a MediaPipe Image object
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # Increment timestamp
        frame_timestamp_ms = int(time.time() * 1000)
        
        # Process the frame and find hands
        recognizer.recognize_async(mp_image, frame_timestamp_ms)

        # --- Process the latest result ---
        left_hand_fingertips = None
        right_hand_fingertips = None
        command = "none"
        
        if latest_result:
            # Draw the hand annotations on the image
            if latest_result.hand_landmarks:
                for hand_idx, hand_landmarks in enumerate(latest_result.hand_landmarks):
                    # Draw landmarks for debugging
                    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
                    hand_landmarks_proto.landmark.extend([
                        landmark_pb2.NormalizedLandmark(x=lm.x, y=lm.y, z=lm.z) for lm in hand_landmarks
                    ])
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame,
                        hand_landmarks_proto,
                        mp.solutions.hands.HAND_CONNECTIONS
                    )

                    # Extract fingertip data
                    fingertips = []
                    # THUMB_TIP, INDEX_FINGER_TIP, etc.
                    for tip_id in [4, 8, 12, 16, 20]:
                        lm = hand_landmarks[tip_id]
                        fingertips.append({"x": lm.x, "y": lm.y, "z": lm.z})

                    # Check handedness
                    handedness = latest_result.handedness[hand_idx][0].category_name
                    if handedness == "Left":
                        left_hand_fingertips = fingertips
                    else: # Right
                        right_hand_fingertips = fingertips
                        
                        # Check for our existing gestures
                        if is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP):
                            command = "deform"
                        elif is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.MIDDLE_FINGER_TIP):
                            command = "rotate_z"
                        elif is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.RING_FINGER_TIP):
                            command = "rotate_y"
                        elif is_thumb_and_finger_touching(hand_landmarks, mp.solutions.hands.HandLandmark.PINKY_TIP):
                            command = "create_cube"
            
            # Check for classified gestures (like Closed_Fist)
            if latest_result.gestures:
                for hand_gestures in latest_result.gestures:
                    if hand_gestures: # Check if list is not empty
                        top_gesture = hand_gestures[0]
                        if top_gesture.category_name == "Closed_Fist":
                            command = "reset_view"

        # --- Structure and Write JSON ---
        output_data = {
            "command": command,
            "left_hand": {"fingertips": left_hand_fingertips} if left_hand_fingertips else None,
            "right_hand": {"fingertips": right_hand_fingertips} if right_hand_fingertips else None,
        }

        try:
            with open(FINGERTIPS_JSON_PATH, 'w') as f:
                json.dump(output_data, f, indent=2)
        except Exception as e:
            print(f"Error writing to JSON file: {e}")

        # --- Display Debugging View ---
        status_text = f"Command: {command}"
        color = (0, 255, 0) if command != "none" else (0, 0, 255)
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)
        
        cv2.imshow('CONJURE Hand Tracker', frame)

        # Check for 'q' key to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    recognizer.close()
    cap.release()
    cv2.destroyAllWindows()
    print("Hand tracker stopped.")

if __name__ == "__main__":
    run_hand_tracker() 