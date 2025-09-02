#!/usr/bin/env python3
"""
CONJURE Data Package Builder
Builds consistent data packages for ChatGPT with proper labeling
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional

class DataPackageBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.generated_text_dir = self.project_root / "data" / "generated_text"
        
        # File paths
        self.user_transcript_path = self.generated_text_dir / "user_transcript.txt"
        self.user_prompt_path = self.generated_text_dir / "userPrompt.txt"
        
    def save_whisper_transcript(self, transcript: str):
        """Save the latest Whisper transcription, resetting previous content"""
        try:
            # Reset and write new transcript (overwrites previous)
            with open(self.user_transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript.strip())
            print(f"💾 Saved Whisper transcript: {transcript[:50]}...")
            return True
        except Exception as e:
            print(f"❌ Error saving transcript: {e}")
            return False
    
    def read_user_transcript(self) -> str:
        """Read the current user transcript"""
        try:
            if self.user_transcript_path.exists():
                with open(self.user_transcript_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                return content if content else ""
            return ""
        except Exception as e:
            print(f"❌ Error reading user transcript: {e}")
            return ""
    
    def read_user_prompt(self) -> str:
        """Read the complete userPrompt.txt string"""
        try:
            if self.user_prompt_path.exists():
                with open(self.user_prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                return content if content else ""
            return ""
        except Exception as e:
            print(f"❌ Error reading user prompt: {e}")
            return ""
    
    def build_chatgpt_package(self, new_transcript: Optional[str] = None) -> Dict[str, str]:
        """
        Build the standardized data package for ChatGPT
        
        Args:
            new_transcript: If provided, saves this as the new transcript first
            
        Returns:
            Dict with properly labeled user_transcription and user_prompt
        """
        
        # Save new transcript if provided
        if new_transcript:
            self.save_whisper_transcript(new_transcript)
        
        # Read current data
        user_transcription = self.read_user_transcript()
        user_prompt = self.read_user_prompt()
        
        # Build the standardized package
        package = {
            "user_transcription": user_transcription,
            "user_prompt": user_prompt
        }
        
        print(f"📦 Built ChatGPT package:")
        print(f"   🎤 User transcription: {user_transcription[:50]}..." if user_transcription else "   🎤 User transcription: (empty)")
        print(f"   📝 User prompt: {user_prompt[:50]}..." if user_prompt else "   📝 User prompt: (empty)")
        
        return package
    
    def format_for_chatgpt_api(self, new_transcript: Optional[str] = None) -> str:
        """
        Format the package as a properly labeled string for ChatGPT API
        
        Returns:
            Formatted string ready for ChatGPT system prompt
        """
        package = self.build_chatgpt_package(new_transcript)
        
        formatted_message = f"""CONTEXT DATA:

user_transcription: "{package['user_transcription']}"

user_prompt: "{package['user_prompt']}"

Please process this user input and update the structured FLUX prompt accordingly."""
        
        return formatted_message
    
    def get_package_status(self) -> Dict[str, any]:
        """Get status of current data package"""
        user_transcript = self.read_user_transcript()
        user_prompt = self.read_user_prompt()
        
        return {
            "transcript_exists": bool(user_transcript),
            "transcript_length": len(user_transcript),
            "prompt_exists": bool(user_prompt),
            "prompt_length": len(user_prompt),
            "transcript_preview": user_transcript[:100] if user_transcript else None,
            "prompt_preview": user_prompt[:100] if user_prompt else None
        }

def build_package(new_transcript: Optional[str] = None) -> Dict[str, str]:
    """Convenience function for external calls"""
    builder = DataPackageBuilder()
    return builder.build_chatgpt_package(new_transcript)

def format_for_api(new_transcript: Optional[str] = None) -> str:
    """Convenience function for API formatting"""
    builder = DataPackageBuilder()
    return builder.format_for_chatgpt_api(new_transcript)

if __name__ == "__main__":
    # Test the package builder
    builder = DataPackageBuilder()
    status = builder.get_package_status()
    print("📊 Package Status:", json.dumps(status, indent=2)) 