"""
Backend Agent (Agent B)
Handles interaction with the OpenAI Chat Completions API to get structured instructions.
Now uses the custom ChatGPT "VIBE Backend" instead of Assistant API.
"""
import os
import json
import base64
from openai import OpenAI
from pathlib import Path
from instruction_manager import InstructionManager

# Custom ChatGPT ID from the provided URL: https://chatgpt.com/g/g-68742df47c3881918fc61172bf53d4b4-vibe-backend
CUSTOM_GPT_MODEL = "gpt-4o"  # Use the latest model that supports custom instructions

class BackendAgent:
    def __init__(self, instruction_manager: InstructionManager):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=api_key)
        self.instruction_manager = instruction_manager
        
        # System prompt that mimics the VIBE Backend custom GPT behavior
        self.system_prompt = """You are VIBE Backend, a specialized AI assistant for the CONJURE 3D modeling system. You coordinate between a conversational agent (Agent A) and Blender through structured JSON responses.

Your role:
1. Analyze conversations between users and the conversational agent
2. Process visual context from 3D model screenshots
3. Generate structured instructions for 3D modeling workflows
4. Create detailed prompts for AI image/model generation

Available tools:
- spawn_primitive: Create basic 3D shapes (cube, sphere, cylinder, etc.)
- generate_concepts: Generate concept art options based on descriptions
- select_concept: Choose and refine a specific concept
- request_segmentation: Analyze model topology for editing
- isolate_segment: Focus on specific model parts
- apply_material: Add materials and textures
- export_final_model: Save completed model
- undo_last_action: Revert previous operation
- import_last_model: Load the most recent generated model

Response format:
{
  "vision": "Description of what you see in the 3D viewport",
  "user_prompt": "Detailed prompt for AI generation based on user intent",
  "instruction": "Brief instruction summary",
  "tool_name": "specific_tool_name",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  }
}

Focus on understanding user creative intent and translating it into actionable 3D modeling steps."""

    def _encode_image_to_base64(self, image_path):
        """Encode image to base64 for Chat Completions API."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image: {e}")
            return None

    def get_response(self, conversation_history: str):
        """
        Gets a structured response from the OpenAI Chat Completions API based on the conversation and image context.
        """
        print(f"Received conversation for backend processing:\n{conversation_history}")

        # 1. Prepare the context image from Blender
        image_path = Path(__file__).parent.parent / "data" / "generated_images" / "gestureCamera" / "render.png"
        image_base64 = None
        
        if image_path.exists():
            image_base64 = self._encode_image_to_base64(image_path)
            if image_base64:
                print("✅ Context image encoded for Chat Completions API")
            else:
                print("⚠️ Failed to encode context image")
        else:
            print("⚠️ gestureCamera/render.png not found. Proceeding without image context.")

        # 2. Prepare the messages for Chat Completions
        messages = [
            {
                "role": "system", 
                "content": self.system_prompt
            }
        ]
        
        # Add user message with conversation history and optional image
        if image_base64:
            # Message with both text and image
            messages.append({  # type: ignore
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Here is the latest conversation turn between the user and the conversational AI. "
                            "Based on this, and the attached image of the current 3D model, "
                            "please provide the next action as a structured JSON response.\n\n"
                            f"--- CONVERSATION ---\n{conversation_history}"
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            })
        else:
            # Text-only message
            messages.append({  # type: ignore
                "role": "user",
                "content": (
                    "Here is the latest conversation turn between the user and the conversational AI. "
                    "Based on this conversation, please provide the next action as a structured JSON response.\n\n"
                    f"--- CONVERSATION ---\n{conversation_history}"
                )
            })

        try:
            # 3. Call the Chat Completions API
            response = self.client.chat.completions.create(
                model=CUSTOM_GPT_MODEL,
                messages=messages,  # type: ignore
                max_tokens=1000,
                temperature=0.7,
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            # 4. Extract the response
            if response.choices and response.choices[0].message.content:
                agent_response_str = response.choices[0].message.content.strip()
                print(f"✅ Received response from Chat Completions API")
                return self._parse_and_process_response(agent_response_str)
            else:
                print("❌ Error: No content in Chat Completions response")
                return None

        except Exception as e:
            print(f"❌ Error interacting with Chat Completions API: {e}")
            return None

    def _parse_and_process_response(self, response_str: str):
        """Parses the JSON response from the agent and acts on it."""
        print(f"AGENT B RESPONSE:\n{response_str}")
        try:
            # Parse the JSON response
            response_json = json.loads(response_str)
            
            # Write vision summary
            vision_summary = response_json.get("vision")
            if vision_summary:
                # Write to the expected location for vision descriptions
                vision_path = Path(__file__).parent.parent / "screen_description.txt"
                with open(vision_path, 'w', encoding='utf-8') as f:
                    f.write(vision_summary)
                print(f"✅ Wrote vision summary to {vision_path}")

            # Write user prompt for AI generation
            user_prompt = response_json.get("user_prompt")
            if user_prompt:
                prompt_path = Path(__file__).parent.parent / "data" / "generated_text" / "userPrompt.txt"
                prompt_path.parent.mkdir(parents=True, exist_ok=True)
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(user_prompt)
                print("✅ Updated userPrompt.txt")

            # Execute instruction
            instruction = response_json.get("instruction")
            tool_name = response_json.get("tool_name")
            parameters = response_json.get("parameters")

            if tool_name:
                # Construct the instruction object for the manager
                full_instruction = {
                    "tool_name": tool_name,
                    "parameters": parameters or {}
                }
                print(f"🔧 Executing tool: {tool_name}")
                self.instruction_manager.execute_instruction(full_instruction)
                return full_instruction
            elif instruction:
                # Handle legacy format if needed
                print("⚠️ Received legacy instruction format")
                self.instruction_manager.execute_instruction(instruction)
                return instruction

            return None

        except json.JSONDecodeError as e:
            print(f"❌ Error: Could not decode JSON from agent response: {e}")
            print(f"Raw response: {response_str}")
            return None
        except KeyError as e:
            print(f"❌ Error: Response JSON missing expected key: {e}")
            return None
        except Exception as e:
            print(f"❌ Error processing agent response: {e}")
            return None 