# RunComfy Development Server

Fast iteration development workflow for CONJURE's RunComfy cloud integration.

## Quick Start

### 1. Setup Credentials
Ensure your `runcomfy/credentials.txt` contains:
```
userID:"your-user-id"
RUNCOMFY_API_TOKEN:"your-api-token"
version_id: "your-workflow-version-id"
```

### 2. Launch Development Server
```bash
# Launch server (one time per development session)
python runcomfy/dev_server_startup.py

# Choose server type and duration
python runcomfy/dev_server_startup.py --server-type medium --duration 3600
```

### 3. Develop Iteratively
```bash
# Run main.py multiple times using the same server
python launcher/main.py  # Uses existing server connection
python test_flux_mesh_workflow.py
python launcher/main.py  # Another iteration - no startup delay!
```

### 4. End Development Session
```bash
# Shutdown server when done
python runcomfy/dev_server_startup.py --shutdown
```

## Commands

### Server Management
```bash
# Launch server
python runcomfy/dev_server_startup.py

# Check server status
python runcomfy/dev_server_startup.py --status

# Restart server
python runcomfy/dev_server_startup.py --restart

# Shutdown server
python runcomfy/dev_server_startup.py --shutdown
```

### Server Options
```bash
# Server types
--server-type medium        # Default, cheapest
--server-type large         # More powerful
--server-type extra-large   # High performance
--server-type 2x-large      # Maximum performance
--server-type 2xl-turbo     # Ultra-fast

# Duration (in seconds)
--duration 1800   # 30 minutes
--duration 3600   # 1 hour (default)
--duration 7200   # 2 hours
```

## Development Workflow

### Traditional Workflow (Slow)
```
Test 1: 3min startup + 30s execution = 3.5min
Test 2: 3min startup + 30s execution = 3.5min  
Test 3: 3min startup + 30s execution = 3.5min
Total: 10.5 minutes for 3 tests
```

### Development Server Workflow (Fast)
```
Setup:  3min startup (once per session)
Test 1: 0s startup + 30s execution = 30s
Test 2: 0s startup + 30s execution = 30s
Test 3: 0s startup + 30s execution = 30s
Total: 4.5 minutes for 3 tests (57% time savings!)
```

## State Management

### State File Location
`runcomfy/dev_server_state.json`

### State File Contents
```json
{
  "server_id": "srv-abc123",
  "user_id": "user-def456", 
  "base_url": "https://abc123.runcomfy.com",
  "status": "running",
  "launch_time": "2024-01-01T10:00:00Z",
  "workflow_version": "v1.0-abc",
  "server_type": "medium",
  "total_cost": 0.25,
  "session_cost": 0.15,
  "last_health_check": "2024-01-01T10:05:00Z",
  "health_status": "healthy"
}
```

## Health Monitoring

The system automatically:
- ✅ Validates server availability before use
- ✅ Performs health checks on server endpoints
- ✅ Cleans up invalid/unreachable servers
- ✅ Tracks server costs and uptime

## Integration with Main Application

### In main.py
The development server state is automatically detected:

```python
from runcomfy.dev_server_state import get_active_server, has_active_dev_server

# Check for active development server
if has_active_dev_server():
    server_state = get_active_server()
    # Use existing server connection
    print(f"Using dev server: {server_state.base_url}")
else:
    # Launch new server or use local mode
    print("No dev server available")
```

### In Generation Services
```python
from runcomfy.dev_server_state import validate_dev_server

async def generate_something():
    # Validate server before use
    if await validate_dev_server():
        # Use cloud mode with dev server
        server_state = get_active_server()
        # ... use server_state.base_url for requests
    else:
        # Fall back to local mode
        # ... use local HuggingFace models
```

## Cost Management

### Cost Tracking
- **Total Cost**: Cumulative cost across all sessions
- **Session Cost**: Cost for current development session
- **Real-time Updates**: Costs updated during server lifecycle

### Cost Optimization Tips
1. **Use appropriate server types** - Don't use 2xl-turbo for simple tests
2. **Set reasonable durations** - Don't launch 8-hour servers for 30-minute work
3. **Shutdown when done** - Always run `--shutdown` to avoid charges
4. **Monitor status** - Use `--status` to check costs and uptime

## Troubleshooting

### Server Won't Start
```bash
# Check credentials
cat runcomfy/credentials.txt

# Check server status
python runcomfy/dev_server_startup.py --status

# Try restart
python runcomfy/dev_server_startup.py --restart
```

### Server Not Responding
```bash
# Health check will detect this and auto-cleanup
python runcomfy/dev_server_startup.py --status

# Force restart
python runcomfy/dev_server_startup.py --restart
```

### State File Issues
```bash
# Clear corrupted state
rm runcomfy/dev_server_state.json

# Launch fresh server
python runcomfy/dev_server_startup.py
```

## Demo

Run the demo to see the development workflow in action:
```bash
python runcomfy/demo_dev_workflow.py
```

## Testing

Test the development server functionality:
```bash
# Run basic tests (no real servers)
python test_dev_server_startup.py

# Run comprehensive tests with pytest
pytest test_dev_server_startup.py

# Run tests with live servers (requires credits)
pytest test_dev_server_startup.py --live
```

---

**Benefits Summary:**
- 🚀 **80% faster iteration** - No startup delays between tests
- 💰 **Cost efficient** - Single server for multiple dev cycles  
- 🔧 **Clean separation** - Dev server independent from main.py
- 🧪 **Easy testing** - Rapid development and debugging cycles
- 📊 **Transparent monitoring** - Real-time cost and health tracking
