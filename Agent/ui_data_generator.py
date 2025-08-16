"""
UI Data Generator for CONJURE
Aggregates data from multiple sources into unified UI JSON for display
"""

import json
import os
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNCOMFY_DIR = PROJECT_ROOT / "runcomfy"

# Data source paths
STATE_JSON = DATA_DIR / "input" / "state.json"
FINGERTIPS_JSON = DATA_DIR / "input" / "fingertips.json"
TRANSCRIPT_DEBUG = PROJECT_ROOT / "transcript_debug.txt"
ELEVENLABS_LOG = PROJECT_ROOT / "elevenlabs_transcript_log.txt"
RUNCOMFY_STATE = RUNCOMFY_DIR / "dev_server_state.json"
UI_OUTPUT = PROJECT_ROOT / "Agent" / "ui_data.json"

@dataclass
class ConversationMessage:
    timestamp: str
    speaker: str
    message: str
    source: str

@dataclass
class CommandStatus:
    command: str
    parameters: Dict[str, Any]
    status: str
    phase: str
    timestamp: str

@dataclass
class BrushInfo:
    active_command: str
    active_hand: Optional[str]
    scale_axis: str
    fingertip_count: int

@dataclass
class WorkflowProgress:
    active: bool
    overall_progress: float
    current_stage: str
    current_node: str
    estimated_time_remaining: str

@dataclass
class UIData:
    conversation: List[ConversationMessage]
    current_command: CommandStatus
    brush_info: BrushInfo
    workflow_progress: WorkflowProgress

