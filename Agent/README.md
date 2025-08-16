# CONJURE UI System

A comprehensive, transparent overlay UI for the CONJURE 3D modeling system. Provides real-time visibility into system status, conversations, and workflow progress.

## Overview

The CONJURE UI is designed as a **read-only informational display** that shows system activity without interfering with voice/camera interactions. It features:

- **Transparent overlay design** - Non-intrusive, always-on-top display
- **Real-time data updates** - Live monitoring of system state
- **Conversation tracking** - Display of user-agent interactions
- **Workflow progress** - Semi-transparent overlay during mesh generation
- **Brush/tool status** - Current hand tracking and active tools

## Components

### Core Files

1. **`ui_data_generator.py`** - Aggregates data from multiple sources
2. **`conjure_ui.py`** - Main transparent overlay UI
3. **`workflow_overlay.py`** - Progress overlay for mesh generation
4. **`ui_config.py`** - Central configuration and styling
5. **`conjure_ui_launcher.py`** - Integrated launcher script

### Supporting Files

- **`UIplan.txt`** - Comprehensive implementation plan
- **`test_ui.py`** - Test suite for all components
- **`README.md`** - This documentation

## Data Sources

The UI aggregates information from:

- `data/input/state.json` - Main application state
- `data/input/fingertips.json` - Hand tracking and brush data
- `transcript_debug.txt` - Conversation transcriptions
- `elevenlabs_transcript_log.txt` - Agent responses
- `runcomfy/dev_server_state.json` - Workflow progress

## Installation & Setup

### Prerequisites

- Python 3.7+
- PyQt5
- CONJURE project structure

### Quick Start

1. **Run the integrated launcher:**
   ```bash
   python Agent/conjure_ui_launcher.py
   ```

2. **Run individual components:**
   ```bash
   # Main UI only
   python Agent/conjure_ui.py
   
   # Data generator only
   python Agent/ui_data_generator.py
   
   # Workflow overlay test
   python Agent/workflow_overlay.py
   ```

3. **Run tests:**
   ```bash
   python Agent/test_ui.py
   ```

## UI Layout

### Main Overlay (Right Side)
- **Top Panel:** Current phase and system status
- **Middle Panel:** Conversation history (scrollable)
- **Bottom Panel:** Active brush/tool information

### Workflow Overlay (Full Screen)
- **Semi-transparent backdrop** with "MESH GENERATION" text
- **Progress bar** with real-time updates
- **Current stage/node** information
- **Estimated time remaining**

## Key Features

### Transparent Design
- Frameless, translucent windows
- Always stays on top
- Non-intrusive visual styling
- Inspired by the excellent UI.py reference

### Real-Time Updates
- 5-second refresh interval for main UI
- 1-second checks for workflow status
- File monitoring for instant updates
- Smooth animations and transitions

### Conversation Display
- Color-coded messages (blue for user, green for agent)
- Timestamps for all interactions
- Auto-scroll to latest messages
- Support for multiple transcript sources

### Status Information
- Current command and parameters
- Phase indicators (I, II, III, IV)
- System status with color coding
- Last update timestamps

### Hand Tracking Display
- Active hand indicator (left/right)
- Current tool/brush mode
- Fingertip count
- Scale axis information

### Workflow Progress
- Automatic activation during mesh generation
- Real-time progress tracking
- Stage-by-stage breakdown
- Completion notifications

## Configuration

### UI Settings (`ui_config.py`)
```python
# Refresh intervals
DATA_REFRESH_INTERVAL = 5000  # 5 seconds
WORKFLOW_CHECK_INTERVAL = 1000  # 1 second

# Panel sizes
CONVERSATION_PANEL_SIZE = (400, 300)
STATUS_PANEL_SIZE = (300, 150)
BRUSH_PANEL_SIZE = (250, 120)

# Colors and styling
Colors.USER_MESSAGE = "#80c0ff"
Colors.AGENT_MESSAGE = "#80ff80"
```

