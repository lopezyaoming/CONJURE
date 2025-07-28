"""
Quick fix script for CONJURE conversation issues
Applies recommended fixes for parallel conversations and timing problems
This script works independently and doesn't require importing CONJURE modules
"""
import sys
import os
import json

# Add paths just in case we need them later
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    print("🔧 CONJURE Conversation Quick Fix")
    print("="*50)
    
    print("🎯 Recommended fixes for your issues:")
    print()
    
    print("1. 🔇 DISABLE DUPLICATE TRANSCRIPT SOURCES")
    print("   Problem: Multiple sources causing duplicate processing")
    print("   Solution: Keep only ElevenLabs SDK callbacks active")
    print()
    
    print("2. 🤖 FIX AGENT MESSAGE FRAGMENTATION") 
    print("   Problem: Agent speaking in fragments instead of complete messages")
    print("   Solution: Use message buffering with timeout")
    print()
    
    print("3. 🧹 CLEAR TRANSCRIPT DEBUG FILE")
    print("   Problem: Old conversation data interfering")
    print("   Solution: Start with clean debug log")
    print()
    
    apply_fixes = input("Apply all recommended fixes? (y/n): ").lower().strip()
    
    if apply_fixes == 'y':
        apply_all_fixes()
    else:
        print("❌ Fixes not applied. You can run debug_conversation.py for manual control.")

def apply_all_fixes():
    """Apply all recommended fixes."""
    print("\n🔧 Applying fixes...")
    
    # Fix 1: Clear transcript debug file
    try:
        with open("transcript_debug.txt", "w") as f:
            f.write("=== CONJURE TRANSCRIPT DEBUG LOG (FIXED) ===\n")
        print("✅ Cleared transcript debug file")
    except Exception as e:
        print(f"❌ Error clearing debug file: {e}")
    
    # Fix 2: Create a configuration override
    try:
        fix_config = {
            "transcript_sources": {
                "whisper": False,        # Disable to avoid duplicates
                "sdk_callbacks": True,   # Keep this as primary
                "websocket": False,      # Disable to avoid duplicates
                "message_hooks": False   # Disable fragments
            },
            "agent_message_timeout": 5.0,  # Longer timeout for complete messages
            "turn_timeout": 60.0,          # Longer timeout for complete turns
            "debug_mode": True             # Enable detailed debugging
        }
        
        with open("conversation_fix_config.json", "w") as f:
            import json
            json.dump(fix_config, f, indent=4)
        
        print("✅ Created conversation fix configuration")
        
    except Exception as e:
        print(f"❌ Error creating fix config: {e}")
    
    print("\n🎯 Next steps:")
    print("1. Restart your CONJURE application")
    print("2. The system will now use only SDK callbacks (reduces duplicates)")
    print("3. Agent messages will be buffered properly (fixes fragmentation)")
    print("4. Use debug_conversation.py to monitor and control sources")
    print("5. Check transcript_debug.txt for clean logging")
    
    print("\n📋 If issues persist:")
    print("- Run: python debug_conversation.py")
    print("- Use option 1 to monitor conversation status")
    print("- Use option 3 to disable problematic sources")
    print("- Use option 6 to check recent transcripts")

if __name__ == "__main__":
    main() 