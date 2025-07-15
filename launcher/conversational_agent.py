"""
ElevenLabs API integration for the primary conversational agent (Agent A).
Handles real-time voice interaction with the user and coordinates with the BackendAgent.
"""
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from backend_agent import BackendAgent

# TODO: Get Agent ID from a config file or environment variable
ELEVENLABS_AGENT_ID = "agent_01k02wep6vev8rzsz6pww831s3"

class ConversationalAgent:
    def __init__(self, backend_agent: BackendAgent):
        self.backend_agent = backend_agent
        self.elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.conversation = self._setup_conversation()
        self.full_transcript = []

    def _setup_conversation(self):
        return Conversation(
            client=self.elevenlabs_client,
            agent_id=ELEVENLABS_AGENT_ID,
            requires_auth=bool(os.getenv("ELEVENLABS_API_KEY")),
            audio_interface=DefaultAudioInterface(),
            callback_user_transcript=self._on_user_transcript,
            callback_agent_response=self._on_agent_response,
        )

    def _on_user_transcript(self, transcript: str):
        """Callback for when the user has finished speaking."""
        print(f"USER: {transcript}")
        self.full_transcript.append(f"User: {transcript}")

    def _on_agent_response(self, response: str):
        """Callback for when the agent has generated a response."""
        print(f"AGENT A: {response}")
        self.full_transcript.append(f"Agent A: {response}")
        
        # Now that a full turn has completed, trigger Agent B
        conversation_turn = "\n".join(self.full_transcript)
        print("--- Sending to Backend Agent ---")
        self.backend_agent.get_response(conversation_turn)
        
        # Clear the transcript for the next turn
        self.full_transcript = []

    def start(self):
        """Starts the conversational session."""
        print("Starting conversational agent session. Press Ctrl+C to exit.")
        self.conversation.start_session()

    def stop(self):
        """Stops the conversational session."""
        print("Stopping conversational agent session.")
        self.conversation.end_session() 