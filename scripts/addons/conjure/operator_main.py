# This is the main Blender script for CONJURE.
# It handles the core logic for real-time mesh interaction based on hand data.
#
# Its primary functions are:
# 1. Receiving real-time hand data from 'fingertips.json'.
# 2. Plotting fingertips as visual markers in the 3D scene.
# 3. Deforming a target mesh based on fingertip positions and the active command.

import bpy
import json
import os
import mathutils
import bmesh
import time
from pathlib import Path
import math
from collections import deque
import blf # For drawing text on the screen
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_vector_3d, region_2d_to_origin_3d

# Import all constants and settings from our new config file
from . import config


# --- FLICKER FIX ---
# A short grace period (in frames) before hiding a marker that has disappeared.
# This prevents flickering from minor, single-frame dropouts in hand tracking.
HIDE_GRACE_PERIOD_FRAMES = 5

# === 1. UI PANEL ===
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

        # Check a custom property to see if the modal operator is running
        if wm.conjure_is_running:
            layout.operator("conjure.stop_operator", text="Finalize CONJURE", icon='PAUSE')
        else:
            # The 'conjure.fingertip_operator' is the main operator defined below
            layout.operator("conjure.fingertip_operator", text="Initiate CONJURE", icon='PLAY')
        
        # Add separator
        layout.separator()
        
        # Auto-refresh controls
        box = layout.box()
        box.label(text="Backend Agent Context", icon='CAMERA_DATA')
        
        if hasattr(wm, 'conjure_auto_refresh_running') and wm.conjure_auto_refresh_running:
            box.operator("conjure.stop_auto_refresh", text="Stop Auto-Refresh", icon='PAUSE')
            box.label(text="📸 Rendering every 3s", icon='INFO')
        else:
            box.operator("conjure.auto_refresh_render", text="Start Auto-Refresh", icon='PLAY')
            box.label(text="Click to enable automatic rendering", icon='INFO')
        
        # Add separator
        layout.separator()
        
        # Force import controls
        import_box = layout.box()
        import_box.label(text="Mesh Import", icon='IMPORT')
        import_box.operator("conjure.force_import_last_mesh", text="Force Import Last Mesh", icon='MESH_DATA')
        import_box.label(text="Import latest generated mesh", icon='INFO')

class CONJURE_OT_force_import_last_mesh(bpy.types.Operator):
    """Force import the last detected mesh file and trigger segment selection"""
    bl_idname = "conjure.force_import_last_mesh"
    bl_label = "Force Import Last Mesh"
    
    def execute(self, context):
        print("🔄 Force importing last detected mesh...")
        
        try:
            # Find the latest mesh file in the expected directory
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent.parent
            mesh_dir = project_root / "data" / "generated_models" / "partpacker_results"
            
            if not mesh_dir.exists():
                self.report({'ERROR'}, "Mesh directory does not exist")
                print(f"❌ Mesh directory not found: {mesh_dir}")
                return {'CANCELLED'}
            
            # Look for partpacker_result_0.glb (primary) or any .glb file
            mesh_file = mesh_dir / "partpacker_result_0.glb"
            
            if not mesh_file.exists():
                # Look for any .glb files in the directory
                glb_files = list(mesh_dir.glob("*.glb"))
                if glb_files:
                    # Get the most recent one
                    mesh_file = max(glb_files, key=lambda p: p.stat().st_mtime)
                    print(f"📄 Using most recent GLB: {mesh_file.name}")
                else:
                    self.report({'ERROR'}, "No mesh files found in directory")
                    print(f"❌ No GLB files found in: {mesh_dir}")
                    return {'CANCELLED'}
            
            if not mesh_file.exists():
                self.report({'ERROR'}, f"Mesh file not found: {mesh_file.name}")
                print(f"❌ Mesh file not found: {mesh_file}")
                return {'CANCELLED'}
            
            print(f"✅ Found mesh file: {mesh_file}")
            
            # Trigger the import via the state system (same as automatic detection)
            try:
                import httpx
            except ImportError:
                # Fallback to urllib if httpx is not available
                import urllib.request
                import urllib.parse
                import json
                
                data = json.dumps({
                    "mesh_path": str(mesh_file),
                    "min_volume_threshold": 0.001
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    "http://127.0.0.1:8000/blender/import_mesh",
                    data=data,
                    headers={'Content-Type': 'application/json'}
                )
                
                try:
                    with urllib.request.urlopen(req, timeout=30.0) as response:
                        result = json.loads(response.read().decode('utf-8'))
                        response_status = response.status
                except Exception as e:
                    error_msg = str(e)
                    if "404" in error_msg or "Not Found" in error_msg:
                        self.report({'ERROR'}, "API server not running. Start CONJURE launcher first.")
                        print("❌ FORCE IMPORT: API server (127.0.0.1:8000) not running")
                        print("💡 SOLUTION: Run the CONJURE launcher (launcher/main.py) to start the API server")
                    else:
                        self.report({'ERROR'}, f"API request failed: {error_msg}")
                        print(f"❌ API request error: {e}")
                    return {'CANCELLED'}
            else:
                # Use httpx if available
                import json
                
                response = httpx.post(
                    "http://127.0.0.1:8000/blender/import_mesh",
                    json={
                        "mesh_path": str(mesh_file),
                        "min_volume_threshold": 0.001
                    },
                    timeout=30.0
                )
                result = response.json()
                response_status = response.status_code
            
            if response_status == 200:
                if result.get("success", False):
                    self.report({'INFO'}, f"Successfully imported mesh: {mesh_file.name}")
                    print(f"✅ Force import successful: {mesh_file.name}")
                    print("🎯 Mesh import and segment selection triggered")
                else:
                    error_msg = result.get("error", "Unknown error")
                    self.report({'ERROR'}, f"Import failed: {error_msg}")
                    print(f"❌ Import API failed: {error_msg}")
                    return {'CANCELLED'}
            else:
                if response_status == 404:
                    self.report({'ERROR'}, "API server not running. Start CONJURE launcher first.")
                    print("❌ FORCE IMPORT: API server (127.0.0.1:8000) not running")
                    print("💡 SOLUTION: Run the CONJURE launcher (launcher/main.py) to start the API server")
                else:
                    self.report({'ERROR'}, f"API call failed: {response_status}")
                    print(f"❌ API call failed with status: {response_status}")
                return {'CANCELLED'}
            
        except Exception as e:
            error_msg = str(e)
            if "Connection refused" in error_msg or "ConnectTimeout" in error_msg:
                self.report({'ERROR'}, "Cannot connect to API server. Start CONJURE launcher first.")
                print("❌ FORCE IMPORT: Cannot connect to API server (127.0.0.1:8000)")
                print("💡 SOLUTION: Run the CONJURE launcher (launcher/main.py) to start the API server")
            else:
                self.report({'ERROR'}, f"Error during force import: {error_msg}")
                print(f"❌ Force import error: {e}")
                import traceback
                print(f"🔍 Traceback: {traceback.format_exc()}")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class CONJURE_OT_stop_operator(bpy.types.Operator):
    """A simple operator that sets a flag to signal the modal operator to stop."""
    bl_idname = "conjure.stop_operator"
    bl_label = "Stop Conjure Operator"

    def execute(self, context):
        # This property will be checked by the modal operator in its main loop
        context.window_manager.conjure_should_stop = True
        return {'FINISHED'}


# --- CORE CONFIGURATION ---
# Using pathlib to create a robust, OS-agnostic path.
# This assumes the script is run from a context where the project root can be determined.
try:
    # This will work when the script is part of a larger execution from the root
    PROJECT_ROOT = Path(__file__).parent.parent.parent
except NameError:
    # Fallback for running directly in Blender's text editor
    PROJECT_ROOT = Path(bpy.data.filepath).parent.parent
    
DATA_DIR = PROJECT_ROOT / "data"
FINGERTIPS_JSON_PATH = DATA_DIR / "input" / "fingertips.json"
DEFORM_OBJ_NAME = "Mesh"  # The name of the mesh we will manipulate
GESTURE_CAMERA_NAME = "GestureCamera" # The camera used for perspective-based mapping

# --- MAPPING SCALE ---
# These values control how sensitive the hand tracking is.
# Larger values mean the virtual hand moves more for a given physical hand movement.
HAND_SCALE_X = 10.0 # Controls side-to-side movement.
HAND_SCALE_Y = 10.0 # Controls forward-backward movement (from hand depth).
HAND_SCALE_Z = 10.0 # Controls up-down movement.

# --- VISUALIZATION ---
MARKER_OUT_OF_VIEW_LOCATION = (1000, 1000, 1000) # Move unused markers here to prevent flickering.
MARKER_SURFACE_OFFSET = 0.05 # How far to offset the marker from the mesh surface to prevent z-fighting.

# --- REFRESH RATE ---
# The target interval in seconds for the operator to update.
# A smaller value means a higher refresh rate. 30 FPS is a good balance
# between smooth interaction and preventing I/O contention with the hand tracker.
REFRESH_RATE_SECONDS = 1 / 30  # Target 30 updates per second.

# --- ROTATION ---
ORBIT_SENSITIVITY = 400.0 # How sensitive the orbit control is. Higher is faster.
ORBIT_SMOOTHING_FACTOR = 0.25 # How much to smooth the orbit motion. Lower is smoother.

# --- SMOOTHING ---
# Smoothing constants are now defined in config.py

# --- DEFORMATION PARAMETERS ---
# These control how the mesh reacts to the user's hand.
# The following are now defined by the RADIUS_LEVELS below.
# FINGER_INFLUENCE_RADIUS = 3.0
# GRAB_INFLUENCE_RADIUS = 1.5
# INFLATE_FLATTEN_RADIUS = 0.375
RADIUS_LEVELS = [
    {'name': 'small',  'finger': 3.0, 'grab': 1.5, 'flatten': 0.375, 'inflate': 0.75},
    {'name': 'medium', 'finger': 3.0, 'grab': 1.5, 'flatten': 0.75,  'inflate': 1.5},
    {'name': 'large',  'finger': 3.0, 'grab': 3.0, 'flatten': 3.0,   'inflate': 6.0}
]
MAX_DISPLACEMENT_PER_FRAME = 0.25 # Safety limit to prevent vertices from moving too far in one frame.
MASS_COHESION_FACTOR = 0.62 # How much vertices stick together to create a smoother deformation.
DEFORM_TIMESTEP = 0.05 # Multiplier for displacement per frame to create a continuous effect.
VOLUME_LOWER_LIMIT = 0.8 # The mesh cannot shrink to less than 80% of its original volume.
VOLUME_UPPER_LIMIT = 1.2 # The mesh cannot expand to more than 120% of its original volume.

# --- VELOCITY & VISCOSITY ---
# These parameters add a sense of weight and momentum to the mesh.
VELOCITY_DAMPING_FACTOR = 0.80 # How much velocity is retained each frame (lower is 'thicker' viscosity).
FINGER_FORCE_STRENGTH = 0.09    # How strongly the finger pushes/pulls the mesh. A much smaller value is needed for a stable velocity-based system.
GRAB_FORCE_STRENGTH = 10       # How strongly the grab brush moves the mesh with the hand.
SMOOTH_FORCE_STRENGTH = 1.75     # How strongly the smooth brush relaxes vertices.
INFLATE_FORCE_STRENGTH = 0.15    # How strongly the inflate brush adds/removes volume.
FLATTEN_FORCE_STRENGTH = 1.5   # How strongly the flatten brush creates planar surfaces.
USE_VELOCITY_FORCES = True # Master toggle for the entire viscosity system.
MAX_HISTORY_STEPS = 150 # The number of undo steps to store in memory.
BRUSH_TYPES = ['DRAW', 'GRAB', 'SMOOTH', 'INFLATE', 'FLATTEN'] # The available deformation brushes


# === 1. INITIAL SCENE SETUP ===
def setup_scene():
    """
    Ensures that a deformable mesh, fingertip markers, and the gesture camera exist.
    """
    # Ensure the main deformable mesh exists.
    if config.DEFORM_OBJ_NAME not in bpy.data.objects:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1, location=(0, 0, 0))
        bpy.context.active_object.name = config.DEFORM_OBJ_NAME
        print(f"Created '{config.DEFORM_OBJ_NAME}'.")

    # Ensure the GestureCamera exists
    if config.GESTURE_CAMERA_NAME not in bpy.data.objects:
        bpy.ops.object.camera_add(location=(0, -5, 0))
        bpy.context.active_object.name = config.GESTURE_CAMERA_NAME
        # Point the camera towards the origin
        bpy.context.active_object.rotation_euler = (math.radians(90), 0, 0)
        print(f"Created '{config.GESTURE_CAMERA_NAME}'.")

    # Ensure a template object for fingertip markers exists.
    if "FingertipTemplate" not in bpy.data.objects:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.05, location=(0, 0, -10))
        bpy.context.active_object.name = "FingertipTemplate"
        bpy.context.active_object.hide_viewport = True
        print("Created 'FingertipTemplate'.")

    for i in range(10): # For two hands
        marker_name = f"Fingertip.{i:02d}"
        if marker_name not in bpy.data.objects:
            template = bpy.data.objects.get("FingertipTemplate")
            if template:
                marker = template.copy()
                marker.name = marker_name
                bpy.context.collection.objects.link(marker)
                
                # Set up marker for always-visible rendering
                marker.hide_viewport = False
                marker.show_in_front = True
                print(f"🔧 Created fingertip marker '{marker_name}' with show_in_front = {marker.show_in_front}")


# === 2. COORDINATE MAPPING ===
def map_hand_to_3d_space(x_norm, y_norm, z_norm):
    """
    Maps normalized (0-1) hand coordinates to Blender's 3D world space,
    relative to the perspective of the GestureCamera.
    """
    # 1. Get the camera object
    camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
    
    # 2. Define a base coordinate vector from the normalized inputs
    #    (x is side-to-side, y is forward-back, z is up-down)
    local_point = mathutils.Vector((
        (x_norm - 0.5) * config.HAND_SCALE_X,
        z_norm * -config.HAND_SCALE_Y, # The negative sign inverts depth from the camera
        (0.5 - y_norm) * config.HAND_SCALE_Z
    ))

    if camera:
        # 3. Get the camera's orientation vectors in world space
        cam_matrix = camera.matrix_world
        # The camera's right, up, and forward vectors
        cam_right = cam_matrix.to_3x3().col[0]
        cam_up = cam_matrix.to_3x3().col[1]
        # Blender cameras look down their local -Z axis
        cam_forward = -cam_matrix.to_3x3().col[2]

        # 4. Project the local point onto the camera's axes
        #    This transforms the hand movements into the camera's perspective.
        world_vector = (cam_right * local_point.x) + \
                       (cam_up * local_point.z) + \
                       (cam_forward * local_point.y)
        
        return world_vector
    else:
        # Fallback to world-space mapping if the camera isn't found
        print(f"Warning: '{config.GESTURE_CAMERA_NAME}' not found. Using world-space mapping.")
        return local_point


# === 4. MESH DEFORMATION ===
def deform_mesh(mesh_obj, finger_positions_3d, initial_volume):
    """
    Deforms the mesh using bmesh based on the 3D positions of the fingertips.
    This version operates on mesh data directly for stability and performance,
    and is based on the robust implementation from fingertipmain.py.
    """
    if not mesh_obj or not finger_positions_3d:
        return

    # Use the 'medium' radius setting as a default for this legacy function.
    radius_settings = config.RADIUS_LEVELS[1] # 0=small, 1=medium, 2=large
    finger_influence_radius = radius_settings['finger']

    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    
    world_matrix = mesh_obj.matrix_world
    world_matrix_inv = world_matrix.inverted()

    # 1. Calculate raw vertex displacements
    vertex_displacements = {}
    for v in bm.verts:
        v_world = world_matrix @ v.co
        net_displacement = mathutils.Vector((0, 0, 0))
        
        for finger_pos in finger_positions_3d:
            to_finger = finger_pos - v_world
            dist = to_finger.length
            
            if dist < finger_influence_radius:
                # Use a squared falloff for a smoother gradient
                falloff = (1.0 - (dist / finger_influence_radius))**2
                direction = to_finger.normalized()
                force = direction * config.FINGER_FORCE_STRENGTH * falloff
                net_displacement += force
        
        if net_displacement.length > 0.0001:
            # Clamp displacement to avoid extreme results
            if net_displacement.length > config.MAX_DISPLACEMENT_PER_FRAME:
                net_displacement = net_displacement.normalized() * config.MAX_DISPLACEMENT_PER_FRAME
            vertex_displacements[v.index] = net_displacement

    # 2. Smooth the displacements for a more cohesive mass-like effect
    smoothed_displacements = {}
    if not vertex_displacements:
        bm.free()
        return # No vertices were affected, so we can exit early.
        
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
            
        # Interpolate between the raw displacement and the average of its neighbors
        smoothed_displacement = original_displacement.lerp(neighbor_avg, config.MASS_COHESION_FACTOR)
        smoothed_displacements[v.index] = smoothed_displacement
        
    # 3. Apply the smoothed displacements to the vertices
    if smoothed_displacements:
        for v_index, displacement in smoothed_displacements.items():
            # Ensure lookup table is fresh before indexed access
            bm.verts.ensure_lookup_table()
            v = bm.verts[v_index]
            v_world = world_matrix @ v.co
            # Apply the smoothed displacement over time for a continuous effect
            v_world += displacement * config.DEFORM_TIMESTEP
            # Convert back to local space to update the vertex
            v.co = world_matrix_inv @ v_world

    # 4. Volume Preservation - DEACTIVATED
    # Note: Volume preservation has been deactivated to prevent unwanted scaling
    # The mesh is allowed to deform naturally without volume constraints
    pass

    # 5. Write the modified bmesh data back to the mesh
    bm.to_mesh(mesh_obj.data)
    bm.free()

    # 6. Tag the mesh to ensure the viewport updates
    mesh_obj.data.update()


