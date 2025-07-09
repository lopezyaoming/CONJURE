from state_manager import StateManager

class InstructionManager:
    """
    Receives instruction objects from the agent and triggers the corresponding
    backend logic by updating the state file.
    """
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.tool_map = {
            "spawn_primitive": self._update_for_spawn_primitive,
            "change_brush": self._update_for_change_brush,
            "change_radius": self._update_for_change_radius,
            "import_last_model": self._update_for_import_model,
        }

    def execute_instruction(self, instruction: dict):
        """
        Public method to execute a given instruction.
        """
        if not instruction or "tool_name" not in instruction:
            # This can happen if the agent just wants to talk
            return

        tool_name = instruction.get("tool_name")
        params = instruction.get("parameters", {})

        print(f"Instruction Manager: Executing '{tool_name}' with params: {params}")

        if tool_name in self.tool_map:
            self.tool_map[tool_name](params)
        else:
            print(f"Warning: Unknown tool '{tool_name}' received from agent.")

    def _update_for_spawn_primitive(self, params: dict):
        """Updates the state file to trigger a primitive spawn in Blender."""
        command_to_write = {
            "tool_name": "spawn_primitive",
            "parameters": params
        }
        self.state_manager.update_state({"command": command_to_write})

    def _update_for_change_brush(self, params: dict):
        """Updates the state file to trigger a brush change in Blender."""
        command_to_write = {
            "tool_name": "change_brush",
            "parameters": params
        }
        self.state_manager.update_state({"command": command_to_write})

    def _update_for_change_radius(self, params: dict):
        """Updates the state file to trigger a radius change in Blender."""
        command_to_write = {
            "tool_name": "change_radius",
            "parameters": params
        }
        self.state_manager.update_state({"command": command_to_write})

    def _update_for_import_model(self, params: dict):
        """Updates the state file to trigger importing the last generated model."""
        command_to_write = {
            "tool_name": "import_last_model",
            "parameters": params # Pass empty params for now
        }
        self.state_manager.update_state({"command": command_to_write})