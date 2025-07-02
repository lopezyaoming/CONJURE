import bpy
import json
import math
import mathutils
import os
import time
import logging
import bmesh
from bpy.app.handlers import persistent
from pathlib import Path

# Global variables
original_volume = 1.0  # Default value in case calculation fails
view_layer_processed_objects = {}  # Track objects we've already tried to fix
VIEW_LAYER_PROCESS_TIMEOUT = 5.0  # Only try to fix an object's view layer every 5 seconds

# === IMAGE DISPLAY PANEL ===
class IMAGE_PT_reload_all(bpy.types.Operator):
    bl_idname = "image.reload_all"
    bl_label = "Reload All Images"
    bl_description = "Force reload all images from disk"
    
    def execute(self, context):
        # Use absolute path with forward slashes
        image_dir = "C:/CODING/VIBE/VIBE_Massing/output/generated/ImageOptions"
        image_names = ['A.png', 'B.png', 'C.png']
        
        logging.info(f"Reloading images from directory: {image_dir}")
        logging.info(f"Current working directory: {os.getcwd()}")
        
        # First remove existing images
        for img_name in image_names:
            if img_name in bpy.data.images:
                try:
                    bpy.data.images.remove(bpy.data.images[img_name])
                    logging.info(f"Removed existing image: {img_name}")
                except Exception as e:
                    logging.error(f"Error removing image {img_name}: {str(e)}")
        
        # Load fresh copies
        loaded_images = []
        for img_name in image_names:
            img_path = os.path.join(image_dir, img_name)
            logging.info(f"Attempting to load image from: {img_path}")
            
            if os.path.exists(img_path):
                logging.info(f"File exists: {img_path}")
                try:
                    # Try to load image
                    img = bpy.data.images.load(filepath=img_path, check_existing=False)
                    if img:
                        img.name = img_name
                        # Force reload
                        img.reload()
                        # Pack into .blend file
                        if not img.packed_file:
                            img.pack()
                        loaded_images.append(img)
                        logging.info(f"Successfully loaded image: {img_name} (size: {img.size[0]}x{img.size[1]})")
                    else:
                        logging.error(f"Failed to load image {img_name}: load returned None")
                except Exception as e:
                    logging.error(f"Exception loading {img_path}: {str(e)}")
            else:
                logging.error(f"Image file not found: {img_path}")
        
        logging.info(f"Successfully loaded {len(loaded_images)} images")
        logging.info(f"Images in bpy.data.images: {[img.name for img in bpy.data.images]}")
        
        # Force UI refresh
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
                logging.info("Tagged VIEW_3D area for redraw")
            
        return {'FINISHED'}

class IMAGE_PT_display_panel(bpy.types.Panel):
    bl_label = "Generated Images"
    bl_idname = "IMAGE_PT_display_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE Massing'

    def draw(self, context):
        layout = self.layout
        
        # Refresh button in a small row at top
        layout.operator("image.reload_all", text="Refresh All Images", icon='FILE_REFRESH')
        
        # Image directory
        image_dir = "C:/CODING/VIBE/VIBE_Massing/output/generated/ImageOptions"
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
                    
                    # Add a "You like it?" button below each image
                    op = col.operator("option.select", text="You like it?")
                    op.option = img_name.split('.')[0]  # Pass A, B, or C as the option

def register_image_panel():
    try:
        logging.info("Registering image panel...")
        # Clear any existing images first
        for img_name in ['A.png', 'B.png', 'C.png']:
            if img_name in bpy.data.images:
                try:
                    bpy.data.images.remove(bpy.data.images[img_name])
                    logging.info(f"Removed existing image: {img_name}")
                except Exception as e:
                    logging.error(f"Error removing image {img_name}: {str(e)}")
        
        bpy.utils.register_class(IMAGE_PT_reload_all)
        bpy.utils.register_class(IMAGE_PT_display_panel)
        logging.info("Successfully registered image panel classes")
        
        # Try to load images immediately after registration
        try:
            bpy.ops.image.reload_all('EXEC_DEFAULT')
            logging.info("Initial image reload completed")
        except Exception as e:
            logging.error(f"Failed to perform initial image reload: {e}")
            
    except Exception as e:
        logging.error(f"Failed to register image panel: {e}")

def unregister_image_panel():
    try:
        bpy.utils.unregister_class(IMAGE_PT_display_panel)
        bpy.utils.unregister_class(IMAGE_PT_reload_all)
        logging.info("Successfully unregistered image panel")
    except Exception as e:
        logging.error(f"Failed to unregister image panel: {e}")

# === CONFIGURATION ===
LIVE_DATA_FILE = "C:/CODING/VIBE/VIBE_Massing/output/live_hand_data.json"  # JSON file from capture script

# Deformation parameters
FINGER_INFLUENCE_RADIUS = 3.0        
FINGER_FORCE_STRENGTH = 0.55        
ANCHOR_FORCE_MULTIPLIER = 3.0        
MAX_DISPLACEMENT_PER_FRAME = 0.25    
MASS_COHESION_FACTOR = 0.62          
DEFORM_TIMESTEP = 0.05               
VOLUME_LOWER_LIMIT = 0.8             
VOLUME_UPPER_LIMIT = 1.2             

# Velocity-based deformation parameters
VELOCITY_TRACKING_FRAMES = 3         
VELOCITY_MAX_SPEED = 2.0             
VELOCITY_MIN_SPEED = 0.05            
VELOCITY_FORCE_MULTIPLIER = 0.15     
VELOCITY_SMOOTHING = 0.3             
VELOCITY_DIRECTION_WEIGHT = 0.8      

# Smoothing and anchor parameters
SMOOTHING_ALPHA = 0.1       
ROTATION_SPEED = 45

# Radius constants for influence areas
FINGER_AOE_RADIUS = 5.0     
ANCHOR_AOE_RADIUS = 5.0     

# Mapping scales (from normalized space to mesh space)
SCALE_X = 20.0              
SCALE_Y = 20.0              
SCALE_Z = 20.0              

# Debug visualization settings
MAX_FINGERS = 5             
MAX_FINGER_ORBS = 10        
MAX_ANCHOR_ORBS = 10        
ENABLE_DEBUG_ORBS = True    

# Remesh settings
REMESH_TYPES = ["Blocks", "Smooth", "Sharp", "Voxel", "NONE"]
DEFAULT_VOXEL_SIZE = 0.1
DEFAULT_OCTREE_DEPTH = 2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Global list for objects created by this script (for cleanup)
created_objects = []

# Name of the primary mesh that is deformed
DEFORM_OBJ_NAME = "DeformingMesh"

# Render configuration
RENDER_OUTPUT_DIR = r"C:\CODING\VIBE\VIBE_Massing\input\COMFYINPUTS\blenderRender"
RENDER_CAMERA_NAME = "RenderCam"
RENDER_FRAMES = {
    0: "0.png",
    1: "front.png",
    2: "right.png",
    3: "back.png",
    4: "left.png"
}

# === OBJECT INITIALIZATION ===

def ensure_object_exists(name, create_func):
    obj = bpy.data.objects.get(name)
    if not obj:
        logging.info(f"Creating missing object: {name}")
        obj = create_func()
        obj.name = name
    else:
        logging.info(f"Found existing object: {name}")
    return obj

def create_default_mesh():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    update_remesh_modifier(obj, "Blocks")
    return obj

def create_orb_template(radius=0.2, segments=8):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, rings=segments)
    obj = bpy.context.active_object
    if "Orb_Material" not in bpy.data.materials:
        mat = bpy.data.materials.new("Orb_Material")
        mat.diffuse_color = (0.2, 0.8, 1.0, 0.7)
    else:
        mat = bpy.data.materials["Orb_Material"]
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj

def create_anchor_template(radius=0.4, segments=12):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, rings=segments)
    obj = bpy.context.active_object
    if "Anchor_Material" not in bpy.data.materials:
        mat = bpy.data.materials.new("Anchor_Material")
        mat.diffuse_color = (1.0, 0.3, 0.3, 0.8)
    else:
        mat = bpy.data.materials["Anchor_Material"]
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj

def compute_mesh_volume(obj: bpy.types.Object) -> float:
    mesh = obj.data
    volume = 0.0
    for poly in mesh.polygons:
        verts = [obj.matrix_world @ mesh.vertices[i].co for i in poly.vertices]
        for i in range(1, len(verts) - 1):
            v0, v1, v2 = verts[0], verts[i], verts[i+1]
            volume += v0.dot(v1.cross(v2)) / 6.0
    return abs(volume)

def map_to_3d_space(x_norm: float, y_norm: float, z_val: float) -> mathutils.Vector:
    mesh_x = -z_val * SCALE_X
    mesh_y = -(x_norm - 0.5) * SCALE_Y
    mesh_z = (0.5 - y_norm) * SCALE_Z
    return mathutils.Vector((mesh_x, mesh_y, mesh_z))

def map_to_camera_relative_space(x_norm: float, y_norm: float, z_val: float) -> mathutils.Vector:
    """Maps normalized coordinates to 3D space relative to camera view
    
    This function uses the Camera object to ensure mapping is always
    consistent from the user's perspective regardless of environment rotation.
    Includes a 45-degree rotation to the right to better align with user's perspective.
    """
    # Get basic mapping first (standard coordinate conversion)
    point = mathutils.Vector((-z_val * SCALE_X, -(x_norm - 0.5) * SCALE_Y, (0.5 - y_norm) * SCALE_Z))
    
    # Look for the Camera object (not RenderCam)
    camera = bpy.data.objects.get("Camera")
    if camera is not None:
        # Get the camera's world matrix, which includes its position and orientation
        cam_matrix = camera.matrix_world
        
        # Create a coordinate system based on the camera's orientation
        # The camera looks along the -Z axis in its local space
        cam_forward = -cam_matrix.to_3x3().col[2].normalized()  # -Z axis (forward direction)
        cam_right = cam_matrix.to_3x3().col[0].normalized()     # X axis (right direction)
        cam_up = cam_matrix.to_3x3().col[1].normalized()        # Y axis (up direction)
        
        # Apply 45-degree rotation around the camera's up axis (clockwise when looking down)
        angle_rad = math.radians(45)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        
        # Rotate the right and forward vectors around the up vector
        cam_right_rotated = cam_right * cos_angle + cam_forward * sin_angle
        cam_forward_rotated = -cam_right * sin_angle + cam_forward * cos_angle
        
        # Create a new point in camera-relative coordinates with the 45-degree rotation
        cam_relative_point = (
            cam_right_rotated * point.x +    # Right/left of camera (X) with 45° rotation
            cam_up * point.z +               # Above/below camera (Z mapped to Y)
            cam_forward_rotated * point.y    # Forward/back from camera (Y mapped to Z) with 45° rotation
        )
        
        logging.debug(f"Camera-relative mapping with 45° rotation: {point} -> {cam_relative_point}")
        return cam_relative_point
    
    # Fallback to older Env-based rotation if Camera isn't available
    env = bpy.data.objects.get("Env")
    if env is not None:
        # Create rotation matrix from environment's Z rotation
        angle_z = env.rotation_euler.z
        cos_z = math.cos(-angle_z)  # Negative to counteract the rotation
        sin_z = math.sin(-angle_z)
        
        # Apply rotation around Z axis to maintain camera-relative position
        x_rot = point.x * cos_z - point.y * sin_z
        y_rot = point.x * sin_z + point.y * cos_z
        
        return mathutils.Vector((x_rot, y_rot, point.z))
    
    # If neither Camera nor Env exists, return standard mapping
    return point

