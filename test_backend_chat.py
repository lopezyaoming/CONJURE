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
import re

def parse_conversation_file(file_path):
    """Parse the conversation file and extract Agent/User turns"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"🔍 File content length: {len(content)} characters")
        print(f"🔍 First 200 chars: {content[:200]}...")
        
        # Extract conversation turns - handle sequential Agent/User pairs
        lines = content.split('\n')
        print(f"🔍 Total lines: {len(lines)}")
        
        turns = []
        agent_messages = []
        user_messages = []
        
        # First pass: collect all agent and user lines
        for i, line in enumerate(lines):
            original_line = line
            line = line.strip()
            if line.startswith('Agent:'):
                agent_msg = line[6:].strip()  # Remove "Agent:"
                agent_messages.append(agent_msg)
                print(f"🔍 Line {i}: Found Agent: {agent_msg[:50]}...")
            elif line.startswith('User:'):
                user_msg = line[5:].strip()  # Remove "User:"
                user_messages.append(user_msg)
                print(f"🔍 Line {i}: Found User: {user_msg}")
        
        print(f"🔍 Debug: Found {len(agent_messages)} agent messages, {len(user_messages)} user messages")
        
        # Second pass: create meaningful turns by pairing them intelligently
        for i, user_msg in enumerate(user_messages):
            # Skip meaningless user responses
            if user_msg in ['...', '', 'J-J-', 'J-J-', '...']:
                continue
                
            # Find the most recent agent message before this user response
            # For simplicity, use the agent message at the same index or previous
            if i < len(agent_messages):
                agent_msg = agent_messages[i]
            elif len(agent_messages) > 0:
                agent_msg = agent_messages[-1]  # Use last agent message
            else:
                continue
                
            # Create a meaningful turn
            turn = f"Agent: {agent_msg} User: {user_msg}"
            turns.append(turn)
            print(f"🔍 Created turn: Agent: {agent_msg[:50]}... User: {user_msg}")
        
        print(f"🔍 Debug: Created {len(turns)} total turns")
        return turns
        
    except Exception as e:
        print(f"❌ Error parsing conversation file: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return []

def test_baked_conversation(backend_agent, file_path):
    """Test the backend agent with pre-baked conversation"""
    print("🧪 Testing Pre-baked Conversation")
    print("=" * 50)
    
    turns = parse_conversation_file(file_path)
    if not turns:
        print("❌ No valid conversation turns found")
        return
    
    print(f"📋 Found {len(turns)} valid conversation turns")
    print("\n🎯 Testing each turn:")
    
    for i, turn in enumerate(turns, 1):
        print(f"\n--- Turn {i}/{len(turns)} ---")
        print(f"📝 Input: {turn}")
        
        # Extract just the user response for analysis
        user_response = turn.split('User:')[1].strip()
        if len(user_response) < 3:
            print("⏭️ Skipping very short user response")
            continue
        
        try:
            result = backend_agent.get_response(turn)
            
            if result:
                tool_name = result.get('tool_name', 'null')
                print(f"✅ Result: {tool_name}")
                
                if tool_name != 'null' and 'parameters' in result:
                    print(f"⚙️ Parameters: {result['parameters']}")
                    
                # Show generated prompt snippet
                if 'user_prompt' in result and result['user_prompt']:
                    prompt_snippet = result['user_prompt'][:100] + "..." if len(result['user_prompt']) > 100 else result['user_prompt']
                    print(f"🎨 FLUX Prompt: {prompt_snippet}")
            else:
                print("❌ No result")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Pause between turns for readability
        if i < len(turns):
            input("Press Enter to continue to next turn...")
    
    print("\n🎯 Pre-baked conversation test completed!")

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
    print("  Type 'baked' to test with pre-baked conversation from Agent/exampleconversation.txt")
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
            
            if user_input.lower() == 'baked':
                print("🧪 Testing with pre-baked conversation...")
                baked_file = Path("Agent/exampleconversation.txt")
                print(f"🔍 Looking for file: {baked_file.absolute()}")
                print(f"🔍 File exists: {baked_file.exists()}")
                
                if baked_file.exists():
                    test_baked_conversation(backend_agent, baked_file)
                else:
                    print(f"❌ Conversation file not found: {baked_file}")
                    # Try alternative paths
                    alt_paths = [
                        Path("./Agent/exampleconversation.txt"),
                        Path("../Agent/exampleconversation.txt"),
                        Path("exampleconversation.txt")
                    ]
                    for alt_path in alt_paths:
                        print(f"🔍 Trying: {alt_path.absolute()} - Exists: {alt_path.exists()}")
                        if alt_path.exists():
                            print(f"✅ Found file at: {alt_path}")
                            test_baked_conversation(backend_agent, alt_path)
                            break
                continue
            
            if user_input.lower() == 'apitest':
                print("🧪 Testing OpenAI API directly...")
                try:
                    client = OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="gpt-5-mini",
                        messages=[{
                            "role": "user", 
                            "content": "Respond with JSON: {\"test\": \"success\"}"
                        }],
                        max_completion_tokens=50,
                        # temperature=0.1,  # GPT-5-mini only supports default temperature
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
