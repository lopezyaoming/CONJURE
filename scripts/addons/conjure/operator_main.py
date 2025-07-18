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
# How much to smooth the movement of the visual fingertip markers.
# A value closer to 0 is smoother but has more "lag". A value of 1 is no smoothing.
SMOOTHING_FACTOR = 0.3

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
BRUSH_TYPES = ['PINCH', 'GRAB', 'SMOOTH', 'INFLATE', 'FLATTEN'] # The available deformation brushes


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

    # 4. Volume Preservation
    # This crucial step prevents the mesh from collapsing on itself.
    current_volume = bm.calc_volume(signed=True)
    if initial_volume != 0: # Avoid division by zero
        volume_ratio = current_volume / initial_volume
        
        if volume_ratio < config.VOLUME_LOWER_LIMIT or volume_ratio > config.VOLUME_UPPER_LIMIT:
            target_ratio = max(config.VOLUME_LOWER_LIMIT, min(volume_ratio, config.VOLUME_UPPER_LIMIT))
            scale_factor = (target_ratio / volume_ratio)**(1/3)
            
            # Calculate the centroid of the mesh to scale from the center
            centroid = mathutils.Vector()
            for v in bm.verts:
                centroid += v.co
            centroid /= len(bm.verts)
            
            # Apply corrective scaling to each vertex
            for v in bm.verts:
                v.co = centroid + (v.co - centroid) * scale_factor

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

        if brush_type == 'PINCH':
            # PINCH has its own special falloff based on distance to each finger,
            # so we don't use the centered falloff.
            v_world = world_matrix @ v.co
            for finger_pos in finger_positions_3d:
                to_finger = finger_pos - v_world
                dist = to_finger.length
                if dist < effective_radius:
                    pinch_falloff = (1.0 - (dist / effective_radius))**2
                    force += to_finger.normalized() * config.FINGER_FORCE_STRENGTH * pinch_falloff

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

    # --- 3. Volume Preservation ---
    current_volume = bm.calc_volume(signed=True)
    if initial_volume != 0:
        volume_ratio = current_volume / initial_volume
        if volume_ratio < config.VOLUME_LOWER_LIMIT or volume_ratio > config.VOLUME_UPPER_LIMIT:
            target_ratio = max(config.VOLUME_LOWER_LIMIT, min(volume_ratio, config.VOLUME_UPPER_LIMIT))
            scale_factor = (target_ratio / volume_ratio)**(1/3)
            centroid = mathutils.Vector()
            for v in bm.verts:
                centroid += v.co
            centroid /= len(bm.verts)
            for v in bm.verts:
                v.co = centroid + (v.co - centroid) * scale_factor

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

        # --- 5. Recalculate Initial Volume for Deformation ---
        self._initial_volume = self.get_mesh_volume(new_obj)
        print(f"Set initial volume for new mesh: {self._initial_volume}")


    def draw_ui_text(self, context):
        """Draws the current brush name on the viewport."""
        font_id = 0  # Default font
        
        # Draw Brush Name
        blf.position(font_id, 15, 60, 0)
        blf.size(font_id, 20)
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        active_brush = config.BRUSH_TYPES[self._current_brush_index]
        blf.draw(font_id, f"Brush: {active_brush}")

        # Draw Radius Size
        blf.position(font_id, 15, 30, 0)
        blf.size(font_id, 20)
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        active_radius = config.RADIUS_LEVELS[self._current_radius_index]['name'].upper()
        blf.draw(font_id, f"Radius: {active_radius}")

    def check_for_launcher_requests(self):
        """Checks state.json for commands from the launcher/agent."""
        # --- Define the absolute path to state.json relative to this script ---
        # This is the most robust way to ensure we're always looking in the right place.
        state_file_path = Path(__file__).parent.parent.parent / "data" / "input" / "state.json"

        # Read the state file
        try:
            with open(state_file_path, 'r') as f:
                state_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return # File not found or invalid JSON, nothing to do

        command = state_data.get("command")
        if command:
            print(f"DEBUG: Operator detected command '{command}' in state file.")

        if command == "spawn_primitive":
            primitive_type = state_data.get("primitive_type")
            if primitive_type:
                self.handle_spawn_primitive(primitive_type)
                # Clear the command in the state file so it doesn't run again
                print(f"DEBUG: Clearing command '{command}' from state file.")
                state_data["command"] = None
                state_data["primitive_type"] = None
                with open(state_file_path, 'w') as f:
                    json.dump(state_data, f, indent=4)
        
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
            with open(state_file_path, 'w') as f:
                json.dump(state_data, f, indent=4)

    def modal(self, context, event):
        # The UI panel can set this property to signal the operator to stop
        if context.window_manager.conjure_should_stop:
            context.window_manager.conjure_is_running = False
            context.window_manager.conjure_should_stop = False # Reset the flag
            self.cancel(context)
            return {'CANCELLED'}

        # --- Handle Mouse & Keyboard Input ---
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE', 'RIGHTMOUSE'}:
            # Allow standard navigation controls to pass through
            return {'PASS_THROUGH'}

        # --- Main Logic on Timer Tick ---
        if event.type == 'TIMER':
            # Add this call to poll for external commands
            self.check_for_launcher_requests()

            # --- 1. Read Hand Data ---
            try:
                with open(config.FINGERTIPS_JSON_PATH, 'r') as f:
                    self.hand_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                self.hand_data = {} # Reset if file is missing or corrupt
                pass # Continue silently if the file isn't ready

            # --- 2. Process Commands & Gestures ---
            command = self.hand_data.get("command", "none")
            remesh_type = self.hand_data.get("remesh_type", "NONE")
            is_deforming = self.hand_data.get("deform_active", False)
            closed_fist_detected = self.hand_data.get("closed_fist", False)
            rotation_delta = self.hand_data.get("rotation", 0.0)
            brush_change_request = self.hand_data.get("change_brush", 0) # -1 for prev, 1 for next
            radius_change_request = self.hand_data.get("change_radius", 0) # -1 for prev, 1 for next

            # Update the brush or radius if requested
            if brush_change_request != 0:
                self.handle_brush_change(brush_change_request)
            if radius_change_request != 0:
                self.handle_radius_change(radius_change_request)

            # --- 3. Update Camera Orbit ---
            self.handle_camera_orbit(rotation_delta)

            # --- 4. Update Fingertip Markers ---
            self.update_fingertip_markers(context)

            # --- 5. Perform Mesh Deformation ---
            deform_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
            if deform_obj and is_deforming and self.visible_fingers:
                # Get the active brush type
                brush_type = self.brush_settings['name']
                
                # Calculate hand movement vector for the GRAB brush
                hand_move_vector = None
                if brush_type == 'GRAB' and self._last_hand_center:
                    current_hand_center = self.get_hand_center()
                    if current_hand_center:
                        hand_move_vector = current_hand_center - self._last_hand_center
                
                # Always use the viscosity-based deformation now
                self.deform_mesh_with_viscosity(
                    deform_obj,
                    [f['world_pos'] for f in self.visible_fingers],
                    self._initial_volume,
                    self._vertex_velocities,
                    self._history_buffer,
                    self,
                    brush_type=brush_type,
                    hand_move_vector=hand_move_vector
                )

            # --- 6. Handle Gesture-based Rendering ---
            if closed_fist_detected and not self.last_closed_fist_state:
                self.handle_gesture_render()

            # --- 7. Update State & Redraw ---
            self.last_closed_fist_state = closed_fist_detected
            self._last_hand_center = self.get_hand_center() # Update for next frame
            
            # Tag the viewport for redrawing to show updates
            if context.area:
                context.area.tag_redraw()

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

        # Initialize the state for each of the 10 markers
        self.marker_states = []
        for i in range(10):
            marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
            initial_pos = marker_obj.location.copy() if marker_obj else mathutils.Vector((0,0,0))
            self.marker_states.append({
                'last_pos': initial_pos,
                'missing_frames': 0
            })

        # Reset the orbit delta tracker
        self._last_orbit_delta = {"x": 0.0, "y": 0.0}

        self._timer = context.window_manager.event_timer_add(config.REFRESH_RATE_SECONDS, window=context.window)
        context.window_manager.modal_handler_add(self)
        print("Conjure Fingertip Operator is now running.")

        # Add the draw handler for the UI text
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(self.draw_ui_text, (context,), 'WINDOW', 'POST_PIXEL')

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        # Clear the state-tracking properties when the operator stops
        context.window_manager.conjure_is_running = False
        context.window_manager.conjure_should_stop = False

        # Remove the draw handler
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None

        context.window_manager.event_timer_remove(self._timer)
        print("Conjure Fingertip Operator has been cancelled.")
        return {'CANCELLED'}


# --- REGISTRATION ---
classes = (
    ConjureFingertipOperator,
    CONJURE_OT_stop_operator,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Register custom properties to the WindowManager
    bpy.types.WindowManager.conjure_is_running = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.conjure_should_stop = bpy.props.BoolProperty(default=False)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    # Clean up the custom properties
    del bpy.types.WindowManager.conjure_is_running
    del bpy.types.WindowManager.conjure_should_stop


if __name__ == "__main__":
    register()
    # We no longer call the operator directly. It must be started from the UI panel.
    # bpy.ops.conjure.fingertip_operator() 