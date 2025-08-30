"""
Subprocess manager for handling external processes.
Manages Blender, CGAL, and ComfyUI processes.
"""

import subprocess
import os
import sys
import socket
import time
from pathlib import Path

# Import the configured path from the config file.
from launcher.config import BLENDER_EXECUTABLE_PATH

class SubprocessManager:
    def __init__(self):
        self.processes = {}
        # Assuming the project root is two levels up from this script's directory
        self.project_root = Path(__file__).parent.parent

    def _is_port_in_use(self, port):
        """Check if a port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return False
            except socket.error:
                return True

    def _wait_for_port(self, port, timeout=10):
        """Wait for a port to become available (server to start)."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_in_use(port):
                return True
            time.sleep(0.5)
        return False

    def start_hand_tracker(self):
        """Starts the hand_tracker.py script in a new process."""
        print("Starting hand tracker...")
        script_path = self.project_root / "launcher" / "hand_tracker.py"
        # Use sys.executable to ensure we run with the same Python interpreter
        # that is running the launcher itself.
        process = subprocess.Popen([sys.executable, str(script_path)])
        self.processes['hand_tracker'] = process
        print("Hand tracker process started.")

    def start_blender(self):
        """Starts Blender and enables the CONJURE addon."""
        print("Starting Blender...")
        blender_scene_dir = self.project_root / "blender"
        scene_path = blender_scene_dir / "scene.blend"

        # --- Enhanced Command with Auto-Enable Addon ---
        # Enable the CONJURE addon automatically when Blender starts
        addon_path = self.project_root / "scripts" / "addons"
        python_expr = f"""
import bpy
import sys
import os

# Add addon path to Blender's Python path
addon_path = r"{addon_path}"
if addon_path not in sys.path:
    sys.path.insert(0, addon_path)

# Enable CONJURE addon
try:
    print("🚀 Auto-enabling CONJURE addon...")
    bpy.ops.preferences.addon_enable(module="conjure")
    print("✅ CONJURE addon enabled successfully!")
except Exception as e:
    print(f"❌ Failed to enable CONJURE addon: {{e}}")
"""
        
        command = [
            str(BLENDER_EXECUTABLE_PATH),
            str(scene_path),
            "--python-expr", python_expr
        ]
        
        # We run Blender with its UI visible for interaction, not in the background.
        process = subprocess.Popen(command)
        self.processes['blender'] = process
        print("Blender process started with CONJURE addon enabled.")

    def start_api_server(self):
        """Starts the FastAPI server in a separate process."""
        # Check if API server is already running
        if 'api_server' in self.processes:
            if self.processes['api_server'].poll() is None:
                print("⚠️ API server already running, skipping startup")
                return
            else:
                # Process exists but has terminated, remove it
                del self.processes['api_server']
        
        # Check if port 8000 is already in use
        if self._is_port_in_use(8000):
            print("⚠️ Port 8000 is already in use. Attempting to continue...")
            # Try to find and terminate any existing API server process
            self._cleanup_existing_api_server()
            time.sleep(2)  # Wait a bit before trying again
        
        print("Starting CONJURE API server...")
        script_path = self.project_root / "launcher" / "api_server.py"
        
        # Start the API server directly with Python (not uvicorn module)
        # This ensures proper module resolution
        try:
            process = subprocess.Popen([
                sys.executable, str(script_path)
            ], cwd=self.project_root)
            
            self.processes['api_server'] = process
            print("API server process started on http://127.0.0.1:8000")
            
            # Wait for the server to actually start
            if self._wait_for_port(8000, timeout=10):
                print("✅ API server is responding on port 8000")
            else:
                print("⚠️ API server may not have started properly")
                
        except Exception as e:
            print(f"❌ Failed to start API server: {e}")

    def _cleanup_existing_api_server(self):
        """Try to cleanup any existing API server processes."""
        try:
            if sys.platform == "win32":
                # On Windows, try to find and kill processes using port 8000
                result = subprocess.run([
                    "netstat", "-ano"
                ], capture_output=True, text=True, timeout=5)
                
                for line in result.stdout.split('\n'):
                    if ':8000' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) > 4:
                            pid = parts[-1]
                            try:
                                subprocess.run([
                                    "taskkill", "/PID", pid, "/F"
                                ], capture_output=True, timeout=5)
                                print(f"🧹 Cleaned up process {pid} using port 8000")
                            except:
                                pass
        except Exception as e:
            print(f"⚠️ Could not cleanup existing processes: {e}")

    def stop_all(self):
        """Terminates all managed subprocesses gracefully."""
        print("Stopping all subprocesses...")
        for name, process in self.processes.items():
            try:
                if process.poll() is None:  # Check if the process is still running
                    print(f"Stopping {name} (PID: {process.pid})...")
                    
                    if sys.platform == "win32" and name == 'blender':
                        print(f"Attempting to terminate Blender process tree (PID: {process.pid})...")
                        subprocess.run(f"taskkill /PID {process.pid} /F /T", check=True, capture_output=True, text=True)
                        print(f"Successfully sent termination signal to Blender process tree.")
                    elif name == 'api_server':
                        # Give API server a moment to shutdown gracefully
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                            print(f"API server terminated gracefully.")
                        except subprocess.TimeoutExpired:
                            print(f"API server didn't terminate gracefully, forcing kill...")
                            process.kill()
                            process.wait(timeout=2)
                    else:
                        process.terminate()
                        process.wait(timeout=5)
                        print(f"Terminated '{name}'.")
                else:
                    print(f"Process '{name}' was already terminated.")
            except subprocess.TimeoutExpired:
                print(f"Process '{name}' did not terminate gracefully, attempting to kill...")
                process.kill()
                try:
                    process.wait(timeout=5) # Wait a bit after killing
                    print(f"Forcefully killed '{name}'.")
                except subprocess.TimeoutExpired:
                    print(f"Could not kill '{name}' - it may have become unresponsive.")
            except subprocess.CalledProcessError as e:
                print(f"Error forcefully terminating {name} with taskkill: {e.stderr}")
            except Exception as e:
                print(f"Error while stopping '{name}': {e}")
        
        # Additional cleanup for API server port
        if self._is_port_in_use(8000):
            print("🧹 Port 8000 still in use after shutdown, attempting cleanup...")
            self._cleanup_existing_api_server()
        
        self.processes.clear()
        print("All subprocesses stopped.") 