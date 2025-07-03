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
HAND_SCALE_X = 5.0 # Controls side-to-side movement.
HAND_SCALE_Y = 5.0 # Controls forward-backward movement (from hand depth).
HAND_SCALE_Z = 5.0 # Controls up-down movement.

# --- VISUALIZATION ---
MARKER_OUT_OF_VIEW_LOCATION = (1000, 1000, 1000) # Move unused markers here to prevent flickering.

# --- REFRESH RATE ---
# The target interval in seconds for the operator to update.
# A smaller value means a higher refresh rate. 30 FPS is a good balance
# between smooth interaction and preventing I/O contention with the hand tracker.
REFRESH_RATE_SECONDS = 1 / 30  # Target 30 updates per second.

# --- ROTATION ---
ROTATION_SPEED_DEGREES_PER_SEC = 45.0 # How fast the object rotates

# --- SMOOTHING ---
# How much to smooth the movement of the visual fingertip markers.
# A value closer to 0 is smoother but has more "lag". A value of 1 is no smoothing.
SMOOTHING_FACTOR = 0.3

# --- DEFORMATION PARAMETERS ---
# These control how the mesh reacts to the user's hand.
FINGER_INFLUENCE_RADIUS = 3.0  # How far the influence of a finger reaches.
MAX_DISPLACEMENT_PER_FRAME = 0.25 # Safety limit to prevent vertices from moving too far in one frame.
MASS_COHESION_FACTOR = 0.62 # How much vertices stick together to create a smoother deformation.
DEFORM_TIMESTEP = 0.05 # Multiplier for displacement per frame to create a continuous effect.
VOLUME_LOWER_LIMIT = 0.8 # The mesh cannot shrink to less than 80% of its original volume.
VOLUME_UPPER_LIMIT = 1.2 # The mesh cannot expand to more than 120% of its original volume.

# --- VELOCITY & VISCOSITY ---
# These parameters add a sense of weight and momentum to the mesh.
VELOCITY_DAMPING_FACTOR = 0.80 # How much velocity is retained each frame (lower is 'thicker' viscosity).
FINGER_FORCE_STRENGTH = 0.08    # How strongly the finger pushes/pulls the mesh. A much smaller value is needed for a stable velocity-based system.
USE_VELOCITY_FORCES = True # Master toggle for the entire viscosity system.
MAX_HISTORY_STEPS = 50 # The number of undo steps to store in memory.


