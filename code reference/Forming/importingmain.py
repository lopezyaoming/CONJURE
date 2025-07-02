import bpy
import os
import logging
import time
import math
import mathutils
import subprocess
import sys
import json
import urllib.request
import random
import shutil
from bpy.props import StringProperty, EnumProperty, PointerProperty, IntProperty, FloatProperty, BoolProperty
from bpy.types import Panel, Operator, PropertyGroup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Base directories
BASE_DIR = r"C:\CODING\VIBE\VIBE_Forming"

# Render configuration
RENDER_OUTPUT_DIR = r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\blenderRender"
RENDER_CAMERA_NAME = "RenderCam"
RENDER_FRAMES = {
    0: "0.png",
    1: "front.png",
    2: "right.png",
    3: "back.png",
    4: "left.png"
}

# Generated mesh location
GENERATED_MESH_PATH = r"C:\CODING\VIBE\VIBE_Forming\output\generated\Models\current_mesh.glb"

# ComfyUI server configuration
COMFYUI_SERVER = "127.0.0.1:8188"
COMFYUI_OUTPUT_DIR = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\ComfyUI\output"

# Text prompt configuration
TEXT_OPTIONS_DIR = r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\textOptions"
PROMPT_FILE = "prompt.txt"
INPUT_TEXT_FILE = r"C:\CODING\VIBE\VIBE_Forming\input\input.txt"
OPTIONS_API_SCRIPT = r"C:\CODING\VIBE\VIBE_Forming\src\comfyworkflows\options_API.py"

# Communication files for integration with UI
RENDER_REQUEST_FILE = r"C:\CODING\VIBE\VIBE_Forming\render_request.txt"
RENDER_COMPLETE_FILE = r"C:\CODING\VIBE\VIBE_Forming\render_complete.txt"
IMPORT_REQUEST_FILE = r"C:\CODING\VIBE\VIBE_Forming\import_request.txt"
IMPORT_COMPLETE_FILE = r"C:\CODING\VIBE\VIBE_Forming\import_complete.txt"

# Custom request property group
class CustomRequestProperties(PropertyGroup):
    custom_prompt: StringProperty(
        name="Custom Prompt",
        description="Enter your custom request for generating 3D models",
        default="",
        maxlen=500
    )

# Text prompt property group
class PromptProperties(PropertyGroup):
    prompt_items = [
        ("A", "Prompt A", "Use text prompt A"),
        ("B", "Prompt B", "Use text prompt B"),
        ("C", "Prompt C", "Use text prompt C")
    ]
    
    # Selection for text prompt
    active_prompt: EnumProperty(
        name="Text Prompt",
        description="Select the text prompt to use for generation",
        items=prompt_items,
        default="A"
    )
    
    # Display the current prompt text
    show_prompt_text: BoolProperty(
        name="Show Prompt Text",
        description="Show the content of the selected prompt",
        default=False
    )

# Remesh stages property group
class RemeshProperties(PropertyGroup):
    # Toggle for enabling the remesh stages
    enable_remesh: BoolProperty(
        name="Enable Remesh",
        description="Enable staged remesh processing on mesh import",
        default=False
    )
    
    # Current remesh stage (1, 2, or 3)
    current_stage: IntProperty(
        name="Remesh Stage",
        description="Current remesh processing stage",
        default=1,
        min=1,
        max=3
    )
    
    # Remesh type
    remesh_types = [
        ("BLOCKS", "Blocks", "Apply blocks remesh"),
        ("SMOOTH", "Smooth", "Apply smooth remesh"),
        ("SHARP", "Sharp", "Apply sharp remesh")
    ]
    
    remesh_type: EnumProperty(
        name="Remesh Type",
        description="Type of remesh to apply",
        items=remesh_types,
        default="SHARP"
    )

# Add this new class for refreshing images
class IMAGE_OT_refresh(bpy.types.Operator):
    bl_idname = "image.refresh"
    bl_label = "Refresh Images"
    bl_description = "Reload all images from disk"
    
    def execute(self, context):
        logging.info("Manual image refresh requested...")
        
        # Use the common refresh function
        refresh_images_from_disk()
        
        self.report({'INFO'}, "Images refreshed")
        return {'FINISHED'}

class IMAGE_PT_display_panel(bpy.types.Panel):
    bl_label = "Generated Images"
    bl_idname = "IMAGE_PT_display_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE'

    def draw(self, context):
        layout = self.layout
        
        # Add refresh button at the top
        layout.operator("image.refresh", text="Refresh Images", icon='FILE_REFRESH')
        
        # Add custom request section
        box = layout.box()
        box.label(text="Custom Request:", icon='TEXT')
        box.prop(context.scene.custom_request_properties, "custom_prompt", text="")
        box.operator("request.submit", text="Submit Request", icon='PLAY')
        
        # Add a separator after the refresh button
        layout.separator(factor=0.5)
        
        # Image directory
        image_dir = "C:/CODING/VIBE/VIBE_Forming/input/options"
        image_names = ['A.png', 'B.png', 'C.png']

        # Create a horizontal layout
        row = layout.row()
        
        # Load and display images side by side
        for img_name in image_names:
            # Create a column for each image
            col = row.column(align=True)  # Align items in column
            col.scale_x = 1.0
            col.scale_y = 1.0
            
            # Get or load image
            img = bpy.data.images.get(img_name)
            if not img:
                try:
                    img_path = os.path.join(image_dir, img_name)
                    if os.path.exists(img_path):
                        img = bpy.data.images.load(img_path)
                        img.name = img_name
                        if not img.packed_file:
                            img.pack()
                except Exception as e:
                    col.label(text=f"Error: {str(e)}")
                    continue
            
            if img:
                # Ensure preview is generated
                if img.preview is None:
                    img.preview_ensure()
                    
                if img.preview and img.preview.icon_id:
                    # Show the image preview
                    col.template_icon(icon_value=img.preview.icon_id, scale=8.0)
                    
                    # Add a "Select" button below each image
                    option_letter = img_name.split('.')[0]  # A, B, or C
                    op = col.operator("option.select", text=f"Select {option_letter}")
                    op.option = option_letter
        
        # Add a separator
        layout.separator()
        
        # Show currently selected text prompt
        props = context.scene.prompt_properties
        box = layout.box()
        box.label(text="Current Text Prompt:", icon='TEXT')
        box.label(text=f"Prompt {props.active_prompt}")
        
        # Add toggle for showing prompt content
        box.prop(props, "show_prompt_text", text="Show Prompt Content")
        
        # Show the prompt content if toggle is on
        if props.show_prompt_text:
            prompt_text = get_prompt_content(f"{props.active_prompt}_0001.txt")
            if prompt_text:
                text_box = box.box()
                # Show first 100 characters with ellipsis
                if len(prompt_text) > 100:
                    display_text = prompt_text[:100] + "..."
                else:
                    display_text = prompt_text
                text_box.label(text=display_text)
        
        # Add a separator for generation buttons
        layout.separator()
        
        # Generation and terminate buttons
        row = layout.row(align=True)
        row.operator("object.generate_iteration", text="Generate New Iteration", icon='CAMERA_DATA')
        
        # Add remesh toggle button showing the current stage
        props = context.scene.remesh_properties
        stage_text = f"Remesh ({props.current_stage})"
        remesh_button = row.operator("object.toggle_remesh", text=stage_text, icon='OUTLINER_OB_MESH')
        
        # Show the current state with different button colors
        if props.enable_remesh:
            row.alert = True  # Make the button red when enabled
        
        # Add a separator before terminate button
        layout.separator(factor=0.5)
        layout.operator("option.terminate_script", text="Terminate Script", icon='X')

# Remesh settings panel
class REMESH_PT_settings_panel(bpy.types.Panel):
    bl_label = "Remesh Settings"
    bl_idname = "REMESH_PT_settings_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE'
    bl_options = {'DEFAULT_CLOSED'}  # Panel starts collapsed
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.remesh_properties
        
        # Remesh enable toggle
        layout.prop(props, "enable_remesh", text="Enable Staged Remesh")
        
        # Current stage display
        box = layout.box()
        box.label(text=f"Current Stage: {props.current_stage}")
        
        if props.current_stage == 1:
            box.label(text="Octree Depth: 3")
        elif props.current_stage == 2:
            box.label(text="Octree Depth: 5")
        else:  # stage 3
            box.label(text="No remesh applied")
        
        # Remesh type selection
        layout.prop(props, "remesh_type", text="Remesh Type")
        
        # Help text
        help_box = layout.box()
        help_box.label(text="How It Works:", icon='INFO')
        help_box.label(text="Stage 1: Octree depth 3")
        help_box.label(text="Stage 2: Octree depth 5")
        help_box.label(text="Stage 3: No remesh applied")
        help_box.label(text="Each import advances the stage")

