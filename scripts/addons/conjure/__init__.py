# blender/__init__.py

bl_info = {
    "name": "CONJURE",
    "author": "CONJURE Team",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > UI > CONJURE",
    "description": "Core addon for the CONJURE gesture-based modeling experience.",
    "warning": "This addon is part of the CONJURE ecosystem and is not standalone.",
    "doc_url": "",
    "category": "3D View",
}

# Import all modules that contain Blender registration functions.
from . import operator_main
from . import panel_ui
from . import ops_io
from . import config

# A list of all modules that contain register/unregister functions.
# The order is critical. Operators must be registered before UI panels that use them.
modules = [
    config,
    ops_io,
    operator_main,
    panel_ui,
]

def register():
    """
    This function is called by Blender when the addon is enabled.
    It iterates through our modules list and calls the register() function in each.
    """
    print("--- Registering CONJURE Modules ---")
    for module in modules:
        try:
            module.register()
            print(f"Registered module: {module.__name__}")
        except Exception as e:
            print(f"FAILED to register module: {module.__name__}")
            print(f"Error: {e}")
    print("--- CONJURE Addon Registration Complete ---")

def unregister():
    """
    This function is called by Blender when the addon is disabled.
    It unregisters all classes in the reverse order of registration.
    """
    print("--- Unregistering CONJURE Modules ---")
    for module in reversed(modules):
        try:
            module.unregister()
            print(f"Unregistered module: {module.__name__}")
        except Exception as e:
            print(f"FAILED to unregister module: {module.__name__}")
            print(f"Error: {e}")
    print("--- CONJURE Addon Unregistration Complete ---")

if __name__ == "__main__":
    register() 