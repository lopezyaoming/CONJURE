"""
Debug script for CONJURE Conversational Agent
Helps analyze and control conversation issues
"""
import sys
import os

# Add both the current directory and launcher directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
launcher_dir = os.path.join(project_root, 'launcher')
sys.path.insert(0, project_root)
sys.path.insert(0, launcher_dir)

import time
import json

def main():
    print("🐛 CONJURE Conversation Debug Tool")
    print("="*50)
    
    # Try to import the conversational agent with better error handling
    try:
        # Import from launcher directory
        from launcher.conversational_agent import ConversationalAgent
        print("✅ ConversationalAgent imported successfully")
        
        # Initialize the conversational agent (without starting)
        agent = ConversationalAgent()
        print("✅ Conversational agent initialized")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("🔧 Trying alternative import method...")
        
        try:
            # Alternative: Import directly from the launcher directory
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'launcher'))
            from conversational_agent import ConversationalAgent
            agent = ConversationalAgent()
            print("✅ Conversational agent initialized (alternative method)")
        except Exception as e2:
            print(f"❌ Failed to initialize agent: {e2}")
            print("\n🔍 Debug info:")
            print(f"   Current directory: {os.getcwd()}")
            print(f"   Script location: {os.path.dirname(os.path.abspath(__file__))}")
            print(f"   Python path: {sys.path[:3]}...")
            return
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        print(f"   Error type: {type(e).__name__}")
        return
    
    # Run the interactive debug menu
    run_debug_menu(agent)

def run_debug_menu(agent):
    """Run the interactive debug menu."""
    while True:
        print("\n🐛 Debug Options:")
        print("1. Show conversation status")
        print("2. Show transcript sources")
        print("3. Disable transcript source")
        print("4. Enable transcript source")
        print("5. Clear transcript debug file")
        print("6. Show recent transcripts")
        print("7. Test agent methods")
        print("8. Check current turn status")
        print("9. Apply quick fixes")
        print("10. Exit")
        
        choice = input("\nEnter choice (1-10): ").strip()
        
        try:
            if choice == "1":
                show_conversation_status(agent)
            elif choice == "2":
                show_transcript_sources(agent)
            elif choice == "3":
                disable_source(agent)
            elif choice == "4":
                enable_source(agent)
            elif choice == "5":
                clear_debug_file()
            elif choice == "6":
                show_recent_transcripts()
            elif choice == "7":
                test_agent_methods(agent)
            elif choice == "8":
                check_current_turn_status(agent)
            elif choice == "9":
                apply_quick_fixes()
            elif choice == "10":
                print("👋 Exiting debug tool")
                break
            else:
                print("❌ Invalid choice")
        except Exception as e:
            print(f"❌ Error executing option {choice}: {e}")

def show_conversation_status(agent):
    """Show current conversation status."""
    print("\n" + "="*50)
    print("📊 CONVERSATION STATUS")
    print("="*50)
    
    try:
        status = agent.get_conversation_status()
        print(f"🏃 Running: {status['is_running']}")
        print(f"📝 Current Turn: {status['current_turn']}")
        print(f"📚 History Length: {status['conversation_history_length']}")
        
        if status['turn_start_time']:
            elapsed = time.time() - status['turn_start_time']
            print(f"⏱️ Turn Elapsed: {elapsed:.1f}s")
        
        # Show current turn details
        if hasattr(agent, 'current_turn'):
            turn = agent.current_turn
            print(f"\n🔍 CURRENT TURN DETAILS:")
            print(f"   User Message: {turn.get('user_message', 'None')}")
            print(f"   Agent Message: {turn.get('agent_message', 'None')}")
            print(f"   Turn Complete: {turn.get('turn_complete', False)}")
        
        # Show detailed status
        if hasattr(agent, 'print_debug_status'):
            agent.print_debug_status()
        else:
            print("⚠️ print_debug_status method not available")
            
    except Exception as e:
        print(f"❌ Error getting conversation status: {e}")

def show_transcript_sources(agent):
    """Show current transcript source settings."""
    print("\n" + "="*50)
    print("📡 TRANSCRIPT SOURCES")
    print("="*50)
    
    try:
        if hasattr(agent, 'transcript_sources'):
            for source, enabled in agent.transcript_sources.items():
                status = "🟢 ENABLED" if enabled else "🔴 DISABLED"
                print(f"{source}: {status}")
        else:
            print("⚠️ transcript_sources not available")
    except Exception as e:
        print(f"❌ Error showing transcript sources: {e}")

