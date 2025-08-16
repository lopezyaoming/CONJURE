#!/usr/bin/env python3
"""
Simple separate process launcher for CONJURE UI overlay
This runs the UI completely independently of the main CONJURE process
"""

import subprocess
import sys
from pathlib import Path

def launch_conjure_ui():
    """Launch the CONJURE UI as a separate process"""
    print("🚀 Launching CONJURE UI overlay as separate process...")
    
    # Path to the UI script
    ui_script = Path(__file__).parent / "Agent" / "conjure_ui_direct.py"
    python_exe = sys.executable
    
    # Launch as completely separate process
    try:
        # Launch as background process but with better startup verification
        import platform
        import time
        
        if platform.system() == "Windows":
            # On Windows, create detached process  
            process = subprocess.Popen(
                [python_exe, str(ui_script)],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            # On other systems
            process = subprocess.Popen(
                [python_exe, str(ui_script)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        
        # Give it a moment to start up and check if it's still running
        time.sleep(2)
        
        if process.poll() is not None:
            # Process has already terminated, which means there was an error
            stdout, stderr = process.communicate()
            print(f"❌ UI process terminated immediately!")
            print(f"Return code: {process.returncode}")
            if stdout:
                print(f"STDOUT: {stdout.decode()}")
            if stderr:
                print(f"STDERR: {stderr.decode()}")
            return False
        
        print("✅ CONJURE UI overlay launched successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to launch UI overlay: {e}")
        return False

if __name__ == "__main__":
    launch_conjure_ui()