class OPTION_OT_select(bpy.types.Operator):
    bl_idname = "option.select"
    bl_label = "Select Option"
    bl_description = "Select this design option and apply corresponding text prompt"
    
    option: StringProperty()
    
    def execute(self, context):
        logging.info(f"Selected option: {self.option}")
        
        # Save selection to output directory
        output_dir = "C:/CODING/VIBE/VIBE_Forming/output"
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, "selected_option.txt"), "w") as f:
            f.write(f"Selected Option: {self.option}\n")
            f.write(f"Timestamp: {time.time()}\n")
        
        # Store the option value in a variable for the closure
        option_value = self.option
        
        # Also apply the corresponding text prompt
        success = copy_text_file(f"{option_value}_0001.txt", PROMPT_FILE)
        
        if success:
            logging.info(f"Applied text prompt {option_value}")
        else:
            logging.error(f"Failed to apply text prompt {option_value}")
        
        # Update the active prompt in the UI to reflect the selection
        context.scene.prompt_properties.active_prompt = option_value
        
        # Show a message box using a closure to capture the option value
        def draw(popup, context):
            popup.layout.label(text=f"Selected Option {option_value}")
            popup.layout.label(text="Result saved to output directory")
            popup.layout.label(text=f"Text prompt {option_value} applied")
            
        bpy.context.window_manager.popup_menu(draw, title="Selection Confirmed", icon='INFO')
        
        return {'FINISHED'}

class OPTION_OT_terminate_script(bpy.types.Operator):
    bl_idname = "option.terminate_script"
    bl_label = "Terminate Script"
    bl_description = "Unregister the addon and stop the script"
    
    def execute(self, context):
        logging.info("Terminating script...")
        unregister()
        self.report({'INFO'}, "Script terminated")
        return {'FINISHED'}

# Generate new iteration operator
class OBJECT_OT_generate_iteration(bpy.types.Operator):
    bl_idname = "object.generate_iteration"
    bl_label = "Generate New Iteration"
    bl_description = "Render views, process through ComfyUI, and import the resulting mesh"
    
    def execute(self, context):
        # Check if there's an active selection first
        active_obj = context.active_object
        if not active_obj or active_obj.type != 'MESH':
            # Instead of cancelling, just log a warning and continue
            self.report({'WARNING'}, "No active mesh found. Proceeding without active mesh reference.")
            logging.warning("No active mesh found. Proceeding without active mesh reference.")
            # Continue with the operation instead of returning CANCELLED
            
        # Step 1: Render multi-view images
        logging.info("Starting new iteration generation...")
        render_success = render_multiview()
        if not render_success:
            self.report({'ERROR'}, "Failed to render multi-views")
            return {'CANCELLED'}
            
        # Step 2: Process renders through ComfyUI
        api_success = run_comfyui_workflow()
        if not api_success:
            self.report({'ERROR'}, "Failed to process through ComfyUI")
            return {'CANCELLED'}
            
        # Step 3: Import the generated mesh
        import_success = import_generated_mesh()
        if not import_success:
            self.report({'ERROR'}, "Failed to import generated mesh")
            return {'CANCELLED'}
            
        self.report({'INFO'}, "Successfully generated new iteration")
        return {'FINISHED'}

# Remesh toggle operator
class OBJECT_OT_toggle_remesh(bpy.types.Operator):
    bl_idname = "object.toggle_remesh"
    bl_label = "Toggle Remesh"
    bl_description = "Toggle the staged remesh functionality"
    
    def execute(self, context):
        # Toggle the enable_remesh property
        props = context.scene.remesh_properties
        props.enable_remesh = not props.enable_remesh
        
        status = "enabled" if props.enable_remesh else "disabled"
        stage = props.current_stage
        
        # Show a message about the current status
        self.report({'INFO'}, f"Remesh {status}. Will be applied at stage {stage} on next import")
        logging.info(f"Remesh {status}. Will be applied at stage {stage} on next import")
        
        # Update the remesh state file for UI
        try:
            remesh_state_path = os.path.join(os.path.dirname(bpy.data.filepath), "remesh_state.txt")
            with open(remesh_state_path, "w") as f:
                f.write(f"enabled={str(props.enable_remesh).lower()}\n")
                f.write(f"stage={props.current_stage}\n")
                f.write(f"type={props.remesh_type}\n")
                f.write(f"timestamp={time.time()}\n")
            logging.info(f"Updated remesh state file: {remesh_state_path}")
        except Exception as e:
            logging.error(f"Error writing remesh state file: {str(e)}")
        
        return {'FINISHED'}

def get_prompt_content(prompt_file):
    """Get the content of a text prompt file"""
    try:
        file_path = os.path.join(TEXT_OPTIONS_DIR, prompt_file)
        if not os.path.exists(file_path):
            logging.error(f"Prompt file not found: {file_path}")
            return "File not found"
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading prompt file: {e}")
        return "Error reading file"

def copy_text_file(source_file, target_file):
    """Copy the contents of source file to target file"""
    try:
        source_path = os.path.join(TEXT_OPTIONS_DIR, source_file)
        target_path = os.path.join(TEXT_OPTIONS_DIR, target_file)
        
        if not os.path.exists(source_path):
            logging.error(f"Source file not found: {source_path}")
            return False
            
        with open(source_path, 'r', encoding='utf-8') as source:
            content = source.read()
            
        with open(target_path, 'w', encoding='utf-8') as target:
            target.write(content)
            
        logging.info(f"Successfully copied {source_file} to {target_file}")
        return True
    except Exception as e:
        logging.error(f"Error copying file: {e}")
        return False

def run_comfyui_workflow():
    """Process renders through ComfyUI using direct HTTP requests instead of websockets"""
    try:
        logging.info("Starting ComfyUI workflow processing...")
        
        # Generate a unique client ID for this session
        client_id = f"blender_{random.randint(1000, 9999)}"
        
        # Load the workflow JSON
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        json_path = os.path.join(parent_dir, "comfyworkflows", "multiview.json")
        
        if not os.path.exists(json_path):
            logging.error(f"Workflow JSON not found at {json_path}")
            return False
            
        logging.info(f"Loading workflow from {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        
        # Update the seed in the workflow to prevent caching
        try:
            workflow["83"]["inputs"]["seed"] = random.randint(0, 999999999)
            logging.info("Updated random seed in workflow")
        except KeyError:
            logging.warning("Could not update seed in workflow (node 83 not found)")
        
        # Queue the prompt with the workflow
        prompt_data = {"prompt": workflow, "client_id": client_id}
        json_data = json.dumps(prompt_data).encode('utf-8')
        
        # Send the prompt to ComfyUI
        try:
            req = urllib.request.Request(f"http://{COMFYUI_SERVER}/prompt", data=json_data)
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req) as response:
                prompt_result = json.loads(response.read().decode('utf-8'))
                prompt_id = prompt_result.get('prompt_id')
                if not prompt_id:
                    logging.error("No prompt ID received from ComfyUI")
                    return False
                logging.info(f"Prompt queued with ID: {prompt_id}")
        except Exception as e:
            logging.error(f"Error sending prompt to ComfyUI: {e}")
            return False
        
        # Poll for completion by checking history endpoint
        max_attempts = 120  # 10 minutes (5 sec interval)
        for attempt in range(max_attempts):
            try:
                logging.info(f"Checking prompt status (attempt {attempt+1}/{max_attempts})...")
                history_url = f"http://{COMFYUI_SERVER}/history/{prompt_id}"
                with urllib.request.urlopen(history_url) as response:
                    history_data = json.loads(response.read().decode('utf-8'))
                    
                # Check if the execution is complete
                if prompt_id in history_data and "outputs" in history_data[prompt_id]:
                    outputs = history_data[prompt_id]["outputs"]
                    if "84" in outputs and "model_file" in outputs["84"]:
                        logging.info("Mesh generation completed!")
                        
                        # Extract the model file path
                        model_file_path = outputs["84"]["model_file"]
                        logging.info(f"Generated model file: {model_file_path}")
                        
                        # Copy the model file to our target location
                        copy_mesh_to_target(COMFYUI_OUTPUT_DIR, os.path.dirname(GENERATED_MESH_PATH))
                        return True
            except Exception as e:
                logging.error(f"Error checking prompt status: {e}")
            
            # Wait before checking again
            time.sleep(5)
        
        logging.error("Timed out waiting for ComfyUI to process")
        return False
    except Exception as e:
        logging.error(f"Error processing ComfyUI workflow: {e}")
        return False

