#!/usr/bin/env python3
"""
Backend Agent Console Chat - Direct testing tool for CONJURE Backend Agent

This script allows you to directly test the backend agent's OpenAI API integration
without running the full CONJURE application. Useful for debugging and testing.

Usage:
    python test_backend_chat.py

Commands:
    - Type 'quit' or 'exit' to stop
    - Type 'test' for a simple test conversation
    - Type 'apitest' to test OpenAI API directly
    - Or type any conversation like: 'Agent: Let's spawn a cube. User: Yes'
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from launcher.backend_agent import BackendAgent
from launcher.instruction_manager import InstructionManager
from launcher.state_manager import StateManager
from openai import OpenAI

def main():
    print("🤖 Backend Agent Console Chat")
    print("=" * 50)
    
    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key and try again.")
        return
    
    print(f"✅ OpenAI API key found: {api_key[:10]}...")
    
    try:
        # Initialize components (StateManager must be initialized first)
        state_manager = StateManager()
        print("✅ State manager initialized")
        
        instruction_manager = InstructionManager(state_manager)
        print("✅ Instruction manager initialized")
        
        backend_agent = BackendAgent(instruction_manager)
        print("✅ Backend agent initialized")
        
    except Exception as e:
        print(f"❌ Error initializing backend agent: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return

    print("\n🎯 Chat Commands:")
    print("  Type 'quit' or 'exit' to stop")
    print("  Type 'test' for a simple test conversation")
    print("  Type 'apitest' to test OpenAI API directly")
    print("  Or type any conversation like: 'Agent: Let's spawn a cube. User: Yes'")
    print("\n" + "=" * 50)

    while True:
        try:
            user_input = input("\n💬 Enter conversation: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'test':
                user_input = "Agent: Backend agent, let's spawn a cube. User: Yes, let's do it"
                print(f"🧪 Testing with: {user_input}")
            
            if user_input.lower() == 'apitest':
                print("🧪 Testing OpenAI API directly...")
                try:
                    client = OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{
                            "role": "user", 
                            "content": "Respond with JSON: {\"test\": \"success\"}"
                        }],
                        max_tokens=50,
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    if response.choices and response.choices[0].message.content:
                        content = response.choices[0].message.content.strip()
                        print(f"✅ Direct OpenAI API Success: {content}")
                    else:
                        print("❌ Direct OpenAI API returned no content")
                        print(f"🔍 Full response: {response}")
                except Exception as e:
                    print(f"❌ Direct OpenAI API Error: {e}")
                    import traceback
                    print(f"🔍 Traceback: {traceback.format_exc()}")
                continue
            
            if not user_input:
                continue
            
            print(f"\n🚀 Sending to backend agent...")
            print(f"📝 Input: {user_input}")
            
            # Call the backend agent
            result = backend_agent.get_response(user_input)
            
            print(f"\n📊 Backend Agent Response:")
            print("-" * 30)
            if result:
                print("✅ Success!")
                print(f"📄 Response Type: {type(result)}")
                print(f"📋 Content: {result}")
                
                if isinstance(result, dict):
                    print(f"\n🔍 Detailed Analysis:")
                    if "tool_name" in result:
                        print(f"  Tool Name: {result['tool_name']}")
                    if "parameters" in result:
                        print(f"  Parameters: {result['parameters']}")
            else:
                print("❌ No response or error occurred")
            print("-" * 30)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
