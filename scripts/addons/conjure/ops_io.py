"""
Contains Blender operators related to Input/Output,
such as rendering images for the AI pipeline or importing models.
"""

import bpy
import json
import os
from . import config

# --- HELPER FUNCTIONS ---

def render_multiview():
    """
    Renders 6 views from the multi-view camera and saves them to the
    configured directory. Returns True on success, False on failure.
    """
    print("\n--- DEBUG: render_multiview() called ---")
    scene = bpy.context.scene
    
    print(f"Searching for camera named: '{config.MV_CAMERA_NAME}'")
    all_object_names = [obj.name for obj in scene.objects]
    print(f"Objects in current scene: {all_object_names}")

    camera = scene.objects.get(config.MV_CAMERA_NAME)

    if not camera:
        print(f"ERROR: Camera '{config.MV_CAMERA_NAME}' not found in the current scene.")
        # Check for possible typos or case-sensitivity issues
        for name in all_object_names:
            if config.MV_CAMERA_NAME.lower() in name.lower():
                print(f"  -> Did you mean '{name}'? (Note: names are case-sensitive)")
        print("--- END DEBUG ---")
        return False

    print("Rendering multi-view images...")
    original_camera = scene.camera
    scene.camera = camera

    render = scene.render
    original_filepath = render.filepath
    original_file_format = render.image_settings.file_format

    os.makedirs(config.MV_RENDER_DIR, exist_ok=True)
    render.image_settings.file_format = 'PNG'

    # Define the 6 views: frame number and corresponding file name
    # Frame 0 is skipped as per the new layout.
    views = {
        1: "FRONT.png",
        2: "FRONT_RIGHT.png",
        3: "RIGHT.png",
        4: "BACK.png",
        5: "LEFT.png",
        6: "FRONT_LEFT.png"
    }

    for frame, filename in views.items():
        scene.frame_set(frame)
        render.filepath = str(config.MV_RENDER_DIR / filename)
        bpy.ops.render.render(write_still=True)
        print(f"  ...rendered {filename}")

    render.filepath = original_filepath
    render.image_settings.file_format = original_file_format
    scene.camera = original_camera
    print("Multi-view rendering complete.")
    return True

def update_state_file(data_to_update: dict):
    """
    Reads the existing state file, merges the new data, and writes it back.
    This prevents overwriting a key like 'app_status'.
    """
    print(f"Updating state file at {config.STATE_JSON_PATH} with: {data_to_update}")
    
    current_state = {}
    try:
        if os.path.exists(config.STATE_JSON_PATH):
            with open(config.STATE_JSON_PATH, 'r') as f:
                # Handle empty or corrupted JSON file
                content = f.read()
                if content:
                    current_state = json.loads(content)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Warning: Could not read or parse existing state file. A new one will be created. Error: {e}")
        current_state = {}

    # Update the state with the new data
    current_state.update(data_to_update)

    # Write the merged state back to the file
    try:
        with open(config.STATE_JSON_PATH, 'w') as f:
            json.dump(current_state, f, indent=4)
        print("State file updated successfully.")
        return True
    except IOError as e:
        print(f"ERROR: Failed to write to state file: {e}")
        return False

# --- OPERATORS ---

