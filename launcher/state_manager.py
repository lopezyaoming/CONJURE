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

    def update_state(self, data_to_update: dict):
        """Merges the given dictionary into the current state and saves it."""
        state = self.get_state()
        state.update(data_to_update)
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=4)

    def set_ui_state(self, ui_data_to_update: dict):
        """
        Safely updates nested keys within the 'ui' dictionary in the state.
        """
        state = self.get_state()
        # Ensure the 'ui' key exists and is a dictionary
        if 'ui' not in state or not isinstance(state['ui'], dict):
            state['ui'] = {}
        
        # Merge the new data into the ui sub-dictionary
        for key, value in ui_data_to_update.items():
            if key == "dialogue" and isinstance(value, dict):
                if 'dialogue' not in state['ui'] or not isinstance(state['ui']['dialogue'], dict):
                    state['ui']['dialogue'] = {}
                state['ui']['dialogue'].update(value)
            else:
                state['ui'][key] = value

        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=4)

    def clear_command(self):
        """Sets the 'command' and 'text' keys to null in the state file."""
        state = self.get_state()
        state['command'] = None
        state['text'] = None
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=4) 

    def clear_specific_requests(self, keys_to_clear: list):
        """Sets the specified keys to null in the state file."""
        state = self.get_state()
        for key in keys_to_clear:
            if key in state:
                state[key] = None
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=4) 