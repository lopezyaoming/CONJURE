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
DEFORM_OBJ_NAME = "DeformableMesh"  # The name of the mesh we will manipulate
GESTURE_CAMERA_NAME = "GestureCamera" # The camera used for perspective-based mapping

# --- MAPPING SCALE ---
# These values control how sensitive the hand tracking is.
# Larger values mean the virtual hand moves more for a given physical hand movement.
HAND_SCALE_X = 2.0 # Controls side-to-side movement.
HAND_SCALE_Y = 2.0 # Controls forward-backward movement (from hand depth).
HAND_SCALE_Z = 2.0 # Controls up-down movement.

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
FINGER_INFLUENCE_RADIUS = 0.5  # How far the influence of a finger reaches.
FINGER_FORCE_STRENGTH = 0.1    # How strongly the finger pushes/pulls the mesh.
MAX_DISPLACEMENT_PER_FRAME = 0.1 # Safety limit to prevent vertices from moving too far in one frame.


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


# === 3. MESH DEFORMATION ===
def deform_mesh(mesh_obj, finger_positions_3d):
    """
    Deforms the mesh using bmesh based on the 3D positions of the fingertips.
    This version operates on mesh data directly for stability and performance,
    avoiding repeated mode switching.
    """
    if not mesh_obj or not finger_positions_3d:
        return

    # 1. Create a bmesh from the object's mesh data
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)

    # Ensure the lookup table is current before any indexed access
    bm.verts.ensure_lookup_table()

    # The mesh's vertices are in its own local space, but the fingertip
    # positions are in world space. We must convert the fingertips to local space.
    inv_matrix = mesh_obj.matrix_world.inverted()
    local_finger_positions = [inv_matrix @ pos for pos in finger_positions_3d]

    # 2. Build a KDTree for efficient spatial lookups of vertices
    size = len(bm.verts)
    kd = mathutils.kdtree.KDTree(size)
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()

    # 3. Calculate all displacements first, storing them in a dictionary.
    # This avoids modifying the mesh while iterating over it.
    displacements = {}  # {vertex_index: displacement_vector}
    for finger_pos in local_finger_positions:
        for (co, index, dist) in kd.find_range(finger_pos, FINGER_INFLUENCE_RADIUS):
            if dist > 0:
                falloff = (1.0 - (dist / FINGER_INFLUENCE_RADIUS))**2
                direction = (finger_pos - co).normalized()
                
                # Add to existing displacement for this vertex or create a new one
                current_displacement = displacements.get(index, mathutils.Vector((0, 0, 0)))
                displacements[index] = current_displacement + (direction * FINGER_FORCE_STRENGTH * falloff)

    # 4. Apply the calculated displacements to the bmesh vertices
    if displacements:
        for index, displacement in displacements.items():
            # Safety clamp to prevent extreme, glitchy movements
            if displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                displacement = displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
            
            bm.verts[index].co += displacement

    # 5. Write the modified bmesh data back to the mesh
    bm.to_mesh(mesh_obj.data)
    bm.free()

    # 6. Tag the mesh to ensure the viewport updates
    mesh_obj.data.update()


# === 4. CUBE CREATION ===
def create_new_cube(pos1, pos2):
    """Creates a new cube object between two points in space."""
    if not pos1 or not pos2:
        return None
    
    center = (pos1 + pos2) / 2.0
    size = (pos1 - pos2).length
    if size < 0.01:
        size = 0.01

    bpy.ops.mesh.primitive_cube_add(size=1, location=center, scale=(size, size, size))
    cube = bpy.context.active_object
    cube.name = "ConjureCube"
    return cube

def update_cube(cube, pos1, pos2):
    """Updates an existing cube's position and scale based on two points."""
    if not cube or not pos1 or not pos2:
        return
        
    center = (pos1 + pos2) / 2.0
    size = (pos1 - pos2).length
    if size < 0.01:
        size = 0.01
        
    cube.location = center
    cube.scale = (size, size, size)

def finalize_cube_creation(deform_obj, cube_obj):
    """Applies a boolean union to merge the cube with the deform mesh."""
    if not deform_obj or not cube_obj:
        return

    print(f"Finalizing cube: applying UNION with {deform_obj.name}")
    
    # Ensure deform_obj is active and selected
    bpy.ops.object.select_all(action='DESELECT')
    deform_obj.select_set(True)
    bpy.context.view_layer.objects.active = deform_obj

    # Create and configure the boolean modifier
    bool_mod = deform_obj.modifiers.new(name="ConjureUnion", type='BOOLEAN')
    bool_mod.operation = 'UNION'
    bool_mod.object = cube_obj
    
    # Apply the modifier
    try:
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        print("Boolean modifier applied.")
    except RuntimeError as e:
        print(f"Error applying boolean modifier: {e}. Removing modifier.")
        deform_obj.modifiers.remove(bool_mod)

    # Clean up the temporary cube
    bpy.data.objects.remove(cube_obj, do_unlink=True)
    print("Temporary cube removed.")


# === BLENDER MODAL OPERATOR ===
class ConjureFingertipOperator(bpy.types.Operator):
    """The main operator that reads hand data and orchestrates actions."""
    bl_idname = "conjure.fingertip_operator"
    bl_label = "Conjure Fingertip Operator"

    _timer = None
    _last_command = "none"
    _active_cube = None
    _initial_camera_matrix = None
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

            # --- Handle state transitions (e.g., finishing a cube creation) ---
            if self._last_command == "create_cube" and command != "create_cube":
                if self._active_cube and mesh_obj:
                    finalize_cube_creation(mesh_obj, self._active_cube)
                self._active_cube = None # Reset cube state

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
                    deform_mesh(mesh_obj, deform_points)

            elif command == "rotate_z":
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
                camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
                if camera:
                    # Orbit the camera around the world Y-axis
                    angle_rad = math.radians(ROTATION_SPEED_DEGREES_PER_SEC * REFRESH_RATE_SECONDS)
                    # Create a rotation matrix around the Y axis
                    rot_mat = mathutils.Matrix.Rotation(angle_rad, 4, 'Y')
                    # Apply the rotation
                    camera.matrix_world = rot_mat @ camera.matrix_world

            elif command == "reset_rotation":
                camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
                if camera and self._initial_camera_matrix:
                    camera.matrix_world = self._initial_camera_matrix

            elif command == "create_cube":
                if right_hand_data and "fingertips" in right_hand_data and len(right_hand_data["fingertips"]) >= 5:
                    # Get thumb and pinky from right hand
                    thumb_tip = right_hand_data["fingertips"][0]
                    pinky_tip = right_hand_data["fingertips"][4]

                    thumb_pos_3d = map_hand_to_3d_space(thumb_tip['x'], thumb_tip['y'], thumb_tip['z'])
                    pinky_pos_3d = map_hand_to_3d_space(pinky_tip['x'], pinky_tip['y'], pinky_tip['z'])

                    if self._active_cube is None:
                        # Create the cube for the first time
                        self._active_cube = create_new_cube(thumb_pos_3d, pinky_pos_3d)
                    else:
                        # Update the existing cube's position and scale
                        update_cube(self._active_cube, thumb_pos_3d, pinky_pos_3d)

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
        # Clean up any leftover cube
        if self._active_cube:
            bpy.data.objects.remove(self._active_cube, do_unlink=True)
            self._active_cube = None
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