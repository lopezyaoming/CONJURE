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
    scene = bpy.context.scene
    camera = scene.objects.get(config.MV_CAMERA_NAME)

    if not camera:
        print(f"ERROR: Camera '{config.MV_CAMERA_NAME}' not found.")
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

def update_state_file(data):
    """Writes the given dictionary to the state.json file."""
    print(f"Updating state file at {config.STATE_JSON_PATH}...")
    try:
        with open(config.STATE_JSON_PATH, 'w') as f:
            json.dump(data, f, indent=4)
        print("State file updated for launcher.")
        return True
    except Exception as e:
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
        if not update_state_file({"generation_request": "new"}):
            self.report({'ERROR'}, "Failed to write to state file.")
            return {'CANCELLED'}

        return {'FINISHED'}


class CONJURE_OT_select_option_1(bpy.types.Operator):
    """Selects option 1 and signals the launcher."""
    bl_idname = "conjure.select_option_1"
    bl_label = "Select Concept Option 1"

    def execute(self, context):
        option_index = 1
        if not render_multiview():
            self.report({'ERROR'}, f"Failed to render multi-view for option {option_index}.")
            return {'CANCELLED'}
        
        if not update_state_file({"selection_request": option_index}):
            self.report({'ERROR'}, "Failed to write to state file.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Option {option_index} selected. Multi-view rendered and state updated.")
        return {'FINISHED'}


class CONJURE_OT_select_option_2(bpy.types.Operator):
    """Selects option 2 and signals the launcher."""
    bl_idname = "conjure.select_option_2"
    bl_label = "Select Concept Option 2"

    def execute(self, context):
        option_index = 2
        if not render_multiview():
            self.report({'ERROR'}, f"Failed to render multi-view for option {option_index}.")
            return {'CANCELLED'}

        if not update_state_file({"selection_request": option_index}):
            self.report({'ERROR'}, "Failed to write to state file.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Option {option_index} selected. Multi-view rendered and state updated.")
        return {'FINISHED'}


class CONJURE_OT_select_option_3(bpy.types.Operator):
    """Selects option 3 and signals the launcher."""
    bl_idname = "conjure.select_option_3"
    bl_label = "Select Concept Option 3"

    def execute(self, context):
        option_index = 3
        if not render_multiview():
            self.report({'ERROR'}, f"Failed to render multi-view for option {option_index}.")
            return {'CANCELLED'}

        if not update_state_file({"selection_request": option_index}):
            self.report({'ERROR'}, "Failed to write to state file.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Option {option_index} selected. Multi-view rendered and state updated.")
        return {'FINISHED'}


class CONJURE_OT_import_model(bpy.types.Operator):
    """
    Manually triggers the import of the last generated .glb model from the
    data folder.
    """
    bl_idname = "conjure.import_model"
    bl_label = "Import Last Generated Model"

    def execute(self, context):
        print(f"Operator '{self.bl_label}' executed.")
        # In the future, this will:
        # 1. Check for 'genMesh.glb' in the data/generated_models folder.
        # 2. Import it, replacing the current deformable mesh.
        self.report({'INFO'}, "Model import triggered (placeholder).")
        return {'FINISHED'}


classes = (
    CONJURE_OT_generate_concepts,
    CONJURE_OT_select_option_1,
    CONJURE_OT_select_option_2,
    CONJURE_OT_select_option_3,
    CONJURE_OT_import_model,
)

def register():
    """Registers the I/O operators."""
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    """Unregisters the I/O operators."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 