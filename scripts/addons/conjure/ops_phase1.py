"""
Phase 1 operators for CONJURE - VIBE Modeling workflow
Handles FLUX1.DEPTH + PartPacker integration and mesh processing
"""

import bpy
import bmesh
import mathutils
from pathlib import Path
from . import config
import json
import time

class CONJURE_OT_render_gesture_camera(bpy.types.Operator):
    """Render the GestureCamera for FLUX1.DEPTH input"""
    bl_idname = "conjure.render_gesture_camera"
    bl_label = "Render Gesture Camera"
    
    def execute(self, context):
        print("📸 Rendering GestureCamera for FLUX1.DEPTH...")
        
        # Ensure the output directory exists
        output_dir = config.DATA_DIR / "generated_images" / "gestureCamera"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set the active camera to GestureCamera
        gesture_camera = bpy.data.objects.get(config.GESTURE_CAMERA_NAME)
        if not gesture_camera:
            self.report({'ERROR'}, f"GestureCamera '{config.GESTURE_CAMERA_NAME}' not found")
            return {'CANCELLED'}
        
        # Store original settings
        original_camera = context.scene.camera
        original_filepath = context.scene.render.filepath
        original_resolution_x = context.scene.render.resolution_x
        original_resolution_y = context.scene.render.resolution_y
        
        try:
            # Set render settings for FLUX1.DEPTH (1024x1024)
            context.scene.camera = gesture_camera
            context.scene.render.resolution_x = 1024
            context.scene.render.resolution_y = 1024
            context.scene.render.filepath = str(output_dir / "render.png")
            
            # Render the image
            bpy.ops.render.render(write_still=True)
            
            print(f"✅ GestureCamera render completed: {context.scene.render.filepath}")
            
        finally:
            # Restore original settings
            context.scene.camera = original_camera
            context.scene.render.filepath = original_filepath
            context.scene.render.resolution_x = original_resolution_x
            context.scene.render.resolution_y = original_resolution_y
        
        return {'FINISHED'}

