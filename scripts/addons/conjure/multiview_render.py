bl_info = {
    "name": "One-Click Multiview (Auto-Fit & Render)",
    "author": "ChatGPT",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > N-panel > Multiview",
    "description": "Creates front/right/back/left cameras around selected object, auto-fits frame (ortho or persp), and renders all views.",
    "category": "Render",
}

import bpy
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import (
    StringProperty, BoolProperty, EnumProperty, FloatProperty,
    IntProperty, PointerProperty
)
from mathutils import Vector
from math import tan
import os


# ---------------------------
# Utilities
# ---------------------------

def depsgraph(context=None):
    return (context or bpy.context).evaluated_depsgraph_get()

def get_bbox_world(obj, context=None):
    """
    Return (bbox_corners_world:list[Vector], center_world:Vector, radius:float)
    BBox includes modifiers by evaluating the object.
    """
    dg = depsgraph(context)
    obj_eval = obj.evaluated_get(dg)
    corners_local = None
    mesh_tmp = None
    try:
        mesh_tmp = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
        corners_local = [Vector(c) for c in mesh_tmp.bound_box]
    except:
        # Fallback (no mesh or to_mesh failed): use object's local bound_box
        corners_local = [Vector(c) for c in obj.bound_box]
    finally:
        if mesh_tmp:
            obj_eval.to_mesh_clear()

    mw = obj_eval.matrix_world
    corners_world = [mw @ v for v in corners_local]
    center = sum(corners_world, Vector()) / 8.0
    radius = max((c - center).length for c in corners_world)
    return corners_world, center, radius

def ensure_collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(coll)
    return coll

def clear_collection(coll):
    # remove all objects and unlink collection (non-destructive to data used elsewhere)
    for obj in list(coll.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for child in list(coll.children):
        clear_collection(child)
        coll.children.unlink(child)

def look_at(camera_obj, target):
    """
    Orient camera so its -Z axis points at target, with +Y as up.
    """
    direction = (target - camera_obj.location)
    if direction.length == 0:
        return
    camera_obj.rotation_mode = 'QUATERNION'
    camera_obj.rotation_quaternion = direction.to_track_quat('-Z', 'Y')
    camera_obj.rotation_mode = 'XYZ'

def aspect_ratio(scene):
    r = scene.render
    ax = r.resolution_x * r.pixel_aspect_x
    ay = r.resolution_y * r.pixel_aspect_y
    return ax / ay if ay != 0 else 1.0

def ortho_scale_for_bbox_in_cam(cam_obj, bbox_world, margin, scene):
    """
    Compute orthographic scale so all bbox corners fit in frame given aspect.
    Ortho scale is the *width* of the frame in world units.
    Height = width / aspect.
    """
    M = cam_obj.matrix_world.inverted()
    pts_cam = [M @ p for p in bbox_world]
    xs = [p.x for p in pts_cam]
    ys = [p.y for p in pts_cam]
    width = (max(xs) - min(xs)) * margin
    height = (max(ys) - min(ys)) * margin
    ar = aspect_ratio(scene)
    # Need scale S s.t. S >= width and S/ar >= height  => S >= max(width, height*ar)
    return max(width, height * ar)

def persp_distance_for_sphere(cam_data, radius, margin, scene):
    """
    Compute camera distance so a sphere of radius fits inside both horizontal and vertical FOVs.
    d = r / tan(fov_axis/2), choose max of horizontal/vertical.
    """
    # Ensure angles are up to date (depends on lens + sensor + resolution fit)
    # Blender provides angle_x and angle_y for perspective cameras.
    fov_x = cam_data.angle_x
    fov_y = cam_data.angle_y
    # Avoid division by zero
    fov_x = max(fov_x, 1e-6)
    fov_y = max(fov_y, 1e-6)
    d_x = radius / tan(fov_x * 0.5)
    d_y = radius / tan(fov_y * 0.5)
    return max(d_x, d_y) * margin

def create_camera(name, cam_type='ORTHO', lens_mm=50.0, clip_start=0.01, clip_end=10000.0):
    cam_data = bpy.data.cameras.new(name)
    cam_obj = bpy.data.objects.new(name, cam_data)
    cam_data.type = 'ORTHO' if cam_type == 'ORTHO' else 'PERSP'
    if cam_data.type == 'PERSP':
        cam_data.lens = lens_mm
    else:
        cam_data.ortho_scale = 1.0
    cam_data.clip_start = clip_start
    cam_data.clip_end = clip_end
    bpy.context.collection.objects.link(cam_obj)
    return cam_obj

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"[Multiview] Could not create directory {path}: {e}")

# ---------------------------
# Properties
# ---------------------------

class MVProps(PropertyGroup):
    output_dir: StringProperty(
        name="Output Folder",
        subtype='DIR_PATH',
        default="//multiview/"
    )
    camera_type: EnumProperty(
        name="Camera Type",
        items=[
            ('ORTHO', "Orthographic (recommended)", ""),
            ('PERSP', "Perspective", ""),
        ],
        default='ORTHO'
    )
    lens_mm: FloatProperty(
        name="Lens (mm, persp)",
        default=50.0, min=1.0, max=300.0
    )
    margin: FloatProperty(
        name="Margin",
        description="Frame slack so object is fully contained",
        default=1.10, min=1.0, max=2.0
    )
    res_x: IntProperty(name="Width", default=1024, min=16, max=16384)
    res_y: IntProperty(name="Height", default=1024, min=16, max=16384)
    transparent: BoolProperty(
        name="Transparent BG",
        default=True
    )
    overwrite_collection: BoolProperty(
        name="Overwrite Cameras",
        description="Replace any existing multiview cameras for this object",
        default=True
    )
    keep_cameras: BoolProperty(
        name="Keep Cameras",
        description="Keep created cameras in scene after rendering",
        default=True
    )

