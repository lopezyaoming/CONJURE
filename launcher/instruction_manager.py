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
            "generate_concepts": self._update_for_generate_concepts,
            "select_concept": self._update_for_select_concept,
            "undo_last_action": self._update_for_undo_last_action,
            # --- Tools to be implemented ---
            "request_segmentation": self._not_yet_implemented,
            "isolate_segment": self._not_yet_implemented,
            "apply_material": self._not_yet_implemented,
            "export_final_model": self._not_yet_implemented,
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

    def _not_yet_implemented(self, params: dict):
        """Placeholder for tools that are defined but not yet implemented."""
        print(f"NOTE: Tool called with params '{params}', but it is not yet implemented.")
        pass

    def _update_for_select_concept(self, params: dict):
        """Updates the state file to trigger a concept selection."""
        option_id = params.get("option_id")
        if option_id not in [1, 2, 3]:
            print(f"Warning: Invalid option_id '{option_id}' received for select_concept.")
            return

        state = self.state_manager.get_state()
        generation_mode = state.get("generation_mode", "standard")

        update_data = {
            "selection_request": option_id,
            "generation_mode": generation_mode
        }
        self.state_manager.update_state(update_data)

    def _update_for_undo_last_action(self, params: dict):
        """Updates the state file to trigger an undo action in Blender."""
        command_to_write = {
            "tool_name": "rewind_backward",
            "parameters": {}
        }
        self.state_manager.update_state({"command": command_to_write})

    def _update_for_generate_concepts(self, params: dict):
        """
        Updates the state file to trigger concept generation.
        This assumes the agent has already written the prompt and Blender
        has already rendered the source image.
        """
        # Read the last-used generation mode from the state file.
        # This is set by the Blender UI when a generation is triggered.
        state = self.state_manager.get_state()
        generation_mode = state.get("generation_mode", "standard") # Default to standard

        update_data = {
            "generation_request": "new",
            "generation_mode": generation_mode
        }
        self.state_manager.update_state(update_data)

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