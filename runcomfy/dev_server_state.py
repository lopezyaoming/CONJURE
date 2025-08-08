"""
Development Server State Management

Manages shared state for runComfy development servers to enable connection reuse
across multiple main.py runs and testing cycles.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import httpx


@dataclass
class DevServerState:
    """State information for a development runComfy server"""
    server_id: str
    user_id: str
    base_url: str
    status: str
    launch_time: str
    workflow_version: str
    server_type: str = "medium"
    total_cost: float = 0.0
    session_cost: float = 0.0
    last_health_check: Optional[str] = None
    health_status: str = "unknown"


class DevServerStateManager:
    """Manages development server state persistence and health monitoring"""
    
    def __init__(self, state_file_path: Optional[str] = None):
        """
        Initialize state manager
        
        Args:
            state_file_path: Path to state file (defaults to runcomfy/dev_server_state.json)
        """
        if state_file_path is None:
            # Use runcomfy directory for state file
            runcomfy_dir = Path(__file__).parent
            state_file_path = runcomfy_dir / "dev_server_state.json"
        
        self.state_file_path = Path(state_file_path)
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        
    def save_server_state(self, state: DevServerState) -> None:
        """Save server state to file"""
        try:
            with open(self.state_file_path, 'w') as f:
                json.dump(asdict(state), f, indent=2)
            print(f"✅ Saved server state to {self.state_file_path}")
        except Exception as e:
            print(f"❌ Error saving server state: {e}")
            raise
    
    def load_server_state(self) -> Optional[DevServerState]:
        """Load server state from file"""
        try:
            if not self.state_file_path.exists():
                return None
            
            # Check if file is empty
            if self.state_file_path.stat().st_size == 0:
                return None
            
            with open(self.state_file_path, 'r') as f:
                data = json.load(f)
            
            return DevServerState(**data)
        except json.JSONDecodeError:
            # Handle corrupted or empty JSON files
            print(f"⚠️ Invalid JSON in server state file, clearing...")
            self.clear_server_state()
            return None
        except Exception as e:
            print(f"⚠️ Error loading server state: {e}")
            return None
    
    def clear_server_state(self) -> None:
        """Clear/delete server state file"""
        try:
            if self.state_file_path.exists():
                self.state_file_path.unlink()
                print(f"🗑️ Cleared server state file: {self.state_file_path}")
        except Exception as e:
            print(f"⚠️ Error clearing server state: {e}")
    
    def has_active_server(self) -> bool:
        """Check if there's an active server state"""
        state = self.load_server_state()
        return state is not None and state.status in ["running", "ready"]
    
    async def check_server_health(self, state: DevServerState) -> bool:
        """
        Check if the server is actually healthy and reachable
        
        Args:
            state: Server state to check
            
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            # Try to reach ComfyUI-specific endpoints (not /health)
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try ComfyUI queue endpoint first
                response = await client.get(f"{state.base_url}/queue")
                
                if response.status_code == 200:
                    # Update health check timestamp
                    state.last_health_check = datetime.now(timezone.utc).isoformat()
                    state.health_status = "healthy"
                    self.save_server_state(state)
                    print(f"✅ ComfyUI server is healthy (queue endpoint responding)")
                    return True
                else:
                    # Try root endpoint as fallback
                    response = await client.get(f"{state.base_url}/")
                    if response.status_code == 200:
                        state.last_health_check = datetime.now(timezone.utc).isoformat()
                        state.health_status = "healthy"
                        self.save_server_state(state)
                        print(f"✅ ComfyUI server is healthy (root endpoint responding)")
                        return True
                    else:
                        print(f"⚠️ Server health check failed: HTTP {response.status_code}")
                        state.health_status = "unhealthy"
                        self.save_server_state(state)
                        return False
                    
        except Exception as e:
            print(f"❌ Server health check error: {e}")
            state.health_status = "unreachable"
            state.last_health_check = datetime.now(timezone.utc).isoformat()
            self.save_server_state(state)
            return False
    
    def update_cost(self, additional_cost: float) -> None:
        """Update server costs"""
        state = self.load_server_state()
        if state:
            state.total_cost += additional_cost
            state.session_cost += additional_cost
            self.save_server_state(state)
    
    def get_server_info(self) -> Optional[Dict[str, Any]]:
        """Get formatted server information for display"""
        state = self.load_server_state()
        if not state:
            return None
        
        # Calculate uptime
        launch_time = datetime.fromisoformat(state.launch_time.replace('Z', '+00:00'))
        uptime = datetime.now(timezone.utc) - launch_time
        uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}m"
        
        return {
            "server_id": state.server_id,
            "status": state.status,
            "base_url": state.base_url,
            "server_type": state.server_type,
            "uptime": uptime_str,
            "total_cost": f"${state.total_cost:.3f}",
            "session_cost": f"${state.session_cost:.3f}",
            "health_status": state.health_status,
            "last_health_check": state.last_health_check
        }
    
    async def validate_and_cleanup_state(self) -> bool:
        """
        Validate current server state and cleanup if server is no longer available
        
        Returns:
            True if server is valid and available, False if cleaned up
        """
        state = self.load_server_state()
        if not state:
            return False
        
        # Check if server is still healthy
        is_healthy = await self.check_server_health(state)
        
        if not is_healthy:
            print(f"🧹 Server {state.server_id} is not healthy, cleaning up state...")
            self.clear_server_state()
            return False
        
        return True


# Global instance for easy access
dev_server_state = DevServerStateManager()


def get_active_server() -> Optional[DevServerState]:
    """Convenience function to get active development server state"""
    return dev_server_state.load_server_state()


def has_active_dev_server() -> bool:
    """Convenience function to check if there's an active development server"""
    return dev_server_state.has_active_server()


async def validate_dev_server() -> bool:
    """Convenience function to validate and cleanup development server state"""
    return await dev_server_state.validate_and_cleanup_state()
