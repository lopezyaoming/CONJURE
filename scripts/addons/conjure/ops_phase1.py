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
from .auto_replace_fit import auto_replace_fit_conjure

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
    """Import and process mesh from generation results (PartPacker local or RunComfy cloud)
    - HuggingFace mode: Handles pre-segmented meshes from PartPacker
    - Cloud mode: Separates single mesh from RunComfy into loose parts for segmentation"""
    bl_idname = "conjure.import_and_process_mesh"
    bl_label = "Import and Process Mesh"
    
    def execute(self, context):
        print("📦 Starting mesh import and processing (supports both local and cloud generation)...")
        
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
            
            # Detect generation mode based on file path
            if "partpacker_result" in str(full_path):
                print("🏠 HUGGINGFACE MODE: PartPacker-generated mesh (pre-segmented)")
            elif "genMesh" in str(full_path):
                print("☁️ CLOUD MODE: RunComfy-generated mesh (single object - will be separated)") 
            else:
                print("❓ UNKNOWN MODE: Generic GLB mesh")
            
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
            
            # Handle cloud mode: separate single mesh into loose parts
            is_cloud_mode = "genMesh" in str(full_path)
            
            if is_cloud_mode:
                print("☁️ CLOUD MODE detected")
                if len(mesh_objects) == 1:
                    print("🔧 Single mesh found - separating into loose parts...")
                    separated_objects = self.separate_mesh_by_loose_parts(mesh_objects[0])
                    if separated_objects and len(separated_objects) > 1:
                        print(f"✅ Successfully separated into {len(separated_objects)} parts")
                        mesh_objects = separated_objects
                    else:
                        print("⚠️ Separation did not create multiple parts - keeping as single mesh")
                else:
                    print(f"📊 Found {len(mesh_objects)} objects - no separation needed")
            else:
                print("🏠 HUGGINGFACE MODE: Using pre-segmented meshes from PartPacker")
            
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
            
            # Use auto_replace_fit to properly align new meshes with existing "Mesh" object
            print("🎯 Aligning new meshes with existing 'Mesh' object using auto_replace_fit...")
            self.align_meshes_with_existing(valid_meshes)
            
            print(f"✅ Successfully imported and processed {len(valid_meshes)} mesh segments")
            
            # Setup materials and apply default material to all segments
            print("🎨 Setting up materials...")
            self.setup_selection_materials()
            self.apply_default_materials_to_segments(valid_meshes)
            
            # Auto-launch segment selection immediately after successful import
            print("🎯 Auto-launching segment selection mode...")
            try:
                bpy.ops.conjure.segment_selection()
                print("✅ Segment selection mode auto-launched successfully!")
            except Exception as e:
                print(f"⚠️ Failed to auto-launch segment selection: {e}")
                # Fallback to manual mode entry
                self.enter_selection_mode()
            
            print("🎉 Mesh import and processing completed successfully!")
            return {'FINISHED'}
            
        except Exception as e:
            print(f"💥 CRITICAL ERROR in mesh import: {e}")
            import traceback
            print(f"🔍 Full error traceback:\n{traceback.format_exc()}")
            self.report({'ERROR'}, f"Critical error during import: {e}")
            return {'CANCELLED'}
    
    def separate_mesh_by_loose_parts(self, mesh_obj):
        """
        Separate a single mesh object into multiple objects based on loose parts.
        This is used for cloud-generated meshes that come as a single merged object.
        """
        try:
            print(f"🔧 Separating mesh: {mesh_obj.name}")
            
            # Ensure the mesh is selected and active
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            
            # Store the original name for numbering
            original_name = mesh_obj.name
            
            # Switch to Edit Mode
            bpy.ops.object.mode_set(mode='EDIT')
            
            # Select all geometry
            bpy.ops.mesh.select_all(action='SELECT')
            
            # Check if mesh has disconnected parts before separation
            import bmesh
            bm = bmesh.from_edit_mesh(mesh_obj.data)
            
            # Count islands (disconnected parts)
            islands = []
            faces_visited = set()
            
            for face in bm.faces:
                if face.index not in faces_visited:
                    island = []
                    stack = [face]
                    while stack:
                        current_face = stack.pop()
                        if current_face.index in faces_visited:
                            continue
                        faces_visited.add(current_face.index)
                        island.append(current_face)
                        
                        for edge in current_face.edges:
                            for linked_face in edge.link_faces:
                                if linked_face.index not in faces_visited:
                                    stack.append(linked_face)
                    
                    if island:
                        islands.append(island)
            
            print(f"🔍 Detected {len(islands)} disconnected parts in mesh")
            
            if len(islands) <= 1:
                print("⚠️ Mesh appears to be a single connected component - separation may not be needed")
            
            # Separate by loose parts
            print("🔨 Executing separate by loose parts...")
            result = bpy.ops.mesh.separate(type='LOOSE')
            
            if result != {'FINISHED'}:
                print(f"⚠️ Separation operation returned: {result}")
            
            # Switch back to Object Mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Get all selected objects (these are the separated parts)
            separated_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
            
            print(f"📊 Separation resulted in {len(separated_objects)} objects")
            
            # Rename the separated objects to follow our naming convention
            for i, obj in enumerate(separated_objects):
                # Name them as seg_0, seg_1, etc. like PartPacker does
                obj.name = f"seg_{i}"
                print(f"🏷️ Renamed {obj.name}")
            
            # Deselect all objects
            bpy.ops.object.select_all(action='DESELECT')
            
            return separated_objects
            
        except Exception as e:
            print(f"❌ Error during mesh separation: {e}")
            import traceback
            print(f"🔍 Separation error traceback:\n{traceback.format_exc()}")
            
            # Make sure we're back in Object Mode
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except:
                pass
                
            return []
    
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
    
    def align_meshes_with_existing(self, new_mesh_objects):
        """
        Use auto_replace_fit to align new imported meshes with the existing 'Mesh' object.
        This treats all new meshes as a single unit and aligns them to replace the old mesh.
        """
        try:
            # Find the existing "Mesh" object (target)
            existing_mesh = bpy.data.objects.get("Mesh")
            if not existing_mesh:
                print("⚠️ No existing 'Mesh' object found - falling back to origin centering")
                self.center_meshes_at_origin(new_mesh_objects)
                return
            
            if existing_mesh.type != 'MESH':
                print("⚠️ Existing 'Mesh' object is not a mesh - falling back to origin centering") 
                self.center_meshes_at_origin(new_mesh_objects)
                return
            
            # Filter to only mesh objects
            valid_meshes = [obj for obj in new_mesh_objects if obj.type == 'MESH']
            if not valid_meshes:
                print("❌ No valid mesh objects to align")
                return
            
            print(f"🎯 Aligning {len(valid_meshes)} new meshes to existing 'Mesh' object...")
            print(f"   📍 Target: {existing_mesh.name}")
            print(f"   📦 Sources: {[obj.name for obj in valid_meshes]}")
            
            # Use auto_replace_fit_conjure to align all new meshes as a group
            transform_matrix = auto_replace_fit_conjure(
                old_mesh_obj=existing_mesh,
                new_mesh_objects=valid_meshes,
                icp_points=2000,  # Moderate point count for performance
                icp_iters=10,     # Fewer iterations for speed
                icp_trim=0.2,     # Robust trimming
                seed=42           # Consistent results
            )
            
            print("✅ Auto-replace alignment completed successfully!")
            print(f"📊 Applied transformation matrix to {len(valid_meshes)} mesh objects")
            
            # Now hide the old mesh since it's been replaced
            existing_mesh.hide_viewport = True
            existing_mesh.hide_render = True
            print(f"👁️ Hidden old mesh '{existing_mesh.name}' - replaced by new aligned meshes")
            
        except Exception as e:
            print(f"❌ Error during mesh alignment: {e}")
            import traceback
            print(f"🔍 Alignment error traceback:\n{traceback.format_exc()}")
            print("🔄 Falling back to simple origin centering...")
            self.center_meshes_at_origin(new_mesh_objects)
    
    def create_placeholder_mesh(self):
        """
        Create a reasonably-sized mesh object named 'Mesh' for proper alignment reference.
        This creates a better target for auto_replace_fit alignment.
        """
        # Remove existing Mesh if it exists
        existing_mesh = bpy.data.objects.get("Mesh")
        if existing_mesh:
            bpy.data.objects.remove(existing_mesh, do_unlink=True)
            print("🗑️ Removed existing Mesh object")
        
        # Create a properly-sized cube mesh as placeholder (2x2x2 units)
        # This provides a good reference size for alignment without being too small or large
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
        placeholder = bpy.context.active_object
        placeholder.name = "Mesh"
        placeholder.hide_viewport = True  # Hidden from viewport
        placeholder.hide_render = True   # Hidden from renders - fixes invisible box issue
        print("📍 Created placeholder 'Mesh' cube object (2x2x2 units) for alignment reference (hidden from renders)")
    
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
        
        # Recalculate mesh properties for deformation system
        self.recalculate_mesh_properties_for_deformation(target_obj)
        
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
        # NOTE: Don't set command="segment_selection" here to avoid infinite loop
        self.update_state({
            "selection_mode": "active"
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
                
                # Step 5.5: Recalculate mesh properties for deformation system
                self.recalculate_mesh_properties_for_deformation(confirmed_segment)
                
                # Step 6: Apply remesh modifier for polycount control (target: 12500 faces max)
                print("🔧 Applying remesh modifier for polycount control...")
                self.apply_remesh_modifier(confirmed_segment)
                
                # Step 7: Restore original mesh material (remove selection highlighting)
                print("🎨 Restoring original mesh material...")
                self.restore_original_material(confirmed_segment)
                
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
    
    def apply_remesh_modifier(self, mesh_obj):
        """Apply remesh modifier with smooth type and resolution 6 to control polycount"""
        try:
            # Remove any existing remesh modifiers first
            for modifier in mesh_obj.modifiers:
                if modifier.type == 'REMESH':
                    mesh_obj.modifiers.remove(modifier)
            
            # Add new remesh modifier
            remesh_modifier = mesh_obj.modifiers.new(name="RemeshPolycount", type='REMESH')
            remesh_modifier.mode = 'SMOOTH'  # Smooth remesh type
            remesh_modifier.octree_depth = 7  # Resolution level 7 for higher quality smooth remesh
            remesh_modifier.use_remove_disconnected = False  # Keep all parts
            
            # Apply the modifier
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.modifier_apply(modifier="RemeshPolycount")
            
            # Check final face count
            face_count = len(mesh_obj.data.polygons)
            print(f"✅ Remesh applied - Final face count: {face_count}")
            
            if face_count > 15000:  # Warning if still too high
                print(f"⚠️ Face count ({face_count}) is still high - consider lowering octree depth")
            elif face_count < 1000:  # Warning if too low
                print(f"⚠️ Face count ({face_count}) is very low - consider raising octree depth")
            else:
                print(f"✅ Face count ({face_count}) is within optimal range for deformation")
                
        except Exception as e:
            print(f"❌ Error applying remesh modifier: {e}")
    
    def recalculate_mesh_properties_for_deformation(self, mesh_obj):
        """Recalculate mesh properties for the deformation system"""
        try:
            # Find the active ConjureFingertipOperator instance
            operator_instance = None
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Check if operator is running by looking for modal handlers
                            if hasattr(bpy.context.window_manager, 'modal_handler_add'):
                                # Try to find the operator instance through the active operators
                                break
            
            # Calculate mesh properties directly using bmesh
            import bmesh
            import mathutils
            
            if not mesh_obj or not mesh_obj.data:
                print("⚠️ Cannot recalculate properties: invalid mesh object")
                return
                
            bm = bmesh.new()
            bm.from_mesh(mesh_obj.data)
            volume = bm.calc_volume(signed=True)
            vertex_count = len(bm.verts)
            
            # Initialize vertex velocities
            vertex_velocities = {v.index: mathutils.Vector((0,0,0)) for v in bm.verts}
            bm.free()
            
            print(f"🔧 Recalculated mesh properties for deformation:")
            print(f"   Volume: {volume}")
            print(f"   Vertices: {vertex_count}")
            
            # Store properties on the mesh object for the operator to access
            mesh_obj["_conjure_volume"] = volume
            mesh_obj["_conjure_vertex_count"] = vertex_count
            mesh_obj["_conjure_vertex_velocities"] = str(vertex_velocities)  # Store as string
            
            # Try to update the operator instance if we can find it
            # Look for the operator in the current context
            for operator in bpy.context.window_manager.operators:
                if hasattr(operator, 'bl_idname') and operator.bl_idname == 'conjure.fingertip_operator':
                    if hasattr(operator, '_initial_volume'):
                        operator._initial_volume = volume
                        operator._vertex_velocities = vertex_velocities
                        print("✅ Updated operator deformation properties")
                        break
            
        except Exception as e:
            print(f"❌ Error recalculating mesh properties: {e}")
    
    def restore_original_material(self, mesh_obj):
        """Restore the original mesh material instead of selection material"""
        try:
            # Look for the original/default material to restore
            default_mat = bpy.data.materials.get("default_material") 
            
            if default_mat:
                # Clear existing materials and apply default
                mesh_obj.data.materials.clear()
                mesh_obj.data.materials.append(default_mat)
                print("✅ Restored default_material to selected mesh")
            else:
                # If no default material, try to find a neutral material or create one
                print("⚠️ default_material not found - mesh will keep current material")
                
        except Exception as e:
            print(f"❌ Error restoring original material: {e}")
    
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