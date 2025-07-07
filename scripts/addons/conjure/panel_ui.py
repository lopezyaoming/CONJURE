import bpy
from . import ops_io


class CONJURE_PT_control_panel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport UI to control the script."""
    bl_label = "CONJURE Control"
    bl_idname = "CONJURE_PT_control_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CONJURE'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- Main Operator Controls ---
        box = layout.box()
        box.label(text="Main Controls")
        wm = context.window_manager
        if wm.conjure_is_running:
            box.operator("conjure.stop_operator", text="Finalize CONJURE", icon='PAUSE')
        else:
            box.operator("conjure.fingertip_operator", text="Initiate CONJURE", icon='PLAY')

        # --- Generative Pipeline Controls ---
        gen_box = layout.box()
        gen_box.label(text="Generative Pipeline")
        
        # Add the dropdown for generation mode
        gen_box.prop(scene.conjure_settings, "generation_mode")

        gen_box.operator("conjure.generate_concepts", text="Generate Concepts", icon='LIGHT')
        
        # --- Concept Selection ---
        split = gen_box.split(factor=0.33, align=True)
        col1 = split.column()
        col2 = split.column()
        col3 = split.column()
        
        col1.operator("conjure.select_option_1", text="Option 1")
        col2.operator("conjure.select_option_2", text="Option 2")
        col3.operator("conjure.select_option_3", text="Option 3")

        # --- Manual Import ---
        gen_box.operator("conjure.import_model", text="Import Last Model", icon='IMPORT')

class CONJURE_PG_settings(bpy.types.PropertyGroup):
    """Custom property group to hold CONJURE settings."""
    generation_mode: bpy.props.EnumProperty(
        name="Mode",
        description="Choose the generation pipeline mode",
        items=[
            ('standard', "Standard", "High-quality, slower generation"),
            ('turbo', "Turbo", "Lower-quality, faster generation for previews"),
        ],
        default='standard'
    )

def register():
    """Registers the UI panel and custom properties."""
    bpy.utils.register_class(CONJURE_PT_control_panel)
    bpy.utils.register_class(CONJURE_PG_settings)
    bpy.types.Scene.conjure_settings = bpy.props.PointerProperty(type=CONJURE_PG_settings)

def unregister():
    """Unregisters the UI panel and custom properties."""
    bpy.utils.unregister_class(CONJURE_PT_control_panel)
    bpy.utils.unregister_class(CONJURE_PG_settings)
    del bpy.types.Scene.conjure_settings 