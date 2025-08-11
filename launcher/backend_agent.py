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
from launcher.instruction_manager import InstructionManager

# Custom ChatGPT ID from the provided URL: https://chatgpt.com/g/g-68742df47c3881918fc61172bf53d4b4-vibe-backend
CUSTOM_GPT_MODEL = "gpt-5-mini"  # Use GPT-5-mini for fast and reliable responses

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
1. listen for commands from the conversation between the user and the conversational agent and execute them.
2. Create detailed FLUX.1-optimized prompts for AI image/model generation.
WHEN TO EXECUTE COMMANDS:
You should be AGGRESSIVE about executing commands. Execute when ANY of these conditions are met:
1. The conversational agent suggests creating/spawning something AND user responds positively
2. The conversational agent asks about creating something AND user shows ANY interest
3. The user mentions wanting to create, make, spawn, generate, or build something
4. The user agrees, says yes, or shows positive intent toward any modeling action
5. The user asks for help with 3D modeling tasks

EXAMPLES OF WHEN TO EXECUTE:
- Agent: "Would you like me to create a cube?" User: "Yes" → EXECUTE spawn_primitive with primitive_type: "Cube"
- Agent: "I can spawn a cube" User: "Ok" → EXECUTE spawn_primitive with primitive_type: "Cube"  
- Agent: "Would you like me to create a sphere?" User: "Sure" → EXECUTE spawn_primitive with primitive_type: "Sphere"
- Agent: "I'll place a cube" User: "Go ahead" → EXECUTE spawn_primitive with primitive_type: "Cube"
- Agent: "Should I generate a mesh?" User: "Do it" → EXECUTE generate_flux_mesh
- User mentions: "cube", "sphere", "create", "make", "spawn" → EXECUTE appropriate command
- Agent suggests any action + User responds with: "yes", "ok", "sure", "do it", "go ahead", "please", "create it" → EXECUTE

WHEN NOT TO EXECUTE (return null instruction):
- User gives unclear/confused responses: "what?", "huh?", "what's up?", "I don't understand"
- User asks questions about the system itself: "how does this work?", "what can you do?"
- User makes random conversation: "hello", "how are you?", "what's happening?"
- Agent is explaining something and user just acknowledges: "ok", "got it", "I see"

BE RESPONSIVE: If there's any doubt about creation intent, EXECUTE the command rather than returning null.

You follow the strict order: SPAWN_PRIMITIVE, GENERATE_FLUX_MESH, FUSE_MESH, SEGMENT_SELECTION, SELECT_CONCEPT.


AGENT OUTPUT STRUCTURE
Your response for every turn MUST be a JSON object with this exact structure. Never include any kind of conversational text beyond the raw JSON format:

You **always** respond with a single, complete JSON object:

```json
{
  "instruction": {
    "tool_name": "The backend function to trigger.",
    "parameters": {
      "param1": "value1",
      "param2": "value2"
    }
  },
  "user_prompt": "A Flux/SDXL-ready prompt derived from the user's conversation."
}
```
 
- `instruction` → Triggers a backend tool. If no action is needed, return `null`.
- `user_prompt` → A long-form visual prompt (between 60–75 words) for generating images/models. ONLY create visual prompts when there's clear creative intent in the conversation. If instruction is null or user is confused/asking questions, create a simple placeholder prompt like "neutral studio background with soft lighting". 

**CONTEXT BUILDING**: If you receive a "PREVIOUS CONTEXT" with a previous user_prompt, BUILD UPON IT coherently. Don't start from scratch - evolve, refine, or add details to the existing prompt. This maintains visual consistency across conversation turns.

To make a good user prompt when appropriate, follow these steps:

Be specific and detailed. Describe the subject, style, composition, lighting, and mood. The more precise you are, the better the results. Break down the scene into layers like foreground, middle ground, and background. Describe each part in order for clear guidance. Use artistic references. Mention specific artists or art movements to guide the model's output. Include technical details if needed, like camera settings, lens type, or aperture. Describe the mood or atmosphere of the image to influence the tone. Avoid chaotic or disorganized prompts. Break the description into clear, logical elements like subject, text, tone, and style. Always use a neutral studio background with soft studio lighting, professional photography standards, and high-definition quality. Avoid abstract language and focus on precise descriptions, emphasizing details like form, shape, and texture. Refer to only one element in the scene at a time. Keep the description simple by avoiding complex scenes with multiple objects.

By following these steps, you can create effective FLUX.1 prompts for high-quality and creative images.

If no backend action is required, set `"instruction"` to `null`.
Never return anything without this structure, as it will catastrophically crash the system.
Always return a valid JSON object with the correct structure.
Always stick to the structure, and do not add any other text or comments.

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
Then the cycle goes back to generate_flux_mesh, either select_concept or generate_flux_mesh again. The cycle repeats until the user is satisfied with the result.