# === 1. INITIAL SCENE SETUP ===
def setup_scene():
    """
    Ensures that a deformable mesh, fingertip markers, and the gesture camera exist.
    """
    # Ensure the main deformable mesh exists.
    if DEFORM_OBJ_NAME not in bpy.data.objects:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1, location=(0, 0, 0))
        bpy.context.active_object.name = DEFORM_OBJ_NAME
        print(f"Created '{DEFORM_OBJ_NAME}'.")

    # Ensure the GestureCamera exists
    if GESTURE_CAMERA_NAME not in bpy.data.objects:
        bpy.ops.object.camera_add(location=(0, -5, 0))
        bpy.context.active_object.name = GESTURE_CAMERA_NAME
        # Point the camera towards the origin
        bpy.context.active_object.rotation_euler = (math.radians(90), 0, 0)
        print(f"Created '{GESTURE_CAMERA_NAME}'.")

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
    camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
    
    # 2. Define a base coordinate vector from the normalized inputs
    #    (x is side-to-side, y is forward-back, z is up-down)
    local_point = mathutils.Vector((
        (x_norm - 0.5) * HAND_SCALE_X,
        z_norm * -HAND_SCALE_Y, # The negative sign inverts depth from the camera
        (0.5 - y_norm) * HAND_SCALE_Z
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
        print(f"Warning: '{GESTURE_CAMERA_NAME}' not found. Using world-space mapping.")
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
            
            if dist < FINGER_INFLUENCE_RADIUS:
                # Use a squared falloff for a smoother gradient
                falloff = (1.0 - (dist / FINGER_INFLUENCE_RADIUS))**2
                direction = to_finger.normalized()
                force = direction * FINGER_FORCE_STRENGTH * falloff
                net_displacement += force
        
        if net_displacement.length > 0.0001:
            # Clamp displacement to avoid extreme results
            if net_displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                net_displacement = net_displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
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
        smoothed_displacement = original_displacement.lerp(neighbor_avg, MASS_COHESION_FACTOR)
        smoothed_displacements[v.index] = smoothed_displacement
        
    # 3. Apply the smoothed displacements to the vertices
    if smoothed_displacements:
        for v_index, displacement in smoothed_displacements.items():
            # Ensure lookup table is fresh before indexed access
            bm.verts.ensure_lookup_table()
            v = bm.verts[v_index]
            v_world = world_matrix @ v.co
            # Apply the smoothed displacement over time for a continuous effect
            v_world += displacement * DEFORM_TIMESTEP
            # Convert back to local space to update the vertex
            v.co = world_matrix_inv @ v_world

    # 4. Volume Preservation
    # This crucial step prevents the mesh from collapsing on itself.
    current_volume = bm.calc_volume(signed=True)
    if initial_volume != 0: # Avoid division by zero
        volume_ratio = current_volume / initial_volume
        
        if volume_ratio < VOLUME_LOWER_LIMIT or volume_ratio > VOLUME_UPPER_LIMIT:
            target_ratio = max(VOLUME_LOWER_LIMIT, min(volume_ratio, VOLUME_UPPER_LIMIT))
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
def deform_mesh_with_viscosity(mesh_obj, finger_positions_3d, initial_volume, vertex_velocities, history_buffer):
    """
    Deforms the mesh by applying forces and simulating viscosity.
    This version updates vertex velocities for a more dynamic and weighty feel.
    """
    if not mesh_obj:
        return

    # --- Save current state to history before deforming ---
    # We only save if there are active forces being applied.
    if finger_positions_3d:
        current_verts = [v.co.copy() for v in mesh_obj.data.vertices]
        history_buffer.append(current_verts)

    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)

    world_matrix = mesh_obj.matrix_world
    world_matrix_inv = world_matrix.inverted()

    # --- 1. Calculate Forces and Update Velocities ---
    new_displacements = {}
    for v in bm.verts:
        # Get current velocity for this vertex
        current_velocity = vertex_velocities.get(v.index, mathutils.Vector((0,0,0)))
        
        # Calculate force from fingers
        v_world = world_matrix @ v.co
        finger_force = mathutils.Vector((0, 0, 0))
        for finger_pos in finger_positions_3d:
            to_finger = finger_pos - v_world
            dist = to_finger.length
            if dist < FINGER_INFLUENCE_RADIUS:
                falloff = (1.0 - (dist / FINGER_INFLUENCE_RADIUS))**2
                direction = to_finger.normalized()
                finger_force += direction * FINGER_FORCE_STRENGTH * falloff
        
        # Update velocity: add force and apply damping
        new_velocity = (current_velocity + finger_force) * VELOCITY_DAMPING_FACTOR
        
        # Store the updated velocity for the next frame
        vertex_velocities[v.index] = new_velocity
        
        # Calculate the displacement for this frame
        displacement = new_velocity * DEFORM_TIMESTEP
        if displacement.length > MAX_DISPLACEMENT_PER_FRAME:
            displacement = displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
        
        new_displacements[v.index] = displacement

    # --- 2. Apply Displacements ---
    if new_displacements:
        for v_index, displacement in new_displacements.items():
            bm.verts.ensure_lookup_table()
            bm.verts[v_index].co += world_matrix_inv @ displacement

    # --- 3. Volume Preservation ---
    current_volume = bm.calc_volume(signed=True)
    if initial_volume != 0:
        volume_ratio = current_volume / initial_volume
        if volume_ratio < VOLUME_LOWER_LIMIT or volume_ratio > VOLUME_UPPER_LIMIT:
            target_ratio = max(VOLUME_LOWER_LIMIT, min(volume_ratio, VOLUME_UPPER_LIMIT))
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
    last_marker_positions = []

    def modal(self, context, event):
        # The UI panel can set this property to signal the operator to stop
        if context.window_manager.conjure_should_stop:
            return self.cancel(context)

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            return self.cancel(context)

        if event.type == 'TIMER':
            live_data = {}
            if os.path.exists(FINGERTIPS_JSON_PATH):
                with open(FINGERTIPS_JSON_PATH, "r") as f:
                    try:
                        live_data = json.load(f)
                    except json.JSONDecodeError:
                        live_data = {} # Keep going with empty data

            command = live_data.get("command", "none")
            mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)

            # --- Process Fingertips for Visualization ---
            all_fingertips = []
            right_hand_data = live_data.get("right_hand")
            left_hand_data = live_data.get("left_hand")

            # Process both left and right hands for visual markers
            for hand_data in [left_hand_data, right_hand_data]:
                if hand_data and "fingertips" in hand_data:
                    all_fingertips.extend(hand_data["fingertips"])

            finger_positions_3d = []
            # This loop updates the visual markers for all fingers
            for i, tip in enumerate(all_fingertips):
                if tip:
                    target_pos_3d = map_hand_to_3d_space(tip['x'], tip['y'], tip['z'])
                    finger_positions_3d.append(target_pos_3d)
                    marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
                    if marker_obj:
                        last_pos = self.last_marker_positions[i]
                        smoothed_pos = last_pos.lerp(target_pos_3d, SMOOTHING_FACTOR)
                        marker_obj.location = smoothed_pos
                        # Ensure the marker is always visible when in use.
                        marker_obj.hide_viewport = False
                        self.last_marker_positions[i] = smoothed_pos
            
            # Move unused markers out of view instead of hiding them
            for i in range(len(all_fingertips), 10):
                marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
                if marker_obj:
                    marker_obj.location = MARKER_OUT_OF_VIEW_LOCATION

            # --- Execute Commands ---
            if not mesh_obj:
                print(f"'{DEFORM_OBJ_NAME}' not found. Cannot execute commands.")
                return {'PASS_THROUGH'}

            if command == "deform":
                if right_hand_data and "fingertips" in right_hand_data and len(right_hand_data["fingertips"]) >= 2:
                    # Per instructions, only thumb and index finger on right hand cause deformation
                    thumb_tip = right_hand_data["fingertips"][0] # Thumb
                    index_tip = right_hand_data["fingertips"][1] # Index
                    
                    deform_points = [
                        map_hand_to_3d_space(thumb_tip['x'], thumb_tip['y'], thumb_tip['z']),
                        map_hand_to_3d_space(index_tip['x'], index_tip['y'], index_tip['z'])
                    ]
                    
                    if USE_VELOCITY_FORCES:
                        deform_mesh_with_viscosity(mesh_obj, deform_points, self._initial_volume, self._vertex_velocities, self._history_buffer)
                    else:
                        # Non-velocity deformation would also need history tracking added if used
                        deform_mesh(mesh_obj, deform_points, self._initial_volume)

            elif command == "rotate_z":
                # When rotating, gradually bring vertex velocities to a halt
                for index in self._vertex_velocities:
                    self._vertex_velocities[index] *= 0.9 # Dampen significantly
                
                camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
                if camera:
                    # Orbit the camera around the world Z-axis
                    angle_rad = math.radians(ROTATION_SPEED_DEGREES_PER_SEC * REFRESH_RATE_SECONDS)
                    # Create a rotation matrix around the Z axis
                    rot_mat = mathutils.Matrix.Rotation(angle_rad, 4, 'Z')
                    # Apply the rotation to the camera's matrix_world.
                    # This rotates the camera's location and orientation around the world origin.
                    camera.matrix_world = rot_mat @ camera.matrix_world
            
            elif command == "rotate_y":
                # When rotating, gradually bring vertex velocities to a halt
                for index in self._vertex_velocities:
                    self._vertex_velocities[index] *= 0.9 # Dampen significantly

                camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
                if camera:
                    # Orbit the camera around the world Y-axis
                    angle_rad = math.radians(ROTATION_SPEED_DEGREES_PER_SEC * REFRESH_RATE_SECONDS)
                    # Create a rotation matrix around the Y axis
                    rot_mat = mathutils.Matrix.Rotation(angle_rad, 4, 'Y')
                    # Apply the rotation
                    camera.matrix_world = rot_mat @ camera.matrix_world

            elif command == "reset_rotation":
                # Also reset velocities when resetting camera for a clean stop
                for index in self._vertex_velocities:
                    self._vertex_velocities[index] = mathutils.Vector((0,0,0))

                camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
                if camera and self._initial_camera_matrix:
                    camera.matrix_world = self._initial_camera_matrix

            elif command == "rewind":
                if self._last_command != "rewind": # Trigger only once per gesture start
                    if len(self._history_buffer) > 0:
                        previous_verts = self._history_buffer.pop()
                        # Apply the retrieved vertex coordinates to the mesh
                        for i, v_co in enumerate(previous_verts):
                            mesh_obj.data.vertices[i].co = v_co
                        mesh_obj.data.update()
                        print(f"Rewind successful. History has {len(self._history_buffer)} steps remaining.")
                    else:
                        print("History buffer is empty. Nothing to rewind.")

            else:
                # If no command is active, gradually bring all vertex velocities to a stop.
                # This makes the mesh feel like it's settling in a viscous fluid.
                if USE_VELOCITY_FORCES:
                    is_settling = False
                    for index, vel in self._vertex_velocities.items():
                        if vel.length > 0.001:
                            self._vertex_velocities[index] *= VELOCITY_DAMPING_FACTOR
                            is_settling = True
                    
                    # If any vertex is still moving, we need to update the mesh
                    if is_settling:
                        deform_mesh_with_viscosity(mesh_obj, [], self._initial_volume, self._vertex_velocities, self._history_buffer)

            self._last_command = command

        return {'PASS_THROUGH'}

    def execute(self, context):
        setup_scene()

        # Set custom properties on the window manager to track operator state for the UI
        context.window_manager.conjure_is_running = True
        context.window_manager.conjure_should_stop = False

        # Store the camera's initial transform matrix
        camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
        if camera:
            self._initial_camera_matrix = camera.matrix_world.copy()
        else:
            self._initial_camera_matrix = mathutils.Matrix() # Fallback to identity matrix

        # Initialize the history buffer as a deque with a max length
        self._history_buffer = deque(maxlen=MAX_HISTORY_STEPS)

        # Calculate and store the initial volume of the mesh
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
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

        # Initialize the list that will store the last known position of each marker.
        self.last_marker_positions = [mathutils.Vector((0,0,0))] * 10
        for i in range(10):
            marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
            if marker_obj:
                self.last_marker_positions[i] = marker_obj.location.copy()

        self._timer = context.window_manager.event_timer_add(REFRESH_RATE_SECONDS, window=context.window)
        context.window_manager.modal_handler_add(self)
        print("Conjure Fingertip Operator is now running.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        # Clear the state-tracking properties when the operator stops
        context.window_manager.conjure_is_running = False
        context.window_manager.conjure_should_stop = False

        context.window_manager.event_timer_remove(self._timer)
        print("Conjure Fingertip Operator has been cancelled.")
        return {'CANCELLED'}


# --- REGISTRATION ---
def register():
    bpy.utils.register_class(CONJURE_PT_control_panel)
    bpy.utils.register_class(CONJURE_OT_stop_operator)
    bpy.utils.register_class(ConjureFingertipOperator)
    # Register custom properties to the WindowManager
    bpy.types.WindowManager.conjure_is_running = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.conjure_should_stop = bpy.props.BoolProperty(default=False)


def unregister():
    bpy.utils.unregister_class(CONJURE_PT_control_panel)
    bpy.utils.unregister_class(CONJURE_OT_stop_operator)
    bpy.utils.unregister_class(ConjureFingertipOperator)
    # Clean up the custom properties
    del bpy.types.WindowManager.conjure_is_running
    del bpy.types.WindowManager.conjure_should_stop


if __name__ == "__main__":
    register()
    # We no longer call the operator directly. It must be started from the UI panel.
    # bpy.ops.conjure.fingertip_operator() 