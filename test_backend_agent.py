"""
Simple Backend Agent Tester
Test OpenAI Chat Completions API connectivity and response format.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to sys.path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_openai_connectivity():
    """Test basic OpenAI API connectivity"""
    print("🧪 Testing OpenAI API Connectivity")
    print("="*50)
    
    try:
        import openai
        
        # Check if API key is set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY environment variable not set")
            return False
        
        print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
        
        # Test basic API call
        client = openai.Client(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": "Say 'Hello, CONJURE!' if you can hear me."}
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        if response.choices and response.choices[0].message.content:
            content = response.choices[0].message.content.strip()
            print(f"✅ OpenAI Response: {content}")
            return True
        else:
            print("❌ Empty response from OpenAI API")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return False


def test_backend_agent_direct():
    """Test the backend agent directly"""
    print("\n🧪 Testing Backend Agent Direct Call")
    print("="*50)
    
    try:
        from launcher.backend_agent import BackendAgent
        from launcher.state_manager import StateManager
        from launcher.instruction_manager import InstructionManager
        
        # Initialize components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        backend_agent = BackendAgent(instruction_manager=instruction_manager)
        
        print("✅ Backend Agent initialized successfully")
        
        # Test conversation
        test_conversation = "User: Can you spawn a cube?\nAgent: I'll help you spawn a cube."
        
        print(f"📝 Testing conversation: {test_conversation}")
        
        result = backend_agent.get_response(test_conversation)
        
        print(f"📊 Result type: {type(result)}")
        print(f"📊 Result content: {result}")
        
        return result is not None
        
    except Exception as e:
        print(f"❌ Backend Agent Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def interactive_backend_test():
    """Interactive test where user can input conversations"""
    print("\n🎮 Interactive Backend Agent Test")
    print("="*50)
    print("Type 'quit' to exit, 'help' for examples")
    print()
    
    try:
        from launcher.backend_agent import BackendAgent
        from launcher.state_manager import StateManager
        from launcher.instruction_manager import InstructionManager
        
        # Initialize components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        backend_agent = BackendAgent(instruction_manager=instruction_manager)
        
        print("✅ Backend Agent ready for testing")
        print()
        
        while True:
            try:
                # Get user input
                print("💬 Enter a conversation (or 'quit' to exit):")
                print("   Format: 'User: [message] Agent: [response]'")
                user_input = input(">>> ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if user_input.lower() == 'help':
                    print("\n📖 Example conversations:")
                    print("   User: Spawn a cube Agent: I'll create a cube for you")
                    print("   User: Generate a sword Agent: I'll generate a sword design")
                    print("   User: Make it bigger Agent: I'll scale up the object")
                    print()
                    continue
                
                if not user_input:
                    continue
                
                # Test the conversation
                print(f"\n🔄 Processing: {user_input}")
                print("-" * 40)
                
                result = backend_agent.get_response(user_input)
                
                print(f"\n📊 Backend Agent Response:")
                print(f"   Type: {type(result)}")
                if result:
                    if isinstance(result, dict):
                        print(f"   Content: {json.dumps(result, indent=2)}")
                    else:
                        print(f"   Content: {result}")
                else:
                    print(f"   Content: None (empty response)")
                
                print()
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                print()
                
    except Exception as e:
        print(f"❌ Failed to initialize backend agent: {e}")
        import traceback
        traceback.print_exc()


def test_image_context():
    """Test backend agent with image context"""
    print("\n🖼️ Testing Backend Agent with Image Context")
    print("="*50)
    
    try:
        from launcher.backend_agent import BackendAgent
        from launcher.state_manager import StateManager
        from launcher.instruction_manager import InstructionManager
        
        # Initialize components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        backend_agent = BackendAgent(instruction_manager=instruction_manager)
        
        # Check if render image exists
        render_path = Path("data/generated_images/gestureCamera/render.png")
        if render_path.exists():
            print(f"✅ Found render image: {render_path}")
            
            test_conversation = "User: What do you see in this image?\nAgent: Let me analyze what I see."
            
            print(f"📝 Testing with image: {test_conversation}")
            
            result = backend_agent.get_response(test_conversation)
            
            print(f"📊 Result with image: {result}")
            
            return True
        else:
            print(f"⚠️ No render image found at: {render_path}")
            print("   Run CONJURE first to generate a render image")
            return False
            
    except Exception as e:
        print(f"❌ Image context test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all backend agent tests"""
    print("🚀 CONJURE Backend Agent Tester")
    print("="*60)
    
    # Test 1: OpenAI connectivity
    openai_ok = test_openai_connectivity()
    
    # Test 2: Backend agent direct
    backend_ok = test_backend_agent_direct()
    
    # Test 3: Image context (if available)
    image_ok = test_image_context()
    
    # Summary
    print("\n📊 Test Summary")
    print("="*60)
    print(f"   ✅ OpenAI API: {'PASS' if openai_ok else 'FAIL'}")
    print(f"   ✅ Backend Agent: {'PASS' if backend_ok else 'FAIL'}")
    print(f"   ✅ Image Context: {'PASS' if image_ok else 'SKIP'}")
    
    if openai_ok and backend_ok:
        print("\n🎉 Basic functionality is working!")
        print("   Starting interactive test...")
        interactive_backend_test()
    else:
        print("\n❌ Fix the failing tests before proceeding")
        
        if not openai_ok:
            print("   🔑 Set OPENAI_API_KEY environment variable")
        if not backend_ok:
            print("   🔧 Check backend agent configuration")


if __name__ == "__main__":
    main()
