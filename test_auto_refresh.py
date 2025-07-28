"""
Test script for CONJURE auto-refresh functionality
This script monitors the gestureCamera render.png file to verify it's being updated
"""
import os
import time
from pathlib import Path

def test_auto_refresh():
    """Test if the auto-refresh is working by monitoring render.png timestamps"""
    render_path = Path("data/generated_images/gestureCamera/render.png")
    
    print("🧪 CONJURE Auto-Refresh Test")
    print("=" * 50)
    print(f"📁 Monitoring: {render_path}")
    
    if not render_path.exists():
        print("❌ render.png not found - please start CONJURE first")
        return False
    
    initial_time = render_path.stat().st_mtime
    print(f"📅 Initial timestamp: {time.ctime(initial_time)}")
    print()
    print("⏰ Waiting for auto-refresh updates (should happen every 3 seconds)...")
    print("📋 Press Ctrl+C to stop monitoring")
    
    update_count = 0
    last_time = initial_time
    
    try:
        while True:
            time.sleep(1)  # Check every second
            
            if render_path.exists():
                current_time = render_path.stat().st_mtime
                
                if current_time > last_time:
                    update_count += 1
                    time_diff = current_time - last_time
                    print(f"✅ Update #{update_count}: {time.ctime(current_time)} (after {time_diff:.1f}s)")
                    last_time = current_time
                    
                    # Check if update interval is reasonable (2-4 seconds)
                    if update_count > 1 and (time_diff < 2.0 or time_diff > 5.0):
                        print(f"⚠️ Warning: Update interval {time_diff:.1f}s is not expected (should be ~3s)")
                    
            else:
                print("❌ render.png disappeared!")
                return False
                
    except KeyboardInterrupt:
        print(f"\n🏁 Test completed!")
        print(f"📊 Results:")
        print(f"   Total updates: {update_count}")
        if update_count > 0:
            total_time = last_time - initial_time
            avg_interval = total_time / update_count if update_count > 0 else 0
            print(f"   Average interval: {avg_interval:.1f}s")
            
            if 2.5 <= avg_interval <= 3.5:
                print("✅ Auto-refresh is working correctly!")
                return True
            else:
                print(f"⚠️ Auto-refresh interval ({avg_interval:.1f}s) is not optimal (should be ~3s)")
                return False
        else:
            print("❌ No updates detected - auto-refresh may not be working")
            return False

def check_blender_addon():
    """Check if the CONJURE Blender addon is properly set up"""
    addon_path = Path("scripts/addons/conjure/__init__.py")
    
    print("\n🔍 Addon Check:")
    if addon_path.exists():
        print("✅ CONJURE addon found")
        return True
    else:
        print("❌ CONJURE addon not found - please check installation")
        return False

def main():
    """Run the complete test suite"""
    print("🚀 CONJURE Auto-Refresh Test Suite")
    print("=" * 60)
    
    # Check addon
    if not check_blender_addon():
        print("\n💡 Install instructions:")
        print("1. Open Blender")
        print("2. Go to Edit > Preferences > Add-ons")
        print("3. Install the CONJURE addon from scripts/addons/conjure/")
        print("4. Enable the addon")
        print("5. Start CONJURE from the 3D Viewport > CONJURE panel")
        return
    
    # Test auto-refresh
    print("\n📋 Instructions:")
    print("1. Start CONJURE in Blender (3D Viewport > CONJURE > Initiate CONJURE)")
    print("2. The auto-refresh should start automatically")
    print("3. Run this test to verify it's working")
    print("4. You can also manually start/stop via the 'Backend Agent Context' panel")
    
    input("\nPress Enter when CONJURE is running and you're ready to test...")
    
    if test_auto_refresh():
        print("\n🎉 All tests passed! Auto-refresh is working properly.")
    else:
        print("\n🔧 Auto-refresh needs troubleshooting.")
        print("\n💡 Troubleshooting:")
        print("- Make sure CONJURE is running in Blender")
        print("- Check the 'Backend Agent Context' panel in the CONJURE UI")
        print("- Look for auto-refresh messages in Blender's console")
        print("- Verify GestureCamera exists in your scene")

if __name__ == "__main__":
    main() 