class CONJURE_OT_import_and_process_mesh(bpy.types.Operator):
    """Import and process mesh from PartPacker results"""
    bl_idname = "conjure.import_and_process_mesh"
    bl_label = "Import and Process Mesh"
    
    def execute(self, context):
        print("📦 Starting mesh import and processing...")
        
        # Check if we have a mesh path in state
        try:
            with open(config.STATE_JSON_PATH, 'r') as f:
                state_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.report({'ERROR'}, "Could not read state file")
            return {'CANCELLED'}
        
        mesh_path = state_data.get("mesh_path")
        if not mesh_path:
            self.report({'ERROR'}, "No mesh path specified")
            return {'CANCELLED'}
        
        full_path = Path(mesh_path)
        if not full_path.exists():
            self.report({'ERROR'}, f"Mesh file not found: {mesh_path}")
            return {'CANCELLED'}
        
        print(f"📦 Importing mesh from: {full_path}")
        
        # Create placeholder "Mesh" empty to prevent console errors
        self.create_placeholder_mesh()
        
        # Clear existing imported meshes (but keep Mesh placeholder)
        self.clear_existing_segments()
        
        # Import the GLB file
        try:
            bpy.ops.import_scene.gltf(filepath=str(full_path))
            print("✅ GLTF import completed")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import GLB: {e}")
            return {'CANCELLED'}
        
        # Process imported meshes
        mesh_objects = self.get_imported_meshes()
        if not mesh_objects:
            self.report({'ERROR'}, "No valid meshes found after import")
            return {'CANCELLED'}
        
        # Filter by volume and rename
        min_volume_threshold = state_data.get("min_volume_threshold", 0.001)
        valid_meshes = self.filter_and_rename_meshes(mesh_objects, min_volume_threshold)
        
        if not valid_meshes:
            self.report({'ERROR'}, "No meshes survived volume filtering")
            return {'CANCELLED'}
        
        # Center all meshes at origin
        self.center_meshes_at_origin(valid_meshes)
        
        print(f"✅ Successfully imported and processed {len(valid_meshes)} mesh segments")
        
        # Setup materials and apply default material to all segments
        self.setup_selection_materials()
        self.apply_default_materials_to_segments(valid_meshes)
        
        # Enter segment selection mode automatically
        self.enter_selection_mode()
        
        return {'FINISHED'}
    
    def setup_selection_materials(self):
        """Get existing materials for default and selected states"""
        # Get existing default material
        default_mat = bpy.data.materials.get("default_material")
        if default_mat:
            print("✅ Found existing default_material")
        else:
            print("⚠️ default_material not found in scene")
        
                # Get existing selection material
        selected_mat = bpy.data.materials.get("selected_material")
        if selected_mat:
            print("✅ Found existing selected_material")
        else:
            print("⚠️ selected_material not found in scene")
    
    def apply_default_materials_to_segments(self, mesh_objects):
        """Apply default material to all imported segments"""
        default_mat = bpy.data.materials.get("default_material")
        if not default_mat:
            print("⚠️ Cannot apply materials - default_material not found")
            return
        
        for obj in mesh_objects:
            try:
                # Clear existing materials
                obj.data.materials.clear()
                # Apply default material
                obj.data.materials.append(default_mat)
                print(f"🎨 Applied default_material to {obj.name}")
            except Exception as e:
                print(f"❌ Error applying material to {obj.name}: {e}")
    
    def create_placeholder_mesh(self):
        """Create a small mesh object named 'Mesh' to prevent console errors"""
        # Remove existing Mesh if it exists
        existing_mesh = bpy.data.objects.get("Mesh")
        if existing_mesh:
            bpy.data.objects.remove(existing_mesh, do_unlink=True)
            print("🗑️ Removed existing Mesh object")
        
        # Create a small cube mesh as placeholder
        bpy.ops.mesh.primitive_cube_add(size=0.01, location=(0, 0, 0))
        placeholder = bpy.context.active_object
        placeholder.name = "Mesh"
        placeholder.hide_viewport = True  # Hidden by default
        print("📍 Created placeholder 'Mesh' cube object")
    
    def enter_selection_mode(self):
        """Enter segment selection mode and update state"""
        try:
            with open(config.STATE_JSON_PATH, 'r') as f:
                state_data = json.load(f)
            
            # Set selection mode
            state_data.update({
                "selection_mode": "active",
                "command": "segment_selection"  # This will disable deform mode
            })
            
            with open(config.STATE_JSON_PATH, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            print("🎯 Entered segment selection mode")
            
        except Exception as e:
            print(f"❌ Error setting selection mode: {e}")
    
    def get_state_data(self):
        """Read current state data from state.json"""
        try:
            with open(config.STATE_JSON_PATH, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def clear_existing_segments(self):
        """Remove existing segment meshes but keep placeholder and primitives"""
        to_remove = []
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.name.startswith('seg_'):
                to_remove.append(obj)
        
        for obj in to_remove:
            obj_name = obj.name  # Store name before removal
            bpy.data.objects.remove(obj, do_unlink=True)
            print(f"🗑️ Removed existing segment: {obj_name}")
    
    def get_imported_meshes(self):
        """Get all newly imported mesh objects"""
        # Get all selected objects that are meshes (recently imported)
        imported_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        return imported_objects
    
    def filter_and_rename_meshes(self, mesh_objects, min_volume_threshold):
        """Filter meshes by volume and rename them as segments"""
        valid_meshes = []
        
        # Calculate volumes and filter
        mesh_volumes = []
        for obj in mesh_objects:
            volume = self.calculate_mesh_volume(obj)
            if volume >= min_volume_threshold:
                mesh_volumes.append((obj, volume))
                print(f"✅ Kept mesh: {obj.name} (volume: {volume:.6f})")
            else:
                print(f"🗑️ Culling small mesh: {obj.name} (volume: {volume:.6f})")
                bpy.data.objects.remove(obj, do_unlink=True)
        
        # Sort by volume (largest first) and rename
        mesh_volumes.sort(key=lambda x: x[1], reverse=True)
        
        for i, (obj, volume) in enumerate(mesh_volumes, 1):
            obj.name = f"seg_{i}"
            valid_meshes.append(obj)
            print(f"🏷️ Labeled mesh: {obj.name} (volume: {volume:.6f})")
        
        return valid_meshes
    
    def calculate_mesh_volume(self, obj):
        """Calculate the volume of a mesh object"""
        # Create a new bmesh instance
        bm = bmesh.new()
        
        # Copy the mesh data
        bm.from_mesh(obj.data)
        
        # Apply object transform to the bmesh
        bm.transform(obj.matrix_world)
        
        # Ensure face indices are correct
        bm.faces.ensure_lookup_table()
        
        # Calculate volume
        volume = bm.calc_volume()
        
        # Clean up
        bm.free()
        
        return abs(volume)  # Take absolute value in case of inverted faces
    
    def cull_small_meshes(self, mesh_objects, min_volume_threshold):
        """Remove meshes smaller than the threshold"""
        valid_meshes = []
        culled_count = 0
        
        for obj in mesh_objects:
            volume = self.calculate_mesh_volume(obj)
            if volume >= min_volume_threshold:
                valid_meshes.append(obj)
                print(f"✅ Keeping mesh: {obj.name} (volume: {volume:.6f})")
            else:
                print(f"🗑️ Culling small mesh: {obj.name} (volume: {volume:.6f})")
                bpy.data.objects.remove(obj, do_unlink=True)
                culled_count += 1
        
        print(f"📊 Culled {culled_count} small meshes, kept {len(valid_meshes)} meshes")
        return valid_meshes
    
    def center_meshes_at_origin(self, mesh_objects):
        """Center all mesh objects at the origin"""
        if not mesh_objects:
            return
        
        # Calculate the combined bounding box of all meshes
        min_bound = mathutils.Vector((float('inf'), float('inf'), float('inf')))
        max_bound = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))
        
        for obj in mesh_objects:
            for vertex in obj.bound_box:
                world_vertex = obj.matrix_world @ mathutils.Vector(vertex)
                min_bound.x = min(min_bound.x, world_vertex.x)
                min_bound.y = min(min_bound.y, world_vertex.y)
                min_bound.z = min(min_bound.z, world_vertex.z)
                max_bound.x = max(max_bound.x, world_vertex.x)
                max_bound.y = max(max_bound.y, world_vertex.y)
                max_bound.z = max(max_bound.z, world_vertex.z)
        
        # Calculate center offset
        center_offset = (min_bound + max_bound) / 2
        
        # Move all meshes to center them at origin
        for obj in mesh_objects:
            obj.location -= center_offset
        
        print(f"📍 Centered {len(mesh_objects)} meshes at origin (offset: {center_offset})")