# ---------------------------
# Operator
# ---------------------------

class OBJECT_OT_generate_multiview(Operator):
    bl_idname = "object.generate_multiview_renders"
    bl_label = "Generate & Render Multiview"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object selected.")
            return {'CANCELLED'}

        scene = context.scene
        props = scene.mv_props

        # Compute bbox (with modifiers), center, and radius
        bbox_world, center, radius = get_bbox_world(obj, context)
        if radius <= 0:
            self.report({'ERROR'}, "Object bounds are degenerate.")
            return {'CANCELLED'}

        # Prepare collection
        coll_name = f"{obj.name}_Multiview"
        coll = bpy.data.collections.get(coll_name)
        if coll and props.overwrite_collection:
            clear_collection(coll)
        coll = ensure_collection(coll_name)

        # Camera view directions (unit vectors of camera forward, i.e., where camera looks)
        # Camera will be placed opposite to this direction from the center.
        views = {
            "front": Vector((0, 1, 0)),   # camera at -Y looking +Y
            "right": Vector((-1, 0, 0)),  # camera at +X looking -X
            "back":  Vector((0, -1, 0)),  # camera at +Y looking -Y
            "left":  Vector((1, 0, 0)),   # camera at -X looking +X
        }

        # Backup render settings
        r = scene.render
        orig_camera = scene.camera
        orig_filepath = r.filepath
        orig_res_x, orig_res_y = r.resolution_x, r.resolution_y
        orig_transp = scene.render.film_transparent
        orig_format = r.image_settings.file_format

        # Apply requested render settings
        r.resolution_x = props.res_x
        r.resolution_y = props.res_y
        scene.render.film_transparent = props.transparent
        r.image_settings.file_format = 'PNG'

        outdir = bpy.path.abspath(props.output_dir)
        ensure_dir(outdir)

        created_cams = []
        base_clip_start = max(0.001, radius * 0.001)
        base_clip_end   = radius * 1000.0

        for label, look_dir in views.items():
            cam_name = f"{obj.name}_cam_{label}"
            cam_obj = create_camera(
                cam_name,
                cam_type=props.camera_type,
                lens_mm=props.lens_mm,
                clip_start=base_clip_start,
                clip_end=base_clip_end
            )
            created_cams.append(cam_obj)
            if cam_obj.name not in coll.objects:
                coll.objects.link(cam_obj)
            # Remove from root collection if also linked there
            try:
                bpy.context.scene.collection.objects.unlink(cam_obj)
            except Exception:
                pass

            # Position camera
            if cam_obj.data.type == 'PERSP':
                # Distance needed for sphere fit
                d = persp_distance_for_sphere(cam_obj.data, radius, props.margin, scene)
                cam_obj.location = center - look_dir.normalized() * d
                look_at(cam_obj, center)

            else:  # ORTHO
                # Place at a sensible distance (distance doesn't affect framing in ortho but affects clipping)
                d = radius * 3.0
                cam_obj.location = center - look_dir.normalized() * d
                look_at(cam_obj, center)
                # Compute ortho scale to fit bbox
                scale = ortho_scale_for_bbox_in_cam(cam_obj, bbox_world, props.margin, scene)
                cam_obj.data.ortho_scale = scale

            # Render
            scene.camera = cam_obj
            filename = f"{obj.name}_{label}.png"
            r.filepath = os.path.join(outdir, filename)
            bpy.ops.render.render(write_still=True, use_viewport=False)

        # Restore render settings
        r.filepath = orig_filepath
        r.resolution_x, r.resolution_y = orig_res_x, orig_res_y
        scene.render.film_transparent = orig_transp
        r.image_settings.file_format = orig_format
        scene.camera = orig_camera

        if not props.keep_cameras:
            # Clean up cameras & collection
            for cam in created_cams:
                try:
                    bpy.data.objects.remove(cam, do_unlink=True)
                except Exception:
                    pass
            try:
                # If empty, remove the collection
                if coll and not coll.objects and not coll.children:
                    bpy.data.collections.remove(coll)
            except Exception:
                pass

        self.report({'INFO'}, f"Multiview renders saved to: {outdir}")
        return {'FINISHED'}


# ---------------------------
# UI Panel
# ---------------------------

class VIEW3D_PT_multiview(Panel):
    bl_label = "Multiview"
    bl_category = "Multiview"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        props = context.scene.mv_props

        col = layout.column(align=True)
        col.prop(props, "output_dir")
        col.prop(props, "camera_type")
        if props.camera_type == 'PERSP':
            col.prop(props, "lens_mm")
        col.prop(props, "margin")
        col.separator()
        col.prop(props, "res_x")
        col.prop(props, "res_y")
        col.prop(props, "transparent")
        col.separator()
        col.prop(props, "overwrite_collection")
        col.prop(props, "keep_cameras")
        col.separator()
        col.operator(OBJECT_OT_generate_multiview.bl_idname, icon='RENDER_STILL')


# ---------------------------
# Registration
# ---------------------------

classes = (
    MVProps,
    OBJECT_OT_generate_multiview,
    VIEW3D_PT_multiview,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.mv_props = PointerProperty(type=MVProps)

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    if hasattr(bpy.types.Scene, "mv_props"):
        del bpy.types.Scene.mv_props

if __name__ == "__main__":
    register()