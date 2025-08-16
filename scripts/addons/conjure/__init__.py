bl_info = {
    "name": "CONJURE",
    "author": "MS Architectural Technologies Thesis",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > UI > CONJURE",
    "description": "AI-powered, gesture-based 3D modeling platform",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

# Load all the sub-modules
if "bpy" in locals():
    import importlib
    importlib.reload(config)
    importlib.reload(operator_main)
    importlib.reload(panel_ui)
    importlib.reload(ops_io)
    importlib.reload(ops_phase1)  # New Phase 1 operators
    importlib.reload(conjure_workspace)  # New workspace setup
else:
    from . import config
    from . import operator_main
    from . import panel_ui
    from . import ops_io
    from . import ops_phase1  # New Phase 1 operators
    from . import conjure_workspace  # New workspace setup

import bpy

def register():
    print("🚀 Registering CONJURE addon...")
    
    # Register all operator classes
    operator_main.register()
    panel_ui.register()
    ops_io.register()
    ops_phase1.register()  # Register Phase 1 operators
    conjure_workspace.register()  # Register workspace setup
    
    print("✅ CONJURE addon registered successfully!")

def unregister():
    print("🛑 Unregistering CONJURE addon...")
    
    # Unregister all operator classes in reverse order
    conjure_workspace.unregister()  # Unregister workspace setup
    ops_phase1.unregister()  # Unregister Phase 1 operators
    ops_io.unregister()
    panel_ui.unregister()
    operator_main.unregister()
    
    print("👋 CONJURE addon unregistered successfully!")

if __name__ == "__main__":
    register() 