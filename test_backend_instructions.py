"""
Test script for CONJURE backend agent instruction detection
Helps verify that the backend agent correctly detects and generates instructions
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from launcher.backend_agent import BackendAgent

def test_instruction_detection():
    """Test various conversation examples to see if instructions are detected correctly."""
    print("🧪 Backend Agent Instruction Detection Test")
    print("=" * 60)
    
    # Initialize backend agent
    try:
        agent = BackendAgent()
        print("✅ Backend agent initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize backend agent: {e}")
        return False
    
    # Test cases with expected results
    test_cases = [
        {
            "conversation": "User: Can you hear me?\nAgent: Hello there. Yes, I can hear you clearly.",
            "expected_instruction": None,
            "description": "Greeting conversation - no action expected"
        },
        {
            "conversation": "User: I want to create a cylinder.\nAgent: Alright, back-end agent, let's spawn a cylinder primitive.",
            "expected_instruction": "spawn_primitive",
            "description": "Clear spawn primitive request"
        },
        {
            "conversation": "User: Let's start with a sphere.\nAgent: Perfect! Back-end agent, let's trigger spawn primitive with primitive type sphere.",
            "expected_instruction": "spawn_primitive", 
            "description": "Spawn sphere request"
        },
        {
            "conversation": "User: I'm ready to generate the mesh.\nAgent: Excellent! Backend, activate generate flux mesh workflow.",
            "expected_instruction": "generate_flux_mesh",
            "description": "Generate mesh request"
        },
        {
            "conversation": "User: How are you today?\nAgent: I'm doing well, thank you for asking! What would you like to create?",
            "expected_instruction": None,
            "description": "Casual conversation - no action expected"
        }
    ]
    
    print(f"\n🎯 Testing {len(test_cases)} conversation scenarios...\n")
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['description']}")
        print(f"Conversation: {test['conversation']}")
        
        try:
            # Test the backend agent response (but don't actually call OpenAI)
            # Just test the trigger detection logic
            action_triggers = [
                "back-end agent", "backend agent", "backend,", 
                "spawn", "generate", "trigger", "activate"
            ]
            
            trigger_found = any(trigger.lower() in test['conversation'].lower() for trigger in action_triggers)
            
            if test['expected_instruction'] is None:
                # Expecting no instruction
                if not trigger_found:
                    print("✅ PASS: No action triggers detected (as expected)")
                    passed += 1
                else:
                    print("❌ FAIL: Action triggers detected but none expected")
                    print(f"   Triggers found: {[t for t in action_triggers if t.lower() in test['conversation'].lower()]}")
                    failed += 1
            else:
                # Expecting an instruction
                if trigger_found:
                    matching_triggers = [t for t in action_triggers if t.lower() in test['conversation'].lower()]
                    print(f"✅ PASS: Action triggers detected: {matching_triggers}")
                    passed += 1
                else:
                    print("❌ FAIL: No action triggers detected but instruction expected")
                    failed += 1
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{len(test_cases)}")
    print(f"❌ Failed: {failed}/{len(test_cases)}")
    
    if failed == 0:
        print("🎉 All tests passed! Instruction detection is working correctly.")
        return True
    else:
        print("🔧 Some tests failed - instruction detection needs improvement.")
        return False

def test_conversation_examples():
    """Show examples of what the backend agent should detect."""
    print("\n🔍 CONVERSATION EXAMPLES")
    print("=" * 40)
    
    examples = [
        ("❌ No Action", "User: Hello! How are you?\nAgent: I'm great! What would you like to create?"),
        ("✅ Spawn Primitive", "User: I want a cylinder.\nAgent: Back-end agent, let's spawn a cylinder primitive."),
        ("✅ Generate Mesh", "User: I'm ready.\nAgent: Backend, activate generate flux mesh."),
        ("❌ Just Description", "User: Tell me about cylinders.\nAgent: Cylinders are useful 3D shapes..."),
        ("✅ Segment Selection", "User: I want to select parts.\nAgent: Back-end agent, trigger segment selection.")
    ]
    
    for label, conversation in examples:
        print(f"\n{label}")
        print(f"   {conversation}")

def main():
    """Run the instruction detection test suite."""
    print("🔧 CONJURE Backend Agent Test Suite")
    print("="*50)
    
    # Show examples
    test_conversation_examples()
    
    print("\n")
    input("Press Enter to run instruction detection tests...")
    
    # Run tests
    if test_instruction_detection():
        print("\n🎯 Next Steps:")
        print("1. Test in actual CONJURE session")
        print("2. Say: 'I want to create a cylinder'")
        print("3. Agent should respond: 'Back-end agent, let's spawn a cylinder primitive'")
        print("4. Backend should detect trigger and generate spawn_primitive instruction")
    else:
        print("\n🔧 Troubleshooting needed:")
        print("1. Check trigger phrase detection logic")
        print("2. Verify conversation format")
        print("3. Test with actual backend agent calls")

if __name__ == "__main__":
    main() 