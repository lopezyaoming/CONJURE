"""
Development Server Startup Script

Independent script to launch and manage runComfy servers for development.
Avoids the 3-minute startup delay during iterative development cycles.

Usage:
    python runcomfy/dev_server_startup.py                    # Launch server with interactive menu
    python runcomfy/dev_server_startup.py --status           # Check server status  
    python runcomfy/dev_server_startup.py --shutdown         # Shutdown server
    python runcomfy/dev_server_startup.py --restart          # Restart server with optional type change
    python runcomfy/dev_server_startup.py --server-type large # Launch specific server type
    python runcomfy/dev_server_startup.py --no-interactive   # Skip interactive menu (use default)
"""

import asyncio
import argparse
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add websockets import for monitoring
try:
    import websockets
except ImportError:
    print("⚠️ websockets module not found - monitoring features will be limited")

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
    
    def _select_server_type(self) -> str:
        """Interactive server type selection"""
        server_options = {
            "medium": {
                "description": "Medium server - Good for basic workflows",
                "specs": "Balanced CPU/GPU",
                "cost": "Lower cost"
            },
            "large": {
                "description": "Large server - Better performance for complex workflows", 
                "specs": "More CPU/GPU power",
                "cost": "Medium cost"
            },
            "extra-large": {
                "description": "Extra Large server - High performance for demanding workflows",
                "specs": "High CPU/GPU power", 
                "cost": "Higher cost"
            },
            "2x-large": {
                "description": "2X Large server - Maximum performance",
                "specs": "Very high CPU/GPU power",
                "cost": "High cost"
            },
            "2xl-turbo": {
                "description": "2XL Turbo server - Ultra high performance with optimized speed",
                "specs": "Ultra high CPU/GPU power + speed optimizations",
                "cost": "Highest cost"
            }
        }
        
        print("\n🖥️ Select Server Type:")
        print("=" * 60)
        
        options_list = list(server_options.keys())
        for i, (server_type, info) in enumerate(server_options.items(), 1):
            print(f"{i}. {server_type.upper()}")
            print(f"   📝 {info['description']}")
            print(f"   ⚙️  {info['specs']}")
            print(f"   💰 {info['cost']}")
            print()
        
        while True:
            try:
                choice = input(f"Enter your choice (1-{len(options_list)}) or 'q' to quit: ").strip()
                
                if choice.lower() == 'q':
                    print("❌ Server launch cancelled")
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(options_list):
                    selected_type = options_list[choice_num - 1]
                    print(f"✅ Selected: {selected_type.upper()}")
                    return selected_type
                else:
                    print(f"❌ Please enter a number between 1 and {len(options_list)}")
                    
            except ValueError:
                print("❌ Please enter a valid number")

    async def launch_server(self, server_type: str = None, duration: int = 3600, interactive: bool = True) -> bool:
        """
        Launch a new development server
        
        Args:
            server_type: Server type (medium, large, etc.) - if None and interactive=True, will prompt user
            duration: Duration in seconds (default: 1 hour)
            interactive: Whether to show interactive server selection menu
            
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
        
        # Interactive server type selection if not specified
        if server_type is None and interactive:
            server_type = self._select_server_type()
            if server_type is None:
                return False
        elif server_type is None:
            server_type = "medium"  # Default fallback
        
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
                    
                    # Pre-warm the server with a startup workflow
                    print("\n🔥 Pre-warming server with startup workflow...")
                    warmup_success = await self._prewarm_server(state)
                    
                    if warmup_success:
                        print("🚀 Startup workflow completed: machine is ready to go!")
                        
                        # Start workflow monitoring mode
                        print("\n" + "="*60)
                        print("🖥️ DEVELOPMENT SERVER MONITORING")
                        print("="*60)
                        print("Server is now ready and monitoring workflows.")
                        print("Use Ctrl+C to stop monitoring and shutdown server.")
                        print("="*60 + "\n")
                        
                        # Enter monitoring mode
                        await self._monitor_workflow_progress(state)
                    else:
                        print("⚠️ Server warmup failed, but server is still available")
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
    
    async def restart_server(self, interactive: bool = True) -> bool:
        """Restart the development server"""
        print("🔄 Restarting development server...")
        
        # Get current server config
        state = self.state_manager.load_server_state()
        current_server_type = state.server_type if state else None
        
        # Shutdown existing server
        await self.shutdown_server()
        
        # Ask if they want to change server type during restart
        if interactive and current_server_type:
            print(f"\n📋 Current server type: {current_server_type.upper()}")
            change_type = input("Do you want to change the server type? (y/N): ").strip().lower()
            
            if change_type == 'y':
                server_type = self._select_server_type()
                if server_type is None:
                    return False
            else:
                server_type = current_server_type
        else:
            server_type = current_server_type
        
        # Launch new server
        return await self.launch_server(server_type=server_type, interactive=False)
    
    async def _prewarm_server(self, state: DevServerState) -> bool:
        """
        Pre-warm the server by sending a simple workflow to load AI models
        
        Args:
            state: Active server state
            
        Returns:
            True if warmup successful, False otherwise
        """
        try:
            print("🔥 Starting server warmup workflow...")
            
            # Import ComfyUI client
            from runcomfy.comfyui_workflow_client import ComfyUIWorkflowClient
            import json
            
            # Load the full generate_flux_mesh workflow for proper warmup
            workflow_path = Path(__file__).parent / "workflows" / "generate_flux_mesh.json"
            if not workflow_path.exists():
                print(f"⚠️ Workflow file not found: {workflow_path}")
                return False
                
            with open(workflow_path, 'r', encoding='utf-8') as f:
                warmup_workflow = json.load(f)
                
            print(f"📄 Loaded warmup workflow from: {workflow_path.name}")
            
            # Randomize seeds for warmup workflow
            import random
            noise_seed = random.randint(0, 18446744073709551615)
            partpacker_seed = random.randint(0, 2147483647)
            
            if "3" in warmup_workflow and "inputs" in warmup_workflow["3"]:
                warmup_workflow["3"]["inputs"]["noise_seed"] = noise_seed
                print(f"🎲 Randomized warmup noise_seed: {noise_seed}")
                
            if "32" in warmup_workflow and "inputs" in warmup_workflow["32"]:
                warmup_workflow["32"]["inputs"]["seed"] = partpacker_seed
                print(f"🎲 Randomized warmup PartPacker seed: {partpacker_seed}")
            
            # Initialize workflow client
            client = ComfyUIWorkflowClient()
            
            print("📤 Submitting warmup workflow...")
            prompt_id, client_id = await client.submit_workflow(
                state.base_url, 
                warmup_workflow
            )
            
            print(f"✅ Warmup workflow submitted: {prompt_id}")
            print("⏳ Waiting for models to load...")
            
            # Monitor the warmup workflow using WebSocket
            print("🔌 Monitoring warmup workflow via WebSocket...")
            execution_result = await client.wait_for_completion_websocket(
                state.base_url, 
                prompt_id, 
                client_id
            )
            
            success = execution_result.status == "completed"
            if success:
                print("✅ Warmup workflow completed successfully!")
            else:
                print(f"❌ Warmup workflow failed: {execution_result.error_message}")
            
            return success
            
        except Exception as e:
            print(f"❌ Server warmup failed: {e}")
            return False
    

    async def _monitor_workflow_progress(self, state: DevServerState):
        """
        Monitor workflow progress in real-time and display updates
        
        Args:
            state: Active server state
        """
        try:
            import websockets
            import json
            
            # Connect to ComfyUI WebSocket for real-time progress
            ws_url = state.base_url.replace("http", "ws") + "/ws?clientId=dev_monitor"
            
            print("🔌 Connecting to workflow monitoring...")
            
            async with websockets.connect(ws_url) as websocket:
                print("✅ Connected to workflow monitoring")
                print("📊 Monitoring workflow progress...\n")
                
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        data = json.loads(message)
                        
                        await self._process_workflow_event(data)
                        
                    except asyncio.TimeoutError:
                        # Periodic heartbeat - show we're still alive
                        current_time = datetime.now().strftime("%H:%M:%S")
                        print(f"[{current_time}] 📡 Monitoring active...")
                        
                    except websockets.exceptions.ConnectionClosed:
                        print("❌ WebSocket connection closed")
                        break
                        
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            await self._handle_shutdown_request(state)
            
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
    
    async def _process_workflow_event(self, data: dict):
        """Process workflow progress events from WebSocket"""
        event_type = data.get("type")
        
        if event_type == "status":
            status_data = data.get("data", {})
            queue_size = status_data.get("status", {}).get("exec_info", {}).get("queue_remaining", 0)
            if queue_size > 0:
                print(f"📬 Workflow received - Queue position: {queue_size}")
        
        elif event_type == "executing":
            node_data = data.get("data")
            if node_data:
                node_id = node_data.get("node")
                if node_id:
                    print(f"🔄 Executing: Node {node_id}")
        
        elif event_type == "executed":
            node_data = data.get("data")
            if node_data:
                node_id = node_data.get("node")
                if node_id:
                    print(f"✅ Completed: Node {node_id}")
        
        elif event_type == "progress":
            progress_data = data.get("data")
            if progress_data:
                value = progress_data.get("value", 0)
                max_value = progress_data.get("max", 100)
                node_id = progress_data.get("node", "?")
                percentage = int((value / max_value) * 100) if max_value > 0 else 0
                print(f"🔄 Progress: Node {node_id} - {percentage}% ({value}/{max_value})")
        
        elif event_type == "crystools.monitor":
            # Show simplified system monitoring (only occasionally)
            if hasattr(self, '_last_monitor_time'):
                if time.time() - self._last_monitor_time < 30:  # Only show every 30 seconds
                    return
            self._last_monitor_time = time.time()
            
            data_info = data.get("data", {})
            cpu = data_info.get("cpu_utilization", 0)
            ram = data_info.get("ram_used_percent", 0)
            gpu_info = data_info.get("gpus", [{}])[0] if data_info.get("gpus") else {}
            gpu_util = gpu_info.get("gpu_utilization", 0)
            gpu_temp = gpu_info.get("gpu_temperature", 0)
            vram = gpu_info.get("vram_used_percent", 0)
            print(f"📊 System: CPU {cpu:.1f}% | RAM {ram:.1f}% | GPU {gpu_util}% ({gpu_temp}°C) | VRAM {vram:.1f}%")
        
        # Skip all other message types (reduces noise)
    
    async def _handle_shutdown_request(self, state: DevServerState):
        """Handle user request to shutdown monitoring and server"""
        try:
            print("\n🤔 What would you like to do?")
            print("1. Stop monitoring but keep server running")
            print("2. Shutdown server and stop monitoring")
            
            choice = input("Enter your choice (1 or 2): ").strip()
            
            if choice == "2":
                print("🛑 Shutting down development server...")
                await self.shutdown_server()
            else:
                print("📡 Monitoring stopped, server still running")
                print(f"💡 Server URL: {state.base_url}")
                print("💡 Use --status to check server later")
                
        except Exception as e:
            print(f"❌ Error during shutdown: {e}")


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
        default=None,
        choices=["medium", "large", "extra-large", "2x-large", "2xl-turbo"],
        help="Server type for launch (if not specified, interactive menu will be shown)"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Skip interactive server selection menu and use default/specified server type"
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
            interactive = not args.no_interactive
            success = await manager.restart_server(interactive=interactive)
            sys.exit(0 if success else 1)
        else:
            # Default action: launch server
            interactive = not args.no_interactive
            success = await manager.launch_server(
                server_type=args.server_type,
                duration=args.duration,
                interactive=interactive
            )
            # Note: launch_server now includes monitoring, so we don't exit immediately
            if not success:
                sys.exit(1)
            
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
