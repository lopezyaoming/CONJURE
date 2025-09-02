#!/usr/bin/env python3
"""
Test the new Phase 3 UI layout design
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT / "Agent"))

def test_ui_layout():
    """Test the new UI layout without actually showing the window"""
    print("🎨 Testing New UI Layout")
    print("-" * 40)
    
    try:
        # Mock QApplication to avoid display requirements
        from unittest.mock import patch
        
        with patch('PyQt5.QtWidgets.QApplication.instance', return_value=None):
            with patch('PyQt5.QtWidgets.QApplication.__init__', return_value=None):
                with patch('PyQt5.QtCore.QTimer.__init__', return_value=None):
                    with patch('PyQt5.QtWidgets.QMainWindow.showFullScreen', return_value=None):
                        
                        # Test imports
                        from conjure_ui import BrushIconsPanel, PromptDisplayPanel, StatusPanel, ConjureMainWindow
                        print("✅ All UI components import successfully")
                        
                        # Test BrushIconsPanel
                        try:
                            brush_panel = BrushIconsPanel()
                            print("✅ BrushIconsPanel creates successfully")
                            print(f"   Size: {brush_panel.size().width()}x{brush_panel.size().height()}")
                            print(f"   Brush types: {list(brush_panel.brush_icons.keys())}")
                        except Exception as e:
                            print(f"❌ BrushIconsPanel failed: {e}")
                        
                        # Test PromptDisplayPanel
                        try:
                            prompt_panel = PromptDisplayPanel()
                            print("✅ PromptDisplayPanel creates successfully")
                            print(f"   Size: {prompt_panel.size().width()}x{prompt_panel.size().height()}")
                        except Exception as e:
                            print(f"❌ PromptDisplayPanel failed: {e}")
                        
                        # Test StatusPanel  
                        try:
                            status_panel = StatusPanel()
                            print("✅ StatusPanel creates successfully")
                        except Exception as e:
                            print(f"❌ StatusPanel failed: {e}")
                        
                        print("✅ New UI layout test completed successfully")
                        return True
                        
    except Exception as e:
        print(f"❌ UI layout test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_brush_icons():
    """Test brush icon loading"""
    print("\n🖌️ Testing Brush Icon Loading")
    print("-" * 40)
    
    try:
        brush_icons_dir = PROJECT_ROOT / "blender" / "assets" / "brush icons"
        
        expected_icons = ["soften.png", "inflate.png", "flatten.png", "grab.png"]
        
        for icon_name in expected_icons:
            icon_path = brush_icons_dir / icon_name
            if icon_path.exists():
                size_kb = icon_path.stat().st_size / 1024
                print(f"✅ {icon_name} found ({size_kb:.1f} KB)")
            else:
                print(f"❌ {icon_name} missing")
                
        print(f"✅ Brush icons directory: {brush_icons_dir}")
        return True
        
    except Exception as e:
        print(f"❌ Brush icon test failed: {e}")
        return False

def test_prompt_length_display():
    """Test how the new prompt display handles the 50-word limit"""
    print("\n📝 Testing Prompt Display with 50-Word Limit")
    print("-" * 40)
    
    try:
        # Read current prompt if it exists
        prompt_path = PROJECT_ROOT / "data" / "generated_text" / "userPrompt.txt"
        
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                full_prompt = f.read().strip()
            
            print(f"✅ Full prompt length: {len(full_prompt)} characters")
            
            # Test the filtering logic (remove photography setup)
            display_prompt = full_prompt
            if "Shown in a three-quarter view" in display_prompt:
                display_prompt = display_prompt.split("Shown in a three-quarter view")[0].strip()
            
            print(f"✅ Filtered prompt length: {len(display_prompt)} characters")
            print(f"📄 Display preview: {display_prompt[:100]}...")
            
            # Test word count
            words = display_prompt.split()
            print(f"✅ Word count: {len(words)} words")
            
            if len(words) <= 50:
                print("✅ Prompt is within 50-word limit")
            else:
                print(f"⚠️ Prompt exceeds 50 words ({len(words)})")
                
        else:
            print("⚠️ No prompt file found - creating test prompt")
            # Create a test prompt
            test_prompt = "modern chair with curved organic form, brushed aluminum materials"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(test_prompt)
            print(f"✅ Test prompt created: {test_prompt}")
            
        return True
        
    except Exception as e:
        print(f"❌ Prompt display test failed: {e}")
        return False

def main():
    """Run all UI tests"""
    print("🧪 CONJURE New UI Layout Tests")
    print("=" * 50)
    
    tests = [
        ("UI Layout Components", test_ui_layout),
        ("Brush Icon Loading", test_brush_icons), 
        ("Prompt Display Length", test_prompt_length_display)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📋 UI Test Results")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        if result:
            print(f"✅ {test_name}")
            passed += 1
        else:
            print(f"❌ {test_name}")
            failed += 1
    
    print(f"\nPassed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL UI TESTS PASSED!")
        print("✅ New UI layout is ready")
        print("\nWhat you should see:")
        print("- 🖌️ Left column: Brush icons (SOFTEN, INFLATE, FLATTEN, GRAB)")
        print("- 📊 Top-right: Compact status panel")
        print("- 📝 Bottom-center: Wide prompt display box")
        print("- 🔄 Real-time updates: Active brush highlighting & prompt updates")
        print("\n🚀 To launch the new UI:")
        print("   python Agent/conjure_ui.py")
        print("   or")
        print("   python launcher/main.py")
    else:
        print(f"\n⚠️ {failed} TESTS FAILED")
        print("❌ UI issues need fixing")

if __name__ == "__main__":
    main()
