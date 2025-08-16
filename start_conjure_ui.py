"""
CONJURE UI Startup Script
Simple launcher that handles path setup and starts the UI system
"""

import sys
import os
from pathlib import Path

# Add Agent directory to Python path
project_root = Path(__file__).parent
agent_dir = project_root / "Agent"
sys.path.insert(0, str(agent_dir))

# Change to project directory
os.chdir(project_root)

def main():
    """Main startup function"""
    print("Starting CONJURE UI System...")
    print(f"Project root: {project_root}")
    print(f"Agent directory: {agent_dir}")
    
    try:
        # Import the launcher
        from conjure_ui_launcher import ConjureUISystem
        
        # Create and run the system
        system = ConjureUISystem()
        exit_code = system.run()
        
        return exit_code
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all required packages are installed:")
        print("  pip install PyQt5")
        return 1
        
    except Exception as e:
        print(f"Error starting UI system: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
