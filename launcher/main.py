"""
Main controller (.exe entry point)
This is the main entry point for the CONJURE application.
It orchestrates the various components like the hand tracker, Blender,
and eventually the AI agent and GUI.
"""
# --- Add project root to sys.path ---
# This is necessary to ensure that local modules like 'comfyui' can be found
# when this script is run as the main entry point.
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# -----------------------------------

import time
import atexit
import json
import uuid
from pathlib import Path
import shutil

from subprocess_manager import SubprocessManager
from state_manager import StateManager
from comfyui.api_wrapper import load_workflow, run_workflow, modify_workflow_paths
import launcher.config as config

class ConjureApp:
    def __init__(self):
        print("Initializing CONJURE...")
        self.subprocess_manager = SubprocessManager()
        self.state_manager = StateManager()
        # Get the project root directory (parent of the 'launcher' directory)
        self.project_root = Path(__file__).parent.parent.resolve()
        # Ensure processes are cleaned up on exit, even if the script crashes.
        atexit.register(self.stop)

    def start(self):
        """Starts all the necessary components of the application."""
        print("CONJURE application starting...")
        self.state_manager.set_state("app_status", "running")

        # Start background processes
        self.subprocess_manager.start_hand_tracker()
        self.state_manager.set_state("hand_tracker_status", "running")

        # A small delay to ensure the hand tracker has time to initialize
        # and create the initial fingertips.json file before Blender starts.
        print("Waiting for hand tracker to initialize...")
        time.sleep(3)

        self.subprocess_manager.start_blender()
        self.state_manager.set_state("blender_status", "running")

        print("\nCONJURE is now running. Close the Blender window or press Ctrl+C here to exit.")

    def check_for_requests(self):
        """Checks the state file for requests from Blender and triggers workflows."""
        state_file_path = self.project_root / "data" / "input" / "state.json"
        if not state_file_path.exists():
            return

        try:
            with open(state_file_path, 'r') as f:
                state_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is empty or currently being written, skip this check
            return
        
        # Check for a request to generate concept options
        if state_data.get("generation_request") == "new":
            print("--- Detected Generation Request ---")
            
            # --- 1. Copy the input image to ComfyUI's input directory ---
            source_render_path = self.project_root / "data" / "generated_images" / "gestureCamera" / "render.png"
            comfyui_input_path = config.COMFYUI_ROOT_PATH / "input" / "render.png"
            
            try:
                print(f"Copying {source_render_path} to {comfyui_input_path}...")
                shutil.copy(source_render_path, comfyui_input_path)
            except (IOError, FileNotFoundError) as e:
                print(f"ERROR: Could not copy render.png to ComfyUI input: {e}")
                return

            # --- 2. Load and Modify Workflow ---
            workflow_path = self.project_root / "comfyui" / "workflows" / "promptMaker.json"
            workflow = load_workflow(str(workflow_path))
            if not workflow:
                print("ERROR: Could not load promptMaker workflow.")
                return

            # Define the absolute output path for the generated images
            output_dir_abs = self.project_root / "data" / "generated_images" / "imageOPTIONS"
            output_dir_abs.mkdir(parents=True, exist_ok=True)
            
            # Create the modifications dictionary to set the absolute path
            # The node IDs ('139', '142', '143') are from our promptMaker.json
            modifications = {
                "139": {"output_path": str(output_dir_abs)},
                "142": {"output_path": str(output_dir_abs)},
                "143": {"output_path": str(output_dir_abs)},
            }

            workflow = modify_workflow_paths(workflow, modifications)

            # --- 3. Execute Workflow ---
            client_id = f"conjure_launcher_{uuid.uuid4()}"
            success = run_workflow(workflow, client_id)
            if success:
                print("--- promptMaker.json workflow completed successfully. ---")
            else:
                print("--- ERROR: promptMaker.json workflow failed. ---")

            # --- Reset State File ---
            # Clear the request to prevent re-running
            with open(state_file_path, 'w') as f:
                json.dump({"generation_request": "done"}, f, indent=4)
            print("State file has been reset.")

    def run(self):
        """Main application loop. Monitors subprocesses and checks for requests."""
        try:
            while self.state_manager.get_state("app_status") == "running":
                # Check for requests from Blender
                self.check_for_requests()

                # Check if the Blender process has been closed by the user
                blender_process = self.subprocess_manager.processes.get('blender')
                if blender_process and blender_process.poll() is not None:
                    print("Blender window was closed. Shutting down.")
                    break # Exit the loop to trigger the shutdown sequence

                time.sleep(1)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt detected. Shutting down CONJURE.")
        finally:
            self.stop()

    def stop(self):
        """Stops all components and gracefully exits."""
        # Check if already stopped to prevent multiple calls from atexit
        if self.state_manager.get_state("app_status") == "stopped":
            return
            
        print("CONJURE application stopping...")
        self.subprocess_manager.stop_all()
        self.state_manager.set_state("app_status", "stopped")
        self.state_manager.set_state("hand_tracker_status", "stopped")
        self.state_manager.set_state("blender_status", "stopped")
        print("CONJURE has stopped.")


if __name__ == "__main__":
    app = ConjureApp()
    app.start()
    app.run() 