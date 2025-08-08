"""
Development Workflow Demo

This script demonstrates how to use the development server for fast iteration.
Run this to see how the development workflow would work.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from runcomfy.dev_server_state import DevServerStateManager, has_active_dev_server, get_active_server


async def demo_workflow():
    """Demonstrate the development server workflow"""
    print("🚀 RunComfy Development Workflow Demo")
    print("=" * 50)
    
    # Check if there's an active development server
    print("\\n1. Checking for active development server...")
    
    if has_active_dev_server():
        print("✅ Active development server found!")
        
        server_state = get_active_server()
        if server_state:
            print(f"   Server ID: {server_state.server_id}")
            print(f"   Base URL: {server_state.base_url}")
            print(f"   Status: {server_state.status}")
            print(f"   Server Type: {server_state.server_type}")
            print(f"   Total Cost: ${server_state.total_cost:.3f}")
            
            # Simulate a health check
            state_manager = DevServerStateManager()
            print("\\n   Performing health check...")
            is_healthy = await state_manager.check_server_health(server_state)
            
            if is_healthy:
                print("   ✅ Server is healthy and ready for use!")
                print("   💡 You can now run main.py multiple times using this server")
            else:
                print("   ❌ Server health check failed")
                print("   💡 Consider restarting the development server")
    else:
        print("ℹ️ No active development server found")
        print("\\n💡 To start a development server, run:")
        print("   python runcomfy/dev_server_startup.py")
        print("\\n   Available options:")
        print("   --server-type medium|large|extra-large|2x-large|2xl-turbo")
        print("   --duration 3600  # Duration in seconds")
    
    print("\\n" + "=" * 50)
    print("📋 Development Workflow Summary:")
    print("=" * 50)
    
    print("\\n🔄 Fast Development Cycle:")
    print("1. Launch server once: python runcomfy/dev_server_startup.py")
    print("2. Develop iteratively:")
    print("   - python launcher/main.py  # Uses existing server")
    print("   - python test_flux_mesh_workflow.py")
    print("   - python launcher/main.py  # Another iteration")
    print("3. End session: python runcomfy/dev_server_startup.py --shutdown")
    
    print("\\n📊 Status Commands:")
    print("- Check status: python runcomfy/dev_server_startup.py --status")
    print("- Restart server: python runcomfy/dev_server_startup.py --restart")
    
    print("\\n💰 Cost Benefits:")
    print("- Traditional: 3 minutes startup per test = 15 minutes for 5 tests")
    print("- Development: 3 minutes startup once = 3 minutes for 5 tests")
    print("- Time saved: 80% faster iteration!")
    
    print("\\n🔧 Technical Details:")
    print("- State file: runcomfy/dev_server_state.json")
    print("- Credentials: runcomfy/credentials.txt") 
    print("- Health checks: Automatic server validation")
    print("- Auto cleanup: Invalid servers removed automatically")


def demo_state_management():
    """Demonstrate state management functionality"""
    print("\\n" + "=" * 50)
    print("🗃️ State Management Demo")
    print("=" * 50)
    
    state_manager = DevServerStateManager()
    
    # Show state file location
    print(f"State file location: {state_manager.state_file_path}")
    
    # Check if state file exists
    if state_manager.state_file_path.exists():
        print("✅ State file exists")
        
        # Show file contents
        try:
            with open(state_manager.state_file_path, 'r') as f:
                content = f.read()
            print("\\n📄 Current state file contents:")
            print(content)
        except Exception as e:
            print(f"⚠️ Error reading state file: {e}")
    else:
        print("ℹ️ No state file found (no active servers)")
    
    # Show server info if available
    info = state_manager.get_server_info()
    if info:
        print("\\n📊 Formatted server information:")
        for key, value in info.items():
            print(f"   {key}: {value}")


async def main():
    """Main demo function"""
    await demo_workflow()
    demo_state_management()
    
    print("\\n" + "=" * 50)
    print("🎯 Next Steps:")
    print("=" * 50)
    print("1. Verify your credentials in runcomfy/credentials.txt")
    print("2. Launch a development server:")
    print("   python runcomfy/dev_server_startup.py")
    print("3. Run this demo again to see the active server")
    print("4. Start developing with instant server reuse!")


if __name__ == "__main__":
    asyncio.run(main())
