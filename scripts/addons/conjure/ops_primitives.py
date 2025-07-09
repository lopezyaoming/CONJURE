import bpy

class CONJURE_OT_spawn_primitive(bpy.types.Operator):
    """Unhides a primitive from the PRIMITIVES collection and renames it"""
    bl_idname = "conjure.spawn_primitive"
    bl_label = "Spawn Primitive"
    bl_options = {'REGISTER', 'UNDO'}

    primitive_type: bpy.props.StringProperty()

    def execute(self, context):
        # 1. Find and delete the existing 'Mesh' object
        if "Mesh" in bpy.data.objects:
            mesh_to_delete = bpy.data.objects["Mesh"]
            bpy.data.objects.remove(mesh_to_delete, do_unlink=True)
            self.report({'INFO'}, "Removed existing 'Mesh' object.")

        # 2. Find the 'PRIMITIVES' collection
        primitives_collection = bpy.data.collections.get("PRIMITIVES")
        if not primitives_collection:
            self.report({'ERROR'}, "Collection 'PRIMITIVES' not found. Please check scene setup.")
            return {'CANCELLED'}

        # 3. Find the target primitive object within the collection
        target_primitive = None
        for obj in primitives_collection.objects:
            if obj.name.lower() == self.primitive_type.lower():
                target_primitive = obj
                break
        
        if not target_primitive:
            self.report({'ERROR'}, f"Primitive '{self.primitive_type}' not found in 'PRIMITIVES' collection.")
            return {'CANCELLED'}

        # 4. Unhide the primitive, link it to the main scene, and rename it
        self.report({'INFO'}, f"Spawning primitive: {target_primitive.name}")

        try:
            # Unhide from viewport
            target_primitive.hide_set(False)
            # Unhide from render
            target_primitive.hide_render = False

            # Link it to the scene's main collection if not already there
            if target_primitive.name not in context.scene.collection.objects:
                 context.scene.collection.objects.link(target_primitive)
            
            # Unlink from the primitives collection so it's a standalone object
            primitives_collection.objects.unlink(target_primitive)

        except RuntimeError as e:
            self.report({'WARNING'}, f"Could not move object out of collection, might already be in scene: {e}")


        # 5. Rename to 'Mesh'
        target_primitive.name = "Mesh"
        
        # 6. Set location to 3D cursor
        target_primitive.location = context.scene.cursor.location
        
        # 7. Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        target_primitive.select_set(True)
        context.view_layer.objects.active = target_primitive

        self.report({'INFO'}, f"Successfully spawned '{self.primitive_type}' as 'Mesh' at cursor location.")

        return {'FINISHED'} 