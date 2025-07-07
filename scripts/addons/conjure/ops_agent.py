import bpy
import json
from pathlib import Path

class CONJURE_OT_send_to_agent(bpy.types.Operator):
    """Sends the user's text input to the CONJURE agent via state.json"""
    bl_idname = "conjure.send_to_agent"
    bl_label = "Send to Agent"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        user_input = context.scene.conjure_user_input
        if not user_input:
            self.report({'WARNING'}, "Input text cannot be empty.")
            return {'CANCELLED'}

        # Construct the path to state.json
        # The addon file is at /scripts/addons/conjure/, so we go up four levels to the project root.
        project_root = Path(__file__).parent.parent.parent.parent
        state_file_path = project_root / "data" / "input" / "state.json"
        
        if not state_file_path.parent.exists():
            self.report({'ERROR'}, "The data/input directory does not exist. Please check your project structure.")
            return {'CANCELLED'}

        if not state_file_path.exists():
            # In case the file doesn't exist, create it with the agent message
            state_data = {}
        else:
             # Read the existing state to not overwrite other keys
            with open(state_file_path, 'r') as f:
                try:
                    state_data = json.load(f)
                except json.JSONDecodeError:
                    state_data = {} # Overwrite if corrupt

        # Update the state with the agent message
        state_data['command'] = 'agent_user_message'
        state_data['text'] = user_input
        state_data['timestamp'] = bpy.context.scene.frame_current # Add a timestamp to ensure file update

        # Write the new state back to the file
        with open(state_file_path, 'w') as f:
            json.dump(state_data, f, indent=4)

        self.report({'INFO'}, f"Sent to agent: {user_input}")
        
        # Clear the input field
        context.scene.conjure_user_input = ""
        
        return {'FINISHED'} 