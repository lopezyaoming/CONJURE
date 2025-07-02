# CONJURE
### MS Architectural Technologies Thesis Project

> CONJURE is an AI-powered, gesture- and conversation-based platform that transforms ideas into production-ready 3D models—instantly and intuitively. It bypasses traditional, technical modeling interfaces by allowing users to design using natural gestures and spoken instructions, bridging human intent with generative intelligence.

## Key Features
- **Intuitive Gesture Control:** Shape and manipulate 3D models with natural hand movements.
- **Conversational AI Agent:** Guide the design process with voice commands.
- **Generative Workflows:** Use multi-view AI to generate complex geometry and textures.
- **Real-Time Interaction:** See your changes reflected instantly in the Blender viewport.
- **Modular Architecture:** A flexible system integrating Blender, Mediapipe, and ComfyUI.

---

## Core Components

The CONJURE ecosystem is composed of several key modules that work in concert.

### 1. The Launcher (`launcher/`)
The main orchestrator, written in Python. It's the entry point of the application and is responsible for managing all other sub-components.

- **`main.py`**: The main controller that starts and coordinates all other processes.
- **`hand_tracker.py`**: Manages camera capture and uses **Mediapipe** to detect hand landmarks, writing the output to `fingertips.json`.
- **`gui.py`**: (Planned) A transparent **PyQt6** UI for displaying AI image options, chat interfaces, and status info.
- **`agent_api.py`**: (Planned) Hosts the conversational AI agent using **ElevenLabs**.
- **`state_manager.py`**: Manages the main application state via `state.json`.
- **`subprocess_manager.py`**: Launches and monitors the Blender and ComfyUI processes.
- **`config.py`** & **`utils.py`**: For shared configuration and helper functions.

### 2. Blender Environment (`blender/`)
The central 3D modeling environment where all geometry is created, deformed, and rendered. All operations are handled via Blender's Python API (`bpy`).

- **`scene.blend`**: The base `.blend` file containing the default lighting, `GestureCamera`, and bounding box.
- **`conjure_blender.py`**: The core script that runs inside Blender. It reads `fingertips.json` to map hand movements to mesh deformations and control the camera.

### 3. ComfyUI (`comfyui/`)
The generative backbone of the platform, responsible for image generation and 3D reconstruction. It runs as a background server process.

- **`workflows/`**: Contains the JSON definitions for generative tasks.
  - `promptMaker.json`: Generates image options from a single render.
  - `mvto3D.json`: Generates a 3D model from a set of 6 multi-view renders.
- **`api_wrapper.py`**: A Python wrapper to communicate with the ComfyUI API.

---

## Workflow & Usage

### Step 1: Calibration (Planned)

For the most precise and intuitive control, a one-time calibration process will map your unique hand movements to the screen space.

1.  **Run the Calibration Script:** A dedicated script (`launcher/calibrate.py`) will be provided.
2.  **Follow On-Screen Prompts:** The user will be asked to perform simple gestures, such as placing their hand in the center of the view or touching the corners of the interaction area.
3.  **Save Calibration Data:** The script will save the calculated center offset and interaction scale to a `calibration.json` file.
4.  **Automatic Loading:** The `conjure_blender.py` script will automatically detect and use this file to adjust the mapping, ensuring that your hand movements are perfectly translated to the 3D space.

### Step 2: Launch the System

1.  **Run the Hand Tracker:**
    ```bash
    python launcher/hand_tracker.py
    ```
    This will activate your webcam and start writing your hand movements to `data/input/fingertips.json`. A window will appear showing you the live tracking feed.

2.  **Run the Blender Script:**
    - Open Blender.
    - Go to the **Scripting** workspace.
    - Open the `blender/conjure_blender.py` file.
    - Click the "Run Script" button (play icon).

### Step 3: Interact

- With both scripts running, you can now interact with the default mesh in Blender.
- Find the **CONJURE** panel in the 3D Viewport's UI shelf (press `N` if not visible) and click **"Initiate CONJURE"**.

---

## User Manual: Gesture Controls

CONJURE is designed to be controlled with intuitive hand gestures. All actions are performed relative to the camera's view, giving you a stable and predictable workspace.

### Right-Hand Gestures: Primary Actions

Your right hand is your primary tool for creating and shaping.

| Gesture                 | Action                                                                                                                             |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Thumb + Index Finger**  | **Deform Mesh:** Activates sculpting mode. Only the thumb and index finger will pull and push the mesh, allowing for fine control. |
| **Thumb + Middle Finger** | **Orbit Camera (Z-axis):** Rotates your view horizontally around the object.                                                      |
| **Thumb + Ring Finger**   | **Orbit Camera (Y-axis):** Rotates your view vertically around the object.                                                         |
| **Thumb + Pinky Finger**  | **Create Cube:** Spawns a cube. The size is controlled by the distance between your thumb and pinky. Release to merge it.           |

### Left-Hand Gestures: Utility Actions

Your left hand is used for support and utility functions.

| Gesture                            | Action                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------- |
| **Thumb + Index Finger (Hold 1s)** | **Reset Camera:** Snaps the camera back to its original starting position.    |

---

## Project File Structure
```
CONJURE/
├── launcher/
│   ├── main.py
│   ├── hand_tracker.py
│   ├── gui.py
│   ├── agent_api.py
│   ├── state_manager.py
│   ├── subprocess_manager.py
│   ├── config.py
│   └── utils.py
│
├── blender/
│   ├── scene.blend
│   └── conjure_blender.py
│
├── comfyui/
│   ├── workflows/
│   │   ├── promptMaker.json
│   │   └── mvto3D.json
│   └── api_wrapper.py
│
├── data/
│   ├── input/
│   │   ├── fingertips.json
│   │   └── state.json
│   └── output/
│
└── README.md
```

