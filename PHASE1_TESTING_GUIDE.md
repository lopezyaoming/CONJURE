# CONJURE Phase 1 Testing Guide

## Overview
This guide provides step-by-step instructions to verify that all Phase 1 simplifications work correctly before implementing Phase 2. Follow each test in order to ensure the foundation is solid.

---

## 🧪 **Test Environment Setup**

### Prerequisites
1. **Python Environment**: Ensure Python 3.7+ is available
2. **API Keys**: Required environment variables set:
   ```bash
   export OPENAI_API_KEY="your_openai_key"
   export HUGGINGFACE_HUB_ACCESS_TOKEN="your_huggingface_token"
   ```
3. **Project Structure**: All Phase 1 files are in place

### Quick Environment Check
```bash
# Navigate to project root
cd path/to/CONJURE

# Check Python availability
python --version
# OR
py --version

# Verify key files exist
ls launcher/main.py
ls launcher/backend_agent.py
ls launcher/instruction_manager.py
```

---

## 🔍 **Test 1: Backend Agent Simplification**

### Purpose
Verify the backend agent processes voice input and generates structured FLUX prompts without conversation logic.

### Test Steps

#### 1.1 Manual Backend Agent Test
```python
# Create test script: test_backend_manual.py
from launcher.backend_agent import BackendAgent
from launcher.instruction_manager import InstructionManager
from launcher.state_manager import StateManager

# Initialize components
state_manager = StateManager()
instruction_manager = InstructionManager(state_manager)
backend_agent = BackendAgent(instruction_manager)

# Test voice input processing
test_cases = [
    {
        "speech": "I want a modern chair",
        "current_prompt": "",
        "expected": "chair with modern design elements"
    },
    {
        "speech": "make it more curved and metallic",
        "current_prompt": "modern office chair",
        "expected": "curved form, metallic materials"
    },
    {
        "speech": "change the color to blue",
        "current_prompt": "ergonomic chair with curved form, aluminum materials",
        "expected": "blue color keywords"
    }
]

for i, test_case in enumerate(test_cases):
    print(f"\n--- Test Case {i+1} ---")
    print(f"Speech: '{test_case['speech']}'")
    print(f"Current: '{test_case['current_prompt']}'")
    
    result = backend_agent.process_voice_input(
        speech_transcript=test_case["speech"],
        current_prompt_state=test_case["current_prompt"]
    )
    
    if result:
        print("✅ Backend agent responded")
        
        # Check userPrompt.txt was updated
        with open("data/generated_text/userPrompt.txt", "r") as f:
            generated_prompt = f.read()
        
        print(f"Generated: {generated_prompt[:150]}...")
        
        # Verify it contains expected elements
        if test_case["expected"].lower() in generated_prompt.lower():
            print("✅ Contains expected elements")
        else:
            print("⚠️ Missing expected elements")
    else:
        print("❌ Backend agent failed")
```

#### 1.2 Expected Results
- ✅ Backend agent initializes without errors
- ✅ `process_voice_input()` method exists and works
- ✅ Returns structured JSON response
- ✅ Updates `data/generated_text/userPrompt.txt`
- ✅ Generated prompts include professional photography setup
- ✅ Prompts maintain continuity with previous state

#### 1.3 Validation Checklist
- [ ] No conversation analysis logic present
- [ ] No tool execution decisions made
- [ ] Structured JSON schema returned: `{"subject": {"name": "...", "form_keywords": [...], ...}}`
- [ ] Photography setup appended: "Shown in a three-quarter view..."
- [ ] userPrompt.txt file updated with full FLUX prompt

---

## 🔍 **Test 2: Instruction Manager Simplification**

### Purpose
Verify instruction manager only handles `generate_flux_mesh` and executes without complex logic.

### Test Steps

#### 2.1 Tool Map Verification
```python
# Create test script: test_instruction_manager.py
from launcher.instruction_manager import InstructionManager
from launcher.state_manager import StateManager

# Initialize
state_manager = StateManager()
instruction_manager = InstructionManager(state_manager)

# Check tool map
print("Available tools:", list(instruction_manager.tool_map.keys()))

# Should only show: ['generate_flux_mesh']
assert len(instruction_manager.tool_map) == 1
assert "generate_flux_mesh" in instruction_manager.tool_map
print("✅ Tool map simplified correctly")
```

