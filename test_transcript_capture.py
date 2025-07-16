"""
Test Script for Transcript Capture
Run this to verify that both user and agent transcripts are being captured correctly.
"""
import os
import time
import sys
from pathlib import Path

# Add the launcher directory to the path
sys.path.append(str(Path(__file__).parent / "launcher"))

def test_transcript_capture():
    """Test the transcript capture functionality."""
    print("=== CONJURE TRANSCRIPT CAPTURE TEST ===")
    
    # Check if required environment variables are set
    if not os.getenv("ELEVENLABS_API_KEY"):
        print("❌ ELEVENLABS_API_KEY not set")
        return False
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set")
        return False
    
    print("✅ API keys are set")
    
    try:
        from backend_agent import BackendAgent
        from conversational_agent import ConversationalAgent
        from instruction_manager import InstructionManager
        from state_manager import StateManager
        
        print("✅ All modules imported successfully")
        
        # Initialize components
        state_manager = StateManager()
        instruction_manager = InstructionManager(state_manager)
        backend_agent = BackendAgent(instruction_manager=instruction_manager)
        conversational_agent = ConversationalAgent(backend_agent=backend_agent)
        
        print("✅ Components initialized successfully")
        print("\n🎤 Starting transcript capture test...")
        print("🗣️  Please speak to the agent when prompted")
        print("🤖 We'll monitor for both user and agent transcripts")
        print("⏹️  Press Ctrl+C to stop the test\n")
        
        # Start the conversational agent
        conversational_agent.start()
        
        print("📝 Monitoring transcript_debug.txt for results...")
        print("   - Look for: 'USER (Whisper): ...' entries")
        print("   - Look for: 'AGENT: ...' entries")
        print("   - Look for: '🎯 FOUND AGENT RESPONSE EVENT:' messages")
        
        # Monitor for a while
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️ Test stopped by user")
            conversational_agent.stop()
            
        print("\n📊 Test Results:")
        
        # Check transcript_debug.txt for results
        debug_file = Path("transcript_debug.txt")
        if debug_file.exists():
            with open(debug_file, 'r') as f:
                content = f.read()
                
            user_whisper_count = content.count("USER (Whisper):")
            user_sdk_count = content.count("USER_SDK:")
            agent_count = content.count("AGENT:")
            
            print(f"   - User transcripts (Whisper): {user_whisper_count}")
            print(f"   - User transcripts (SDK): {user_sdk_count}")
            print(f"   - Agent transcripts: {agent_count}")
            
            if user_whisper_count > 0:
                print("✅ User speech transcription working")
            else:
                print("❌ User speech transcription not detected")
                
            if agent_count > 0:
                print("✅ Agent response capture working")
                return True
            else:
                print("❌ Agent response capture not working")
                print("💡 Check console output for '🎯 FOUND AGENT RESPONSE EVENT:' messages")
                return False
        else:
            print("❌ No transcript_debug.txt file found")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_transcript_capture()
    if success:
        print("\n🎉 SUCCESS: Both user and agent transcripts are being captured!")
    else:
        print("\n🔧 Issues detected. Check the console output and transcript_debug.txt for details.") 