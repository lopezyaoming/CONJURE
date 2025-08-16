"""
CONJURE Workspace Setup
Automatically creates a new window and configures the viewport for CONJURE
"""

import bpy
import bmesh

def start_conjure_gesture_modeling():
    """Auto-start the CONJURE gesture modeling with proper error handling"""
    try:
        print("🚀 Auto-starting CONJURE gesture modeling...")
        
        # Check if CONJURE is already running
        wm = bpy.context.window_manager
        if not hasattr(wm, 'conjure_is_running') or not wm.conjure_is_running:
            # Start the main CONJURE operator
            bpy.ops.conjure.fingertip_operator()
            print("✅ CONJURE gesture modeling started automatically!")
        else:
            print("ℹ️ CONJURE gesture modeling already running")
            
    except Exception as start_error:
        print(f"⚠️ Could not auto-start CONJURE: {start_error}")
        # Try again in 5 seconds if it failed
        bpy.app.timers.register(start_conjure_gesture_modeling, first_interval=5.0)
    
    # Return None to unregister the timer (one-time execution)
    return None

def setup_conjure_workspace():
    """Set up the CONJURE workspace with optimal settings"""
    try:
        print("🎨 Setting up CONJURE workspace...")
        
        # Count existing windows
        initial_windows = len(bpy.context.window_manager.windows)
        print(f"📊 Initial window count: {initial_windows}")
        
        # 1. Create a new window for CONJURE
        original_window = bpy.context.window
        
        # Try to create new window with safer approach
        try:
            # Ensure we have a valid context first
            if bpy.context.window_manager and bpy.context.window:
                # Method 1: Direct operator call (safer during startup)
                bpy.ops.wm.window_new()
            else:
                print("⚠️ Invalid context for window creation")
        except Exception as e:
            print(f"⚠️ Could not create new window: {e}")
            print("   Continuing with single window setup...")
        
        # Check if window was created
        final_windows = len(bpy.context.window_manager.windows)
        print(f"📊 Final window count: {final_windows}")
        
        # Get the new window (it becomes the active window)
        new_window = None
        for window in bpy.context.window_manager.windows:
            if window != original_window:
                new_window = window
                break
        
        if not new_window:
            print("⚠️ Could not create new window, configuring current window instead")
            new_window = bpy.context.window
        else:
            print("✅ Successfully created new window!")
        
        screen = new_window.screen
        
        # 2. Set the window title to identify it as CONJURE
        screen.name = "CONJURE Workspace"
        
        # 3. Find the 3D viewport area
        area_3d = None
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area_3d = area
                break
        
        if area_3d:
            # Get the 3D viewport space
            space_3d = area_3d.spaces.active
            
            # 4. Set viewport shading to RENDERED
            space_3d.shading.type = 'RENDERED'
            print("✅ Set viewport shading to RENDERED")
            
            # 5. Disable overlays
            space_3d.overlay.show_overlays = False
            print("✅ Disabled viewport overlays")
            
            # 6. Additional viewport optimizations
            space_3d.overlay.show_extras = False
            space_3d.overlay.show_floor = True  # Keep floor for reference
            space_3d.overlay.show_axis_x = False
            space_3d.overlay.show_axis_y = False
            space_3d.overlay.show_axis_z = False
            space_3d.overlay.show_cursor = False
            space_3d.overlay.show_outline_selected = False
            space_3d.overlay.show_object_origins = False
            
            # 7. Set clean viewport settings for maximum minimalism
            space_3d.show_gizmo = False  # Hide gizmos
            space_3d.show_region_header = False  # Hide header for cleaner look
            space_3d.show_region_toolbar = False  # Hide toolbar
            space_3d.show_region_ui = False  # Hide properties panel
            space_3d.show_region_tool_header = False  # Hide tool header
            
            print("✅ Configured viewport for minimal, clean display")
            
            # 8. FIRST: Lock viewport to GestureCamera for finger parallax control (BEFORE fullscreen)
            print("📷 Locking viewport to GestureCamera for finger parallax control...")
            
            try:
                # Find the GestureCamera
                gesture_camera = bpy.data.objects.get("GestureCamera")
                if not gesture_camera:
                    print("⚠️ GestureCamera not found, creating it...")
                    # Create GestureCamera if it doesn't exist
                    with bpy.context.temp_override(window=new_window, area=area_3d):
                        bpy.ops.object.camera_add(location=(0, -7, 4))
                        gesture_camera = bpy.context.active_object
                        gesture_camera.name = "GestureCamera"
                        
                        # Set camera properties for optimal finger tracking
                        gesture_camera.data.lens = 50  # Standard lens
                        gesture_camera.rotation_euler = (1.1, 0, 0)  # Slight downward angle
                        print("✅ Created GestureCamera")
                
                # Set the view to camera mode and lock to GestureCamera
                if space_3d.region_3d:
                    space_3d.region_3d.view_perspective = 'CAMERA'
                    bpy.context.scene.camera = gesture_camera
                    print("✅ Viewport locked to GestureCamera view")
                else:
                    print("⚠️ Could not access region_3d for camera lock")
                            
            except Exception as camera_error:
                print(f"⚠️ Error setting up GestureCamera: {camera_error}")
                print("   Continuing with default viewport setup...")
            
            # 9. THEN: Make the 3D viewport area fullscreen (AFTER camera lock)
            try:
                # Override context to the new window and 3D area
                with bpy.context.temp_override(window=new_window, area=area_3d):
                    bpy.ops.screen.screen_full_area()
                print("✅ Made 3D viewport fullscreen")
            except Exception as fullscreen_error:
                print(f"⚠️ Could not make viewport fullscreen: {fullscreen_error}")
                # Try alternative method - maximize the area
                try:
                    # First, try to join areas to make this one larger
                    original_area_count = len(screen.areas)
                    if original_area_count > 1:
                        # There are other areas, try to maximize this one
                        with bpy.context.temp_override(window=new_window, area=area_3d, screen=screen):
                            # This will make the current area take up more space
                            for other_area in screen.areas:
                                if other_area != area_3d and other_area.type != 'VIEW_3D':
                                    try:
                                        # Try to minimize other areas
                                        other_area.type = 'EMPTY'
                                        break
                                    except:
                                        pass
                        print("✅ Maximized 3D viewport by minimizing other areas")
                except Exception as alt_error:
                    print(f"⚠️ Alternative fullscreen method also failed: {alt_error}")
                    print("   Continuing with regular viewport...")
            
            # 10. FINALLY: Make the entire Blender window fullscreen
            try:
                with bpy.context.temp_override(window=new_window):
                    bpy.ops.wm.window_fullscreen_toggle()
                print("✅ Made Blender window fullscreen")
            except Exception as window_fullscreen_error:
                print(f"⚠️ Could not make window fullscreen: {window_fullscreen_error}")
                print("   Viewport will remain in windowed mode")
            
            # 11. Verify camera lock is still active after fullscreen operations
            try:
                current_camera = bpy.context.scene.camera
                if current_camera and current_camera.name == "GestureCamera":
                    print("✅ GestureCamera lock verified after fullscreen setup")
                else:
                    print("⚠️ GestureCamera lock may have been lost during fullscreen setup")
                    # Try to re-establish the lock
                    gesture_camera = bpy.data.objects.get("GestureCamera")
                    if gesture_camera:
                        bpy.context.scene.camera = gesture_camera
                        print("✅ Re-established GestureCamera lock")
            except Exception as verify_error:
                print(f"⚠️ Could not verify camera lock: {verify_error}")
            
        else:
            print("⚠️ Could not find 3D viewport area")
        
        # 9. Clear default scene objects (except camera and light for rendering)
        if bpy.context.mode == 'OBJECT':
            # Delete default cube if it exists
            if "Cube" in bpy.data.objects:
                bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)
                print("✅ Removed default cube")
        
        # 10. Set up optimal render settings for real-time preview
        scene = bpy.context.scene
        # Use the correct EEVEE engine name for Blender 4.x
        scene.render.engine = 'BLENDER_EEVEE_NEXT'  # Fast rendering engine
        
        # Set up EEVEE settings with compatibility check
        if hasattr(scene, 'eevee'):
            if hasattr(scene.eevee, 'use_bloom'):
                scene.eevee.use_bloom = True
            if hasattr(scene.eevee, 'use_ssr'):
                scene.eevee.use_ssr = True  # Screen space reflections
            if hasattr(scene.eevee, 'use_gtao'):
                scene.eevee.use_gtao = True  # Ambient occlusion
        
        print("✅ CONJURE workspace setup complete!")
        
    except Exception as e:
        print(f"❌ Error setting up CONJURE workspace: {e}")
    
    # Always schedule auto-start of CONJURE gesture modeling (even if workspace setup had issues)
    print("⏰ Scheduling auto-start of CONJURE gesture modeling...")
    bpy.app.timers.register(start_conjure_gesture_modeling, first_interval=5.0)

