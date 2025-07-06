"""
Contains Blender operators related to Input/Output,
such as rendering images for the AI pipeline or importing models.
"""

import bpy

class CONJURE_OT_generate_concepts(bpy.types.Operator):
    """
    Renders the current view from the GestureCamera and signals the
    launcher to start the concept generation pipeline.
    """
    bl_idname = "conjure.generate_concepts"
    bl_label = "Generate Concept Options"

    def execute(self, context):
        print(f"Operator '{self.bl_label}' executed.")
        # In the future, this will:
        # 1. Render image from GestureCamera to the correct path.
        # 2. Update state.json to notify the launcher.
        self.report({'INFO'}, "Concept generation triggered (placeholder).")
        return {'FINISHED'}


class CONJURE_OT_select_option(bpy.types.Operator):
    """
    Based on the user's choice, this renders the 6 multi-view images
    and signals the launcher to start the multi-view refinement pipeline.
    """
    bl_idname = "conjure.select_option"
    bl_label = "Select Concept Option"

    # Using a standard class attribute assignment for properties is more robust
    # than the type annotation syntax, which can sometimes fail silently.
    option_index = bpy.props.IntProperty()

    def execute(self, context):
        print(f"Operator '{self.bl_label}' executed for option {self.option_index}.")
        # In the future, this will:
        # 1. Render 6 images from MVCamera.
        # 2. Update state.json with the selected option index.
        self.report({'INFO'}, f"Option {self.option_index} selected (placeholder).")
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
    CONJURE_OT_select_option,
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