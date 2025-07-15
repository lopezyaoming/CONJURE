# This file is a simplified pseudocode version of `fingertipmain.py`.
# Its purpose is to lay down the armature for the core logic of CONJURE's
# Blender integration, focusing on three key tasks:
# 1. Receiving real-time hand data from a JSON file.
# 2. Plotting the detected fingertips as visual markers in the 3D scene.
# 3. Deforming a target mesh based on the fingertip positions.
#
# Unnecessary "bloat" such as UI panels, complex state management for multiple
# modes (e.g., rotation, scaling beyond deformation), and advanced features
# like rendering have been removed to clarify the fundamental mechanics.

import bpy
import json
import os
import mathutils
import bmesh
import time

# --- CORE CONFIGURATION ---
# In a real script, these would be in a config.py file.
# For simplicity, we define the path to the JSON file from the capture script here.
FINGERTIPS_JSON_PATH = "C:/Coding/CONJURE/data/input/fingertips.json"
DEFORM_OBJ_NAME = "DeformableMesh"  # The name of the mesh we will manipulate

# --- DEFORMATION PARAMETERS ---
# These control how the mesh reacts to the user's hand.
FINGER_INFLUENCE_RADIUS = 0.5  # How far the influence of a finger reaches.
FINGER_FORCE_STRENGTH = 0.1    # How strongly the finger pushes/pulls the mesh.
MAX_DISPLACEMENT_PER_FRAME = 0.1 # Safety limit to prevent vertices from moving too far in one frame.
SMOOTHING_FACTOR = 0.5         # How much the deformation is smoothed out across the mesh.


# === 1. INITIAL SCENE SETUP ===
# Functions to ensure the necessary objects exist in the Blender scene.

def setup_scene():
    """
    Ensures that a deformable mesh and a fingertip marker template exist.
    """
    # Ensure the main deformable mesh exists.
    if DEFORM_OBJ_NAME not in bpy.data.objects:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1, location=(0, 0, 0))
        bpy.context.active_object.name = DEFORM_OBJ_NAME
        print(f"Created '{DEFORM_OBJ_NAME}'.")

    # Ensure a template object for fingertip markers exists.
    if "FingertipTemplate" not in bpy.data.objects:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.05, location=(0, 0, -10))
        bpy.context.active_object.name = "FingertipTemplate"
        print("Created 'FingertipTemplate'.")

    # Ensure 10 fingertip markers are created and ready to be moved.
    for i in range(10):
        marker_name = f"Fingertip.{i:02d}"
        if marker_name not in bpy.data.objects:
            template = bpy.data.objects.get("FingertipTemplate")
            if template:
                marker = template.copy()
                marker.name = marker_name
                bpy.context.collection.objects.link(marker)


# === 2. COORDINATE MAPPING ===
# This is the most critical function for translating 2D hand data to 3D space.

def map_hand_to_3d_space(x_norm, y_norm, z_norm, scale=2.0):
    """
    Maps normalized (0-1) coordinates from Mediapipe to Blender's 3D world space.
    This function needs to be calibrated to feel intuitive.

    - The camera is assumed to be looking down the -Y axis.
    - Hand X -> World X
    - Hand Y -> World Z (up/down)
    - Hand Z (depth) -> World Y (forward/backward)
    """
    # Center the coordinates around the origin (0,0,0)
    x = (x_norm - 0.5) * scale
    y = (z_norm) * -scale  # Invert Z so moving hand away from camera moves point away
    z = (0.5 - y_norm) * scale # Invert Y so moving hand up moves point up

    return mathutils.Vector((x, y, z))


# === 3. MESH DEFORMATION ===
# The core logic for altering the mesh vertices.