def disable_source(agent):
    """Disable a transcript source."""
    try:
        if not hasattr(agent, 'transcript_sources'):
            print("⚠️ transcript_sources not available")
            return
            
        print("\nAvailable sources:")
        for i, source in enumerate(agent.transcript_sources.keys(), 1):
            status = "🟢" if agent.transcript_sources[source] else "🔴"
            print(f"{i}. {source} {status}")
        
        choice = int(input("Enter source number to disable: ")) - 1
        sources = list(agent.transcript_sources.keys())
        if 0 <= choice < len(sources):
            if hasattr(agent, 'disable_transcript_source'):
                agent.disable_transcript_source(sources[choice])
            else:
                agent.transcript_sources[sources[choice]] = False
                print(f"🔴 DISABLED transcript source: {sources[choice]}")
        else:
            print("❌ Invalid choice")
    except ValueError:
        print("❌ Please enter a number")
    except Exception as e:
        print(f"❌ Error disabling source: {e}")

def enable_source(agent):
    """Enable a transcript source."""
    try:
        if not hasattr(agent, 'transcript_sources'):
            print("⚠️ transcript_sources not available")
            return
            
        print("\nAvailable sources:")
        for i, source in enumerate(agent.transcript_sources.keys(), 1):
            status = "🟢" if agent.transcript_sources[source] else "🔴"
            print(f"{i}. {source} {status}")
        
        choice = int(input("Enter source number to enable: ")) - 1
        sources = list(agent.transcript_sources.keys())
        if 0 <= choice < len(sources):
            agent.transcript_sources[sources[choice]] = True
            print(f"🟢 ENABLED transcript source: {sources[choice]}")
        else:
            print("❌ Invalid choice")
    except ValueError:
        print("❌ Please enter a number")
    except Exception as e:
        print(f"❌ Error enabling source: {e}")

def clear_debug_file():
    """Clear the transcript debug file."""
    try:
        with open("transcript_debug.txt", "w") as f:
            f.write("=== CONJURE TRANSCRIPT DEBUG LOG (CLEARED) ===\n")
        print("✅ Transcript debug file cleared")
    except Exception as e:
        print(f"❌ Error clearing debug file: {e}")

def show_recent_transcripts():
    """Show recent transcript entries."""
    try:
        with open("transcript_debug.txt", "r") as f:
            lines = f.readlines()
        
        print("\n" + "="*50)
        print("📝 RECENT TRANSCRIPTS (last 20 lines)")
        print("="*50)
        
        for line in lines[-20:]:
            print(line.strip())
            
    except FileNotFoundError:
        print("❌ No transcript debug file found")
    except Exception as e:
        print(f"❌ Error reading transcripts: {e}")

def test_agent_methods(agent):
    """Test available agent methods."""
    print("\n" + "="*50)
    print("🧪 TESTING AGENT METHODS")
    print("="*50)
    
    methods_to_test = [
        'get_conversation_status',
        'print_debug_status', 
        'disable_transcript_source',
        '_debug_log',
        '_add_user_message',
        'transcript_sources'
    ]
    
    for method_name in methods_to_test:
        if hasattr(agent, method_name):
            print(f"✅ {method_name}: Available")
        else:
            print(f"❌ {method_name}: Not available")

def check_current_turn_status(agent):
    """Check and debug current turn status."""
    print("\n" + "="*50)
    print("🔍 CURRENT TURN DEBUG")
    print("="*50)
    
    try:
        if hasattr(agent, 'check_current_turn_debug'):
            agent.check_current_turn_debug()
        elif hasattr(agent, 'current_turn'):
            turn = agent.current_turn
            print(f"📝 User Message: {turn.get('user_message', 'None')}")
            print(f"🤖 Agent Message: {turn.get('agent_message', 'None')}")
            print(f"✅ Turn Complete: {turn.get('turn_complete', False)}")
            
            # Check if turn should be complete
            has_user = turn.get('user_message') is not None
            has_agent = turn.get('agent_message') is not None
            is_complete = turn.get('turn_complete', False)
            
            print(f"\n🔍 ANALYSIS:")
            print(f"   Has user message: {has_user}")
            print(f"   Has agent message: {has_agent}")
            print(f"   Should be complete: {has_user and has_agent}")
            print(f"   Actually complete: {is_complete}")
            
            if has_user and has_agent and not is_complete:
                print("⚠️ WARNING: Turn should be complete but isn't marked as such!")
                print("💡 This indicates the turn completion logic may not be working.")
        else:
            print("⚠️ Agent doesn't have current_turn attribute")
            
    except Exception as e:
        print(f"❌ Error checking turn status: {e}")

def apply_quick_fixes():
    """Apply quick fixes without needing the full agent."""
    print("\n🔧 Applying quick fixes...")
    
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
            json.dump(fix_config, f, indent=4)
        
        print("✅ Created conversation fix configuration")
        
    except Exception as e:
        print(f"❌ Error creating fix config: {e}")
    
    print("\n🎯 Quick fixes applied successfully!")

if __name__ == "__main__":
    main() 