#!/usr/bin/env python3
"""
CONJURE Session Cleaner
Resets transcript and prompt files at the start of each session
"""

import os
from pathlib import Path
import json
import time

class SessionCleaner:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.generated_text_dir = self.project_root / "data" / "generated_text"
        
        # Ensure directory exists
        self.generated_text_dir.mkdir(parents=True, exist_ok=True)
        
    def clean_session(self):
        """Clean all session files at startup"""
        print("🧹 CONJURE Session Cleaner - Starting fresh session...")
        
        # Files to clean/reset
        files_to_clean = [
            "user_transcript.txt",  # Whisper transcription history
            "userPrompt.txt",       # Current FLUX prompt
            "selectedControlNet.txt"  # ControlNet selection
        ]
        
        cleaned_files = []
        
        for filename in files_to_clean:
            file_path = self.generated_text_dir / filename
            try:
                if file_path.exists():
                    # Reset file with empty content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("")
                    cleaned_files.append(filename)
                    print(f"   ✅ Reset: {filename}")
                else:
                    # Create empty file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("")
                    cleaned_files.append(filename)
                    print(f"   ✅ Created: {filename}")
                    
            except Exception as e:
                print(f"   ❌ Error cleaning {filename}: {e}")
        
        # Create session info file
        session_info = {
            "session_start": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cleaned_files": cleaned_files,
            "status": "clean"
        }
        
        session_info_path = self.generated_text_dir / "session_info.json"
        with open(session_info_path, 'w', encoding='utf-8') as f:
            json.dump(session_info, f, indent=2)
        
        print(f"🎉 Session cleaned successfully! {len(cleaned_files)} files reset.")
        print(f"📁 Session info saved to: {session_info_path}")
        
        return True

def clean_session():
    """Convenience function for external calls"""
    cleaner = SessionCleaner()
    return cleaner.clean_session()

if __name__ == "__main__":
    clean_session() 