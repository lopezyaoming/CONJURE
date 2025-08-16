"""
CONJURE UI Direct Startup
Launches the direct UI.py copy for CONJURE
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
    print("Starting CONJURE UI (Direct UI.py Copy)...")
    print(f"Project root: {project_root}")
    print(f"Agent directory: {agent_dir}")
    
    try:
        # Import and run the direct UI
        from conjure_ui_direct import TransparentWindow
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        
        # Set application attributes like UI.py
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        
        app = QApplication(sys.argv)
        
        # Use system font like UI.py
        font = QFont("Segoe UI" if sys.platform == "win32" else "Helvetica")
        font.setPointSize(10)
        app.setFont(font)
        
        # Create and show window
        window = TransparentWindow()
        window.show()
        
        print("✅ CONJURE UI is running (ESC to close)")
        
        # Run the application
        return app.exec_()
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all required packages are installed:")
        print("  pip install PyQt5")
        return 1
        
    except Exception as e:
        print(f"Error starting UI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
