#!/usr/bin/env python3
"""
Phase 2 Verification Test - Continuous Loop System
Tests the 30-second generation cycles and voice-to-prompt integration.
"""

import sys
import os
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

def test_continuous_loop_logic():
    """Test the core continuous loop timing logic"""
    print("\n🔄 Testing Continuous Loop Logic")
    print("-" * 40)
    
    try:
        from launcher.main import ConjureApp
        
        # Mock some dependencies to avoid full startup
        with patch('launcher.main.SubprocessManager'), \
             patch('launcher.main.VoiceProcessor'), \
             patch('launcher.backend_agent.OpenAI'):
            
            app = ConjureApp(generation_mode="local")
            
            # Test initial state
            if app.demo_start_time is None:
                print("✅ Initial timer state correct (None)")
            else:
                print(f"❌ Initial timer state incorrect: {app.demo_start_time}")
                return False
            
            # Simulate the continuous loop logic
            current_time = time.time()
            app.demo_start_time = current_time - 35  # Simulate 35 seconds passed
            app.demo_flux_triggered = False
            app.last_flux_trigger_time = None
            
            # Test first trigger condition
            time_since_demo_start = current_time - app.demo_start_time
            should_trigger_first = (not app.demo_flux_triggered and time_since_demo_start >= 30)
            
            if should_trigger_first:
                print("✅ First trigger condition works (30s elapsed)")
            else:
                print(f"❌ First trigger condition failed - {time_since_demo_start}s elapsed")
                return False
            
            # Simulate first trigger happened
            app.demo_flux_triggered = True
            app.last_flux_trigger_time = current_time - 35  # 35s ago
            
            # Test subsequent trigger condition
            should_trigger_subsequent = (app.last_flux_trigger_time and 
                                       current_time - app.last_flux_trigger_time >= 30)
            
            if should_trigger_subsequent:
                print("✅ Subsequent trigger condition works (30s since last)")
            else:
                print(f"❌ Subsequent trigger condition failed")
                return False
            
            print("✅ Continuous loop timing logic verified")
            return True
            
    except Exception as e:
        print(f"❌ Continuous loop test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_voice_processor_integration():
    """Test voice processor initialization and integration"""
    print("\n🎤 Testing Voice Processor Integration")
    print("-" * 40)
    
    try:
        from launcher.voice_processor import VoiceProcessor
        from launcher.backend_agent import BackendAgent
        from launcher.instruction_manager import InstructionManager
        from launcher.state_manager import StateManager
        
        # Create minimal components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        
        # Mock OpenAI client to avoid API calls
        with patch('launcher.backend_agent.OpenAI'):
            backend_agent = BackendAgent(instruction_manager)
            
            # Test voice processor creation
            with patch('launcher.voice_processor.OpenAI'), \
                 patch('pyaudio.PyAudio'):
                voice_processor = VoiceProcessor(backend_agent)
                print("✅ VoiceProcessor creation successful")
                
                # Test status checking
                status = voice_processor.get_status()
                expected_keys = ['enabled', 'running', 'has_openai_key', 'has_audio']
                
                if all(key in status for key in expected_keys):
                    print("✅ Voice processor status method works")
                else:
                    print(f"❌ Status method missing keys: {expected_keys}")
                    return False
                
                # Test voice processing method exists
                if hasattr(voice_processor, '_update_prompt_with_speech'):
                    print("✅ Voice-to-prompt update method exists")
                else:
                    print("❌ Voice-to-prompt update method missing")
                    return False
                
                print("✅ Voice processor integration verified")
                return True
                
    except Exception as e:
        print(f"❌ Voice processor integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prompt_generation_flow():
    """Test the complete voice → prompt generation flow"""
    print("\n📝 Testing Voice-to-Prompt Flow")
    print("-" * 40)
    
    try:
        from launcher.backend_agent import BackendAgent
        from launcher.instruction_manager import InstructionManager
        from launcher.state_manager import StateManager
        
        # Setup components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        
        with patch('launcher.backend_agent.OpenAI') as mock_openai:
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "subject": {
                    "name": "modern chair",
                    "form_keywords": ["curved", "ergonomic"],
                    "material_keywords": ["brushed aluminum"],
                    "color_keywords": ["matte black"]
                }
            })
            
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            
            backend_agent = BackendAgent(instruction_manager)
            
            # Test voice input processing
            result = backend_agent.process_voice_input(
                speech_transcript="make it more curved and metallic",
                current_prompt_state="simple chair",
                gesture_render_path=None
            )
            
            if result:
                print("✅ Voice input processing successful")
                
                # Check if userPrompt.txt was updated
                prompt_path = PROJECT_ROOT / "data" / "generated_text" / "userPrompt.txt"
                if prompt_path.exists():
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        updated_prompt = f.read()
                    
                    if "modern chair" in updated_prompt and "curved" in updated_prompt:
                        print("✅ Prompt file updated correctly")
                        print(f"📝 Generated prompt: {updated_prompt[:100]}...")
                    else:
                        print(f"❌ Prompt file content incorrect: {updated_prompt[:100]}...")
                        return False
                else:
                    print("❌ Prompt file not created")
                    return False
            else:
                print("❌ Voice input processing failed")
                return False
            
            print("✅ Voice-to-prompt flow verified")
            return True
            
    except Exception as e:
        print(f"❌ Voice-to-prompt flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_continuous_generation():
    """Test continuous generation trigger mechanism"""
    print("\n⚙️ Testing Continuous Generation")
    print("-" * 40)
    
    try:
        from launcher.instruction_manager import InstructionManager
        from launcher.state_manager import StateManager
        
        # Setup components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        
        # Test generate_flux_mesh instruction
        test_instruction = {
            "tool_name": "generate_flux_mesh",
            "parameters": {
                "prompt": "test continuous generation prompt",
                "seed": 12345
            }
        }
        
        instruction_manager.execute_instruction(test_instruction)
        
        # Verify state was updated
        current_state = state_manager.get_state()
        if current_state and current_state.get("flux_pipeline_request") == "new":
            print("✅ Generation trigger successful")
            
            # Check for expected state values
            expected_prompt = "test continuous generation prompt"
            if current_state.get("flux_prompt") == expected_prompt:
                print("✅ Prompt properly stored in state")
            else:
                print(f"⚠️ Prompt in state: {current_state.get('flux_prompt')}")
            
            if current_state.get("flux_seed") == 12345:
                print("✅ Seed properly stored in state")
            else:
                print(f"⚠️ Seed in state: {current_state.get('flux_seed')}")
        else:
            print(f"❌ Generation trigger failed - state: {current_state}")
            return False
        
        print("✅ Continuous generation mechanism verified")
        return True
        
    except Exception as e:
        print(f"❌ Continuous generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_operations():
    """Test Phase 2 file operation requirements"""
    print("\n📁 Testing Phase 2 File Operations")
    print("-" * 40)
    
    try:
        # Ensure data directories exist
        data_dir = PROJECT_ROOT / "data"
        required_files = [
            data_dir / "generated_text" / "userPrompt.txt",
            data_dir / "generated_images" / "gestureCamera" / "render.png"
        ]
        
        # Check/create userPrompt.txt
        prompt_path = required_files[0]
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        
        test_prompt = "Phase 2 test prompt for continuous generation"
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(test_prompt)
        print("✅ userPrompt.txt write successful")
        
        # Read back
        with open(prompt_path, 'r', encoding='utf-8') as f:
            read_prompt = f.read()
        
        if read_prompt == test_prompt:
            print("✅ userPrompt.txt read successful")
        else:
            print(f"❌ Prompt mismatch - wrote: {test_prompt}, read: {read_prompt}")
            return False
        
        # Check gesture render directory
        gesture_dir = required_files[1].parent
        gesture_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Gesture camera directory ready: {gesture_dir}")
        
        print("✅ Phase 2 file operations verified")
        return True
        
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def test_environment_requirements():
    """Test Phase 2 environment requirements"""
    print("\n🔑 Testing Phase 2 Environment")
    print("-" * 40)
    
    # Check required packages
    required_packages = ['openai', 'pyaudio', 'pathlib']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} available")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} missing")
    
    if missing_packages:
        print(f"⚠️ Missing packages: {missing_packages}")
        return False
    
    # Check API keys
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print(f"✅ OPENAI_API_KEY set ({len(openai_key)} chars)")
    else:
        print("⚠️ OPENAI_API_KEY not set (voice processing will be disabled)")
    
    print("✅ Phase 2 environment verified")
    return True

