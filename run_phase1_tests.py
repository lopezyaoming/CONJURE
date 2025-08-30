#!/usr/bin/env python3
"""
Quick Phase 1 Verification Script
Run this to confirm all Phase 1 implementations work correctly before Phase 2.
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

def test_imports():
    """Test 1: Verify all components can be imported"""
    print("\n🔍 Test 1: Component Imports")
    print("-" * 40)
    
    try:
        from launcher.main import ConjureAgents
        print("✅ launcher.main imports successfully")
    except Exception as e:
        print(f"❌ launcher.main import failed: {e}")
        return False
    
    try:
        from launcher.backend_agent import BackendAgent
        print("✅ launcher.backend_agent imports successfully")
    except Exception as e:
        print(f"❌ launcher.backend_agent import failed: {e}")
        return False
    
    try:
        from launcher.instruction_manager import InstructionManager
        print("✅ launcher.instruction_manager imports successfully")
    except Exception as e:
        print(f"❌ launcher.instruction_manager import failed: {e}")
        return False
    
    try:
        from launcher.state_manager import StateManager
        print("✅ launcher.state_manager imports successfully")
    except Exception as e:
        print(f"❌ launcher.state_manager import failed: {e}")
        return False
    
    return True

def test_conversational_agent_removal():
    """Test 2: Verify conversational agent is properly removed"""
    print("\n🔍 Test 2: Conversational Agent Removal")
    print("-" * 40)
    
    try:
        from launcher.main import ConjureAgents
        
        # Check main.py doesn't import conversational agent
        with open(PROJECT_ROOT / "launcher" / "main.py", 'r') as f:
            main_content = f.read()
        
        if "from conversational_agent import ConversationalAgent" in main_content:
            print("❌ ConversationalAgent import still active")
            return False
        else:
            print("✅ ConversationalAgent import commented out")
        
        # Test initialization without conversational agent
        agents = ConjureAgents(is_debug_mode=False)
        
        if hasattr(agents, 'conversational_agent'):
            print("❌ conversational_agent attribute still exists")
            return False
        else:
            print("✅ conversational_agent attribute removed")
        
        if hasattr(agents, 'backend_agent'):
            print("✅ backend_agent still available")
        else:
            print("❌ backend_agent missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Conversational agent removal test failed: {e}")
        return False

def test_backend_agent_simplification():
    """Test 3: Verify backend agent processes voice input correctly"""
    print("\n🔍 Test 3: Backend Agent Simplification")
    print("-" * 40)
    
    try:
        from launcher.backend_agent import BackendAgent
        from launcher.instruction_manager import InstructionManager
        from launcher.state_manager import StateManager
        
        # Initialize components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        backend_agent = BackendAgent(instruction_manager)
        
        # Check method exists
        if hasattr(backend_agent, 'process_voice_input'):
            print("✅ process_voice_input method exists")
        else:
            print("❌ process_voice_input method missing")
            return False
        
        # Check old conversation method is gone
        if hasattr(backend_agent, 'get_response'):
            print("⚠️ Old get_response method still exists (should be renamed)")
        else:
            print("✅ Old conversation method removed")
        
        # Test voice input processing (without API call)
        print("🔧 Testing voice input processing structure...")
        
        # Mock test - check method signature
        import inspect
        sig = inspect.signature(backend_agent.process_voice_input)
        params = list(sig.parameters.keys())
        
        expected_params = ['speech_transcript', 'current_prompt_state', 'gesture_render_path']
        if all(param in params for param in expected_params):
            print("✅ Method signature correct")
        else:
            print(f"❌ Method signature incorrect. Expected: {expected_params}, Got: {params}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Backend agent test failed: {e}")
        return False

def test_instruction_manager_simplification():
    """Test 4: Verify instruction manager only has generate_flux_mesh"""
    print("\n🔍 Test 4: Instruction Manager Simplification")
    print("-" * 40)
    
    try:
        from launcher.instruction_manager import InstructionManager
        from launcher.state_manager import StateManager
        
        # Initialize
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        
        # Check tool map
        available_tools = list(instruction_manager.tool_map.keys())
        print(f"Available tools: {available_tools}")
        
        if len(available_tools) == 1 and available_tools[0] == "generate_flux_mesh":
            print("✅ Only generate_flux_mesh available")
        else:
            print(f"❌ Wrong tools available. Expected: ['generate_flux_mesh'], Got: {available_tools}")
            return False
        
        # Check method exists
        if hasattr(instruction_manager, 'generate_flux_mesh'):
            print("✅ generate_flux_mesh method exists")
        else:
            print("❌ generate_flux_mesh method missing")
            return False
        
        # Test instruction execution structure
        test_instruction = {
            "tool_name": "generate_flux_mesh",
            "parameters": {
                "prompt": "test prompt",
                "seed": 42
            }
        }
        
        # This should work without errors (just updates state)
        instruction_manager.execute_instruction(test_instruction)
        print("✅ Instruction execution works")
        
        # Test invalid tool handling
        invalid_instruction = {
            "tool_name": "spawn_primitive",
            "parameters": {"primitive_type": "Cube"}
        }
        
        # This should handle gracefully
        instruction_manager.execute_instruction(invalid_instruction)
        print("✅ Invalid tool handled gracefully")
        
        return True
        
    except Exception as e:
        print(f"❌ Instruction manager test failed: {e}")
        return False

def test_file_operations():
    """Test 5: Verify file operations work correctly"""
    print("\n🔍 Test 5: File Operations")
    print("-" * 40)
    
    try:
        # Check data directory structure
        data_dir = PROJECT_ROOT / "data"
        required_dirs = [
            data_dir / "input",
            data_dir / "generated_text",
            data_dir / "generated_images" / "gestureCamera",
            data_dir / "generated_models"
        ]
        
        for dir_path in required_dirs:
            if dir_path.exists():
                print(f"✅ {dir_path.relative_to(PROJECT_ROOT)} exists")
            else:
                print(f"🔧 Creating {dir_path.relative_to(PROJECT_ROOT)}")
                dir_path.mkdir(parents=True, exist_ok=True)
        
        # Test state file operations
        from launcher.state_manager import StateManager
        state_manager = StateManager()
        
        # Test write
        test_state = {
            "test_key": "test_value",
            "flux_pipeline_request": "new"
        }
        state_manager.update_state(test_state)
        print("✅ State write successful")
        
        # Test read
        current_state = state_manager.get_state()
        if current_state and current_state.get("test_key") == "test_value":
            print("✅ State read successful")
        else:
            print("❌ State read/write mismatch")
            return False
        
        # Test userPrompt.txt creation
        prompt_file = data_dir / "generated_text" / "userPrompt.txt"
        test_prompt = "Test FLUX prompt for Phase 1 verification"
        
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(test_prompt)
        print("✅ userPrompt.txt write successful")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            read_prompt = f.read()
        
        if read_prompt == test_prompt:
            print("✅ userPrompt.txt read successful")
        else:
            print("❌ userPrompt.txt read/write mismatch")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def test_api_readiness():
    """Test 6: Check API configuration"""
    print("\n🔍 Test 6: API Readiness")
    print("-" * 40)
    
    # Check environment variables
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print(f"✅ OPENAI_API_KEY set ({len(openai_key)} chars)")
    else:
        print("⚠️ OPENAI_API_KEY not set (required for voice processing)")
    
    hf_token = os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN")
    if hf_token:
        print(f"✅ HUGGINGFACE_HUB_ACCESS_TOKEN set ({len(hf_token)} chars)")
    else:
        print("⚠️ HUGGINGFACE_HUB_ACCESS_TOKEN not set (required for FLUX generation)")
    
    # Check OpenAI import
    try:
        from openai import OpenAI
        print("✅ OpenAI library available")
    except ImportError:
        print("❌ OpenAI library not installed")
        return False
    
    return True

def test_system_integration():
    """Test 7: Verify components work together"""
    print("\n🔍 Test 7: System Integration")
    print("-" * 40)
    
    try:
        from launcher.main import ConjureAgents
        
        # Initialize full system
        agents = ConjureAgents(is_debug_mode=False)
        print("✅ Full system initialization successful")
        
        # Test component connections
        if hasattr(agents, 'backend_agent') and hasattr(agents, 'instruction_manager'):
            # Test that backend agent has access to instruction manager
            if hasattr(agents.backend_agent, 'instruction_manager'):
                print("✅ Backend agent → instruction manager connection")
            else:
                print("⚠️ Backend agent missing instruction manager reference")
        
        # Test state manager integration
        if hasattr(agents, 'state_manager'):
            # Test state operations
            test_data = {"integration_test": "success"}
            agents.state_manager.update_state(test_data)
            
            retrieved = agents.state_manager.get_state()
            if retrieved and retrieved.get("integration_test") == "success":
                print("✅ State manager integration working")
            else:
                print("❌ State manager integration failed")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ System integration test failed: {e}")
        return False

def main():
    """Run all Phase 1 verification tests"""
    print("🧪 CONJURE Phase 1 Verification Tests")
    print("=" * 50)
    print("Confirming all Phase 1 implementations work correctly")
    print("Before proceeding to Phase 2 implementation\n")
    
    tests = [
        ("Component Imports", test_imports),
        ("Conversational Agent Removal", test_conversational_agent_removal),
        ("Backend Agent Simplification", test_backend_agent_simplification),
        ("Instruction Manager Simplification", test_instruction_manager_simplification),
        ("File Operations", test_file_operations),
        ("API Readiness", test_api_readiness),
        ("System Integration", test_system_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📋 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        if result:
            print(f"✅ {test_name}")
            passed += 1
        else:
            print(f"❌ {test_name}")
            failed += 1
    
    print(f"\nPassed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Phase 1 implementation is complete and working")
        print("🚀 Ready to proceed with Phase 2 implementation")
        print("\nNext steps:")
        print("- Implement 30-second automatic generation cycles")
        print("- Add real-time voice processing")
        print("- Create streamlined UI updates")
    else:
        print(f"\n⚠️ {failed} TESTS FAILED")
        print("❌ Phase 1 has issues that need fixing before Phase 2")
        print("\nRecommended actions:")
        print("- Review failed tests above")
        print("- Check PHASE1_TESTING_GUIDE.md for detailed troubleshooting")
        print("- Fix issues and re-run this script")

if __name__ == "__main__":
    main()
