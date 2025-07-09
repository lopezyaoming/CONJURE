# blender/__init__.py

import bpy
from .ops_agent import CONJURE_OT_send_to_agent
from .operator_main import ConjureFingertipOperator
from .ops_io import CONJURE_OT_generate_concepts, CONJURE_OT_select_concept, CONJURE_OT_import_model
from .ops_primitives import CONJURE_OT_spawn_primitive
from .panel_ui import CONJURE_PT_ui_panel, CONJURE_PG_settings
from .startup import register_properties, unregister_properties

bl_info = {
    "name": "CONJURE",
    "author": "CONJURE Team",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > CONJURE",
    "description": "Main addon for CONJURE application",
    "category": "3D View",
}

CLASSES = [
    ConjureFingertipOperator,
    CONJURE_PT_ui_panel,
    CONJURE_PG_settings,
    CONJURE_OT_generate_concepts,
    CONJURE_OT_select_concept,
    CONJURE_OT_import_model,
    CONJURE_OT_send_to_agent,
    CONJURE_OT_spawn_primitive,
]

def register():
    register_properties()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.conjure_settings = bpy.props.PointerProperty(type=CONJURE_PG_settings)

def unregister():
    del bpy.types.Scene.conjure_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    unregister_properties()

if __name__ == "__main__":
    register() 