def copy_mesh_to_target(comfyui_output_dir, target_dir):
    """Copy the latest generated mesh from ComfyUI output to target directory"""
    try:
        # Ensure target directory exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Find the latest .glb file in ComfyUI output
        glb_files = [f for f in os.listdir(comfyui_output_dir) if f.endswith('.glb')]
        if not glb_files:
            logging.error("No .glb files found in ComfyUI output directory")
            return False
            
        # Sort by modification time to get the latest
        latest_glb = max(glb_files, key=lambda x: os.path.getmtime(os.path.join(comfyui_output_dir, x)))
        
        # Copy to target location
        source_path = os.path.join(comfyui_output_dir, latest_glb)
        target_path = os.path.join(target_dir, "current_mesh.glb")
        
        shutil.copy2(source_path, target_path)
        logging.info(f"Successfully copied mesh from {source_path} to {target_path}")
        return True
    except Exception as e:
        logging.error(f"Error copying mesh: {e}")
        return False

def import_generated_mesh():
    """Import the generated mesh into Blender"""
    try:
        if not os.path.exists(GENERATED_MESH_PATH):
            logging.error(f"Generated mesh not found at {GENERATED_MESH_PATH}")
            return False
            
        logging.info(f"Importing mesh from {GENERATED_MESH_PATH}")
        
        # Check if there's an active selection first
        active_obj = bpy.context.active_object
        has_active_mesh = active_obj and active_obj.type == 'MESH'
        
        # Initialize previous_obj and previous dimensions
        previous_obj = None
        previous_max_dim = 1.0  # Default if no previous object
        previous_x_larger_than_y = True  # Default orientation assumption
        
        if has_active_mesh:
            # Store the reference to the previously active object
            previous_obj = active_obj
            
            # Get the max dimension of the previous object
            previous_max_dim = max(previous_obj.dimensions.x, previous_obj.dimensions.y, previous_obj.dimensions.z)
            
            # Store which dimension is larger (x or y)
            previous_x_larger_than_y = previous_obj.dimensions.x >= previous_obj.dimensions.y
            
            logging.info(f"Previous object max dimension: {previous_max_dim}")
            logging.info(f"Previous object X > Y: {previous_x_larger_than_y}")
        else:
            logging.warning("No active mesh found. Importing without hiding any mesh.")
            
        # Hide all existing mesh objects before importing the new one
        logging.info("Hiding selected existing mesh objects...")
        existing_meshes = []
        
        # Keep track of objects to skip (base objects)
        protected_objects = []
        
        # Get a clean list of existing mesh objects to avoid reference errors later
        try:
            # Create a safe copy of object names to avoid iterator issues
            existing_mesh_names = [obj.name for obj in bpy.data.objects if obj.type == 'MESH']
            logging.info(f"Found {len(existing_mesh_names)} existing mesh objects")
            
            # First identify protected objects
            for obj_name in existing_mesh_names:
                # Skip objects named 'base' or containing 'base' in their name (case insensitive)
                if 'base' in obj_name.lower():
                    protected_objects.append(obj_name)
                    logging.info(f"Protected object (will stay visible): {obj_name}")
            
            # Process each mesh by name to avoid reference errors
            for obj_name in existing_mesh_names:
                # Skip if the object is protected
                if obj_name in protected_objects:
                    continue
                    
                # Only hide selected or previously generated objects
                try:
                    # Check if the object still exists in the scene
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        # Store selection state to ensure we can check it safely
                        is_selected = False
                        try:
                            is_selected = obj.select_get()
                        except ReferenceError:
                            logging.warning(f"Reference error when checking selection of {obj_name}")
                            continue
                        except Exception as select_err:
                            logging.warning(f"Error when checking selection of {obj_name}: {str(select_err)}")
                            continue
                            
                        # Check if this was the previous object (the active object)
                        is_previous = False
                        try:
                            is_previous = (has_active_mesh and active_obj and obj.name == active_obj.name)
                        except ReferenceError:
                            is_previous = False
                            logging.warning(f"Reference error when checking if {obj_name} was the previous object")
                        except Exception as prev_err:
                            logging.warning(f"Error when checking if {obj_name} was the previous object: {str(prev_err)}")
                        
                        if is_selected or is_previous:
                            try:
                                # Double-check the object still exists before hiding
                                if obj_name in bpy.data.objects:
                                    obj = bpy.data.objects[obj_name]  # Get a fresh reference
                                    obj.hide_viewport = True
                                    obj.hide_render = True
                                    existing_meshes.append(obj_name)
                                    logging.info(f"Hidden selected mesh: {obj_name}")
                            except ReferenceError:
                                logging.warning(f"Reference error when hiding {obj_name}")
                            except Exception as hide_err:
                                logging.warning(f"Error when hiding {obj_name}: {str(hide_err)}")
                except Exception as e:
                    logging.error(f"Failed to hide mesh {obj_name}: {str(e)}")
                    import traceback
                    logging.error(traceback.format_exc())
        except Exception as e:
            logging.error(f"Error processing existing meshes: {str(e)}")
            
        logging.info(f"Successfully hidden {len(existing_meshes)} meshes")
            
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Get the list of objects before import
        objects_before = set(bpy.context.scene.objects)
        
        # Import the GLB file with specific import options
        try:
            logging.info(f"Attempting to import {GENERATED_MESH_PATH}")
            
            # Make sure the file exists and has size
            file_size = os.path.getsize(GENERATED_MESH_PATH)
            logging.info(f"GLB file size: {file_size} bytes")
            
            if file_size == 0:
                logging.error("GLB file exists but is empty (0 bytes)")
                return False
                
            # Import with more detailed options and error catching
            try:
                # First try to use import options that exclude empty objects
                bpy.ops.import_scene.gltf(
                    filepath=GENERATED_MESH_PATH,
                    import_pack_images=True,
                    merge_vertices=True,
                    import_cameras=False,
                    import_lights=False
                )
                logging.info("Successfully imported glTF with advanced options")
            except TypeError:
                # Fall back to basic import if the version doesn't support those options
                bpy.ops.import_scene.gltf(filepath=GENERATED_MESH_PATH)
                logging.info("Successfully imported glTF with basic options")
                
        except Exception as import_error:
            logging.error(f"Error during import: {import_error}")
            # Try with pure filepath
            try:
                logging.info("Trying alternative import method...")
                bpy.ops.import_scene.gltf(filepath=str(GENERATED_MESH_PATH))
                logging.info("Alternative import method succeeded")
            except Exception as alt_error:
                logging.error(f"Alternative import also failed: {alt_error}")
                return False
        
        # Get the list of objects after import
        objects_after = set(bpy.context.scene.objects)
        
        # Find the newly added objects
        imported_objects = list(objects_after - objects_before)
        logging.info(f"Imported {len(imported_objects)} new objects")
        
        if not imported_objects:
            logging.error("No objects were imported")
            return False
        
        # Find all imported mesh objects, regardless of hierarchy
        all_imported_meshes = []
        empties_to_remove = []
        
        # Identify meshes and empty container objects
        for obj in imported_objects:
            if obj.type == 'MESH' and hasattr(obj.data, 'vertices') and len(obj.data.vertices) > 0:
                all_imported_meshes.append(obj)
                logging.info(f"Found mesh: {obj.name} with {len(obj.data.vertices)} vertices")
            elif obj.type == 'EMPTY' and (obj.name.lower() == 'world' or obj.name.lower() == 'scene' or obj.name.lower().startswith('empty')):
                # This is likely a container object we want to remove
                empties_to_remove.append(obj)
                logging.info(f"Found empty container: {obj.name}")
                
                # Check for mesh children and add them to our list
                for child in obj.children:
                    if child.type == 'MESH' and child not in all_imported_meshes:
                        all_imported_meshes.append(child)
                        logging.info(f"Found mesh child: {child.name} with {len(child.data.vertices) if hasattr(child.data, 'vertices') else 0} vertices")
            
        if not all_imported_meshes:
            logging.error("No valid mesh objects found in the import")
            return False
            
        # Find the mesh with the most vertices
        main_mesh = max(all_imported_meshes, key=lambda obj: len(obj.data.vertices) if hasattr(obj.data, 'vertices') else 0)
        logging.info(f"Selected main mesh: {main_mesh.name} with {len(main_mesh.data.vertices)} vertices")
        
        # Parent all mesh objects to main_mesh if they're not already in a hierarchy
        for mesh_obj in all_imported_meshes:
            if mesh_obj != main_mesh and mesh_obj.parent in empties_to_remove:
                # Clear parent but keep transform
                original_matrix = mesh_obj.matrix_world.copy()
                mesh_obj.parent = None
                mesh_obj.matrix_world = original_matrix
                
                # Make it a child of main_mesh
                mesh_obj.parent = main_mesh
                logging.info(f"Re-parented {mesh_obj.name} to {main_mesh.name}")
        
        # Now delete all empty container objects
        for empty in empties_to_remove:
            bpy.data.objects.remove(empty, do_unlink=True)
            logging.info(f"Removed empty container: {empty.name}")
        
        # Hide the previous object if it exists (double-check in case our initial hiding missed it)
        if has_active_mesh and previous_obj:
            try:
                # Make sure the previous object reference is still valid
                if previous_obj.name in bpy.data.objects:
                    previous_obj.hide_viewport = True
                    previous_obj.hide_render = True
                    logging.info(f"Hidden previous active object: {previous_obj.name}")
                    
                    # Also hide any children the previous object might have
                    for child in previous_obj.children:
                        if child.type == 'MESH':
                            child.hide_viewport = True
                            child.hide_render = True
                            logging.info(f"Hidden child object: {child.name}")
            except ReferenceError:
                logging.warning("Previous object reference no longer valid, cannot hide it")
            except Exception as e:
                logging.error(f"Error hiding previous object: {str(e)}")
        
        # Set the main mesh as active
        bpy.context.view_layer.objects.active = main_mesh
        main_mesh.select_set(True)
        
        # Ensure the main mesh and its children are visible
        try:
            if main_mesh.name in bpy.data.objects:  # Verify the object still exists
                main_mesh.hide_viewport = False
                main_mesh.hide_render = False
                logging.info(f"Made main mesh visible: {main_mesh.name}")
            
                # Make sure any children are also visible (with error protection)
                try:
                    # First check if children_recursive property exists and is accessible
                    if hasattr(main_mesh, 'children_recursive'):
                        for child in main_mesh.children_recursive:
                            try:
                                if child.type == 'MESH':
                                    child.hide_viewport = False
                                    child.hide_render = False
                                    logging.info(f"Made child mesh visible: {child.name}")
                            except ReferenceError:
                                logging.warning(f"Reference error while trying to access child of {main_mesh.name}")
                            except Exception as child_error:
                                logging.error(f"Error processing child: {str(child_error)}")
                except ReferenceError:
                    logging.warning("Reference error while accessing children_recursive")
                except Exception as children_error:
                    logging.error(f"Error accessing children: {str(children_error)}")
        except ReferenceError:
            logging.warning("Main mesh reference is no longer valid - cannot update visibility")
        except Exception as e:
            logging.error(f"Error setting main mesh visibility: {str(e)}")
        
        # Set the object's origin to its geometry center
        try:
            if main_mesh.name in bpy.data.objects:  # Check if the object still exists
                # Set origin to geometry
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                logging.info("Set object origin to geometry center")
                
                # Center the object at the world origin
                main_mesh.location = (0, 0, 0)
                logging.info("Centered object at world origin")
            else:
                logging.warning("Main mesh no longer exists - skipping origin and location setting")
        except ReferenceError:
            logging.warning("Main mesh reference is no longer valid - skipping origin and location setting")
        except Exception as e:
            logging.error(f"Error setting object origin and location: {str(e)}")
        
        # Calculate and apply scaling to match the previous object's max dimension
        try:
            if main_mesh.name in bpy.data.objects:  # Check if the object still exists
                current_max_dim = max(main_mesh.dimensions.x, main_mesh.dimensions.y, main_mesh.dimensions.z)
                logging.info(f"Current mesh max dimension: {current_max_dim}")
                
                if current_max_dim > 0:
                    # If a previous object exists, use its dimensions for scaling
                    if has_active_mesh and previous_obj:
                        scale_factor = previous_max_dim / current_max_dim
                    else:
                        # Default scaling if no previous object
                        scale_factor = 1.0 / current_max_dim  # Scale to unit size
                        
                    logging.info(f"Calculated scale factor: {scale_factor}")
                    
                    # Apply scaling to main mesh
                    main_mesh.scale = (scale_factor, scale_factor, scale_factor)
                    
                    # Apply the scale
                    try:
                        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                        logging.info(f"Applied scaling factor {scale_factor}")
                    except Exception as apply_error:
                        logging.error(f"Error applying transform: {str(apply_error)}")
                    
                    # Check if we need to rotate the model based on X and Y dimensions
                    current_x_larger_than_y = main_mesh.dimensions.x >= main_mesh.dimensions.y
                    
                    # If previous object exists and dimension orientation doesn't match
                    if has_active_mesh and previous_obj and (current_x_larger_than_y != previous_x_larger_than_y):
                        logging.info("X/Y dimension orientation mismatch detected, rotating object 45 degrees")
                        
                        # Rotate 45 degrees counterclockwise around Z axis
                        # Convert degrees to radians (45 degrees = π/4 radians)
                        rotation_angle = math.radians(45)
                        
                        # Rotate the object
                        main_mesh.rotation_euler.z += rotation_angle
                        
                        # Apply the rotation
                        try:
                            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
                            logging.info("Applied 45 degree counterclockwise rotation")
                        except Exception as rot_error:
                            logging.error(f"Error applying rotation: {str(rot_error)}")
                else:
                    logging.warning("Imported mesh has zero dimensions, couldn't scale properly")
            else:
                logging.warning("Main mesh no longer exists - skipping scaling and rotation")
        except ReferenceError:
            logging.warning("Main mesh reference is no longer valid - skipping scaling and rotation")
        except Exception as e:
            logging.error(f"Error during scaling and rotation: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
        
        # Apply staged remesh if enabled
        if bpy.context.scene.remesh_properties.enable_remesh:
            stage = bpy.context.scene.remesh_properties.current_stage
            remesh_type = bpy.context.scene.remesh_properties.remesh_type
            
            logging.info(f"Applying staged remesh: Stage {stage}, Type {remesh_type}")
            
            # Store the main_mesh name so we can look it up again if needed
            main_mesh_name = ""
            
            # Make sure main_mesh still exists and is valid before applying remesh
            try:
                # Verify main_mesh is still a valid reference
                if not main_mesh or not hasattr(main_mesh, 'name'):
                    logging.error("Cannot apply remesh: Invalid main mesh reference")
                    return False
                    
                # Store the name for later reference
                main_mesh_name = main_mesh.name
                
                # Verify the object exists in the scene
                if main_mesh_name in bpy.data.objects:
                    # Get a fresh reference to the mesh
                    mesh_obj = bpy.data.objects[main_mesh_name]
                    
                    # Make sure it's a mesh
                    if mesh_obj.type == 'MESH':
                        # Deselect all objects and select only our target mesh
                        bpy.ops.object.select_all(action='DESELECT')
                        mesh_obj.select_set(True)
                        bpy.context.view_layer.objects.active = mesh_obj
                        
                        # Now apply the remesh using the fresh reference
                        remesh_result = apply_staged_remesh(mesh_obj, stage, remesh_type)
                        
                        if remesh_result:
                            # Increment stage for next import
                            next_stage = stage + 1
                            if next_stage > 3:
                                next_stage = 1  # Reset to stage 1 if we're past stage 3
                                
                            bpy.context.scene.remesh_properties.current_stage = next_stage
                            logging.info(f"Incremented remesh stage to {next_stage}")
                        else:
                            logging.error("Failed to apply remesh")
                    else:
                        logging.error(f"Cannot apply remesh: Object {main_mesh_name} is not a mesh")
                else:
                    logging.error(f"Cannot apply remesh: Object {main_mesh_name} not found in the scene")
            except ReferenceError:
                logging.error("Cannot apply remesh: Main mesh reference is no longer valid")
                
                # If we stored the name, try to use it to get a fresh reference
                if main_mesh_name and main_mesh_name in bpy.data.objects:
                    logging.info(f"Attempting remesh with fresh reference to {main_mesh_name}")
                    mesh_obj = bpy.data.objects[main_mesh_name]
                    remesh_result = apply_staged_remesh(mesh_obj, stage, remesh_type)
                    
                    if remesh_result:
                        next_stage = stage + 1
                        if next_stage > 3:
                            next_stage = 1
                        bpy.context.scene.remesh_properties.current_stage = next_stage
                        logging.info(f"Recovered and incremented remesh stage to {next_stage}")
            except Exception as e:
                logging.error(f"Error preparing for remesh: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
        
        # Make sure the main_mesh still exists before returning
        try:
            # Store the mesh name first to avoid reference errors
            mesh_name = ""
            
            # Carefully extract the name
            try:
                if main_mesh and hasattr(main_mesh, 'name'):
                    mesh_name = main_mesh.name
                else:
                    logging.error("Main mesh reference is invalid")
                    # Try to find any active mesh as a fallback
                    if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                        logging.info(f"Using active mesh as fallback: {bpy.context.active_object.name}")
                        return True
                    return False
            except ReferenceError:
                logging.error("Cannot access main mesh name (reference error)")
                # Try to find any active mesh as a fallback
                if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                    logging.info(f"Using active mesh as fallback: {bpy.context.active_object.name}")
                    return True
                return False
            
            # Ensure the object is still in the Blender data using the stored name
            if mesh_name and mesh_name in bpy.data.objects:
                # Double-check it's a mesh
                if bpy.data.objects[mesh_name].type == 'MESH':
                    logging.info(f"Successfully imported and processed mesh: {mesh_name}")
                    return True
                else:
                    logging.error(f"Object {mesh_name} exists but is no longer a mesh")
            else:
                if mesh_name:
                    logging.error(f"Object {mesh_name} no longer exists in the scene")
                else:
                    logging.error("No valid mesh name could be determined")
                
            # Try to find another active mesh
            if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                logging.info(f"Found alternative active mesh: {bpy.context.active_object.name}")
                return True
                
            return False
        except ReferenceError:
            logging.error("Main mesh was removed during processing")
            # Try to find another active mesh
            if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                logging.info(f"Found alternative active mesh: {bpy.context.active_object.name}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error in final mesh verification: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    except Exception as e:
        logging.error(f"Error importing generated mesh: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def apply_staged_remesh(main_mesh, stage, remesh_type):
    """Apply a remesh modifier based on the current stage
    
    Args:
        main_mesh: The mesh object to apply the remesh to
        stage: The current remesh stage (1, 2, or 3)
        remesh_type: The type of remesh to apply (BLOCKS, SMOOTH, SHARP)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logging.info(f"Starting remesh process - Stage {stage}, Type: {remesh_type}")
        
        # Verify we have a valid mesh object
        if not main_mesh:
            logging.error("Cannot apply remesh: No mesh provided")
            return False
        
        # Get the name now while reference is still valid
        mesh_name = ""
        try:
            # Check if this is even a blender object
            if not hasattr(main_mesh, 'name'):
                logging.error("Cannot apply remesh: Invalid object (not a Blender object)")
                return False
                
            mesh_name = main_mesh.name
            logging.info(f"Applying remesh to object: {mesh_name}")
        except ReferenceError:
            logging.error("Cannot apply remesh: Cannot access object name (reference error)")
            return False
        except Exception as name_error:
            logging.error(f"Cannot access object properties: {str(name_error)}")
            return False
            
        # Verify the object still exists in the scene using the name
        if mesh_name not in bpy.data.objects:
            logging.error(f"Cannot apply remesh: Object '{mesh_name}' not found in scene")
            return False
            
        # Get a fresh reference to the object
        mesh_obj = bpy.data.objects.get(mesh_name)
        if not mesh_obj:
            logging.error(f"Cannot apply remesh: Failed to get object '{mesh_name}'")
            return False
            
        # Verify it's a mesh
        if mesh_obj.type != 'MESH':
            logging.error(f"Cannot apply remesh: Object '{mesh_name}' is not a mesh")
            return False
            
        logging.info(f"Object verification passed for '{mesh_name}'")
        
        # Early exit for stage 3 (no remesh)
        if stage == 3:
            logging.info("Stage 3: No remesh applied (as configured)")
            return True
            
        # Select and make the mesh active - use the fresh reference
        try:
            # Deselect all objects first
            logging.info("Deselecting all objects")
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select our target mesh
            logging.info(f"Selecting mesh: {mesh_obj.name}")
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj
        except Exception as select_error:
            logging.error(f"Failed to select mesh: {str(select_error)}")
            return False
        
        # Remove any existing remesh modifiers
        try:
            mod_count = 0
            modifiers_to_remove = []
            
            # Create a safe copy of modifiers to avoid reference errors
            for mod in mesh_obj.modifiers:
                if mod.type == 'REMESH':
                    modifiers_to_remove.append(mod.name)
                    
            for mod_name in modifiers_to_remove:
                mod = mesh_obj.modifiers.get(mod_name)
                if mod:
                    mesh_obj.modifiers.remove(mod)
                    mod_count += 1
            if mod_count > 0:
                logging.info(f"Removed {mod_count} existing remesh modifiers")
        except Exception as mod_error:
            logging.error(f"Error removing existing modifiers: {str(mod_error)}")
            # Continue anyway - this isn't fatal
        
        # Create a new remesh modifier
        try:
            logging.info("Creating new remesh modifier")
            remesh_mod = mesh_obj.modifiers.new(name="StageRemesh", type='REMESH')
            
            # Set the remesh mode based on type
            if remesh_type == 'BLOCKS':
                remesh_mod.mode = 'BLOCKS'
            elif remesh_type == 'SMOOTH':
                remesh_mod.mode = 'SMOOTH'
            else:  # Default to SHARP
                remesh_mod.mode = 'SHARP'
            
            # Set octree depth based on stage
            if stage == 1:
                remesh_mod.octree_depth = 3
            else:  # stage 2
                remesh_mod.octree_depth = 5
            
            # Set remove disconnected to False
            remesh_mod.use_remove_disconnected = False
            
            logging.info(f"Applied {remesh_type} remesh with octree depth {remesh_mod.octree_depth}")
        except Exception as create_error:
            logging.error(f"Failed to create remesh modifier: {str(create_error)}")
            return False
        
        # Apply the modifier with robust error handling
        try:
            logging.info("Applying remesh modifier")
            # Ensure we're in object mode
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
                
            # Do a final check that the object and modifier still exist
            if mesh_name in bpy.data.objects and "StageRemesh" in bpy.data.objects[mesh_name].modifiers:
                # Apply the modifier
                bpy.ops.object.modifier_apply(modifier="StageRemesh")
                logging.info("Remesh modifier applied successfully!")
            else:
                logging.error("Object or modifier no longer exists, cannot apply")
                return False
        except Exception as apply_error:
            logging.error(f"Error applying modifier: {str(apply_error)}")
            # Try a different approach - sometimes the modifier apply fails
            try:
                logging.info("Trying alternate method: convert to mesh")
                # Check if the object still exists
                if mesh_name in bpy.data.objects:
                    # Ensure object is still selected
                    mesh_obj = bpy.data.objects[mesh_name]  # Get fresh reference
                    mesh_obj.select_set(True)
                    bpy.context.view_layer.objects.active = mesh_obj
                    
                    # Ensure we're in object mode
                    if bpy.context.mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode='OBJECT')
                        
                    # Try converting to mesh
                    bpy.ops.object.convert(target='MESH')
                    logging.info("Applied remesh by converting to mesh")
                else:
                    logging.error("Object no longer exists for alternative method")
                    return False
            except Exception as convert_error:
                logging.error(f"Failed to apply remesh: {str(convert_error)}")
                return False
        
        # Verify the mesh still exists after remeshing - get fresh reference
        try:
            # Use a safe approach to check existence
            if mesh_name in bpy.data.objects:
                final_obj = bpy.data.objects[mesh_name]
                if final_obj.type == 'MESH':
                    logging.info(f"Remesh successfully applied to {mesh_name}")
                    return True
                else:
                    logging.error(f"Object {mesh_name} exists but is no longer a mesh")
            else:
                logging.error(f"Object {mesh_name} no longer exists after remeshing")
            return False
        except Exception as verify_error:
            logging.error(f"Error verifying mesh after remesh: {str(verify_error)}")
            return False
    except Exception as e:
        logging.error(f"Error applying remesh: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def render_multiview():
    """
    Render multiple views using the RenderCam camera:
    - front view (frame 1)
    - right view (frame 2)
    - back view (frame 3)
    - left view (frame 4)
    """
    try:
        # Create output directory
        os.makedirs(RENDER_OUTPUT_DIR, exist_ok=True)
        logging.info(f"Render output directory created: {RENDER_OUTPUT_DIR}")
        
        # Get the render camera
        render_cam = bpy.data.objects.get(RENDER_CAMERA_NAME)
        if not render_cam:
            logging.error(f"Render camera not found: {RENDER_CAMERA_NAME}")
            # Try to create a camera if it doesn't exist
            try:
                bpy.ops.object.camera_add(location=(0, -10, 0), rotation=(math.radians(90), 0, 0))
                render_cam = bpy.context.active_object
                render_cam.name = RENDER_CAMERA_NAME
                logging.info(f"Created new render camera: {RENDER_CAMERA_NAME}")
                
                # Set camera properties for better rendering
                render_cam.data.type = 'PERSP'
                render_cam.data.lens = 50
                render_cam.data.clip_start = 0.1
                render_cam.data.clip_end = 100
            except Exception as e:
                logging.error(f"Failed to create render camera: {e}")
                return False
            
        # Store current camera and frame
        current_camera = bpy.context.scene.camera
        current_frame = bpy.context.scene.frame_current
        
        # Set render camera as active camera
        bpy.context.scene.camera = render_cam
        
        # Configure render settings
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.resolution_x = 512
        bpy.context.scene.render.resolution_y = 512
        
        # Render each frame
        for frame, filename in RENDER_FRAMES.items():
            try:
                # Set frame
                bpy.context.scene.frame_current = frame
                
                # Set output path
                output_path = os.path.join(RENDER_OUTPUT_DIR, filename)
                bpy.context.scene.render.filepath = output_path
                
                # Render
                logging.info(f"Rendering frame {frame} to {output_path}")
                bpy.ops.render.render(write_still=True)
                
                if os.path.exists(output_path):
                    logging.info(f"Successfully rendered {filename}")
                else:
                    logging.warning(f"Render file not found after rendering: {output_path}")
                    
            except Exception as frame_error:
                logging.error(f"Error rendering frame {frame}: {frame_error}")
        
        # Restore original camera and frame
        bpy.context.scene.camera = current_camera
        bpy.context.scene.frame_current = current_frame
        
        logging.info("Multi-view render completed")
        return True
    except Exception as e:
        logging.error(f"Error in multi-view render: {e}")
        # Restore original camera and frame if possible
        try:
            if 'current_camera' in locals():
                bpy.context.scene.camera = current_camera
            if 'current_frame' in locals():
                bpy.context.scene.frame_current = current_frame
        except:
            pass
        return False

# Create and configure RenderCam function
def ensure_render_camera():
    """Create and configure the RenderCam if it doesn't exist"""
    render_cam = bpy.data.objects.get(RENDER_CAMERA_NAME)
    
    if not render_cam:
        logging.info(f"Creating render camera: {RENDER_CAMERA_NAME}")
        bpy.ops.object.camera_add(location=(0, -10, 0), rotation=(math.radians(90), 0, 0))
        render_cam = bpy.context.active_object
        render_cam.name = RENDER_CAMERA_NAME
        
        # Configure camera settings
        render_cam.data.type = 'PERSP'
        render_cam.data.lens = 50
        render_cam.data.clip_start = 0.1
        render_cam.data.clip_end = 100
        
        # Create animation for the camera to rotate around
        render_cam.animation_data_create()
        render_cam.animation_data.action = bpy.data.actions.new(name="RenderCamAction")
        
        # Create the rotation track
        rot_curves = []
        for i in range(3):  # X, Y, Z
            fcurve = render_cam.animation_data.action.fcurves.new(data_path="rotation_euler", index=i)
            rot_curves.append(fcurve)
        
        # Set keyframes for each view
        # Frame 1: Front View (0 degrees)
        rot_curves[2].keyframe_points.insert(1, 0)
        # Frame 2: Right View (90 degrees)
        rot_curves[2].keyframe_points.insert(2, math.radians(90))
        # Frame 3: Back View (180 degrees)
        rot_curves[2].keyframe_points.insert(3, math.radians(180))
        # Frame 4: Left View (270 degrees)
        rot_curves[2].keyframe_points.insert(4, math.radians(270))
        # Frame 5: Back to Front (360/0 degrees)
        rot_curves[2].keyframe_points.insert(5, math.radians(360))
        
        logging.info("Render camera configured with rotation animation")
    else:
        logging.info(f"Render camera {RENDER_CAMERA_NAME} already exists")
    
    return render_cam

# Load images from disk function (internal, not exposed as an operator)
def load_images():
    # Define the path
    image_dir = "C:/CODING/VIBE/VIBE_Forming/input/options"
    alt_image_dir = r"C:\CODING\VIBE\VIBE_Forming\input\options"  # Alternative path format
    
    # Debug information
    logging.info(f"Attempting to load images from: {image_dir}")
    
    # Check if directory exists
    if not os.path.exists(image_dir):
        # Try alternative path format
        if os.path.exists(alt_image_dir):
            logging.info(f"Using alternative path format: {alt_image_dir}")
            image_dir = alt_image_dir
        else:
            logging.error(f"Image directory not found at: {image_dir} or {alt_image_dir}")
            # Try to create the directory
            try:
                os.makedirs(image_dir, exist_ok=True)
                logging.info(f"Created image directory: {image_dir}")
            except Exception as e:
                logging.error(f"Failed to create image directory: {e}")
                return []
    
    # Log directory contents
    try:
        dir_contents = os.listdir(image_dir)
        logging.info(f"Directory contents of {image_dir}: {dir_contents}")
    except Exception as e:
        logging.error(f"Error listing directory contents: {e}")
    
    # List of image names to look for
    image_names = ['A.png', 'B.png', 'C.png']
    
    # Check which ComfyUI output directory also exists
    comfyui_output = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\ComfyUI\output"
    if os.path.exists(comfyui_output):
        try:
            comfyui_files = os.listdir(comfyui_output)
            logging.info(f"ComfyUI output directory contents: {comfyui_files}")
            # Look for any image files that could be copied
            for file in comfyui_files:
                if file.endswith('.png') and file.startswith(('A', 'B', 'C')):
                    source_path = os.path.join(comfyui_output, file)
                    target_path = os.path.join(image_dir, file[0] + '.png')  # Just use the first letter + .png
                    try:
                        shutil.copy2(source_path, target_path)
                        logging.info(f"Copied {file} from ComfyUI output to {target_path}")
                    except Exception as e:
                        logging.error(f"Failed to copy file: {e}")
        except Exception as e:
            logging.error(f"Error checking ComfyUI output: {e}")
    
    loaded_images = []
    for img_name in image_names:
        img_path = os.path.join(image_dir, img_name)
        logging.info(f"Attempting to load image from: {img_path}")
        
        if os.path.exists(img_path):
            try:
                # Try to load image if not already loaded
                if img_name not in bpy.data.images:
                    img = bpy.data.images.load(filepath=img_path, check_existing=False)
                    img.name = img_name
                    if not img.packed_file:
                        img.pack()
                    loaded_images.append(img)
                    logging.info(f"Successfully loaded image: {img_name}")
                else:
                    # Reload the image from disk
                    bpy.data.images[img_name].reload()
                    loaded_images.append(bpy.data.images[img_name])
                    logging.info(f"Reloaded existing image: {img_name}")
            except Exception as e:
                logging.error(f"Exception loading {img_path}: {str(e)}")
        else:
            logging.error(f"Image file not found: {img_path}")
    
    return loaded_images

# Create required directories
def ensure_directories():
    dirs = [
        "C:/CODING/VIBE/VIBE_Forming/input/options",
        "C:/CODING/VIBE/VIBE_Forming/input/COMFYINPUTS/blenderRender",
        "C:/CODING/VIBE/VIBE_Forming/input/COMFYINPUTS/textOptions",
        "C:/CODING/VIBE/VIBE_Forming/output",
        "C:/CODING/VIBE/VIBE_Forming/output/generated/Models"
    ]
    
    # Also try backslash versions as alternative
    alt_dirs = [
        r"C:\CODING\VIBE\VIBE_Forming\input\options",
        r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\blenderRender",
        r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\textOptions",
        r"C:\CODING\VIBE\VIBE_Forming\output",
        r"C:\CODING\VIBE\VIBE_Forming\output\generated\Models"
    ]
    
    # Combine the sets
    all_dirs = dirs + alt_dirs
    
    for dir_path in all_dirs:
        try:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logging.info(f"Created directory: {dir_path}")
            else:
                # Test write permissions
                try:
                    test_file = os.path.join(dir_path, "test_write.tmp")
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    logging.info(f"Directory exists with write permission: {dir_path}")
                except Exception as e:
                    logging.error(f"Directory exists but has no write permission: {dir_path} - {e}")
        except Exception as e:
            logging.error(f"Failed to create directory: {dir_path} - {e}")
    
    # Log the current state of key directories
    key_dirs = [
        "C:/CODING/VIBE/VIBE_Forming/input/options",
        r"C:\CODING\VIBE\VIBE_Forming\input\options"
    ]
    
    for dir_path in key_dirs:
        if os.path.exists(dir_path):
            try:
                files = os.listdir(dir_path)
                logging.info(f"Contents of {dir_path}: {files}")
            except Exception as e:
                logging.error(f"Error listing contents of {dir_path}: {e}")
    
    # Create default prompt files if they don't exist
    default_prompts = {
        "A_0001.txt": "A sleek, futuristic sculpture with smooth curves and metallic surfaces, resembling a abstract interpretation of motion and energy.",
        "B_0001.txt": "An organic, biomechanical structure with intricate details and flowing forms, inspired by natural patterns and biological systems.",
        "C_0001.txt": "A crystalline geometric composition with sharp angles and faceted surfaces, showcasing mathematical precision and architectural complexity."
    }
    
    for filename, content in default_prompts.items():
        file_path = os.path.join(TEXT_OPTIONS_DIR, filename)
        if not os.path.exists(file_path):
            try:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logging.info(f"Created default prompt file: {filename}")
            except Exception as e:
                logging.error(f"Failed to create default prompt file {filename}: {e}")

def check_remesh_state():
    """Check the remesh state from the UI and update Blender properties"""
    try:
        # Use global BASE_DIR
        remesh_state_path = os.path.join(BASE_DIR, "remesh_state.txt")
        
        if not os.path.exists(remesh_state_path):
            logging.info("No remesh state file found")
            return
            
        # Parse the state file
        enabled = False
        stage = 1
        remesh_type = "SHARP"
        
        with open(remesh_state_path, "r") as f:
            for line in f:
                if line.startswith("enabled="):
                    enabled_text = line.strip().split("=")[1].lower()
                    enabled = (enabled_text == "true")
                elif line.startswith("stage="):
                    try:
                        stage = int(line.strip().split("=")[1])
                    except:
                        stage = 1
                elif line.startswith("type="):
                    remesh_type = line.strip().split("=")[1].upper()
        
        # Make sure the scene exists and has remesh_properties before updating
        if not hasattr(bpy.context, 'scene') or not bpy.context.scene:
            logging.error("Cannot update remesh state: No active scene")
            return
            
        if not hasattr(bpy.context.scene, 'remesh_properties'):
            logging.error("Cannot update remesh state: remesh_properties not found in scene")
            return
        
        # Update Blender properties
        try:
            bpy.context.scene.remesh_properties.enable_remesh = enabled
            bpy.context.scene.remesh_properties.current_stage = stage
            
            # Set remesh type if it's a valid value
            if remesh_type in ["BLOCKS", "SMOOTH", "SHARP"]:
                bpy.context.scene.remesh_properties.remesh_type = remesh_type
                
            logging.info(f"Updated remesh state: enabled={enabled}, stage={stage}, type={remesh_type}")
        except Exception as props_error:
            logging.error(f"Error updating remesh properties: {str(props_error)}")
        
        # Write back with updated values (in case Blender changed them)
        try:
            with open(remesh_state_path, "w") as f:
                f.write(f"enabled={str(bpy.context.scene.remesh_properties.enable_remesh).lower()}\n")
                f.write(f"stage={bpy.context.scene.remesh_properties.current_stage}\n")
                f.write(f"type={bpy.context.scene.remesh_properties.remesh_type}\n")
                f.write(f"timestamp={time.time()}\n")
        except Exception as write_error:
            logging.error(f"Error writing back remesh state: {str(write_error)}")
        
    except Exception as e:
        logging.error(f"Error checking remesh state: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())

def check_image_updates(operator_report_func, process):
    # Check if process is still running
    if process.poll() is None:
        # Process is still running, check again later
        logging.info("Still processing options...")
        return 2.0  # Check again in 2 seconds
    
    # Process completed, get output
    stdout, stderr = process.communicate()
    
    # Log the output
    if stdout:
        logging.info(f"options_API.py output: {stdout}")
    if stderr:
        logging.error(f"options_API.py errors: {stderr}")
    
    # Check return code
    if process.returncode != 0:
        if operator_report_func:
            try:
                operator_report_func({'ERROR'}, f"Error generating options: {stderr}")
            except ReferenceError:
                # If operator reference is no longer valid, just log the error
                logging.error(f"Error generating options: {stderr}")
    else:
        logging.info("Successfully generated new options")
        try:
            # Refresh images in UI
            refresh_images_from_disk()
            
            # Try to show a notification if the operator is still valid
            if operator_report_func:
                try:
                    operator_report_func({'INFO'}, "Images refreshed successfully")
                except ReferenceError:
                    # Just log if operator reference is no longer valid
                    logging.info("Images refreshed successfully")
        except Exception as e:
            logging.error(f"Error refreshing images: {e}")
    
    return None  # Don't run again

# Function to refresh images from disk
def refresh_images_from_disk():
    """Refresh all option images from disk"""
    logging.info("Refreshing images from disk...")
    
    # Define the image directory
    image_dir = "C:/CODING/VIBE/VIBE_Forming/input/options"
    image_names = ['A.png', 'B.png', 'C.png']
    
    # Check if images exist on disk
    for img_name in image_names:
        img_path = os.path.join(image_dir, img_name)
        if os.path.exists(img_path):
            logging.info(f"Found image on disk: {img_path}")
            
            # Get existing image or create new one
            if img_name in bpy.data.images:
                # If the image already exists in Blender, reload it
                img = bpy.data.images[img_name]
                img.reload()
                logging.info(f"Reloaded existing image: {img_name}")
            else:
                # If not, load it from disk
                try:
                    img = bpy.data.images.load(img_path, check_existing=True)
                    img.name = img_name
                    if not img.packed_file:
                        img.pack()
                    logging.info(f"Loaded new image: {img_name}")
                except Exception as e:
                    logging.error(f"Error loading image {img_name}: {e}")
        else:
            logging.warning(f"Image not found on disk: {img_path}")
    
    # Force a redraw of all UI areas to show the updated images
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
    
    logging.info("Image refresh completed")

# Add a new operator for submitting custom requests
class REQUEST_OT_submit(bpy.types.Operator):
    bl_idname = "request.submit"
    bl_label = "Submit Request"
    bl_description = "Submit custom request to generate new options"
    
    def execute(self, context):
        custom_prompt = context.scene.custom_request_properties.custom_prompt
        
        if not custom_prompt.strip():
            self.report({'ERROR'}, "Please enter a prompt before submitting")
            return {'CANCELLED'}
        
        logging.info(f"Submitting custom request: {custom_prompt}")
        
        # Step 1: Write to input.txt
        try:
            with open(INPUT_TEXT_FILE, 'w', encoding='utf-8') as f:
                f.write(custom_prompt)
            logging.info(f"Successfully wrote custom prompt to {INPUT_TEXT_FILE}")
        except Exception as e:
            logging.error(f"Failed to write to input.txt: {e}")
            self.report({'ERROR'}, f"Failed to save custom prompt: {str(e)}")
            return {'CANCELLED'}
        
        # Step 2: Render views
        render_success = render_multiview()
        if not render_success:
            self.report({'ERROR'}, "Failed to render multi-views")
            return {'CANCELLED'}
        
        # Step 3: Run options_API.py
        try:
            # Use absolute paths for both the script and working directory
            base_dir = r"C:\CODING\VIBE\VIBE_Forming"
            comfyworkflows_dir = os.path.join(base_dir, "src", "comfyworkflows")
            options_api_script = os.path.join(comfyworkflows_dir, "options_API.py")
            
            # Verify the paths exist
            if not os.path.exists(comfyworkflows_dir):
                logging.error(f"Comfyworkflows directory does not exist: {comfyworkflows_dir}")
                self.report({'ERROR'}, f"Directory not found: {comfyworkflows_dir}")
                return {'CANCELLED'}
            
            if not os.path.exists(options_api_script):
                logging.error(f"Script not found: {options_api_script}")
                self.report({'ERROR'}, f"Script not found: {options_api_script}")
                return {'CANCELLED'}
            
            # Create process to run options_API.py
            python_exe = sys.executable
            
            # Set up the command
            cmd = [python_exe, options_api_script]
            
            # Log the command for debugging
            logging.info(f"Running command: {' '.join(cmd)} in directory: {comfyworkflows_dir}")
            
            # Start the process
            process = subprocess.Popen(
                cmd, 
                cwd=comfyworkflows_dir,  # Set working directory to the comfyworkflows directory
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Display a message that processing has started
            self.report({'INFO'}, "Generating options, please wait...")
            
            # Create a report function that will use a weak reference to the operator
            report_func = self.report
            
            # Use a timer to periodically check if images have been updated
            bpy.app.timers.register(lambda: check_image_updates(report_func, process), first_interval=2.0)
            
            return {'FINISHED'}
            
        except Exception as e:
            logging.error(f"Failed to run options_API.py: {e}")
            self.report({'ERROR'}, f"Failed to generate options: {str(e)}")
            return {'CANCELLED'}

# Check for render requests from UI
def check_render_requests():
    """Check if there's a render request from the UI and process it"""
    if os.path.exists(RENDER_REQUEST_FILE):
        logging.info(f"Found render request file: {RENDER_REQUEST_FILE}")
        try:
            # Read request details
            with open(RENDER_REQUEST_FILE, 'r') as f:
                request_details = f.read()
                
            logging.info(f"Request details: {request_details}")
            
            # Delete the request file
            os.remove(RENDER_REQUEST_FILE)
            
            # Process the render
            success = render_multiview()
            
            # Write completion status
            with open(RENDER_COMPLETE_FILE, 'w') as f:
                if success:
                    f.write("SUCCESS")
                    logging.info("Render completed successfully")
                else:
                    f.write("ERROR: Render failed")
                    logging.info("Render failed")
                    
            return True
        except Exception as e:
            logging.error(f"Error processing render request: {e}")
            
            # Write error status
            try:
                with open(RENDER_COMPLETE_FILE, 'w') as f:
                    f.write(f"ERROR: {str(e)}")
            except:
                pass
                
            return False
    
    return False

# Check for import requests from UI
def check_import_requests():
    """Check for requests to import generated models"""
    try:
        # Use the global BASE_DIR, not a local definition
        request_path = os.path.join(BASE_DIR, "import_request.txt")
        
        if not os.path.exists(request_path):
            return False
            
        # Read the request file
        with open(request_path, "r") as f:
            request_content = f.read()
            
        # Delete the request file
        try:
            os.remove(request_path)
            logging.info(f"Deleted import request file")
        except Exception as e:
            logging.warning(f"Could not delete request file: {str(e)}")
        
        logging.info(f"Found import request: {request_content}")
        
        # Check remesh state from UI
        check_remesh_state()
        
        # Process the import
        success = import_generated_mesh()
        
        # Write completion status
        status_message = "SUCCESS" if success else "FAILURE"
        with open(os.path.join(BASE_DIR, "import_complete.txt"), "w") as f:
            f.write(f"Status: {status_message}\n")
            f.write(f"Timestamp: {time.time()}\n")
            
        return success
    except Exception as e:
        logging.error(f"Error checking import requests: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

# Timer function to check for render and import requests
def check_requests_timer():
    """Timer function to periodically check for requests"""
    try:
        render_processed = check_render_requests()
        import_processed = check_import_requests()
        
        if render_processed:
            logging.info("Processed render request")
        if import_processed:
            logging.info("Processed import request")
            
        # Return the time interval for the next check (in seconds)
        return 2.0  # Check every 2 seconds
    except Exception as e:
        logging.error(f"Error in request timer: {e}")
        return 5.0  # Try again after 5 seconds if there was an error

# Registration function
def register():
    ensure_directories()
    
    # Register property groups
    bpy.utils.register_class(CustomRequestProperties)
    bpy.utils.register_class(PromptProperties)
    bpy.utils.register_class(RemeshProperties)
    bpy.types.Scene.prompt_properties = PointerProperty(type=PromptProperties)
    bpy.types.Scene.custom_request_properties = PointerProperty(type=CustomRequestProperties)
    bpy.types.Scene.remesh_properties = PointerProperty(type=RemeshProperties)
    
    # Register operators and panels
    bpy.utils.register_class(IMAGE_PT_display_panel)
    bpy.utils.register_class(OPTION_OT_select)
    bpy.utils.register_class(REQUEST_OT_submit)
    bpy.utils.register_class(IMAGE_OT_refresh)
    bpy.utils.register_class(OPTION_OT_terminate_script)
    bpy.utils.register_class(OBJECT_OT_generate_iteration)
    bpy.utils.register_class(OBJECT_OT_toggle_remesh)
    bpy.utils.register_class(REMESH_PT_settings_panel)

    # Create render camera
    ensure_render_camera()
    
    # Check the remesh state from UI
    check_remesh_state()
    
    # Load images on startup
    try:
        load_images()
        logging.info("Initial image loading completed")
    except Exception as e:
        logging.error(f"Failed to load images: {e}")
    
    # Apply default prompt A if prompt.txt doesn't exist
    prompt_path = os.path.join(TEXT_OPTIONS_DIR, PROMPT_FILE)
    if not os.path.exists(prompt_path):
        copy_text_file("A_0001.txt", PROMPT_FILE)
        logging.info("Applied default prompt A")
        
    # Start timer to check for render requests
    bpy.app.timers.register(check_requests_timer, first_interval=1.0)
        
    logging.info("Successfully registered VIBE panel")

# Unregistration function
def unregister():
    try:
        # Unregister property groups
        del bpy.types.Scene.prompt_properties
        del bpy.types.Scene.custom_request_properties
        del bpy.types.Scene.remesh_properties
        
        # Unregister operators and panels
        bpy.utils.unregister_class(IMAGE_PT_display_panel)
        bpy.utils.unregister_class(OPTION_OT_select)
        bpy.utils.unregister_class(REQUEST_OT_submit)
        bpy.utils.unregister_class(IMAGE_OT_refresh)
        bpy.utils.unregister_class(OPTION_OT_terminate_script)
        bpy.utils.unregister_class(OBJECT_OT_generate_iteration)
        bpy.utils.unregister_class(OBJECT_OT_toggle_remesh)
        bpy.utils.unregister_class(REMESH_PT_settings_panel)
        
        logging.info("Successfully unregistered VIBE panel")
    except Exception as e:
        logging.error(f"Failed to unregister panel: {e}")

# Run register when script is run directly in Blender's text editor
if __name__ == "__main__":
    try:
        # Try to unregister first (in case it's already registered)
        unregister()
    except:
        pass
    register()
    
    # Check for render requests from UI
    check_render_requests() 