"""

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
        tool_name = instruction.get("tool_name", "unknown")
        print(f"🚀 Attempting to execute {tool_name} via API...")
        
        try:
            with httpx.Client() as client:
                response = client.post(
                    "http://127.0.0.1:8000/execute_instruction",
                    json={"instruction": instruction},
                    timeout=1.0  # Reduced from 30s to 3s for faster fallback
                )
                if response.status_code == 200:
                    print(f"✅ Successfully executed {tool_name} via API")
                    return True
                else:
                    print(f"❌ Instruction API error: {response.status_code} - {response.text}")
                    raise Exception(f"API returned status {response.status_code}")
        except Exception as e:
            print(f"❌ Error calling instruction API: {e}")
            # Fallback to direct call if API is unavailable
            print(f"🔄 Falling back to direct instruction manager call for {tool_name}")
            print(f"🔍 Instruction manager available: {hasattr(self, 'instruction_manager')}")
            print(f"🔍 Instruction manager not None: {getattr(self, 'instruction_manager', None) is not None}")
            
            if hasattr(self, 'instruction_manager') and self.instruction_manager:
                print(f"🎯 Calling instruction_manager.execute_instruction for {tool_name}")
                try:
                    self.instruction_manager.execute_instruction(instruction)
                    print(f"✅ Direct execution of {tool_name} completed")
                    return True
                except Exception as fallback_error:
                    print(f"❌ Fallback execution failed: {fallback_error}")
                    return False
            else:
                print(f"❌ No instruction manager available for fallback!")
                return False

    def _read_previous_user_prompt(self):
        """Read the previous user_prompt from userPrompt.txt for context"""
        try:
            user_prompt_path = Path("data/generated_text/userPrompt.txt")
            if user_prompt_path.exists():
                with open(user_prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    return content if content else None
            return None
        except Exception as e:
            print(f"❌ Error reading previous user prompt: {e}")
            return None

    def get_response(self, conversation_history: str):
        """
        Gets a structured response from the OpenAI Chat Completions API based on the conversation and image context.
        """
        print(f"Received conversation for backend processing:\n{conversation_history}")
        
        # Read previous user_prompt as context
        previous_prompt = self._read_previous_user_prompt()
        if previous_prompt:
            print(f"📝 Previous context: {previous_prompt[:100]}...")
        else:
            print("📝 No previous context found")
        
        # Simple single-turn processing - fast and efficient
        print(f"🧠 Sending single turn to {CUSTOM_GPT_MODEL} for intelligent processing")

        # 1. IMAGE PROCESSING DISABLED - Text-only mode for better reliability
        image_base64 = None
        print("🚫 Image processing disabled - using text-only mode")

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
                            "The user has made a request in CONJURE. Based on this conversation, determine what action to take.\n\n"
                                            "ANALYZE THE CONVERSATION:\n"
                "BE AGGRESSIVE about executing commands! Look for ANY indication the user wants to create something.\n"
                "- Agent mentions creating/spawning + User shows ANY positive response → EXECUTE\n"
                "- User mentions any 3D modeling words → EXECUTE appropriate command\n"
                "- User agrees to anything related to modeling → EXECUTE\n"
                "- When in doubt, EXECUTE rather than returning null\n\n"
                "EXAMPLES:\n"
                "Agent: 'Would you like me to create a cube?' User: 'Yes' → spawn_primitive with primitive_type: 'Cube'\n"
                "Agent: 'I can spawn a cube' User: 'Ok' → spawn_primitive with primitive_type: 'Cube'\n"
                "Agent: 'I'll place a cube now' User: 'Sure' → spawn_primitive with primitive_type: 'Cube'\n"
                "Agent: 'Should I create a sphere?' User: 'Do it' → spawn_primitive with primitive_type: 'Sphere'\n"
                "Agent: 'Generate a mesh?' User: 'Go ahead' → generate_flux_mesh\n"
                "User: 'Create a cube' → spawn_primitive with primitive_type: 'Cube'\n"
                "User: 'Make something' → spawn_primitive with primitive_type: 'Cube'\n\n"
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
            # Text-only message with context
            user_content = (
                "Here is the latest conversation turn between the user and the conversational AI. "
                "The format is: Agent asks/suggests → User responds. "
                "Based on this conversation, please provide the next action as a structured JSON response.\n\n"
            )
            
            # Add previous user_prompt as context if available
            if previous_prompt:
                user_content += (
                    f"--- PREVIOUS CONTEXT ---\n"
                    f"Previous user_prompt: {previous_prompt}\n"
                    f"NOTE: This is the context from the previous turn. Build upon this coherently for any new user_prompt. "
                    f"If generating a new creative prompt, evolve or refine the previous context rather than starting fresh.\n\n"
                )
            
            user_content += f"--- CONVERSATION ---\n{conversation_history}"
            
            messages.append({  # type: ignore
                "role": "user",
                "content": user_content
            })

        try:
            # 3. Call the Chat Completions API with structured output (equivalent to Code Interpreter)
            response = self.client.chat.completions.create(
                model=CUSTOM_GPT_MODEL,
                messages=messages,  # type: ignore
                max_completion_tokens=1500,  # GPT-5-mini uses max_completion_tokens instead of max_tokens
                # temperature=0.3,   # GPT-5-mini only supports default temperature of 1
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
            
            # Vision processing disabled - skip vision summary writing

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