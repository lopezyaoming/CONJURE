"""
ElevenLabs API integration for conversational agent.
Handles voice interaction and response generation.
"""
import os
import json
from openai import OpenAI
from pathlib import Path
from instruction_manager import InstructionManager
from elevenlabs import play
from elevenlabs.client import ElevenLabs

# --- ElevenLabs Configuration ---
# You can find your Voice ID in the Voice Lab on the ElevenLabs website.
# 'Adam' is a good, deep, generic male voice.
TTS_VOICE_ID = "XcXEQzuLXRU9RcfWzEJt" 
# This is the latest and highest-quality model.
TTS_MODEL_ID = "eleven_flash_v2_5"

class ConversationalAgent:
    def __init__(self, openai_api_key: str, instruction_manager: InstructionManager):
        if not openai_api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        self.openai_client = OpenAI(api_key=openai_api_key)
        
        elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not elevenlabs_api_key:
            raise ValueError("ElevenLabs API key not found. Please set the ELEVENLABS_API_KEY environment variable.")
        self.elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)

        self.instruction_manager = instruction_manager
        self.history = []
        self.system_prompt = self._load_system_prompt()
        self.history.append({"role": "system", "content": self.system_prompt})

    def _load_system_prompt(self):
        try:
            prompt_path = Path(__file__).parent.parent / "devnotes" / "agentPrompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # The agentToolset.txt was deleted, so we can't rely on the old prompt.
            print("WARNING: devnotes/agentPrompt.txt not found. Agent will use a basic prompt.")
            return "You are a helpful 3D design assistant named Conjure. Respond in JSON."

    def get_response(self, user_message):
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=self.history,
                response_format={"type": "json_object"}
            )
            
            agent_response_str = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": agent_response_str})

            # Keep history from getting too long
            if len(self.history) > 10:
                self.history = [self.history[0]] + self.history[-9:]

            return self._parse_and_process_response(agent_response_str)

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return None

    def _play_agent_response(self, text: str):
        """Converts text to speech and plays it using ElevenLabs."""
        try:
            print("AGENT_API: Generating audio from ElevenLabs...")
            audio = self.elevenlabs_client.text_to_speech.convert(
                text=text,
                voice_id=TTS_VOICE_ID,
                model_id=TTS_MODEL_ID,
            )
            print("AGENT_API: Playing audio...")
            play(audio)
            print("AGENT_API: Audio playback finished.")
        except Exception as e:
            print(f"AGENT_API: Error playing ElevenLabs audio: {e}")

    def _parse_and_process_response(self, response_str):
        try:
            response_json = json.loads(response_str)
            
            spoken_text = response_json.get("spoken")
            instruction = response_json.get("instruction")

            if "user_prompt" in response_json:
                user_prompt = response_json.get("user_prompt")
                prompt_path = Path(__file__).parent.parent / "data" / "generated_text" / "userPrompt.txt"
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(user_prompt or "") # Always write, use empty string if prompt is null
                print("Updated userPrompt.txt.")

            if spoken_text:
                print(f"AGENT: {spoken_text}")
                self._play_agent_response(spoken_text)
            
            if instruction:
                self.instruction_manager.execute_instruction(instruction)
            
            return spoken_text

        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON response from agent: {response_str}")
            return None
        except KeyError as e:
            print(f"Error: Response JSON missing expected key: {e}")
            return None 