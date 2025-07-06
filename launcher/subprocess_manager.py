"""
Subprocess manager for handling external processes.
Manages Blender, CGAL, and ComfyUI processes.
"""

import subprocess
import os
import sys
from pathlib import Path

# Import the configured path from the config file.
from config import BLENDER_EXECUTABLE_PATH

class SubprocessManager:
    def __init__(self):
        self.processes = {}
        # Assuming the project root is two levels up from this script's directory
        self.project_root = Path(__file__).parent.parent

    def start_hand_tracker(self):
        """Starts the hand_tracker.py script in a new process."""
        print("Starting hand tracker...")
        script_path = self.project_root / "launcher" / "hand_tracker.py"
        # Use sys.executable to ensure we run with the same Python interpreter
        # that is running the launcher itself.
        process = subprocess.Popen([sys.executable, str(script_path)])
        self.processes['hand_tracker'] = process
        print("Hand tracker process started.")

    def start_blender(self):
        """Starts Blender and enables the CONJURE addon."""
        print("Starting Blender...")
        blender_scene_dir = self.project_root / "blender"
        scene_path = blender_scene_dir / "scene.blend"

        # This command expression tells Blender to enable our addon,
        # which is assumed to be in a registered scripts path.
        # The addon's name is 'conjure', matching the folder name.
        enable_addon_expr = "import bpy; bpy.ops.preferences.addon_enable(module='conjure'); bpy.ops.wm.save_userpref()"

        command = [
            BLENDER_EXECUTABLE_PATH,
            str(scene_path),
            "--python-expr",
            enable_addon_expr
        ]
        # We run Blender with its UI visible for interaction, not in the background.
        process = subprocess.Popen(command)
        self.processes['blender'] = process
        print("Blender process started with CONJURE addon enabled.")

    def stop_all(self):
        """Terminates all managed subprocesses gracefully."""
        print("Stopping all subprocesses...")
        for name, process in self.processes.items():
            try:
                if process.poll() is None: # Check if the process is still running
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"Terminated '{name}'.")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"Forcefully killed '{name}' as it did not terminate gracefully.")
            except Exception as e:
                print(f"Error while stopping '{name}': {e}")
        self.processes.clear()
        print("All subprocesses stopped.") 