class UIDataGenerator:
    def __init__(self):
        self.last_check_times = {}
        self.conversation_cache = []
        self.max_conversation_length = 50
        
    def load_state_data(self) -> Dict[str, Any]:
        """Load main application state from state.json"""
        try:
            if STATE_JSON.exists():
                with open(STATE_JSON, 'r') as f:
                    return json.load(f)
            else:
                print(f"Warning: {STATE_JSON} not found")
                return self._default_state()
        except Exception as e:
            print(f"Error loading state data: {e}")
            return self._default_state()
    
    def _default_state(self) -> Dict[str, Any]:
        """Default state when file is missing or corrupted"""
        return {
            "app_status": "unknown",
            "command": "idle",
            "current_phase": "I",
            "primitive_type": "None"
        }
    
    def load_conversation_data(self) -> List[ConversationMessage]:
        """Parse transcript files to extract conversation history"""
        messages = []
        
        # Load from transcript_debug.txt (primary source)
        if TRANSCRIPT_DEBUG.exists():
            messages.extend(self._parse_transcript_debug())
        
        # Load from elevenlabs log (agent responses)
        if ELEVENLABS_LOG.exists():
            messages.extend(self._parse_elevenlabs_log())
        
        # Sort by timestamp and keep recent messages
        messages.sort(key=lambda x: x.timestamp)
        return messages[-self.max_conversation_length:]
    
    def _parse_transcript_debug(self) -> List[ConversationMessage]:
        """Parse transcript_debug.txt for conversation messages"""
        messages = []
        try:
            with open(TRANSCRIPT_DEBUG, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse different message formats
                    # [14:30:15] [AGENT_TURN] MESSAGE: Welcome to Conjure...
                    agent_match = re.match(r'\[([^\]]+)\] \[AGENT_TURN\] MESSAGE: (.+)', line)
                    if agent_match:
                        timestamp, message = agent_match.groups()
                        messages.append(ConversationMessage(
                            timestamp=timestamp,
                            speaker="AGENT",
                            message=message,
                            source="debug"
                        ))
                        continue
                    
                    # [14:30:20] [USER_TURN] MESSAGE: I want to create...
                    user_match = re.match(r'\[([^\]]+)\] \[USER_TURN\] MESSAGE: (.+)', line)
                    if user_match:
                        timestamp, message = user_match.groups()
                        messages.append(ConversationMessage(
                            timestamp=timestamp,
                            speaker="USER",
                            message=message,
                            source="debug"
                        ))
                        continue
                    
                    # USER (Whisper): I want to create an alien head
                    whisper_match = re.match(r'USER \(Whisper\): (.+)', line)
                    if whisper_match:
                        message = whisper_match.group(1)
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        messages.append(ConversationMessage(
                            timestamp=timestamp,
                            speaker="USER",
                            message=message,
                            source="whisper"
                        ))
                        continue
                        
        except Exception as e:
            print(f"Error parsing transcript debug: {e}")
        
        return messages
    
    def _parse_elevenlabs_log(self) -> List[ConversationMessage]:
        """Parse elevenlabs log for agent responses"""
        messages = []
        try:
            with open(ELEVENLABS_LOG, 'r') as f:
                content = f.read().strip()
                if content and content != f"Log started at {os.path.getmtime(ELEVENLABS_LOG)}":
                    # Parse actual log content if available
                    lines = content.split('\n')
                    for line in lines:
                        if line.strip() and not line.startswith('Log started'):
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            messages.append(ConversationMessage(
                                timestamp=timestamp,
                                speaker="AGENT",
                                message=line.strip(),
                                source="elevenlabs"
                            ))
        except Exception as e:
            print(f"Error parsing elevenlabs log: {e}")
        
        return messages
    
    def load_fingertip_data(self) -> BrushInfo:
        """Extract brush/tool info from fingertips.json"""
        try:
            if FINGERTIPS_JSON.exists():
                with open(FINGERTIPS_JSON, 'r') as f:
                    data = json.load(f)
                
                # Determine active hand
                active_hand = None
                fingertip_count = 0
                
                if data.get("left_hand") and data["left_hand"] != "null":
                    active_hand = "left"
                    fingertip_count = len(data["left_hand"].get("fingertips", []))
                elif data.get("right_hand") and data["right_hand"] != "null":
                    active_hand = "right"
                    fingertip_count = len(data["right_hand"].get("fingertips", []))
                
                return BrushInfo(
                    active_command=data.get("command", "idle"),
                    active_hand=active_hand,
                    scale_axis=data.get("scale_axis", "XYZ"),
                    fingertip_count=fingertip_count
                )
            else:
                return self._default_brush_info()
        except Exception as e:
            print(f"Error loading fingertip data: {e}")
            return self._default_brush_info()
    
    def _default_brush_info(self) -> BrushInfo:
        """Default brush info when file is missing"""
        return BrushInfo(
            active_command="idle",
            active_hand=None,
            scale_axis="XYZ",
            fingertip_count=0
        )
    
    def load_workflow_progress(self) -> WorkflowProgress:
        """Get workflow progress from runcomfy status"""
        try:
            # Check if workflow is active from state
            state_data = self.load_state_data()
            is_workflow_active = state_data.get("command") == "generate_flux_mesh"
            
            if not is_workflow_active:
                return WorkflowProgress(
                    active=False,
                    overall_progress=0.0,
                    current_stage="Idle",
                    current_node="None",
                    estimated_time_remaining="N/A"
                )
            
            # Load runcomfy state if available
            if RUNCOMFY_STATE.exists():
                with open(RUNCOMFY_STATE, 'r') as f:
                    runcomfy_data = json.load(f)
                
                # Basic progress estimation based on status
                progress = 0.0
                stage = "Initializing"
                
                if runcomfy_data.get("status") == "running":
                    progress = 25.0
                    stage = "FLUX Generation"
                elif runcomfy_data.get("health_status") == "healthy":
                    progress = 50.0
                    stage = "Processing"
                
                return WorkflowProgress(
                    active=True,
                    overall_progress=progress,
                    current_stage=stage,
                    current_node="ComfyUI",
                    estimated_time_remaining="Calculating..."
                )
            else:
                # Workflow active but no detailed progress
                return WorkflowProgress(
                    active=True,
                    overall_progress=10.0,
                    current_stage="Starting",
                    current_node="Initializing",
                    estimated_time_remaining="Unknown"
                )
                
        except Exception as e:
            print(f"Error loading workflow progress: {e}")
            return WorkflowProgress(
                active=False,
                overall_progress=0.0,
                current_stage="Error",
                current_node="N/A",
                estimated_time_remaining="N/A"
            )
    
    def generate_ui_json(self) -> UIData:
        """Create unified data structure for UI"""
        # Load all data sources
        state_data = self.load_state_data()
        conversation = self.load_conversation_data()
        brush_info = self.load_fingertip_data()
        workflow_progress = self.load_workflow_progress()
        
        # Create command status
        current_command = CommandStatus(
            command=state_data.get("command", "idle"),
            parameters=state_data.get("flux_pipeline_request", {}),
            status=state_data.get("app_status", "unknown"),
            phase=state_data.get("current_phase", "I"),
            timestamp=datetime.now().strftime("%H:%M:%S")
        )
        
        return UIData(
            conversation=conversation,
            current_command=current_command,
            brush_info=brush_info,
            workflow_progress=workflow_progress
        )
    
    def save_ui_data(self, ui_data: UIData):
        """Save UI data to JSON file"""
        try:
            # Ensure output directory exists
            UI_OUTPUT.parent.mkdir(exist_ok=True)
            
            # Convert to dict for JSON serialization
            data_dict = asdict(ui_data)
            
            with open(UI_OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, indent=2, ensure_ascii=False)
            
            print(f"UI data updated: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            print(f"Error saving UI data: {e}")
    
    def has_data_changed(self) -> bool:
        """Check if any source files have been modified"""
        files_to_check = [STATE_JSON, FINGERTIPS_JSON, TRANSCRIPT_DEBUG, ELEVENLABS_LOG, RUNCOMFY_STATE]
        
        for file_path in files_to_check:
            if not file_path.exists():
                continue
                
            current_mtime = os.path.getmtime(file_path)
            last_mtime = self.last_check_times.get(str(file_path), 0)
            
            if current_mtime > last_mtime:
                self.last_check_times[str(file_path)] = current_mtime
                return True
        
        return False
    
    def monitor_and_update(self, interval: float = 5.0):
        """Monitor files and update UI data when changes detected"""
        print("Starting UI data monitoring...")
        
        # Initial generation
        ui_data = self.generate_ui_json()
        self.save_ui_data(ui_data)
        
        try:
            while True:
                time.sleep(interval)
                
                if self.has_data_changed():
                    print("Data changes detected, updating UI...")
                    ui_data = self.generate_ui_json()
                    self.save_ui_data(ui_data)
                    
        except KeyboardInterrupt:
            print("UI data monitoring stopped")

def main():
    """Main function for standalone execution"""
    generator = UIDataGenerator()
    
    # Generate once and save
    ui_data = generator.generate_ui_json()
    generator.save_ui_data(ui_data)
    
    # Or run continuous monitoring
    # generator.monitor_and_update()

if __name__ == "__main__":
    main()