#### 2.2 Instruction Execution Test
```python
# Test generate_flux_mesh execution
test_instruction = {
    "tool_name": "generate_flux_mesh",
    "parameters": {
        "prompt": "modern ergonomic chair with sleek aluminum finish",
        "seed": 42,
        "min_volume_threshold": 0.001
    }
}

print("Executing test instruction...")
instruction_manager.execute_instruction(test_instruction)

# Check state was updated
current_state = state_manager.get_state()
print("State after execution:", current_state)

# Verify flux pipeline request was set
assert current_state.get("flux_pipeline_request") == "new"
assert current_state.get("flux_prompt") == test_instruction["parameters"]["prompt"]
assert current_state.get("flux_seed") == 42
print("✅ Instruction executed correctly")
```

#### 2.3 Invalid Tool Test
```python
# Test invalid tool handling
invalid_instruction = {
    "tool_name": "spawn_primitive",  # This should no longer work
    "parameters": {"primitive_type": "Cube"}
}

print("Testing invalid tool...")
instruction_manager.execute_instruction(invalid_instruction)
# Should print error message about unknown tool
print("✅ Invalid tool handled correctly")
```

#### 2.4 Expected Results
- ✅ Only `generate_flux_mesh` in tool map
- ✅ No deduplication logic present
- ✅ No conversation-triggered execution
- ✅ Direct state updates for FLUX pipeline
- ✅ Clear error messages for invalid tools

---

## 🔍 **Test 3: Main Launcher Without Conversational Agent**

### Purpose
Verify main launcher starts without conversational agent and maintains core functionality.

### Test Steps

#### 3.1 Import Test
```python
# Create test script: test_main_launcher.py
try:
    from launcher.main import ConjureAgents
    print("✅ Main launcher imports successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
```

#### 3.2 Initialization Test
```python
# Test initialization without conversational agent
try:
    agents = ConjureAgents(is_debug_mode=False)
    print("✅ ConjureAgents initialized")
    
    # Check components
    assert hasattr(agents, 'backend_agent'), "Backend agent missing"
    assert hasattr(agents, 'instruction_manager'), "Instruction manager missing"
    assert hasattr(agents, 'state_manager'), "State manager missing"
    
    # Check conversational agent is NOT present
    assert not hasattr(agents, 'conversational_agent'), "Conversational agent should be removed"
    
    print("✅ All required components present")
    print("✅ Conversational agent successfully removed")
    
except Exception as e:
    print(f"❌ Initialization failed: {e}")
```

#### 3.3 Component Integration Test
```python
# Test that components work together
try:
    # Test backend agent -> instruction manager flow
    result = agents.backend_agent.process_voice_input(
        speech_transcript="create a modern lamp",
        current_prompt_state=""
    )
    
    if result:
        # Test instruction manager execution
        test_instruction = {
            "tool_name": "generate_flux_mesh",
            "parameters": {
                "prompt": "modern table lamp with minimalist design",
                "seed": 123
            }
        }
        
        agents.instruction_manager.execute_instruction(test_instruction)
        
        # Check state coordination
        current_state = agents.state_manager.get_state()
        if current_state.get("flux_pipeline_request") == "new":
            print("✅ Components integrated successfully")
        else:
            print("⚠️ State coordination issue")
    
except Exception as e:
    print(f"❌ Component integration failed: {e}")
```

#### 3.4 Expected Results
- ✅ ConjureAgents class initializes without errors
- ✅ No conversational agent attributes
- ✅ Backend agent and instruction manager present
- ✅ Components communicate correctly
- ✅ State updates propagate properly

---

## 🔍 **Test 4: File System Integration**

### Purpose
Verify all file operations work correctly in the simplified workflow.

### Test Steps

#### 4.1 Data Directory Structure Test
```python
# Create test script: test_file_system.py
from pathlib import Path

# Check required directories exist
required_dirs = [
    "data/input",
    "data/generated_text",
    "data/generated_images/gestureCamera",
    "data/generated_models"
]

for dir_path in required_dirs:
    path = Path(dir_path)
    if path.exists():
        print(f"✅ {dir_path} exists")
    else:
        print(f"⚠️ Creating {dir_path}")
        path.mkdir(parents=True, exist_ok=True)
```

