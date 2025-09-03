import bpy


class CONJURE_PT_ui_panel(bpy.types.Panel):
    bl_label = "CONJURE"
    bl_idname = "CONJURE_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CONJURE'

    def draw(self, context):
        """PHASE 3 SIMPLIFICATION: Essential controls only"""
        layout = self.layout
        wm = context.window_manager

        # Main CONJURE Control
        layout.label(text="CONJURE Control", icon='MODIFIER_DATA')
        layout.separator()
        
        # Check a custom property to see if the modal operator is running
        if wm.conjure_is_running:
            layout.operator("conjure.stop_operator", text="Stop CONJURE", icon='PAUSE')
            
            # Generation Status
            layout.separator()
            layout.label(text="Generation Status: Active", icon='CHECKMARK')
            
            # Show current prompt info
            try:
                from pathlib import Path
                prompt_path = Path(__file__).parent.parent.parent.parent / "data" / "generated_text" / "userPrompt.txt"
                if prompt_path.exists():
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        prompt_text = f.read().strip()
                    # Show just the first 50 characters
                    if "Shown in a three-quarter view" in prompt_text:
                        prompt_text = prompt_text.split("Shown in a three-quarter view")[0].strip()
                    prompt_display = prompt_text[:50] + "..." if len(prompt_text) > 50 else prompt_text
                    layout.label(text=f"Current Prompt:", icon='FILE_TEXT')
                    layout.label(text=prompt_display)
                else:
                    layout.label(text="Current Prompt: Not found", icon='ERROR')
            except:
                layout.label(text="Current Prompt: Error loading", icon='ERROR')
            
            # Active Brush Info
            layout.separator()
            try:
                import json
                from . import config
                with open(config.FINGERTIPS_JSON_PATH, 'r') as f:
                    fingertip_data = json.load(f)
                active_command = fingertip_data.get("active_command", "idle")
                layout.label(text=f"Active Brush: {active_command.upper()}", icon='BRUSH_DATA')
            except:
                layout.label(text="Active Brush: Unknown", icon='BRUSH_DATA')
            
            # Last Generation Time
            layout.separator()
            import time
            current_time = int(time.time())
            cycle_position = current_time % 30
            if cycle_position < 5:
                status_text = "Generating mesh..."
                status_icon = 'MODIFIER_ON'
            else:
                next_gen = 30 - cycle_position
                status_text = f"Next generation: {next_gen}s"
                status_icon = 'TIME'
            layout.label(text=status_text, icon=status_icon)
            
            # Essential Mesh Operations - RESTORED FOR CORE FUNCTIONALITY
            layout.separator()
            layout.label(text="Mesh Operations", icon='OUTLINER_OB_MESH')
            
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
                # Show gesture controls when in selection mode
                box = layout.box()
                box.label(text="🎯 SELECTION MODE ACTIVE", icon='INFO')
                box.label(text="👆 Point to highlight segment")
                box.label(text="🤏 Pinch thumb+index to confirm")
                box.label(text="✊ Close fist to fuse all segments")
                
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
                # Show normal mesh operations when not in selection mode
                box = layout.box()
                row = box.row()
                row.operator("conjure.fuse_mesh", text="Fuse Segments", icon='MOD_BOOLEAN')
                row.operator("conjure.segment_selection", text="Select Segment", icon='RESTRICT_SELECT_OFF')
            
        else:
            # The 'conjure.fingertip_operator' is the main operator defined below
            layout.operator("conjure.fingertip_operator", text="Initiate CONJURE", icon='PLAY')
            layout.separator()
            layout.label(text="Generation Status: Idle", icon='PAUSE')
            layout.label(text="Start CONJURE to begin continuous generation")


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