import bpy


class CONJURE_PT_control_panel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport UI to control the script."""
    bl_label = "CONJURE Control"
    bl_idname = "CONJURE_PT_control_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CONJURE'

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # --- Main Interaction Controls ---
        box = layout.box()
        box.label(text="Interaction")
        # Check a custom property to see if the modal operator is running
        if hasattr(wm, 'conjure_is_running') and wm.conjure_is_running:
            box.operator("conjure.stop_operator", text="Finalize CONJURE", icon='PAUSE')
        else:
            # The 'conjure.fingertip_operator' is the main operator defined in operator_main.py
            box.operator("conjure.fingertip_operator", text="Initiate CONJURE", icon='PLAY')

        # --- Generative Pipeline Controls ---
        box = layout.box()
        box.label(text="Generative Pipeline (Debug)")

        # Stage 1
        box.operator("conjure.generate_concepts", icon='WORLD_DATA')

        # Stage 2
        row = box.row(align=True)
        row.operator("conjure.select_option_1", text="Select Opt 1", icon='IMAGE_DATA')
        row.operator("conjure.select_option_2", text="Select Opt 2", icon='IMAGE_DATA')
        row.operator("conjure.select_option_3", text="Select Opt 3", icon='IMAGE_DATA')
        
        # Stage 3
        box.operator("conjure.import_model", icon='FILE_NEW')


class CONJURE_OT_stop_operator(bpy.types.Operator):
    """A simple operator that sets a flag to signal the modal operator to stop."""
    bl_idname = "conjure.stop_operator"
    bl_label = "Stop Conjure Operator"

    def execute(self, context):
        # This property will be checked by the modal operator in its main loop
        context.window_manager.conjure_should_stop = True
        return {'FINISHED'}


classes = (
    CONJURE_PT_control_panel,
    CONJURE_OT_stop_operator,
)


def register():
    """Registers the UI panel and stop operator."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregisters the UI panel and stop operator."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 