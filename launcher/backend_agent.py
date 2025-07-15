"""
Backend Agent (Agent B)
Handles interaction with the OpenAI Assistant API to get structured instructions.
"""
import os
import json
import time
from openai import OpenAI
from pathlib import Path
from instruction_manager import InstructionManager

# TODO: Get Assistant ID from a config file or environment variable
OPENAI_ASSISTANT_ID = "asst_..." # Replace with your actual assistant ID from the user's link.

class BackendAgent:
    def __init__(self, instruction_manager: InstructionManager):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=api_key)
        self.instruction_manager = instruction_manager
        self.assistant_id = OPENAI_ASSISTANT_ID # Load the assistant ID

    def _upload_context_image(self):
        """Uploads the latest gesture camera render to OpenAI files."""
        try:
            image_path = Path(__file__).parent.parent / "data" / "generated_images" / "gestureCamera" / "render.png"
            if not image_path.exists():
                print("Warning: gestureCamera/render.png not found. Proceeding without image context.")
                return None
            
            with image_path.open("rb") as image_file:
                response = self.client.files.create(file=image_file, purpose='vision')
                print(f"Uploaded context image. File ID: {response.id}")
                return response.id
        except Exception as e:
            print(f"Error uploading context image: {e}")
            return None

    def get_response(self, conversation_history: str):
        """
        Gets a structured response from the OpenAI Assistant based on the conversation and image context.
        """
        print(f"Received conversation for backend processing:\n{conversation_history}")

        # 1. Upload the latest context image from Blender
        image_file_id = self._upload_context_image()

        # 2. Create a message with conversation history and image
        message_parts = [
            {
                "type": "text",
                "text": (
                    "Here is the latest conversation turn between the user and the conversational AI. "
                    "Based on this, and the attached image of the current 3D model, "
                    "please provide the next action as a structured JSON response.\n\n"
                    f"--- CONVERSATION ---\n{conversation_history}"
                )
            }
        ]
        if image_file_id:
            message_parts.append({ # type: ignore
                "type": "image_file",
                "image_file": {"file_id": image_file_id}
            })

        try:
            # 3. Create a thread and run the assistant
            thread = self.client.beta.threads.create()
            
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message_parts # type: ignore
            )
            
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            print(f"Created run {run.id} for thread {thread.id}. Waiting for completion...")

            # 4. Poll for the result
            while run.status in ['queued', 'in_progress', 'cancelling']:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

            if run.status == 'completed':
                messages = self.client.beta.threads.messages.list(thread_id=thread.id, limit=1)
                # The latest message is the first in the list
                latest_message = messages.data[0]
                agent_response_str = ""
                for content_block in latest_message.content:
                    if content_block.type == "text":
                        agent_response_str = content_block.text.value
                        break
                
                if not agent_response_str:
                    print("Error: Assistant response did not contain text.")
                    return None

                return self._parse_and_process_response(agent_response_str)
            else:
                print(f"Error: Run ended with status: {run.status}")
                return None

        except Exception as e:
            print(f"Error interacting with Assistant API: {e}")
            return None
        finally:
            # Clean up the uploaded file
            if image_file_id:
                try:
                    self.client.files.delete(image_file_id)
                    print(f"Deleted context image file {image_file_id}.")
                except Exception as e:
                    print(f"Error deleting context image file: {e}")


    def _parse_and_process_response(self, response_str: str):
        """Parses the JSON response from the agent and acts on it."""
        print(f"AGENT B RESPONSE:\n{response_str}")
        try:
            # The agent might return the JSON inside a code block
            if "```json" in response_str:
                response_str = response_str.split("```json\n")[1].split("\n```")[0]

            response_json = json.loads(response_str)
            
            # Write vision summary
            vision_summary = response_json.get("vision")
            if vision_summary:
                 # This path seems wrong, but following the prompt.
                 # Should probably be in data/generated_text
                vision_path = Path(__file__).parent.parent / "screen_description.txt"
                with open(vision_path, 'w', encoding='utf-8') as f:
                    f.write(vision_summary)
                print(f"Wrote vision summary to {vision_path}.")

            # Write user prompt
            user_prompt = response_json.get("user_prompt")
            if user_prompt:
                prompt_path = Path(__file__).parent.parent / "data" / "generated_text" / "userPrompt.txt"
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(user_prompt)
                print("Updated userPrompt.txt.")

            # Execute instruction
            instruction = response_json.get("instruction")
            tool_name = response_json.get("tool_name")
            parameters = response_json.get("parameters")

            if instruction and tool_name: # instruction field might be legacy, tool_name is key
                # Construct the instruction object for the manager
                full_instruction = {
                    "tool_name": tool_name,
                    "parameters": parameters or {}
                }
                self.instruction_manager.execute_instruction(full_instruction)
                return full_instruction
            elif instruction: # Handle legacy format from agentToolset.txt just in case
                print("Received legacy instruction format.")
                self.instruction_manager.execute_instruction(instruction)
                return instruction

            return None

        except (json.JSONDecodeError, IndexError):
            print(f"Error: Could not decode or parse JSON from agent response: {response_str}")
            return None
        except KeyError as e:
            print(f"Error: Response JSON missing expected key: {e}")
            return None 