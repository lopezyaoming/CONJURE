"""
Test script for CONJURE Blender workspace setup
This script tests the workspace creation directly in Blender
"""

import sys
import subprocess
from pathlib import Path

def test_blender_workspace():
    """Test the CONJURE workspace setup in Blender"""
    
    # Path to Blender executable
    blender_path = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
    project_root = Path(__file__).parent
    addon_path = project_root / "scripts" / "addons" / "conjure"
    
    # Create a test script that will run inside Blender
    test_script = """
import bpy
import sys
import os

# Add the addon path
addon_path = r"{addon_path}"
if addon_path not in sys.path:
    sys.path.append(addon_path)

# Enable the CONJURE addon
try:
    import conjure
    print("✅ CONJURE addon imported successfully")
    
    # Register the addon
    conjure.register()
    print("✅ CONJURE addon registered successfully")
    
    # Check if workspace was created
    windows = bpy.context.window_manager.windows
    print(f"📊 Number of windows: {{len(windows)}}")
    
    for i, window in enumerate(windows):
        print(f"   Window {{i+1}}: {{window.screen.name}}")
        
        # Check viewport settings for each window
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                print(f"      3D Viewport - Shading: {{space.shading.type}}, Overlays: {{space.overlay.show_overlays}}")
    
    print("✅ CONJURE workspace test completed")
    
except Exception as e:
    print(f"❌ Error testing CONJURE workspace: {{e}}")
    import traceback
    traceback.print_exc()

# Save and quit
bpy.ops.wm.save_mainfile(filepath=r"{project_root}/test_workspace.blend")
bpy.ops.wm.quit_blender()
""".format(addon_path=addon_path, project_root=project_root)
    
    # Write the test script to a temporary file
    test_script_path = project_root / "temp_test_script.py"
    with open(test_script_path, 'w') as f:
        f.write(test_script)
    
    try:
        # Run Blender with the test script
        print("🧪 Testing CONJURE workspace setup in Blender...")
        print(f"Using Blender: {blender_path}")
        print(f"Addon path: {addon_path}")
        
        result = subprocess.run([
            blender_path,
            "--background",
            "--python", str(test_script_path)
        ], capture_output=True, text=True, timeout=30)
        
        print("📄 Blender output:")
        print(result.stdout)
        
        if result.stderr:
            print("⚠️ Blender errors:")
            print(result.stderr)
        
        print(f"🏁 Blender exit code: {result.returncode}")
        
    except subprocess.TimeoutExpired:
        print("⏰ Blender test timed out")
    except Exception as e:
        print(f"❌ Error running Blender test: {e}")
    finally:
        # Clean up temp file
        if test_script_path.exists():
            test_script_path.unlink()

if __name__ == "__main__":
    test_blender_workspace()