def recenter_mesh(mesh_obj):
    if not mesh_obj:
        logging.warning("recenter_mesh called with None object")
        return
    
    global view_layer_processed_objects
    current_time = time.time()
    
    # Check if we've tried to process this object recently to avoid flickering
    if mesh_obj.name in view_layer_processed_objects:
        last_process_time = view_layer_processed_objects[mesh_obj.name]
        # Only try again if enough time has passed
        if current_time - last_process_time < VIEW_LAYER_PROCESS_TIMEOUT:
            return
    
    try:
        # First verify the object still exists in bpy.data.objects
        if mesh_obj.name not in bpy.data.objects:
            logging.warning(f"Object {mesh_obj.name} no longer exists in bpy.data.objects")
            return
            
        # Check if the object is in the current view layer
        obj_in_view_layer = False
        for obj in bpy.context.view_layer.objects:
            if obj == mesh_obj:
                obj_in_view_layer = True
                break
        
        if not obj_in_view_layer:
            # Record that we're processing this object now
            view_layer_processed_objects[mesh_obj.name] = current_time
            
            # Try to add the object to the view layer if it's not there
            try:
                # First make sure it's linked to a collection that's in the view layer
                if not mesh_obj.users_collection:
                    bpy.context.scene.collection.objects.link(mesh_obj)
                    logging.info(f"Linked {mesh_obj.name} to scene collection")
                
                # Now ensure it's visible in the view layer
                for col in mesh_obj.users_collection:
                    if col.hide_viewport:
                        col.hide_viewport = False
                        logging.info(f"Made collection {col.name} visible in viewport")
                
                mesh_obj.hide_viewport = False
                logging.info(f"Made {mesh_obj.name} visible in viewport")
                
                # Verify object is now in the view layer
                obj_in_view_layer = False
                for obj in bpy.context.view_layer.objects:
                    if obj == mesh_obj:
                        obj_in_view_layer = True
                        break
                        
                if not obj_in_view_layer:
                    logging.warning(f"Object {mesh_obj.name} still not in view layer after linking attempt")
                    return
            except Exception as e:
                logging.error(f"Could not add {mesh_obj.name} to view layer: {e}")
                return
        
        # Now set as active and recenter
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
        logging.debug(f"Recentered {mesh_obj.name}")
    except Exception as e:
        logging.error(f"Error in recenter_mesh for {mesh_obj.name}: {e}")
        import traceback
        logging.error(traceback.format_exc())

def cleanup_created_objects() -> None:
    global created_objects
    logging.info(f"Cleaning up {len(created_objects)} created objects...")
    for obj in created_objects:
        try:
            if obj and obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        except Exception as e:
            logging.error(f"Error removing object {obj.name if obj else 'None'}: {e}")
    created_objects = []
    patterns = ["fingerOrbs_new", "anchorOrb_new"]
    for obj in list(bpy.data.objects):
        for pattern in patterns:
            if pattern in obj.name:
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception as e:
                    logging.error(f"Error removing pattern object {obj.name}: {e}")
    logging.info("Cleanup complete.")

def update_remesh_modifier(obj, remesh_type):
    if not obj:
        return
    for mod in list(obj.modifiers):
        if mod.type in ['REMESH', 'BEVEL']:
            obj.modifiers.remove(mod)
    if remesh_type != "NONE":
        remesh_mod = obj.modifiers.new(name="Remesh", type='REMESH')
        if remesh_type == "Blocks":
            remesh_mod.mode = 'BLOCKS'
        elif remesh_type == "Voxel":
            remesh_mod.mode = 'VOXEL'
            remesh_mod.voxel_size = DEFAULT_VOXEL_SIZE
        elif remesh_type == "Sharp":
            remesh_mod.mode = 'SHARP'
            remesh_mod.octree_depth = DEFAULT_OCTREE_DEPTH
        elif remesh_type == "Smooth":
            remesh_mod.mode = 'SMOOTH'
            remesh_mod.octree_depth = DEFAULT_OCTREE_DEPTH
            remesh_mod.use_smooth_shade = True
        
        # Ensure "remove_disconnected" is disabled for all remesh types
        try:
            remesh_mod.remove_disconnected = False
            logging.info("Successfully disabled 'remove_disconnected' for remesh modifier")
        except AttributeError:
            try:
                # Alternative attribute name in some Blender versions
                remesh_mod.use_remove_disconnected = False
                logging.info("Successfully disabled 'use_remove_disconnected' for remesh modifier")
            except:
                logging.warning("Could not disable 'remove_disconnected' - property may not exist in this Blender version")
        
        logging.info(f"Remesh updated to type: {remesh_type}")
    else:
        logging.info("Remesh disabled (NONE)")
    bevel_mod = obj.modifiers.new(name="Bevel", type='BEVEL')
    bevel_mod.width = 0.05
    bevel_mod.segments = 5
    bevel_mod.profile = 0.7
    bevel_mod.limit_method = 'NONE'
    bevel_mod.miter_outer = 'MITER_SHARP'
    bevel_mod.offset_type = 'PERCENT'
    bevel_mod.width_pct = 50
    logging.info("Bevel modifier added: width=0.05, segments=5, profile=0.7 (convex), offset_type=PERCENT")

def insert_deformation_keyframe(mesh_obj):
    if not mesh_obj:
        return
    
    global view_layer_processed_objects
    current_time = time.time()
    
    # Check if we've tried to process this object recently to avoid flickering
    if mesh_obj.name in view_layer_processed_objects:
        last_process_time = view_layer_processed_objects[mesh_obj.name]
        # Only try again if enough time has passed
        if current_time - last_process_time < VIEW_LAYER_PROCESS_TIMEOUT:
            return
    
    try:
        # Check if the object is in the current view layer
        obj_in_view_layer = False
        for obj in bpy.context.view_layer.objects:
            if obj == mesh_obj:
                obj_in_view_layer = True
                break
        
        if not obj_in_view_layer:
            # Record that we're processing this object now
            view_layer_processed_objects[mesh_obj.name] = current_time
            
            # Try to add the object to the view layer if it's not there
            try:
                # First make sure it's linked to a collection that's in the view layer
                if not mesh_obj.users_collection:
                    bpy.context.scene.collection.objects.link(mesh_obj)
                    logging.info(f"Linked {mesh_obj.name} to scene collection for keyframing")
                
                # Now ensure it's visible in the view layer
                for col in mesh_obj.users_collection:
                    if col.hide_viewport:
                        col.hide_viewport = False
                        logging.info(f"Made collection {col.name} visible in viewport for keyframing")
                
                mesh_obj.hide_viewport = False
                logging.info(f"Made {mesh_obj.name} visible in viewport for keyframing")
            except Exception as e:
                logging.error(f"Could not add {mesh_obj.name} to view layer for keyframing: {e}")
                return
        
        bpy.context.view_layer.objects.active = mesh_obj
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            mesh_obj.keyframe_insert(data_path="location")
            mesh_obj.keyframe_insert(data_path="rotation_euler")
            mesh_obj.keyframe_insert(data_path="scale")
            logging.debug(f"Inserted keyframes for {mesh_obj.name}")
        except Exception as e:
            logging.error(f"Failed to insert keyframes: {e}")
    except Exception as e:
        logging.error(f"Error in insert_deformation_keyframe for {mesh_obj.name}: {e}")

# Initialize required objects
try:
    # Templates and references for finger movement visualization
    # Ensure we have the necessary objects for our application
    
    # Create objects if needed
    deform_obj = ensure_object_exists(DEFORM_OBJ_NAME, create_default_mesh)
    finger_orb_template = ensure_object_exists("fingerOrb", lambda: create_orb_template())
    anchor_orb_template = ensure_object_exists("anchorOrb", lambda: create_anchor_template())
    
    # Don't recenter during initialization - will be handled by the modal operator
    # with a controlled interval to prevent flickering
    
    finger_orb_template.hide_viewport = True
    anchor_orb_template.hide_viewport = True
    
    try:
        mesh = deform_obj.data
        if mesh and hasattr(mesh, 'vertices') and len(mesh.vertices) > 0:
            original_vertices = [v.co.copy() for v in mesh.vertices]
            calculated_volume = compute_mesh_volume(deform_obj)
            if calculated_volume > 0:
                original_volume = calculated_volume
                logging.info(f"Original mesh volume: {original_volume:.3f}")
            else:
                logging.warning(f"Calculated volume is invalid: {calculated_volume}, using default value of {original_volume}")
        else:
            logging.warning(f"Mesh for {DEFORM_OBJ_NAME} is invalid, using default volume value of {original_volume}")
    except Exception as e:
        logging.error(f"Error calculating original volume: {e}, using default value of {original_volume}")
    
    logging.info("All objects in scene: " + ", ".join(obj.name for obj in bpy.data.objects))
except Exception as e:
    logging.error(f"Error during object initialization: {e}")

# ================================================================
# NEW FUNCTIONALITY: Create a Cube Outside and Then Join It In
# ================================================================

def create_cube_object(fingertips) -> bpy.types.Object:
    """
    Create a new cube object outside DeformingMesh.
    Its corners are positioned at the thumb and pinky fingertips, making
    the cube larger and more directly controlled by hand position.
    """
    if not fingertips or len(fingertips) < 5:
        return None
        
    # Get thumb and pinky positions
    thumb_pos = fingertips[0]
    pinky_pos = fingertips[4]
    thumb_3d = map_to_camera_relative_space(thumb_pos["x"], thumb_pos["y"], thumb_pos["z"])
    pinky_3d = map_to_camera_relative_space(pinky_pos["x"], pinky_pos["y"], pinky_pos["z"])
    
    # Create a cube between these two points
    # First, calculate center and dimensions
    center = (thumb_3d + pinky_3d) / 2.0
    size_vector = thumb_3d - pinky_3d
    size = size_vector.length
    
    # Create cube at center
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    cube = bpy.context.active_object
    
    # Scale and orient the cube to match the fingertips
    if size < 0.001:  # Ensure minimum size
        size = 0.001
        
    # Scale to match the distance between fingers
    cube.scale = (size, size, size)
    
    # Rotate 45 degrees around Z for visual consistency
    cube.rotation_euler.z = math.radians(45)
    cube.name = "Cube"
    
    logging.info(f"Created new cube at {center} with size {size:.4f} and 45° rotation.")
    return cube

def update_cube_object(cube, thumb_tip, pinky_tip):
    """
    Update the cube's size and position dynamically based on the thumb and pinky fingertips.
    The cube will stretch between these two points in 3D space.
    """
    if not cube:
        return
        
    # Get 3D positions of thumb and pinky
    thumb_3d = map_to_camera_relative_space(thumb_tip["x"], thumb_tip["y"], thumb_tip["z"])
    pinky_3d = map_to_camera_relative_space(pinky_tip["x"], pinky_tip["y"], pinky_tip["z"])
    
    # Calculate new center
    new_center = (thumb_3d + pinky_3d) / 2.0
    
    # Calculate size based on distance between fingertips
    size_vector = thumb_3d - pinky_3d
    size = size_vector.length
    
    # Ensure a minimum size
    if size < 0.001:
        size = 0.001
    
    # Update cube location and scale
    cube.location = new_center
    cube.scale = (size, size, size)
    
    # Maintain rotation
    cube.rotation_euler.z = math.radians(45)
    
    logging.info(f"Updated cube: center={new_center}, size={size:.4f}")
    return cube

def join_cube_to_deformingmesh(cube_obj):
    """
    Join the cube object into the DeformingMesh object.
    """
    deform_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
    if not deform_obj or not cube_obj:
        return
    bpy.ops.object.select_all(action='DESELECT')
    deform_obj.select_set(True)
    cube_obj.select_set(True)
    bpy.context.view_layer.objects.active = deform_obj
    bpy.ops.object.join()
    logging.info("Cube joined to DeformingMesh.")

# ================================================================
# REAL-TIME MODAL OPERATOR
# ================================================================

