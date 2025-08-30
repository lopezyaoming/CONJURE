#!/usr/bin/env python3
"""
Backend Agent Console Chat - Direct testing tool for CONJURE Backend Agent (Phase 2)

This script allows you to directly test the backend agent's voice input processing
without running the full CONJURE application. Useful for debugging and testing.

UPDATED FOR PHASE 1/2: Now tests process_voice_input() instead of get_response()

Usage:
    python test_backend_chat.py

Commands:
    - Type 'quit' or 'exit' to stop
    - Type 'test' for a simple voice input test
    - Type 'apitest' to test OpenAI API directly
    - Or type any speech transcript like: 'make it more curved'
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

# Removed old conversation parsing functions - no longer needed for Phase 2 voice input testing

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

    print("\n🎯 Voice Input Commands:")
    print("  Type 'quit' or 'exit' to stop")
    print("  Type 'test' for a simple voice input test")
    print("  Type 'apitest' to test OpenAI API directly")
    print("  Or type any speech transcript like: 'make it more curved'")
    print("  Or: 'change the color to blue'")
    print("  Or: 'add metallic finish'")
    print("\n" + "=" * 50)

    while True:
        try:
            user_input = input("\n🎤 Enter speech transcript: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'test':
                user_input = "make it more curved and add a metallic finish"
                print(f"🧪 Testing with speech transcript: {user_input}")
            
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
            
            print(f"\n🚀 Processing voice input with backend agent...")
            print(f"🎤 Speech transcript: {user_input}")
            
            # Call the backend agent's voice processing method
            result = backend_agent.process_voice_input(
                speech_transcript=user_input,
                current_prompt_state=None,  # Let it read the current state
                gesture_render_path=None    # No gesture render for console testing
            )
            
            print(f"\n📊 Backend Agent Response:")
            print("-" * 30)
            if result:
                print("✅ Voice processing successful!")
                print(f"📄 Response Type: {type(result)}")
                print(f"📋 Structured Response: {result}")
                
                if isinstance(result, dict):
                    print(f"\n🔍 Parsed FLUX Prompt Components:")
                    if "subject" in result:
                        subject = result["subject"]
                        if "name" in subject:
                            print(f"  📝 Object Name: {subject['name']}")
                        if "form_keywords" in subject:
                            print(f"  🔲 Form: {', '.join(subject['form_keywords'])}")
                        if "material_keywords" in subject:
                            print(f"  🏗️  Materials: {', '.join(subject['material_keywords'])}")
                        if "color_keywords" in subject:
                            print(f"  🎨 Colors: {', '.join(subject['color_keywords'])}")
                
                # Check if userPrompt.txt was updated
                prompt_path = Path("data/generated_text/userPrompt.txt")
                if prompt_path.exists():
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        updated_prompt = f.read()
                    print(f"\n📝 Updated userPrompt.txt:")
                    print(f"   {updated_prompt[:150]}...")
                else:
                    print("\n⚠️ userPrompt.txt not found or not updated")
            else:
                print("❌ Voice processing failed or returned no result")
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
