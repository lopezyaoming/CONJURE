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

# --- DEBUGGING: Print Python environment details ---
print("--- Python Environment ---")
print(f"Executable: {sys.executable}")
print("System Path:")
for p in sys.path:
    print(f"  - {p}")
print("--------------------------\n")
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
        
        # Determine the current generation mode, default to standard
        generation_mode = state_data.get("generation_mode", "standard")

        # Check for a request to generate concept options
        if state_data.get("generation_request") == "new":
            self.handle_generation_request()
        
        # Check for a request to process a selected option
        elif state_data.get("selection_request"):
            self.handle_selection_request(state_data, generation_mode)

    def handle_generation_request(self):
        """Handles the request to generate initial concept options."""
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

        output_dir_abs = self.project_root / "data" / "generated_images" / "imageOPTIONS"
        output_dir_abs.mkdir(parents=True, exist_ok=True)
        
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

        # --- 4. Reset State File ---
        self.reset_state_file({"generation_request": "done"})

    def handle_selection_request(self, state_data, mode):
        """Handles the request to process a selected option and generate a 3D model."""
        option_index = state_data["selection_request"]
        print(f"--- Detected Selection Request for Option {option_index} (Mode: {mode.upper()}) ---")

        # --- 1. Prepare all input files for ComfyUI ---
        try:
            # Copy the selected option image (e.g., OP1.png -> selectedOption.png)
            source_option_path = self.project_root / "data" / "generated_images" / "imageOPTIONS" / f"OP{option_index}.png"
            dest_selected_path = config.COMFYUI_ROOT_PATH / "input" / "selectedOption.png"
            print(f"Copying {source_option_path} to {dest_selected_path}...")
            shutil.copy(source_option_path, dest_selected_path)

            # Copy the 6 multi-view renders
            mv_render_dir = self.project_root / "data" / "generated_images" / "multiviewRender"
            for view_file in os.listdir(mv_render_dir):
                source_path = mv_render_dir / view_file
                dest_path = config.COMFYUI_ROOT_PATH / "input" / view_file
                print(f"Copying {source_path} to {dest_path}...")
                shutil.copy(source_path, dest_path)
        except (IOError, FileNotFoundError) as e:
            print(f"ERROR: Could not copy input files to ComfyUI: {e}")
            self.reset_state_file({"selection_status": "failed"})
            return
            
        # --- 2. Load and Modify mv2mv Workflow ---
        workflow_name = f"mv2mv{option_index}turbo.json" if mode == "turbo" else f"mv2mv{option_index}.json"
        workflow_dir = self.project_root / "comfyui" / "workflows" / mode
        workflow_path = workflow_dir / workflow_name
        
        workflow = load_workflow(str(workflow_path))
        if not workflow:
            print(f"ERROR: Could not load {workflow_path}.")
            self.reset_state_file({"selection_status": "failed"})
            return

        # Define absolute paths for workflow inputs/outputs
        prompt_path_abs = self.project_root / "data" / "generated_text" / "userPrompt.txt"
        output_dir_abs = self.project_root / "data" / "generated_images" / "mvResults"
        output_dir_abs.mkdir(parents=True, exist_ok=True)
        
        # --- Clean the output directory before generating new images ---
        print(f"Cleaning output directory: {output_dir_abs}")
        for f in output_dir_abs.glob('*.*'):
            try:
                if f.is_file():
                    f.unlink()
            except OSError as e:
                print(f"Error deleting file {f}: {e}")
        # -------------------------------------------------------------

        # Node IDs are from the mv2mv*.json files
        if mode == 'turbo':
            # The turbo workflows have different node IDs for saving images.
            modifications = {
                "120": {"file_path": str(prompt_path_abs)}, # Load Text File
                # Remap output filenames to match what mv23D expects (mv_1, mv_3, mv_4)
                "165": {"output_path": str(output_dir_abs), "filename_prefix": "mv_1"}, # FRONT SAVE
                "187": {"output_path": str(output_dir_abs), "filename_prefix": "mv_3"}, # LEFT SAVE
                "164": {"output_path": str(output_dir_abs), "filename_prefix": "mv_4"}, # BACK SAVE
            }
        else:
            # Standard workflows
            modifications = {
                "120": {"file_path": str(prompt_path_abs)},
                "124": {"output_path": str(output_dir_abs)},
            }

        workflow = modify_workflow_paths(workflow, modifications)

        # --- 3. Execute mv2mv Workflow ---
        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print(f"--- {workflow_name} workflow completed successfully. ---")
            # Immediately trigger the 3D generation workflow
            self.handle_3d_generation(mode)
        else:
            print(f"--- ERROR: {workflow_name} workflow failed. ---")
            # On failure, reset the selection request to avoid getting stuck in a loop
            self.reset_state_file({"selection_status": "failed"})

    def handle_3d_generation(self, mode):
        """
        Handles the request to generate a 3D model from the multi-view images.
        """
        print(f"--- Detected 3D Generation Request (Mode: {mode.upper()}) ---")

        # --- 1. Copy the latest multi-view results to ComfyUI's input directory ---
        print("Copying latest mvResults to ComfyUI input...")
        mv_results_dir = self.project_root / "data" / "generated_images" / "mvResults"
        try:
            for view_file in os.listdir(mv_results_dir):
                source_path = mv_results_dir / view_file
                dest_path = config.COMFYUI_ROOT_PATH / "input" / view_file
                print(f"  -> Copying {source_path} to {dest_path}")
                shutil.copy(source_path, dest_path)
        except (IOError, FileNotFoundError) as e:
            print(f"ERROR: Could not copy mvResult files to ComfyUI: {e}")
            self.reset_state_file({"3d_generation_request": "failed"})
            return
            
        # --- 2. Load Workflow ---
        if mode == 'turbo':
            workflow_name = "mv23Dturbo.json"
            workflow_dir = self.project_root / "comfyui" / "workflows" / "turbo"
        else: # standard
            workflow_name = "mv23D.json"
            workflow_dir = self.project_root / "comfyui" / "workflows"

        workflow_path = workflow_dir / workflow_name
        if not workflow_path.exists():
            print(f"--- ERROR: Workflow file not found at {workflow_path} ---")
            self.reset_state_file({"3d_generation_request": "failed"})
            return

        workflow = load_workflow(str(workflow_path))
        if not workflow:
            print(f"--- ERROR: Could not load workflow from {workflow_path} ---")
            self.reset_state_file({"3d_generation_request": "failed"})
            return

        # --- 3. Modify Workflow to Save to a Dedicated Folder ---
        # This ensures our generated files don't clutter the main ComfyUI output.
        # Node "13" is the Hy3DExportMesh node in both standard and turbo workflows.
        modifications = {
            "13": {"filename_prefix": "CONJURE/copyMesh"}
        }
        workflow = modify_workflow_paths(workflow, modifications)

        # --- 4. Execute mv23D Workflow ---
        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print(f"--- {workflow_name} workflow completed successfully. ---")
            
            # --- 5. Copy the generated model from ComfyUI's dedicated output to our project ---
            try:
                # Ensure the dedicated output directory exists before searching it
                output_dir = config.COMFYUI_CONJURE_OUTPUT_PATH
                output_dir.mkdir(parents=True, exist_ok=True)

                # Find the newest .glb file in the dedicated CONJURE output directory
                list_of_files = list(output_dir.glob('*.glb'))
                if not list_of_files:
                    raise FileNotFoundError("No .glb files found in the ComfyUI CONJURE output directory.")
                
                latest_file = max(list_of_files, key=lambda p: p.stat().st_mtime)
                print(f"Found latest generated model: {latest_file}")

                # Define the destination path in our project
                destination_dir = self.project_root / "data" / "generated_models"
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination_path = destination_dir / "genMesh.glb"

                # Copy the file
                shutil.copy(latest_file, destination_path)
                print(f"Copied model to {destination_path}")

            except Exception as e:
                print(f"ERROR: Could not copy generated model: {e}")
                self.reset_state_file({"3d_generation_request": "failed"})
                return

            # --- 6. Signal to Blender that a new model is ready for import ---
            self.reset_state_file({"import_request": "new"})
        else:
            print(f"--- ERROR: {workflow_name} workflow failed. ---")
            self.reset_state_file({"3d_generation_request": "failed"})

    def reset_state_file(self, data_to_write):
        """Clears the state file to prevent re-running requests."""
        state_file_path = self.project_root / "data" / "input" / "state.json"
        try:
            with open(state_file_path, 'w') as f:
                json.dump(data_to_write, f, indent=4)
            print("State file has been reset.")
        except IOError as e:
            print(f"ERROR: Could not reset state file: {e}")

    def run(self):
        """Main application loop. Monitors subprocesses and checks for requests."""
        try:
            while self.state_manager.get_state("app_status") == "running":
                # Check for requests from Blender
                self.check_for_requests()

                # Check if the Blender process has been closed by the user
                blender_process = self.subprocess_manager.processes.get('blender')
                
                # --- DEBUGGING: Print the status of the Blender process ---
                if blender_process:
                    poll_result = blender_process.poll()
                    # print(f"DEBUG: Blender process poll() result: {poll_result}") # Uncomment for verbose logging
                else:
                    print("DEBUG: Blender process not found in subprocess manager.")
                # -------------------------------------------------------------

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