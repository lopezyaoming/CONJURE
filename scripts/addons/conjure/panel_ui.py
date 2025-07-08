import bpy


class CONJURE_PT_ui_panel(bpy.types.Panel):
    bl_label = "CONJURE"
    bl_idname = "CONJURE_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CONJURE'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Main Operator Button
        layout.operator("conjure.fingertip_operator", text="Start/Stop CONJURE")

        # IO Operators
        box = layout.box()
        box.label(text="Generation Controls")
        
        # Add the dropdown for generation mode
        box.prop(scene.conjure_settings, "generation_mode")

        box.operator("conjure.generate_concepts", text="Generate Concepts")
        
        row = box.row(align=True)
        row.operator("conjure.select_concept", text="Opt 1").option_id = 1
        row.operator("conjure.select_concept", text="Opt 2").option_id = 2
        row.operator("conjure.select_concept", text="Opt 3").option_id = 3
        
        box.operator("conjure.import_model", text="Import Last Model", icon='IMPORT')

        # Agent Controls
        agent_box = layout.box()
        agent_box.label(text="Agent Communication")
        agent_box.prop(scene, "conjure_user_input", text="")
        agent_box.operator("conjure.send_to_agent", text="Send")


class CONJURE_PG_settings(bpy.types.PropertyGroup):
    generation_mode: bpy.props.EnumProperty(
        name="Mode",
        description="Choose the generation model type.",
        items=[
            ('standard', "Standard", "Use the standard, high-quality models."),
            ('turbo', "Turbo", "Use the fast, real-time turbo models.")
        ],
        default='standard'
    ) 