# === 5. MESH DEFORMATION (with Viscosity) ===
def deform_mesh_with_viscosity(mesh_obj, finger_positions_3d, initial_volume, vertex_velocities, history_buffer, operator_instance, brush_type='PINCH', hand_move_vector=None):
    """
    Deforms the mesh by applying forces and simulating viscosity.
    This version updates vertex velocities for a more dynamic and weighty feel.
    """
    if not mesh_obj:
        return

    # --- Save current state to history before deforming ---
    # We only save if there are active forces being applied (for PINCH/GRAB).
    if finger_positions_3d:
        current_verts = [v.co.copy() for v in mesh_obj.data.vertices]
        history_buffer.append(current_verts)

    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)

    world_matrix = mesh_obj.matrix_world
    world_matrix_inv = world_matrix.inverted()

    # --- 1. Calculate Forces and Update Velocities based on Brush Type ---
    new_displacements = {}
    
    # Create a KDTree for faster spatial lookups, used by all brushes
    size = len(bm.verts)
    kd = mathutils.kdtree.KDTree(size)
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()

    # Ensure the lookup table is fresh before any indexed access.
    bm.verts.ensure_lookup_table()

    # Determine the center of influence (average of finger positions)
    influence_center = mathutils.Vector()
    if finger_positions_3d:
        for pos in finger_positions_3d:
            influence_center += world_matrix_inv @ pos # Convert to local space
        influence_center /= len(finger_positions_3d)

    # Determine the effective radius based on the brush type and current radius level
    radius_level = config.RADIUS_LEVELS[operator_instance._current_radius_index]
    if brush_type == 'GRAB':
        effective_radius = radius_level['grab']
    elif brush_type == 'INFLATE':
        effective_radius = radius_level['inflate']
    elif brush_type == 'FLATTEN':
        effective_radius = radius_level['flatten']
    else: # PINCH, SMOOTH use the default
        effective_radius = radius_level['finger']

    # --- Special pre-calculation for FLATTEN brush ---
    flatten_plane_center = None
    flatten_plane_normal = None
    if brush_type == 'FLATTEN' and finger_positions_3d:
        verts_in_range_indices = [v_idx for co, v_idx, dist in kd.find_range(influence_center, effective_radius)]
        if verts_in_range_indices:
            flatten_plane_center = mathutils.Vector()
            for v_idx in verts_in_range_indices:
                flatten_plane_center += bm.verts[v_idx].co
            flatten_plane_center /= len(verts_in_range_indices)

            flatten_plane_normal = mathutils.Vector()
            for v_idx in verts_in_range_indices:
                flatten_plane_normal += bm.verts[v_idx].normal
            
            if flatten_plane_normal.length > 0:
                flatten_plane_normal.normalize()

    # Iterate through vertices within the brush influence
    for (co, v_idx, dist_from_center) in kd.find_range(influence_center, effective_radius):
        v = bm.verts[v_idx]
        current_velocity = vertex_velocities.get(v.index, mathutils.Vector((0,0,0)))
        force = mathutils.Vector((0, 0, 0))

        # Calculate a smooth falloff based on distance from the brush center.
        # This is the key to making the brushes feel natural and not jagged.
        falloff = (1.0 - (dist_from_center / effective_radius))**2

        if brush_type == 'DRAW':
            # DRAW doesn't deform vertices - it's handled separately in the main modal loop
            # This space is reserved for future DRAW-specific vertex effects if needed
            pass

        elif brush_type == 'GRAB':
            # Moves vertices along with the hand's movement vector, scaled by falloff.
            if hand_move_vector:
                force = hand_move_vector * config.GRAB_FORCE_STRENGTH * falloff

        elif brush_type == 'SMOOTH':
            # Moves vertices towards their neighbors' average position, scaled by falloff.
            neighbor_avg_pos = mathutils.Vector()
            linked_verts = [e.other_vert(v) for e in v.link_edges]
            if linked_verts:
                for nv in linked_verts:
                    neighbor_avg_pos += nv.co
                neighbor_avg_pos /= len(linked_verts)
                force = (neighbor_avg_pos - v.co) * config.SMOOTH_FORCE_STRENGTH * falloff
        
        elif brush_type == 'INFLATE':
            # Pushes vertices outwards along their normal, scaled by falloff.
            force = v.normal * config.INFLATE_FORCE_STRENGTH * falloff

        elif brush_type == 'FLATTEN':
            # Pushes vertices towards a plane, scaled by falloff.
            if flatten_plane_center and flatten_plane_normal:
                dist_to_plane = (v.co - flatten_plane_center).dot(flatten_plane_normal)
                force = -flatten_plane_normal * dist_to_plane * config.FLATTEN_FORCE_STRENGTH * falloff

        # Update velocity: add force and apply damping
        new_velocity = (current_velocity + force) * config.VELOCITY_DAMPING_FACTOR
        vertex_velocities[v.index] = new_velocity
        
        # Calculate the displacement for this frame
        displacement = new_velocity * config.DEFORM_TIMESTEP
        if displacement.length > config.MAX_DISPLACEMENT_PER_FRAME:
            displacement = displacement.normalized() * config.MAX_DISPLACEMENT_PER_FRAME
        
        new_displacements[v.index] = displacement

    # --- 2. Apply Displacements ---
    if new_displacements:
        for v_index, displacement in new_displacements.items():
            bm.verts.ensure_lookup_table()
            # For GRAB, the displacement is in world space, others are local. This is a simplification.
            # A more robust implementation would handle spaces more carefully.
            bm.verts[v_index].co += displacement

    # --- 3. Volume Preservation - DEACTIVATED ---
    # Note: Volume preservation has been deactivated to prevent unwanted scaling
    # The mesh is allowed to deform naturally without volume constraints
    pass

    # --- 4. Finalize ---
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()


