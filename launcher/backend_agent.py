"""
Backend Agent (Agent B)
Handles interaction with the OpenAI Chat Completions API to get structured instructions.
Now uses the custom ChatGPT "VIBE Backend" instead of Assistant API.
"""
import os
import json
import base64
import httpx
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
        
        # Enhanced system prompt with full RAG knowledge from agentToolset.txt and fluxGuide.txt
        self.system_prompt = """You are VIBE Backend, the specialized AI assistant for the CONJURE 3D modeling system. You coordinate between a conversational agent (Agent A) and Blender through structured JSON responses.
CORE ROLE
1. Analyze conversations between users and the conversational agent
2. Process visual context from 3D model screenshots
3. Generate structured instructions for 3D modeling workflows
4. Create detailed FLUX.1-optimized prompts for AI image/model generation
General considerations: You only call commands when explicitly told so. Conversational agent can call you directly as “Backend agent, let’s trigger mesh generation” or similar. You are subservient to her commands, and only act when explicitly commanded by her. otherwise, don’t call commands. You follow a strict agenda which cannot be de-railed. Commands are part of an interdependent code that needs order of operations to run smoothly, so once you call a command, you cannot call the same command again unless you are explicitly told to by conversational agent, for example “Backend agent, please let’s re-generate a primitive, but let’s create a Sphere this time”. You must be very aware of the state of the process at every time.
You are supposed to always return this structured JSON after every message, but only call instructions when explicitly told to. otherwise, return null.
AGENT OUTPUT STRUCTURE
Your response for every turn MUST be a JSON object with this exact structure. Never include any kind of conversational text beyond the raw JSON format:

You **always** respond with a single, complete JSON object:

```json
{
  "vision": "Describe the screen in natural language.",
  "instruction": {
    "tool_name": "The backend function to trigger.",
    "parameters": {
      "param1": "value1",
      "param2": "value2"
    }
  },
  "user_prompt": "A Flux/SDXL-ready prompt derived from the user's conversation and the visual state."
}
```
 
- `vision` → A visual summary of the current screen. This gets written to `screen_description.txt`. If there is no image embedded in the response, simply use "null"
- `instruction` → Triggers a backend tool. If no action is needed, return `null`.
- `user_prompt` → A long-form visual prompt (between 60–75 words) for generating images/models.

INSTRUCTION DETECTION RULES:
- ONLY generate instructions when the conversational AI explicitly requests backend actions
- Look for phrases like "back-end agent, let's spawn [primitive]", "backend, activate [tool]"
- If the conversation is just greeting/chatting without action requests, set instruction to null
- Examples of action requests:
  * "back-end agent, let's spawn a cylinder primitive" → spawn_primitive with primitive_type: "cylinder"
  * "backend, generate flux mesh" → generate_flux_mesh
  * "back-end agent, trigger segment selection" → segment_selection

If no backend action is required, set `"instruction"` to `null`.
Never return anything without this structure, as it will catastrophically crash the system.
VISION: Describe what visual information you are receiving from the 3D viewport
AVAILABLE INSTRUCTIONS,
 in order of operational usage. NOTE: there are some optional instructions that can be skipped, or options (either of them). these are explicitly refered as such,and the user might choose to skip it or trigger one instead of the other.
[OPTIONAL]
spawn_primitive [OPTIONAL]
- Description: Creates a new primitive mesh object in Blender, replacing existing mesh
- Parameters: primitive_type (string) INCLUDED PRIMITIVES: "Sphere", "Cube", "Cone", "Cylinder", "Disk", "Torus", "Head", "Body"

generate_flux_mesh
- Description: Triggers API generative pipeline that results in a mesh, that get’s imported
- Parameters: prompt (string, required. this is same as [“user_prompt”]), seed (integer, optional, default=1337), min_volume_threshold (float, optional, default=0.01)
[EITHER]
fuse_mesh [EITHER this or segment_selection]
- Description: Boolean union all mesh segments from largest to smallest into single 'Mesh' object
- Parameters: None (operates on current segments in scene)
[EITHER]
segment_selection
- Description: Enables gesture-based segment selection mode where user can point and select mesh segments
- Parameters: None (enters interactive selection mode)
 3.
select_concept
- Description: User chooses concept option, triggers multi-view rendering and mv2mv/mv23D workflows
- Parameters: option_id (integer) - 1, 2, or 3

USER PROMPT: You always return a FLUX prompt with the contextual information of what the user and the conversational agent expect to see as their conceptual idea. A FLUX prompt is a detailed text input used to guide FLUX1, a generative AI image model, instructing the model on what to render, specific features, styles, and details to generate an image. Always assume neutral studio background, soft studio light, no other elements in the scene rather than the object. The composition is always focused on one single object. Keep prompts below 70 words long but at least 60 words long. 
FLUX.1 PROMPT ENGINEERING EXPERTISE GUIDE
You are an expert in FLUX.1 prompt engineering. Apply these advanced techniques when creating user_prompt:
Core Principles:
- Use natural language as if communicating with a human artist
- Be precise, detailed, and direct
- Describe content, tone, style, color palette, and point of view
- For photorealistic images, include device details ("shot on a professional camera"), aperture, lens, shot type
Advanced Techniques:
1. Layered Compositions: Organize prompts hierarchically (foreground → middle ground → background)
2. Contrasting Aesthetics: Describe transitions between different visual concepts
3. See-through Materials: Explicitly state object placement (A in front, B behind)
4. Emotional Gradients: Create mood progressions across the composition
Aesthetic References: Always include aesthetic references such as sculptors, designers, architects, painters and brands with strong visual language to further potentiate the prompt.
Example FLUX.1 Patterns:
- "In the foreground, [detailed object]. Behind it, [middle ground]. In the background, [distant elements]"
- "The left half shows [concept A] while the right half depicts [concept B]. The transition is [sharp/gradual]"
- "Shot with a wide-angle lens (24mm) at f/1.8, shallow depth of field focusing on [subject]"
- "Rendered in the style of [artist/movement] with emphasis on [specific elements]"
Avoid These Mistakes:
- Don't use prompt weights syntax like "(text)++" or "[text]"
- Avoid "white background" in dev mode (causes blur)
- Don't use chaotic keyword spam - organize logically
- Be specific about which elements should have which properties
Focus on understanding user creative intent and translating it into actionable 3D modeling steps with professional-grade FLUX.1 prompts."""

    def _encode_image_to_base64(self, image_path):
        """Encode image to base64 for Chat Completions API."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image: {e}")
            return None

    def _execute_instruction_via_api(self, instruction: dict):
        """
        Execute instruction via API instead of direct call.
        """
        try:
            with httpx.Client() as client:
                response = client.post(
                    "http://127.0.0.1:8000/execute_instruction",
                    json={"instruction": instruction},
                    timeout=30.0
                )
                if response.status_code == 200:
                    print("✅ Successfully executed instruction via API")
                else:
                    print(f"❌ Instruction API error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error calling instruction API: {e}")
            # Fallback to direct call if API is unavailable
            print("🔄 Falling back to direct instruction manager call")
            if hasattr(self, 'instruction_manager') and self.instruction_manager:
                self.instruction_manager.execute_instruction(instruction)

    def get_response(self, conversation_history: str):
        """
        Gets a structured response from the OpenAI Chat Completions API based on the conversation and image context.
        """
        print(f"Received conversation for backend processing:\n{conversation_history}")
        
        # Debug: Check for user action requests (for monitoring only)
        action_keywords = [
            "create", "make", "spawn", "generate", "build", "do", "want", "add", "place", "put",
            "cylinder", "sphere", "cube", "cone", "mesh", "bean", "sculpture", "object"
        ]
        
        request_found = any(keyword.lower() in conversation_history.lower() for keyword in action_keywords)
        print(f"🔍 User action request detected: {request_found}")
        
        if request_found:
            matching_keywords = [k for k in action_keywords if k.lower() in conversation_history.lower()]
            print(f"🎯 Matching keywords: {matching_keywords}")
        else:
            print("💬 No obvious action keywords found (but OpenAI may still detect intent)")

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
                            "The user has made a request in CONJURE. Based on this request and the attached image "
                            "of the current 3D model, determine what action to take.\n\n"
                            "ANALYZE THE USER REQUEST:\n"
                            "- If user wants to create/spawn a primitive (cylinder, sphere, cube, etc.), use spawn_primitive\n"
                            "- If user mentions generating or creating a mesh, use generate_flux_mesh\n"
                            "- If user wants to select parts or segments, use segment_selection\n"
                            "- If user is just asking questions or chatting, set instruction to null\n\n"
                            "EXAMPLES:\n"
                            "- 'I want to create a cylinder' → spawn_primitive with primitive_type: 'cylinder'\n"
                            "- 'Let's make a sphere' → spawn_primitive with primitive_type: 'sphere'\n"
                            "- 'Generate a mesh' → generate_flux_mesh\n"
                            "- 'How are you?' → instruction: null\n\n"
                            f"--- USER REQUEST ---\n{conversation_history}"
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
            # 3. Call the Chat Completions API with structured output (equivalent to Code Interpreter)
            response = self.client.chat.completions.create(
                model=CUSTOM_GPT_MODEL,
                messages=messages,  # type: ignore
                max_tokens=1500,  # Increased for more detailed FLUX.1 prompts
                temperature=0.3,   # Lower temperature for more consistent JSON structure
                response_format={"type": "json_object"}  # Enhanced JSON mode with intelligent structure
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

            # Execute instruction (new correct structure)
            instruction = response_json.get("instruction")
            
            if instruction and isinstance(instruction, dict):
                tool_name = instruction.get("tool_name")
                parameters = instruction.get("parameters", {})
                
                if tool_name:
                    print(f"🔧 Executing tool: {tool_name}")
                    self._execute_instruction_via_api(instruction)
                    return instruction
                else:
                    print("⚠️ Error: instruction object missing tool_name")
                    return None
            else:
                print("⚠️ Error: Missing or invalid instruction object in response")
                return None

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