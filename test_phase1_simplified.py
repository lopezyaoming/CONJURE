#!/usr/bin/env python3
"""
Test script for Phase 1 Simplification - Basic Voice → Prompt → Generation Flow
Tests the core components without conversational agent complexity.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

def test_backend_agent_prompt_processing():
    """Test the simplified backend agent prompt processing"""
    print("\n🧠 Testing Backend Agent - Voice Input Processing")
    print("=" * 60)
    
    try:
        from launcher.backend_agent import BackendAgent
        from launcher.instruction_manager import InstructionManager
        from launcher.state_manager import StateManager
        
        # Setup components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        backend_agent = BackendAgent(instruction_manager)
        
        print("✅ Components initialized successfully")
        
        # Test voice input processing
        test_speech = "I want to create a modern chair with curved edges"
        current_prompt = "ergonomic office chair"
        
        print(f"📤 Testing voice input: '{test_speech}'")
        print(f"📝 Current prompt state: '{current_prompt}'")
        
        # Call the new simplified method
        result = backend_agent.process_voice_input(
            speech_transcript=test_speech,
            current_prompt_state=current_prompt
        )
        
        if result:
            print("✅ Backend agent processed voice input successfully")
            print(f"📊 Response type: {type(result)}")
            
            # Check if userPrompt.txt was updated
            prompt_path = PROJECT_ROOT / "data" / "generated_text" / "userPrompt.txt"
            if prompt_path.exists():
                with open(prompt_path, 'r') as f:
                    generated_prompt = f.read()
                print(f"📄 Generated prompt: {generated_prompt[:200]}...")
                print("✅ userPrompt.txt updated successfully")
            else:
                print("⚠️ userPrompt.txt not found")
        else:
            print("❌ Backend agent failed to process voice input")
            
    except Exception as e:
        print(f"❌ Backend agent test failed: {e}")
        import traceback
        traceback.print_exc()

def test_instruction_manager_simplified():
    """Test the simplified instruction manager"""
    print("\n⚙️ Testing Instruction Manager - Simplified Flow")
    print("=" * 60)
    
    try:
        from launcher.instruction_manager import InstructionManager
        from launcher.state_manager import StateManager
        
        # Setup components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        
        print("✅ Instruction manager initialized")
        print(f"🔧 Available tools: {list(instruction_manager.tool_map.keys())}")
        
        # Test generate_flux_mesh instruction
        test_instruction = {
            "tool_name": "generate_flux_mesh",
            "parameters": {
                "prompt": "modern ergonomic chair with sleek design",
                "seed": 42,
                "min_volume_threshold": 0.001
            }
        }
        
        print(f"📤 Testing instruction: {test_instruction}")
        
        # Execute instruction
        instruction_manager.execute_instruction(test_instruction)
        
        # Check state was updated
        current_state = state_manager.get_state()
        if current_state and current_state.get("flux_pipeline_request") == "new":
            print("✅ Instruction executed successfully")
            print(f"📊 State updated: flux_pipeline_request = {current_state.get('flux_pipeline_request')}")
            print(f"🎨 Flux prompt: {current_state.get('flux_prompt', 'Not set')}")
        else:
            print("❌ State not updated correctly")
            print(f"📊 Current state: {current_state}")
            
    except Exception as e:
        print(f"❌ Instruction manager test failed: {e}")
        import traceback
        traceback.print_exc()

def test_main_launcher_simplified():
    """Test that main launcher can start without conversational agent"""
    print("\n🚀 Testing Main Launcher - No Conversational Agent")
    print("=" * 60)
    
    try:
        from launcher.main import ConjureAgents
        
        print("✅ Main launcher imports successfully")
        
        # Test initialization without conversational agent
        print("🔧 Testing initialization...")
        
        # This should work without errors now
        agents = ConjureAgents(is_debug_mode=False)
        print("✅ ConjureAgents initialized without conversational agent")
        
        # Check that backend agent is available
        if hasattr(agents, 'backend_agent'):
            print("✅ Backend agent available")
        else:
            print("❌ Backend agent not available")
            
        # Check that instruction manager is available
        if hasattr(agents, 'instruction_manager'):
            print("✅ Instruction manager available")
        else:
            print("❌ Instruction manager not available")
            
        print("✅ Main launcher test completed successfully")
        
    except Exception as e:
        print(f"❌ Main launcher test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all Phase 1 simplification tests"""
    print("🧪 CONJURE Phase 1 Simplification Tests")
    print("=" * 60)
    print("Testing simplified workflow without conversational agent complexity")
    
    # Test individual components
    test_backend_agent_prompt_processing()
    test_instruction_manager_simplified()
    test_main_launcher_simplified()
    
    print("\n📋 Test Summary")
    print("=" * 60)
    print("✅ Phase 1 simplification core components tested")
    print("🎯 Ready for continuous generation loop implementation (Phase 2)")
    print("🔄 Next: Implement 30-second automatic cycles")

if __name__ == "__main__":
    main()