# === 6. BLENDER MODAL OPERATOR ===
class ConjureFingertipOperator(bpy.types.Operator):
    """The main operator that reads hand data and orchestrates actions."""
    bl_idname = "conjure.fingertip_operator"
    bl_label = "Conjure Fingertip Operator"

    _timer = None
    _last_command = "none"
    _initial_camera_matrix = None
    _initial_volume = 1.0 # Default value
    _vertex_velocities = {} # Stores the velocity of each vertex for viscosity simulation
    _history_buffer = None # Holds previous mesh states for the rewind feature
    _current_brush_index = 0
    _current_radius_index = 0
    _last_hand_center = None # For calculating hand movement for the GRAB brush
    _draw_handler = None # For drawing the UI text
    _last_orbit_delta = {"x": 0.0, "y": 0.0}
    marker_states = []
    
    # === DRAW FUNCTIONALITY STATE ===
    _is_drawing = False              # Whether user is currently drawing
    _draw_path = []                  # List of 3D points for current draw stroke
    _pending_draw_objects = []       # List of all draw objects waiting for boolean operations
    _current_draw_object = None      # Current curve object being drawn
    _draw_last_position = None       # Last recorded position to avoid duplicate points
    _draw_release_timer = 0.0        # Timer to make release detection more robust
    _draw_release_threshold = 0.3    # Time threshold before confirming release (300ms for MediaPipe noise)
    _draw_noise_filter_timer = 0.0   # Timer for filtering MediaPipe tracking noise
    _draw_noise_threshold = 0.05     # Threshold for noise filtering (50ms)
    _realtime_preview_curve = None   # Real-time preview curve object

    # === CREATE FUNCTIONALITY STATE ===
    _current_primitive_index = 0     # Index in config.PRIMITIVE_TYPES
    _is_creating = False             # Whether user is currently placing a primitive
    _create_start_pos = None         # Starting position for primitive creation
    _pending_create_objects = []     # List of all create objects waiting for boolean operations
    _preview_object = None           # Current primitive preview object
    _create_thumb_pos = None         # Last thumb position for creation
    _create_index_pos = None         # Last index position for creation
    _last_finger_positions = None    # Store last known finger positions for CREATE sticky mode
    
    # === TWO-PHASE CREATE STATE ===
    _create_phase = "NONE"           # "NONE", "SIZE", "POSITION"
    _create_size_confirmed = 0.5     # Confirmed size from Phase 1
    _size_start_hands = None         # Initial hand positions when entering size mode
    _both_hands_active = False       # Whether both hands are currently active

    def get_mesh_volume(self, mesh_obj):
        """Calculates the volume of a given mesh object using bmesh."""
        if not mesh_obj or mesh_obj.type != 'MESH':
            print("Warning: get_mesh_volume called on an invalid object.")
            return 0.0

        # Use the evaluated dependency graph to get the mesh with all modifiers applied.
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = mesh_obj.evaluated_get(depsgraph)
        mesh_from_eval = obj_eval.to_mesh()

        bm = bmesh.new()
        bm.from_mesh(mesh_from_eval)
        
        # Triangulation is good practice for robust volume calculation.
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        
        volume = bm.calc_volume(signed=True)
        
        # Clean up the temporary bmesh and mesh data
        bm.free()
        obj_eval.to_mesh_clear()
        
        return abs(volume)

    def handle_spawn_primitive(self, primitive_type):
        """
        Spawns a new primitive by duplicating it from the 'PRIMITIVES' collection.
        """
        # Normalize case - accept both "cylinder" and "Cylinder"
        primitive_type = primitive_type.capitalize()
        print(f"DEBUG: handle_spawn_primitive received type: {primitive_type}")

        # --- 1. Find the Primitive Template ---
        # Look inside CONJURE SETUP -> PRIMITIVES collection for the template
        print("DEBUG: Searching for 'CONJURE SETUP/PRIMITIVES' collection...")
        conjure_setup_coll = bpy.data.collections.get("CONJURE SETUP")
        source_collections = conjure_setup_coll.children.get("PRIMITIVES") if conjure_setup_coll else None
        
        if not source_collections:
             # Fallback for older scene structures
            print("DEBUG: Fallback - Searching for top-level 'PRIMITIVES' collection.")
            source_collections = bpy.data.collections.get("PRIMITIVES")
            if not source_collections:
                 print("ERROR: Could not find the 'PRIMITIVES' or 'CONJURE SETUP/PRIMITIVES' collection.")
                 return

        print(f"DEBUG: Found source collection: {source_collections.name}")

        template_obj = source_collections.objects.get(primitive_type)
        
        if not template_obj:
            print(f"ERROR: Primitive '{primitive_type}' not found in collection '{source_collections.name}'.")
            return
        
        print(f"DEBUG: Found template object: {template_obj.name}")

        # --- 2. Clear Existing Deformable Mesh ---
        if config.DEFORM_OBJ_NAME in bpy.data.objects:
            print(f"DEBUG: Removing existing '{config.DEFORM_OBJ_NAME}'.")
            bpy.data.objects.remove(bpy.data.objects[config.DEFORM_OBJ_NAME], do_unlink=True)

        # --- 3. Duplicate and Link the New Mesh ---
        print("DEBUG: Duplicating template object...")
        new_obj = template_obj.copy()
        new_obj.data = template_obj.data.copy() # Also copy mesh data
        new_obj.name = config.DEFORM_OBJ_NAME
        bpy.context.scene.collection.objects.link(new_obj)
        print(f"DEBUG: Successfully spawned '{new_obj.name}' from template '{template_obj.name}'.")
        
        # --- 4. Set as Active and Selected ---
        print("DEBUG: Setting new object as active and selected.")
        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        bpy.context.view_layer.objects.active = new_obj
        
        # --- 4.5. Ensure Visibility for GestureCamera Rendering ---
        print("DEBUG: Setting visibility for GestureCamera rendering...")
        new_obj.hide_viewport = False  # Visible in viewport
        new_obj.hide_render = False    # Visible in renders (KEY FIX!)
        new_obj.hide_select = False    # Selectable
        print("✅ Mesh is now visible for GestureCamera rendering")

        # --- 5. Recalculate Initial Volume and Reset Velocities for Deformation ---
        self._initial_volume = self.get_mesh_volume(new_obj)
        # Reset vertex velocities for the new mesh
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(new_obj.data)
        self._vertex_velocities = {v.index: mathutils.Vector((0,0,0)) for v in bm.verts}
        bm.free()
        print(f"🔧 Set deformation properties - Volume: {self._initial_volume}, Vertices: {len(self._vertex_velocities)}")

    def check_for_state_commands(self, context):
        """
        Check for state-based commands and execute them.
        This handles communication between the launcher and Blender.
        """
        # Read the state file directly (same pattern as check_for_launcher_requests)
        state_file_path = config.STATE_JSON_PATH
        
        try:
            with open(state_file_path, 'r') as f:
                state_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # 🚨 IMPROVED ERROR HANDLING: Don't spam console with errors
            # Only log once per session to avoid console spam
            if not hasattr(self, '_logged_state_error'):
                print(f"🔧 BLENDER: State file issue detected: {e}")
                print("🔧 BLENDER: Waiting for launcher to recover state file...")
                self._logged_state_error = True
            return  # File corrupted or missing, wait for launcher to fix it
        
        command = state_data.get("command")
        
        # PRIORITY CHECK: Handle import_and_process_mesh with highest priority
        if "import_and_process_mesh" in str(state_data):
            print(f"🔍 URGENT: import_and_process_mesh found SOMEWHERE in state file!")
            print(f"🔍 URGENT: Full state data: {state_data}")
            print(f"🔍 URGENT: Exact command value: '{command}' (type: {type(command)})")
            
            # Force processing if command is not exactly matching
            if command != "import_and_process_mesh":
                print(f"🚨 BLENDER: Forcing import_and_process_mesh execution despite command mismatch!")
                command = "import_and_process_mesh"
        
        # PRIORITY PROCESSING: Handle import commands immediately, skip other checks
        if command == "import_and_process_mesh":
            print(f"🚨 BLENDER: PRIORITY - Processing import_and_process_mesh immediately!")
            print(f"🕐 BLENDER: Current time: {time.time()}")
            # Jump directly to import processing (defined below)
        
        # Only log when there's actually a command (reduce console spam)
        if command:
            print(f"🎯 BLENDER: Detected command from state file: {command}")
            
            if command == "spawn_primitive":
                primitive_type = state_data.get("primitive_type", "Cube")
                print(f"🎯 BLENDER: Processing spawn_primitive command with type: {primitive_type}")
                self.spawn_primitive(context, primitive_type)
                # Clear the command (same pattern as existing code)
                state_data["command"] = None
                print(f"🧹 BLENDER: Cleared spawn_primitive command from state file")
                self.safe_write_state_file(state_data)
            
            elif command == "render_gesture_camera":
                # Trigger GestureCamera render for FLUX1.DEPTH
                bpy.ops.conjure.render_gesture_camera()
                # Clear the command
                state_data["command"] = None
                self.safe_write_state_file(state_data)
            
            elif command == "generate_flux_mesh":
                # Handle the FLUX1.DEPTH -> PartPacker pipeline
                self.handle_flux_mesh_generation(context, state_data)
                # Clear the command
                state_data["command"] = None
                self.safe_write_state_file(state_data)
            
            elif command == "import_and_process_mesh":
                # Import and process PartPacker results
                print(f"🎯 BLENDER: Processing import_and_process_mesh command...")
                print(f"🎯 BLENDER: State data: {state_data}")
                
                # Check if operator exists before calling
                try:
                    # Check if the operator is registered
                    if hasattr(bpy.ops.conjure, 'import_and_process_mesh'):
                        print(f"✅ BLENDER: import_and_process_mesh operator is registered")
                    else:
                        print(f"❌ BLENDER: import_and_process_mesh operator NOT REGISTERED!")
                        print(f"🔍 BLENDER: Available conjure operators: {dir(bpy.ops.conjure)}")
                    
                    print(f"🔧 BLENDER: About to call bpy.ops.conjure.import_and_process_mesh()")
                    result = bpy.ops.conjure.import_and_process_mesh()
                    print(f"✅ BLENDER: import_and_process_mesh completed with result: {result}")
                except Exception as e:
                    print(f"❌ BLENDER: Error executing import_and_process_mesh: {e}")
                    import traceback
                    print(f"🔍 BLENDER: Full traceback:\n{traceback.format_exc()}")
                
                # Clear the command using safe StateManager method
                print(f"🧹 BLENDER: Clearing import_and_process_mesh command from state file")
                try:
                    # Use safer file operations with the same locking mechanism  
                    from pathlib import Path
                    import tempfile
                    
                    # Clear the command safely
                    state_data["command"] = None
                    if self.safe_write_state_file(state_data):
                        print(f"✅ BLENDER: Command cleared safely")
                    else:
                        print(f"❌ BLENDER: Failed to clear command")
                    
                except Exception as clear_error:
                    print(f"❌ BLENDER: Error clearing command: {clear_error}")
                    # Still try to clear the command
                    state_data["command"] = None
                    self.safe_write_state_file(state_data)
            
            elif command == "fuse_mesh":
                # Boolean union all segments
                bpy.ops.conjure.fuse_mesh()
                # Clear the command
                state_data["command"] = None
                self.safe_write_state_file(state_data)
            
            elif command == "segment_selection":
                # Check if segments exist before entering selection mode
                segment_objects = [obj for obj in bpy.data.objects 
                                  if obj.type == 'MESH' and obj.name.startswith('seg_')]
                
                # Debug disabled for cleaner console
                # all_mesh_objects = [obj.name for obj in bpy.data.objects if obj.type == 'MESH']
                # print(f"🔍 DEBUG: All mesh objects in scene: {all_mesh_objects}")
                # print(f"🔍 DEBUG: Found {len(segment_objects)} segments: {[obj.name for obj in segment_objects]}")
                
                if segment_objects:
                    # Enable gesture-based segment selection
                    print(f"🎯 BLENDER: Activating segment selection for {len(segment_objects)} segments")
                    bpy.ops.conjure.segment_selection()
                    print(f"✅ BLENDER: Segment selection activated - clearing command to prevent loop")
                    
                    # Clear the command to prevent repeated processing - use safe write method
                    try:
                        from pathlib import Path
                        temp_file = Path(state_file_path).with_suffix('.tmp')
                        state_data["command"] = None
                        
                        if self.safe_write_state_file(state_data):
                            print(f"✅ BLENDER: segment_selection command cleared safely")
                        else:
                            print(f"❌ BLENDER: Failed to clear segment_selection command")
                        
                    except Exception as clear_error:
                        print(f"❌ BLENDER: Error clearing segment_selection command: {clear_error}")
                        # Still try to clear the command
                        state_data["command"] = None
                        self.safe_write_state_file(state_data)
                else:
                    # No segments found - try to import mesh first
                    print("⚠️ DEBUG: No segments found for selection - attempting to import mesh first")
                    mesh_path = state_data.get("mesh_path")
                    if mesh_path:
                        print(f"📦 DEBUG: Found mesh path, importing: {mesh_path}")
                        bpy.ops.conjure.import_and_process_mesh()
                    else:
                        print("❌ DEBUG: No mesh_path found in state - cannot import segments")
                        # Clear the command to prevent repeated attempts
                        state_data["command"] = None
                        state_data["selection_mode"] = "inactive"
                        self.safe_write_state_file(state_data)
        
        # Check for import requests (existing functionality)
        import_request = state_data.get("import_request")
        if import_request == "new":
            # Use the same pattern as check_for_launcher_requests
            area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
            if area:
                try:
                    print("CONJURE: Executing bpy.ops.conjure.import_model() with context override.")
                    with bpy.context.temp_override(area=area):
                        bpy.ops.conjure.import_model('EXEC_DEFAULT')
                    # Clear the import request
                    state_data["import_request"] = "done"
                    self.safe_write_state_file(state_data)
                except Exception as e:
                    print(f"ERROR: Failed to execute conjure.import_model operator: {e}")
            else:
                print("ERROR: Could not find a 3D View area to run the import operator.")

    def handle_flux_mesh_generation(self, context, state_data):
        """
        Handle the complete FLUX1.DEPTH -> PartPacker pipeline
        """
        prompt = state_data.get("prompt", "")
        seed = state_data.get("seed", 0)
        min_volume_threshold = state_data.get("min_volume_threshold", 0.001)
        
        print(f"🚀 Starting FLUX mesh generation pipeline...")
        print(f"📝 Prompt: {prompt}")
        print(f"🎲 Seed: {seed}")
        
        # Step 1: Render GestureCamera
        print("📸 Step 1: Rendering GestureCamera...")
        bpy.ops.conjure.render_gesture_camera()
        
        # Step 2: Save prompt to userPrompt.txt
        print("📝 Step 2: Saving prompt...")
        self.save_prompt_to_file(prompt)
        
        # Step 3: Set state to trigger the API pipeline
        # The main launcher will detect this and handle the API calls
        print("🔄 Step 3: Triggering API pipeline...")
        
        # DEBUG: Read current state before update
        current_state = self.safe_read_state_file()
        print(f"🔍 BLENDER: Read state file, current flux_pipeline_request = '{current_state.get('flux_pipeline_request', 'missing')}')")
        
        # Update state file with flux pipeline request
        print(f"🔧 BLENDER: Writing flux_pipeline_request = 'new' to state file...")
        current_state.update({
            "flux_pipeline_request": "new",
            "flux_prompt": prompt,
            "flux_seed": seed,
            "min_volume_threshold": min_volume_threshold
        })
        
        self.safe_write_state_file(current_state)
        
        # DEBUG: Verify the write was successful
        verify_state = self.safe_read_state_file()
        written_value = verify_state.get('flux_pipeline_request', 'missing')
        print(f"✅ BLENDER: Verified write - flux_pipeline_request = '{written_value}'")
        if written_value != "new":
            print(f"❌ BLENDER: Write verification FAILED! Expected 'new', got '{written_value}'")
        else:
            print(f"⏳ BLENDER: Waiting 1 second for main launcher to detect...")
            time.sleep(1.0)  # Give main launcher time to detect the change
            print(f"🔍 BLENDER: Step 3 completed - main launcher should have detected the request")
    
    def save_prompt_to_file(self, prompt):
        """Save the prompt to userPrompt.txt for the generation pipeline"""
        prompt_dir = config.DATA_DIR / "generated_text"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        
        prompt_file = prompt_dir / "userPrompt.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        
        print(f"✅ Prompt saved to: {prompt_file}")

    def spawn_primitive(self, context, primitive_type):
        """
        Spawn a primitive object and replace the current Mesh.
        """
        # Normalize case - accept both "cylinder" and "Cylinder"
        primitive_type = primitive_type.capitalize()
        print(f"Spawning primitive: {primitive_type}")
        
        # Remove existing mesh if it exists
        existing_mesh = bpy.data.objects.get("Mesh")
        if existing_mesh:
            bpy.data.objects.remove(existing_mesh, do_unlink=True)
            print("✅ Removed existing mesh")
        
        # Create the new primitive
        if primitive_type == "Sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(location=(0, 0, 0))
            print("✅ Created sphere primitive")
        elif primitive_type == "Cube":
            bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
            print("✅ Created cube primitive")
        elif primitive_type == "Cone":
            bpy.ops.mesh.primitive_cone_add(location=(0, 0, 0))
            print("✅ Created cone primitive")
        elif primitive_type == "Cylinder":
            bpy.ops.mesh.primitive_cylinder_add(location=(0, 0, 0))
            print("✅ Created cylinder primitive")
        elif primitive_type == "Disk":
            bpy.ops.mesh.primitive_circle_add(location=(0, 0, 0), fill_type='NGON')
            print("✅ Created disk primitive")
        elif primitive_type == "Torus":
            bpy.ops.mesh.primitive_torus_add(location=(0, 0, 0))
            print("✅ Created torus primitive")
        elif primitive_type == "Head":
            # Create a rough head shape using a sphere with some deformation
            bpy.ops.mesh.primitive_uv_sphere_add(location=(0, 0, 0))
            head_obj = context.active_object
            head_obj.scale = (0.8, 1.0, 1.2)  # Make it more head-like
            print("✅ Created head primitive (scaled sphere)")
        elif primitive_type == "Body":
            # Create a rough body shape using a cylinder
            bpy.ops.mesh.primitive_cylinder_add(location=(0, 0, 0))
            body_obj = context.active_object
            body_obj.scale = (1.2, 0.8, 2.0)  # Make it more body-like
            print("✅ Created body primitive (scaled cylinder)")
        else:
            # Default to cube if unknown type
            print(f"⚠️ Unknown primitive type '{primitive_type}', defaulting to cube")
            bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
            print("✅ Created default cube primitive")
        
        # Rename the new object to "Mesh"
        new_obj = context.active_object
        new_obj.name = "Mesh"
        
        print(f"✅ Spawned {primitive_type} as 'Mesh'")
        
        # Recalculate initial volume for deformation system
        self._initial_volume = self.get_mesh_volume(new_obj)
        # Reset vertex velocities for the new mesh
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(new_obj.data)
        self._vertex_velocities = {v.index: mathutils.Vector((0,0,0)) for v in bm.verts}
        bm.free()
        print(f"🔧 Updated deformation properties - Volume: {self._initial_volume}, Vertices: {len(self._vertex_velocities)}")
        
        # Clear the history since we have a new starting point
        self.mesh_history.clear()
        self.add_to_history()

    def draw_ui_text(self, context):
        """Draws the current brush name and user prompt on the viewport."""
        font_id = 0  # Default font
        
        # Draw Brush Name
        blf.position(font_id, 15, 60, 0)
        blf.size(font_id, 20)
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        try:
            active_brush = config.BRUSH_TYPES[self._current_brush_index]
        except (ReferenceError, AttributeError):
            active_brush = "UNKNOWN"
        blf.draw(font_id, f"Brush: {active_brush}")

        # Draw Radius Size
        blf.position(font_id, 15, 30, 0)
        blf.size(font_id, 20)
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        try:
            active_radius = config.RADIUS_LEVELS[self._current_radius_index]['name'].upper()
        except (ReferenceError, AttributeError):
            active_radius = "UNKNOWN"
        blf.draw(font_id, f"Radius: {active_radius}")
        
        # Draw Primitive Type (only when in CREATE mode)
        try:
            active_brush = config.BRUSH_TYPES[self._current_brush_index]
            if active_brush == "CREATE":
                blf.position(font_id, 15, 0, 0)  # Bottom position
                blf.size(font_id, 20)
                blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
                try:
                    active_primitive = config.PRIMITIVE_TYPES[self._current_primitive_index]
                except (IndexError, AttributeError):
                    active_primitive = "UNKNOWN"
                blf.draw(font_id, f"Primitive: {active_primitive}")
        except (ReferenceError, AttributeError):
            pass  # Silently handle any config access errors
        
        # Draw User Prompt (centered in bottom half of screen)
        self.draw_user_prompt(context, font_id)
    
    def draw_user_prompt(self, context, font_id):
        """Draw the user prompt text in the middle column with text wrapping."""
        try:
            # Read userPrompt.txt from generated_text (where voice system writes)
            project_root = Path(__file__).parent.parent.parent.parent
            prompt_file = project_root / "data" / "generated_text" / "userPrompt.txt"
            
            prompt_text = "USER PROMPT: txt"  # Default fallback
            if prompt_file.exists():
                try:
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        prompt_content = f.read().strip()
                    if prompt_content:
                        prompt_text = prompt_content
                except Exception as e:
                    print(f"Error reading userPrompt.txt: {e}")
            
            # Get viewport dimensions
            region = context.region
            if not region:
                return
                
            viewport_width = region.width
            viewport_height = region.height
            
            # Define middle column (divide screen into 3 columns)
            column_width = viewport_width / 3
            middle_column_start = column_width  # Start of middle column
            middle_column_end = column_width * 2  # End of middle column
            usable_width = column_width * 0.9  # 90% of column width for padding
            
            # Use same font size as brush info for consistency
            blf.size(font_id, 20)
            
            # Wrap text to fit in middle column
            wrapped_lines = self.wrap_text_to_width(prompt_text, font_id, usable_width)
            
            # Calculate starting Y position (bottom half, centered vertically for text block)
            line_height = 25  # Slightly more than font size for line spacing
            total_text_height = len(wrapped_lines) * line_height
            start_y = (viewport_height * 0.25) + (total_text_height / 2)  # Center the text block
            
            # Draw each line
            blf.color(font_id, 1.0, 1.0, 1.0, 1.0)  # White color
            for i, line in enumerate(wrapped_lines):
                # Center each line within the middle column
                line_width, _ = blf.dimensions(font_id, line)
                x_pos = middle_column_start + (column_width - line_width) / 2
                y_pos = start_y - (i * line_height)
                
                blf.position(font_id, x_pos, y_pos, 0)
                blf.draw(font_id, line)
            
        except Exception as e:
            print(f"Error drawing user prompt: {e}")
    
    def wrap_text_to_width(self, text, font_id, max_width):
        """Wrap text to fit within the specified width, breaking at word boundaries."""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # Test if adding this word would exceed the width
            test_line = current_line + (" " if current_line else "") + word
            test_width, _ = blf.dimensions(font_id, test_line)
            
            if test_width <= max_width:
                current_line = test_line
            else:
                # If current_line is not empty, finish it and start a new line
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # Single word is too long, break it
                    lines.append(word)
                    current_line = ""
        
        # Add the last line if there's content
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def detect_gesture(self, finger_positions_3d):
        """
        Detect special gestures from finger positions.
        Returns: 'fist', 'thumb_index_pinch', 'pointing', or 'none'
        """
        try:
            # Need at least right hand fingers (thumb=5, index=6, middle=7, ring=8, pinky=9)
            if len(finger_positions_3d) < 10:
                return 'none'
            
            # Get right hand finger positions (indices 5-9)
            thumb = finger_positions_3d[5]
            index = finger_positions_3d[6] 
            middle = finger_positions_3d[7]
            ring = finger_positions_3d[8]
            pinky = finger_positions_3d[9]
            
            # Count how many fingers are detected (not None)
            detected_fingers = [f for f in [thumb, index, middle, ring, pinky] if f is not None]
            
            if len(detected_fingers) < 2:
                return 'none'
            
            # FIST DETECTION: All fingers close together (low variance in positions)
            if len(detected_fingers) >= 4:  # Need at least 4 fingers for fist detection
                # Calculate centroid of detected fingers
                centroid = sum(detected_fingers, mathutils.Vector()) / len(detected_fingers)
                
                # Calculate maximum distance from centroid
                max_distance = max((finger - centroid).length for finger in detected_fingers)
                
                # If all fingers are within a small radius, it's a fist
                fist_threshold = 0.3  # Adjust based on hand tracking precision
                if max_distance < fist_threshold:
                    return 'fist'
            
            # THUMB+INDEX PINCH DETECTION: Thumb and index close together
            if thumb is not None and index is not None:
                distance = (thumb - index).length
                pinch_threshold = 0.15  # Adjust based on hand tracking precision
                if distance < pinch_threshold:
                    return 'thumb_index_pinch'
            
            # DEFAULT: Just pointing
            if index is not None:
                return 'pointing'
                
            return 'none'
            
        except Exception as e:
            print(f"⚠️ Error in gesture detection: {e}")
            return 'none'

    def handle_segment_selection(self, context, finger_positions_3d, region, rv3d, depsgraph):
        """Handle segment selection with gesture-based confirmation and fusion"""
        try:
            # Initialize selection state if not exists
            if not hasattr(self, '_selection_state'):
                self._selection_state = {
                    'current_selected_segment': None,
                    'stability_counter': 0,
                    'stability_threshold': 15,  # Frames to wait before changing selection
                    'candidate_segment': None,
                    'gesture_confirmation_counter': 0,
                    'gesture_confirmation_threshold': 10,  # Frames to wait for gesture confirmation
                    'last_gesture': 'none'
                }
                print("🎯 Initialized segment selection state with gesture detection")
        except (ReferenceError, AttributeError) as e:
            print(f"⚠️ Segment selection error (operator removed): {e}")
            return
        
        try:
            # Restore selected segment from scene materials if state was lost
            if not self._selection_state['current_selected_segment']:
                self.restore_selected_segment_from_scene()
            
            # Get segment objects
            segment_objects = [obj for obj in bpy.data.objects 
                              if obj.type == 'MESH' and obj.name.startswith('seg_')]
            
            if not segment_objects:
                return
            
            # Get materials
            default_mat = bpy.data.materials.get("default_material")
            selected_mat = bpy.data.materials.get("selected_material")
            
            if not default_mat or not selected_mat:
                print("❌ Required materials not found in scene")
                return
            
            # Check if we have right hand index finger (finger 6)
            if len(finger_positions_3d) <= 6 or not finger_positions_3d[6]:
                # No finger detected - keep current selection unchanged
                return
            
            index_finger_pos = finger_positions_3d[6]
            
            # Cast ray from index finger to detect segment
            detected_segment = self.detect_segment_under_finger(
                index_finger_pos, segment_objects, context, region, rv3d, depsgraph
            )
        except (ReferenceError, AttributeError) as e:
            print(f"⚠️ Segment selection data access error (operator removed): {e}")
            return
        except Exception as e:
            print(f"⚠️ Unexpected error in segment selection setup: {e}")
            return
        
        try:
            # Detect current gesture
            current_gesture = self.detect_gesture(finger_positions_3d)
            
            # Handle gesture confirmation for actions
            if current_gesture == self._selection_state['last_gesture']:
                self._selection_state['gesture_confirmation_counter'] += 1
            else:
                self._selection_state['last_gesture'] = current_gesture
                self._selection_state['gesture_confirmation_counter'] = 0
            
            # GESTURE ACTIONS (only when gesture is held stable)
            if self._selection_state['gesture_confirmation_counter'] >= self._selection_state['gesture_confirmation_threshold']:
                
                # FIST GESTURE: Fuse all segments
                if current_gesture == 'fist':
                    print("✊ FIST GESTURE DETECTED - Fusing all segments...")
                    try:
                        bpy.ops.conjure.fuse_mesh()
                        print("✅ Mesh fusion triggered by fist gesture")
                        # Exit selection mode after fusion
                        bpy.ops.conjure.exit_selection_mode()
                        return
                    except Exception as e:
                        print(f"❌ Error during fist gesture fusion: {e}")
                
                # THUMB+INDEX PINCH: Confirm current selection
                elif current_gesture == 'thumb_index_pinch' and self._selection_state['current_selected_segment']:
                    print("🤏 PINCH GESTURE DETECTED - Confirming selection...")
                    try:
                        bpy.ops.conjure.exit_selection_mode()
                        print("✅ Selection confirmed by pinch gesture")
                        return
                    except Exception as e:
                        print(f"❌ Error during pinch gesture confirmation: {e}")
            
            # POINTING SELECTION (only when pointing)
            if current_gesture == 'pointing':
                # Stability system: only change selection after consistent detection
                if detected_segment == self._selection_state['candidate_segment']:
                    # Same segment detected - increment stability counter
                    self._selection_state['stability_counter'] += 1
                else:
                    # Different segment detected - reset counter
                    self._selection_state['candidate_segment'] = detected_segment
                    self._selection_state['stability_counter'] = 0
                
                # Only change selection if we've had stable detection and it's different from current
                if (self._selection_state['stability_counter'] >= self._selection_state['stability_threshold'] and 
                    self._selection_state['candidate_segment'] != self._selection_state['current_selected_segment']):
                    
                    # Clear previous selection
                    if self._selection_state['current_selected_segment']:
                        self.apply_material_to_segment(self._selection_state['current_selected_segment'], default_mat)
                    
                    # Apply new selection
                    new_selected_segment = self._selection_state['candidate_segment']
                    if new_selected_segment:
                        self.apply_material_to_segment(new_selected_segment, selected_mat)
                        print(f"🎯 Selected segment: {new_selected_segment.name}")
                    else:
                        print("🌌 Deselected - pointing at empty space")
                    
                    # Update current selection
                    self._selection_state['current_selected_segment'] = new_selected_segment
                    self._selection_state['stability_counter'] = 0  # Reset counter
                    
        except (ReferenceError, AttributeError) as e:
            print(f"⚠️ Segment selection update error (operator removed): {e}")
            return
        except Exception as e:
            print(f"⚠️ Unexpected error in segment selection update: {e}")
            return
    
    def restore_selected_segment_from_scene(self):
        """Restore the selected segment by checking which segment has the selected material"""
        try:
            selected_mat = bpy.data.materials.get("selected_material")
            if not selected_mat:
                return
                
            segment_objects = [obj for obj in bpy.data.objects 
                              if obj.type == 'MESH' and obj.name.startswith('seg_')]
            
            # Find all segments with selected material
            selected_segments = []
            for obj in segment_objects:
                try:
                    if obj.data.materials and obj.data.materials[0] == selected_mat:
                        selected_segments.append(obj)
                except (ReferenceError, AttributeError):
                    # Skip objects that have been removed
                    continue
        except (ReferenceError, AttributeError) as e:
            print(f"⚠️ Error restoring segment selection (operator removed): {e}")
            return
        except Exception as e:
            print(f"⚠️ Unexpected error restoring segment selection: {e}")
            return
        
        if len(selected_segments) == 0:
            # No selection found - that's fine
            return
        elif len(selected_segments) == 1:
            # Perfect - only one segment is selected
            self._selection_state['current_selected_segment'] = selected_segments[0]
            print(f"🔄 Restored selected segment from scene: {selected_segments[0].name}")
        else:
            # Multiple segments are selected - fix it by keeping only the first one
            print(f"⚠️ Found {len(selected_segments)} segments with selected material - fixing...")
            self._selection_state['current_selected_segment'] = selected_segments[0]
            default_mat = bpy.data.materials.get("default_material")
            if default_mat:
                for obj in selected_segments[1:]:
                    print(f"🧹 Clearing incorrect selection from {obj.name}")
                    self.apply_material_to_segment(obj, default_mat)
            print(f"✅ Fixed multiple selections - kept {selected_segments[0].name}")
    
    def detect_segment_under_finger(self, finger_pos, segment_objects, context, region, rv3d, depsgraph):
        """Cast ray from finger position to detect which segment is being touched"""
        try:
            if not region or not rv3d:
                return None
            
            # Convert 3D finger position to 2D screen coordinates
            finger_2d = location_3d_to_region_2d(region, rv3d, finger_pos)
            if not finger_2d:
                return None
            
            # Cast ray from camera through finger position
            ray_origin = region_2d_to_origin_3d(region, rv3d, finger_2d)
            ray_direction = region_2d_to_vector_3d(region, rv3d, finger_2d)
            
            if not ray_origin or not ray_direction:
                return None
            
            # Single raycast to find what's under the finger
            hit, loc, normal, _, hit_obj, _ = context.scene.ray_cast(
                depsgraph, ray_origin, ray_direction
            )
        except (ReferenceError, AttributeError) as e:
            print(f"⚠️ Ray casting error (operator removed): {e}")
            return None
        except Exception as e:
            print(f"⚠️ Unexpected ray casting error: {e}")
            return None
        
        # Return the hit segment
        if hit and hit_obj in segment_objects:
            return hit_obj
        
        return None
    
    def reset_segment_materials(self, segment_objects, default_mat):
        """Reset all segments to default material"""
        for segment in segment_objects:
            self.apply_material_to_segment(segment, default_mat)
    
    def apply_material_to_segment(self, segment, material):
        """Apply material to a segment object, only if it needs to change"""
        if not segment or not material:
            print(f"⚠️ Cannot apply material: segment={segment}, material={material}")
            return
        
        try:
            # Check if the segment already has the correct material applied
            if (segment.data.materials and 
                len(segment.data.materials) > 0 and 
                segment.data.materials[0] == material):
                # Material is already correct, no need to reapply
                return
            
            # Clear existing materials first
            segment.data.materials.clear()
            # Add the new material
            segment.data.materials.append(material)
            # Force viewport update
            segment.data.update()
            print(f"✅ Applied {material.name} to {segment.name}")
        except Exception as e:
            print(f"❌ Error applying material to {segment.name}: {e}")
    
    def clear_all_segment_selections(self):
        """Clear selection material from ALL segments and reset to default"""
        default_mat = bpy.data.materials.get("default_material")
        if not default_mat:
            print("❌ Cannot clear selections: default_material not found")
            return
        
        segment_objects = [obj for obj in bpy.data.objects 
                          if obj.type == 'MESH' and obj.name.startswith('seg_')]
        
        for obj in segment_objects:
            self.apply_material_to_segment(obj, default_mat)
        
        print(f"🧹 Cleared selection from all {len(segment_objects)} segments")

    def safe_read_state_file(self):
        """Safely read state.json with retry mechanism for permission errors."""
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                with open(config.STATE_JSON_PATH, 'r') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}  # File not found or invalid JSON, return empty dict
            except PermissionError as e:
                if attempt < max_retries - 1:
                    print(f"Permission error reading state.json (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"Failed to read state.json after {max_retries} attempts: {e}")
                    return {}
            except Exception as e:
                print(f"Unexpected error reading state.json: {e}")
                return {}

    def safe_write_state_file(self, state_data):
        """Safely write to state.json with retry mechanism for permission errors."""
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                with open(config.STATE_JSON_PATH, 'w') as f:
                    json.dump(state_data, f, indent=4)
                return True  # Success
            except PermissionError as e:
                if attempt < max_retries - 1:
                    print(f"Permission error writing state.json (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"Failed to write state.json after {max_retries} attempts: {e}")
                    return False
            except Exception as e:
                print(f"Unexpected error writing state.json: {e}")
                return False

    def check_for_launcher_requests(self):
        """Checks state.json for commands from the launcher/agent."""
        # Read the state file safely
        state_data = self.safe_read_state_file()
        if not state_data:
            return  # No valid state data available

        command = state_data.get("command")

        if command == "spawn_primitive":
            primitive_type = state_data.get("primitive_type")
            if primitive_type:
                self.handle_spawn_primitive(primitive_type)
                # Clear the command in the state file so it doesn't run again
                print(f"DEBUG: Clearing command '{command}' from state file.")
                state_data["command"] = None
                state_data["primitive_type"] = None
                self.safe_write_state_file(state_data)
        
        # We can add more command handlers here with elif blocks
        elif command == "import_last_model":
            # We need to override the context to ensure the operator runs in the 3D view
            area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
            if area:
                try:
                    print("DEBUG: Executing bpy.ops.conjure.import_model() with context override.")
                    with bpy.context.temp_override(area=area):
                        bpy.ops.conjure.import_model('EXEC_DEFAULT')
                except Exception as e:
                    print(f"ERROR: Failed to execute conjure.import_model operator: {e}")
            else:
                print("ERROR: Could not find a 3D View area to run the import operator.")
            
            # Clear the command
            print(f"DEBUG: Clearing command '{command}' from state file.")
            state_data["command"] = None
            self.safe_write_state_file(state_data)

    # === DRAW FUNCTIONALITY METHODS ===
    
    def start_drawing(self, context, start_position):
        """Start a new drawing stroke with real-time preview"""
        self._is_drawing = True
        self._draw_path = [start_position.copy()]
        self._draw_last_position = start_position.copy()
        
        # Create real-time preview curve immediately
        self.create_realtime_preview_curve(context)
        
        print(f"🎨 Started drawing with real-time preview at: {start_position}")
    
    def add_draw_point(self, context, new_position):
        """Add a point to the current drawing path"""
        if not self._is_drawing:
            return
            
        # Check minimum distance to avoid too many points (reduced threshold for easier drawing)
        min_distance = 0.2   # Minimum distance between points (1/4 of original 0.05 * 4 = 0.2)
        if self._draw_last_position and (new_position - self._draw_last_position).length < min_distance:
            return
            
        self._draw_path.append(new_position.copy())
        self._draw_last_position = new_position.copy()
        
        # Update real-time preview curve
        self.update_realtime_preview_curve(context)
        
        print(f"🎨 Added draw point: {new_position} (total: {len(self._draw_path)})")
    
    def finish_drawing(self, context):
        """Complete the drawing stroke and bake the real-time preview"""
        print(f"🔍 FINISH_DRAWING DEBUG: _is_drawing={self._is_drawing}, draw_path_length={len(self._draw_path)}, has_preview={self._realtime_preview_curve is not None}")
        
        if not self._is_drawing or len(self._draw_path) < 2:
            print(f"⚠️ Not enough points to create curve (have {len(self._draw_path)} points, need at least 2)")
            self._is_drawing = False
            self._draw_path = []
            # Clean up preview if it exists
            self.cleanup_realtime_preview(context)
            return None
            
        print(f"🎨 Finishing draw with {len(self._draw_path)} points - baking real-time preview")
        
        # Bake the real-time preview into final object
        final_obj = self.bake_realtime_preview(context)
        
        if final_obj:
            print(f"✅ Real-time preview baked successfully: {final_obj.name}")
            # Add to pending objects for batch processing
            self._pending_draw_objects.append(final_obj)
            print(f"📝 Added to pending objects ({len(self._pending_draw_objects)} total)")
            print(f"🔍 DEBUG: Pending object names: {[obj.name for obj in self._pending_draw_objects]}")
            self._current_draw_object = final_obj
        else:
            print("❌ Failed to create curve")
            self._current_draw_object = None
        
        # Reset drawing state
        self._is_drawing = False
        self._draw_path = []
        self._draw_last_position = None
        
        return self._current_draw_object
    
    # === REAL-TIME DRAW PREVIEW METHODS ===
    
    def create_realtime_preview_curve(self, context):
        """Create a real-time preview curve that updates as the user draws."""
        try:
            # Create a new curve object for real-time preview (matching original DRAWbrush structure)
            curve_data = bpy.data.curves.new(name="RealtimeDrawPreview", type='CURVE')
            curve_data.dimensions = '3D'
            
            # Apply same basic properties as original DRAWbrush curve
            try:
                curve_data.twist_method = 'MINIMUM'
            except AttributeError:
                pass
            
            try:
                curve_data.twist_smooth = 0.0
            except AttributeError:
                pass
            
            curve_data.fill_mode = 'FULL'
            
            # Create the curve object
            self._realtime_preview_curve = bpy.data.objects.new("RealtimeDrawPreview", curve_data)
            bpy.context.collection.objects.link(self._realtime_preview_curve)
            
            # Make it visible and slightly transparent for preview
            material = bpy.data.materials.new(name="RealtimePreviewMaterial")
            material.use_nodes = True
            material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (0.8, 0.8, 1.0, 0.7)  # Light blue, semi-transparent
            self._realtime_preview_curve.data.materials.append(material)
            
            print("🎨 Created real-time preview curve")
            
        except Exception as e:
            print(f"❌ Error creating real-time preview curve: {e}")
    
    def update_realtime_preview_curve(self, context):
        """Update the real-time preview curve with current path."""
        if not self._realtime_preview_curve or len(self._draw_path) < 2:
            return
            
        try:
            # Clear existing splines
            curve_data = self._realtime_preview_curve.data
            curve_data.splines.clear()
            
            # Create simplified bezier curve from current path
            simplified_points = self.simplify_path_to_4_points(self._draw_path)
            
            # Create bezier spline
            spline = curve_data.splines.new(type='BEZIER')
            spline.bezier_points.add(len(simplified_points) - 1)
            
            # Set points and handles
            for i, point in enumerate(simplified_points):
                bp = spline.bezier_points[i]
                bp.co = point
                bp.handle_left_type = 'AUTO'
                bp.handle_right_type = 'AUTO'
            
            # Apply minimal curve properties - DRAWbrush GeometryNode will handle the geometry
            curve_data.fill_mode = 'FULL'
            # Don't set extrude/bevel here - DRAWbrush GeometryNode creates the variable thickness
            
            # Update the object (Blender 4.x compatible)
            bpy.context.view_layer.update()
            
            # Apply DRAWbrush GeometryNodes - but only once when first created
            if not any(mod.name == "DRAWbrush" for mod in self._realtime_preview_curve.modifiers):
                self.apply_realtime_geometry_preview()
            
        except Exception as e:
            print(f"❌ Error updating real-time preview: {e}")
    
    def apply_realtime_geometry_preview(self):
        """Apply GeometryNodes modifier to real-time preview for live strip visualization."""
        try:
            if not self._realtime_preview_curve:
                return
                
            # Check if DRAWbrush GeometryNode modifier already exists
            existing_modifier = None
            for modifier in self._realtime_preview_curve.modifiers:
                if modifier.name == "DRAWbrush":
                    existing_modifier = modifier
                    break
            
            # Apply DRAWbrush GeometryNode modifier if not exists
            if not existing_modifier:
                drawbrush_node_group = bpy.data.node_groups.get("DRAWbrush")
                if drawbrush_node_group:
                    modifier = self._realtime_preview_curve.modifiers.new(name="DRAWbrush", type='NODES')
                    modifier.node_group = drawbrush_node_group
                    print("🎨 Applied DRAWbrush GeometryNodes to real-time preview")
                    print(f"🔍 DRAWbrush should create variable thickness from {len(self._draw_path)} bezier points")
                else:
                    print("⚠️ DRAWbrush node group not found - using fallback curve properties")
                    # Fallback to basic curve properties if DRAWbrush not available
                    curve_data = self._realtime_preview_curve.data
                    curve_data.extrude = 0.01
                    curve_data.bevel_depth = 0.12
                    curve_data.bevel_resolution = 6
                    curve_data.use_fill_caps = True
            
        except Exception as e:
            print(f"❌ Error applying real-time geometry preview: {e}")
    
    def bake_realtime_preview(self, context):
        """Bake the real-time preview into a final mesh object."""
        try:
            print(f"🔍 BAKE_PREVIEW DEBUG: Starting bake process...")
            print(f"🔍 BAKE_PREVIEW DEBUG: _realtime_preview_curve = {self._realtime_preview_curve}")
            
            if not self._realtime_preview_curve:
                print("❌ No real-time preview to bake")
                return None
            
            if self._realtime_preview_curve.name not in bpy.data.objects:
                print("❌ Real-time preview curve no longer exists in scene")
                return None
            
            # Select the preview curve and make it active
            bpy.context.view_layer.objects.active = self._realtime_preview_curve
            bpy.ops.object.select_all(action='DESELECT')
            self._realtime_preview_curve.select_set(True)
            
            # SIMPLE: Just convert to mesh immediately
            print("   🔧 Converting curve to mesh (simple & clean)...")
            bpy.ops.object.convert(target='MESH')
            print("   ✅ Converted to mesh successfully")
            
            # Apply selection material
            self.apply_selection_material(self._realtime_preview_curve)
            
            print("✅ Real-time preview baked successfully")
            
            # Rename to final object name
            final_name = f"DrawCurve_{len(self._pending_draw_objects)+1:03d}"
            self._realtime_preview_curve.name = final_name
            
            # Return the baked object and clear preview reference
            baked_obj = self._realtime_preview_curve
            self._realtime_preview_curve = None
            
            return baked_obj
            
        except Exception as e:
            print(f"❌ Error baking real-time preview: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def cleanup_realtime_preview(self, context):
        """Clean up the real-time preview curve if drawing is cancelled."""
        try:
            if self._realtime_preview_curve:
                # Remove the preview object
                bpy.data.objects.remove(self._realtime_preview_curve, do_unlink=True)
                self._realtime_preview_curve = None
                print("🧹 Cleaned up real-time preview")
        except Exception as e:
            print(f"❌ Error cleaning up real-time preview: {e}")
    
    def simplify_path_to_4_points(self, path_points):
        """Simplify a path to exactly 4 control points: start, 1/4, 3/4, end with smooth interpolation"""
        import mathutils
        
        if len(path_points) < 2:
            return path_points
            
        # Always use start and end points
        start_point = mathutils.Vector(path_points[0])
        end_point = mathutils.Vector(path_points[-1])
        
        if len(path_points) == 2:
            # For 2 points, create intermediate points at 1/3 and 2/3 for smooth curve
            direction = end_point - start_point
            point_1_4 = start_point + direction * 0.33
            point_3_4 = start_point + direction * 0.67
            return [start_point, point_1_4, point_3_4, end_point]
        
        # Calculate total path length for accurate positioning
        total_length = 0.0
        segment_lengths = []
        
        for i in range(len(path_points) - 1):
            current_point = mathutils.Vector(path_points[i])
            next_point = mathutils.Vector(path_points[i + 1])
            segment_length = (next_point - current_point).length
            segment_lengths.append(segment_length)
            total_length += segment_length
        
        if total_length == 0:
            # Fallback for zero-length paths
            return [start_point, start_point, end_point, end_point]
        
        # Find points at 1/4 and 3/4 of total path length using interpolation
        target_1_4_length = total_length * 0.25
        target_3_4_length = total_length * 0.75
        
        def find_point_at_length(target_length):
            """Find the 3D point at a specific length along the path using linear interpolation"""
            current_length = 0.0
            
            for i, segment_length in enumerate(segment_lengths):
                if current_length + segment_length >= target_length:
                    # Target point is within this segment
                    remaining_length = target_length - current_length
                    ratio = remaining_length / segment_length if segment_length > 0 else 0
                    
                    # Linear interpolation between path_points[i] and path_points[i+1]
                    point_a = mathutils.Vector(path_points[i])
                    point_b = mathutils.Vector(path_points[i + 1])
                    interpolated_point = point_a.lerp(point_b, ratio)
                    return interpolated_point
                    
                current_length += segment_length
            
            # Fallback: return end point if target_length exceeds total
            return end_point
        
        # Calculate the 1/4 and 3/4 points along the path
        point_1_4 = find_point_at_length(target_1_4_length)
        point_3_4 = find_point_at_length(target_3_4_length)
        
        print(f"🎯 Path simplified: {len(path_points)} points → 4 control points")
        print(f"   Start: {start_point}")
        print(f"   1/4 (25%): {point_1_4}")
        print(f"   3/4 (75%): {point_3_4}")
        print(f"   End: {end_point}")
        
        return [start_point, point_1_4, point_3_4, end_point]
    
    # === TWO-PHASE CREATE HELPER METHODS ===
    
    def detect_both_hands_active(self, finger_positions_3d):
        """Check if both hands have index+thumb active"""
        if len(finger_positions_3d) < 10:
            return False, None, None, None, None
            
        # Left hand: index=1, thumb=0
        left_thumb = finger_positions_3d[0]
        left_index = finger_positions_3d[1]
        
        # Right hand: index=6, thumb=5  
        right_thumb = finger_positions_3d[5]
        right_index = finger_positions_3d[6]
        
        # Check if both hands have thumb+index detected
        left_active = (left_thumb is not None and left_index is not None)
        right_active = (right_thumb is not None and right_index is not None)
        
        both_active = left_active and right_active
        
        return both_active, left_thumb, left_index, right_thumb, right_index
    
    def calculate_hands_distance(self, left_thumb, left_index, right_thumb, right_index):
        """Calculate distance between hand centers for size control"""
        import mathutils
        
        # Calculate center of each hand
        left_center = (mathutils.Vector(left_thumb) + mathutils.Vector(left_index)) / 2
        right_center = (mathutils.Vector(right_thumb) + mathutils.Vector(right_index)) / 2
        
        # Distance between hand centers
        raw_distance = (right_center - left_center).length
        
        # SCALE FACTOR: Multiply by 3.0 to make hand distance more intuitive
        # Raw distance might be small (0.2-1.0), but we want primitives sized 0.6-3.0+
        scaled_distance = raw_distance * 3.0
        
        print(f"🎯 DISTANCE DEBUG: raw={raw_distance:.3f}, scaled={scaled_distance:.3f}")
        print(f"   Left center: {left_center}")
        print(f"   Right center: {right_center}")
        
        return scaled_distance, left_center, right_center
    
    def start_size_phase(self, context, left_thumb, left_index, right_thumb, right_index):
        """Start Phase 1: Size definition with both hands"""
        print("🎯 CREATE Phase 1: SIZE DEFINITION started")
        self._create_phase = "SIZE"
        self._both_hands_active = True
        
        # Store initial hand positions
        self._size_start_hands = {
            'left_thumb': left_thumb.copy(),
            'left_index': left_index.copy(), 
            'right_thumb': right_thumb.copy(),
            'right_index': right_index.copy()
        }
        
        # Calculate initial size and create preview
        distance, left_center, right_center = self.calculate_hands_distance(left_thumb, left_index, right_thumb, right_index)
        
        # Clamp size to reasonable bounds  
        size = max(0.1, min(distance, 10.0))
        self._create_size_confirmed = size
        
        print(f"🎯 Initial size: {size:.2f} (scaled distance between hands)")
        
        # Create preview object at midpoint between hands
        preview_center = (left_center + right_center) / 2
        self.create_size_preview(context, preview_center, size)
    
    def update_size_phase(self, context, left_thumb, left_index, right_thumb, right_index):
        """Update Phase 1: Live size adjustment"""
        distance, left_center, right_center = self.calculate_hands_distance(left_thumb, left_index, right_thumb, right_index)
        
        # Clamp size to reasonable bounds
        size = max(0.1, min(distance, 10.0))
        self._create_size_confirmed = size
        
        # Update preview location and size
        preview_center = (left_center + right_center) / 2
        
        if self._preview_object and self._preview_object.name in bpy.data.objects:
            # Update existing preview
            self._preview_object.location = preview_center
            # Apply uniform scaling based on size
            self._preview_object.scale = (size, size, size)
            print(f"🎯 Size updated: {size:.2f} (scale applied: {self._preview_object.scale})")
        else:
            # Recreate preview if lost
            self.create_size_preview(context, preview_center, size)
    
    def create_size_preview(self, context, center, size):
        """Create the size preview object"""
        # Remove old preview if it exists
        if self._preview_object and self._preview_object.name in bpy.data.objects:
            bpy.data.objects.remove(self._preview_object, do_unlink=True)
        
        # Create new preview at center with base size
        primitive_name = self.get_current_primitive_name()
        self._preview_object = self.create_primitive(context, primitive_name, center, center, is_preview=True)
        
        if self._preview_object:
            # Apply size scaling
            self._preview_object.scale = (size, size, size)
            self._preview_object.location = center
            
            # Apply selection material for visibility
            self.apply_selection_material(self._preview_object)
            print(f"✅ Size preview created: {primitive_name} at {center} with size {size:.2f}")
    
    def confirm_size_phase(self, context):
        """Confirm Phase 1 and transition to Phase 2: Position"""
        print(f"✅ CREATE Phase 1 CONFIRMED: Size = {self._create_size_confirmed:.2f}")
        print("🎯 CREATE Phase 2: POSITION started - use right hand thumb+index to position")
        
        self._create_phase = "POSITION"
        self._both_hands_active = False
        self._is_creating = True  # Keep for compatibility with existing logic
    
    def start_position_phase(self, context, thumb_pos, index_pos):
        """Handle Phase 2: Position control with right hand"""
        if self._preview_object and self._preview_object.name in bpy.data.objects:
            # Update position based on right hand
            new_center = (thumb_pos + index_pos) / 2
            self._preview_object.location = new_center
            print(f"🎯 Position updated: {new_center}")
        else:
            print("⚠️ No preview object for positioning")
    
    def create_bezier_curve_from_path(self, context, path_points):
        """Create a smooth bezier curve from a list of 3D points, simplified to exactly 4 control points"""
        if len(path_points) < 2:
            print(f"❌ Not enough path points: {len(path_points)}")
            return None
            
        try:
            # SIMPLIFY TO 4 CONTROL POINTS with smooth interpolation
            simplified_points = self.simplify_path_to_4_points(path_points)
            print(f"🔧 Creating smooth curve: {len(path_points)} points → 4 control points")
            
            # Create new curve data (minimal settings - DRAWbrush will handle geometry)
            curve_data = bpy.data.curves.new(name="DrawCurve", type='CURVE')
            curve_data.dimensions = '3D'
            
            # Keep basic curve properties for DRAWbrush compatibility
            try:
                curve_data.twist_method = 'MINIMUM'
            except AttributeError:
                pass
            
            try:
                curve_data.twist_smooth = 0.0
            except AttributeError:
                pass
            
            # No manual extrude/bevel - DRAWbrush GeometryNode will handle this
            print("✅ Curve data created with properties")
            
            # Create spline with exactly 4 bezier points
            spline = curve_data.splines.new(type='BEZIER')
            spline.bezier_points.add(3)  # Add 3 more points (spline starts with 1) = 4 total
            print(f"✅ Spline created with 4 bezier control points")
            
            # Set the 4 simplified bezier points with smooth handles
            for i, point in enumerate(simplified_points):
                bp = spline.bezier_points[i]
                bp.co = point
                bp.handle_left_type = 'AUTO'
                bp.handle_right_type = 'AUTO'
                print(f"  Control Point {i+1}/4: {point}")
            print("✅ All 4 bezier control points set with smooth auto handles")
            
            # Create curve object
            curve_obj = bpy.data.objects.new("DrawCurve", curve_data)
            context.collection.objects.link(curve_obj)
            print(f"✅ Smooth curve object '{curve_obj.name}' created and linked to scene")
            
            # Make sure the curve is visible and selected
            curve_obj.hide_viewport = False
            curve_obj.hide_render = False
            curve_obj.select_set(True)
            context.view_layer.objects.active = curve_obj
            
            # Debug curve properties
            print(f"✅ Curve object made visible and selected")
            print(f"📏 Curve location: {curve_obj.location}")
            print(f"📏 Curve scale: {curve_obj.scale}")
            print(f"📏 Curve rotation: {curve_obj.rotation_euler}")
            print(f"📏 Curve dimensions: {curve_obj.dimensions}")
            
            # Calculate bounding box
            bbox = curve_obj.bound_box
            bbox_size = max(bbox[6][0] - bbox[0][0], bbox[6][1] - bbox[0][1], bbox[6][2] - bbox[0][2])
            print(f"📏 Curve bounding box size: {bbox_size}")
            
            # Apply selection material
            self.apply_selection_material(curve_obj)
            print("✅ Selection material applied")
            
            print(f"✅ Created bezier curve with {len(path_points)} points")
            return curve_obj
            
        except Exception as e:
            print(f"❌ Error creating curve: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def apply_selection_material(self, obj):
        """Apply or create selection material for draw objects"""
        try:
            selection_mat = bpy.data.materials.get("selected_material")
            
            if not selection_mat:
                print("⚠️ Warning: 'selected_material' not found in scene, creating fallback material")
                # Create fallback material if selected_material doesn't exist
                selection_mat = bpy.data.materials.new(name="selected_material")
                selection_mat.use_nodes = True
                nodes = selection_mat.node_tree.nodes
                nodes.clear()
                
                # Create a bright highlighting material
                bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
                bsdf.inputs['Base Color'].default_value = (1.0, 0.3, 0.0, 1.0)  # Orange highlight
                bsdf.inputs['Emission'].default_value = (1.0, 0.3, 0.0, 1.0)
                bsdf.inputs['Emission Strength'].default_value = 0.5
                
                output = nodes.new(type='ShaderNodeOutputMaterial')
                selection_mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
                print("✅ Selection material created")
            else:
                print("✅ Using existing selection material")
            
            # Apply material
            if obj.data.materials:
                obj.data.materials[0] = selection_mat
                print(f"✅ Applied material to existing slot on {obj.name}")
            else:
                obj.data.materials.append(selection_mat)
                print(f"✅ Added new material slot to {obj.name}")
                
        except Exception as e:
            print(f"❌ Error applying selection material: {e}")
            import traceback
            traceback.print_exc()
    
    def apply_drawbrush_geometry_node(self, curve_obj):
        """Apply DRAWbrush GeometryNode modifier to curve and then remesh"""
        if not curve_obj or curve_obj.type != 'CURVE':
            print(f"❌ Cannot apply DRAWbrush: invalid curve object (type: {curve_obj.type if curve_obj else 'None'})")
            return None
            
        try:
            print(f"🎨 Applying DRAWbrush GeometryNode to curve '{curve_obj.name}'...")
            
            # Check if DRAWbrush node group exists in the scene
            if "DRAWbrush" not in bpy.data.node_groups:
                print("❌ DRAWbrush node group not found in scene! Please ensure it's properly loaded.")
                return None
            
            # Add GeometryNodes modifier
            print("🔧 Adding GeometryNodes modifier...")
            geometry_mod = curve_obj.modifiers.new(name="DRAWbrush", type='NODES')
            geometry_mod.node_group = bpy.data.node_groups["DRAWbrush"]
            print("✅ DRAWbrush GeometryNode modifier added")
            
            # Convert to mesh to be able to apply remesh
            print("🔧 Converting curve to mesh...")
            bpy.context.view_layer.objects.active = curve_obj
            bpy.ops.object.convert(target='MESH')
            print(f"✅ Curve converted to mesh (now type: {curve_obj.type})")
            
            # Add remesh modifier (only this modifier, as requested)
            print("🔧 Adding remesh modifier...")
            remesh_mod = curve_obj.modifiers.new(name="Remesh", type='REMESH')
            remesh_mod.mode = 'SMOOTH'
            remesh_mod.octree_depth = 7  # Reduced from 8 to 6 for DRAW brush
            remesh_mod.scale = 0.9
            remesh_mod.use_remove_disconnected = False
            remesh_mod.threshold = 1.0
            print("✅ Remesh modifier added")
            
            # Apply the remesh modifier
            print("🔧 Applying remesh modifier...")
            bpy.context.view_layer.objects.active = curve_obj
            bpy.ops.object.modifier_apply(modifier="Remesh")
            print("✅ Remesh modifier applied")
            
            # Make sure it's visible and selected
            curve_obj.hide_viewport = False
            curve_obj.hide_render = False
            curve_obj.select_set(True)
            
            print(f"✅ Applied DRAWbrush GeometryNode and remesh to: {curve_obj.name}")
            return curve_obj
            
        except Exception as e:
            print(f"❌ Error applying DRAWbrush GeometryNode: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    
    def batch_remesh_and_boolean(self, context, operation='UNION'):
        """
        EXTREMELY SIMPLE: Join all stripes → Remesh 7 → Boolean Union
        """
        if not self._pending_draw_objects:
            print("⚠️ No pending draw objects to process")
            return
            
        print(f"🔧 SIMPLE: Processing {len(self._pending_draw_objects)} stripes - join → remesh 7 → union")
        
        mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
        if not mesh_obj:
            print("❌ Main mesh object not found!")
            return
        
        try:
            # Step 1: Join all stripes into one object
            if len(self._pending_draw_objects) == 1:
                combined_obj = self._pending_draw_objects[0]
                print(f"✅ Single stripe - using {combined_obj.name}")
            else:
                print(f"🔧 Joining {len(self._pending_draw_objects)} stripes...")
                
                # Select all draw objects
                bpy.ops.object.select_all(action='DESELECT')
                for obj in self._pending_draw_objects:
                    obj.select_set(True)
                
                # Make first object active
                bpy.context.view_layer.objects.active = self._pending_draw_objects[0]
                
                # Join all selected objects
                bpy.ops.object.join()
                combined_obj = bpy.context.active_object
                print(f"   ✅ All stripes joined into {combined_obj.name}")
            
            # Step 2: Remesh with octree depth 7
            print(f"🔧 Applying remesh (octree depth 7)...")
            remesh_mod = combined_obj.modifiers.new(name="Remesh", type='REMESH')
            remesh_mod.mode = 'SMOOTH'
            remesh_mod.octree_depth = 7
            remesh_mod.scale = 0.99
            
            bpy.context.view_layer.objects.active = combined_obj
            bpy.ops.object.modifier_apply(modifier="Remesh")
            print(f"   ✅ Remesh applied")
            
            # Step 3: Boolean union with main mesh
            print(f"🔧 Boolean union with main mesh...")
            bool_mod = mesh_obj.modifiers.new(name="Union", type='BOOLEAN')
            bool_mod.operation = 'UNION'
            bool_mod.object = combined_obj
            
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.modifier_apply(modifier="Union")
            print(f"   ✅ Boolean union applied")
            
            # Step 4: Clean up - remove the combined object
            bpy.data.objects.remove(combined_obj, do_unlink=True)
            print(f"   ✅ Temporary object removed")
            
        except Exception as e:
            print(f"❌ Error in simple workflow: {e}")
            import traceback
            traceback.print_exc()
        
        # Clear pending objects list
        self._pending_draw_objects.clear()
        print(f"✅ SIMPLE COMPLETE: All stripes joined → remeshed → added to mesh")
    
    def apply_boolean_operation(self, context, draw_obj, operation='UNION'):
        """Apply boolean operation between draw object and main mesh"""
        mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
        if not mesh_obj or not draw_obj:
            print(f"⚠️ Cannot apply boolean: mesh_obj={mesh_obj}, draw_obj={draw_obj}")
            return
            
        # Apply DRAWbrush GeometryNode if it's still a curve
        if draw_obj.type == 'CURVE':
            draw_obj = self.apply_drawbrush_geometry_node(draw_obj)
            if not draw_obj:
                print("❌ Failed to apply DRAWbrush GeometryNode for boolean operation")
                return
        
        # Apply boolean modifier to main mesh
        bool_mod = mesh_obj.modifiers.new(name=f"Boolean_{operation}", type='BOOLEAN')
        bool_mod.operation = operation
        bool_mod.object = draw_obj
        
        # Apply the modifier
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        
        # Remove the draw object
        bpy.data.objects.remove(draw_obj, do_unlink=True)
        
        operation_text = "ADDED TO" if operation == 'UNION' else "SUBTRACTED FROM"
        print(f"✅ Draw object {operation_text} main mesh")

    # === CREATE FUNCTIONALITY METHODS ===
    
    def cycle_primitive(self):
        """Cycle to the next primitive type"""
        self._current_primitive_index = (self._current_primitive_index + 1) % len(config.PRIMITIVE_TYPES)
        current_primitive = config.PRIMITIVE_TYPES[self._current_primitive_index]
        print(f"🎯 Switched to primitive: {current_primitive}")
        return current_primitive
    
    def get_current_primitive_name(self):
        """Get the name of the currently selected primitive"""
        return config.PRIMITIVE_TYPES[self._current_primitive_index]
    
    def start_creating(self, context, thumb_pos, index_pos):
        """Start creating a new primitive with real-time preview"""
        self._is_creating = True
        self._create_thumb_pos = thumb_pos.copy()
        self._create_index_pos = index_pos.copy()
        
        # Create preview object
        self.update_primitive_preview(context, thumb_pos, index_pos)
        print(f"🏗️ Started creating {self.get_current_primitive_name()}")
    
    def update_primitive_preview(self, context, thumb_pos, index_pos):
        """Update the primitive preview based on thumb and index positions"""
        if not self._is_creating:
            return
            
        # Store current positions
        self._create_thumb_pos = thumb_pos.copy()
        self._create_index_pos = index_pos.copy()
        
        # Remove old preview if it exists
        if self._preview_object and self._preview_object.name in bpy.data.objects:
            bpy.data.objects.remove(self._preview_object, do_unlink=True)
        
        # Create new preview
        primitive_name = self.get_current_primitive_name()
        self._preview_object = self.create_primitive(context, primitive_name, thumb_pos, index_pos, is_preview=True)
        
        if self._preview_object:
            # Make preview semi-transparent and use selection material
            self.apply_selection_material(self._preview_object)
            # Make it slightly transparent for preview effect
            if hasattr(self._preview_object, 'color'):
                self._preview_object.color = (1.0, 0.8, 0.0, 0.7)  # Yellow with transparency
    
    def confirm_primitive_placement(self, context):
        """Confirm the current primitive placement and add to pending objects"""
        print(f"🔍 CONFIRM DEBUG: confirm_primitive_placement() called - _is_creating={self._is_creating}, _preview_object={self._preview_object is not None}")
        
        if not self._is_creating or not self._preview_object:
            print("⚠️ No primitive to confirm")
            return None
            
        # Convert preview to final object
        primitive_obj = self._preview_object
        primitive_obj.name = f"Create{self.get_current_primitive_name()}"
        
        # Apply selection material (remove transparency)
        self.apply_selection_material(primitive_obj)
        
        # Add to pending objects
        self._pending_create_objects.append(primitive_obj)
        print(f"🏗️ Confirmed {self.get_current_primitive_name()}: {primitive_obj.name}")
        print(f"📝 Added to pending objects ({len(self._pending_create_objects)} total)")
        
        # Reset creation state
        self._is_creating = False
        self._preview_object = None
        self._create_thumb_pos = None
        self._create_index_pos = None
        
        print(f"🔍 CONFIRM DEBUG: State reset - _is_creating={self._is_creating}, _preview_object={self._preview_object}")
        
        return primitive_obj
    
    def create_primitive(self, context, primitive_name, thumb_pos, index_pos, is_preview=False):
        """Create a specific primitive based on thumb and index finger positions"""
        
        # Calculate center, size, and rotation from finger positions
        center = (thumb_pos + index_pos) / 2
        size_vector = index_pos - thumb_pos
        size = size_vector.length
        
        # Ensure minimum size
        if size < 0.1:
            size = 0.1
            
        print(f"🏗️ Creating {primitive_name} at {center} with size {size:.3f}")
        
        # Clear selection and set 3D cursor to center
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.scene.cursor.location = center
        
        try:
            if primitive_name == 'CUBE':
                bpy.ops.mesh.primitive_cube_add(size=size, location=center)
                
            elif primitive_name == 'SPHERE':
                bpy.ops.mesh.primitive_ico_sphere_add(radius=size/2, subdivisions=5, location=center)
                
            elif primitive_name == 'CYLINDER':
                bpy.ops.mesh.primitive_cylinder_add(radius=size/2, depth=size, vertices=128, location=center)
                
            elif primitive_name == 'CONE':
                bpy.ops.mesh.primitive_cone_add(radius1=size/2, depth=size, vertices=128, location=center)
                
            elif primitive_name == 'TORUS':
                bpy.ops.mesh.primitive_torus_add(major_radius=size/2, minor_radius=size/4, location=center)
                
            else:
                print(f"❌ Unknown primitive type: {primitive_name}")
                return None
            
            # Get the created object
            primitive_obj = bpy.context.active_object
            if is_preview:
                primitive_obj.name = f"Preview{primitive_name}"
            else:
                primitive_obj.name = f"Create{primitive_name}"
            
            # Apply rotation based on finger direction
            self.apply_primitive_rotation(primitive_obj, thumb_pos, index_pos)
            
            print(f"✅ Created {primitive_name}: {primitive_obj.name}")
            return primitive_obj
            
        except Exception as e:
            print(f"❌ Failed to create {primitive_name}: {e}")
            return None
    
    def apply_primitive_rotation(self, obj, thumb_pos, index_pos):
        """Apply rotation to primitive based on gestureCamera orientation (not finger direction)"""
        import mathutils
        
        # Get the gestureCamera for orientation reference
        gesture_camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
        
        if gesture_camera:
            # Use gestureCamera's rotation directly
            obj.rotation_euler = gesture_camera.rotation_euler.copy()
            print(f"🔄 Applied gestureCamera rotation to {obj.name}: {obj.rotation_euler}")
        else:
            # Fallback: no rotation (keep default orientation)
            obj.rotation_euler = (0, 0, 0)
            print(f"⚠️ gestureCamera not found, using default rotation for {obj.name}")
    
    def apply_create_remesh(self, obj):
        """Apply remesh modifier with smooth, octree depth 7 to CREATE primitives."""
        try:
            # Add remesh modifier
            remesh_modifier = obj.modifiers.new(name="Remesh", type='REMESH')
            remesh_modifier.mode = 'SMOOTH'
            remesh_modifier.octree_depth = 6
            remesh_modifier.scale = 0.99
            remesh_modifier.remove_disconnected = False
            remesh_modifier.threshold = 1.0
            
            print(f"🔧 Added remesh modifier: mode=SMOOTH, octree_depth=7, scale=0.99")
            
            # Apply the modifier
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier="Remesh")
            
            print(f"✅ Remesh applied successfully to {obj.name}")
            
        except Exception as e:
            print(f"❌ Error applying remesh to {obj.name}: {e}")
    
    def batch_remesh_and_boolean_create(self, context, operation='UNION'):
        """Apply boolean operations to all pending create objects"""
        if not self._pending_create_objects:
            print("⚠️ No pending create objects for boolean operation")
            return
            
        print(f"🔧 Starting batch processing of {len(self._pending_create_objects)} objects for {operation}...")
        
        processed_objects = []
        for i, create_obj in enumerate(self._pending_create_objects):
            # Store object name BEFORE applying boolean operation (object gets deleted)
            obj_name = create_obj.name
            print(f"🔧 Processing object {i+1}/{len(self._pending_create_objects)}: {obj_name}")
            
            # Apply boolean operation (this will delete the object)
            self.apply_boolean_operation_create(context, create_obj, operation)
            processed_objects.append(obj_name)  # Use stored name, not create_obj.name
        
        # Clear pending objects
        self._pending_create_objects.clear()
        
        operation_text = "ADDED TO" if operation == 'UNION' else "SUBTRACTED FROM"
        print(f"✅ Batch complete: {len(processed_objects)} objects {operation_text} main mesh")
        print(f"   Processed: {', '.join(processed_objects)}")
    
    def apply_boolean_operation_create(self, context, create_obj, operation='UNION'):
        """Apply boolean operation between create object and main mesh"""
        mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
        if not mesh_obj or not create_obj:
            print(f"⚠️ Cannot apply boolean: mesh_obj={mesh_obj}, create_obj={create_obj}")
            return
        
        # Apply boolean modifier to main mesh
        bool_mod = mesh_obj.modifiers.new(name=f"Boolean_{operation}", type='BOOLEAN')
        bool_mod.operation = operation
        bool_mod.object = create_obj
        
        # Apply the modifier
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        
        # Remove the create object
        bpy.data.objects.remove(create_obj, do_unlink=True)
        
        operation_text = "ADDED TO" if operation == 'UNION' else "SUBTRACTED FROM"
        print(f"✅ Boolean {operation} applied")

    def modal(self, context, event):
        # The UI panel can set this property to signal the operator to stop
        if context.window_manager.conjure_should_stop:
            context.window_manager.conjure_should_stop = False # Reset the flag
            context.window_manager.conjure_is_running = False
            self.cancel(context)
            print("Conjure Fingertip Operator has been cancelled.")
            return {'CANCELLED'}

        # --- Handle Mouse & Keyboard Input ---
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE', 'RIGHTMOUSE'}:
            # Allow standard navigation controls to pass through
            return {'PASS_THROUGH'}

        # --- Handle Operator Logic only on Timer Events ---
        if event.type == 'TIMER':
            # === Left hand boolean operations handled directly by gestures ===
            
            # Check for commands from the launcher (e.g., spawn primitive)
            self.check_for_launcher_requests()
            self.check_for_state_commands(context) # Check for new state-based commands

            # --- Robustly find the 3D view context, regardless of mouse position ---
            area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)
            if not area:
                return {'PASS_THROUGH'} # No 3D view available, do nothing

            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if not region:
                return {'PASS_THROUGH'} # No window region in the 3D view

            space_data = area.spaces.active
            rv3d = space_data.region_3d if space_data else None
            if not rv3d:
                return {'PASS_THROUGH'} # No 3D region data

            depsgraph = context.evaluated_depsgraph_get()

            live_data = {}
            if os.path.exists(config.FINGERTIPS_JSON_PATH):
                with open(config.FINGERTIPS_JSON_PATH, "r") as f:
                    try:
                        live_data = json.load(f)
                    except json.JSONDecodeError:
                        live_data = {} # Keep going with empty data

            command = live_data.get("command", "none")
            mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
            
            # DEBUG: Track all commands for CREATE brush (reduced frequency)
            active_brush = config.BRUSH_TYPES[self._current_brush_index]
            if active_brush == "CREATE" and command != "none":  # Only log non-none commands to reduce spam
                print(f"🔍 COMMAND DEBUG: command={command}, _last_command={getattr(self, '_last_command', 'None')}, _is_creating={self._is_creating}")
            
            # Debug current command every few frames to avoid spam
            if not hasattr(self, '_command_debug_counter'):
                self._command_debug_counter = 0
            self._command_debug_counter += 1
            
            if self._command_debug_counter % 60 == 0:  # Every 60 frames (~2 seconds)
                pass  # Removed debug logging for cleaner console output

            # --- Process Fingertips for Visualization ---
            right_hand_data = live_data.get("right_hand")
            left_hand_data = live_data.get("left_hand")
            
            # Create a combined list of all 10 possible finger datas (None if not present)
            all_finger_datas = (left_hand_data["fingertips"] if left_hand_data else [None]*5) + \
                               (right_hand_data["fingertips"] if right_hand_data else [None]*5)

            finger_positions_3d = [] # This will store the final, snapped positions for deformation

            for i, tip in enumerate(all_finger_datas):
                marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
                if not marker_obj:
                    continue

                if tip:
                    # --- FINGER IS PRESENT ---
                    self.marker_states[i]['missing_frames'] = 0
                    marker_obj.hide_viewport = False

                    raw_pos_3d = map_hand_to_3d_space(tip['x'], tip['y'], tip['z'])
                    
                    # Default positions, in case no snapping occurs
                    deformation_pos = raw_pos_3d
                    visual_marker_pos = raw_pos_3d

                    # --- SURFACE SNAPPING LOGIC ---
                    if region and rv3d and mesh_obj:
                        pos_2d = location_3d_to_region_2d(region, rv3d, raw_pos_3d)
                        if pos_2d:
                            ray_origin = region_2d_to_origin_3d(region, rv3d, pos_2d)
                            ray_direction = region_2d_to_vector_3d(region, rv3d, pos_2d)
                            hit, loc, normal, _, hit_obj, _ = context.scene.ray_cast(depsgraph, ray_origin, ray_direction)
                            
                            if hit and hit_obj == mesh_obj:
                                # DEFORMATION happens at the exact hit location.
                                deformation_pos = loc

                                # VISUAL MARKER is offset toward camera to ensure visibility
                                gesture_camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
                                if gesture_camera:
                                    # Direction FROM surface TO camera
                                    to_camera_dir = (gesture_camera.location - loc).normalized()
                                    # Move fingertip toward camera by offsetting in that direction
                                    visual_marker_pos = loc + (to_camera_dir * config.MARKER_SURFACE_OFFSET)
                                else:
                                    # Fallback: offset along surface normal
                                    visual_marker_pos = loc + (normal * config.MARKER_SURFACE_OFFSET)
                                
                                # Update state tracking
                                self.marker_states[i]['was_hitting_surface'] = True
                                self.marker_states[i]['last_hit_normal'] = normal.copy()
                            else:
                                # Smooth transition when raycast fails
                                if self.marker_states[i]['was_hitting_surface']:
                                    # Use last known surface normal for brief continuation
                                    last_normal = self.marker_states[i]['last_hit_normal']
                                    # Gradually transition back to raw position
                                    surface_fallback = self.marker_states[i]['last_pos'] + (last_normal * config.MARKER_SURFACE_OFFSET * 0.5)
                                    visual_marker_pos = surface_fallback.lerp(raw_pos_3d, 0.3)
                                
                                self.marker_states[i]['was_hitting_surface'] = False
                    
                    # The deformation list gets the precise, non-offset position.
                    finger_positions_3d.append(deformation_pos)

                    # Advanced smoothing with velocity-based filtering
                    last_pos = self.marker_states[i]['last_pos']
                    last_velocity = self.marker_states[i]['last_velocity']
                    
                    # Calculate raw velocity
                    raw_velocity = visual_marker_pos - last_pos
                    
                    # Apply velocity smoothing to prevent sudden direction changes
                    smoothed_velocity = last_velocity.lerp(raw_velocity, config.VELOCITY_SMOOTHING_FACTOR)
                    
                    # Choose smoothing factor based on surface interaction
                    if self.marker_states[i]['was_hitting_surface']:
                        # Extra smooth when hovering over mesh surface
                        smoothing_factor = config.HOVER_SMOOTHING_FACTOR
                    else:
                        # Normal smoothing in free space
                        smoothing_factor = config.SMOOTHING_FACTOR
                    
                    # Apply position smoothing
                    smoothed_pos = last_pos.lerp(visual_marker_pos, smoothing_factor)
                    
                    # Update marker position and state
                    marker_obj.location = smoothed_pos
                    self.marker_states[i]['last_pos'] = smoothed_pos
                    self.marker_states[i]['last_velocity'] = smoothed_velocity
                    
                    # Force fingertip to always render in front (multiple approaches)
                    marker_obj.show_in_front = True
                    
                    # Alternative: Try display_type as wireframe/solid overlay
                    if hasattr(marker_obj, 'display_type'):
                        marker_obj.display_type = 'SOLID'  # Try SOLID for better visibility
                    
                    # Alternative: Force viewport visibility
                    marker_obj.hide_viewport = False
                    marker_obj.hide_render = False
                    
                    # Marker visibility configured properly
                
                else:
                    # --- FINGER IS MISSING ---
                    finger_positions_3d.append(None) # Add a placeholder for indexing
                    self.marker_states[i]['missing_frames'] += 1
                    if self.marker_states[i]['missing_frames'] > config.HIDE_GRACE_PERIOD_FRAMES:
                        marker_obj.hide_viewport = True

            # --- Execute Commands ---
            if not mesh_obj:
                print(f"'{config.DEFORM_OBJ_NAME}' not found. Cannot execute commands.")
                return {'PASS_THROUGH'}

            # --- Calculate hand movement vector for GRAB brush ---
            current_hand_center = None
            hand_move_vector = None
            if right_hand_data and "fingertips" in right_hand_data and len(right_hand_data["fingertips"]) >= 2:
                thumb_tip = right_hand_data["fingertips"][0]
                index_tip = right_hand_data["fingertips"][1]
                # We use the raw positions for calculating the grab vector to avoid snapping influencing it
                thumb_pos = map_hand_to_3d_space(thumb_tip['x'], thumb_tip['y'], thumb_tip['z'])
                index_pos = map_hand_to_3d_space(index_tip['x'], index_tip['y'], index_tip['z'])
                current_hand_center = (thumb_pos + index_pos) / 2.0
                if self._last_hand_center:
                    hand_move_vector = current_hand_center - self._last_hand_center
            
            # Update last hand center for the next frame
            self._last_hand_center = current_hand_center

            # OLD STICKY MODE DISABLED - Two-phase CREATE system handles state management explicitly
            # active_brush = config.BRUSH_TYPES[self._current_brush_index]
            # (Old sticky mode logic removed for cleaner two-phase workflow)
            
            # Handle orbit first (works in any mode including selection)
            if command == "orbit":
                camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
                orbit_delta = live_data.get("orbit_delta", {"x": 0.0, "y": 0.0})

                if camera and orbit_delta:
                    # Apply smoothing to the raw delta values
                    raw_delta_x = orbit_delta.get("x", 0.0)
                    raw_delta_y = orbit_delta.get("y", 0.0)
                    
                    self._last_orbit_delta['x'] = self._last_orbit_delta['x'] * (1 - config.ORBIT_SMOOTHING_FACTOR) + raw_delta_x * config.ORBIT_SMOOTHING_FACTOR
                    self._last_orbit_delta['y'] = self._last_orbit_delta['y'] * (1 - config.ORBIT_SMOOTHING_FACTOR) + raw_delta_y * config.ORBIT_SMOOTHING_FACTOR

                    smoothed_delta_x = self._last_orbit_delta['x']
                    smoothed_delta_y = self._last_orbit_delta['y']

                    if abs(smoothed_delta_x) > 0.0001 or abs(smoothed_delta_y) > 0.0001:
                        # Horizontal movement orbits around the world Z-axis
                        angle_z = -smoothed_delta_x * math.radians(config.ORBIT_SENSITIVITY)
                        rot_z = mathutils.Matrix.Rotation(angle_z, 4, 'Z')

                        # Vertical movement orbits around the camera's local X-axis
                        angle_x = -smoothed_delta_y * math.radians(config.ORBIT_SENSITIVITY)
                        local_x_axis = camera.matrix_world.to_3x3().col[0]
                        rot_x = mathutils.Matrix.Rotation(angle_x, 4, local_x_axis)

                        # Apply rotation to the camera's location vector
                        new_location = rot_z @ rot_x @ camera.location

                        # Re-point the camera to the origin (0,0,0) after moving
                        direction = -new_location
                        rot_quat = direction.to_track_quat('-Z', 'Y')

                        camera.location = new_location
                        camera.rotation_euler = rot_quat.to_euler()

            # Check if we're in segment selection mode from state.json 
            try:
                with open(config.STATE_JSON_PATH, 'r') as f:
                    state_data = json.load(f)
                selection_mode = state_data.get("selection_mode", "inactive")
                state_command = state_data.get("command")
            except:
                selection_mode = "inactive"
                state_command = None
            
            # === DRAW STATE MANAGEMENT (Independent of command) ===
            # Check if we're currently drawing and handle finger release detection
            active_brush = config.BRUSH_TYPES[self._current_brush_index]
            if active_brush == "DRAW" and self._is_drawing:
                # Check if fingers are still present in the data (use same logic as main detection)
                # Left hand: indices 0 (thumb) and 1 (index)
                # Right hand: indices 5 (thumb) and 6 (index)
                has_left_thumb_index = (len(finger_positions_3d) > 1 and 
                                      finger_positions_3d[0] is not None and 
                                      finger_positions_3d[1] is not None)
                has_right_thumb_index = (len(finger_positions_3d) > 6 and 
                                       finger_positions_3d[5] is not None and 
                                       finger_positions_3d[6] is not None)
                fingers_present = has_left_thumb_index or has_right_thumb_index
                
                print(f"🔍 DRAW RELEASE DEBUG: fingers_present={fingers_present}, command={command}, left={has_left_thumb_index}, right={has_right_thumb_index}")

                if not fingers_present or command != "deform":
                    # Start or continue the release timer
                    if self._draw_release_timer == 0.0:
                        self._draw_release_timer = time.time()
                        print("⏱️ DRAW: Starting release confirmation timer...")
                    
                    # Check if we've been without fingers for long enough (300ms for noise immunity)
                    elapsed_time = time.time() - self._draw_release_timer
                    if elapsed_time > self._draw_release_threshold:
                        # Fingers released for long enough - finish drawing
                        print(f"🖐️ DRAW: Confirmed finger release after {elapsed_time:.2f}s - finishing drawing...")
                        curve_obj = self.finish_drawing(context)
                        if curve_obj:
                            print("🎨 Drawing finished - use quick index+thumb clicks to add/subtract from mesh")
                        self._draw_release_timer = 0.0  # Reset timer
                    else:
                        # Still waiting for confirmation
                        remaining = self._draw_release_threshold - elapsed_time
                        if remaining > 0.1:  # Only print if more than 100ms remaining
                            print(f"⏳ DRAW: Waiting {remaining:.2f}s more to confirm release...")
                else:
                    # Fingers are present again - reset release timer
                    if self._draw_release_timer > 0.0:
                        print("✋ DRAW: Fingers detected again - canceling release timer")
                    self._draw_release_timer = 0.0
            
            if selection_mode == "active" or state_command == "segment_selection":
                # print("🎯 DEBUG: segment_selection mode ACTIVE - calling handler")
                try:
                    self.handle_segment_selection(context, finger_positions_3d, region, rv3d, depsgraph)
                except (ReferenceError, AttributeError) as e:
                    print(f"⚠️ Segment selection handler error (operator removed): {e}")
                except Exception as e:
                    print(f"⚠️ Unexpected error in segment selection handler: {e}")
            elif command == "deform":
                # Store finger positions for CREATE sticky mode (when data is available)
                if len(finger_positions_3d) >= 7:
                    self._last_finger_positions = finger_positions_3d.copy()
                
                # Check if we have valid thumb and index finger positions 
                # Left hand: indices 0 (thumb) and 1 (index)
                # Right hand: indices 5 (thumb) and 6 (index)
                has_left_thumb_index = (len(finger_positions_3d) > 1 and 
                                      finger_positions_3d[0] is not None and 
                                      finger_positions_3d[1] is not None)
                has_right_thumb_index = (len(finger_positions_3d) > 6 and 
                                       finger_positions_3d[5] is not None and 
                                       finger_positions_3d[6] is not None)
                has_thumb_index = has_left_thumb_index or has_right_thumb_index
                
                active_brush = config.BRUSH_TYPES[self._current_brush_index]
                
                # DEBUG: CREATE brush state tracking (only when state changes)
                if active_brush == "CREATE" and hasattr(self, '_last_has_thumb_index'):
                    if has_thumb_index != self._last_has_thumb_index:
                        print(f"🔍 CREATE DEBUG: finger detection changed - has_thumb_index={has_thumb_index}, _is_creating={self._is_creating}")
                elif active_brush == "CREATE":
                    print(f"🔍 CREATE DEBUG: Initial state - has_thumb_index={has_thumb_index}, _is_creating={self._is_creating}")
                
                # Store for next comparison
                if active_brush == "CREATE":
                    self._last_has_thumb_index = has_thumb_index
                
                if has_thumb_index:
                    # FINGERS DETECTED - Determine which hand is active and get correct finger positions
                    if has_right_thumb_index:
                        # Use right hand fingers
                        thumb_pos = finger_positions_3d[5]
                        index_pos = finger_positions_3d[6]
                        hand_side = "RIGHT"
                    else:
                        # Use left hand fingers
                        thumb_pos = finger_positions_3d[0]
                        index_pos = finger_positions_3d[1]
                        hand_side = "LEFT"
                    
                    deform_points = [thumb_pos, index_pos]
                    
                    if active_brush == "DRAW":
                        # DRAW FUNCTIONALITY: Handle drawing with index+thumb from either hand
                        # Calculate midpoint between thumb and index for draw position
                        draw_position = (thumb_pos + index_pos) / 2
                        print(f"🎨 DRAW ({hand_side}): thumb={thumb_pos}, index={index_pos}, midpoint={draw_position}")
                        
                        # DRAW LOGIC: Always prioritize drawing over clicking
                        if not self._is_drawing:
                            # Start drawing (always start drawing, don't worry about clicks here)
                            print("🎨 Starting new drawing stroke...")
                            self.start_drawing(context, draw_position)
                        else:
                            # Continue drawing - add point to path
                            self.add_draw_point(context, draw_position)
                    
                    elif active_brush == "CREATE":
                        # TWO-PHASE CREATE FUNCTIONALITY
                        both_hands, left_thumb, left_index, right_thumb, right_index = self.detect_both_hands_active(finger_positions_3d)
                        
                        if self._create_phase == "NONE":
                            # Not in any phase - check for both hands to start Phase 1
                            if both_hands:
                                print("🎯 Both hands detected - starting Phase 1: SIZE")
                                self.start_size_phase(context, left_thumb, left_index, right_thumb, right_index)
                            else:
                                # Reduce debug spam
                                if not hasattr(self, '_waiting_debug_counter'):
                                    self._waiting_debug_counter = 0
                                self._waiting_debug_counter += 1
                                if self._waiting_debug_counter % 30 == 0:  # Every ~1 second
                                    print("🔍 CREATE: Waiting for both hands (thumb+index) to start sizing...")
                                
                        elif self._create_phase == "SIZE":
                            # Phase 1: Size definition with both hands
                            if both_hands:
                                # Continue size adjustment
                                self.update_size_phase(context, left_thumb, left_index, right_thumb, right_index)
                            else:
                                # Both hands released - confirm size and move to Phase 2
                                print("🎯 Both hands released - confirming size and starting position phase")
                                print(f"🔍 TRANSITION DEBUG: Before transition - _create_phase={self._create_phase}")
                                self.confirm_size_phase(context)
                                print(f"🔍 TRANSITION DEBUG: After transition - _create_phase={self._create_phase}, _is_creating={self._is_creating}")
                                
                        elif self._create_phase == "POSITION":
                            # Phase 2: Position control with right hand only
                            right_hand_active = (len(finger_positions_3d) > 6 and 
                                               finger_positions_3d[5] is not None and 
                                               finger_positions_3d[6] is not None)
                            
                            if right_hand_active:
                                thumb_pos = finger_positions_3d[5]
                                index_pos = finger_positions_3d[6]
                                print(f"🎯 POSITION: thumb={thumb_pos}, index={index_pos}")
                                self.start_position_phase(context, thumb_pos, index_pos)
                            else:
                                # Reduce debug spam for position phase
                                if not hasattr(self, '_position_debug_counter'):
                                    self._position_debug_counter = 0
                                self._position_debug_counter += 1
                                if self._position_debug_counter % 30 == 0:  # Every ~1 second
                                    print("🎯 POSITION: Use right hand thumb+index to position primitive")
                                    print(f"🎯 POSITION DEBUG: Ready for left ring+thumb to confirm placement")
                     
                    else:
                        # OTHER BRUSHES: Standard deformation
                        if not mesh_obj or not mesh_obj.data or not hasattr(mesh_obj.data, 'vertices'):
                            print(f"⚠️ Cannot deform: invalid mesh object (mesh_obj={mesh_obj})")
                            return {'PASS_THROUGH'}
                        
                        if config.USE_VELOCITY_FORCES:
                            deform_mesh_with_viscosity(mesh_obj, deform_points, self._initial_volume, self._vertex_velocities, self._history_buffer, self, active_brush, hand_move_vector)
                        else:
                            deform_mesh(mesh_obj, deform_points, self._initial_volume)
                            
                else:
                    # NO FINGERS DETECTED - Handle finger release
                    active_brush = config.BRUSH_TYPES[self._current_brush_index]
                    print(f"🔍 FINGER RELEASE DEBUG: active_brush={active_brush}, _is_drawing={self._is_drawing}, _is_creating={self._is_creating}")
                    
                    if self._is_drawing and active_brush == "DRAW":
                        # DRAW brush: Finish drawing when user releases index+thumb
                        print("🎨 User released fingers - finishing drawing...")
                        curve_obj = self.finish_drawing(context)
                        if curve_obj:
                            print("🎨 Drawing finished - use quick index+thumb clicks to add/subtract from mesh")
                    
                    elif self._is_creating and active_brush == "CREATE":
                        # CREATE brush: IGNORE finger release - preview stays active until left hand confirmation
                        print("🏗️ CREATE: Ignoring finger release - preview remains active")
                        print("🏗️ Touch thumb+index again to adjust, or left ring+thumb to confirm")
                        print(f"🔍 CREATE DEBUG: State preserved - _is_creating={self._is_creating}, _preview_object={self._preview_object is not None}")
                        # CRITICAL: We do NOT change _is_creating or _preview_object here - they stay active!
                        # This prevents accidental confirmation when fingers spread too wide
                    
                    elif active_brush in ["GRAB", "SMOOTH", "INFLATE", "FLATTEN"]:
                        # Other brushes: Normal finger release handling
                        print(f"🖐️ Finger release detected for {active_brush} brush")
                    
                    # Handle single click timer for left hand boolean operations
                    # (This was moved to run independently of commands)

            # REMOVED: reset_rotation command (left hand index+thumb) is no longer supported

            elif command == "deform" and not finger_positions_3d:
                # This handles the case where deform command exists but no fingers detected
                # Used for click detection when user has a draw object ready
                active_brush = config.BRUSH_TYPES[self._current_brush_index]
                if active_brush == "DRAW" and self._current_draw_object:
                    # User might be doing a quick click for boolean operation
                    print("🖱️ Potential click detected for draw object")
                elif active_brush == "CREATE" and self._is_creating:
                    # CREATE brush: Ignore finger loss - preview stays active until confirmed
                    print("🏗️ CREATE: Fingers lost but preview stays active (wide finger spread)")
                    print("🏗️ Touch thumb+index again to adjust, or left ring+thumb to confirm")

            elif command == "boolean_union":
                if self._last_command != "boolean_union": # Trigger only once per gesture
                    active_brush = config.BRUSH_TYPES[self._current_brush_index]
                    print("🖱️ Left hand index+thumb detected - SIMPLE UNION!")
                    
                    if active_brush == "DRAW":
                        print(f"🔍 DEBUG: _pending_draw_objects count: {len(self._pending_draw_objects)}")
                        if self._pending_draw_objects:
                            print(f"🎨 SIMPLE: Processing {len(self._pending_draw_objects)} stripes...")
                            self.batch_remesh_and_boolean(context, 'UNION')
                        else:
                            print("⚠️ No stripes to process - draw some first!")
                            
                    elif active_brush == "CREATE":
                        print(f"🔍 DEBUG: _pending_create_objects count: {len(self._pending_create_objects)}")
                        if self._pending_create_objects:
                            print(f"🏗️ SIMPLE: Processing {len(self._pending_create_objects)} primitives...")
                            self.batch_remesh_and_boolean_create(context, 'UNION')
                        else:
                            print("⚠️ No primitives to process - create some first!")
                    else:
                        print(f"⚠️ UNION not supported for brush: {active_brush}")
                    
            elif command == "boolean_difference":
                if self._last_command != "boolean_difference": # Trigger only once per gesture
                    active_brush = config.BRUSH_TYPES[self._current_brush_index]
                    print("🖱️ Left hand pinky+thumb detected - SIMPLE DIFFERENCE!")
                    
                    if active_brush == "DRAW":
                        print(f"🔍 DEBUG: _pending_draw_objects count: {len(self._pending_draw_objects)}")
                        if self._pending_draw_objects:
                            print(f"🎨 SIMPLE: Processing {len(self._pending_draw_objects)} stripes...")
                            self.batch_remesh_and_boolean(context, 'DIFFERENCE')
                        else:
                            print("⚠️ No stripes to process - draw some first!")
                            
                    elif active_brush == "CREATE":
                        print(f"🔍 DEBUG: _pending_create_objects count: {len(self._pending_create_objects)}")
                        if self._pending_create_objects:
                            print(f"🏗️ SIMPLE: Processing {len(self._pending_create_objects)} primitives...")
                            self.batch_remesh_and_boolean_create(context, 'DIFFERENCE')
                        else:
                            print("⚠️ No primitives to process - create some first!")
                    else:
                        print(f"⚠️ DIFFERENCE not supported for brush: {active_brush}")
                    
            elif command == "cycle_brush":
                if self._last_command != "cycle_brush": # Trigger only once per gesture
                    self._current_brush_index = (self._current_brush_index + 1) % len(config.BRUSH_TYPES)
                    current_brush = config.BRUSH_TYPES[self._current_brush_index]
                    print(f"Switched brush to: {current_brush}")
                    
                    # Write current brush to fingertips.json for UI overlay
                    try:
                        from pathlib import Path
                        project_root = Path(__file__).parent.parent.parent.parent
                        fingertips_path = project_root / "data" / "input" / "fingertips.json"
                        
                        # Read existing data
                        if fingertips_path.exists():
                            with open(fingertips_path, 'r') as f:
                                fingertip_data = json.load(f)
                        else:
                            fingertip_data = {
                                "command": "none",
                                "left_hand": None,
                                "right_hand": None,
                                "orbit_delta": {"x": 0.0, "y": 0.0},
                                "anchors": [],
                                "scale_axis": "XYZ",
                                "remesh_type": "BLOCKS"
                            }
                        
                        # Update with current brush and radius
                        fingertip_data["active_brush"] = current_brush
                        fingertip_data["active_radius"] = config.RADIUS_LEVELS[self._current_radius_index]['name'].upper()
                        
                        # Write back to file
                        with open(fingertips_path, 'w') as f:
                            json.dump(fingertip_data, f, indent=2)
                        
                        print(f"Updated fingertips.json with active_brush: {current_brush}, radius: {fingertip_data['active_radius']}")
                        
                    except Exception as e:
                        print(f"Error updating fingertips.json with brush info: {e}")

            elif command == "cycle_radius":
                # Check if we're in CREATE brush mode - if so, this gesture cycles primitives instead
                active_brush = config.BRUSH_TYPES[self._current_brush_index]
                if active_brush == "CREATE":
                    # In CREATE mode, left thumb+middle cycles primitives
                    if self._last_command != "cycle_radius":  # Using same command name for simplicity
                        current_primitive = self.cycle_primitive()
                        
                        # Update fingertips.json with current primitive for UI overlay
                        try:
                            from pathlib import Path
                            project_root = Path(__file__).parent.parent.parent.parent
                            fingertips_path = project_root / "data" / "input" / "fingertips.json"
                            
                            # Read existing data
                            if fingertips_path.exists():
                                with open(fingertips_path, 'r') as f:
                                    fingertip_data = json.load(f)
                            else:
                                fingertip_data = {"command": "none", "left_hand": None, "right_hand": None}
                            
                            # Update with current primitive
                            fingertip_data["current_primitive"] = current_primitive
                            
                            # Write back to file
                            with open(fingertips_path, 'w') as f:
                                json.dump(fingertip_data, f, indent=2)
                                
                            print(f"Updated fingertips.json with current_primitive: {current_primitive}")
                            
                        except Exception as e:
                            print(f"Error updating fingertips.json with primitive info: {e}")
                else:
                    # Normal radius cycling for other brushes
                    if self._last_command != "cycle_radius":
                        self._current_radius_index = (self._current_radius_index + 1) % len(config.RADIUS_LEVELS)
                        current_radius = config.RADIUS_LEVELS[self._current_radius_index]['name']
                        print(f"Set brush radius to: {current_radius}")
                        
                        # Update fingertips.json with new radius
                        try:
                            project_root = Path(__file__).parent.parent.parent.parent
                            fingertips_path = project_root / "data" / "input" / "fingertips.json"
                            
                            # Read existing data or create default
                            if fingertips_path.exists():
                                with open(fingertips_path, 'r') as f:
                                    fingertip_data = json.load(f)
                            else:
                                fingertip_data = {
                                    "fingers": [{"id": i, "x": 0, "y": 0, "z": 0, "detected": False} for i in range(10)],
                                    "command": "none",
                                    "left_hand": None,
                                    "right_hand": None,
                                    "orbit_delta": {"x": 0.0, "y": 0.0},
                                    "anchors": [],
                                    "scale_axis": "XYZ",
                                    "remesh_type": "BLOCKS"
                                }
                            
                            # Update with current radius and brush
                            fingertip_data["active_radius"] = current_radius.upper()
                            fingertip_data["active_brush"] = config.BRUSH_TYPES[self._current_brush_index]
                            
                            # Write back to file
                            with open(fingertips_path, 'w') as f:
                                json.dump(fingertip_data, f, indent=2)
                            
                            print(f"Updated fingertips.json with radius: {current_radius.upper()}")
                            
                        except Exception as e:
                            print(f"Error updating fingertips.json with radius info: {e}")

            elif command == "cycle_primitive":
                # This is the same as cycle_radius but explicitly for CREATE mode
                # (Both gestures map to the same finger combination)
                active_brush = config.BRUSH_TYPES[self._current_brush_index]
                if active_brush == "CREATE" and self._last_command != "cycle_primitive":
                    current_primitive = self.cycle_primitive()
                    print(f"🎯 Cycled to primitive: {current_primitive}")

            elif command == "confirm_placement":
                # Left hand ring+thumb: Confirm primitive placement
                active_brush = config.BRUSH_TYPES[self._current_brush_index]
                print(f"🔍 CONFIRM COMMAND DEBUG: active_brush={active_brush}, _last_command={self._last_command}, _create_phase={self._create_phase}")
                print(f"🔍 CONFIRM STATE: _is_creating={self._is_creating}, _preview_object={self._preview_object is not None}")
                
                if active_brush == "CREATE" and self._last_command != "confirm_placement":
                    if self._create_phase == "POSITION" and self._preview_object:
                        print("✅ Left hand ring+thumb detected - confirming primitive placement!")
                        primitive_obj = self.confirm_primitive_placement(context)
                        if primitive_obj:
                            # Automatically apply remesh modifier with smooth octree depth 7
                            print("🔧 Applying automatic remesh (smooth, octree depth 7)...")
                            self.apply_create_remesh(primitive_obj)
                            print("🏗️ Primitive confirmed and remeshed - ready for boolean operations!")
                            print("🏗️ Use left hand index+thumb (UNION) or pinky+thumb (DIFFERENCE) to apply to mesh")
                            # Reset to NONE phase for next primitive
                            self._create_phase = "NONE"
                            self._is_creating = False
                    elif self._create_phase == "SIZE":
                        print("⚠️ Still in size phase - release both hands first to enter position phase")
                    elif self._create_phase == "NONE":
                        print("⚠️ No primitive active. Start creating with both hands (thumb+index) first.")
                    else:
                        print(f"⚠️ Invalid create phase: {self._create_phase}")
                elif active_brush != "CREATE":
                    print(f"🔍 CONFIRM COMMAND DEBUG: Ignoring confirm_placement - not in CREATE brush (current: {active_brush})")
                elif self._last_command == "confirm_placement":
                    print("🔍 CONFIRM COMMAND DEBUG: Ignoring confirm_placement - already processed this gesture")

            elif command == "rewind":
                active_brush = config.BRUSH_TYPES[self._current_brush_index]
                
                if active_brush == "DRAW":
                    # DRAW brush: Remove the last pending draw object
                    if self._pending_draw_objects:
                        removed_obj = self._pending_draw_objects.pop()
                        # Delete the object from Blender scene
                        if removed_obj and removed_obj.name in bpy.data.objects:
                            bpy.data.objects.remove(removed_obj, do_unlink=True)
                            print(f"🗑️ DRAW REWIND: Removed last drawn object. {len(self._pending_draw_objects)} objects remaining.")
                        else:
                            print("⚠️ DRAW REWIND: Last object no longer exists in scene")
                    else:
                        print("⚠️ DRAW REWIND: No pending draw objects to remove")
                
                elif active_brush == "CREATE":
                    # CREATE brush: Remove the last pending create object or cancel current preview
                    if self._is_creating and self._preview_object:
                        # Cancel current preview
                        if self._preview_object.name in bpy.data.objects:
                            bpy.data.objects.remove(self._preview_object, do_unlink=True)
                        self._is_creating = False
                        self._preview_object = None
                        print("🗑️ CREATE REWIND: Canceled current primitive preview")
                    elif self._pending_create_objects:
                        # Remove last confirmed primitive
                        removed_obj = self._pending_create_objects.pop()
                        if removed_obj and removed_obj.name in bpy.data.objects:
                            bpy.data.objects.remove(removed_obj, do_unlink=True)
                            print(f"🗑️ CREATE REWIND: Removed last created object. {len(self._pending_create_objects)} objects remaining.")
                        else:
                            print("⚠️ CREATE REWIND: Last object no longer exists in scene")
                    else:
                        print("⚠️ CREATE REWIND: No pending create objects to remove")
                
                else:
                    # Other brushes: Use mesh deformation history buffer
                    if self._history_buffer and len(self._history_buffer) > 0:
                        previous_verts = self._history_buffer.pop()
                        for i, v_co in enumerate(previous_verts):
                            mesh_obj.data.vertices[i].co = v_co
                        mesh_obj.data.update()
                        print(f"🗑️ MESH REWIND: History step. {len(self._history_buffer)} steps remaining.")
                    else:
                        # To prevent console spam, we can just pass or have a silent print
                        pass

            else:
                # If no command is active, gradually bring all vertex velocities to a stop.
                # This makes the mesh feel like it's settling in a viscous fluid.
                if config.USE_VELOCITY_FORCES:
                    is_settling = False
                    for index, vel in self._vertex_velocities.items():
                        if vel.length > 0.001:
                            self._vertex_velocities[index] *= config.VELOCITY_DAMPING_FACTOR
                            is_settling = True
                    
                    # If any vertex is still moving, we need to update the mesh
                    if is_settling:
                        deform_mesh_with_viscosity(mesh_obj, [], self._initial_volume, self._vertex_velocities, self._history_buffer, self)

            self._last_command = command

            # This is our main refresh tick
            self._timer_last_update = time.time()
            # self.check_for_launcher_requests() # Moved to the top of the modal method

        return {'PASS_THROUGH'}

    def execute(self, context):
        setup_scene()

        # Set custom properties on the window manager to track operator state for the UI
        context.window_manager.conjure_is_running = True
        context.window_manager.conjure_should_stop = False

        # Store the camera's initial transform matrix
        camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
        if camera:
            self._initial_camera_matrix = camera.matrix_world.copy()
        else:
            self._initial_camera_matrix = mathutils.Matrix() # Fallback to identity matrix

        # Initialize the history buffer as a deque with a max length
        self._history_buffer = deque(maxlen=config.MAX_HISTORY_STEPS)
        
        # Calculate and store the initial volume of the mesh
        mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
        if mesh_obj:
            bm = bmesh.new()
            bm.from_mesh(mesh_obj.data)
            self._initial_volume = bm.calc_volume(signed=True)
            # Initialize velocities for all vertices to zero
            self._vertex_velocities = {v.index: mathutils.Vector((0,0,0)) for v in bm.verts}
            bm.free()
            print(f"Initial mesh volume calculated: {self._initial_volume}")
        else:
            self._initial_volume = 1.0
            self._vertex_velocities = {}
            print("Warning: Could not find 'Mesh' object to calculate initial volume.")
        
        # Write initial brush state to fingertips.json for UI overlay
        try:
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent.parent
            fingertips_path = project_root / "data" / "input" / "fingertips.json"
            
            initial_brush = config.BRUSH_TYPES[self._current_brush_index]
            
            # Read existing data or create new
            if fingertips_path.exists():
                with open(fingertips_path, 'r') as f:
                    fingertip_data = json.load(f)
            else:
                fingertip_data = {
                    "command": "none",
                    "left_hand": None,
                    "right_hand": None,
                    "orbit_delta": {"x": 0.0, "y": 0.0},
                    "anchors": [],
                    "scale_axis": "XYZ",
                    "remesh_type": "BLOCKS"
                }
            
            # Set initial brush and radius
            fingertip_data["active_brush"] = initial_brush
            fingertip_data["active_radius"] = config.RADIUS_LEVELS[self._current_radius_index]['name'].upper()
            
            # Write to file
            with open(fingertips_path, 'w') as f:
                json.dump(fingertip_data, f, indent=2)
            
            print(f"Initialized fingertips.json with active_brush: {initial_brush}, radius: {fingertip_data['active_radius']}")
            
        except Exception as e:
            print(f"Error initializing fingertips.json with brush info: {e}")

        # Initialize the state for each of the 10 markers
        self.marker_states = []
        for i in range(10):
            marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
            initial_pos = marker_obj.location.copy() if marker_obj else mathutils.Vector((0,0,0))
            self.marker_states.append({
                'last_pos': initial_pos,
                'last_velocity': mathutils.Vector((0,0,0)),  # Track velocity for smoothing
                'missing_frames': 0,
                'was_hitting_surface': False,  # Track surface contact state
                'last_hit_normal': mathutils.Vector((0,0,1))  # Fallback surface normal
            })

        # Reset the orbit delta tracker
        self._last_orbit_delta = {"x": 0.0, "y": 0.0}

        self._timer = context.window_manager.event_timer_add(config.REFRESH_RATE_SECONDS, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        # Auto-start the backend agent context refresh
        print("🎬 Auto-starting backend agent context refresh...")
        if not CONJURE_OT_auto_refresh_render.is_auto_refresh_running():
            try:
                bpy.app.timers.register(CONJURE_OT_auto_refresh_render.auto_render_timer, first_interval=2.0, persistent=True)
                context.window_manager.conjure_auto_refresh_running = True
                print("✅ Backend agent auto-refresh started (every 3 seconds)")
            except Exception as e:
                print(f"❌ Failed to start auto-refresh: {e}")
        else:
            print("ℹ️ Auto-refresh already running")
        print("Conjure Fingertip Operator is now running.")

        # Add the draw handler for the UI text
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(self.draw_ui_text, (context,), 'WINDOW', 'POST_PIXEL')

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        # Clear the state-tracking properties when the operator stops
        context.window_manager.conjure_is_running = False
        context.window_manager.conjure_should_stop = False

        # Stop auto-refresh when main operator stops
        if hasattr(context.window_manager, 'conjure_auto_refresh_running') and \
           context.window_manager.conjure_auto_refresh_running:
            context.window_manager.conjure_auto_refresh_running = False
            print("🛑 Auto-stopped backend agent context refresh")

        # Remove the draw handler
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None

        context.window_manager.event_timer_remove(self._timer)
        print("Conjure Fingertip Operator has been cancelled.")
        return {'CANCELLED'}


# --- REGISTRATION ---
class CONJURE_OT_auto_refresh_render(bpy.types.Operator):
    """Automatically refresh GestureCamera render every 3 seconds for backend agent context"""
    bl_idname = "conjure.auto_refresh_render"
    bl_label = "Auto Refresh Render"
    bl_description = "Start automatic rendering of GestureCamera every 3 seconds"
    
    def execute(self, context):
        if self.is_auto_refresh_running():
            self.report({'INFO'}, "Auto-refresh is already running")
            return {'CANCELLED'}
        
        print("🎬 Starting automatic GestureCamera refresh (every 3 seconds)...")
        
        # Register the timer for periodic rendering
        bpy.app.timers.register(self.auto_render_timer, first_interval=1.0, persistent=True)
        
        # Set a flag to track that auto-refresh is running
        context.window_manager.conjure_auto_refresh_running = True
        
        self.report({'INFO'}, "Auto-refresh started - GestureCamera will render every 3 seconds")
        return {'FINISHED'}
    
    @staticmethod
    def auto_render_timer():
        """Timer function that renders GestureCamera every 3 seconds"""
        try:
            context = bpy.context
            
            # Check if we should stop (if addon is being unregistered or user stopped it)
            if not hasattr(context.window_manager, 'conjure_auto_refresh_running') or \
               not context.window_manager.conjure_auto_refresh_running:
                print("🛑 Auto-refresh timer stopped")
                return None  # This stops the timer
            
            # Perform the render using the same logic as the manual render
            CONJURE_OT_auto_refresh_render.render_gesture_camera(context)
            
            # Return 3.0 to schedule the next call in 3 seconds
            return 3.0
            
        except Exception as e:
            print(f"❌ Error in auto-refresh timer: {e}")
            # Stop the timer on error
            if hasattr(bpy.context.window_manager, 'conjure_auto_refresh_running'):
                bpy.context.window_manager.conjure_auto_refresh_running = False
            return None
    
    @staticmethod
    def render_gesture_camera(context):
        """Render the GestureCamera to update backend agent context"""
        # Ensure the output directory exists
        output_dir = config.DATA_DIR / "generated_images" / "gestureCamera"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set the active camera to GestureCamera
        gesture_camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
        if not gesture_camera:
            print(f"⚠️ GestureCamera '{config.GESTURE_CAMERA_NAME}' not found - skipping render")
            return
        
        # Store original settings
        original_camera = context.scene.camera
        original_filepath = context.scene.render.filepath
        original_resolution_x = context.scene.render.resolution_x
        original_resolution_y = context.scene.render.resolution_y
        
        try:
            # Set render settings for backend agent context (1024x1024)
            context.scene.camera = gesture_camera
            context.scene.render.resolution_x = 1024
            context.scene.render.resolution_y = 1024
            context.scene.render.filepath = str(output_dir / "render.png")
            
            # Render the image
            bpy.ops.render.render(write_still=True)
            
                            # Removed auto-refresh logging for cleaner console output
            
        except Exception as e:
            print(f"❌ Error rendering GestureCamera: {e}")
        finally:
            # Restore original settings
            context.scene.camera = original_camera
            context.scene.render.filepath = original_filepath
            context.scene.render.resolution_x = original_resolution_x
            context.scene.render.resolution_y = original_resolution_y
    
    @staticmethod
    def is_auto_refresh_running():
        """Check if auto-refresh is currently running"""
        return hasattr(bpy.context.window_manager, 'conjure_auto_refresh_running') and \
               bpy.context.window_manager.conjure_auto_refresh_running


class CONJURE_OT_stop_auto_refresh(bpy.types.Operator):
    """Stop the automatic GestureCamera refresh"""
    bl_idname = "conjure.stop_auto_refresh"
    bl_label = "Stop Auto Refresh"
    bl_description = "Stop automatic rendering of GestureCamera"
    
    def execute(self, context):
        if not CONJURE_OT_auto_refresh_render.is_auto_refresh_running():
            self.report({'INFO'}, "Auto-refresh is not running")
            return {'CANCELLED'}
        
        print("🛑 Stopping automatic GestureCamera refresh...")
        
        # Set flag to stop the timer
        context.window_manager.conjure_auto_refresh_running = False
        
        # The timer will check this flag and stop itself
        self.report({'INFO'}, "Auto-refresh stopped")
        return {'FINISHED'}


classes = (
    CONJURE_PT_control_panel,
    ConjureFingertipOperator,
    CONJURE_OT_force_import_last_mesh,
    CONJURE_OT_stop_operator,
    CONJURE_OT_auto_refresh_render,
    CONJURE_OT_stop_auto_refresh,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Register custom properties to the WindowManager
    bpy.types.WindowManager.conjure_is_running = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.conjure_should_stop = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.conjure_auto_refresh_running = bpy.props.BoolProperty(default=False)


def unregister():
    # Stop auto-refresh timer if it's running
    if hasattr(bpy.types.WindowManager, 'conjure_auto_refresh_running'):
        try:
            bpy.context.window_manager.conjure_auto_refresh_running = False
        except:
            pass  # Context might not be available during shutdown
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    # Clean up the custom properties
    del bpy.types.WindowManager.conjure_is_running
    del bpy.types.WindowManager.conjure_should_stop
    del bpy.types.WindowManager.conjure_auto_refresh_running


if __name__ == "__main__":
    register()
    # We no longer call the operator directly. It must be started from the UI panel.
    # bpy.ops.conjure.fingertip_operator() 