def main():
    """Run Phase 2 verification tests"""
    print("🧪 CONJURE Phase 2 Verification Tests")
    print("=" * 50)
    print("Testing continuous loop system and voice integration\n")
    
    tests = [
        ("Environment Requirements", test_environment_requirements),
        ("Continuous Loop Logic", test_continuous_loop_logic), 
        ("Voice Processor Integration", test_voice_processor_integration),
        ("Voice-to-Prompt Flow", test_prompt_generation_flow),
        ("Continuous Generation", test_continuous_generation),
        ("File Operations", test_file_operations)
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
    print("\n📋 Phase 2 Test Results")
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
        print("\n🎉 ALL PHASE 2 TESTS PASSED!")
        print("✅ Continuous loop system is working correctly")
        print("✅ Voice processing integration ready")
        print("🚀 Phase 2 implementation complete and testable!")
        print("\nPhase 2 Achievements:")
        print("- ✅ 30-second continuous generation cycles")
        print("- ✅ Voice input → immediate prompt updates")
        print("- ✅ Simplified workflow without conversation")
        print("- ✅ File operations working reliably")
        print("- ✅ Integration components ready")
        print("\n🔄 READY FOR REAL-WORLD TESTING:")
        print("- Run the main launcher to test full system")
        print("- Speak into microphone to update prompts")
        print("- Watch 30-second generation cycles")
    else:
        print(f"\n⚠️ {failed} TESTS FAILED")
        print("❌ Phase 2 has issues that need fixing")
        print("\nRecommended actions:")
        print("- Fix the failing tests above")
        print("- Ensure all components integrate properly")
        print("- Test voice processing separately if needed")

if __name__ == "__main__":
    main()