class CONJURE_OT_generate_concepts(bpy.types.Operator):
    """
    Renders the current view from the GestureCamera and signals the
    launcher to start the concept generation pipeline.
    """
    bl_idname = "conjure.generate_concepts"
    bl_label = "Generate Concept Options"

    def execute(self, context):
        scene = context.scene
        camera = scene.objects.get(config.GESTURE_CAMERA_NAME)

        if not camera:
            self.report({'ERROR'}, f"Camera '{config.GESTURE_CAMERA_NAME}' not found.")
            return {'CANCELLED'}

        # --- 1. Render the image ---
        print("Rendering concept image...")
        original_camera = scene.camera
        scene.camera = camera # Temporarily set the scene's active camera

        # Store original render settings to restore them later
        render = scene.render
        original_filepath = render.filepath
        original_file_format = render.image_settings.file_format

        # Ensure the output directory exists
        render_dir = config.GESTURE_RENDER_PATH.parent
        os.makedirs(render_dir, exist_ok=True)

        # Set new render settings
        render.filepath = str(config.GESTURE_RENDER_PATH)
        render.image_settings.file_format = 'PNG'

        # Trigger the render
        bpy.ops.render.render(write_still=True)
        self.report({'INFO'}, f"Image rendered to {render.filepath}")

        # Restore original render settings
        render.filepath = original_filepath
        render.image_settings.file_format = original_file_format
        scene.camera = original_camera

        # --- 2. Update the state file ---
        state_update = {
            "generation_request": "new",
            "generation_mode": context.scene.conjure_settings.generation_mode
        }
        if not update_state_file(state_update):
            self.report({'ERROR'}, "Failed to write to state file.")
            return {'CANCELLED'}

        return {'FINISHED'}


class CONJURE_OT_select_concept(bpy.types.Operator):
    """Selects a concept option, renders multi-view, and signals the launcher."""
    bl_idname = "conjure.select_concept"
    bl_label = "Select Concept Option"

    option_id: bpy.props.IntProperty()

    def execute(self, context):
        if not render_multiview():
            self.report({'ERROR'}, f"Failed to render multi-view for option {self.option_id}.")
            return {'CANCELLED'}
        
        state_update = {
            "selection_request": self.option_id,
            "generation_mode": context.scene.conjure_settings.generation_mode
        }
        if not update_state_file(state_update):
            self.report({'ERROR'}, "Failed to write to state file.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Option {self.option_id} selected. Multi-view rendered and state updated.")
        return {'FINISHED'}


class CONJURE_OT_import_model(bpy.types.Operator):
    """
    Manually triggers the import of the last generated .glb model from the
    data folder.
    """
    bl_idname = "conjure.import_model"
    bl_label = "Import Last Generated Model"

    def execute(self, context):
        self.report({'INFO'}, "Attempting to import last generated model...")
        
        # --- 1. Define Paths ---
        # The new location for the final mesh from the ComfyUI workflow
        model_path = config.GENERATED_MODEL_DIR / "genMesh.glb"
        
        if not model_path.exists():
            self.report({'ERROR'}, f"Model file not found at: {model_path}")
            return {'CANCELLED'}
            
        # --- 2. Create History Collection ---
        history_collection_name = "HISTORY"
        if history_collection_name not in bpy.data.collections:
            history_collection = bpy.data.collections.new(history_collection_name)
            bpy.context.scene.collection.children.link(history_collection)
        else:
            history_collection = bpy.data.collections[history_collection_name]

        # --- 3. Move Current Mesh to History ---
        current_mesh = context.scene.objects.get(config.DEFORM_OBJ_NAME)
        if current_mesh:
            # Find a new, unique name for the history object
            i = 1
            while f"{config.DEFORM_OBJ_NAME}.{i:03d}" in bpy.data.objects:
                i += 1
            new_name = f"{config.DEFORM_OBJ_NAME}.{i:03d}"
            
            # Unlink from scene collections and link to history
            for coll in current_mesh.users_collection:
                coll.objects.unlink(current_mesh)
            history_collection.objects.link(current_mesh)
            
            current_mesh.name = new_name
            current_mesh.hide_set(True) # Hide it from the viewport
            print(f"Moved '{config.DEFORM_OBJ_NAME}' to HISTORY as '{new_name}'.")

        # --- 4. Import the New Model ---
        try:
            bpy.ops.import_scene.gltf(filepath=str(model_path))
            imported_object = context.selected_objects[0] # The newly imported object should be selected
            imported_object.name = config.DEFORM_OBJ_NAME # Rename it to become the new active mesh
            self.report({'INFO'}, f"Successfully imported '{imported_object.name}' from {model_path}.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import GLB file: {e}")
            return {'CANCELLED'}
            
        # --- 5. Reset State File ---
        if not update_state_file({"import_request": "done"}):
            self.report({'WARNING'}, "Could not reset state file after import.")

        return {'FINISHED'} 