def setup_conjure_scene():
    """Set up the scene with optimal settings for CONJURE"""
    try:
        scene = bpy.context.scene
        
        # Set up world lighting
        world = bpy.data.worlds.get("World")
        if world and world.use_nodes:
            # Set up a clean HDRI environment
            bg_node = world.node_tree.nodes.get("Background")
            if bg_node:
                bg_node.inputs["Strength"].default_value = 1.0
                # Set a neutral gray background
                bg_node.inputs["Color"].default_value = (0.05, 0.05, 0.05, 1.0)
        
        # Ensure we have good lighting
        if "Light" in bpy.data.objects:
            light = bpy.data.objects["Light"]
            light.data.energy = 10.0  # Increase light energy
            light.location = (4, 4, 5)  # Good position for lighting
        
        print("✅ CONJURE scene setup complete!")
        
    except Exception as e:
        print(f"❌ Error setting up CONJURE scene: {e}")

def register():
    """Register the workspace setup"""
    # Set up the workspace when the addon is registered
    # Use a longer delay to ensure Blender is fully loaded
    bpy.app.timers.register(setup_conjure_workspace, first_interval=3.0)
    bpy.app.timers.register(setup_conjure_scene, first_interval=3.5)

def unregister():
    """Unregister workspace setup"""
    pass