def deform_mesh(mesh_obj, finger_positions_3d):
    """
    Deforms the mesh using bmesh based on the 3D positions of the fingertips.
    """
    if not mesh_obj or not finger_positions_3d:
        return

    # Enter Edit Mode and get the bmesh representation for high-performance operations
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh_obj.data)

    # Use a KDTree for faster lookup of nearby vertices (more efficient than iterating all)
    size = len(bm.verts)
    kd = mathutils.kdtree.KDTree(size)
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()


    # For each fingertip, find and displace nearby vertices
    for finger_pos in finger_positions_3d:
        # Find all vertices within the influence radius of the finger
        for (co, index, dist) in kd.find_range(finger_pos, FINGER_INFLUENCE_RADIUS):
            vertex = bm.verts[index]

            # Calculate falloff: closer vertices are affected more
            falloff = 1.0 - (dist / FINGER_INFLUENCE_RADIUS)
            falloff = falloff ** 2 # squared for a smoother curve

            # Calculate the direction and magnitude of displacement
            direction = (finger_pos - vertex.co).normalized()
            displacement = direction * FINGER_FORCE_STRENGTH * falloff

            # Safety clamp to prevent extreme deformation
            if displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                displacement = displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME

            # Apply the displacement
            vertex.co += displacement

    # Exit Edit Mode and update the mesh in the viewport
    bpy.ops.object.mode_set(mode='OBJECT')
    bmesh.update_edit_mesh(mesh_obj.data)


# === BLENDER MODAL OPERATOR ===
# A persistent operator that runs in the background to continuously process data.

class ConjureFingertipOperator(bpy.types.Operator):
    """The main operator that reads hand data and orchestrates actions."""
    bl_idname = "conjure.fingertip_operator"
    bl_label = "Conjure Fingertip Operator"

    _timer = None

    def modal(self, context, event):
        # This method is called repeatedly by the timer
        if event.type == 'ESC':
            return self.cancel(context)

        if event.type == 'TIMER':
            # --- 1. RECEIVE JSON INFORMATION ---
            live_data = {}
            if os.path.exists(FINGERTIPS_JSON_PATH):
                with open(FINGERTIPS_JSON_PATH, "r") as f:
                    try:
                        live_data = json.load(f)
                    except json.JSONDecodeError:
                        pass # Ignore errors from partially written files

            # --- Process Data ---
            command = live_data.get("command", "none")
            right_hand_data = live_data.get("right_hand", {})
            
            if right_hand_data:
                fingertips_norm = right_hand_data.get("fingertips", [])

                # --- 2. PLOT FINGERS IN 3D SPACE ---
                finger_positions_3d = []
                for i, tip in enumerate(fingertips_norm):
                    # Map normalized coords to 3D space
                    pos_3d = map_hand_to_3d_space(tip['x'], tip['y'], tip['z'])
                    finger_positions_3d.append(pos_3d)
                    
                    # Update the visual marker for this fingertip
                    marker_name = f"Fingertip.{i:02d}"
                    marker_obj = bpy.data.objects.get(marker_name)
                    if marker_obj:
                        marker_obj.location = pos_3d
                
                # Hide unused markers
                for i in range(len(fingertips_norm), 10):
                     marker_name = f"Fingertip.{i:02d}"
                     marker_obj = bpy.data.objects.get(marker_name)
                     if marker_obj:
                         marker_obj.hide_viewport = True


                # --- 3. DEFORM THE MESH ---
                if command == "deform":
                    mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
                    if mesh_obj:
                        deform_mesh(mesh_obj, finger_positions_3d)

        return {'PASS_THROUGH'}

    def execute(self, context):
        """Called when the operator is first run."""
        # Setup the scene with required objects
        setup_scene()
        
        # Add a timer that will trigger the 'modal' method every 0.05 seconds
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        print("Fingertip Operator is now running.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """Called when the operator is cancelled (e.g., by pressing ESC)."""
        context.window_manager.event_timer_remove(self._timer)
        print("Fingertip Operator has been cancelled.")
        return {'CANCELLED'}


# --- REGISTRATION ---
# Standard Blender addon registration boilerplate.

def register():
    bpy.utils.register_class(ConjureFingertipOperator)

def unregister():
    bpy.utils.unregister_class(ConjureFingertipOperator)

if __name__ == "__main__":
    register()
    # To run this operator, you would typically call it from the Blender UI
    # or another script using: bpy.ops.conjure.fingertip_operator()
    # For testing, we can run it directly when the script is loaded.
    bpy.ops.conjure.fingertip_operator() 