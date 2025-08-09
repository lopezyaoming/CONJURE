import hashlib
import json
import time
from launcher.state_manager import StateManager

class InstructionManager:
    """
    Receives instruction objects from the agent and triggers the corresponding
    backend logic by updating the state file.
    """
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self._executed_instructions = {}  # Hash -> timestamp for deduplication
        self._instruction_timeout = 15  # seconds before allowing re-execution
        
        # Define which commands should be deduplicated vs. allowed to repeat
        self._heavy_operations = {
            "generate_flux_mesh",  # 3D generation - expensive, should not repeat
            "import_and_process_mesh",  # File operations - should not repeat
            "spawn_primitive"  # Basic operations that shouldn't repeat rapidly
        }
        
        self._interactive_operations = {
            "segment_selection",  # Interactive mode - can be entered/exited multiple times
            "fuse_mesh",  # Quick operation that user might want to retry
            "select_concept"  # Selection operations that might need repeating
        }
        self.tool_map = {
            "spawn_primitive": self.spawn_primitive,
            # "generate_concepts": self.generate_concepts,  # COMMENTED OUT - Advanced operation not used
            "select_concept": self.select_concept,
            # "request_segmentation": self.request_segmentation,  # COMMENTED OUT - Advanced operation not used
            # "isolate_segment": self.isolate_segment,  # COMMENTED OUT - Advanced operation not used
            # "apply_material": self.apply_material,  # COMMENTED OUT - Advanced operation not used
            # "export_final_model": self.export_final_model,  # COMMENTED OUT - Advanced operation not used
            # "undo_last_action": self.undo_last_action,  # COMMENTED OUT - Advanced operation not used
            # "import_last_model": self.import_last_model,  # COMMENTED OUT - Advanced operation not used
            # New Phase 1 tools (ACTIVE)
            "generate_flux_mesh": self.generate_flux_mesh,
            "fuse_mesh": self.fuse_mesh,
            "segment_selection": self.segment_selection,
            # "mesh_import": self.mesh_import,  # COMMENTED OUT - Advanced operation not used
        }

    def _generate_instruction_hash(self, instruction: dict):
        """Generate a unique hash for an instruction to prevent duplicates."""
        # Create a deterministic hash based on tool name and parameters
        instruction_str = json.dumps(instruction, sort_keys=True)
        return hashlib.md5(instruction_str.encode()).hexdigest()
    
    def _is_duplicate_instruction(self, instruction: dict):
        """Check if this instruction was recently executed to prevent duplicates."""
        tool_name = instruction.get('tool_name', 'unknown')
        
        # Interactive operations are always allowed to repeat
        if tool_name in self._interactive_operations:
            print(f"🔄 INTERACTIVE COMMAND: {tool_name} allowed to repeat (interactive operation)")
            return False
        
        # Heavy operations should be deduplicated
        if tool_name in self._heavy_operations:
            instruction_hash = self._generate_instruction_hash(instruction)
            current_time = time.time()
            
            # Clean up old entries first
            expired_hashes = [
                h for h, timestamp in self._executed_instructions.items()
                if current_time - timestamp > self._instruction_timeout
            ]
            for h in expired_hashes:
                del self._executed_instructions[h]
            
            # Check if this instruction was recently executed
            if instruction_hash in self._executed_instructions:
                time_since_execution = current_time - self._executed_instructions[instruction_hash]
                print(f"🚫 DUPLICATE HEAVY OPERATION: {tool_name} was executed {time_since_execution:.1f}s ago")
                return True
            
            # Mark this instruction as executed
            self._executed_instructions[instruction_hash] = current_time
            print(f"✅ HEAVY OPERATION: {tool_name} allowed (first execution or timeout expired)")
            return False
        
        # Unknown operations - apply light deduplication (5 second cooldown)
        instruction_hash = self._generate_instruction_hash(instruction)
        current_time = time.time()
        
        if instruction_hash in self._executed_instructions:
            time_since_execution = current_time - self._executed_instructions[instruction_hash]
            if time_since_execution < 5:  # Shorter cooldown for unknown operations
                print(f"🚫 DUPLICATE UNKNOWN OPERATION: {tool_name} was executed {time_since_execution:.1f}s ago")
                return True
        
        self._executed_instructions[instruction_hash] = current_time
        print(f"✅ UNKNOWN OPERATION: {tool_name} allowed with light deduplication")
        return False

    def execute_instruction(self, instruction: dict):
        """
        Public method to execute a given instruction.
        """
        if not instruction or "tool_name" not in instruction:
            # This can happen if the agent just wants to talk
            return

        # Check for duplicate instructions
        if self._is_duplicate_instruction(instruction):
            print(f"⏭️ Skipping duplicate instruction: {instruction.get('tool_name')}")
            return

        tool_name = instruction.get("tool_name")
        params = instruction.get("parameters", {})

        if tool_name in self.tool_map:
            print(f"EXECUTING INSTRUCTION: {tool_name} with params: {params}")
            # Call the corresponding method
            self.tool_map[tool_name](params)
        else:
            print(f"Warning: Unknown tool '{tool_name}' requested by agent.")

    # --- Tool Implementations (ACTIVE TOOLS) ---

    def spawn_primitive(self, params: dict):
        """
        Handles the 'spawn_primitive' instruction by updating the state file
        with a command for Blender.
        """
        primitive_type = params.get("primitive_type")
        if not primitive_type:
            print("Error: spawn_primitive called without 'primitive_type' parameter.")
            return
        
        print(f"INFO: Spawning {primitive_type} primitive via state file...")
        
        # This command will be read by the main operator in Blender
        command_data = {
            "command": "spawn_primitive",
            "primitive_type": primitive_type
        }
        self.state_manager.update_state(command_data)
        print(f"✅ Command written to state file: spawn_primitive({primitive_type})")
        
        # Debug: Read back the state to confirm it was written
        try:
            current_state = self.state_manager.get_state()
            print(f"🔍 Current state after update: command='{current_state.get('command', 'None')}', primitive_type='{current_state.get('primitive_type', 'None')}'")
        except Exception as e:
            print(f"⚠️ Error reading state back: {e}")

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

    # --- ADVANCED OPERATIONS (COMMENTED OUT - NOT CURRENTLY USED) ---

    # def request_segmentation(self, params: dict):
    #     """Handles the 'request_segmentation' instruction."""
    #     print("INFO: Setting command for 'request_segmentation'")
    #     self.state_manager.set_state("command", "request_segmentation")

    # def isolate_segment(self, params: dict):
    #     """Handles the 'isolate_segment' instruction."""
    #     print("INFO: Setting command for 'isolate_segment'")
    #     self.state_manager.set_state("command", "isolate_segment")

    # def apply_material(self, params: dict):
    #     """Handles the 'apply_material' instruction."""
    #     print("INFO: Setting command for 'apply_material'")
    #     command_data = {
    #         "command": "apply_material",
    #         "material_description": params.get("material_description"),
    #         "segment_id": params.get("segment_id") # Can be None
    #     }
    #     self.state_manager.update_state(command_data)

    # def export_final_model(self, params: dict):
    #     """Handles the 'export_final_model' instruction."""
    #     print("INFO: Setting command for 'export_final_model'")
    #     self.state_manager.set_state("command", "export_final_model")

    # def undo_last_action(self, params: dict):
    #     """Handles the 'undo_last_action' instruction."""
    #     print("INFO: Setting command for 'undo_last_action'")
    #     self.state_manager.set_state("command", "undo_last_action")

    # def import_last_model(self, params: dict):
    #     """Handles the 'import_last_model' instruction."""
    #     print("INFO: Setting state for 'import_last_model'")
    #     self.state_manager.set_state("import_request", "new")

    # def mesh_import(self, params: dict):
    #     """
    #     Handles the 'mesh_import' instruction. Import and process a mesh file,
    #     typically from PartPacker results.
    #     """
    #     mesh_path = params.get("mesh_path")
    #     if not mesh_path:
    #         print("Error: mesh_import called without 'mesh_path' parameter.")
    #         return
        
    #     print(f"INFO: Setting command for mesh import: {mesh_path}")
    #     command_data = {
    #         "command": "import_and_process_mesh", 
    #         "mesh_path": mesh_path,
    #         "min_volume_threshold": params.get("min_volume_threshold", 0.001)
    #     }
    #     self.state_manager.update_state(command_data) 

    # --- New Phase 1 Tools (ACTIVE) ---

    def generate_flux_mesh(self, params: dict):
        """
        Handles the 'generate_flux_mesh' instruction. This triggers the 
        FLUX1.DEPTH -> PartPacker pipeline to generate a 3D mesh.
        """
        prompt = params.get("prompt")
        if not prompt:
            print("Error: generate_flux_mesh called without 'prompt' parameter.")
            return
        
        print(f"INFO: Starting FLUX mesh generation with prompt: {prompt[:100]}...")
        
        # Set state to trigger the FLUX mesh generation pipeline
        command_data = {
            "command": "generate_flux_mesh",
            "prompt": prompt,
            "seed": params.get("seed", 0),
            "min_volume_threshold": params.get("min_volume_threshold", 0.001)
        }
        self.state_manager.update_state(command_data)

    def fuse_mesh(self, params: dict):
        """
        Handles the 'fuse_mesh' instruction. Boolean union all mesh segments
        from largest to smallest into a single 'Mesh' object.
        """
        print("INFO: Setting command for 'fuse_mesh'")
        self.state_manager.set_state("command", "fuse_mesh")

    def segment_selection(self, params: dict):
        """
        Handles the 'segment_selection' instruction. Enables gesture-based
        segment selection mode where user can pick segments with index finger.
        """
        print("INFO: Setting command for 'segment_selection'")
        self.state_manager.set_state("command", "segment_selection") 