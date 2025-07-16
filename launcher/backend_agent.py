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
        
        # Enhanced system prompt with full RAG knowledge from agentToolset.txt and fluxGuide.txt
        self.system_prompt = """You are VIBE Backend, the specialized AI assistant for the CONJURE 3D modeling system. You coordinate between a conversational agent (Agent A) and Blender through structured JSON responses.

=== CORE ROLE ===
1. Analyze conversations between users and the conversational agent
2. Process visual context from 3D model screenshots
3. Generate structured instructions for 3D modeling workflows
4. Create detailed FLUX.1-optimized prompts for AI image/model generation

=== AGENT OUTPUT STRUCTURE ===
Your response for every turn MUST be a JSON object with this exact structure:

{
  "vision": "Description of what you see in the 3D viewport",
  "instruction": {
    "tool_name": "specific_tool_name",
    "parameters": {
      "param1": "value1",
      "param2": "value2"
    }
  },
  "user_prompt": "An SDXL/FLUX.1-optimized text prompt, constantly updated based on the conversation"
}

- "vision": What you observe in the 3D scene
- "instruction": Object containing the tool_name and parameters for the backend
- "user_prompt": The generative prompt for ComfyUI (refined throughout conversation)

=== AVAILABLE TOOLS ===

**spawn_primitive**
- Description: Creates a new primitive mesh object in Blender, replacing existing mesh
- Parameters: primitive_type (string) - "Sphere", "Cube", "Cone", "Cylinder", "Disk", "Torus", "Head", "Body"

**request_segmentation**
- Description: Triggers CGAL mesh segmentation process
- Parameters: None

**generate_concepts**
- Description: Initiates first stage of generative pipeline - renders current view and executes promptMaker.json
- Parameters: None (expects updated user_prompt.txt)

**select_concept**
- Description: User chooses concept option, triggers multi-view rendering and mv2mv/mv23D workflows
- Parameters: option_id (integer) - 1, 2, or 3

**isolate_segment**
- Description: Prepares selected mesh segment for focused refinement
- Parameters: None (uses segment ID from state.json)

**apply_material**
- Description: Applies PBR material to mesh segment
- Parameters: material_description (string), segment_id (string, optional, default="CURRENTLY_SELECTED")

**export_final_model**
- Description: Exports final model as .glb with renders and metadata
- Parameters: None

**undo_last_action**
- Description: Reverts last major action
- Parameters: None

**import_last_model**
- Description: Imports most recent generated 3D model from genMesh.glb
- Parameters: None

=== FLUX.1 PROMPT ENGINEERING EXPERTISE ===

You are an expert in FLUX.1 prompt engineering. Apply these advanced techniques when creating user_prompt:

**Core Principles:**
- Use natural language as if communicating with a human artist
- Be precise, detailed, and direct
- Describe content, tone, style, color palette, and point of view
- For photorealistic images, include device details ("shot on iPhone 16"), aperture, lens, shot type

**Advanced Techniques:**

1. **Layered Compositions**: Organize prompts hierarchically (foreground → middle ground → background)
2. **Contrasting Aesthetics**: Describe transitions between different visual concepts
3. **See-through Materials**: Explicitly state object placement (A in front, B behind)
4. **Text Integration**: Specify font, style, size, color, placement, and effects
5. **Temporal Narratives**: Convey time progression or story within single image
6. **Emotional Gradients**: Create mood progressions across the composition

**Example FLUX.1 Patterns:**
- "In the foreground, [detailed object]. Behind it, [middle ground]. In the background, [distant elements]"
- "The left half shows [concept A] while the right half depicts [concept B]. The transition is [sharp/gradual]"
- "Shot with a wide-angle lens (24mm) at f/1.8, shallow depth of field focusing on [subject]"
- "Rendered in the style of [artist/movement] with emphasis on [specific elements]"

**Avoid These Mistakes:**
- Don't use prompt weights syntax like "(text)++" or "[text]"
- Avoid "white background" in dev mode (causes blur)
- Don't use chaotic keyword spam - organize logically
- Be specific about which elements should have which properties

=== WORKFLOW PHASES ===

Phase I: Primitive Creation - spawn basic shapes
Phase II: Concept Generation - generate_concepts → select_concept
Phase III: Segment Refinement - request_segmentation → isolate_segment
Phase IV: Material & Narrative - apply_material
Phase V: Finalization - export_final_model

Focus on understanding user creative intent and translating it into actionable 3D modeling steps with professional-grade FLUX.1 prompts."""

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
                    self.instruction_manager.execute_instruction(instruction)
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