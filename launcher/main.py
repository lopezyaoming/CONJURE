"""
Main controller (.exe entry point)
This is the main entry point for the CONJURE application.
It orchestrates the various components like the hand tracker, Blender,
and eventually the AI agent and GUI.
"""
import time
import atexit

from subprocess_manager import SubprocessManager
from state_manager import StateManager

class ConjureApp:
    def __init__(self):
        print("Initializing CONJURE...")
        self.subprocess_manager = SubprocessManager()
        self.state_manager = StateManager()
        # Ensure processes are cleaned up on exit, even if the script crashes.
        atexit.register(self.stop)

    def start(self):
        """Starts all the necessary components of the application."""
        print("CONJURE application starting...")
        self.state_manager.set_state("app_status", "running")

        # Start background processes
        self.subprocess_manager.start_hand_tracker()
        self.state_manager.set_state("hand_tracker_status", "running")

        # A small delay to ensure the hand tracker has time to initialize
        # and create the initial fingertips.json file before Blender starts.
        print("Waiting for hand tracker to initialize...")
        time.sleep(3)

        self.subprocess_manager.start_blender()
        self.state_manager.set_state("blender_status", "running")

        print("\nCONJURE is now running. Close the Blender window or press Ctrl+C here to exit.")

    def run(self):
        """Main application loop. Monitors the state of subprocesses."""
        try:
            while self.state_manager.get_state("app_status") == "running":
                # Check if the Blender process has been closed by the user
                blender_process = self.subprocess_manager.processes.get('blender')
                if blender_process and blender_process.poll() is not None:
                    print("Blender window was closed. Shutting down.")
                    break # Exit the loop to trigger the shutdown sequence

                time.sleep(1)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt detected. Shutting down CONJURE.")
        finally:
            self.stop()

    def stop(self):
        """Stops all components and gracefully exits."""
        # Check if already stopped to prevent multiple calls from atexit
        if self.state_manager.get_state("app_status") == "stopped":
            return
            
        print("CONJURE application stopping...")
        self.subprocess_manager.stop_all()
        self.state_manager.set_state("app_status", "stopped")
        self.state_manager.set_state("hand_tracker_status", "stopped")
        self.state_manager.set_state("blender_status", "stopped")
        print("CONJURE has stopped.")


if __name__ == "__main__":
    app = ConjureApp()
    app.start()
    app.run() 