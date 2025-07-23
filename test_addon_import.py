"""
Simple test to verify CONJURE addon import structure
Run this in Blender's Python console to test the addon imports
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
scripts_path = project_root / "scripts"
if str(scripts_path) not in sys.path:
    sys.path.append(str(scripts_path))

try:
    print("🔍 Testing CONJURE addon imports...")
    
    # Test importing the addon modules
    print("  → Testing config import...")
    from addons.conjure import config
    print("  ✅ config imported successfully")
    
    print("  → Testing operator_main import...")
    from addons.conjure import operator_main
    print("  ✅ operator_main imported successfully")
    
    print("  → Testing panel_ui import...")
    from addons.conjure import panel_ui
    print("  ✅ panel_ui imported successfully")
    
    print("  → Testing ops_io import...")
    from addons.conjure import ops_io
    print("  ✅ ops_io imported successfully")
    
    print("  → Testing ops_phase1 import...")
    from addons.conjure import ops_phase1
    print("  ✅ ops_phase1 imported successfully")
    
    print("  → Testing main addon import...")
    from addons import conjure
    print("  ✅ main addon module imported successfully")
    
    print("\n🎉 All imports successful!")
    print("✅ CONJURE addon structure is working correctly")
    
    # Test that classes exist
    print("\n🔍 Verifying operator classes...")
    
    # Check Phase 1 operators
    phase1_ops = [
        'CONJURE_OT_render_gesture_camera',
        'CONJURE_OT_import_and_process_mesh', 
        'CONJURE_OT_fuse_mesh',
        'CONJURE_OT_segment_selection',
        'CONJURE_OT_test_flux_pipeline'
    ]
    
    for op_name in phase1_ops:
        if hasattr(ops_phase1, op_name):
            print(f"  ✅ {op_name} found")
        else:
            print(f"  ❌ {op_name} missing")
    
    # Check main operators
    main_ops = [
        'ConjureFingertipOperator',
        'CONJURE_OT_stop_operator'
    ]
    
    for op_name in main_ops:
        if hasattr(operator_main, op_name):
            print(f"  ✅ {op_name} found")
        else:
            print(f"  ❌ {op_name} missing")
    
    # Check UI operators
    ui_ops = [
        'CONJURE_OT_generate_concepts',
        'CONJURE_OT_select_concept_1',
        'CONJURE_OT_select_concept_2', 
        'CONJURE_OT_select_concept_3',
        'CONJURE_OT_import_model'
    ]
    
    for op_name in ui_ops:
        if hasattr(ops_io, op_name):
            print(f"  ✅ {op_name} found")
        else:
            print(f"  ❌ {op_name} missing")
    
    print("\n🚀 Ready to test in Blender!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Check that the addon files are properly structured")
    
except AttributeError as e:
    print(f"❌ Attribute error: {e}")
    print("Check that all operators are properly defined")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

if __name__ == "__main__":
    print("Run this script in Blender's Python console to test the addon") 