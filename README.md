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

### 2. Blender Environment (`scripts/addons/conjure/`)
The central 3D modeling environment where all geometry is created, deformed, and rendered. All operations are handled via Blender's Python API (`bpy`). The scripts are structured as a standard Blender addon.

- **`scene.blend`**: The base `.blend` file (located in the separate `blender/` directory) containing the default lighting, cameras, and bounding box.
- **`__init__.py`**: The entry point that registers the addon with Blender.
- **`operator_main.py`**: The core script that runs inside Blender. It reads `fingertips.json` to map hand movements to mesh deformations and orchestrates all other operations.
- **`panel_ui.py`**: Defines the "CONJURE Control" panel in the 3D Viewport for starting and stopping the interaction.
- **`ops_io.py`**: Contains operators for the generative pipeline, such as rendering images and importing models. These are triggered by the UI panel.
- **`ops_...py`**: (Planned) Additional modules for specific operations like camera control, I/O, etc.

### 3. ComfyUI (`comfyui/`)
The generative backbone of the platform, responsible for a sophisticated, multi-stage pipeline that transforms a sculpted shape and a text prompt into a high-quality 3D model. It runs as a background server process, orchestrated by the Launcher.

- **`workflows/`**: Contains the JSON definitions for the generative pipeline. This is a multi-step process designed for iterative refinement, with parallel `standard` and `turbo` versions for most stages.
  - **`promptMaker.json`**: The first stage. It takes a single render from Blender and a text prompt, producing three distinct stylistic image concepts (`OP1.png`, `OP2.png`, `OP3.png`).
  - **`standard/mv2mv[1-3].json`**: The second stage (Standard Mode). Based on the user's choice of concept, one of these three workflows is run. Each takes the 6 multi-view renders of the current Blender mesh and the chosen concept image to generate a new, refined set of 6 multi-view images that match the target style.
  - **`turbo/mv2mv[1-3]turbo.json`**: The second stage (Turbo Mode). A faster version of the above.
  - **`standard/mv23D.json`**: The final stage (Standard Mode). It takes four of the refined multi-view images and uses a 2D-to-3D diffusion model to generate the final 3D mesh, which is then sent back to Blender.
  - **`turbo/mv23Dturbo.json`**: The final stage (Turbo Mode). A faster version that uses only three views.
- **`api_wrapper.py`**: A Python wrapper to communicate with the ComfyUI API, allowing the Launcher to trigger these workflows programmatically.
- **`panel_ui.py`**: Defines the "CONJURE Control" panel in the 3D Viewport for starting and stopping the interaction.
- **`ops_io.py`**: Contains operators for the generative pipeline, such as rendering images and importing models. These are triggered by the UI panel.
- **`...`**: Additional modules for specific operations.

### 4. UI Panel
The CONJURE UI Panel in Blender's 3D Viewport is your main command center for the generative pipeline.

- **Initiate/Finalize CONJURE**: Starts or stops the main gesture control operator.
- **Generation Mode**: A dropdown to switch between `Standard` and `Turbo` modes.
  - **Standard**: Slower, higher-quality generation.
  - **Turbo**: Much faster, lower-quality generation ideal for rapid prototyping.
- **Generate Concepts**: Triggers the first stage of the AI pipeline.
- **Select Option [1-3]**: Triggers the second stage with your chosen concept.
- **Import Last Model**: Manually triggers an import of the last generated 3D model.

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

1.  **Trigger**: You select one of the three images (e.g., `OP2.png`) via the UI panel.
2.  **Blender Renders**: The `MVCamera` in Blender renders your current mesh from 6 standard angles (`FRONT`, `BACK`, `LEFT`, etc.) and saves them to `data/generated_images/multiviewRender/`.
3.  **AI Processing**: The Launcher reads the `generation_mode` (`Standard` or `Turbo`) and triggers the corresponding workflow (e.g., `mv2mv2.json` or `mv2mv2turbo.json`), feeding it the 6 multi-view renders, your selected concept image, and the latest `userPrompt.txt`.
4.  **Output**: The workflow generates a new, refined set of multi-view images that are stylistically consistent with your selection. These are saved to `data/generated_images/mvResults/`.

### Stage 3: 3D Model Generation (`mv23D.json`)

The final stage builds the 3D model.

1.  **Trigger**: This stage runs automatically after Stage 2 completes successfully.
2.  **AI Processing**: The Launcher copies the necessary refined images from `mvResults/` into the ComfyUI input directory. It then sends them to the appropriate `mv23D` workflow (`standard` or `turbo`).
    - **Standard Mode** uses 4 views.
    - **Turbo Mode** uses 3 views for faster processing.
3.  **Output**: The workflow outputs a `.glb` file containing the new 3D mesh to a dedicated output folder inside ComfyUI.
4.  **Import to Blender**: The Launcher finds the new model, copies it to `data/generated_models/`, and signals Blender to import it into your scene, creating a history state of the previous mesh. You can now continue sculpting or start the process over again.

---

## How to Run

### Step 1: Initial Setup (Do this only once)

1.  **Start Blender:** Open the Blender application manually.
2.  **Add Scripts Path:**
    -   Go to `Edit > Preferences... > File Paths`.
    -   In the `Scripts` text box, click the `+ Add` button.
    -   Navigate to this project's root folder (the main `CONJURE` directory) and add the `scripts` folder within it. The path should look something like `C:\path\to\CONJURE\scripts`.
    -   Click the `Save Preferences` button in the bottom-left of the window.
3.  **Close Blender.**

### Step 2: Launch the System

Now, you can launch the entire application with a single command.

1.  **Open your terminal** (like PowerShell or Command Prompt).
2.  **Navigate to the project root folder:**
    ```bash
    cd path\to\CONJURE
    ```
3.  **Run the main launcher script:**
    ```bash
    python launcher/main.py
    ```

### Step 3: Interact

- The command will automatically start the hand tracker and launch a configured Blender instance with the addon enabled.
- Find the **CONJURE** panel in the 3D Viewport's UI shelf (press `N` if not visible) and click **"Initiate CONJURE"**.
- Your webcam feed will appear in a separate window. You can now control Blender with your gestures.
- To shut everything down, simply close the Blender window or press `Ctrl+C` in the terminal.

The UI Panel will also contain a "Generative Pipeline" section with buttons to manually trigger each stage of the ComfyUI workflow for debugging and direct control.
- **Generation Mode**: A dropdown allows you to select between `Standard` and `Turbo` modes before starting a generation. `Turbo` mode uses a faster, more lightweight set of workflows for rapid iteration.

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
│   └── scene.blend
│
├── scripts/
│   └── addons/
│       └── conjure/
│           ├── __init__.py
│           ├── operator_main.py
│           └── ... (other .py files)
│
├── comfyui/
│   ├── workflows/
│   │   ├── standard/
│   │   │   ├── mv2mv1.json
│   │   │   └── ...
│   │   ├── turbo/
│   │   │   ├── mv2mv1turbo.json
│   │   │   └── ...
│   │   ├── promptMaker.json
│   │   └── mv23D.json
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