class CONJURE_OT_fuse_mesh(bpy.types.Operator):
    """Boolean union all mesh segments into a single 'Mesh' object"""
    bl_idname = "conjure.fuse_mesh"
    bl_label = "Fuse Mesh Segments"
    
    def execute(self, context):
        print("🔗 Starting mesh fusion process...")
        
        # Get all segment objects (seg_1, seg_2, etc.)
        segment_objects = [obj for obj in bpy.data.objects 
                          if obj.type == 'MESH' and obj.name.startswith('seg_')]
        
        if len(segment_objects) < 2:
            self.report({'ERROR'}, "Need at least 2 segments to fuse")
            return {'CANCELLED'}
        
        # Sort by name to ensure consistent order (seg_1, seg_2, seg_3, etc.)
        segment_objects.sort(key=lambda obj: int(obj.name.split('_')[1]))
        
        print(f"🔗 Fusing {len(segment_objects)} segments: {[obj.name for obj in segment_objects]}")
        
        # Start with the largest segment (seg_1)
        target_obj = segment_objects[0]
        target_obj.name = "Mesh"  # Rename to main mesh
        
        # Boolean union each subsequent segment
        for i, source_obj in enumerate(segment_objects[1:], 2):
            print(f"🔗 Fusing seg_{i} into Mesh...")
            
            # Add boolean modifier
            bool_modifier = target_obj.modifiers.new(name=f"Union_{source_obj.name}", type='BOOLEAN')
            bool_modifier.operation = 'UNION'
            bool_modifier.object = source_obj
            
            # Apply the modifier
            bpy.context.view_layer.objects.active = target_obj
            bpy.ops.object.modifier_apply(modifier=bool_modifier.name)
            
            # Remove the source object
            bpy.data.objects.remove(source_obj, do_unlink=True)
        
        # Ensure the final mesh is centered and properly named
        self.finalize_mesh(target_obj)
        
        print("✅ Mesh fusion completed successfully")
        return {'FINISHED'}
    
    def finalize_mesh(self, mesh_obj):
        """Final processing of the fused mesh"""
        # Ensure it's at origin
        mesh_obj.location = (0, 0, 0)
        
        # Recalculate normals
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print(f"✅ Finalized mesh: {mesh_obj.name}")

