"""
This module receives instruction objects from the agent and calls the appropriate
backend functions, primarily by updating the state file for Blender to react to.
"""
from launcher.state_manager import StateManager

def _handle_spawn_primitive(parameters: dict, state_manager: StateManager):
    """Handles the spawn_primitive instruction."""
    primitive_type = parameters.get("primitive_type")
    if not primitive_type:
        print("ERROR: spawn_primitive instruction received without primitive_type.")
        return

    print(f"Instruction: Spawning primitive '{primitive_type}'")
    state_manager.set_state("command", {
        "name": "spawn_primitive",
        "primitive_type": primitive_type
    })

# A router to call the correct handler based on the tool name
INSTRUCTION_ROUTER = {
    "spawn_primitive": _handle_spawn_primitive,
    # Future instructions will be added here
    # "request_segmentation": _handle_request_segmentation,
    # "generate_concepts": _handle_generate_concepts,
}

def handle_instruction(instruction: dict, state_manager: StateManager):
    """
    Receives an instruction object from the agent, finds the correct
    handler function, and executes it.
    """
    if not instruction:
        return

    tool_name = instruction.get("tool_name")
    parameters = instruction.get("parameters", {})

    handler = INSTRUCTION_ROUTER.get(tool_name)
    if handler:
        handler(parameters, state_manager)
    else:
        print(f"Warning: No handler found for instruction '{tool_name}'") 