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
        

        
        # PHASE 1 SIMPLIFICATION: Streamlined system prompt for pure FLUX prompt processing
        self.system_prompt = """You are a FLUX prompt specialist for the CONJURE 3D modeling system. Your ONLY job is to analyze user voice input and current 3D model state, then output a structured JSON prompt optimized for high-quality 3D mesh generation.

CORE ROLE:
You receive three inputs:
1. User speech transcript (what they just said)
2. Current prompt state (userPrompt.txt content)
3. Visual context (gestureRender.png - current 3D model view)

Your output must be ONLY a JSON structure with this exact format:

{
  "subject": {
    "name": "string",                 // e.g., "stackable chair", "wireless headset"
    "form_keywords": ["string"],      // shape descriptors: "curved shell", "mono-block", "faceted"
    "material_keywords": ["string"],  // CMF: "brushed aluminum", "matte ABS", "polished steel"
    "color_keywords": ["string"]      // palette: "graphite gray", "satin sand", "electric blue"
  }
}

PROCESSING RULES:
1. **MAINTAIN CONTINUITY**: Always build upon the existing prompt state - don't completely replace unless user explicitly requests
2. **INCORPORATE NEW INPUT**: Seamlessly integrate new speech input into the existing description
3. **PRODUCT DESIGN FOCUS**: Use professional product design and industrial design terminology
4. **3D MESH OPTIMIZATION**: Prioritize descriptions that will generate clean, manufacturable 3D geometry
5. **NO CONVERSATION**: Never ask questions, never respond conversationally - output JSON only

TRANSCRIPTION ERROR HANDLING:
- Infer meaning from garbled speech (e.g., "qube" = "cube", "spear" = "sphere")
- Use visual context to understand unclear audio
- Default to subtle refinements if speech is unintelligible

EXAMPLES:

User says: "make it more curved"
Current: {"name": "chair", "form_keywords": ["angular"], ...}
Output: {"subject": {"name": "chair", "form_keywords": ["curved", "flowing"], ...}}

User says: "I want a blue metallic finish"
Current: {"name": "device", "material_keywords": ["plastic"], "color_keywords": ["gray"]}
Output: {"subject": {"name": "device", "material_keywords": ["brushed metal", "aluminum"], "color_keywords": ["electric blue", "metallic"]}}

REMEMBER: Output ONLY the JSON structure. No explanations, no conversation, no questions.


OUTPUT FORMAT:
You must respond with ONLY the JSON structure - no explanations, no conversation, no additional text.

Example output:
{
  "subject": {
    "name": "ergonomic office chair",
    "form_keywords": ["curved", "streamlined", "ergonomic"],
    "material_keywords": ["brushed aluminum", "mesh fabric"],
    "color_keywords": ["charcoal gray", "metallic accents"]
  }
}
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

    def process_voice_input(self, speech_transcript: str, current_prompt_state: str = None, gesture_render_path: str = None):
        """
        PHASE 1 SIMPLIFICATION: Process voice input to generate structured FLUX prompts.
        No conversation analysis, no tool execution - just prompt refinement.
        """
        print(f"🎤 Processing voice input: {speech_transcript}")
        
        # Load current prompt state if not provided
        if current_prompt_state is None:
            current_prompt_state = self._read_previous_user_prompt() or "No previous prompt"
        
        print(f"📝 Current prompt state: {current_prompt_state[:100] if current_prompt_state else 'None'}...")
        
        # Encode gesture render image if available
        image_base64 = None
        if gesture_render_path and Path(gesture_render_path).exists():
            image_base64 = self._encode_image_to_base64(gesture_render_path)
            print(f"📸 Gesture render loaded: {gesture_render_path}")
        else:
            print("🚫 No gesture render available - using text-only mode")

        # 2. Prepare the messages for Chat Completions
        messages = [
            {
                "role": "system", 
                "content": self.system_prompt
            }
        ]
        
        # Add user message for voice input processing
        if image_base64:
            # Message with both text and image
            messages.append({  # type: ignore
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"INPUTS:\n"
                            f"1. User speech transcript: '{speech_transcript}'\n"
                            f"2. Current prompt state: {current_prompt_state}\n"
                            f"3. Visual context: [Gesture render image attached]\n\n"
                            f"Please process this voice input and update the structured FLUX prompt accordingly. "
                            f"Maintain continuity with the existing prompt while incorporating the new speech input."
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
            # Text-only message for voice input processing
            user_content = (
                f"INPUTS:\n"
                f"1. User speech transcript: '{speech_transcript}'\n"
                f"2. Current prompt state: {current_prompt_state}\n"
                f"3. Visual context: No gesture render available\n\n"
                f"Please process this voice input and update the structured FLUX prompt accordingly. "
                f"Maintain continuity with the existing prompt while incorporating the new speech input."
            )
            
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
        """PHASE 1 SIMPLIFICATION: Parse structured FLUX prompt and save to userPrompt.txt"""
        print(f"🎨 FLUX PROMPT RESPONSE:\n{response_str}")
        try:
            # Parse the JSON response
            response_json = json.loads(response_str)
            
            # Validate the structured prompt format
            subject = response_json.get("subject")
            if not subject or not isinstance(subject, dict):
                print("⚠️ Error: Invalid response format - missing 'subject' object")
                return None
            
            # Extract components
            name = subject.get("name", "")
            form_keywords = subject.get("form_keywords", [])
            material_keywords = subject.get("material_keywords", [])
            color_keywords = subject.get("color_keywords", [])
            
            # Generate the full FLUX prompt from structured data
            form_desc = ", ".join(form_keywords) if form_keywords else ""
            material_desc = ", ".join(material_keywords) if material_keywords else ""
            color_desc = ", ".join(color_keywords) if color_keywords else ""
            
            # Build the professional product photography prompt
            flux_prompt = f"{name}"
            if form_desc:
                flux_prompt += f" with {form_desc} form"
            if material_desc:
                flux_prompt += f", {material_desc} materials"
            if color_desc:
                flux_prompt += f", {color_desc} colors"
            
            # Add the standard photography setup
            photography_setup = f"Shown in a three-quarter view and centered in frame, set against a clean studio background in neutral mid-gray. The {name} sits under soft studio lighting with a large key softbox at 45 degrees, gentle fill, and a subtle rim to control reflections. Shot on a 35mm lens at f/5.6, ISO 100—product-catalog clarity, no clutter or props, no text or people, avoid pure white backgrounds."
            
            full_prompt = f"{flux_prompt}. {photography_setup}"
            
            # Save to userPrompt.txt
            prompt_path = Path(__file__).parent.parent / "data" / "generated_text" / "userPrompt.txt"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(full_prompt)
            
            print(f"✅ Updated userPrompt.txt with structured FLUX prompt")
            print(f"📝 Generated prompt: {full_prompt[:100]}...")
            
            return response_json

        except json.JSONDecodeError as e:
            print(f"❌ Error: Could not decode JSON from agent response: {e}")
            print(f"Raw response: {response_str}")
            return None
        except Exception as e:
            print(f"❌ Error processing FLUX prompt response: {e}")
            return None 