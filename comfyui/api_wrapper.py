"""
ComfyUI API wrapper for CONJURE.
Handles workflow loading and execution.
"""

import requests
from pathlib import Path

class ComfyUIAPI:
    def __init__(self, host: str = "localhost", port: int = 8188):
        self.base_url = f"http://{host}:{port}"
        
    def load_workflow(self, workflow_path: Path) -> dict:
        """Load a workflow from a JSON file."""
        pass
    
    def execute_workflow(self, workflow: dict) -> dict:
        """Execute a loaded workflow."""
        pass 