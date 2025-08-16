"""
Simple UI Test Script
Tests the CONJURE UI components individually
"""

import sys
import os
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent
agent_dir = project_root / "Agent"
sys.path.insert(0, str(agent_dir))
os.chdir(project_root)

def test_data_generator():
    """Test data generator"""
    print("Testing Data Generator...")
    try:
        from ui_data_generator import UIDataGenerator
        
        generator = UIDataGenerator()
        ui_data = generator.generate_ui_json()
        generator.save_ui_data(ui_data)
        
        print("✓ Data generator works")
        print(f"  - Generated {len(ui_data.conversation)} conversation messages")
        print(f"  - Current command: {ui_data.current_command.command}")
        print(f"  - Active brush: {ui_data.brush_info.active_command}")
        
        return True
    except Exception as e:
        print(f"✗ Data generator error: {e}")
        return False

def test_ui_import():
    """Test UI imports"""
    print("\nTesting UI Imports...")
    try:
        from conjure_ui import ConjureUI
        from workflow_overlay import WorkflowOverlayManager
        from ui_config import UIConfig
        
        print("✓ All UI components import successfully")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_pyqt():
    """Test PyQt5 availability"""
    print("\nTesting PyQt5...")
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        
        print("✓ PyQt5 is available")
        return True
    except Exception as e:
        print(f"✗ PyQt5 error: {e}")
        return False

def main():
    """Run all tests"""
    print("CONJURE UI Simple Test")
    print("=" * 30)
    
    tests = [
        test_pyqt,
        test_data_generator,
        test_ui_import
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "=" * 30)
    success_count = sum(results)
    total_count = len(results)
    print(f"Results: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("\n🎉 All tests passed! UI system is ready to use.")
        print("\nTo start the UI:")
        print("  python start_conjure_ui.py")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
    
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
