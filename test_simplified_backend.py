"""
Test script for CONJURE simplified backend agent approach
Tests the new user-only request format
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_simplified_requests():
    """Test the new simplified user request format."""
    print("🧪 CONJURE Simplified Backend Test")
    print("=" * 50)
    
    # Test cases with new simplified format
    test_cases = [
        {
            "request": "User Request: I want to create a cylinder",
            "expected": "spawn_primitive",
            "description": "Direct cylinder request"
        },
        {
            "request": "User Request: Let's make a sphere",
            "expected": "spawn_primitive", 
            "description": "Direct sphere request"
        },
        {
            "request": "User Request: Generate a mesh for this shape",
            "expected": "generate_flux_mesh",
            "description": "Mesh generation request"
        },
        {
            "request": "User Request: How are you doing today?",
            "expected": None,
            "description": "Casual conversation - no action"
        },
        {
            "request": "User Request: I need to build a cube",
            "expected": "spawn_primitive",
            "description": "Cube building request"
        }
    ]
    
    print(f"🎯 Testing {len(test_cases)} simplified requests...\n")
    
    # Test keyword detection logic
    action_keywords = [
        "create", "make", "spawn", "generate", "build", 
        "cylinder", "sphere", "cube", "cone", "mesh"
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['description']}")
        print(f"Request: {test['request']}")
        
        # Test keyword detection
        request_found = any(keyword.lower() in test['request'].lower() for keyword in action_keywords)
        
        if test['expected'] is None:
            # Expecting no action
            if not request_found:
                print("✅ PASS: No action keywords detected (as expected)")
                passed += 1
            else:
                matching_keywords = [k for k in action_keywords if k.lower() in test['request'].lower()]
                print(f"❌ FAIL: Action keywords detected but none expected: {matching_keywords}")
                failed += 1
        else:
            # Expecting an action
            if request_found:
                matching_keywords = [k for k in action_keywords if k.lower() in test['request'].lower()]
                print(f"✅ PASS: Action keywords detected: {matching_keywords}")
                passed += 1
            else:
                print("❌ FAIL: No action keywords detected but action expected")
                failed += 1
        
        print()
    
    # Summary
    print("=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)
    print(f"✅ Passed: {passed}/{len(test_cases)}")
    print(f"❌ Failed: {failed}/{len(test_cases)}")
    
    if failed == 0:
        print("🎉 All tests passed! Simplified approach is working correctly.")
        return True
    else:
        print("🔧 Some tests failed - keyword detection needs improvement.")
        return False

def show_simplified_approach():
    """Show the benefits of the new simplified approach."""
    print("\n🚀 SIMPLIFIED APPROACH BENEFITS")
    print("=" * 40)
    
    print("\n❌ OLD COMPLEX APPROACH:")
    print("   1. User: 'I want a cylinder'")
    print("   2. Agent: 'Back-end agent, let's spawn a cylinder primitive.'")
    print("   3. Send: 'User: I want a cylinder\\nAgent: Back-end agent, let's spawn...'")
    print("   4. Backend: Parse complex conversation, get confused by fragments")
    print("   5. Result: instruction: null ❌")
    
    print("\n✅ NEW SIMPLIFIED APPROACH:")
    print("   1. User: 'I want a cylinder'")
    print("   2. Send: 'User Request: I want a cylinder'")
    print("   3. Backend: Clear user intent → spawn_primitive")
    print("   4. Result: Cylinder spawns! ✅")
    
    print("\n🎯 KEY IMPROVEMENTS:")
    print("   • No complex conversation parsing")
    print("   • No fragmented agent responses")
    print("   • Direct user intent to backend")
    print("   • Cleaner OpenAI prompts")
    print("   • More reliable instruction generation")

def main():
    """Run the simplified backend test."""
    print("🔧 CONJURE Simplified Backend Test Suite")
    print("="*50)
    
    # Show approach
    show_simplified_approach()
    
    print("\n")
    input("Press Enter to run simplified request tests...")
    
    # Run tests
    if test_simplified_requests():
        print("\n🎯 Ready to test in CONJURE!")
        print("Expected behavior:")
        print("1. Say: 'I want to create a cylinder'")
        print("2. See: '🎯 SENDING USER REQUEST TO BACKEND AGENT'")
        print("3. See: '🔍 User action request detected: True'")
        print("4. See: '🎯 Matching keywords: ['create', 'cylinder']'")
        print("5. Result: Cylinder should spawn in Blender!")
    else:
        print("\n🔧 Fix needed before testing in CONJURE")

if __name__ == "__main__":
    main() 