"""
State manager for handling state.json events.
Manages the event loop and state transitions.
"""

import json
import time
import threading
from pathlib import Path

class StateManager:
    """Handles reading, writing, and managing the application's state.json file."""
    def __init__(self, state_file='data/input/state.json'):
        self.state_file_path = Path(state_file)
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # Thread-safe locking for state file operations
        
        if not self.state_file_path.exists():
            self._write_state_safely({})

    def _write_state_safely(self, state_data, max_retries=3):
        """Thread-safe write with retry mechanism to prevent corruption."""
        with self._lock:
            for attempt in range(max_retries):
                try:
                    # Write to temporary file first, then atomically rename
                    temp_file = self.state_file_path.with_suffix('.tmp')
                    with open(temp_file, 'w') as f:
                        json.dump(state_data, f, indent=4)
                    
                    # Atomically replace the original file
                    temp_file.replace(self.state_file_path)
                    return
                except Exception as e:
                    print(f"🚨 STATE MANAGER: Write attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        print(f"❌ STATE MANAGER: Failed to write state after {max_retries} attempts")
                        raise
                    time.sleep(0.1)  # Brief delay before retry

    def _read_state_safely(self):
        """Thread-safe read with JSON validation and recovery."""
        with self._lock:
            try:
                with open(self.state_file_path, 'r') as f:
                    data = json.load(f)
                return data
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"🚨 STATE MANAGER: State file corrupted or missing: {e}")
                print("🔧 STATE MANAGER: Resetting to clean state...")
                clean_state = {
                    "app_status": "initializing",
                    "hand_tracker_status": "stopped", 
                    "blender_status": "stopped"
                }
                self._write_state_safely(clean_state)
                return clean_state

    def get_state(self):
        """Loads the state from the JSON file, or creates it if it doesn't exist."""
        return self._read_state_safely()

    def set_state(self, key, value):
        """Sets a value in the state and immediately saves it to disk."""
        # DEBUG: Track FLUX pipeline request changes
        if key == "flux_pipeline_request":
            print(f"🔧 STATE MANAGER: Setting {key} = {value}")
        
        state = self.get_state()
        state[key] = value
        self._write_state_safely(state)
            
        # DEBUG: Confirm FLUX pipeline request was written
        if key == "flux_pipeline_request":
            print(f"✅ STATE MANAGER: {key} written to file")

    def update_state(self, data_to_update: dict):
        """Merges the given dictionary into the current state and saves it."""
        # DEBUG: Track FLUX pipeline request changes
        if "flux_pipeline_request" in data_to_update:
            print(f"🔧 STATE MANAGER: Updating flux_pipeline_request = {data_to_update['flux_pipeline_request']}")
        
        # DEBUG: Track import_and_process_mesh command specifically
        if "command" in data_to_update and data_to_update["command"] == "import_and_process_mesh":
            print(f"🚨 STATE MANAGER: Writing CRITICAL command = import_and_process_mesh")
            print(f"🚨 STATE MANAGER: Full update data: {data_to_update}")
        
        state = self.get_state()
        state.update(data_to_update)
        
        # DEBUG: Show what we're about to write for import command
        if "command" in data_to_update and data_to_update["command"] == "import_and_process_mesh":
            print(f"🚨 STATE MANAGER: About to write state with command = '{state.get('command')}'")
        
        self._write_state_safely(state)
            
        # DEBUG: Confirm FLUX pipeline request was written
        if "flux_pipeline_request" in data_to_update:
            print(f"✅ STATE MANAGER: flux_pipeline_request updated in file")
            
        # DEBUG: Confirm import command was written
        if "command" in data_to_update and data_to_update["command"] == "import_and_process_mesh":
            print(f"🚨 STATE MANAGER: import_and_process_mesh command WRITTEN to file!")
            # Immediately read back to verify
            try:
                verify_state = self.get_state()  # Use safe read method
                print(f"🚨 STATE MANAGER: Verification read: command = '{verify_state.get('command')}'")
            except Exception as e:
                print(f"❌ STATE MANAGER: Failed to verify write: {e}")

    def clear_command(self):
        """Sets the 'command' and 'text' keys to null in the state file."""
        state = self.get_state()
        
        # DEBUG: Track when import command gets cleared
        if state.get('command') == 'import_and_process_mesh':
            print(f"🚨 STATE MANAGER: CLEARING import_and_process_mesh command!")
            import traceback
            print(f"🚨 STATE MANAGER: Clear called from:\n{traceback.format_stack()}")
        
        state['command'] = None
        state['text'] = None
        self._write_state_safely(state)

    def clear_specific_requests(self, keys_to_clear: list):
        """Sets the specified keys to null in the state file."""
        # DEBUG: Track FLUX pipeline request clearing
        if "flux_pipeline_request" in keys_to_clear:
            print(f"🧹 STATE MANAGER: Clearing flux_pipeline_request (along with {keys_to_clear})")
            
        # DEBUG: Track import command clearing
        if "command" in keys_to_clear:
            state = self.get_state()
            if state.get('command') == 'import_and_process_mesh':
                print(f"🚨 STATE MANAGER: CLEARING import_and_process_mesh via clear_specific_requests!")
                print(f"🚨 STATE MANAGER: Keys being cleared: {keys_to_clear}")
                import traceback
                print(f"🚨 STATE MANAGER: Clear called from:\n{traceback.format_stack()}")
        
        state = self.get_state()
        for key in keys_to_clear:
            if key in state:
                state[key] = None
        self._write_state_safely(state)
            
        # DEBUG: Confirm FLUX pipeline request was cleared
        if "flux_pipeline_request" in keys_to_clear:
            print(f"✅ STATE MANAGER: flux_pipeline_request cleared from file")

    def clear_all_requests(self):
        """
        Clears all request-related keys to prevent processing leftover requests
        from previous runs. Called on startup and shutdown.
        """
        print("🧹 STATE MANAGER: Clearing all pending requests...")
        
        # Define all request-related keys that should be cleared
        request_keys_to_clear = [
            "flux_pipeline_request",
            "generation_request", 
            "selection_request",
            "import_request",
            "command",
            "text",
            "selection_mode",
            "selected_segment",
            "flux_pipeline_status",
            "mesh_path",
            "primitive_type"
        ]
        
        state = self.get_state()
        cleared_keys = []
        
        for key in request_keys_to_clear:
            if key in state and state[key] is not None:
                cleared_keys.append(f"{key}: {state[key]}")
                state[key] = None
        
        # Keep essential status keys but reset them to safe values
        state["app_status"] = "initializing"
        state["hand_tracker_status"] = "stopped"
        state["blender_status"] = "stopped"
        
        self._write_state_safely(state)
            
        if cleared_keys:
            print(f"✅ Cleared leftover requests: {', '.join(cleared_keys)}")
        else:
            print("✅ No leftover requests found - state is clean")

    def reset_to_clean_state(self):
        """
        Resets state to a completely clean initial state.
        Used for startup initialization.
        """
        print("🔄 STATE MANAGER: Resetting to clean initial state...")
        
        clean_state = {
            "app_status": "initializing",
            "hand_tracker_status": "stopped", 
            "blender_status": "stopped",
            "flux_pipeline_request": None,
            "generation_request": None,
            "selection_request": None,
            "import_request": None,
            "command": None,
            "text": None,
            "selection_mode": "inactive",
            "selected_segment": None,
            "flux_pipeline_status": None,
            "mesh_path": None,
            "primitive_type": None,
            "flux_prompt": None,
            "flux_seed": None,
            "min_volume_threshold": None
        }
        
        self._write_state_safely(clean_state)
            
        print("✅ State reset to clean initial values") 