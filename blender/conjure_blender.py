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

# --- REFRESH RATE ---
# The target interval in seconds for the operator to update.
# A smaller value means a higher refresh rate. 30 FPS is a good balance
# between smooth interaction and preventing I/O contention with the hand tracker.
REFRESH_RATE_SECONDS = 1 / 30  # Target 30 updates per second.

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
def map_hand_to_3d_space(x_norm, y_norm, z_norm, scale=2.0):
    """
    Maps normalized (0-1) hand coordinates to Blender's 3D world space,
    relative to the perspective of the GestureCamera.
    """
    # 1. Get the camera object
    camera = bpy.data.objects.get(GESTURE_CAMERA_NAME)
    
    # 2. Define a base coordinate vector from the normalized inputs
    #    (x is side-to-side, y is forward-back, z is up-down)
    local_point = mathutils.Vector((
        (x_norm - 0.5) * scale,
        z_norm * -scale,
        (0.5 - y_norm) * scale
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


# === BLENDER MODAL OPERATOR ===
class ConjureFingertipOperator(bpy.types.Operator):
    """The main operator that reads hand data and orchestrates actions."""
    bl_idname = "conjure.fingertip_operator"
    bl_label = "Conjure Fingertip Operator"

    _timer = None
    last_marker_positions = []

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            return self.cancel(context)

        if event.type == 'TIMER':
            live_data = {}
            if os.path.exists(FINGERTIPS_JSON_PATH):
                with open(FINGERTIPS_JSON_PATH, "r") as f:
                    try:
                        live_data = json.load(f)
                    except json.JSONDecodeError:
                        live_data = {}

            command = live_data.get("command", "none")
            all_fingertips = []
            
            # Process both left and right hands
            for hand_type in ["left_hand", "right_hand"]:
                hand_data = live_data.get(hand_type)
                if hand_data and "fingertips" in hand_data:
                    all_fingertips.extend(hand_data["fingertips"])

            finger_positions_3d = []
            for i, tip in enumerate(all_fingertips):
                if tip:
                    # The target position is the actual, precise location from the hand tracker.
                    target_pos_3d = map_hand_to_3d_space(tip['x'], tip['y'], tip['z'])
                    
                    # The deformation logic should use the precise coordinates for responsiveness.
                    finger_positions_3d.append(target_pos_3d)
                    
                    marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
                    if marker_obj:
                        # Get the marker's last position.
                        last_pos = self.last_marker_positions[i]
                        
                        # Calculate the new smoothed position using linear interpolation (lerp).
                        smoothed_pos = last_pos.lerp(target_pos_3d, SMOOTHING_FACTOR)
                        
                        # Apply the smoothed position to the visual marker only.
                        marker_obj.location = smoothed_pos
                        marker_obj.hide_viewport = False
                        
                        # Store the new smoothed position for the next frame's calculation.
                        self.last_marker_positions[i] = smoothed_pos
            
            # Hide unused markers
            for i in range(len(all_fingertips), 10):
                marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
                if marker_obj:
                    marker_obj.hide_viewport = True

            if command == "deform" and live_data.get("deform_active", False):
                mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
                if mesh_obj:
                    deform_mesh(mesh_obj, finger_positions_3d)

        return {'PASS_THROUGH'}

    def execute(self, context):
        setup_scene()

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
        context.window_manager.event_timer_remove(self._timer)
        print("Conjure Fingertip Operator has been cancelled.")
        return {'CANCELLED'}


# --- REGISTRATION ---
def register():
    bpy.utils.register_class(ConjureFingertipOperator)

def unregister():
    bpy.utils.unregister_class(ConjureFingertipOperator)

if __name__ == "__main__":
    register()
    bpy.ops.conjure.fingertip_operator() 