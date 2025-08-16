"""
Test script for CONJURE UI components
Tests individual components and integration
"""

import sys
import json
import time
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_data_generator():
    """Test the UI data generator"""
    print("Testing UI Data Generator...")
    
    try:
        from ui_data_generator import UIDataGenerator
        
        generator = UIDataGenerator()
        ui_data = generator.generate_ui_json()
        
        print(f"✓ Generated UI data successfully")
        print(f"  - Conversation messages: {len(ui_data.conversation)}")
        print(f"  - Current command: {ui_data.current_command.command}")
        print(f"  - Brush command: {ui_data.brush_info.active_command}")
        print(f"  - Workflow active: {ui_data.workflow_progress.active}")
        
        # Save to file
        generator.save_ui_data(ui_data)
        print("✓ Saved UI data to file")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing data generator: {e}")
        return False

def test_main_ui():
    """Test the main UI window"""
    print("\nTesting Main UI...")
    
    try:
        from conjure_ui import ConjureUI
        
        app = ConjureUI(sys.argv)
        print("✓ Main UI created successfully")
        
        # Show window briefly
        app.main_window.show()
        QTimer.singleShot(2000, app.quit)  # Close after 2 seconds
        
        app.exec_()
        print("✓ Main UI test completed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing main UI: {e}")
        return False

def test_workflow_overlay():
    """Test the workflow overlay"""
    print("\nTesting Workflow Overlay...")
    
    try:
        from workflow_overlay import WorkflowOverlayManager
        
        if not QApplication.instance():
            app = QApplication(sys.argv)
        
        manager = WorkflowOverlayManager()
        print("✓ Workflow overlay manager created")
        
        # Show overlay briefly
        manager.show_overlay()
        print("✓ Workflow overlay shown")
        
        QTimer.singleShot(3000, manager.hide_overlay)  # Hide after 3 seconds
        QTimer.singleShot(4000, QApplication.instance().quit)
        
        QApplication.instance().exec_()
        print("✓ Workflow overlay test completed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing workflow overlay: {e}")
        return False

def test_integration():
    """Test full system integration"""
    print("\nTesting System Integration...")
    
    try:
        from conjure_ui_launcher import ConjureUISystem
        
        system = ConjureUISystem()
        print("✓ UI system created")
        
        # Initialize without running
        system.initialize()
        print("✓ System initialized")
        
        # Test data generation
        ui_data = system.data_generator.generate_ui_json()
        system.data_generator.save_ui_data(ui_data)
        print("✓ Data generation works")
        
        # Test workflow monitoring setup
        system.setup_workflow_monitoring()
        print("✓ Workflow monitoring setup")
        
        print("✓ Integration test completed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing integration: {e}")
        return False

def create_test_data():
    """Create test data files for UI testing"""
    print("\nCreating test data...")
    
    # Create test directories
    agent_dir = Path(__file__).parent
    project_root = agent_dir.parent
    data_dir = project_root / "data" / "input"
    
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Test state.json
    test_state = {
        "app_status": "running",
        "hand_tracker_status": "running",
        "blender_status": "running",
        "command": "generate_flux_mesh",
        "flux_pipeline_request": {
            "prompt": "test alien head"
        },
        "current_phase": "II",
        "primitive_type": "Sphere"
    }
    
    with open(data_dir / "state.json", 'w') as f:
        json.dump(test_state, f, indent=2)
    
    # Test fingertips.json
    test_fingertips = {
        "command": "deform",
        "left_hand": None,
        "right_hand": {
            "fingertips": [
                {"x": 0.5, "y": 0.5, "z": 0.0}
            ]
        },
        "scale_axis": "XYZ"
    }
    
    with open(data_dir / "fingertips.json", 'w') as f:
        json.dump(test_fingertips, f, indent=2)
    
    # Test transcript
    test_transcript = """=== CONJURE TRANSCRIPT DEBUG LOG ===
[14:30:15] [AGENT_TURN] MESSAGE: Welcome to Conjure, what do you want to create today?
USER (Whisper): I want to create an alien head
[14:30:20] [USER_TURN] MESSAGE: I want to create an alien head
[14:30:25] [AGENT_TURN] MESSAGE: Perfect! Let me generate that for you. Initiating mesh generation...
"""
    
    with open(project_root / "transcript_debug.txt", 'w') as f:
        f.write(test_transcript)
    
    print("✓ Test data created")

def run_all_tests():
    """Run all tests"""
    print("CONJURE UI Test Suite")
    print("=" * 50)
    
    # Create test data first
    create_test_data()
    
    tests = [
        ("Data Generator", test_data_generator),
        ("Main UI", test_main_ui),
        ("Workflow Overlay", test_workflow_overlay),
        ("Integration", test_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * len(test_name))
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("TEST RESULTS:")
    print("=" * 50)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
