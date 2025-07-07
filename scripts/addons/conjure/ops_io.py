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
        state_update = {
            "generation_request": "new",
            "generation_mode": context.scene.conjure_settings.generation_mode
        }
        if not update_state_file(state_update):
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
        
        state_update = {
            "selection_request": option_index,
            "generation_mode": context.scene.conjure_settings.generation_mode
        }
        if not update_state_file(state_update):
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

        state_update = {
            "selection_request": option_index,
            "generation_mode": context.scene.conjure_settings.generation_mode
        }
        if not update_state_file(state_update):
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

        state_update = {
            "selection_request": option_index,
            "generation_mode": context.scene.conjure_settings.generation_mode
        }
        if not update_state_file(state_update):
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
        model_path = config.GENERATED_MODEL_DIR / "genMesh.glb"
        
        if not model_path.exists():
            self.report({'ERROR'}, f"Generated model not found at: {model_path}")
            return {'CANCELLED'}

        # --- 1. Manage the existing mesh and history ---
        scene = context.scene
        current_mesh = scene.objects.get(config.DEFORM_OBJ_NAME)
        
        if current_mesh:
            # --- Ensure HISTORY collection exists ---
            history_collection_name = "HISTORY"
            history_collection = bpy.data.collections.get(history_collection_name)
            if not history_collection:
                history_collection = bpy.data.collections.new(history_collection_name)
                scene.collection.children.link(history_collection)

            # --- Move current mesh to HISTORY collection ---
            current_collection = current_mesh.users_collection[0]
            current_collection.objects.unlink(current_mesh)
            history_collection.objects.link(current_mesh)
            
            # --- Rename and hide the old mesh ---
            # Find a unique name like Mesh.001, Mesh.002, etc.
            i = 1
            while f"{config.DEFORM_OBJ_NAME}.{i:03d}" in bpy.data.objects:
                i += 1
            new_name = f"{config.DEFORM_OBJ_NAME}.{i:03d}"
            current_mesh.name = new_name
            current_mesh.hide_set(True)
            current_mesh.hide_render = True
            print(f"Archived previous mesh as '{new_name}' in HISTORY collection.")

        # --- 2. Import the new GLB model ---
        try:
            bpy.ops.import_scene.gltf(filepath=str(model_path))
            print(f"Imported new model from {model_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import GLB: {e}")
            # Try to restore the previous mesh if import fails
            if current_mesh:
                current_mesh.hide_set(False)
                current_mesh.hide_render = False
                history_collection.objects.unlink(current_mesh)
                current_collection.objects.link(current_mesh)
                current_mesh.name = config.DEFORM_OBJ_NAME
            return {'CANCELLED'}

        # --- 3. Rename the newly imported object to be the active mesh ---
        # The imported object is usually the last one selected/added.
        if context.selected_objects:
            newly_imported_obj = context.selected_objects[0]
            # It might be an empty if the GLB has a scene root, find the mesh
            if newly_imported_obj.type == 'EMPTY' and newly_imported_obj.children:
                 mesh_child = next((child for child in newly_imported_obj.children if child.type == 'MESH'), None)
                 if mesh_child:
                    # Parent mesh to scene, remove empty
                    mesh_child.parent = None
                    bpy.data.objects.remove(newly_imported_obj)
                    newly_imported_obj = mesh_child

            newly_imported_obj.name = config.DEFORM_OBJ_NAME
            # Ensure it's in the main scene collection
            if newly_imported_obj.users_collection[0].name == "HISTORY":
                 history_collection.objects.unlink(newly_imported_obj)
                 scene.collection.objects.link(newly_imported_obj)

            self.report({'INFO'}, f"Successfully imported and set '{config.DEFORM_OBJ_NAME}' as the active mesh.")
        else:
            self.report({'WARNING'}, "Could not find newly imported object to rename.")

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