### Data Limits
- Maximum 50 conversation messages stored
- Display recent 20 messages
- 1MB maximum log file size

## Usage Examples

### Standalone Data Generation
```python
from ui_data_generator import UIDataGenerator

generator = UIDataGenerator()
ui_data = generator.generate_ui_json()
generator.save_ui_data(ui_data)
```

### Custom UI Integration
```python
from conjure_ui import ConjureUI

app = ConjureUI(sys.argv)
app.run()
```

### Workflow Overlay Control
```python
from workflow_overlay import WorkflowOverlayManager

manager = WorkflowOverlayManager()
manager.show_overlay()  # Show during generation
manager.hide_overlay()  # Hide when complete
```

## Controls

### Keyboard Shortcuts
- **ESC** - Close UI or cancel workflow
- **Mouse drag** - Move windows (when not locked)

### Mouse Interaction
- **Close button (×)** - Exit application
- **Window dragging** - Reposition overlay
- **Workflow overlay** - Click-through protection

## Data Flow

1. **File Monitoring** - `ui_data_generator.py` watches source files
2. **Data Aggregation** - Combines all sources into `ui_data.json`
3. **UI Updates** - Main UI polls for changes every 5 seconds
4. **Workflow Detection** - Launcher monitors for mesh generation
5. **Overlay Control** - Shows/hides progress overlay automatically

## Troubleshooting

### Common Issues

**UI not updating:**
- Check if data files exist in correct locations
- Verify file permissions
- Run `test_ui.py` to diagnose issues

**Workflow overlay not showing:**
- Ensure `state.json` contains `"command": "generate_flux_mesh"`
- Check runcomfy state files
- Verify QApplication instance

**Import errors:**
- Install PyQt5: `pip install PyQt5`
- Check Python path includes Agent directory
- Verify all files are present

### Debug Mode

Enable debug output:
```python
# In ui_data_generator.py
print(f"UI data updated: {datetime.now().strftime('%H:%M:%S')}")

# In conjure_ui.py  
print("No UI data available")
```

### Log Files

Check these locations for debugging:
- `transcript_debug.txt` - Conversation logs
- `elevenlabs_transcript_log.txt` - Agent responses
- `Agent/ui_data.json` - Current UI state

## Integration with CONJURE

### Launcher Integration
Add to `launcher/main.py`:
```python
# Start UI system
ui_system = ConjureUISystem()
ui_thread = threading.Thread(target=ui_system.run, daemon=True)
ui_thread.start()
```

### State Updates
The UI automatically detects changes in:
- Backend agent commands
- Conversation transcripts
- Hand tracking data
- Workflow progress

### Workflow Coordination
The UI coordinates with:
- RunComfy workflow execution
- Blender operations
- Hand gesture recognition
- Voice processing

## Advanced Usage

### Custom Panels
Extend the UI with additional panels:
```python
class CustomPanel(MinimalFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Custom implementation
```

### Data Source Extensions
Add new data sources:
```python
# In ui_data_generator.py
def load_custom_data(self):
    # Custom data loading logic
    return custom_data
```

### Styling Customization
Modify `ui_config.py` for custom themes:
```python
# Custom color scheme
class DarkTheme(Colors):
    PANEL_BACKGROUND = "rgba(10, 10, 10, 160)"
    TEXT_PRIMARY = "rgba(255, 255, 255, 200)"
```

## Performance Notes

- UI refresh limited to 5-second intervals
- File monitoring uses efficient change detection
- Smooth animations with Qt property animations
- Memory management for conversation history
- Optimized for always-on operation

## Future Enhancements

- Network status monitoring
- Performance metrics display
- User preference storage
- Multi-monitor support
- Accessibility features
- Plugin architecture

---

*Built with PyQt5 and designed for seamless integration with the CONJURE 3D modeling system.*