#### 4.2 State File Operations Test
```python
from launcher.state_manager import StateManager

# Test state file read/write with new simplified format
state_manager = StateManager()

# Test write
test_state = {
    "flux_pipeline_request": "new",
    "flux_prompt": "test prompt for file operations",
    "flux_seed": 999
}

state_manager.update_state(test_state)
print("✅ State write successful")

# Test read
retrieved_state = state_manager.get_state()
assert retrieved_state.get("flux_prompt") == "test prompt for file operations"
print("✅ State read successful")
```

#### 4.3 UserPrompt.txt Generation Test
```python
# Test prompt file generation
from launcher.backend_agent import BackendAgent
from launcher.instruction_manager import InstructionManager

# Initialize and test
state_manager = StateManager()
instruction_manager = InstructionManager(state_manager)
backend_agent = BackendAgent(instruction_manager)

# Process voice input
result = backend_agent.process_voice_input(
    speech_transcript="create a futuristic robot",
    current_prompt_state=""
)

# Check file was created/updated
prompt_file = Path("data/generated_text/userPrompt.txt")
if prompt_file.exists():
    with open(prompt_file, 'r') as f:
        content = f.read()
    
    if "futuristic robot" in content.lower():
        print("✅ userPrompt.txt updated correctly")
    else:
        print("⚠️ userPrompt.txt content issue")
else:
    print("❌ userPrompt.txt not created")
```

#### 4.4 Expected Results
- ✅ All required directories exist
- ✅ State file operations work reliably
- ✅ userPrompt.txt updates correctly
- ✅ File permissions work (no PermissionError)

---

## 🔍 **Test 5: API Integration Readiness**

### Purpose
Verify the system is ready for Phase 2 API integrations.

### Test Steps

#### 5.1 OpenAI API Connection Test
```python
# Create test script: test_api_readiness.py
import os
from openai import OpenAI

# Test OpenAI connection
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    try:
        client = OpenAI(api_key=api_key)
        # Simple test call
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print("✅ OpenAI API connection working")
    except Exception as e:
        print(f"⚠️ OpenAI API issue: {e}")
else:
    print("⚠️ OPENAI_API_KEY not set")
```

#### 5.2 HuggingFace Token Test
```python
import os

# Test HuggingFace token
hf_token = os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN")
if hf_token:
    print("✅ HuggingFace token available")
    print(f"Token length: {len(hf_token)} characters")
else:
    print("⚠️ HUGGINGFACE_HUB_ACCESS_TOKEN not set")
```

#### 5.3 Backend Agent JSON Response Test
```python
# Test structured JSON response format
from launcher.backend_agent import BackendAgent
from launcher.instruction_manager import InstructionManager
from launcher.state_manager import StateManager

# Initialize
state_manager = StateManager()
instruction_manager = InstructionManager(state_manager)
backend_agent = BackendAgent(instruction_manager)

# Test with actual API call (if keys available)
if os.getenv("OPENAI_API_KEY"):
    try:
        result = backend_agent.process_voice_input(
            speech_transcript="modern minimalist vase",
            current_prompt_state=""
        )
        
        if result and isinstance(result, dict):
            if "subject" in result:
                subject = result["subject"]
                required_keys = ["name", "form_keywords", "material_keywords", "color_keywords"]
                
                if all(key in subject for key in required_keys):
                    print("✅ Structured JSON format correct")
                else:
                    print("⚠️ Missing required JSON keys")
            else:
                print("⚠️ Missing 'subject' in response")
        else:
            print("⚠️ Invalid response format")
            
    except Exception as e:
        print(f"⚠️ API call failed: {e}")
```

#### 5.4 Expected Results
- ✅ OpenAI API accessible with provided key
- ✅ HuggingFace token available
- ✅ Backend agent returns proper JSON structure
- ✅ No conversation-related API calls

---

## 🔍 **Test 6: Error Handling & Edge Cases**

### Purpose
Verify system handles errors gracefully in simplified workflow.

### Test Steps

