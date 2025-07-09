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
from agent_api import ConversationalAgent
from instruction_manager import InstructionManager
from launcher.voice_input_manager import VoiceInputManager


class ConjureApp:
    def __init__(self):
        print("Initializing CONJURE...")
        self.state_manager = StateManager()
        self.subprocess_manager = SubprocessManager()
        self.instruction_manager = InstructionManager(self.state_manager)
        self.project_root = Path(__file__).parent.parent.resolve()
        atexit.register(self.stop)
        
        # Initialize UI state
        self.state_manager.update_state({
            "ui": {
                "view": "DIALOG_ONLY",
                "dialogue": {
                    "user_transcript": "",
                    "agent_response": "Welcome to CONJURE.",
                    "status": "Say something..."
                },
                "selected_option": None
            }
        })

        # Initialize the agent
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("FATAL: OPENAI_API_KEY environment variable not set. Application will exit.")
            sys.exit(1) # Exit with a non-zero status code to indicate an error
        self.agent = ConversationalAgent(openai_api_key=api_key, instruction_manager=self.instruction_manager)
        
        # Initialize Voice Input Manager for STT
        self.voice_input_manager = VoiceInputManager(api_key=api_key)
        self.is_recording = False
        
        print("CONJURE Agent is initialized and listening...")

    def start(self):
        """Starts all the necessary components of the application."""
        print("CONJURE application starting...")
        self.state_manager.set_state("app_status", "running")

        self.subprocess_manager.start_gui()
        self.state_manager.set_state("gui_status", "running")

        self.subprocess_manager.start_hand_tracker()
        self.state_manager.set_state("hand_tracker_status", "running")
        
        print("Waiting for hand tracker to initialize...")
        time.sleep(3)

        self.subprocess_manager.start_blender()
        self.state_manager.set_state("blender_status", "running")

        print("\nCONJURE is now running. Close the Blender window or press Ctrl+C here to exit.")

    def check_for_requests(self):
        """Checks the state file for requests from Blender and triggers workflows."""
        state_data = self.state_manager.get_state()
        if not state_data:
            return

        # --- Handle Voice Input (STT) ---
        # This block handles the push-to-talk state from the hand tracker.
        user_is_speaking = state_data.get("user_is_speaking")

        if user_is_speaking is True and not self.is_recording:
            # Clear previous dialogue and set status to "Listening..."
            self.state_manager.set_ui_state({
                "dialogue": {
                    "user_transcript": "",
                    "agent_response": "",
                    "status": "Listening..."
                }
            })
            self.voice_input_manager.start_recording()
            self.is_recording = True
        
        elif user_is_speaking is False and self.is_recording:
            self.is_recording = False
            # Set status to "Thinking..." while we transcribe and process
            self.state_manager.set_ui_state({
                "dialogue": { "status": "Thinking..." }
            })
            # This is a blocking call that will transcribe the audio.
            transcribed_text = self.voice_input_manager.stop_recording_and_transcribe()
            
            # Important: Reset the speaking state to avoid re-triggering.
            # We set it to None instead of False.
            self.state_manager.update_state({"user_is_speaking": None})

            # If transcription was successful, send the text to the agent.
            if transcribed_text:
                print(f"\n>>> Sending to Agent: '{transcribed_text}'")
                # First, update the UI with the user's transcript
                self.state_manager.set_ui_state({
                    "dialogue": {
                        "user_transcript": transcribed_text,
                        "agent_response": "..."
                    }
                })
                # Now, set the command for the agent to process
                self.state_manager.update_state({
                    "command": "agent_user_message",
                    "text": transcribed_text
                })
            # After handling, we can return to process this on the next cycle.
            return 
        
        # --- Handle Agent and Blender Commands ---
        command = state_data.get("command")
        generation_mode = state_data.get("generation_mode", "standard")

        if command == "agent_user_message":
            print(f"\nUser message received: {state_data.get('text')}")
            # First, clear the user message command so it doesn't get processed again.
            self.state_manager.clear_command()
            # Now, get the agent's response. The agent may issue a new command
            # to Blender by updating the state file itself.
            agent_reply = self.agent.get_response(state_data.get('text'))
            
            # Check if the agent returned a valid spoken response.
            if agent_reply:
                # Update the UI with the agent's final response and reset status
                self.state_manager.set_ui_state({
                    "dialogue": { 
                        "agent_response": agent_reply,
                        "status": "Say something..."
                    }
                })
            else:
                # Inform the user that something went wrong.
                error_message = "I had a problem processing that. Please try again."
                self.state_manager.set_ui_state({
                    "dialogue": { 
                        "agent_response": error_message,
                        "status": "Say something..."
                    }
                })
        elif state_data.get("generation_request") == "new":
            self.handle_generation_request()
            self.state_manager.clear_specific_requests(["generation_request"])
        elif state_data.get("selection_request"):
            self.handle_selection_request(state_data, generation_mode)
            self.state_manager.clear_specific_requests(["selection_request", "selection_status"])

    def handle_generation_request(self):
        """Handles the request to generate initial concept options."""
        print("--- Detected Generation Request ---")
        
        source_render_path = self.project_root / "data" / "generated_images" / "gestureCamera" / "render.png"
        comfyui_input_path = config.COMFYUI_ROOT_PATH / "input" / "render.png"
        
        try:
            print(f"Copying {source_render_path} to {comfyui_input_path}...")
            shutil.copy(source_render_path, comfyui_input_path)
        except (IOError, FileNotFoundError) as e:
            print(f"ERROR: Could not copy render.png to ComfyUI input: {e}")
            return

        workflow_path = self.project_root / "comfyui" / "workflows" / "promptMaker.json"
        workflow = load_workflow(str(workflow_path))
        if not workflow:
            print("ERROR: Could not load promptMaker workflow.")
            return

        output_dir_abs = self.project_root / "data" / "generated_images" / "imageOPTIONS"
        output_dir_abs.mkdir(parents=True, exist_ok=True)
        
        prompt_path_abs = self.project_root / "data" / "generated_text" / "userPrompt.txt"
        
        modifications = {
            "134": {"file_path": str(prompt_path_abs)},
            "139": {"output_path": str(output_dir_abs)},
            "142": {"output_path": str(output_dir_abs)},
            "143": {"output_path": str(output_dir_abs)},
        }
        workflow = modify_workflow_paths(workflow, modifications)

        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print("--- promptMaker.json workflow completed successfully. ---")
            # Update the UI to show the options
            self.state_manager.set_ui_state({ "view": "SHOWING_OPTIONS" })
        else:
            print("--- ERROR: promptMaker.json workflow failed. ---")

        self.reset_state_file({"generation_request": "done"})

    def handle_selection_request(self, state_data, mode):
        """Handles the request to process a selected option and generate a 3D model."""
        option_index = state_data["selection_request"]
        print(f"--- Detected Selection Request for Option {option_index} (Mode: {mode.upper()}) ---")

        try:
            source_option_path = self.project_root / "data" / "generated_images" / "imageOPTIONS" / f"OP{option_index}.png"
            dest_selected_path = config.COMFYUI_ROOT_PATH / "input" / "selectedOption.png"
            print(f"Copying {source_option_path} to {dest_selected_path}...")
            shutil.copy(source_option_path, dest_selected_path)

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
        if mode == 'turbo':
            workflow_name = f"mv2mv{option_index}turbo.json"
            workflow_dir = self.project_root / "comfyui" / "workflows" / "turbo"
        else: # standard
            workflow_name = f"mv2mv{option_index}.json"
            workflow_dir = self.project_root / "comfyui" / "workflows" / "standard"

        workflow_path = workflow_dir / workflow_name
        
        workflow = load_workflow(str(workflow_path))
        if not workflow:
            print(f"ERROR: Could not load {workflow_path}.")
            self.reset_state_file({"selection_status": "failed"})
            return

        # Hide the options selector while processing
        self.state_manager.set_ui_state({ "view": "DIALOG_ONLY" })

        prompt_path_abs = self.project_root / "data" / "generated_text" / "userPrompt.txt"
        output_dir_abs = self.project_root / "data" / "generated_images" / "mvResults"
        output_dir_abs.mkdir(parents=True, exist_ok=True)
        
        print(f"Cleaning output directory: {output_dir_abs}")
        for f in output_dir_abs.glob('*.*'):
            try:
                if f.is_file():
                    f.unlink()
            except OSError as e:
                print(f"Error deleting file {f}: {e}")

        if mode == 'turbo':
            modifications = {
                "120": {"file_path": str(prompt_path_abs)}, 
                "165": {"output_path": str(output_dir_abs), "filename_prefix": "mv_1"},
                "187": {"output_path": str(output_dir_abs), "filename_prefix": "mv_3"},
                "164": {"output_path": str(output_dir_abs), "filename_prefix": "mv_4"},
            }
        else:
            modifications = {
                "120": {"file_path": str(prompt_path_abs)},
                "124": {"output_path": str(output_dir_abs)},
            }

        workflow = modify_workflow_paths(workflow, modifications)

        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print(f"--- {workflow_name} workflow completed successfully. ---")
            self.handle_3d_generation(mode)
        else:
            print(f"--- ERROR: {workflow_name} workflow failed. ---")
            self.reset_state_file({"selection_status": "failed"})

    def handle_3d_generation(self, mode):
        print(f"--- Detected 3D Generation Request (Mode: {mode.upper()}) ---")

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
            
        if mode == 'turbo':
            workflow_name = "mv23Dturbo.json"
            workflow_dir = self.project_root / "comfyui" / "workflows" / "turbo"
        else:
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

        modifications = {
            "13": {"filename_prefix": "CONJURE/copyMesh"}
        }
        workflow = modify_workflow_paths(workflow, modifications)

        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print(f"--- {workflow_name} workflow completed successfully. ---")
            
            try:
                output_dir = config.COMFYUI_CONJURE_OUTPUT_PATH
                output_dir.mkdir(parents=True, exist_ok=True)

                list_of_files = list(output_dir.glob('*.glb'))
                if not list_of_files:
                    raise FileNotFoundError("No .glb files found in the ComfyUI CONJURE output directory.")
                
                latest_file = max(list_of_files, key=lambda p: p.stat().st_mtime)
                print(f"Found latest generated model: {latest_file}")

                destination_dir = self.project_root / "data" / "generated_models"
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination_path = destination_dir / "genMesh.glb"

                shutil.copy(latest_file, destination_path)
                print(f"Copied model to {destination_path}")

            except Exception as e:
                print(f"ERROR: Could not copy generated model: {e}")
                self.reset_state_file({"3d_generation_request": "failed"})
                return

            self.reset_state_file({"import_request": "new"})
        else:
            print(f"--- ERROR: {workflow_name} workflow failed. ---")
            self.reset_state_file({"3d_generation_request": "failed"})

    def reset_state_file(self, data_to_update: dict):
        """
        Updates the state file with the given data, preserving existing keys.
        """
        self.state_manager.update_state(data_to_update)
        print("State file has been updated.")

    def run(self):
        """Main application loop. Monitors subprocesses and checks for requests."""
        try:
            while self.state_manager.get_state().get("app_status") == "running":
                self.check_for_requests()

                blender_process = self.subprocess_manager.processes.get('blender')
                if blender_process and blender_process.poll() is not None:
                    print("Blender window was closed. Shutting down.")
                    break

                time.sleep(1)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt detected. Shutting down CONJURE.")
        finally:
            self.stop()

    def stop(self):
        """Stops all running subprocesses."""
        print("CONJURE application stopping...")
        self.subprocess_manager.stop_all()

        # Clear the state file to prevent stale commands on restart
        print("Clearing application state...")
        # We preserve the state file, but clear volatile keys
        self.state_manager.update_state({
            "command": None,
            "text": None,
            "user_is_speaking": None,
            "generation_request": None,
            "selection_request": None,
            "import_request": None
        })

        print("CONJURE has stopped.")

if __name__ == "__main__":
    app = ConjureApp()
    app.start()
    app.run() 