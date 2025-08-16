"""
CONJURE UI Launcher
Integrates main UI with workflow overlay and data generation
"""

import sys
import time
import threading
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import our UI components
try:
    from ui_data_generator import UIDataGenerator
    from conjure_ui import ConjureUI
    from workflow_overlay import WorkflowOverlayManager
    from ui_config import UIConfig
except ImportError as e:
    print(f"Error importing UI components: {e}")
    sys.exit(1)

class ConjureUISystem:
    """Main system that coordinates all UI components"""
    
    def __init__(self):
        self.app = None
        self.main_ui = None
        self.data_generator = None
        self.workflow_overlay = None
        self.monitoring_thread = None
        self.running = False
        
    def initialize(self):
        """Initialize all components"""
        print("Initializing CONJURE UI System...")
        
        # Create QApplication
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        
        # Set application properties
        self.app.setAttribute(Qt.AA_EnableHighDpiScaling)
        self.app.setApplicationName("CONJURE UI")
        self.app.setApplicationVersion("1.0")
        
        # Initialize data generator
        self.data_generator = UIDataGenerator()
        print("Data generator initialized")
        
        # Initialize workflow overlay manager
        self.workflow_overlay = WorkflowOverlayManager()
        print("Workflow overlay manager initialized")
        
        # Initialize main UI
        self.main_ui = ConjureUI(sys.argv)
        print("Main UI initialized")
        
        # Set up workflow monitoring
        self.setup_workflow_monitoring()
        
        print("CONJURE UI System initialization complete")
    
    def setup_workflow_monitoring(self):
        """Set up monitoring for workflow state changes"""
        # Timer to check for workflow activation
        self.workflow_timer = QTimer()
        self.workflow_timer.timeout.connect(self.check_workflow_state)
        self.workflow_timer.start(UIConfig.WORKFLOW_CHECK_INTERVAL)
    
    def check_workflow_state(self):
        """Check if workflow overlay should be shown/hidden"""
        try:
            # Load current UI data
            ui_data = self.data_generator.generate_ui_json()
            workflow_progress = ui_data.workflow_progress
            
            # Check if workflow is active
            if workflow_progress.active and not self.workflow_overlay.is_visible():
                print("Workflow started - showing overlay")
                self.workflow_overlay.show_overlay()
            elif not workflow_progress.active and self.workflow_overlay.is_visible():
                print("Workflow completed - hiding overlay")
                self.workflow_overlay.hide_overlay()
                
        except Exception as e:
            print(f"Error checking workflow state: {e}")
    
    def start_data_monitoring(self):
        """Start data monitoring in background thread"""
        def monitor_data():
            print("Starting data monitoring thread...")
            while self.running:
                try:
                    if self.data_generator.has_data_changed():
                        print("Data changes detected, updating UI data...")
                        ui_data = self.data_generator.generate_ui_json()
                        self.data_generator.save_ui_data(ui_data)
                    time.sleep(UIConfig.DATA_REFRESH_INTERVAL / 1000.0)  # Convert to seconds
                except Exception as e:
                    print(f"Error in data monitoring: {e}")
                    time.sleep(5)  # Wait before retrying
        
        self.monitoring_thread = threading.Thread(target=monitor_data, daemon=True)
        self.monitoring_thread.start()
    
    def run(self):
        """Run the UI system"""
        try:
            print("Starting CONJURE UI System...")
            
            # Initialize components
            self.initialize()
            
            # Generate initial UI data
            print("Generating initial UI data...")
            ui_data = self.data_generator.generate_ui_json()
            self.data_generator.save_ui_data(ui_data)
            
            # Start background monitoring
            self.running = True
            self.start_data_monitoring()
            
            # Run main UI
            print("Launching main UI...")
            exit_code = self.main_ui.run()
            
            # Cleanup
            self.shutdown()
            
            return exit_code
            
        except Exception as e:
            print(f"Error running UI system: {e}")
            self.shutdown()
            return 1
    
    def shutdown(self):
        """Clean shutdown of all components"""
        print("Shutting down CONJURE UI System...")
        
        self.running = False
        
        # Stop timers
        if hasattr(self, 'workflow_timer'):
            self.workflow_timer.stop()
        
        # Hide workflow overlay
        if self.workflow_overlay:
            self.workflow_overlay.hide_overlay()
        
        # Wait for monitoring thread to finish
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            print("Waiting for monitoring thread to finish...")
            self.monitoring_thread.join(timeout=2)
        
        print("CONJURE UI System shutdown complete")

def main():
    """Main entry point"""
    try:
        system = ConjureUISystem()
        exit_code = system.run()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
