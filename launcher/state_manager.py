"""
State manager for handling state.json events.
Manages the event loop and state transitions.
"""

import json
from pathlib import Path

class StateManager:
    """Handles reading, writing, and managing the application's state.json file."""
    def __init__(self, state_file='state.json'):
        self.project_root = Path(__file__).parent.parent
        self.state_path = self.project_root / "data" / "input" / state_file
        self.state = {}
        self.load_state()

    def load_state(self):
        """Loads the state from the JSON file, or creates it if it doesn't exist."""
        try:
            with open(self.state_path, 'r') as f:
                self.state = json.load(f)
            print("State loaded from file.")
        except (FileNotFoundError, json.JSONDecodeError):
            print("No valid state file found. Creating a new one with default values.")
            self.state = self._get_default_state()
            self.save_state()

    def save_state(self):
        """Saves the current state dictionary to the JSON file."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, 'w') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            print(f"Error saving state to {self.state_path}: {e}")

    def get_state(self, key, default=None):
        """Gets a value from the state."""
        return self.state.get(key, default)

    def set_state(self, key, value):
        """Sets a value in the state and immediately saves it to disk."""
        self.state[key] = value
        self.save_state()

    def _get_default_state(self):
        """Returns the default initial state for the application."""
        return {
            "app_status": "initializing",
            "blender_status": "stopped",
            "hand_tracker_status": "stopped",
            "comfyui_status": "stopped",
            "current_phase": "modeling",
            "last_action": None
        } 