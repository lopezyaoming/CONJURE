from state_manager import StateManager

class InstructionManager:
    """
    Receives instruction objects from the agent and triggers the corresponding
    backend logic by updating the state file.
    """
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.tool_map = {
            "spawn_primitive": self.spawn_primitive,
            "generate_concepts": self.generate_concepts,
            "select_concept": self.select_concept,
            "request_segmentation": self.request_segmentation,
            "isolate_segment": self.isolate_segment,
            "apply_material": self.apply_material,
            "export_final_model": self.export_final_model,
            "undo_last_action": self.undo_last_action,
            "import_last_model": self.import_last_model,
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

        if tool_name in self.tool_map:
            print(f"EXECUTING INSTRUCTION: {tool_name} with params: {params}")
            # Call the corresponding method
            self.tool_map[tool_name](params)
        else:
            print(f"Warning: Unknown tool '{tool_name}' requested by agent.")

    # --- Tool Implementations ---

    def spawn_primitive(self, params: dict):
        """
        Handles the 'spawn_primitive' instruction by updating the state file
        with a command for Blender.
        """
        primitive_type = params.get("primitive_type")
        if not primitive_type:
            print("Error: spawn_primitive called without 'primitive_type' parameter.")
            return
        
        # This command will be read by the main operator in Blender
        command_data = {
            "command": "spawn_primitive",
            "primitive_type": primitive_type
        }
        self.state_manager.update_state(command_data) 

    def generate_concepts(self, params: dict):
        """
        Handles the 'generate_concepts' instruction by setting the
        'generation_request' state for the main loop.
        """
        # The main loop in launcher/main.py will detect this state change.
        print("INFO: Setting state for concept generation request.")
        self.state_manager.set_state("generation_request", "new")

    def select_concept(self, params: dict):
        """
        Handles the 'select_concept' instruction by setting the 'selection_request'
        state, which is detected by the main loop in launcher/main.py.
        """
        option_id = params.get("option_id")
        if option_id not in [1, 2, 3]:
            print(f"Error: select_concept called with invalid 'option_id': {option_id}")
            return
        
        print(f"INFO: Setting state for concept selection: {option_id}")
        self.state_manager.set_state("selection_request", option_id)

    def request_segmentation(self, params: dict):
        """Handles the 'request_segmentation' instruction."""
        print("INFO: Setting command for 'request_segmentation'")
        self.state_manager.set_state("command", "request_segmentation")

    def isolate_segment(self, params: dict):
        """Handles the 'isolate_segment' instruction."""
        print("INFO: Setting command for 'isolate_segment'")
        self.state_manager.set_state("command", "isolate_segment")

    def apply_material(self, params: dict):
        """Handles the 'apply_material' instruction."""
        print("INFO: Setting command for 'apply_material'")
        command_data = {
            "command": "apply_material",
            "material_description": params.get("material_description"),
            "segment_id": params.get("segment_id") # Can be None
        }
        self.state_manager.update_state(command_data)

    def export_final_model(self, params: dict):
        """Handles the 'export_final_model' instruction."""
        print("INFO: Setting command for 'export_final_model'")
        self.state_manager.set_state("command", "export_final_model")

    def undo_last_action(self, params: dict):
        """Handles the 'undo_last_action' instruction."""
        print("INFO: Setting command for 'undo_last_action'")
        self.state_manager.set_state("command", "undo_last_action")

    def import_last_model(self, params: dict):
        """Handles the 'import_last_model' instruction."""
        print("INFO: Setting command for 'import_last_model'")
        self.state_manager.set_state("command", "import_last_model") 