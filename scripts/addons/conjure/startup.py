import bpy

# The name of the module is the name of the folder containing __init__.py
ADDON_NAME = "blender"

def register_properties():
    bpy.types.Scene.conjure_user_input = bpy.props.StringProperty(
        name="Agent Input",
        description="Type your message to the agent here",
        default="",
    )
    bpy.types.WindowManager.conjure_is_running = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.conjure_should_stop = bpy.props.BoolProperty(default=False)

def unregister_properties():
    del bpy.types.Scene.conjure_user_input
    del bpy.types.WindowManager.conjure_is_running
    del bpy.types.WindowManager.conjure_should_stop

def register():
    register_properties()

def unregister():
    unregister_properties()

def main():
    """
    Ensures the CONJURE addon is enabled in Blender.
    This script is intended to be run via the --python command line argument
    when launching Blender from an external script.
    """
    if ADDON_NAME not in bpy.context.preferences.addons:
        print(f"CONJURE addon '{ADDON_NAME}' not found. Please ensure it is installed correctly.")
        return

    if not bpy.context.preferences.addons[ADDON_NAME].preferences:
        print(f"Enabling CONJURE addon: '{ADDON_NAME}'")
        bpy.ops.preferences.addon_enable(module=ADDON_NAME)
        # It's good practice to save user settings after enabling an addon via script
        # so it stays enabled on subsequent launches.
        bpy.ops.wm.save_userpref()
    else:
        print(f"CONJURE addon '{ADDON_NAME}' is already enabled.")

if __name__ == "__main__":
    main() 