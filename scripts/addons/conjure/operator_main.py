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


# === 3. HISTORY BUFFER ===
class HistoryBuffer:
    """A circular buffer to store mesh states for undo/redo functionality."""
    def __init__(self, max_size):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.cursor = -1

    def add_state(self, mesh_data):
        """Adds a new state to the buffer, clearing any 'future' states."""
        if self.cursor < len(self.buffer) - 1:
            temp_buffer = list(self.buffer)
            self.buffer = deque(temp_buffer[:self.cursor + 1], maxlen=self.max_size)
        
        new_mesh_data = mesh_data.copy()
        self.buffer.append(new_mesh_data)
        self.cursor = len(self.buffer) - 1

    def rewind(self):
        """Moves the cursor back one step in history."""
        if self.cursor > 0:
            self.cursor -= 1
        return self.get_current_state()

    def fast_forward(self):
        """Moves the cursor forward one step in history."""
        if self.cursor < len(self.buffer) - 1:
            self.cursor += 1
        return self.get_current_state()

    def get_current_state(self):
        """Returns the mesh data at the current cursor position."""
        if 0 <= self.cursor < len(self.buffer):
            return self.buffer[self.cursor]
        return None

    def clear(self):
        """Clears the entire history buffer."""
        self.buffer.clear()
        self.cursor = -1

# === 4. MESH DEFORMATION ===
def deform_mesh_with_viscosity(mesh_obj, finger_positions_3d, initial_volume, vertex_velocities, history_buffer, operator_instance, brush_type='PINCH', hand_move_vector=None):
    """
    Deforms the mesh using a velocity-based system for a more 'viscous' feel.
    This is the primary deformation logic.
    """
    if not mesh_obj or not finger_positions_3d:
        return

    radius_settings = operator_instance.get_current_radius_setting()
    
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    
    world_matrix = mesh_obj.matrix_world
    
    # --- 1. Calculate forces on each vertex ---
    vertex_forces = {}
    
    # A. Calculate average position of active fingers (for brushes like FLATTEN)
    avg_finger_pos = mathutils.Vector((0, 0, 0))
    for finger_pos in finger_positions_3d:
        avg_finger_pos += finger_pos
    if finger_positions_3d:
        avg_finger_pos /= len(finger_positions_3d)

    for v in bm.verts:
        v_world = world_matrix @ v.co
        net_force = mathutils.Vector((0, 0, 0))

        for finger_pos in finger_positions_3d:
            to_finger = finger_pos - v_world
            dist = to_finger.length
            
            # --- BRUSH-SPECIFIC LOGIC ---
            if brush_type == 'PINCH':
                radius = radius_settings['finger']
                if dist < radius:
                    falloff = (1.0 - (dist / radius))**2
                    net_force += to_finger.normalized() * config.FINGER_FORCE_STRENGTH * falloff
            
            elif brush_type == 'GRAB' and hand_move_vector:
                radius = radius_settings['grab']
                if dist < radius:
                    falloff = (1.0 - (dist / radius))**2
                    net_force += hand_move_vector * config.GRAB_FORCE_STRENGTH * falloff

            elif brush_type == 'INFLATE':
                radius = radius_settings['inflate']
                if dist < radius:
                    falloff = (1.0 - (dist / radius))**2
                    # Use vertex normal for inflation/deflation direction
                    net_force += v.normal * config.INFLATE_FORCE_STRENGTH * falloff

            elif brush_type == 'SMOOTH':
                radius = radius_settings['finger']
                if dist < radius:
                    # Move vertex towards the average position of its neighbors
                    avg_neighbor_pos = mathutils.Vector()
                    if v.link_edges:
                        for edge in v.link_edges:
                            avg_neighbor_pos += edge.other_vert(v).co
                        avg_neighbor_pos /= len(v.link_edges)
                        
                        # Convert to world space for calculation
                        avg_neighbor_pos_world = world_matrix @ avg_neighbor_pos
                        smoothing_vec = avg_neighbor_pos_world - v_world
                        falloff = (1.0 - (dist / radius))**2
                        net_force += smoothing_vec * config.SMOOTH_FORCE_STRENGTH * falloff
            
            elif brush_type == 'FLATTEN':
                radius = radius_settings['flatten']
                if dist < radius:
                    # Project vertex onto a plane defined by the average finger position and normal
                    plane_normal = (v_world - avg_finger_pos).normalized()
                    plane_point = avg_finger_pos
                    
                    point_on_plane = v_world.project(plane_point + plane_normal) - v_world.project(plane_point)
                    flatten_vec = (plane_point + point_on_plane) - v_world

                    falloff = (1.0 - (dist / radius))**2
                    net_force += flatten_vec * config.FLATTEN_FORCE_STRENGTH * falloff

        if net_force.length > 0.0001:
            vertex_forces[v.index] = net_force

    # --- 2. Update velocities and apply displacements ---
    for v_idx, force in vertex_forces.items():
        # Update velocity: v_new = (v_old * damping) + (force * timestep)
        old_velocity = vertex_velocities.get(v_idx, mathutils.Vector((0, 0, 0)))
        new_velocity = (old_velocity * config.VELOCITY_DAMPING_FACTOR) + (force * config.DEFORM_TIMESTEP)
        vertex_velocities[v_idx] = new_velocity

        # Apply displacement
        displacement = new_velocity * config.DEFORM_TIMESTEP
        if displacement.length > config.MAX_DISPLACEMENT_PER_FRAME:
            displacement = displacement.normalized() * config.MAX_DISPLACEMENT_PER_FRAME
        
        bm.verts[v_idx].co += displacement

    # --- 3. Enforce Volume Constraints ---
    current_volume = bm.calc_volume(signed=True)
    volume_ratio = current_volume / initial_volume
    
    if not (config.VOLUME_LOWER_LIMIT < volume_ratio < config.VOLUME_UPPER_LIMIT):
        # If volume is out of bounds, scale the mesh back towards the original volume
        scale_factor = (1.0 / volume_ratio)**(1/3) # Cube root for uniform scaling
        bmesh.ops.scale(bm, vec=(scale_factor, scale_factor, scale_factor), verts=bm.verts)

    # --- 4. Update the actual mesh data and clean up ---
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()

