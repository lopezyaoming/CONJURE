"""
CONJURE Addon Reload Script
Run this in Blender's Python console to force reload the addon and fix caching issues
"""

import bpy
import addon_utils

def reload_conjure_addon():
    """Force reload the CONJURE addon"""
    addon_name = "conjure"
    
    print("🔄 Reloading CONJURE addon...")
    
    try:
        # Disable the addon first
        addon_utils.disable(addon_name, default_set=True)
        print("  ✅ CONJURE addon disabled")
        
        # Enable it again 
        addon_utils.enable(addon_name, default_set=True)
        print("  ✅ CONJURE addon enabled")
        
        print("🎉 CONJURE addon reloaded successfully!")
        print("✅ The AttributeError should now be fixed")
        
    except Exception as e:
        print(f"❌ Error reloading addon: {e}")
        print("💡 Try manually disabling and re-enabling the addon in Blender preferences")

def quick_test():
    """Quick test to verify the addon is working"""
    try:
        # Check if the main operator is available
        if hasattr(bpy.ops.conjure, 'fingertip_operator'):
            print("✅ Main operator available")
        else:
            print("❌ Main operator not found")
            
        # Check if Phase 1 operators are available
        phase1_ops = [
            'render_gesture_camera',
            'test_flux_pipeline', 
            'fuse_mesh',
            'segment_selection'
        ]
        
        for op_name in phase1_ops:
            if hasattr(bpy.ops.conjure, op_name):
                print(f"✅ {op_name} available")
            else:
                print(f"❌ {op_name} not found")
                
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("CONJURE ADDON RELOAD SCRIPT")
    print("=" * 50)
    
    reload_conjure_addon()
    print("\n" + "=" * 30)
    print("QUICK TEST")
    print("=" * 30)
    quick_test()
    
    print("\n🚀 Ready to test CONJURE!")
    print("   Try clicking 'Initiate CONJURE' in the 3D Viewport panel")

# Manual instructions if script fails
print("\n" + "=" * 60)
print("MANUAL RELOAD INSTRUCTIONS (if script fails):")
print("=" * 60)
print("1. Go to Edit > Preferences > Add-ons")
print("2. Search for 'CONJURE'")
print("3. Uncheck the box to disable it")
print("4. Check the box again to re-enable it")
print("5. Close preferences and try again")
print("=" * 60) 