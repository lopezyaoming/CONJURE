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

# A list of all modules that contain register/unregister functions.
# The order can be important, especially for unregistering.
modules = [
    operator_main,
    panel_ui,
]

def register():
    """
    This function is called by Blender when the addon is enabled.
    It iterates through our modules list and calls the register() function in each.
    """
    for module in modules:
        module.register()
    print("CONJURE Addon Registered.")

def unregister():
    """
    This function is called by Blender when the addon is disabled.
    It unregisters all classes in the reverse order of registration.
    """
    for module in reversed(modules):
        module.unregister()
    print("CONJURE Addon Unregistered.")

if __name__ == "__main__":
    register() 