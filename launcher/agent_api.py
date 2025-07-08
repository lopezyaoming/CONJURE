"""
ElevenLabs API integration for conversational agent.
Handles voice interaction and response generation.
"""
import os
import json
from openai import OpenAI
from pathlib import Path
from instruction_manager import InstructionManager

class ConversationalAgent:
    def __init__(self, api_key: str, instruction_manager: InstructionManager):
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=api_key)
        self.instruction_manager = instruction_manager
        self.history = []
        self.system_prompt = self._load_system_prompt()
        self.history.append({"role": "system", "content": self.system_prompt})

    def _load_system_prompt(self):
        try:
            # Assuming the script is run from the project root (e.g., /CONJURE/launcher)
            # and devnotes is at the same level
            prompt_path = Path(__file__).parent.parent / "devnotes" / "agentPrompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print("ERROR: devnotes/agentPrompt.txt not found. Agent will use a basic prompt.")
            return "You are a helpful assistant. Respond in JSON."

    def get_response(self, user_message):
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
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
            
            if instruction:
                self.instruction_manager.execute_instruction(instruction)
            
            return instruction

        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON response from agent: {response_str}")
            return None
        except KeyError as e:
            print(f"Error: Response JSON missing expected key: {e}")
            return None 