class REALTIME_OT_update_mesh(bpy.types.Operator):
    bl_idname = "wm.realtime_update_mesh"
    bl_label = "Real-time Mesh Update Operator"

    _timer = None

    right_fingertips = None
    left_fingertips = None
    smoothed_right_fingertips = None
    smoothed_left_fingertips = None

    _anchors = []
    smoothed_anchors = []

    mode = "none"        # Modes: none, rotate, deform, scale, create, anchor, remesh, render
    last_command = "none"
    prev_mode = "none"

    deform_active = False
    render_created_objects = []

    rotation_value = 0.0
    rotation_speed = 0.0
    last_rotation_update = 0.0
    last_recenter_time = 0.0  # Track when we last recentered to avoid flickering

    current_scale = mathutils.Vector((1.0, 1.0, 1.0))
    scale_axis = "XYZ"
    scale_start_thumb_z = None

    current_remesh_index = 0
    remesh_last_toggle_time = 0

    finger_orbs = []
    anchor_orbs = []

    prev_right_fingertips = None
    prev_left_fingertips = None
    finger_velocities = None
    last_velocity_update = 0
    use_velocity_forces = True

    # For "create" mode
    create_triggered = False
    created_cube = None

    def anchored_points(self) -> list:
        return self.smoothed_anchors

    def smooth_points(self, new_points, old_points, alpha=SMOOTHING_ALPHA):
        if not old_points or len(old_points) != len(new_points):
            return new_points.copy() if new_points else []
        smoothed = []
        for i, new_point in enumerate(new_points):
            old_point = old_points[i]
            sp = {
                'x': (1.0 - alpha) * old_point['x'] + alpha * new_point['x'],
                'y': (1.0 - alpha) * old_point['y'] + alpha * new_point['y'],
                'z': (1.0 - alpha) * old_point.get('z', 0) + alpha * new_point.get('z', 0)
            }
            smoothed.append(sp)
        return smoothed

    def safely_create_debug_orb(self, template_name):
        global created_objects
        try:
            template = bpy.data.objects.get(template_name)
            if template is None:
                logging.warning(f"Template '{template_name}' not found, creating fallback")
                if "anchor" in template_name.lower():
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, segments=12)
                else:
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, segments=8)
                new_orb = bpy.context.active_object
            else:
                new_orb = template.copy()
                if template.data:
                    new_orb.data = template.data.copy()
                bpy.context.collection.objects.link(new_orb)
            new_orb.hide_viewport = False
            created_objects.append(new_orb)
            return new_orb
        except Exception as e:
            logging.error(f"Error creating debug orb: {e}")
            try:
                size = 0.6 if "anchor" in template_name.lower() else 0.3
                bpy.ops.mesh.primitive_cube_add(size=size)
                new_orb = bpy.context.active_object
                created_objects.append(new_orb)
                return new_orb
            except Exception as e2:
                logging.error(f"Fallback cube creation failed: {e2}")
                return None

    def update_fixed_debug_orbs(self, mapped_points, orb_list, template_name, max_count, color=None):
        try:
            if not orb_list:
                logging.info(f"Creating {max_count} debug orbs for {template_name}")
                for _ in range(max_count):
                    new_orb = self.safely_create_debug_orb(template_name)
                    if new_orb:
                        if color and new_orb.material_slots and len(new_orb.material_slots) > 0:
                            if new_orb.material_slots[0].material:
                                new_orb.material_slots[0].material.diffuse_color = color
                        orb_list.append(new_orb)
            if len(orb_list) < max_count:
                additional_needed = max_count - len(orb_list)
                logging.info(f"Need {additional_needed} more orbs for {template_name}")
                for _ in range(additional_needed):
                    new_orb = self.safely_create_debug_orb(template_name)
                    if new_orb:
                        orb_list.append(new_orb)
            for i, orb in enumerate(orb_list):
                if i < len(mapped_points) and orb:
                    try:
                        orb.location = mapped_points[i]
                        orb.hide_viewport = False
                    except Exception as ex:
                        logging.error(f"Error setting orb {i} position: {ex}")
                elif orb:
                    orb.hide_viewport = True
        except Exception as e:
            logging.error(f"Error updating debug orbs: {e}")

    def rotate_mesh(self, angle_degrees):
        angle_radians = math.radians(angle_degrees)
        rotation_matrix = mathutils.Matrix.Rotation(angle_radians, 4, 'Z')
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        mesh = mesh_obj.data
        for i, v in enumerate(mesh.vertices):
            original_pos = original_vertices[i]
            v.co = rotation_matrix @ original_pos
        mesh.update()
        recenter_mesh(mesh_obj)
        insert_deformation_keyframe(mesh_obj)

    def calculate_finger_velocities(self, current_fingertips, previous_fingertips, delta_time):
        if not current_fingertips or not previous_fingertips or len(current_fingertips) != len(previous_fingertips):
            return [mathutils.Vector((0, 0, 0)) for _ in range(len(current_fingertips) if current_fingertips else 0)]
        velocities = []
        for i, (curr, prev) in enumerate(zip(current_fingertips, previous_fingertips)):
            curr_pos = map_to_camera_relative_space(curr["x"], curr["y"], curr["z"])
            prev_pos = map_to_camera_relative_space(prev["x"], prev["y"], prev["z"])
            if delta_time > 0:
                velocity = (curr_pos - prev_pos) / delta_time
            else:
                velocity = mathutils.Vector((0, 0, 0))
            speed = velocity.length
            if speed > VELOCITY_MAX_SPEED:
                velocity = velocity.normalized() * VELOCITY_MAX_SPEED
            if speed < VELOCITY_MIN_SPEED:
                velocity = mathutils.Vector((0, 0, 0))
            velocities.append(velocity)
        if self.finger_velocities and len(self.finger_velocities) == len(velocities):
            for i, (curr_vel, prev_vel) in enumerate(zip(velocities, self.finger_velocities)):
                velocities[i] = curr_vel * VELOCITY_SMOOTHING + prev_vel * (1 - VELOCITY_SMOOTHING)
        return velocities

    def create_render_copy(self):
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.error("DeformingMesh not found, cannot create render copy")
            return None
        try:
            render_copy = mesh_obj.copy()
            if mesh_obj.data:
                render_copy.data = mesh_obj.data.copy()
            render_copy.name = f"Render_{len(self.render_created_objects):03d}"
            bpy.context.collection.objects.link(render_copy)
            render_copy.location = mesh_obj.location.copy()
            render_copy.rotation_euler = mesh_obj.rotation_euler.copy()
            render_copy.scale = mesh_obj.scale.copy()
            self.render_created_objects.append(render_copy)
            logging.info(f"Created render copy: {render_copy.name}")
            return render_copy
        except Exception as e:
            logging.error(f"Error creating render copy: {e}")
            return None

    def deform_mesh_with_velocity(self, fingertips, velocities, anchors=None):
        if not fingertips or not velocities:
            return
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        mesh = mesh_obj.data
        if not mesh:
            logging.error(f"Mesh data for {DEFORM_OBJ_NAME} is None")
            return
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        finger_points = []
        for tip in fingertips:
            # Always use camera-relative mapping for consistent experience
            pos = map_to_camera_relative_space(tip["x"], tip["y"], tip["z"])
            finger_points.append(pos)
        anchor_points = []
        if anchors:
            for anchor in anchors:
                # Always use camera-relative mapping for consistent experience
                pos = map_to_camera_relative_space(anchor["x"], anchor["y"], anchor["z"])
                anchor_points.append(pos)
        if ENABLE_DEBUG_ORBS:
            self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
            self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
        def smooth_falloff(distance, radius):
            if distance >= radius:
                return 0.0
            normalized = distance / radius
            return (1.0 - normalized**2)**2
        world_matrix = mesh_obj.matrix_world
        world_matrix_inv = world_matrix.inverted()
        vertex_displacements = {}
        for v in bm.verts:
            v_world = world_matrix @ v.co
            net_displacement = mathutils.Vector((0, 0, 0))
            for finger_pos in finger_points:
                to_finger = finger_pos - v_world
                dist = to_finger.length
                if dist < FINGER_INFLUENCE_RADIUS:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS)
                    direction = to_finger.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH
                    net_displacement += force
            for anchor_pos in anchor_points:
                to_anchor = anchor_pos - v_world
                dist = to_anchor.length
                if dist < FINGER_INFLUENCE_RADIUS * 1.2:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS * 1.2)
                    direction = to_anchor.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH * ANCHOR_FORCE_MULTIPLIER
                    net_displacement += force
            if net_displacement.length > 0.0001:
                if net_displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                    net_displacement = net_displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
                vertex_displacements[v.index] = net_displacement
            else:
                vertex_displacements[v.index] = mathutils.Vector((0, 0, 0))
        smoothed_displacements = {}
        for v in bm.verts:
            if v.index not in vertex_displacements:
                continue
            original_displacement = vertex_displacements[v.index]
            neighbor_verts = [e.other_vert(v) for e in v.link_edges]
            if not neighbor_verts:
                smoothed_displacements[v.index] = original_displacement
                continue
            neighbor_avg = mathutils.Vector((0, 0, 0))
            for nv in neighbor_verts:
                if nv.index in vertex_displacements:
                    neighbor_avg += vertex_displacements[nv.index]
            if len(neighbor_verts) > 0:
                neighbor_avg /= len(neighbor_verts)
            smoothed_displacement = original_displacement.lerp(neighbor_avg, MASS_COHESION_FACTOR)
            smoothed_displacements[v.index] = smoothed_displacement
        for v in bm.verts:
            if v.index in smoothed_displacements:
                v_world = world_matrix @ v.co
                v_world += smoothed_displacements[v.index] * DEFORM_TIMESTEP
                v.co = world_matrix_inv @ v_world
        bm.to_mesh(mesh)
        mesh.update()
        
        try:
            current_volume = compute_mesh_volume(mesh_obj)
            volume_ratio = current_volume / original_volume
            logging.debug(f"Current volume: {current_volume:.3f}, Ratio: {volume_ratio:.3f}")
            
            if volume_ratio < VOLUME_LOWER_LIMIT or volume_ratio > VOLUME_UPPER_LIMIT:
                if volume_ratio < VOLUME_LOWER_LIMIT:
                    target_ratio = VOLUME_LOWER_LIMIT
                    logging.debug(f"Volume too small: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                else:
                    target_ratio = VOLUME_UPPER_LIMIT
                    logging.debug(f"Volume too large: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                scale_factor = (target_ratio / volume_ratio) ** (1/3)
                bm_corrected = bmesh.new()
                bm_corrected.from_mesh(mesh)
                total = mathutils.Vector((0, 0, 0))
                for v in bm_corrected.verts:
                    total += v.co
                centroid = total / len(bm_corrected.verts)
                for v in bm_corrected.verts:
                    v.co = centroid + (v.co - centroid) * scale_factor
                bm_corrected.to_mesh(mesh)
                mesh.update()
                bm_corrected.free()
                
                corrected_volume = compute_mesh_volume(mesh_obj)
                corrected_ratio = corrected_volume / original_volume
                logging.debug(f"Volume after correction: {corrected_volume:.3f}, Ratio: {corrected_ratio:.3f}")
        except Exception as e:
            logging.error(f"Error during volume calculations/correction: {e}")
        
        recenter_mesh(mesh_obj)
        bm.free()
        insert_deformation_keyframe(mesh_obj)

    def scale_mesh(self, fingertips, axis="XYZ"):
        if not fingertips or len(fingertips) < 5:
            return
            
        # Get thumb position and ring finger position
        thumb_pos = fingertips[0]
        ring_pos = fingertips[3]
        
        # Always use camera-relative coordinates for calculations
        thumb_3d = map_to_camera_relative_space(thumb_pos["x"], thumb_pos["y"], thumb_pos["z"])
        ring_3d = map_to_camera_relative_space(ring_pos["x"], ring_pos["y"], ring_pos["z"])
        
        # Store initial thumb z position when entering scale mode
        if self.prev_mode != "scale" and self.mode == "scale":
            self.scale_start_thumb_z = thumb_3d.z
            logging.info(f"Scale mode entered, reference z: {self.scale_start_thumb_z:.4f}")
        
        # If we have a reference z position, use it to calculate the scale factor
        if hasattr(self, 'scale_start_thumb_z'):
            # Calculate scale factor based on relative change in z position
            # This makes scaling more intuitive and less sensitive
            z_diff = abs(thumb_3d.z - self.scale_start_thumb_z)
            # Use a slower scaling factor (2.0 instead of 5.0)
            scale_factor = 1.0 + (z_diff * 2.0)
            
            # Cap the scale factor at 3.0 to prevent excessive scaling
            scale_factor = min(scale_factor, 3.0)
        else:
            # Fallback to distance-based scaling with reduced sensitivity
            distance = (thumb_3d - ring_3d).length
            scale_factor = 1.0 + (distance * 2.0)
            scale_factor = min(scale_factor, 3.0)
        
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        
        new_scale = mesh_obj.scale.copy()
        if axis == "X" or axis == "XYZ":
            new_scale.x = scale_factor
        if axis == "Y" or axis == "XYZ":
            new_scale.y = scale_factor
        if axis == "Z" or axis == "XYZ":
            new_scale.z = scale_factor
        
        mesh_obj.scale = new_scale
        self.current_scale = new_scale
        self.scale_axis = axis
        
        # Add visual feedback for scale factor
        # Update finger orb colors to show scale intensity (blue->green->yellow->red)
        if ENABLE_DEBUG_ORBS and self.finger_orbs:
            # Normalize the scale factor to 0-1 range (1.0 to 3.0 becomes 0.0 to 1.0)
            norm_scale = (scale_factor - 1.0) / 2.0
            # Create color gradient based on scale factor: blue -> green -> yellow -> red
            if norm_scale < 0.33:
                # Blue to green (0.0 - 0.33)
                sub_norm = norm_scale / 0.33
                color = (0.0, sub_norm, 1.0, 0.7)
            elif norm_scale < 0.66:
                # Green to yellow (0.33 - 0.66)
                sub_norm = (norm_scale - 0.33) / 0.33
                color = (sub_norm, 1.0, 1.0 - sub_norm, 0.7)
            else:
                # Yellow to red (0.66 - 1.0)
                sub_norm = (norm_scale - 0.66) / 0.34
                color = (1.0, 1.0 - sub_norm, 0.0, 0.7)
            
            # Apply color to finger orbs to give visual feedback
            for orb in self.finger_orbs:
                if orb.material_slots and orb.material_slots[0].material:
                    orb.material_slots[0].material.diffuse_color = color
        
        # Display scale factor as text in 3D view
        self.display_scale_info(scale_factor, axis)
        
        recenter_mesh(mesh_obj)
        logging.info(f"Applied scale: {new_scale} on axis {axis}, factor: {scale_factor:.2f}")
        insert_deformation_keyframe(mesh_obj)

    def apply_scale(self):
        """Apply the current scale to the mesh object, resetting scale to 1"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return False
            
        try:
            # Select the object and make it active
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj
            
            # Apply scale
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            
            # Update original vertices reference after applying scale
            global original_vertices
            original_vertices = [v.co.copy() for v in mesh_obj.data.vertices]
            
            logging.info("Scale applied to mesh object")
            return True
        except Exception as e:
            logging.error(f"Failed to apply scale: {e}")
            return False

    def display_scale_info(self, scale_factor, axis):
        """Display scale information temporarily in the 3D view"""
        # Create or update text object in 3D view
        text_name = "ScaleInfo"
        text_obj = bpy.data.objects.get(text_name)
        
        if text_obj is None:
            # Create text object if it doesn't exist
            if "Text" not in bpy.data.curves:
                text_data = bpy.data.curves.new(name="Text", type='FONT')
            else:
                text_data = bpy.data.curves["Text"]
            
            text_obj = bpy.data.objects.new(text_name, text_data)
            bpy.context.collection.objects.link(text_obj)
            
            # Position in top-right of view
            text_obj.location = (-5, 0, 8)
            text_obj.scale = (0.5, 0.5, 0.5)
            
            # Set color and alignment
            text_data.body_format[0].use_bold = True
            if not text_obj.material_slots:
                mat = bpy.data.materials.new(name="TextMaterial")
                text_obj.data.materials.append(mat)
                mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
        
        # Update text content
        text_obj.data.body = f"Scale: {scale_factor:.2f}x [{axis}]"
        
        # Make visible
        text_obj.hide_viewport = False
        
        # Schedule hiding after delay (will be updated continuously while in scale mode)
        self.scale_info_shown_time = time.time()

    def apply_sculpt_brush(self, fingertips, brush_type="GRAB"):
        """Map finger movements directly to Blender's sculpt brushes"""
        if not fingertips or len(fingertips) < 5:
            return
            
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
            
        # Switch to sculpt mode
        bpy.context.view_layer.objects.active = mesh_obj
        if bpy.context.mode != 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')
            
        # Get the sculpt brush
        brush = bpy.context.tool_settings.sculpt.brush
        
        # Set the brush type based on finger position or a predefined mapping
        # For example, we could determine brush type by how many fingers are extended
        brush.sculpt_tool = brush_type
        
        # Calculate brush size based on distance between thumb and pinky
        if len(fingertips) >= 5:
            thumb_pos = fingertips[0]
            pinky_pos = fingertips[4]
            distance = math.sqrt(
                (thumb_pos["x"] - pinky_pos["x"]) ** 2 +
                (thumb_pos["y"] - pinky_pos["y"]) ** 2 +
                (thumb_pos["z"] - pinky_pos["z"]) ** 2
            )
            # Map the distance to a reasonable brush size range (5-50)
            brush_size = 5 + distance * 45
            brush.size = int(min(max(brush_size, 5), 50))
            
            # Calculate brush strength based on z-position (depth)
            # Deeper hand position = stronger brush effect
            avg_z = sum(tip["z"] for tip in fingertips) / len(fingertips)
            # Map z to a reasonable strength range (0.1-1.0)
            strength = 0.1 + avg_z * 0.9
            brush.strength = min(max(strength, 0.1), 1.0)
            
            logging.info(f"Sculpt brush applied: {brush_type}, size={brush.size}, strength={brush.strength:.2f}")
            
    def toggle_dynamic_topology(self):
        """Enable/disable dynamic topology for adaptive mesh detail"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
            
        # Switch to sculpt mode
        bpy.context.view_layer.objects.active = mesh_obj
        if bpy.context.mode != 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')
            
        # Toggle dynamic topology
        try:
            if not hasattr(mesh_obj, "use_dynamic_topology_sculpting"):
                # In newer Blender versions, we need to check the scene settings
                if not bpy.context.scene.tool_settings.sculpt.use_dyntopo:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    logging.info("Dynamic topology enabled")
                else:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    logging.info("Dynamic topology disabled")
            else:
                # In older Blender versions
                if not mesh_obj.use_dynamic_topology_sculpting:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    logging.info("Dynamic topology enabled")
                else:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    
            # Configure dynamic topology settings
            if hasattr(bpy.context.scene.tool_settings.sculpt, "detail_type_method"):
                bpy.context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
                bpy.context.scene.tool_settings.sculpt.constant_detail = 12
                logging.info("Dynamic topology detail set to 12")
                
        except Exception as e:
            logging.error(f"Error toggling dynamic topology: {e}")
    
    def determine_brush_type(self, fingertips):
        """Determine sculpt brush type based on finger positions"""
        if not fingertips or len(fingertips) < 5:
            return "GRAB"  # Default brush
            
        # Count extended fingers (fingers that are straightened)
        # A simple heuristic: if finger tip's y position is less than thumb's y position,
        # the finger is considered extended
        thumb_y = fingertips[0]["y"]
        extended_count = sum(1 for tip in fingertips[1:] if tip["y"] < thumb_y)
        
        # Map extended fingers count to brush types
        brush_map = {
            0: "GRAB",     # Fist (no fingers extended) = grab brush
            1: "CLAY",     # One finger extended = clay brush
            2: "SMOOTH",   # Two fingers extended = smooth brush
            3: "CREASE",   # Three fingers extended = crease brush
            4: "FLATTEN"   # Four fingers extended = flatten brush
        }
        
        brush_type = brush_map.get(extended_count, "GRAB")
        logging.debug(f"Detected {extended_count} extended fingers, selected brush: {brush_type}")
        return brush_type
    
    def multi_select_objects(self, left_fingertips, right_fingertips):
        """Select multiple objects with bimanual gestures"""
        if not left_fingertips or not right_fingertips:
            return
            
        # Use index fingers of both hands to define a selection box
        left_index = left_fingertips[1]
        right_index = right_fingertips[1]
        
        # Map to 3D space with camera-relative coordinates
        left_pos = map_to_camera_relative_space(left_index["x"], left_index["y"], left_index["z"])
        right_pos = map_to_camera_relative_space(right_index["x"], right_index["y"], right_index["z"])
        
        # Calculate min/max coordinates to define a selection box
        min_x = min(left_pos.x, right_pos.x)
        max_x = max(left_pos.x, right_pos.x)
        min_y = min(left_pos.y, right_pos.y)
        max_y = max(left_pos.y, right_pos.y)
        min_z = min(left_pos.z, right_pos.z)
        max_z = max(left_pos.z, right_pos.z)
        
        # Ensure the box has some minimum size
        min_size = 0.5
        if max_x - min_x < min_size:
            center_x = (max_x + min_x) / 2
            min_x = center_x - min_size/2
            max_x = center_x + min_size/2
        if max_y - min_y < min_size:
            center_y = (max_y + min_y) / 2
            min_y = center_y - min_size/2
            max_y = center_y + min_size/2
        if max_z - min_z < min_size:
            center_z = (max_z + min_z) / 2
            min_z = center_z - min_size/2
            max_z = center_z + min_size/2
        
        # Deselect all objects first
        bpy.ops.object.select_all(action='DESELECT')
        
        # Find objects that intersect with the selection box
        for obj in bpy.context.visible_objects:
            if obj.type != 'MESH':
                continue
                
            # Check if object's bounding box intersects with our selection box
            obj_bb = obj.bound_box
            obj_min = mathutils.Vector((min(v[0] for v in obj_bb), min(v[1] for v in obj_bb), min(v[2] for v in obj_bb)))
            obj_max = mathutils.Vector((max(v[0] for v in obj_bb), max(v[1] for v in obj_bb), max(v[2] for v in obj_bb)))
            
            # Transform to world space
            obj_min = obj.matrix_world @ obj_min
            obj_max = obj.matrix_world @ obj_max
            
            # Check for intersection (simple AABB test)
            if (obj_min.x <= max_x and obj_max.x >= min_x and
                obj_min.y <= max_y and obj_max.y >= min_y and
                obj_min.z <= max_z and obj_max.z >= min_z):
                obj.select_set(True)
        
        # Set active object to any selected object
        selected_objects = bpy.context.selected_objects
        if selected_objects:
            bpy.context.view_layer.objects.active = selected_objects[0]
            logging.info(f"Selected {len(selected_objects)} objects with selection box")
        else:
            logging.info("No objects found within selection box")
            
    def apply_boolean_operation(self, operation="UNION"):
        """Apply boolean operation between selected objects"""
        selected_objects = bpy.context.selected_objects
        if len(selected_objects) < 2:
            logging.warning("Need at least 2 selected objects for boolean operation")
            return
            
        # The active object will be the target
        target = bpy.context.active_object
        if target not in selected_objects:
            target = selected_objects[0]
            bpy.context.view_layer.objects.active = target
            
        # All other selected objects will be the operands
        operands = [obj for obj in selected_objects if obj != target]
        
        # Apply boolean modifiers
        for operand in operands:
            bool_mod = target.modifiers.new(name="Boolean", type='BOOLEAN')
            bool_mod.operation = operation
            bool_mod.object = operand
            
            try:
                # Apply the modifier
                bpy.ops.object.modifier_apply(modifier=bool_mod.name)
                # Hide the operand after applying boolean
                operand.hide_viewport = True
                logging.info(f"Applied {operation} boolean with {operand.name}")
            except Exception as e:
                logging.error(f"Boolean operation failed: {e}")
                
    def duplicate_object(self, fingertips):
        """Create a duplicate of the selected object at the new finger position"""
        try:
            # Get active object
            active_obj = bpy.context.active_object
            if not active_obj:
                logging.warning("No active object to duplicate")
                return None
            
            # Create a duplicate
            bpy.ops.object.duplicate_move()
            duplicate_obj = bpy.context.active_object
            
            # Move the duplicate based on thumb position
            thumb_pos = fingertips[0]
            thumb_3d = map_to_camera_relative_space(thumb_pos["x"], thumb_pos["y"], thumb_pos["z"])
            
            # Calculate offset based on original location and thumb position
            offset = thumb_3d - active_obj.location
            duplicate_obj.location = active_obj.location + offset
            
            logging.info(f"Duplicated {active_obj.name} to {duplicate_obj.name}")
            return duplicate_obj
        except Exception as e:
            logging.error(f"Object duplication failed: {e}")
            return None

    def create_new_object(self, fingertips):
        """Create a new cube object based on finger positions.
        
        When the user enters create mode, a cube is created between thumb and pinky.
        As the user moves their hand in create mode, the cube is dynamically updated.
        The cube is only joined to DeformingMesh when the user exits create mode.
        """
        if not fingertips or len(fingertips) < 5:
            return
            
        if not self.create_triggered:
            # Create a new cube between thumb and pinky positions
            new_cube = create_cube_object(fingertips)
            self.created_cube = new_cube
            
            if new_cube:
                # Mark as triggered so we don't create multiple cubes while in create mode
                self.create_triggered = True
                logging.info("Created new cube, ready for positioning")
        elif self.created_cube:
            # Update the cube's size and position based on thumb and pinky
            update_cube_object(self.created_cube, 
                             fingertips[0], 
                             fingertips[4])
            logging.debug("Updated cube position and size")

    def join_created_cube(self):
        """Join the created cube into the DeformingMesh object when exiting create mode."""
        if self.created_cube is None:
            return
            
        try:
            bpy.ops.object.select_all(action='DESELECT')
            deform_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
            if deform_obj and self.created_cube:
                deform_obj.select_set(True)
                self.created_cube.select_set(True)
                bpy.context.view_layer.objects.active = deform_obj
                bpy.ops.object.join()
                logging.info("Cube joined to DeformingMesh.")
                self.created_cube = None
                
                # Update original vertices reference after joining
                global original_vertices
                if deform_obj:
                    original_vertices = [v.co.copy() for v in deform_obj.data.vertices]
                    logging.info(f"Updated original_vertices reference with {len(original_vertices)} vertices")
        except Exception as e:
            logging.error(f"Failed to join cube: {e}")
            self.created_cube = None

    def cycle_remesh_type(self):
        self.current_remesh_index = (self.current_remesh_index + 1) % len(REMESH_TYPES)
        new_type = REMESH_TYPES[self.current_remesh_index]
        mesh_obj = bpy.data.objects.get("DeformingMesh")
        if mesh_obj:
            update_remesh_modifier(mesh_obj, new_type)
        logging.info(f"Switched remesh type to: {new_type}")
        return new_type
        
    def assign_material_to_selection(self, material_index=0):
        """Assign materials to vertices under influence of hand gestures"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj or not mesh_obj.data:
            logging.warning("No mesh object available for material assignment")
            return
            
        # Ensure object has materials
        if len(mesh_obj.data.materials) == 0:
            # Create default materials if none exist
            self.create_default_materials(mesh_obj)
            
        # Cap the material index to valid range
        material_index = min(material_index, len(mesh_obj.data.materials) - 1)
        if material_index < 0:
            logging.warning("Invalid material index")
            return
            
        # Switch to Edit mode for vertex selection
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
            
        # Use the currently influenced vertices for material assignment
        # This leverages the same vertex selection logic as in deformation
        mesh = mesh_obj.data
        bpy.ops.mesh.select_all(action='DESELECT')
        
        # Get current selection
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        
        # Select faces under influence (simplified example - would need to tie into deformation)
        for face in bm.faces:
            # Check if face is under hand influence - simplified example!
            # In a real implementation, use the same logic as your deformation system
            face.select = True
            
        # Assign selected faces to material
        if hasattr(bpy.context, 'object') and hasattr(bpy.context.object, 'active_material_index'):
            bpy.context.object.active_material_index = material_index
            bpy.ops.object.material_slot_assign()
            logging.info(f"Assigned material {material_index} to selected faces")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)
    
    def create_default_materials(self, obj):
        """Create a set of default materials for the object"""
        # Create some default materials with different colors
        materials = [
            ("Material_Red", (1.0, 0.1, 0.1, 1.0)),
            ("Material_Green", (0.1, 0.8, 0.1, 1.0)),
            ("Material_Blue", (0.1, 0.1, 0.8, 1.0)),
            ("Material_Yellow", (0.9, 0.9, 0.1, 1.0)),
            ("Material_White", (0.9, 0.9, 0.9, 1.0))
        ]
        
        # Create and assign materials
        for mat_name, color in materials:
            # Check if material already exists
            if mat_name in bpy.data.materials:
                mat = bpy.data.materials[mat_name]
            else:
                # Create new material
                mat = bpy.data.materials.new(name=mat_name)
                mat.diffuse_color = color
                
            # Append material to object
            if obj.data.materials:
                obj.data.materials.append(mat)
            else:
                obj.data.materials[0] = mat
                
        logging.info(f"Created {len(materials)} default materials for {obj.name}")
    
    def precise_scale(self, axis, value):
        """Apply precise numerical scaling based on voice commands"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for precise scaling")
            return
            
        # Ensure value is within reasonable range
        value = min(max(value, 0.01), 10.0)
        
        # Apply scaling based on axis
        if axis.upper() == "X":
            mesh_obj.scale.x = value
            logging.info(f"Set X scale to {value}")
        elif axis.upper() == "Y":
            mesh_obj.scale.y = value
            logging.info(f"Set Y scale to {value}")
        elif axis.upper() == "Z":
            mesh_obj.scale.z = value
            logging.info(f"Set Z scale to {value}")
        elif axis.upper() == "XYZ" or axis.upper() == "ALL":
            mesh_obj.scale = (value, value, value)
            logging.info(f"Set uniform scale to {value}")
        else:
            logging.warning(f"Unknown axis {axis} for precise scaling")
            
        # Update transformation
        recenter_mesh(mesh_obj)
        insert_deformation_keyframe(mesh_obj)
        
    def enable_snapping(self, snap_type="INCREMENT"):
        """Toggle different snapping modes with gestures"""
        valid_types = {"INCREMENT", "VERTEX", "EDGE", "FACE", "VOLUME", "EDGE_MIDPOINT", "EDGE_PERPENDICULAR"}
        
        if snap_type not in valid_types:
            snap_type = "INCREMENT"
            
        # Toggle snapping
        bpy.context.scene.tool_settings.use_snap = not bpy.context.scene.tool_settings.use_snap
        
        # If enabling, set the snap type
        if bpy.context.scene.tool_settings.use_snap:
            # Clear current snap elements
            for snap_elem in {'INCREMENT', 'VERTEX', 'EDGE', 'FACE', 'VOLUME', 'EDGE_MIDPOINT', 'EDGE_PERPENDICULAR'}:
                if hasattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_elem.lower()}"):
                    setattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_elem.lower()}", False)
            
            # Set the requested snap element
            if hasattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_type.lower()}"):
                setattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_type.lower()}", True)
            else:
                # For older Blender versions
                bpy.context.scene.tool_settings.snap_element = snap_type
                
            logging.info(f"Snapping enabled with type: {snap_type}")
        else:
            logging.info("Snapping disabled")

    def extrude_selection(self, direction, distance=1.0):
        """Extrude selected faces in specified direction"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for extrusion")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in face selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        
        # Perform the extrusion
        try:
            # First extrude
            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={
                    "value": (
                        direction.x * distance,
                        direction.y * distance, 
                        direction.z * distance
                    )
                }
            )
            logging.info(f"Extruded faces by distance {distance}")
        except Exception as e:
            logging.error(f"Extrusion failed: {e}")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)
        
    def inset_faces(self, amount=0.1):
        """Inset selected faces"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for inset")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in face selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        
        # Perform the inset
        try:
            bpy.ops.mesh.inset(thickness=amount, depth=0)
            logging.info(f"Inset faces with thickness {amount}")
        except Exception as e:
            logging.error(f"Inset failed: {e}")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)

    def smooth_edge_flow(self, iterations=5):
        """Apply edge flow smoothing to selected edges"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for edge flow smoothing")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in edge selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)
        
        # Check if LoopTools is enabled
        if hasattr(bpy.ops, 'mesh') and hasattr(bpy.ops.mesh, 'looptools_relax'):
            try:
                bpy.ops.mesh.looptools_relax(
                    input='selected', 
                    interpolation='cubic',
                    iterations=iterations,
                    regular=True
                )
                logging.info(f"Applied edge flow smoothing with {iterations} iterations")
            except Exception as e:
                logging.error(f"Edge flow smoothing failed: {e}")
        else:
            # Fallback to Blender's native smooth
            try:
                bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=iterations)
                logging.info(f"Applied fallback smoothing with {iterations} iterations")
            except Exception as e:
                logging.error(f"Fallback smoothing failed: {e}")
                
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)
        
    def bridge_edge_loops(self):
        """Connect selected edge loops"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for bridge loops")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in edge selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)
        
        # Perform the bridge
        try:
            bpy.ops.mesh.bridge_edge_loops()
            logging.info("Bridge edge loops applied")
        except Exception as e:
            logging.error(f"Bridge edge loops failed: {e}")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)

    def read_live_data(self):
        if not os.path.exists(LIVE_DATA_FILE):
            logging.debug(f"Live data file not found at {LIVE_DATA_FILE}")
            return {}
        try:
            with open(LIVE_DATA_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    logging.debug("Live data file exists but is empty")
                    return {}
                return json.loads(content)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
        except Exception as e:
            logging.error(f"Error reading live data: {e}")
        return {}

    def deform_mesh(self, fingertips, anchors=None):
        """Deform the mesh based on finger positions without velocity information"""
        if not fingertips:
            return
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        mesh = mesh_obj.data
        if not mesh:
            logging.error(f"Mesh data for {DEFORM_OBJ_NAME} is None")
            return
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        finger_points = []
        for tip in fingertips:
            # Always use camera-relative mapping for consistent experience
            pos = map_to_camera_relative_space(tip["x"], tip["y"], tip["z"])
            finger_points.append(pos)
        anchor_points = []
        if anchors:
            for anchor in anchors:
                # Always use camera-relative mapping for consistent experience
                pos = map_to_camera_relative_space(anchor["x"], anchor["y"], anchor["z"])
                anchor_points.append(pos)
        if ENABLE_DEBUG_ORBS:
            self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
            self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
        def smooth_falloff(distance, radius):
            if distance >= radius:
                return 0.0
            normalized = distance / radius
            return (1.0 - normalized**2)**2
        world_matrix = mesh_obj.matrix_world
        world_matrix_inv = world_matrix.inverted()
        vertex_displacements = {}
        for v in bm.verts:
            v_world = world_matrix @ v.co
            net_displacement = mathutils.Vector((0, 0, 0))
            for finger_pos in finger_points:
                to_finger = finger_pos - v_world
                dist = to_finger.length
                if dist < FINGER_INFLUENCE_RADIUS:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS)
                    direction = to_finger.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH
                    net_displacement += force
            for anchor_pos in anchor_points:
                to_anchor = anchor_pos - v_world
                dist = to_anchor.length
                if dist < FINGER_INFLUENCE_RADIUS * 1.2:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS * 1.2)
                    direction = to_anchor.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH * ANCHOR_FORCE_MULTIPLIER
                    net_displacement += force
            if net_displacement.length > 0.0001:
                if net_displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                    net_displacement = net_displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
                vertex_displacements[v.index] = net_displacement
            else:
                vertex_displacements[v.index] = mathutils.Vector((0, 0, 0))
        smoothed_displacements = {}
        for v in bm.verts:
            if v.index not in vertex_displacements:
                continue
            original_displacement = vertex_displacements[v.index]
            neighbor_verts = [e.other_vert(v) for e in v.link_edges]
            if not neighbor_verts:
                smoothed_displacements[v.index] = original_displacement
                continue
            neighbor_avg = mathutils.Vector((0, 0, 0))
            for nv in neighbor_verts:
                if nv.index in vertex_displacements:
                    neighbor_avg += vertex_displacements[nv.index]
            if len(neighbor_verts) > 0:
                neighbor_avg /= len(neighbor_verts)
            smoothed_displacement = original_displacement.lerp(neighbor_avg, MASS_COHESION_FACTOR)
            smoothed_displacements[v.index] = smoothed_displacement
        for v in bm.verts:
            if v.index in smoothed_displacements:
                v_world = world_matrix @ v.co
                v_world += smoothed_displacements[v.index] * DEFORM_TIMESTEP
                v.co = world_matrix_inv @ v_world
        bm.to_mesh(mesh)
        mesh.update()
        
        try:
            current_volume = compute_mesh_volume(mesh_obj)
            volume_ratio = current_volume / original_volume
            logging.debug(f"Current volume: {current_volume:.3f}, Ratio: {volume_ratio:.3f}")
            
            if volume_ratio < VOLUME_LOWER_LIMIT or volume_ratio > VOLUME_UPPER_LIMIT:
                if volume_ratio < VOLUME_LOWER_LIMIT:
                    target_ratio = VOLUME_LOWER_LIMIT
                    logging.debug(f"Volume too small: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                else:
                    target_ratio = VOLUME_UPPER_LIMIT
                    logging.debug(f"Volume too large: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                scale_factor = (target_ratio / volume_ratio) ** (1/3)
                bm_corrected = bmesh.new()
                bm_corrected.from_mesh(mesh)
                total = mathutils.Vector((0, 0, 0))
                for v in bm_corrected.verts:
                    total += v.co
                centroid = total / len(bm_corrected.verts)
                for v in bm_corrected.verts:
                    v.co = centroid + (v.co - centroid) * scale_factor
                bm_corrected.to_mesh(mesh)
                mesh.update()
                bm_corrected.free()
                
                corrected_volume = compute_mesh_volume(mesh_obj)
                corrected_ratio = corrected_volume / original_volume
                logging.debug(f"Volume after correction: {corrected_volume:.3f}, Ratio: {corrected_ratio:.3f}")
        except Exception as e:
            logging.error(f"Error during volume calculations/correction: {e}")
        
        recenter_mesh(mesh_obj)
        bm.free()
        insert_deformation_keyframe(mesh_obj)

    def modal(self, context, event):
        if event.type == 'ESC' and event.value == 'PRESS':
            logging.info("Escape pressed. Cancelling operator.")
            return self.cancel(context)
        if event.type == 'D' and event.value == 'PRESS':
            self.mode = "deform" if self.mode != "deform" else "none"
            self.deform_active = (self.mode == "deform")
            logging.debug(f"Manual toggle: DEFORM = {self.mode == 'deform'}")
        if event.type == 'R' and event.value == 'PRESS':
            if event.shift:
                logging.debug("Manual multi-view render triggered with Shift+R")
                render_obj = self.create_render_copy()
                if render_obj:
                    bpy.context.view_layer.objects.active = render_obj
                    for modifier in render_obj.modifiers:
                        try:
                            bpy.ops.object.modifier_apply(modifier=modifier.name)
                        except Exception as e:
                            logging.error(f"Could not apply modifier {modifier.name}: {e}")
                    self.render_multiview()
            else:
                self.mode = "rotate" if self.mode != "rotate" else "none"
                logging.debug(f"Manual toggle: ROTATE = {self.mode == 'rotate'}")
        if event.type == 'S' and event.value == 'PRESS':
            if self.mode == "scale":
                # Apply scale when exiting scale mode
                self.apply_scale()
                self.mode = "none"
                # Reset the scale reference when exiting scale mode
                self.scale_start_thumb_z = None
                logging.debug("Exiting scale mode, applied current scale and reset reference")
                # Hide scale info text
                self.hide_scale_info()
            else:
                self.mode = "scale"
                # scale_start_thumb_z will be set in scale_mesh
            logging.debug(f"Manual toggle: SCALE = {self.mode == 'scale'}")
        if event.type == 'C' and event.value == 'PRESS':
            if self.mode == "create":
                # If we're exiting create mode, join the cube to DeformingMesh
                if self.created_cube:
                    self.join_created_cube()
                    logging.info("Joined cube to DeformingMesh when exiting create mode")
                self.create_triggered = False
                self.mode = "none"
            else:
                self.mode = "create"
            logging.debug(f"Manual toggle: CREATE = {self.mode == 'create'}")
        if event.type == 'A' and event.value == 'PRESS':
            self.mode = "anchor" if self.mode != "anchor" else "none"
            logging.debug(f"Manual toggle: ANCHOR = {self.mode == 'anchor'}")
        if event.type == 'M' and event.value == 'PRESS':
            self.cycle_remesh_type()
            logging.debug("Manual: Cycled remesh type")
        if event.type == 'V' and event.value == 'PRESS':
            self.use_velocity_forces = not self.use_velocity_forces
            logging.info(f"Velocity forces {'enabled' if self.use_velocity_forces else 'disabled'}")
        
        if event.type == 'TIMER':
            current_time = time.time()
            delta_time = current_time - self.last_rotation_update
            self.last_rotation_update = current_time
            
            # Check for import_command.json file
            import_command_path = os.path.join(os.path.dirname(LIVE_DATA_FILE), "import_command.json")
            if os.path.exists(import_command_path):
                try:
                    with open(import_command_path, 'r') as f:
                        import_command = json.load(f)
                    
                    # Process the import command
                    if import_command.get("command") == "import_mesh":
                        mesh_path = import_command.get("mesh_path")
                        remesh_type = import_command.get("remesh_type", "Blocks")
                        collection_settings = import_command.get("collection_settings", None)
                        
                        if mesh_path and os.path.exists(mesh_path):
                            logging.info(f"Processing import command for mesh: {mesh_path}")
                            
                            # Create or get the render collection if collection settings are provided
                            render_collection = None
                            if collection_settings:
                                collection_name = collection_settings.get("name", "VIBE_Renders")
                                instance_name = collection_settings.get("instance_name", f"Render_{len(bpy.data.collections.get(collection_name, {}).objects) if bpy.data.collections.get(collection_name) else 0}")
                                hide_viewport = collection_settings.get("hide_viewport", True)
                                hide_render = collection_settings.get("hide_render", True)
                                
                                # Create collection if it doesn't exist
                                if collection_name not in bpy.data.collections:
                                    render_collection = bpy.data.collections.new(collection_name)
                                    bpy.context.scene.collection.children.link(render_collection)
                                    logging.info(f"Created new collection: {collection_name}")
                                else:
                                    render_collection = bpy.data.collections[collection_name]
                                
                                # Apply collection settings
                                if render_collection:
                                    # Set the collection properties directly
                                    render_collection.hide_viewport = hide_viewport
                                    render_collection.hide_render = hide_render
                                    logging.info(f"Set collection properties: hide_viewport={hide_viewport}, hide_render={hide_render}")
                                    
                                    # Also set layer collection settings for each view layer
                                    for view_layer in bpy.context.scene.view_layers:
                                        layer_coll = view_layer.layer_collection
                                        found = False
                                        # Find the layer collection
                                        for child in layer_coll.children:
                                            if child.name == render_collection.name:
                                                child.hide_viewport = hide_viewport
                                                child.exclude = hide_render
                                                found = True
                                                logging.info(f"Set layer collection settings in view layer {view_layer.name}")
                                                break
                                        if not found:
                                            logging.warning(f"Could not find layer collection {render_collection.name} in view layer {view_layer.name}")
                            
                            # Delete existing deformingMesh if it exists
                            existing_mesh = bpy.data.objects.get(DEFORM_OBJ_NAME)
                            if existing_mesh:
                                # Save a copy to render collection if needed
                                if render_collection:
                                    # Get iteration from import command
                                    iteration = import_command.get("iteration", 0)
                                    iteration_name = f"iteration_{iteration:03d}"
                                    
                                    # First remove from current collections
                                    logging.info(f"Removing existing mesh from current collections")
                                    for col in existing_mesh.users_collection:
                                        col.objects.unlink(existing_mesh)
                                        logging.info(f"Unlinked from collection: {col.name}")
                                    
                                    # Create a copy with the iteration name
                                    render_obj = existing_mesh.copy()
                                    render_obj.data = existing_mesh.data.copy()
                                    render_obj.name = iteration_name
                                    logging.info(f"Created copy named: {iteration_name}")
                                    
                                    # Link to the render collection
                                    render_collection.objects.link(render_obj)
                                    logging.info(f"Linked {iteration_name} to collection {render_collection.name}")
                                    
                                    # Try to export to session folder
                                    session_dir = import_command.get("session_dir", "")
                                    if session_dir and os.path.isdir(session_dir):
                                        try:
                                            export_path = os.path.join(session_dir, f"{iteration_name}.glb")
                                            logging.info(f"Attempting to export to: {export_path}")
                                            
                                            # Select only the render object
                                            bpy.ops.object.select_all(action='DESELECT')
                                            render_obj.select_set(True)
                                            bpy.context.view_layer.objects.active = render_obj
                                            
                                            # Export as GLB
                                            bpy.ops.export_scene.gltf(
                                                filepath=export_path,
                                                use_selection=True,
                                                export_format='GLB'
                                            )
                                            logging.info(f"Successfully exported to: {export_path}")
                                        except Exception as e:
                                            logging.error(f"Error exporting GLB: {e}")
                                            import traceback
                                            logging.error(traceback.format_exc())
                                
                                # Now remove the original mesh
                                bpy.data.objects.remove(existing_mesh, do_unlink=True)
                                logging.info(f"Removed existing {DEFORM_OBJ_NAME}")
                            
                            # Import the new mesh
                            try:
                                # Import GLB file
                                logging.info(f"Importing new mesh from: {mesh_path}")
                                bpy.ops.import_scene.gltf(filepath=mesh_path)
                                imported_objects = [obj for obj in bpy.context.selected_objects]
                                logging.info(f"Imported {len(imported_objects)} objects")
                                
                                if imported_objects:
                                    # Set up the imported mesh as deformingMesh
                                    new_mesh = imported_objects[0]
                                    original_name = new_mesh.name
                                    new_mesh.name = DEFORM_OBJ_NAME
                                    logging.info(f"Renamed {original_name} to {DEFORM_OBJ_NAME}")
                                    
                                    # Ensure minimum dimensions of 4x4x4 meters
                                    try:
                                        ensure_minimum_dimensions(new_mesh, 4.0)
                                    except Exception as e:
                                        logging.error(f"Error ensuring minimum dimensions: {e}")
                                    
                                    # Apply the remesh modifier
                                    update_remesh_modifier(new_mesh, remesh_type)
                                    logging.info(f"Applied remesh modifier: {remesh_type}")
                                    
                                    # Make sure it's in the correct collection
                                    for col in new_mesh.users_collection:
                                        logging.info(f"Removing from collection: {col.name}")
                                        col.objects.unlink(new_mesh)
                                    bpy.context.scene.collection.objects.link(new_mesh)
                                    logging.info(f"Added to scene collection")
                                    
                                    # Center mesh
                                    try:
                                        recenter_mesh(new_mesh)
                                        logging.info(f"Recentered mesh")
                                    except Exception as e:
                                        logging.error(f"Failed to recenter newly imported mesh: {e}")
                                    
                                    # Update original_volume for the new mesh
                                    try:
                                        global original_volume
                                        calculated_volume = compute_mesh_volume(new_mesh)
                                        if calculated_volume > 0:
                                            original_volume = calculated_volume
                                            logging.info(f"Updated original mesh volume: {original_volume:.3f}")
                                        else:
                                            logging.warning(f"Calculated volume is invalid: {calculated_volume}, keeping previous value of {original_volume}")
                                    except Exception as e:
                                        logging.error(f"Error calculating new original volume: {e}")
                                    
                                    logging.info(f"Successfully set up {DEFORM_OBJ_NAME}")
                                else:
                                    logging.error(f"Failed to import objects from {mesh_path}")
                            except Exception as e:
                                logging.error(f"Error importing mesh: {e}")
                                import traceback
                                logging.error(traceback.format_exc())
                        else:
                            logging.error(f"Mesh path not found: {mesh_path}")
                    
                    # Remove the command file to avoid reprocessing
                    try:
                        os.remove(import_command_path)
                        logging.info(f"Removed processed import command file")
                    except Exception as e:
                        logging.error(f"Error removing import command file: {e}")
                
                except Exception as e:
                    logging.error(f"Error processing import command: {e}")
                    import traceback
                    logging.error(traceback.format_exc())
            
            data = self.read_live_data()
            if not data:
                return {'PASS_THROUGH'}
                
            json_deform_active = data.get("deform_active", None)
            if json_deform_active is not None:
                self.deform_active = json_deform_active

            command = data.get("command", "none")
            left_hand_data = data.get("left_hand")
            left = []
            if left_hand_data is not None and isinstance(left_hand_data, dict):
                left = left_hand_data.get("fingertips", [])
            right_hand_data = data.get("right_hand")
            right = []
            if right_hand_data is not None and isinstance(right_hand_data, dict):
                right = right_hand_data.get("fingertips", [])
            anchors_raw = data.get("anchors", [])
            rotation_value = data.get("rotation", 0.0)
            rotation_speed = data.get("rotation_speed", 0.0)
            scale_axis = data.get("scale_axis", "XYZ")
            remesh_type = data.get("remesh_type", REMESH_TYPES[0])
            
            if command != self.last_command:
                logging.debug(f"Command changed from '{self.last_command}' to '{command}'")
                # Apply scale and reset reference when changing modes via gesture/voice
                if self.last_command == "scale" and command != "scale":
                    self.apply_scale()
                    self.scale_start_thumb_z = None
                    self.hide_scale_info()
                    logging.debug("Exiting scale mode via command change, applied scale and reset reference")
                
                # Join cube to DeformingMesh when exiting create mode
                if self.last_command == "create" and command != "create":
                    if self.created_cube:
                        self.join_created_cube()
                        logging.info("Joined cube to DeformingMesh when exiting create mode")
                    self.create_triggered = False
                    logging.info("Exited create mode, reset for next cube creation")
                
                self.last_command = command
                self.mode = command
            
            # Hide scale info if we're not in scale mode
            if self.mode != "scale":
                self.hide_scale_info()
                
            if self.right_fingertips:
                self.prev_right_fingertips = self.right_fingertips.copy() if self.right_fingertips else None
            if self.left_fingertips:
                self.prev_left_fingertips = self.left_fingertips.copy() if self.left_fingertips else None
                
            self.left_fingertips = left
            self.right_fingertips = right
            
            if self.right_fingertips:
                self.smoothed_right_fingertips = self.smooth_points(self.right_fingertips, self.smoothed_right_fingertips)
            if self.left_fingertips:
                self.smoothed_left_fingertips = self.smooth_points(self.left_fingertips, self.smoothed_left_fingertips)
                
            if anchors_raw:
                self._anchors = anchors_raw
                self.smoothed_anchors = self.smooth_points(self._anchors, self.smoothed_anchors, SMOOTHING_ALPHA / 2)
            
            # ALWAYS update the finger orbs and anchor orbs positions every frame
            # This ensures continuous tracking regardless of mode
            if self.smoothed_right_fingertips:
                finger_points = [map_to_camera_relative_space(t["x"], t["y"], t["z"]) for t in self.smoothed_right_fingertips]
                if ENABLE_DEBUG_ORBS:
                    self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
            
            if self.smoothed_anchors:
                anchor_points = [map_to_camera_relative_space(a["x"], a["y"], a["z"]) for a in self.smoothed_anchors]
                if ENABLE_DEBUG_ORBS:
                    self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
            
            # Only recenter mesh occasionally to prevent flickering
            RECENTER_INTERVAL = 10.0  # Only recenter every 10 seconds
            if current_time - self.last_recenter_time >= RECENTER_INTERVAL:
                mesh_obj = bpy.data.objects.get("DeformingMesh")
                if mesh_obj:
                    try:
                        recenter_mesh(mesh_obj)
                        self.last_recenter_time = current_time
                        logging.debug(f"Recentered mesh (next recenter in {RECENTER_INTERVAL} seconds)")
                    except Exception as e:
                        logging.error(f"Failed to recenter DeformingMesh in modal function: {e}")
            
            velocity_calc_interval = 0.05
            if current_time - self.last_velocity_update >= velocity_calc_interval:
                if self.smoothed_right_fingertips and self.prev_right_fingertips:
                    self.finger_velocities = self.calculate_finger_velocities(self.smoothed_right_fingertips,
                                                                              self.prev_right_fingertips,
                                                                              velocity_calc_interval)
                self.last_velocity_update = current_time
            
            if self.mode == "render":
                if command == "render":
                    logging.info("Render command received, creating mesh copy")
                    render_obj = self.create_render_copy()
                    if render_obj:
                        bpy.context.view_layer.objects.active = render_obj
                        for modifier in render_obj.modifiers:
                            try:
                                bpy.ops.object.modifier_apply(modifier=modifier.name)
                            except Exception as e:
                                logging.error(f"Could not apply modifier {modifier.name}: {e}")
                        # Use the new multi-view render function
                        self.render_multiview()
                self.mode = "none"
                    
            elif self.mode == "deform":
                if self.deform_active and self.smoothed_right_fingertips:
                    # Check if DeformingMesh exists and has valid data
                    mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
                    if not mesh_obj or not mesh_obj.data:
                        logging.error(f"Cannot deform: {DEFORM_OBJ_NAME} object does not exist or has no mesh data")
                        # If in deform mode but the mesh doesn't exist, switch back to 'none' mode
                        self.mode = "none"
                        self.deform_active = False
                    else:
                        if self.use_velocity_forces and self.finger_velocities:
                            self.deform_mesh_with_velocity(self.smoothed_right_fingertips,
                                                        self.finger_velocities,
                                                        self.smoothed_anchors)
                        else:
                            self.deform_mesh(self.smoothed_right_fingertips, self.smoothed_anchors)
                    
            elif self.mode == "rotate":
                env = bpy.data.objects.get("Env")
                if env is not None and self.smoothed_right_fingertips:
                    # Check if thumb and middle fingers are touching
                    thumb_tip = self.smoothed_right_fingertips[0]
                    middle_tip = self.smoothed_right_fingertips[2]
                    distance = math.sqrt(
                        (thumb_tip["x"] - middle_tip["x"])**2 +
                        (thumb_tip["y"] - middle_tip["y"])**2 +
                        (thumb_tip["z"] - middle_tip["z"])**2
                    )
                    # Only rotate if fingers are touching (distance < 0.05)
                    if distance < 0.05:
                        rotation_speed_deg = ROTATION_SPEED
                        angle_delta = math.radians(rotation_speed_deg * delta_time)
                        env.rotation_euler.z += angle_delta
                        
                        # Force update finger and anchor positions using camera-relative mapping
                        # This ensures they stay consistent relative to the camera view
                        camera = bpy.data.objects.get("Camera")
                        if camera is not None:
                            # Update all visualizations after rotation to keep them aligned with the camera
                            if self.smoothed_right_fingertips:
                                finger_points = [map_to_camera_relative_space(t["x"], t["y"], t["z"]) for t in self.smoothed_right_fingertips]
                                if ENABLE_DEBUG_ORBS:
                                    self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
                            
                            if self.smoothed_left_fingertips:
                                left_finger_points = [map_to_camera_relative_space(t["x"], t["y"], t["z"]) for t in self.smoothed_left_fingertips]
                                if ENABLE_DEBUG_ORBS:
                                    # Just update visualization, not actual processing
                                    self.update_fixed_debug_orbs(left_finger_points, [], "fingerOrb", 0)
                            
                            if self.smoothed_anchors:
                                anchor_points = [map_to_camera_relative_space(a["x"], a["y"], a["z"]) for a in self.smoothed_anchors]
                                if ENABLE_DEBUG_ORBS:
                                    self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
                        
                        logging.debug("Rotating: fingers touching, positions updated with camera-relative mapping")
                    else:
                        logging.debug("Rotation stopped: fingers not touching")
                else:
                    logging.warning("Environment object 'Env' not found for rotation.")
            elif self.mode == "scale" and self.smoothed_right_fingertips:
                self.scale_mesh(self.smoothed_right_fingertips, scale_axis)
            elif self.mode == "create" and self.smoothed_right_fingertips:
                # When in create mode, create and position the cube
                # - Create a cube if one doesn't exist
                # - Update cube position continuously based on hand position
                self.create_new_object(self.smoothed_right_fingertips)
            elif self.mode == "sculpt" and self.smoothed_right_fingertips:
                # Determine brush type based on finger positions
                brush_type = self.determine_brush_type(self.smoothed_right_fingertips)
                # Apply the sculpt brush with the determined type
                self.apply_sculpt_brush(self.smoothed_right_fingertips, brush_type)
                
            elif self.mode == "boolean" and self.smoothed_left_fingertips and self.smoothed_right_fingertips:
                # Use both hands for object selection
                self.multi_select_objects(self.smoothed_left_fingertips, self.smoothed_right_fingertips)
                
                # Check if we have at least 2 objects selected for boolean operation
                # The gesture (hand configuration) would determine the boolean type
                if len(bpy.context.selected_objects) >= 2:
                    operation = "UNION"  # Default operation
                    # Determine operation based on hands configuration
                    # This is a simplified example - could be extended with more gestures
                    if (self.smoothed_left_fingertips[1]["y"] < 0.3 and 
                        self.smoothed_right_fingertips[1]["y"] < 0.3):
                        operation = "DIFFERENCE"
                    elif (self.smoothed_left_fingertips[1]["y"] > 0.7 and 
                          self.smoothed_right_fingertips[1]["y"] > 0.7):
                        operation = "INTERSECT"
                    self.apply_boolean_operation(operation)
                
            elif self.mode == "material" and self.smoothed_right_fingertips:
                # Determine material index based on hand height
                avg_y = sum(tip["y"] for tip in self.smoothed_right_fingertips) / len(self.smoothed_right_fingertips)
                # Map y position (0-1) to material indices (0-4)
                material_index = min(int(avg_y * 5), 4)
                self.assign_material_to_selection(material_index)
                
            elif self.mode == "dyntopo":
                # Toggle dynamic topology based on gesture
                self.toggle_dynamic_topology()
                self.mode = "sculpt"  # Automatically switch to sculpt mode after toggling
                
            # Check for additional voice commands from live data
            voice_command = data.get("voice_command", "")
            if voice_command.startswith("scale "):
                try:
                    # Parse commands like "scale x to 2.5"
                    parts = voice_command.split()
                    if len(parts) >= 4 and parts[2].lower() == "to":
                        axis = parts[1].upper()
                        value = float(parts[3])
                        self.precise_scale(axis, value)
                        logging.info(f"Applied precise scale to {axis}: {value}")
                except Exception as e:
                    logging.error(f"Error parsing scale command: {e}")
            elif voice_command == "enable snapping":
                self.enable_snapping()
            elif voice_command == "bridge edges":
                self.bridge_edge_loops()
            elif voice_command == "smooth edges":
                self.smooth_edge_flow()
                    
            self.prev_mode = self.mode
            
        # At the end of the modal loop, check if we're exiting create mode
        if self.prev_mode == "create" and self.mode != "create":
            # Join the cube when exiting create mode
            if self.created_cube:
                self.join_created_cube()
                logging.info("Joined cube to DeformingMesh when exiting create mode via prev_mode check")
            self.create_triggered = False
            
        return {'PASS_THROUGH'}

    def hide_scale_info(self):
        """Hide the scale info text object"""
        text_obj = bpy.data.objects.get("ScaleInfo")
        if text_obj:
            text_obj.hide_viewport = True

    def execute(self, context):
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.last_rotation_update = time.time()
        self.last_velocity_update = time.time()
        self.last_recenter_time = time.time()  # Initialize the recentering timer
        self.use_velocity_forces = True
        self.finger_velocities = None
        self.deform_active = False
        self.render_created_objects = []
        self.create_triggered = False
        self.created_cube = None
        self.prev_mode = self.mode
        self.scale_start_thumb_z = None
        mesh_obj = bpy.data.objects.get("DeformingMesh")
        if mesh_obj:
            try:
                recenter_mesh(mesh_obj)
            except Exception as e:
                logging.error(f"Failed to recenter mesh in execute: {e}")
        logging.info("Real-time mesh update operator started.")
        logging.info("Controls: ESC (cancel), D (deform), R (rotate), S (scale), C (create), A (anchor), M (cycle remesh), V (toggle velocity forces), Shift+R (render)")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        logging.info("Real-time update operator cancelled. Cleaning up...")
        
        # Apply scale if in scale mode when cancelled
        if self.mode == "scale":
            self.apply_scale()
            logging.info("Applied scale before cancelling as we were in scale mode")
        
        # Join cube if in create mode when cancelled
        if self.mode == "create" and self.created_cube:
            self.join_created_cube()
            logging.info("Joined cube to DeformingMesh before cancelling as we were in create mode")
        
        # Hide scale info if visible
        self.hide_scale_info()
        cleanup_created_objects()
        return {'CANCELLED'}

    def render_multiview(self):
        """Render multiple views using the RenderCam camera"""
        # We need to bypass the error that's occurring in this function
        # Let's completely restructure the function to avoid the problematic operations
        
        # ===== PART 1: Setup Session Directory =====
        try:
            # First, find the DeformingMesh
            mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
            if not mesh_obj:
                print("Cannot find DeformingMesh to create snapshot for rendering")
                return False
                
            print("Creating snapshot of current DeformingMesh state")
            
            # Create session directory with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_output_dir = "C:\\CODING\\VIBE\\VIBE_Massing\\output\\generated\\Models"
            session_dir = os.path.join(base_output_dir, f"session_{timestamp}")
            os.makedirs(session_dir, exist_ok=True)
            print(f"Created session directory: {session_dir}")
        except Exception as e:
            print(f"Error in session directory setup: {str(e)}")
            return False
            
        # ===== PART 2: Collection Setup =====
        try:
            # Create or get the VIBE_Renders collection
            collection_name = "VIBE_Renders"
            render_collection = None
            
            if collection_name in bpy.data.collections:
                render_collection = bpy.data.collections[collection_name]
                print(f"Using existing collection: {collection_name}")
            else:
                render_collection = bpy.data.collections.new(collection_name)
                bpy.context.scene.collection.children.link(render_collection)
                print(f"Created new collection: {collection_name}")
            
            # Set collection to be hidden in viewport and excluded from renders
            render_collection.hide_viewport = True
            render_collection.hide_render = True
            print(f"Set collection properties")
            
            # Also set layer collection visibility
            for view_layer in bpy.context.scene.view_layers:
                layer_coll = view_layer.layer_collection
                for child in layer_coll.children:
                    if child.name == collection_name:
                        child.hide_viewport = True
                        child.exclude = True
                        print(f"Set layer collection settings in view layer")
        except Exception as e:
            print(f"Error in collection setup: {str(e)}")
            return False
            
        # ===== PART 3: Find Next Iteration Number =====
        try:
            # Find the next available iteration number
            iteration = 0
            while os.path.exists(os.path.join(session_dir, f"iteration_{iteration:03d}.glb")):
                iteration += 1
            
            iteration_name = f"iteration_{iteration:03d}"
            print(f"Using iteration name: {iteration_name}")
        except Exception as e:
            print(f"Error finding iteration number: {str(e)}")
            return False
            
        # ===== PART 4: Create Snapshot =====
        try:
            # Create a snapshot copy of the DeformingMesh
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj
            
            # Duplicate the mesh (this creates a copy and selects it)
            bpy.ops.object.duplicate()
            
            # Get the duplicated object (it's now the active/selected object)
            snapshot_obj = bpy.context.active_object
            original_name = snapshot_obj.name
            snapshot_obj.name = iteration_name
            print(f"Created snapshot named: {iteration_name}")
            
            # Apply all modifiers to the snapshot
            for modifier in snapshot_obj.modifiers:
                try:
                    bpy.context.view_layer.objects.active = snapshot_obj
                    bpy.ops.object.modifier_apply(modifier=modifier.name)
                except Exception as modifier_error:
                    print(f"Could not apply modifier: {str(modifier_error)}")
        except Exception as e:
            print(f"Error creating snapshot: {str(e)}")
            return False
            
        # ===== PART 5: Collection Management =====
        try:
            # Make sure we have the correct object selected
            bpy.ops.object.select_all(action='DESELECT')
            snapshot_obj.select_set(True)
            bpy.context.view_layer.objects.active = snapshot_obj
            
            # CRITICAL: Remove the snapshot from ALL collections first
            print(f"Moving snapshot to collection: {collection_name}")
            all_collections = list(snapshot_obj.users_collection)
            for col in all_collections:
                col.objects.unlink(snapshot_obj)
            
            # Now link ONLY to the render collection
            render_collection.objects.link(snapshot_obj)
            
            # Verify the object is only in the render collection
            if len(snapshot_obj.users_collection) != 1 or snapshot_obj.users_collection[0].name != collection_name:
                print(f"Warning: snapshot may not be exclusively in {collection_name}")
            else:
                print(f"Snapshot successfully placed in {collection_name}")
        except Exception as e:
            print(f"Error managing collections: {str(e)}")
            # Don't return False here, try to continue with export
            
        # ===== PART 6: Export GLB =====
        try:
            # Export the snapshot to the session directory
            export_path = os.path.join(session_dir, f"{iteration_name}.glb")
            
            # Make sure the object is properly selected again
            bpy.ops.object.select_all(action='DESELECT')
            snapshot_obj.select_set(True)
            bpy.context.view_layer.objects.active = snapshot_obj
            
            # Export as GLB
            bpy.ops.export_scene.gltf(
                filepath=export_path,
                use_selection=True,
                export_format='GLB'
            )
            print(f"Exported to: {export_path}")
            
            # Verify the export file exists
            if os.path.exists(export_path):
                file_size = os.path.getsize(export_path)
                print(f"Verified file exists ({file_size} bytes)")
            else:
                print(f"Warning: Export file not found")
        except Exception as e:
            print(f"Error exporting GLB: {str(e)}")
            # Continue with renders even if export fails
            
        # ===== PART 7: Multi-View Renders =====
        try:
            # Create output directory
            os.makedirs(RENDER_OUTPUT_DIR, exist_ok=True)
            
            # Get the render camera
            render_cam = bpy.data.objects.get(RENDER_CAMERA_NAME)
            if not render_cam:
                print(f"Render camera not found: {RENDER_CAMERA_NAME}")
                return False
                
            # Store current camera and frame
            current_camera = bpy.context.scene.camera
            current_frame = bpy.context.scene.frame_current
            
            # Set render camera
            bpy.context.scene.camera = render_cam
            
            # Render each frame
            for frame, filename in RENDER_FRAMES.items():
                try:
                    # Set frame
                    bpy.context.scene.frame_current = frame
                    
                    # Set output path - ASCII only
                    safe_filename = "".join(c for c in filename if ord(c) < 128)
                    output_path = os.path.join(RENDER_OUTPUT_DIR, safe_filename)
                    bpy.context.scene.render.filepath = output_path
                    
                    # Render
                    print(f"Rendering frame {frame}")
                    bpy.ops.render.render(write_still=True)
                except Exception as frame_error:
                    print(f"Error rendering frame {frame}: {str(frame_error)}")
            
            print("Multi-view render completed")
            return True
        except Exception as e:
            print(f"Error in multi-view render: {str(e)}")
            return False
        finally:
            try:
                # Restore original camera and frame
                bpy.context.scene.camera = current_camera
                bpy.context.scene.frame_current = current_frame
            except:
                pass  # Silently continue if restoration fails

def ensure_minimum_dimensions(obj, min_dimension=4.0):
    """
    Ensures that the object has at least one dimension (X, Y, or Z) that is at least min_dimension meters.
    
    Args:
        obj (bpy.types.Object): The Blender object to resize
        min_dimension (float): The minimum dimension in meters (default: 4.0)
        
    Returns:
        bool: True if scaling was applied, False otherwise
    """
    if not obj:
        logging.error("No object provided to ensure_minimum_dimensions")
        return False
        
    # Get the object's dimensions
    dimensions = obj.dimensions
    logging.info(f"Original dimensions: {dimensions.x:.2f}m x {dimensions.y:.2f}m x {dimensions.z:.2f}m")
    
    # Find the largest dimension
    max_dim = max(dimensions.x, dimensions.y, dimensions.z)
    
    # If the largest dimension is less than the minimum dimension, scale the object
    if max_dim < min_dimension:
        # Calculate the scale factor needed
        scale_factor = min_dimension / max_dim
        
        # Apply the scale factor to the object
        obj.scale = [s * scale_factor for s in obj.scale]
        
        # Update the object to reflect the new scale
        bpy.context.view_layer.update()
        
        # Apply the scale to the mesh (so it's "baked in")
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Log the new dimensions
        new_dimensions = obj.dimensions
        logging.info(f"Scaled to minimum dimensions: {new_dimensions.x:.2f}m x {new_dimensions.y:.2f}m x {new_dimensions.z:.2f}m")
        logging.info(f"Applied scale factor: {scale_factor:.2f}")
        return True
    else:
        logging.info(f"No scaling needed, largest dimension {max_dim:.2f}m already meets minimum {min_dimension:.2f}m")
        return False

class ImageUserProperties(bpy.types.PropertyGroup):
    # Instead of trying to use ImageUser directly, we'll create a simple property
    # that will allow the template_image to work
    use_A: bpy.props.BoolProperty(default=True)
    use_B: bpy.props.BoolProperty(default=True)
    use_C: bpy.props.BoolProperty(default=True)

class OPTION_OT_select(bpy.types.Operator):
    bl_idname = "option.select"
    bl_label = "Select Option"
    bl_description = "Select this design option"
    
    option: bpy.props.StringProperty()
    
    def execute(self, context):
        # Here you can add the logic for what happens when an option is selected
        logging.info(f"Selected option: {self.option}")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(REALTIME_OT_update_mesh)
    bpy.utils.register_class(OPTION_OT_select)  # Register our new operator
    bpy.utils.register_class(ImageUserProperties)
    
    # Register the property group
    bpy.types.Scene.vibe_image_users = bpy.props.PointerProperty(type=ImageUserProperties)
    
    register_image_panel()
    logging.info("Registered VIBE Massing addon with image panel")

def unregister():
    cleanup_created_objects()
    
    # Unregister the property group
    del bpy.types.Scene.vibe_image_users
    
    bpy.utils.unregister_class(ImageUserProperties)
    bpy.utils.unregister_class(OPTION_OT_select)  # Unregister our operator
    unregister_image_panel()
    bpy.utils.unregister_class(REALTIME_OT_update_mesh)
    logging.info("Unregistered VIBE Massing addon")

if __name__ == "__main__":
    register()
    bpy.ops.wm.realtime_update_mesh()