class CONJURE_OT_segment_selection(bpy.types.Operator):
    """Enable gesture-based segment selection with touch detection"""
    bl_idname = "conjure.segment_selection"
    bl_label = "Select Segment"
    
    def execute(self, context):
        print("🎯 Starting segment selection mode...")
        
        # Set up materials for selection feedback
        self.setup_selection_materials()
        
        # Get all segment objects
        segment_objects = [obj for obj in bpy.data.objects 
                          if obj.type == 'MESH' and obj.name.startswith('seg_')]
        
        if not segment_objects:
            print("⚠️ No segments found to select from - checking for available mesh to import")
            # Instead of erroring, try to find and import mesh
            try:
                with open(config.STATE_JSON_PATH, 'r') as f:
                    state_data = json.load(f)
                mesh_path = state_data.get("mesh_path")
                if mesh_path:
                    self.report({'INFO'}, f"No segments found, importing mesh from {mesh_path}")
                    return {'FINISHED'}  # Let the import process handle this
                else:
                    self.report({'ERROR'}, "No segments found and no mesh_path available to import")
                    return {'CANCELLED'}
            except Exception as e:
                self.report({'ERROR'}, f"No segments found and could not read state: {e}")
                return {'CANCELLED'}
        
        # Apply default material to all segments
        default_mat = bpy.data.materials.get("default_material")
        for obj in segment_objects:
            obj.data.materials.clear()
            if default_mat:
                obj.data.materials.append(default_mat)
        
        # Update state to indicate we're in selection mode
        self.update_state({
            "selection_mode": "active",
            "command": "segment_selection",  # This disables deform mode
            "selected_segment": None
        })
        
        print(f"✅ Segment selection mode active for {len(segment_objects)} segments")
        print("👆 Point at a segment with your right index finger")
        print("🤏 Touch thumb to index finger to select the highlighted segment")
        
        return {'FINISHED'}
    
    def setup_selection_materials(self):
        """Get existing materials for default and selected states"""
        # Get existing default material
        default_mat = bpy.data.materials.get("default_material")
        if default_mat:
            print("✅ Found existing default_material")
        else:
            print("⚠️ default_material not found in scene")
        
        # Get existing selection material
        selected_mat = bpy.data.materials.get("selected_material")
        if selected_mat:
            print("✅ Found existing selected_material")
        else:
            print("⚠️ selected_material not found in scene")
    
    def update_state(self, data):
        """Update state.json with new data"""
        try:
            # Read current state
            with open(config.STATE_JSON_PATH, 'r') as f:
                state_data = json.load(f)
            
            # Update with new data
            state_data.update(data)
            
            # Write back to file
            with open(config.STATE_JSON_PATH, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            print(f"❌ Error updating state: {e}")

class CONJURE_OT_exit_selection_mode(bpy.types.Operator):
    """Exit segment selection mode and return to normal operation"""
    bl_idname = "conjure.exit_selection_mode" 
    bl_label = "Exit Selection Mode"
    
    def execute(self, context):
        print("🚪 Exiting segment selection mode...")
        
        # Check if there's a confirmed selection to finalize
        try:
            with open(config.STATE_JSON_PATH, 'r') as f:
                state_data = json.load(f)
            
            # Look for any segment with selected_material as the confirmed choice
            segment_objects = [obj for obj in bpy.data.objects 
                              if obj.type == 'MESH' and obj.name.startswith('seg_')]
            
            selected_mat = bpy.data.materials.get("selected_material")
            confirmed_segment = None
            
            for obj in segment_objects:
                if obj.data.materials and obj.data.materials[0] == selected_mat:
                    confirmed_segment = obj
                    break
            
            if confirmed_segment:
                print(f"🏁 Finalizing selection: {confirmed_segment.name} will become 'Mesh'")
                
                # Get the placeholder Mesh object
                placeholder = bpy.data.objects.get("Mesh")
                if placeholder:
                    bpy.data.objects.remove(placeholder, do_unlink=True)
                    print("🗑️ Removed placeholder Mesh")
                
                # Rename the selected segment to "Mesh"
                confirmed_segment.name = "Mesh"
                
                # Reset all other segments to default material
                default_mat = bpy.data.materials.get("default_material")
                remaining_segments = [obj for obj in bpy.data.objects 
                                    if obj.type == 'MESH' and obj.name.startswith('seg_')]
                
                if default_mat:
                    for obj in remaining_segments:
                        if obj.data.materials:
                            obj.data.materials[0] = default_mat
                        else:
                            obj.data.materials.append(default_mat)
                
                print(f"✅ {confirmed_segment.name} is now the active mesh for deformation")
            else:
                print("ℹ️ No segment was selected - exiting without changes")
                
        except Exception as e:
            print(f"❌ Error during finalization: {e}")
        
        # Update state to exit selection mode
        self.update_state({
            "selection_mode": "inactive",
            "command": None,  # Clear selection command to re-enable deform
            "selected_segment": None
        })
        
        print("✅ Selection mode exited - deform mode re-enabled")
        return {'FINISHED'}
    
    def update_state(self, data):
        """Update state.json with new data"""
        try:
            with open(config.STATE_JSON_PATH, 'r') as f:
                state_data = json.load(f)
            
            state_data.update(data)
            
            with open(config.STATE_JSON_PATH, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            print(f"❌ Error updating state: {e}")

class CONJURE_OT_test_flux_pipeline(bpy.types.Operator):
    """Test the complete FLUX1.DEPTH -> PartPacker pipeline"""
    bl_idname = "conjure.test_flux_pipeline"
    bl_label = "Test FLUX Pipeline"
    
    def execute(self, context):
        print("🧪 Testing FLUX pipeline with sample prompt...")
        
        # Test prompt for the pipeline
        test_prompt = "A futuristic robotic sculpture with smooth curves and metallic surfaces, rendered in a clean studio lighting setup"
        
        # Set up the flux mesh generation command
        command_data = {
            "flux_pipeline_request": "new",
            "flux_prompt": test_prompt,
            "flux_seed": 42,
            "min_volume_threshold": 0.001
        }
        
        self.update_state(command_data)
        
        self.report({'INFO'}, f"FLUX pipeline test initiated with prompt: {test_prompt[:50]}...")
        print(f"✅ FLUX pipeline test command sent to launcher")
        
        return {'FINISHED'}
    
    def update_state(self, data):
        """Update state.json with new data"""
        try:
            # Read current state
            with open(config.STATE_JSON_PATH, 'r') as f:
                state_data = json.load(f)
            
            # Update with new data
            state_data.update(data)
            
            # Write back to file
            with open(config.STATE_JSON_PATH, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            print(f"❌ Error updating state: {e}")

# Register the operators
classes = [
    CONJURE_OT_render_gesture_camera,
    CONJURE_OT_import_and_process_mesh,
    CONJURE_OT_fuse_mesh,
    CONJURE_OT_segment_selection,
    CONJURE_OT_exit_selection_mode,
    CONJURE_OT_test_flux_pipeline,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls) 