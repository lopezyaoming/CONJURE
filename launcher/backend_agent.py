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
CUSTOM_GPT_MODEL = "gpt-5-mini"  # Use GPT-5-mini for fast and reliable responses

class BackendAgent:
    def __init__(self, instruction_manager: InstructionManager):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=api_key)
        self.instruction_manager = instruction_manager
        

        
        # CONJURE Backend Agent - Updated System Prompt for Structured Data Package
        self.system_prompt = """You are a FLUX prompt specialist for the CONJURE 3D modeling system. Your ONLY job is to analyze user voice input and current 3D model state, then output a structured JSON prompt optimized for high-quality 3D mesh generation.

CONTEXT FORMAT:
You will ALWAYS receive context in this exact format:

user_transcription: "last successful whisper transcription of what the user has said"
user_prompt: "complete userPrompt.txt string"

CORE ROLE:
Process the user's spoken input (user_transcription) and build upon the existing prompt state (user_prompt) to create an updated structured FLUX prompt.

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
1. **MAINTAIN CONTINUITY**: Always build upon the existing user_prompt - don't completely replace unless user explicitly requests
2. **INCORPORATE NEW INPUT**: Seamlessly integrate the user_transcription into the existing description
3. **PRODUCT DESIGN FOCUS**: Use professional product design and industrial design terminology
4. **3D MESH OPTIMIZATION**: Prioritize descriptions that will generate clean, manufacturable 3D geometry
5. **NO CONVERSATION**: Never ask questions, never respond conversationally - output JSON only

TRANSCRIPTION ERROR HANDLING:
- Infer meaning from garbled speech (e.g., "qube" = "cube", "spear" = "sphere")
- Use context from existing user_prompt to understand unclear audio
- Default to subtle refinements if speech is unintelligible

EXAMPLES:

Input:
user_transcription: "make it more curved"
user_prompt: "Angular office chair with plastic frame, gray color"
Output: {"subject": {"name": "office chair", "form_keywords": ["curved", "flowing"], "material_keywords": ["plastic"], "color_keywords": ["gray"]}}

Input:
user_transcription: "I want a blue metallic finish"
user_prompt: "Device with plastic materials, gray color"
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
        UPDATED: Process voice input using standardized data package format.
        Uses DataPackageBuilder to create properly labeled data for ChatGPT.
        """
        print(f"🎤 Processing voice input with new data package format: {speech_transcript}")
        
        # Import data package builder
        from data_package_builder import DataPackageBuilder
        
        # Create data package builder
        package_builder = DataPackageBuilder()
        
        # Build the standardized package with new transcript
        formatted_message = package_builder.format_for_chatgpt_api(speech_transcript)
        
        print(f"📦 Formatted message for ChatGPT:")
        print(formatted_message)

        # Prepare the messages for Chat Completions API
        messages = [
            {
                "role": "system", 
                "content": self.system_prompt
            },
            {
                "role": "user",
                "content": formatted_message
            }
        ]
        
        # Call OpenAI API
        try:
            print(f"🚀 Sending request to OpenAI...")
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=1000,
                temperature=0.3
            )
            
            response_content = response.choices[0].message.content
            print(f"✅ Received response from OpenAI: {response_content[:200]}...")
            
            # Parse and process the response
            result = self._parse_and_process_response(response_content)
            return result
            
        except Exception as e:
            print(f"❌ Error calling OpenAI API: {e}")
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
            
            # Generate the full FLUX prompt from structured data with 50-word limit
            # Combine all descriptors into a single list for word counting
            all_descriptors = []
            if form_keywords:
                all_descriptors.extend(form_keywords)
            if material_keywords:
                all_descriptors.extend(material_keywords)
            if color_keywords:
                all_descriptors.extend(color_keywords)
            
            # Build descriptor text and limit to 50 words total
            descriptor_text = ", ".join(all_descriptors)
            descriptor_words = descriptor_text.split()
            
            # Cap at 50 words for the descriptors
            max_descriptor_words = 50
            if len(descriptor_words) > max_descriptor_words:
                descriptor_words = descriptor_words[:max_descriptor_words]
                descriptor_text = " ".join(descriptor_words)
                print(f"⚠️ Descriptors capped at {max_descriptor_words} words: {len(descriptor_words)} words used")
            else:
                print(f"✅ Descriptors within limit: {len(descriptor_words)}/{max_descriptor_words} words")
            
            # Build the concise product description
            if descriptor_text:
                flux_prompt = f"{name} with {descriptor_text}"
            else:
                flux_prompt = name

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