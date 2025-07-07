"""
State manager for handling state.json events.
Manages the event loop and state transitions.
"""

import json
from pathlib import Path

class StateManager:
    """Handles reading, writing, and managing the application's state.json file."""
    def __init__(self, state_file='data/input/state.json'):
        self.state_file_path = Path(state_file)
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file_path.exists():
            with open(self.state_file_path, 'w') as f:
                json.dump({}, f)

    def get_state(self):
        """Loads the state from the JSON file, or creates it if it doesn't exist."""
        try:
            with open(self.state_file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def set_state(self, key, value):
        """Sets a value in the state and immediately saves it to disk."""
        state = self.get_state()
        state[key] = value
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=4)

    def clear_command(self):
        """Sets the 'command' and 'text' keys to null in the state file."""
        state = self.get_state()
        state['command'] = None
        state['text'] = None
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=4) 