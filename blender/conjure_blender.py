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

# --- DEFORMATION PARAMETERS ---
# These control how the mesh reacts to the user's hand.
FINGER_INFLUENCE_RADIUS = 0.5  # How far the influence of a finger reaches.
FINGER_FORCE_STRENGTH = 0.1    # How strongly the finger pushes/pulls the mesh.
MAX_DISPLACEMENT_PER_FRAME = 0.1 # Safety limit to prevent vertices from moving too far in one frame.


# === 1. INITIAL SCENE SETUP ===
def setup_scene():
    """
    Ensures that a deformable mesh and fingertip marker templates exist.
    """
    if DEFORM_OBJ_NAME not in bpy.data.objects:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1, location=(0, 0, 0))
        bpy.context.active_object.name = DEFORM_OBJ_NAME
        print(f"Created '{DEFORM_OBJ_NAME}'.")

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
    Maps normalized (0-1) coordinates from Mediapipe to Blender's 3D world space.
    - Hand X -> World X
    - Hand Y -> World Z (up/down)
    - Hand Z (depth) -> World Y (forward/backward, inverted)
    """
    x = (x_norm - 0.5) * scale
    y = z_norm * -scale
    z = (0.5 - y_norm) * scale
    return mathutils.Vector((x, y, z))


# === 3. MESH DEFORMATION ===
def deform_mesh(mesh_obj, finger_positions_3d):
    """
    Deforms the mesh using bmesh based on the 3D positions of the fingertips.
    """
    if not mesh_obj or not finger_positions_3d:
        return

    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh_obj.data)

    size = len(bm.verts)
    kd = mathutils.kdtree.KDTree(size)
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()

    for finger_pos in finger_positions_3d:
        for (co, index, dist) in kd.find_range(finger_pos, FINGER_INFLUENCE_RADIUS):
            vertex = bm.verts[index]
            falloff = (1.0 - (dist / FINGER_INFLUENCE_RADIUS)) ** 2
            direction = (finger_pos - vertex.co).normalized()
            displacement = direction * FINGER_FORCE_STRENGTH * falloff

            if displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                displacement = displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
            
            vertex.co += displacement

    bmesh.update_edit_mesh(mesh_obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')


# === BLENDER MODAL OPERATOR ===
class ConjureFingertipOperator(bpy.types.Operator):
    """The main operator that reads hand data and orchestrates actions."""
    bl_idname = "conjure.fingertip_operator"
    bl_label = "Conjure Fingertip Operator"

    _timer = None

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
                    pos_3d = map_hand_to_3d_space(tip['x'], tip['y'], tip['z'])
                    finger_positions_3d.append(pos_3d)
                    marker_obj = bpy.data.objects.get(f"Fingertip.{i:02d}")
                    if marker_obj:
                        marker_obj.location = pos_3d
                        marker_obj.hide_viewport = False
            
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
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
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