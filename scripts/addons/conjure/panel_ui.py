import bpy


class CONJURE_PT_ui_panel(bpy.types.Panel):
    bl_label = "CONJURE"
    bl_idname = "CONJURE_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CONJURE'

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # Check a custom property to see if the modal operator is running
        if wm.conjure_is_running:
            layout.operator("conjure.stop_operator", text="Finalize CONJURE", icon='PAUSE')
        else:
            # The 'conjure.fingertip_operator' is the main operator defined below
            layout.operator("conjure.fingertip_operator", text="Initiate CONJURE", icon='PLAY')

        # Add a separator
        layout.separator()

        # Add generation mode dropdown
        layout.label(text="Generation Mode:")
        layout.prop(context.scene, "generation_mode", text="")

        # Phase 1 - VIBE Modeling Section
        layout.separator()
        layout.label(text="Phase 1 - VIBE Modeling", icon='OUTLINER_OB_MESH')
        
        # FLUX Mesh Generation
        box = layout.box()
        box.label(text="FLUX Mesh Generation:")
        row = box.row()
        row.operator("conjure.render_gesture_camera", text="Render Camera", icon='CAMERA_DATA')
        row = box.row()
        row.operator("conjure.test_flux_pipeline", text="Test FLUX Pipeline", icon='MODIFIER_ON')
        
        # Mesh Processing
        box = layout.box()
        box.label(text="Mesh Processing:")
        
        # Check if we're in selection mode
        try:
            import json
            from . import config
            with open(config.STATE_JSON_PATH, 'r') as f:
                state_data = json.load(f)
            selection_mode = state_data.get("selection_mode", "inactive")
        except:
            selection_mode = "inactive"
        
        if selection_mode == "active":
            # Show exit button when in selection mode
            box.label(text="🎯 SELECTION MODE ACTIVE", icon='INFO')
            box.label(text="👆 Point at segment, 🤏 pinch to select")
            
            # Show currently selected segment
            segment_objects = [obj for obj in bpy.data.objects 
                              if obj.type == 'MESH' and obj.name.startswith('seg_')]
            
            selected_mat = bpy.data.materials.get("selected_material")
            current_selection = "None"
            
            for obj in segment_objects:
                if obj.data.materials and obj.data.materials[0] == selected_mat:
                    current_selection = obj.name
                    break
            
            if current_selection != "None":
                box.label(text=f"✅ Selected: {current_selection}", icon='CHECKMARK')
            else:
                box.label(text="⚪ No segment selected yet")
                
            box.operator("conjure.exit_selection_mode", text="Finalize Selection & Exit", icon='EXPORT')
        else:
            # Show normal controls when not in selection mode
            row = box.row()
            row.operator("conjure.fuse_mesh", text="Fuse Segments", icon='MOD_BOOLEAN')
            row.operator("conjure.segment_selection", text="Select Segment", icon='RESTRICT_SELECT_OFF')

        # Generative Pipeline Section (existing functionality)
        layout.separator()
        layout.label(text="Generative Pipeline", icon='MODIFIER_DATA')

        # Generate Concepts button
        layout.operator("conjure.generate_concepts", text="Generate Concepts", icon='TEXTURE')
        
        # Concept selection buttons
        row = layout.row(align=True)
        row.operator("conjure.select_concept_1", text="Option 1", icon='IMAGE_DATA')
        row.operator("conjure.select_concept_2", text="Option 2", icon='IMAGE_DATA') 
        row.operator("conjure.select_concept_3", text="Option 3", icon='IMAGE_DATA')

        # Import last model button
        layout.operator("conjure.import_model", text="Import Last Model", icon='IMPORT')


# Property groups
class CONJURE_PG_settings(bpy.types.PropertyGroup):
    generation_mode: bpy.props.EnumProperty(
        name="Generation Mode",
        description="Choose between Standard and Turbo generation modes",
        items=[
            ('standard', "Standard", "High-quality generation (slower)"),
            ('turbo', "Turbo", "Fast generation (lower quality)")
        ],
        default='standard'
    )

# Registration
classes = [
    CONJURE_PT_ui_panel,
    CONJURE_PG_settings,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register the generation mode property
    bpy.types.Scene.generation_mode = bpy.props.EnumProperty(
        name="Generation Mode",
        description="Choose between Standard and Turbo generation modes",
        items=[
            ('standard', "Standard", "High-quality generation (slower)"),
            ('turbo', "Turbo", "Fast generation (lower quality)")
        ],
        default='standard'
    ) 

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Clean up the property
    if hasattr(bpy.types.Scene, 'generation_mode'):
        del bpy.types.Scene.generation_mode 