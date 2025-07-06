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
The generative backbone of the platform, responsible for a sophisticated, multi-stage pipeline that transforms a sculpted shape and a text prompt into a high-quality 3D model. It runs as a background server process, orchestrated by the Launcher.

- **`workflows/`**: Contains the JSON definitions for the generative pipeline. This is a multi-step process designed for iterative refinement.
  - **`promptMaker.json`**: The first stage. It takes a single render from Blender and a text prompt, producing three distinct stylistic image concepts (`OP1.png`, `OP2.png`, `OP3.png`).
  - **`mv2mv[1-3].json`**: The second stage. Based on the user's choice of concept, one of these three workflows is run. Each takes the 6 multi-view renders of the current Blender mesh and the chosen concept image to generate a new, refined set of 6 multi-view images that match the target style.
  - **`mv23D.json`**: The final stage. It takes four of the refined multi-view images and uses a 2D-to-3D diffusion model to generate the final 3D mesh, which is then sent back to Blender.
- **`api_wrapper.py`**: A Python wrapper to communicate with the ComfyUI API, allowing the Launcher to trigger these workflows programmatically.

---

## Generative Workflow: From Idea to 3D Model

The core generative process is a carefully choreographed sequence of events managed by the Launcher, involving Blender for rendering and ComfyUI for AI generation.

### Stage 1: Concept Generation (`promptMaker.json`)

This stage creates three visual directions for your design.

1.  **Trigger**: Once you're satisfied with your initial sculpted form, you signal the AI agent. The agent generates a descriptive prompt based on your conversation and saves it to `data/generated_text/userPrompt.txt`.
2.  **Blender Render**: Simultaneously, Blender renders the current view from the `GestureCamera` and saves it as `data/generated_images/gestureCamera/render.png`.
3.  **AI Processing**: The Launcher sends both the `render.png` and `userPrompt.txt` to the `promptMaker.json` workflow in ComfyUI.
4.  **Output**: The workflow produces three distinct image concepts, saved as `OP1.png`, `OP2.png`, and `OP3.png` in `data/generated_images/imageOPTIONS/`. These are then displayed to you in the GUI.

### Stage 2: Multi-View Refinement (`mv2mv[1-3].json`)

This stage refines your chosen concept into a full set of images ready for 3D generation.

1.  **Trigger**: You select one of the three images (e.g., `OP2.png`) via the GUI or voice command.
2.  **Blender Renders**: The `MVCamera` in Blender renders your current mesh from 6 standard angles (`FRONT`, `BACK`, `LEFT`, etc.) and saves them to `data/generated_images/multiviewRender/`.
3.  **AI Processing**: The Launcher triggers the corresponding workflow (e.g., `mv2mv2.json`), feeding it the 6 multi-view renders, your selected concept image, and the latest `userPrompt.txt`.
4.  **Output**: The workflow generates a new, refined set of 6 multi-view images that are stylistically consistent with your selection. These are saved as `mv_1.png` through `mv_6.png` in `data/generated_images/mvResults/`.

### Stage 3: 3D Model Generation (`mv23D.json`)

The final stage builds the 3D model.

1.  **Trigger**: This stage runs automatically after Stage 2 completes successfully.
2.  **AI Processing**: The Launcher takes four of the refined images (`mv_1.png`, `mv_3.png`, `mv_4.png`, `mv_5.png`) from `data/generated_images/mvResults/` and sends them to the `mv23D.json` workflow.
3.  **Output**: The workflow outputs a `.glb` file containing the new 3D mesh.
4.  **Import to Blender**: The Launcher detects the new file and automatically imports it back into your Blender scene, replacing the old mesh. You can now continue sculpting or start the process over again.

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

![Gesture Control Diagram](HAND%20INSTRUCTIONS.png)

CONJURE is designed to be controlled with intuitive hand gestures. All actions are performed relative to the camera's view, giving you a stable and predictable workspace.

### Right-Hand Gestures: Primary Actions

Your right hand is your primary tool for creating and shaping.

| Gesture                 | Action                                                                                                                             |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Thumb + Index Finger**  | **Deform Mesh:** Activates the currently selected sculpting brush (`PINCH`, `GRAB`, `SMOOTH`, etc.) to pull and push the mesh.      |
| **Thumb + Middle Finger** | **Orbit Camera:** Activates a direct manipulation orbit. Move your hand left/right and up/down to intuitively rotate your view.    |
| **Thumb + Ring Finger**   | **Cycle Brush:** Switches between the available sculpting brushes: `PINCH`, `GRAB`, `SMOOTH`, `INFLATE`, and `FLATTEN`.            |
| **Thumb + Pinky Finger**  | **Rewind (Continuous):** Rapidly rewinds your changes as long as the gesture is held.                                            |

### Left-Hand Gestures: Utility Actions

Your left hand is used for support and utility functions.

| Gesture                            | Action                                                                              |
| ---------------------------------- | ----------------------------------------------------------------------------------- |
| **Thumb + Index Finger (Hold)**    | **Reset View:** Snaps the camera to its home position and re-centers the mesh at 0,0,0. |
| **Thumb + Middle Finger**          | **Cycle Radius:** Switches the brush size between `SMALL`, `MEDIUM`, and `LARGE`.     |

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