#### 6.1 Missing Parameters Test
```python
# Test instruction with missing parameters
from launcher.instruction_manager import InstructionManager
from launcher.state_manager import StateManager

state_manager = StateManager()
instruction_manager = InstructionManager(state_manager)

# Test missing prompt
invalid_instruction = {
    "tool_name": "generate_flux_mesh",
    "parameters": {
        "seed": 42
        # Missing "prompt" parameter
    }
}

print("Testing missing parameters...")
instruction_manager.execute_instruction(invalid_instruction)
# Should handle gracefully with error message
print("✅ Missing parameters handled")
```

#### 6.2 Empty Voice Input Test
```python
# Test empty/invalid voice input
from launcher.backend_agent import BackendAgent
from launcher.instruction_manager import InstructionManager
from launcher.state_manager import StateManager

# Initialize
state_manager = StateManager()
instruction_manager = InstructionManager(state_manager)
backend_agent = BackendAgent(instruction_manager)

# Test empty speech
test_cases = ["", "   ", "um...", "what?"]

for speech in test_cases:
    print(f"Testing speech: '{speech}'")
    try:
        result = backend_agent.process_voice_input(
            speech_transcript=speech,
            current_prompt_state="chair"
        )
        print(f"Result: {type(result)}")
    except Exception as e:
        print(f"Error: {e}")
```

#### 6.3 File Permission Test
```python
# Test file operations under various conditions
from pathlib import Path
import os

# Test directory creation
test_dir = Path("data/test_temp")
test_dir.mkdir(parents=True, exist_ok=True)
print("✅ Directory creation works")

# Test file write/read
test_file = test_dir / "test.txt"
with open(test_file, 'w') as f:
    f.write("test content")

with open(test_file, 'r') as f:
    content = f.read()

assert content == "test content"
print("✅ File operations work")

# Cleanup
test_file.unlink()
test_dir.rmdir()
print("✅ File cleanup works")
```

#### 6.4 Expected Results
- ✅ Graceful handling of missing parameters
- ✅ Sensible defaults for empty voice input
- ✅ Robust file operations
- ✅ Clear error messages without crashes

---

## 📋 **Complete Testing Checklist**

### Core Functionality
- [ ] Backend agent processes voice input correctly
- [ ] Structured FLUX prompts generated
- [ ] userPrompt.txt updated with professional format
- [ ] Instruction manager executes only generate_flux_mesh
- [ ] State updates propagate correctly
- [ ] Main launcher starts without conversational agent

### Integration
- [ ] Components communicate properly
- [ ] File operations work reliably
- [ ] API connections functional
- [ ] Error handling graceful

### Simplification Verification
- [ ] No conversational agent code active
- [ ] No conversation analysis logic
- [ ] No complex deduplication
- [ ] No tool execution decisions
- [ ] Only generate_flux_mesh available

### Phase 2 Readiness
- [ ] Voice input processing pipeline works
- [ ] Prompt generation reliable
- [ ] State management simplified
- [ ] API integrations ready
- [ ] File system operations stable

---

## 🚀 **Ready for Phase 2 Criteria**

Phase 1 is complete and ready for Phase 2 when:

1. **All tests pass** without errors
2. **No conversational agent dependencies** remain
3. **Backend agent** processes voice → structured prompts reliably
4. **Instruction manager** executes generate_flux_mesh only
5. **File operations** work smoothly
6. **API connections** are functional
7. **Error handling** is graceful

### Next Steps After Successful Testing
Once all tests pass, you're ready to implement:
- **Phase 2: Continuous Loop System** (30-second cycles)
- **Real-time voice processing**
- **Automatic generation triggers**
- **Streamlined UI updates**

---

## 🆘 **Troubleshooting Common Issues**

### Backend Agent Issues
- **"Missing system prompt"**: Check backend_agent.py system_prompt initialization
- **"No structured response"**: Verify OpenAI API key and model access
- **"userPrompt.txt not updated"**: Check file permissions and directory structure

### Instruction Manager Issues  
- **"Unknown tool"**: Verify only generate_flux_mesh in tool_map
- **"State not updated"**: Check state_manager integration

### Main Launcher Issues
- **"ConversationalAgent errors"**: Ensure all conversational agent code is commented out
- **"Component missing"**: Verify initialization order in __init__ method

### File System Issues
- **"Permission denied"**: Check data directory permissions
- **"File not found"**: Verify directory structure exists

Run this testing guide completely before proceeding to Phase 2 implementation!
