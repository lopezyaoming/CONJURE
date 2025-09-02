#!/usr/bin/env python3
"""
CONJURE Whisper → ChatGPT → userPrompt Pipeline Tester

Isolated test for the voice transcription and prompt generation pipeline.
Launch this script and start speaking to see the full pipeline in action.

Features:
- Real-time Whisper transcription
- ChatGPT prompt generation with new data package format
- Live userPrompt.txt updates
- Clear console output for debugging
- Automatic session cleaning on startup
"""

import os
import sys
import time
import json
import threading
from pathlib import Path

# Add launcher directory to path for imports
launcher_dir = Path(__file__).parent / "launcher"
sys.path.insert(0, str(launcher_dir))

# Import CONJURE components
from session_cleaner import clean_session
from data_package_builder import DataPackageBuilder
from backend_agent import BackendAgent
from voice_processor import VoiceProcessor
from instruction_manager import InstructionManager
from state_manager import StateManager

class WhisperChatGPTPipelineTester:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.generated_text_dir = self.project_root / "data" / "generated_text"
        self.user_prompt_path = self.generated_text_dir / "userPrompt.txt"
        
        # Initialize components
        self.data_builder = DataPackageBuilder()
        self.state_manager = StateManager()
        self.instruction_manager = InstructionManager(self.state_manager)
        self.backend_agent = BackendAgent(self.instruction_manager)
        self.voice_processor = None
        
        # Status tracking
        self.last_prompt = ""
        self.transcript_count = 0
        
        print("🎤🤖 CONJURE Whisper → ChatGPT → userPrompt Pipeline Tester")
        print("=" * 70)
        
    def setup(self):
        """Initialize the testing environment"""
        print("\n🧹 STEP 1: Cleaning session...")
        clean_session()
        
        print("\n🎤 STEP 2: Initializing voice processor...")
        try:
            self.voice_processor = VoiceProcessor(self.backend_agent)
            
            # Override the voice processor's callback to use our test handler
            original_callback = self.voice_processor._update_prompt_with_speech
            self.voice_processor._update_prompt_with_speech = self.handle_speech_transcript
            
            print("✅ Voice processor initialized successfully!")
        except Exception as e:
            print(f"❌ Error initializing voice processor: {e}")
            return False
            
        print("\n📝 STEP 3: Testing ChatGPT connection...")
        try:
            # Test with a simple transcript
            test_result = self.backend_agent.process_voice_input("Testing connection")
            print("✅ ChatGPT connection working!")
        except Exception as e:
            print(f"❌ Error connecting to ChatGPT: {e}")
            return False
            
        return True
    
    def handle_speech_transcript(self, transcript):
        """Handle new speech transcripts and show the full pipeline"""
        self.transcript_count += 1
        
        print(f"\n{'='*70}")
        print(f"🎤 TRANSCRIPT #{self.transcript_count}: {transcript}")
        print(f"{'='*70}")
        
        # Step 1: Save transcript
        print("\n📝 STEP 1: Saving Whisper transcript...")
        success = self.data_builder.save_whisper_transcript(transcript)
        if success:
            print(f"✅ Saved to user_transcript.txt: '{transcript[:50]}...'")
        else:
            print("❌ Failed to save transcript")
            return
            
        # Step 2: Read current prompt state
        print("\n📖 STEP 2: Reading current prompt state...")
        current_prompt = self.data_builder.read_user_prompt()
        if current_prompt:
            print(f"📝 Current userPrompt.txt: '{current_prompt[:100]}...'")
        else:
            print("📝 userPrompt.txt is empty (starting fresh)")
            
        # Step 3: Build data package
        print("\n📦 STEP 3: Building ChatGPT data package...")
        package = self.data_builder.build_chatgpt_package()
        formatted_message = self.data_builder.format_for_chatgpt_api()
        
        print("📦 Data Package Contents:")
        print(f"   🎤 user_transcription: '{package['user_transcription']}'")
        print(f"   📝 user_prompt: '{package['user_prompt'][:100] if package['user_prompt'] else '(empty)'}...'")
        
        # Step 4: Send to ChatGPT
        print("\n🤖 STEP 4: Sending to ChatGPT...")
        print(f"📤 Formatted message preview:")
        print(f"   {formatted_message[:200]}...")
        
        try:
            start_time = time.time()
            response = self.backend_agent.process_voice_input(transcript)
            end_time = time.time()
            
            print(f"✅ ChatGPT responded in {end_time - start_time:.2f}s")
            print(f"🤖 Response preview: {str(response)[:200]}...")
            
        except Exception as e:
            print(f"❌ ChatGPT error: {e}")
            return
            
        # Step 5: Check userPrompt.txt update
        print("\n📄 STEP 5: Checking userPrompt.txt update...")
        new_prompt = self.read_user_prompt()
        
        if new_prompt != self.last_prompt:
            print("✅ userPrompt.txt was updated!")
            print(f"📝 NEW PROMPT: {new_prompt}")
            self.last_prompt = new_prompt
            
            # Show the difference
            if current_prompt:
                print(f"\n🔄 PROMPT EVOLUTION:")
                print(f"   BEFORE: {current_prompt[:100]}...")
                print(f"   AFTER:  {new_prompt[:100]}...")
        else:
            print("⚠️ userPrompt.txt was not changed")
            
        print(f"\n{'='*70}")
        print(f"✅ Pipeline complete! Ready for next speech input...")
        print(f"{'='*70}")
    
    def read_user_prompt(self):
        """Read the current userPrompt.txt content"""
        try:
            if self.user_prompt_path.exists():
                with open(self.user_prompt_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            return ""
        except Exception as e:
            print(f"❌ Error reading userPrompt.txt: {e}")
            return ""
    
    def start_monitoring(self):
        """Start the file monitoring thread"""
        def monitor_files():
            while True:
                time.sleep(2)
                # Could add periodic status updates here if needed
                pass
        
        monitor_thread = threading.Thread(target=monitor_files, daemon=True)
        monitor_thread.start()
    
    def run(self):
        """Main test loop"""
        if not self.setup():
            print("❌ Setup failed. Exiting.")
            return
            
        print(f"\n🚀 PIPELINE TESTER READY!")
        print(f"{'='*70}")
        print(f"🗣️ Start speaking to test the pipeline:")
        print(f"   1. Your speech will be transcribed by Whisper")
        print(f"   2. Transcript + current prompt sent to ChatGPT") 
        print(f"   3. ChatGPT updates the structured FLUX prompt")
        print(f"   4. userPrompt.txt gets updated")
        print(f"   5. Full pipeline status shown in console")
        print(f"")
        print(f"💡 Try saying things like:")
        print(f"   • 'Create a skull'")
        print(f"   • 'Make it more detailed'") 
        print(f"   • 'Change the material to gold'")
        print(f"   • 'Add some texture'")
        print(f"")
        print(f"Press Ctrl+C to stop")
        print(f"{'='*70}")
        
        # Start file monitoring
        self.start_monitoring()
        
        # Start voice processing
        try:
            self.voice_processor.start()
            
            # Keep the main thread alive
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Stopping pipeline tester...")
            if self.voice_processor:
                self.voice_processor.stop()
            print(f"✅ Pipeline tester stopped successfully!")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
        finally:
            if self.voice_processor:
                self.voice_processor.stop()

def main():
    """Entry point for the pipeline tester"""
    tester = WhisperChatGPTPipelineTester()
    tester.run()

if __name__ == "__main__":
    main()
