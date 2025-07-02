# CONJURE
MS Architectural Technologies thesis project
CONJURE is an AI-powered, gesture- and conversation-based platform that transforms ideas into production-ready 3D models—instantly and intuitively.
It bypasses traditional, technical modeling interfaces by allowing users to design using natural gestures and spoken instructions, bridging human intent with generative intelligence.
CONJURE core purpose
To make 3D modeling feel like intuitive expression
Key components
Overlay Executable: Is the main orchestrator between all the subcomponents and blender. It manages:
GUI: Transparent UI that displays image options, information, and The AI chat boxes, and loading screens. (maybe managed through QtCSS)
Mediapipe: Camera and mediapipe models that track hand movement and writes coordinates into fingertips.json
Communication: Communicate between Blender and ComfyUI. can ask both blender and comfyui to do stuff
API Agent: Listen, and play by hosting an ElevenLabs API call with an agent. 
Segmenter: CGAL integrated segmenter algorithm that takes meshes as input and segments them.
Blender: Blender is the core 3D environment in which all 3d stuff occurs in. bpy is used to 
map fingertip positions in the 3D space by reading fingertips.json
manage mesh deformation using fingertips
import/export models
render images on given cameras to given directories
ComfyUI: This will be used to generate the 3D models, 2D images, display text and other outputs that will be re-imported back to blender via Overlay. ComfyUI would be running on the background with different workflows in JSON format ready to be loaded.
Generates 3D models from Multiview
Generates image options from multiview

CONJURE/
├── launcher/
│   ├── main.py                   # Main controller (.exe entry point)
│   ├── gui.py                    # PyQt6 interface
│   ├── agent_api.py              # ElevenLabs conversational agent
│   ├── state_manager.py          # Event loop from state.json
│   ├── subprocess_manager.py     # Launches Blender, CGAL, ComfyUI
│   ├── config.py                 # Global constants and paths
│   └── utils.py                  # Shared helper functions

├── blender/
│   ├── scene.blend               # Base scene file with cameras, primitives, fingertip object
│   └── conjure_blender.py        # Single entry script run via --python

├── comfyui/
│   ├── workflows/
│   │   ├── promptMaker.json
│   │   └── mvto3D.json
│   └── api_wrapper.py

├── cgal/
│   ├── segment_mesh.exe
│   └── segmenter_wrapper.py

├── data/
│   ├── input/
│   │   ├── fingertips.json
│   │   ├── state.json
│   │   ├── gesture_render.png
│   │   ├── multiview/
│   │   │   └── front.png ...     # 6-view images
│   ├── output/
│   │   ├── generated.glb
│   │   ├── segmented.ply
│   │   └── renders/
│   └── assets/
│       ├── primitives/
│       └── materials/

├── logs/
│   └── system.log

└── README.md