# --- 5. MAIN OPERATOR ---
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
        """
        Calculates the volume of a mesh.
        """
        # Ensure the mesh is a BMesh object
        bm = bmesh.new()
        bm.from_mesh(mesh_obj.data)
        bm.transform(mesh_obj.matrix_world)
        volume = bm.calc_volume(signed=True)
        bm.free()
        return abs(volume)

    def reinitialize_mesh_state(self):
        """Resets the history and volume tracking for a new mesh."""
        mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
        if mesh_obj:
            # Ensure the history buffer is initialized
            if not self._history_buffer:
                self._history_buffer = HistoryBuffer(max_size=config.MAX_HISTORY_STEPS)

            self._initial_volume = self.get_mesh_volume(mesh_obj)
            self._vertex_velocities.clear()
            self._history_buffer.clear()
            self._history_buffer.add_state(mesh_obj.data) # Save the initial state of the new mesh
            print("Mesh state reinitialized.")
            
    def draw_ui_text(self, context):
        """Draws the current brush and radius on the viewport."""
        active_command = self.get_active_command()
        radius_setting = self.get_current_radius_setting()['name']
        color = config.BRUSH_COLORS.get(active_command, (1.0, 1.0, 1.0, 1.0))

        # --- Draw Text using blf ---
        font_id = 0 # Default font
        blf.position(font_id, 15, 50, 0)
        blf.size(font_id, 16)
        blf.color(font_id, *color)
        blf.draw(font_id, f"Brush: {active_command}")
        
        blf.position(font_id, 15, 25, 0)
        blf.size(font_id, 14)
        blf.color(font_id, 0.8, 0.8, 0.8, 1.0)
        blf.draw(font_id, f"Radius: {radius_setting.capitalize()}")

    def handle_sculpting(self, context, hand_data):
        """Handles the mesh deformation based on the active brush."""
        mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
        if not mesh_obj:
            return

        active_brush = self.get_active_command()
        
        # Filter for only the visible finger positions to pass to the deformer
        visible_finger_locations = [
            state['location'] for state in self.marker_states if state['visible']
        ]
        
        # Calculate the hand movement vector for the 'GRAB' brush
        hand_move_vector = None
        current_hand_center = self.get_hand_center()
        if self._last_hand_center and current_hand_center:
            hand_move_vector = current_hand_center - self._last_hand_center
        self._last_hand_center = current_hand_center
        
        # Call the main deformation function with all necessary parameters
        deform_mesh_with_viscosity(
            mesh_obj,
            visible_finger_locations,
            self._initial_volume,
            self._vertex_velocities,
            self._history_buffer,
            self, # Pass the operator instance itself
            brush_type=active_brush,
            hand_move_vector=hand_move_vector
        )

    def handle_brush_change(self):
        """Cycles through the available brush types."""
        self._current_brush_index = (self._current_brush_index + 1) % len(config.BRUSH_TYPES)
        print(f"Brush changed to: {self.get_active_command()}")

    def handle_radius_change(self):
        """Cycles through the available radius sizes."""
        self._current_radius_index = (self._current_radius_index + 1) % len(config.RADIUS_LEVELS)
        print(f"Radius changed to: {self.get_current_radius_setting()['name']}")

    def handle_camera_orbit(self, rotation_delta):
        """Orbits the camera around the world origin based on hand gesture data."""
        camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
        if not camera:
            return

        # Smooth the rotation delta to prevent jerky movements
        smoothed_delta_x = self._last_orbit_delta['x'] * (1.0 - config.ORBIT_SMOOTHING_FACTOR) + rotation_delta['x'] * config.ORBIT_SMOOTHING_FACTOR
        smoothed_delta_y = self._last_orbit_delta['y'] * (1.0 - config.ORBIT_SMOOTHING_FACTOR) + rotation_delta['y'] * config.ORBIT_SMOOTHING_FACTOR
        
        self._last_orbit_delta['x'] = smoothed_delta_x
        self._last_orbit_delta['y'] = smoothed_delta_y

        # Apply rotation around the Z (yaw) and X (pitch) axes
        # Note: We rotate around the world origin (0,0,0)
        pivot = mathutils.Vector((0.0, 0.0, 0.0))
        
        # Yaw rotation (around world Z-axis)
        bpy.ops.object.select_all(action='DESELECT')
        camera.select_set(True)
        bpy.ops.transform.rotate(
            value=-smoothed_delta_x * config.ORBIT_SENSITIVITY, 
            orient_axis='Z', 
            orient_type='GLOBAL', 
            center_override=pivot
        )
        
        # Pitch rotation (around camera's local X-axis)
        bpy.ops.transform.rotate(
            value=-smoothed_delta_y * config.ORBIT_SENSITIVITY, 
            orient_axis='X', 
            orient_type='LOCAL',
            center_override=pivot
        )

    def handle_rewind(self, direction):
        """Rewinds or fast-forwards the mesh history."""
        mesh_obj = bpy.data.objects.get(config.DEFORM_OBJ_NAME)
        if not mesh_obj or not self._history_buffer:
            return
            
        if direction == 'backward':
            self._history_buffer.rewind()
        elif direction == 'forward':
            self._history_buffer.fast_forward()
        
        # Apply the state from the buffer to the mesh
        current_state = self._history_buffer.get_current_state()
        if current_state:
            bm = bmesh.new()
            bm.from_mesh(current_state)
            bm.to_mesh(mesh_obj.data)
            bm.free()
            mesh_obj.data.update()

    def check_for_launcher_requests(self):
        """Checks the state file for commands from the main launcher."""
        state_file_path = config.STATE_JSON_PATH
        if not state_file_path.exists():
            return
        
        try:
            with open(state_file_path, 'r+') as f:
                state_data = json.load(f)
                command_data = state_data.get("command")

                if not command_data:
                    return

                tool_name = command_data.get("tool_name")
                params = command_data.get("parameters", {})
                
                if tool_name == "spawn_primitive":
                    primitive_type = params.get("primitive_type")
                    if primitive_type:
                        print(f"EXECUTING INSTRUCTION: spawn_primitive with params: {params}")
                        bpy.ops.conjure.spawn_primitive(primitive_type=primitive_type)
                        self.reinitialize_mesh_state()
                        
                        # Clear the command and write back to the file
                        state_data["command"] = None
                        f.seek(0)
                        json.dump(state_data, f, indent=4)
                        f.truncate()

        except (json.JSONDecodeError, IOError, ValueError) as e:
            # This can happen if the file is being written by the other process.
            # It's safe to just skip this check and try again on the next tick.
            # print(f"Could not process state.json: {e}")
            pass

    def modal(self, context, event):
        # The UI panel can set this property to signal the operator to stop
        if context.window_manager.conjure_should_stop:
            context.window_manager.conjure_is_running = False
            context.window_manager.conjure_should_stop = False # Reset the flag
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            # --- Primary Update Loop ---
            try:
                with open(config.FINGERTIPS_JSON_PATH, 'r') as f:
                    hand_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {'PASS_THROUGH'} # Continue if file is missing or malformed

            # --- 1. Process Agent/Launcher Commands ---
            # This is the new integration point for agent-driven actions.
            self.check_for_launcher_requests()

            # --- 2. Process Hand Gesture Commands ---
            command = hand_data.get("command", "none")
            command_data = hand_data.get("data", {})

            # A. Handle Continuous Actions (like sculpting and orbiting)
            if command == "sculpt":
                self.handle_sculpting(context, hand_data)
            elif command == "orbit":
                if "rotation_delta" in command_data:
                    self.handle_camera_orbit(command_data["rotation_delta"])
            
            # B. Handle One-Shot Actions (triggered only on change)
            if command != self._last_command:
                if command == "brush_change":
                    self.handle_brush_change()
                elif command == "radius_change":
                    self.handle_radius_change()
                elif command == "rewind_backward":
                    self.handle_rewind('backward')
                elif command == "rewind_forward":
                    self.handle_rewind('forward')
                
                # Update UI state for speaking
                is_speaking = (command == "start_speaking")
                state_file_path = config.STATE_JSON_PATH # Use the correct path from the config
                if state_file_path.exists():
                    try:
                        with open(state_file_path, 'r+') as f:
                            state = json.load(f)
                            # Only write if the state is different to avoid extra processing
                            if state.get("user_is_speaking") != is_speaking:
                                state["user_is_speaking"] = is_speaking
                                f.seek(0)
                                json.dump(state, f, indent=4)
                                f.truncate()
                    except (IOError, json.JSONDecodeError) as e:
                        print(f"Error updating speaking state: {e}")


            self._last_command = command

            # --- 3. Update Visuals ---
            self.update_fingertip_markers(context, hand_data.get("fingers", []))

            # Tag the viewport for redrawing to show updates
            if context.area:
                context.area.tag_redraw()

        return {'PASS_THROUGH'}

    def get_active_command(self):
        """Gets the name of the currently active brush."""
        if 0 <= self._current_brush_index < len(config.BRUSH_TYPES):
            return config.BRUSH_TYPES[self._current_brush_index]
        return "UNKNOWN"

    def get_current_radius_setting(self):
        """Gets the entire dictionary for the current radius level."""
        return config.RADIUS_LEVELS[self._current_radius_index]

    def update_fingertip_markers(self, context, finger_data):
        """
        Updates the position and visibility of the fingertip markers based on live data.
        This is a stable, restored implementation.
        """
        if not finger_data:
            # If no fingers are detected, hide all markers.
            for i in range(10):
                marker = bpy.data.objects.get(f"Fingertip.{i:02d}")
                if marker:
                    marker.location = config.MARKER_OUT_OF_VIEW_LOCATION
                    marker.hide_viewport = True
            self.marker_states.clear()
            return
            
        new_marker_states = []
        for i, finger in enumerate(finger_data):
            marker_name = f"Fingertip.{i:02d}"
            marker = bpy.data.objects.get(marker_name)
            if not marker:
                continue

            # Map normalized coordinates to world space
            world_pos = map_hand_to_3d_space(finger['x'], finger['y'], finger['z'])
            
            # Smooth the marker's movement
            smoothed_pos = marker.location.lerp(world_pos, config.SMOOTHING_FACTOR)
            marker.location = smoothed_pos
            marker.hide_viewport = False # Make the marker visible
            
            new_marker_states.append({
                "name": marker_name,
                "location": smoothed_pos,
                "visible": True # All detected fingers are considered visible
            })

        # Hide any markers that are no longer in use
        for i in range(len(finger_data), 10):
            marker = bpy.data.objects.get(f"Fingertip.{i:02d}")
            if marker:
                marker.location = config.MARKER_OUT_OF_VIEW_LOCATION
                marker.hide_viewport = True # Hide the unused marker

        self.marker_states = new_marker_states

    def get_hand_center(self):
        """Calculates the average position of all VISIBLE fingertips."""
        if not self.visible_fingers:
            return None
        center = mathutils.Vector()
        for finger in self.visible_fingers:
            center += finger['world_pos']
        return center / len(self.visible_fingers) if self.visible_fingers else None
        
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

        self.visible_fingers = []
        self.last_closed_fist_state = False

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
    # Example of how to add a dummy function if it were missing
    # This is not needed if the function is properly added to the class
    # setattr(ConjureFingertipOperator, 'handle_camera_orbit', lambda self, rot: None)
    
    register()
    # We no longer call the operator directly. It must be started from the UI panel.
    # bpy.ops.conjure.fingertip_operator() 