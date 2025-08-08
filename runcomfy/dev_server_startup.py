"""
Development Server Startup Script

Independent script to launch and manage runComfy servers for development.
Avoids the 3-minute startup delay during iterative development cycles.

Usage:
    python runcomfy/dev_server_startup.py              # Launch server
    python runcomfy/dev_server_startup.py --status     # Check server status  
    python runcomfy/dev_server_startup.py --shutdown   # Shutdown server
    python runcomfy/dev_server_startup.py --restart    # Restart server
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from runcomfy.dev_server_state import DevServerStateManager, DevServerState


class DevServerManager:
    """Manages development server lifecycle"""
    
    def __init__(self):
        self.state_manager = DevServerStateManager()
        self.client = None
        
        # Load credentials from credentials.txt
        self.credentials = self._load_credentials()
        
    def _load_credentials(self) -> dict:
        """Load credentials from runcomfy/credentials.txt"""
        credentials_path = Path(__file__).parent / "credentials.txt"
        
        if not credentials_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
        
        credentials = {}
        try:
            with open(credentials_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        key, value = line.split(':', 1)
                        # Clean up the values (remove quotes and spaces)
                        key = key.strip().strip('"')
                        value = value.strip().strip('"')
                        credentials[key] = value
            
            print(f"✅ Loaded credentials from {credentials_path}")
            print(f"   User ID: {credentials.get('userID', 'NOT SET')}")
            print(f"   Token: {'SET' if credentials.get('RUNCOMFY_API_TOKEN') else 'NOT SET'}")
            print(f"   Version ID: {credentials.get('version_id', 'NOT SET')}")
            
            return credentials
            
        except Exception as e:
            raise RuntimeError(f"Error loading credentials: {e}")
    
    def _get_client(self):
        """Get or create RunComfy API client with credentials"""
        if self.client is None:
            # Set environment variables from credentials
            os.environ["RUNCOMFY_USER_ID"] = self.credentials.get("userID", "")
            os.environ["RUNCOMFY_API_TOKEN"] = self.credentials.get("RUNCOMFY_API_TOKEN", "")
            
            from runcomfy.runcomfy_client import RunComfyAPIClient
            self.client = RunComfyAPIClient()
        
        return self.client
    
    async def launch_server(self, server_type: str = "medium", duration: int = 3600) -> bool:
        """
        Launch a new development server
        
        Args:
            server_type: Server type (medium, large, etc.)
            duration: Duration in seconds (default: 1 hour)
            
        Returns:
            True if successful, False otherwise
        """
        # Check if there's already an active server
        if self.state_manager.has_active_server():
            print("⚠️ Active development server already exists!")
            await self.show_status()
            
            response = input("Do you want to shutdown the existing server and start a new one? (y/N): ")
            if response.lower() != 'y':
                print("❌ Launch cancelled")
                return False
            
            print("🛑 Shutting down existing server...")
            await self.shutdown_server()
        
        print(f"🚀 Launching development server...")
        print(f"   Type: {server_type}")
        print(f"   Duration: {duration}s ({duration//60} minutes)")
        
        try:
            client = self._get_client()
            
            # Launch the machine
            print("📡 Requesting server launch...")
            machine_info = await client.launch_machine(
                server_type=server_type,
                estimated_duration=duration,
                workflow_version_id=self.credentials.get("version_id")
            )
            
            print(f"✅ Server launch initiated: {machine_info.server_id}")
            print("⏳ Waiting for server to be ready...")
            
            # Wait for server to be ready
            ready_machine = await client.wait_for_machine_ready(
                machine_info.server_id,
                timeout=1800  # 30 minutes timeout
            )
            
            if ready_machine and ready_machine.main_service_url:
                # Create and save state
                state = DevServerState(
                    server_id=ready_machine.server_id,
                    user_id=ready_machine.user_id,
                    base_url=ready_machine.main_service_url,
                    status="running",
                    launch_time=datetime.now(timezone.utc).isoformat(),
                    workflow_version=self.credentials.get("version_id", "unknown"),
                    server_type=server_type,
                    total_cost=0.0,
                    session_cost=0.0
                )
                
                self.state_manager.save_server_state(state)
                
                print("🎉 Development server is ready!")
                print(f"   Server ID: {ready_machine.server_id}")
                print(f"   Base URL: {ready_machine.main_service_url}")
                print(f"   Status: {ready_machine.current_status}")
                
                # Do a health check
                is_healthy = await self.state_manager.check_server_health(state)
                if is_healthy:
                    print("✅ Server health check passed")
                else:
                    print("⚠️ Server health check failed")
                
                return True
            else:
                print("❌ Server failed to become ready")
                return False
                
        except Exception as e:
            print(f"❌ Error launching server: {e}")
            import traceback
            print(f"🔍 Full traceback:\\n{traceback.format_exc()}")
            return False
    
    async def shutdown_server(self) -> bool:
        """Shutdown the current development server"""
        state = self.state_manager.load_server_state()
        if not state:
            print("ℹ️ No active development server found")
            return True
        
        print(f"🛑 Shutting down development server: {state.server_id}")
        
        try:
            client = self._get_client()
            
            # Stop the machine
            success = await client.stop_machine(state.server_id)
            
            if success:
                print("✅ Server shutdown initiated")
                
                # Clear the state
                self.state_manager.clear_server_state()
                print("🗑️ Development server state cleared")
                return True
            else:
                print("❌ Failed to shutdown server")
                return False
                
        except Exception as e:
            print(f"❌ Error shutting down server: {e}")
            # Clear state anyway since server might be gone
            self.state_manager.clear_server_state()
            return False
    
    async def show_status(self) -> None:
        """Show current development server status"""
        print("🔍 Development Server Status")
        print("=" * 50)
        
        state = self.state_manager.load_server_state()
        if not state:
            print("ℹ️ No active development server")
            return
        
        # Show basic info
        info = self.state_manager.get_server_info()
        if info:
            print(f"Server ID: {info['server_id']}")
            print(f"Status: {info['status']}")
            print(f"Base URL: {info['base_url']}")
            print(f"Server Type: {info['server_type']}")
            print(f"Uptime: {info['uptime']}")
            print(f"Total Cost: {info['total_cost']}")
            print(f"Session Cost: {info['session_cost']}")
            print(f"Health Status: {info['health_status']}")
            
            if info['last_health_check']:
                print(f"Last Health Check: {info['last_health_check']}")
        
        # Do a live health check
        print("\\n🏥 Performing live health check...")
        is_healthy = await self.state_manager.check_server_health(state)
        
        if is_healthy:
            print("✅ Server is healthy and reachable")
        else:
            print("❌ Server is not reachable")
            print("💡 Try running with --restart to restart the server")
    
    async def restart_server(self) -> bool:
        """Restart the development server"""
        print("🔄 Restarting development server...")
        
        # Get current server config
        state = self.state_manager.load_server_state()
        server_type = state.server_type if state else "medium"
        
        # Shutdown existing server
        await self.shutdown_server()
        
        # Launch new server
        return await self.launch_server(server_type=server_type)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="RunComfy Development Server Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--status", 
        action="store_true", 
        help="Show current server status"
    )
    parser.add_argument(
        "--shutdown", 
        action="store_true", 
        help="Shutdown current server"
    )
    parser.add_argument(
        "--restart", 
        action="store_true", 
        help="Restart current server"
    )
    parser.add_argument(
        "--server-type", 
        default="medium",
        choices=["medium", "large", "extra-large", "2x-large", "2xl-turbo"],
        help="Server type for launch (default: medium)"
    )
    parser.add_argument(
        "--duration", 
        type=int, 
        default=3600,
        help="Server duration in seconds (default: 3600 = 1 hour)"
    )
    
    args = parser.parse_args()
    
    try:
        manager = DevServerManager()
        
        if args.status:
            await manager.show_status()
        elif args.shutdown:
            success = await manager.shutdown_server()
            sys.exit(0 if success else 1)
        elif args.restart:
            success = await manager.restart_server()
            sys.exit(0 if success else 1)
        else:
            # Default action: launch server
            success = await manager.launch_server(
                server_type=args.server_type,
                duration=args.duration
            )
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        print("\\n🛑 Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        print(f"🔍 Full traceback:\\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    print("🚀 RunComfy Development Server Manager")
    print("=" * 50)
    asyncio.run(main())
