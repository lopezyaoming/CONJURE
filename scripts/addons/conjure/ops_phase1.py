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
        
        # Wrap entire execution in try-catch to prevent crashes
        try:
            # Check if we have a mesh path in state
            try:
                with open(config.STATE_JSON_PATH, 'r') as f:
                    state_data = json.load(f)
                print("✅ State file read successfully")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"❌ Could not read state file: {e}")
                self.report({'ERROR'}, "Could not read state file")
                return {'CANCELLED'}
            
            mesh_path = state_data.get("mesh_path")
            if not mesh_path:
                print("❌ No mesh path specified in state")
                self.report({'ERROR'}, "No mesh path specified")
                return {'CANCELLED'}
            
            full_path = Path(mesh_path)
            if not full_path.exists():
                print(f"❌ Mesh file not found: {mesh_path}")
                self.report({'ERROR'}, f"Mesh file not found: {mesh_path}")
                return {'CANCELLED'}
            
            print(f"📦 Importing mesh from: {full_path}")
            print(f"📊 File size: {full_path.stat().st_size / 1024:.1f} KB")
            
            # Create placeholder "Mesh" empty to prevent console errors
            print("📍 Creating placeholder mesh...")
            self.create_placeholder_mesh()
            
            # Clear existing imported meshes (but keep Mesh placeholder)
            print("🗑️ Clearing existing segments...")
            self.clear_existing_segments()
            
            # Import the GLB file with detailed error catching
            print("📥 Starting GLB import...")
            try:
                bpy.ops.import_scene.gltf(filepath=str(full_path))
                print("✅ GLTF import completed")
            except Exception as e:
                print(f"❌ GLB import failed: {e}")
                import traceback
                print(f"🔍 Full error: {traceback.format_exc()}")
                self.report({'ERROR'}, f"Failed to import GLB: {e}")
                return {'CANCELLED'}
            
            # Process imported meshes
            print("🔍 Getting imported meshes...")
            mesh_objects = self.get_imported_meshes()
            print(f"📊 Found {len(mesh_objects)} imported mesh objects")
            
            if not mesh_objects:
                print("❌ No valid meshes found after import")
                # List all objects for debugging
                all_objects = [obj.name for obj in bpy.data.objects]
                print(f"🔍 All objects in scene: {all_objects}")
                self.report({'ERROR'}, "No valid meshes found after import")
                return {'CANCELLED'}
            
            # Filter by volume and rename
            print("🔍 Filtering meshes by volume...")
            min_volume_threshold = state_data.get("min_volume_threshold", 0.001)
            print(f"📊 Volume threshold: {min_volume_threshold}")
            
            valid_meshes = self.filter_and_rename_meshes(mesh_objects, min_volume_threshold)
            print(f"📊 {len(valid_meshes)} meshes survived volume filtering")
            
            if not valid_meshes:
                print("❌ No meshes survived volume filtering")
                self.report({'ERROR'}, "No meshes survived volume filtering")
                return {'CANCELLED'}
            
            # Center all meshes at origin
            print("📍 Centering meshes at origin...")
            self.center_meshes_at_origin(valid_meshes)
            
            print(f"✅ Successfully imported and processed {len(valid_meshes)} mesh segments")
            
            # Setup materials and apply default material to all segments
            print("🎨 Setting up materials...")
            self.setup_selection_materials()
            self.apply_default_materials_to_segments(valid_meshes)
            
            # Enter segment selection mode automatically
            print("🎯 Entering selection mode...")
            self.enter_selection_mode()
            
            print("🎉 Mesh import and processing completed successfully!")
            return {'FINISHED'}
            
        except Exception as e:
            print(f"💥 CRITICAL ERROR in mesh import: {e}")
            import traceback
            print(f"🔍 Full error traceback:\n{traceback.format_exc()}")
            self.report({'ERROR'}, f"Critical error during import: {e}")
            return {'CANCELLED'}
    
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
            print("⚠️ No mesh objects to center")
            return
        
        try:
            print(f"📍 Centering {len(mesh_objects)} meshes...")
            
            # Calculate the combined bounding box of all meshes
            min_bound = mathutils.Vector((float('inf'), float('inf'), float('inf')))
            max_bound = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))
            
            for i, obj in enumerate(mesh_objects):
                print(f"🔍 Processing mesh {i+1}: {obj.name}")
                try:
                    for vertex in obj.bound_box:
                        world_vertex = obj.matrix_world @ mathutils.Vector(vertex)
                        min_bound.x = min(min_bound.x, world_vertex.x)
                        min_bound.y = min(min_bound.y, world_vertex.y)
                        min_bound.z = min(min_bound.z, world_vertex.z)
                        max_bound.x = max(max_bound.x, world_vertex.x)
                        max_bound.y = max(max_bound.y, world_vertex.y)
                        max_bound.z = max(max_bound.z, world_vertex.z)
                except Exception as e:
                    print(f"❌ Error processing mesh {obj.name}: {e}")
                    continue
            
            # Calculate center offset
            center_offset = (min_bound + max_bound) / 2
            print(f"📊 Calculated center offset: {center_offset}")
            
            # Move all meshes to center them at origin
            for obj in mesh_objects:
                try:
                    obj.location -= center_offset
                    print(f"✅ Centered mesh: {obj.name}")
                except Exception as e:
                    print(f"❌ Error centering mesh {obj.name}: {e}")
            
            print(f"📍 Successfully centered {len(mesh_objects)} meshes at origin (offset: {center_offset})")
            
        except Exception as e:
            print(f"❌ Error in center_meshes_at_origin: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")

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
        
        # Apply default material only to segments that don't have selected material
        default_mat = bpy.data.materials.get("default_material")
        selected_mat = bpy.data.materials.get("selected_material")
        
        for obj in segment_objects:
            # Only reset material if it doesn't have the selected material
            current_mat = obj.data.materials[0] if obj.data.materials else None
            if current_mat != selected_mat:
                obj.data.materials.clear()
                if default_mat:
                    obj.data.materials.append(default_mat)
        
        # Update state to indicate we're in selection mode
        # Don't clear existing selection when re-entering selection mode
        self.update_state({
            "selection_mode": "active",
            "command": "segment_selection"  # This disables deform mode
            # Note: We don't reset selected_segment here to preserve existing selections
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
    
    # Target bounding box size for the final mesh
    target_bounding_box_size = 2.0  # 2x2x2 unit cube
    
    def execute(self, context):
        # print("🚪 Exiting segment selection mode...")
        
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
                
                # Get remaining segments (excluding the confirmed one)
                remaining_segments = [obj for obj in segment_objects if obj != confirmed_segment]
                
                # Step 1: Parent all other segments to the confirmed segment
                if remaining_segments:
                    print(f"👨‍👩‍👧‍👦 Parenting {len(remaining_segments)} segments to {confirmed_segment.name}")
                    for segment in remaining_segments:
                        segment.parent = confirmed_segment
                        segment.parent_type = 'OBJECT'
                
                # Step 2: Move confirmed segment to origin (0,0,0)
                print(f"📍 Moving {confirmed_segment.name} to origin")
                confirmed_segment.location = (0, 0, 0)
                
                # Step 3: Scale the confirmed segment to fit target bounding box
                self.scale_to_target_bounding_box(confirmed_segment)
                
                # Step 4: Remove placeholder Mesh object if it exists
                placeholder = bpy.data.objects.get("Mesh")
                if placeholder:
                    bpy.data.objects.remove(placeholder, do_unlink=True)
                    print("🗑️ Removed placeholder Mesh")
                
                # Step 5: Rename the confirmed segment to "Mesh"
                old_name = confirmed_segment.name
                confirmed_segment.name = "Mesh"
                print(f"🏷️ Renamed {old_name} to 'Mesh'")
                
                # Step 6: Keep the selected material on the main mesh
                # (It already has selected_material, so we keep it)
                print("✨ Selected segment remains highlighted for further editing")
                
                print(f"✅ Workflow complete! 'Mesh' is ready for deformation with {len(remaining_segments)} parented segments")
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
    
    def scale_to_target_bounding_box(self, obj):
        """Scale object so its bounding box fits within the target size"""
        # Calculate current bounding box
        bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        
        # Find min/max coordinates
        min_coords = [min(corner[i] for corner in bbox_corners) for i in range(3)]
        max_coords = [max(corner[i] for corner in bbox_corners) for i in range(3)]
        
        # Calculate current dimensions
        current_dimensions = [max_coords[i] - min_coords[i] for i in range(3)]
        max_current_dimension = max(current_dimensions)
        
        if max_current_dimension > 0:
            # Calculate scale factor to fit within target bounding box
            scale_factor = self.target_bounding_box_size / max_current_dimension
            
            # Apply uniform scaling
            obj.scale = (scale_factor, scale_factor, scale_factor)
            
            print(f"📏 Scaled {obj.name} by factor {scale_factor:.3f} to fit {self.target_bounding_box_size}x{self.target_bounding_box_size}x{self.target_bounding_box_size} bounding box")
        else:
            print("⚠️ Object has zero dimensions, skipping scaling")
    
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