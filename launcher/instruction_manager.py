import hashlib
import json
import time
from state_manager import StateManager

class InstructionManager:
    """
    PHASE 1 SIMPLIFICATION: Simplified instruction manager for continuous generation cycles.
    Only handles generate_flux_mesh - no complex logic, no deduplication, no conversation management.
    """
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        # Only one tool needed for the simplified workflow
        self.tool_map = {
            "generate_flux_mesh": self.generate_flux_mesh,
        }

    def execute_instruction(self, instruction: dict):
        """
        Execute instruction without complex deduplication - suitable for 30-second cycles.
        """
        if not instruction or "tool_name" not in instruction:
            print("⚠️ Invalid instruction - missing tool_name")
            return

        tool_name = instruction.get("tool_name")
        params = instruction.get("parameters", {})

        if tool_name in self.tool_map:
            print(f"🚀 EXECUTING: {tool_name} with params: {params}")
            self.tool_map[tool_name](params)
        else:
            print(f"❌ Unknown tool '{tool_name}' - only generate_flux_mesh is available")

    def generate_flux_mesh(self, params: dict):
        """
        The only tool needed for continuous generation cycles.
        Triggers the FLUX1.DEPTH -> PartPacker pipeline to generate a 3D mesh.
        """
        prompt = params.get("prompt")
        if not prompt:
            print("Error: generate_flux_mesh called without 'prompt' parameter.")
            return
        
        print(f"🎨 Starting FLUX mesh generation with prompt: {prompt[:100]}...")
        
        # Set state to trigger the FLUX pipeline
        flux_pipeline_data = {
            "flux_pipeline_request": "new",
            "flux_prompt": prompt,
            "flux_seed": params.get("seed", 0),
            "min_volume_threshold": params.get("min_volume_threshold", 0.001)
        }
        self.state_manager.update_state(flux_pipeline_data)
        print(f"✅ FLUX pipeline request set with seed: {params.get('seed', 0)}")