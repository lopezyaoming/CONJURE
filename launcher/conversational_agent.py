"""
ElevenLabs API integration for the primary conversational agent (Agent A).
Handles real-time voice interaction with the user and coordinates with the BackendAgent.
Now includes real-time audio capture and OpenAI Whisper transcription.
"""
import os
import time
import threading
import requests
import json
import websocket
import pyaudio
import wave
import io
import tempfile
import base64
import httpx
from collections import deque
from typing import Optional
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from backend_agent import BackendAgent
from openai import OpenAI

# TODO: Get Agent ID from a config file or environment variable
ELEVENLABS_AGENT_ID = "agent_01k02wep6vev8rzsz6pww831s3"

# Audio capture settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
SILENCE_THRESHOLD = 1000  # Adjust based on your environment
SILENCE_DURATION = 2.0  # Seconds of silence before processing

# Audio device settings
INPUT_DEVICE = None  # Default microphone
OUTPUT_DEVICE = None  # Default speakers (for system audio capture)

class ConversationalAgent:
    def __init__(self, backend_agent: Optional[BackendAgent] = None):
        self.backend_agent = backend_agent
        
        # ElevenLabs setup
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            print("\n--- FATAL ERROR ---")
            print("The ELEVENLABS_API_KEY environment variable is not set.")
            print("Please set the API key and restart the application.")
            print("-------------------\n")
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables.")
        self.api_key = api_key
        self.elevenlabs_client = ElevenLabs(api_key=api_key)
        
        # OpenAI setup for Whisper
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("\n--- WARNING ---")
            print("The OPENAI_API_KEY environment variable is not set.")
            print("Audio transcription will not work without it.")
            print("---------------\n")
            self.openai_client = None
        else:
            self.openai_client = OpenAI(api_key=openai_api_key)
        
        # Audio capture setup
        self.audio = pyaudio.PyAudio()
        self._running = False
        self._audio_thread = None
        self._transcription_thread = None
        self._audio_queue = deque(maxlen=100)  # Store audio chunks
        self._last_speech_time = 0
        
        # Audio streams for input (microphone) and output (system audio)
        self._input_stream = None
        self._output_stream = None
        self._system_audio_thread = None
        
        self.conversation = self._setup_conversation()
        self.full_transcript = []
        self._logged_conv_id = False
        
        # Initialize debug file
        with open("transcript_debug.txt", "w") as f:
            f.write("=== CONJURE TRANSCRIPT DEBUG LOG WITH WHISPER ===\n")

    def _setup_conversation(self):
        print("--- SETTING UP CONVERSATION WITH CALLBACKS ---")
        conversation = Conversation(
            client=self.elevenlabs_client,
            agent_id=ELEVENLABS_AGENT_ID,
            requires_auth=bool(os.getenv("ELEVENLABS_API_KEY")),
            audio_interface=DefaultAudioInterface(),
            callback_user_transcript=self._on_user_transcript,
            callback_agent_response=self._on_agent_response,
        )
        print(f"--- CONVERSATION OBJECT CREATED: {type(conversation)} ---")
        
        # Hook into the internal message handler to capture agent responses
        original_handle_message = conversation._handle_message
        
        def hooked_handle_message(message, ws):
            try:
                message_type = message.get('type', 'unknown')
                
                # Look for agent audio responses to transcribe
                if message_type == 'audio':
                    audio_event = message.get('audio_event', {})
                    audio_base64 = audio_event.get('audio_base_64', '')
                    
                    if audio_base64 and len(audio_base64) > 1000:  # Significant audio data
                        print(f"🔊 Agent audio received ({len(audio_base64)} chars) - transcribing...")
                        
                        # Process agent audio in background thread
                        agent_audio_thread = threading.Thread(
                            target=self._transcribe_agent_audio,
                            args=(audio_base64,),
                            daemon=True
                        )
                        agent_audio_thread.start()
                
                # Look for ANY message that might contain agent text (backup)
                elif message_type == 'agent_response':
                    print("🎯 FOUND AGENT_RESPONSE MESSAGE:")
                    agent_event = message.get('agent_response_event', {})
                    agent_text = agent_event.get('agent_response', '')
                    if agent_text:
                        print(f"🤖 AGENT TRANSCRIPT: {agent_text}")
                        print("🤖 Sending agent response to Backend Agent...")
                        try:
                            self._send_to_backend_api(f"Agent said: {agent_text}")
                        except Exception as e:
                            print(f"Error sending agent response to backend: {e}")
                
                elif message_type == 'user_transcript':
                    print("🎯 FOUND USER_TRANSCRIPT MESSAGE:")
                    user_event = message.get('user_transcription_event', {})
                    user_text = user_event.get('user_transcript', '')
                    if user_text:
                        print(f"📝 USER TRANSCRIPT (from SDK): {user_text}")
                        print("🤖 Sending SDK user transcript to Backend Agent...")
                        try:
                            self._send_to_backend_api(user_text)
                        except Exception as e:
                            print(f"Error sending user transcript to backend: {e}")
                
                # Check ALL messages for any text/response content
                message_str = str(message)
                if any(keyword in message_str.lower() for keyword in ['response', 'transcript', 'text', 'message', 'reply']):
                    # Don't log if it's just audio data
                    if 'audio_base_64' not in message_str and len(message_str) < 2000:
                        print(f"🔍 POTENTIAL TRANSCRIPT MESSAGE ({message_type}):")
                        print(f"Content: {message}")
                        
                        # Try to extract any text content
                        def extract_text_from_message(msg):
                            if isinstance(msg, dict):
                                for key, value in msg.items():
                                    if isinstance(value, str) and len(value) > 5 and 'base64' not in value.lower():
                                        if any(word in value.lower() for word in ['hello', 'hi', 'can', 'help', 'yes', 'no', 'the', 'and', 'is', 'are']):
                                            return value
                                    elif isinstance(value, dict):
                                        result = extract_text_from_message(value)
                                        if result:
                                            return result
                            return None
                        
                        extracted_text = extract_text_from_message(message)
                        if extracted_text:
                            print(f"🎯 EXTRACTED TEXT: {extracted_text}")
                            if len(extracted_text) > 10:
                                print("🤖 Sending extracted agent text to Backend Agent...")
                                try:
                                    self._send_to_backend_api(f"Agent said: {extracted_text}")
                                except Exception as e:
                                    print(f"Error sending extracted text to backend: {e}")
                
            except Exception as e:
                print(f"Error in message handler: {e}")
            
            # Always call the original handler
            try:
                return original_handle_message(message, ws)
            except Exception as e:
                print(f"Error in original message handler: {e}")
                return None
        
        # Replace the message handler with our hooked version
        conversation._handle_message = hooked_handle_message
        print("--- MESSAGE HANDLER HOOKED FOR AGENT RESPONSE CAPTURE ---")
        
        return conversation

    def _detect_silence(self, audio_data):
        """Detect if audio contains mostly silence."""
        # Convert audio data to amplitude levels
        import struct
        import math
        
        # Unpack audio data (16-bit integers)
        samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
        
        # Calculate RMS (Root Mean Square) for volume detection
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        
        return rms < SILENCE_THRESHOLD

    def _save_audio_to_file(self, audio_data):
        """Save audio data to a temporary WAV file for Whisper."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            with wave.open(temp_file.name, 'wb') as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(self.audio.get_sample_size(FORMAT))
                wav_file.setframerate(RATE)
                wav_file.writeframes(audio_data)
            return temp_file.name

    def _transcribe_audio(self, audio_file_path):
        """Transcribe audio using OpenAI Whisper."""
        if not self.openai_client:
            print("OpenAI client not available for transcription")
            return None
            
        try:
            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"  # You can make this configurable
                )
                return transcript.text
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
        finally:
            # Clean up temporary file
            try:
                os.unlink(audio_file_path)
            except:
                pass

    def _transcribe_agent_audio(self, audio_base64):
        """Transcribe agent audio from base64 data."""
        if not self.openai_client:
            print("Skipping agent audio transcription - OpenAI client not available")
            return
            
        try:
            # Decode base64 audio data
            audio_data = base64.b64decode(audio_base64)
            
            # ElevenLabs sends audio as raw PCM data, not MP3
            # We need to convert it to WAV format for Whisper
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # Create WAV header for PCM data
                # ElevenLabs typically uses 16-bit PCM at 22050 Hz
                import struct
                
                sample_rate = 22050  # ElevenLabs default
                bits_per_sample = 16
                channels = 1
                
                # Calculate sizes
                data_size = len(audio_data)
                file_size = 36 + data_size
                
                # Write WAV header
                temp_file.write(b'RIFF')
                temp_file.write(struct.pack('<I', file_size))
                temp_file.write(b'WAVE')
                temp_file.write(b'fmt ')
                temp_file.write(struct.pack('<I', 16))  # fmt chunk size
                temp_file.write(struct.pack('<H', 1))   # PCM format
                temp_file.write(struct.pack('<H', channels))
                temp_file.write(struct.pack('<I', sample_rate))
                temp_file.write(struct.pack('<I', sample_rate * channels * bits_per_sample // 8))
                temp_file.write(struct.pack('<H', channels * bits_per_sample // 8))
                temp_file.write(struct.pack('<H', bits_per_sample))
                temp_file.write(b'data')
                temp_file.write(struct.pack('<I', data_size))
                
                # Write audio data
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Transcribe with Whisper
            try:
                with open(temp_file_path, 'rb') as audio_file:
                    transcript = self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="en"
                    )
                
                agent_text = transcript.text.strip()
                if agent_text and len(agent_text) > 3:  # Filter out very short transcripts
                    print(f"🤖 AGENT TRANSCRIPT (Whisper): {agent_text}")
                    
                    # Send to backend agent
                    print("🤖 Sending agent transcript to Backend Agent...")
                    try:
                        self._send_to_backend_api(f"Agent said: {agent_text}")
                    except Exception as e:
                        print(f"Error sending agent transcript to backend: {e}")
                else:
                    print("⚠️ Agent audio transcription too short or empty")
                    
            except Exception as e:
                print(f"Error transcribing agent audio: {e}")
            
            # Clean up temp file
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
        except Exception as e:
            print(f"Error processing agent audio: {e}")

    def _audio_capture_thread(self):
        """Continuous audio capture thread."""
        if not self.openai_client:
            print("Skipping audio capture - OpenAI client not available")
            return
            
        try:
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            print("🎤 Audio capture started - listening for user speech...")
            
            audio_buffer = []
            is_speaking = False
            last_speech_time = 0
            
            while self._running:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    current_time = time.time()
                    
                    if not self._detect_silence(data):
                        # Sound detected
                        if not is_speaking:
                            print("🗣️ User started speaking...")
                            is_speaking = True
                        
                        audio_buffer.append(data)
                        last_speech_time = current_time
                    else:
                        # Silence detected
                        if is_speaking and (current_time - last_speech_time) > SILENCE_DURATION:
                            print("🔇 User finished speaking - processing audio...")
                            duration = len(audio_buffer) * CHUNK / RATE
                            print(f"🎵 Processing {duration:.1f}s of audio...")
                            
                            # Process the accumulated audio in a separate thread to avoid blocking
                            transcription_thread = threading.Thread(
                                target=self._process_audio_buffer, 
                                args=(audio_buffer.copy(),), 
                                daemon=True
                            )
                            transcription_thread.start()
                            
                            # Reset for next speech
                            audio_buffer.clear()
                            is_speaking = False
                            
                except Exception as e:
                    if self._running:  # Only log if we're still supposed to be running
                        print(f"Audio capture error: {e}")
                    break
                    
            stream.stop_stream()
            stream.close()
            print("🔇 Audio capture stopped")
            
        except Exception as e:
            print(f"Audio capture setup error: {e}")

    def _process_audio_buffer(self, audio_buffer):
        """Process accumulated audio buffer through Whisper."""
        if not audio_buffer:
            return
            
        # Combine all audio chunks
        audio_data = b''.join(audio_buffer)
        
        # Skip very short recordings
        duration = len(audio_data) / (RATE * 2)  # 2 bytes per sample
        if duration < 0.5:  # Less than half a second
            print("⏱️ Audio too short, skipping...")
            return
        
        print(f"🎵 Processing {duration:.1f}s of audio...")
        
        # Start transcription in a separate thread to avoid blocking
        if self._transcription_thread and self._transcription_thread.is_alive():
            print("⚠️ Previous transcription still running, skipping this one...")
            return
            
        self._transcription_thread = threading.Thread(
            target=self._transcribe_and_process,
            args=(audio_data,),
            daemon=True
        )
        self._transcription_thread.start()

    def _transcribe_and_process(self, audio_data):
        """Transcribe audio and send to backend agent."""
        try:
            # Save audio to temporary file
            audio_file = self._save_audio_to_file(audio_data)
            
            # Transcribe
            transcript = self._transcribe_audio(audio_file)
            
            if transcript and transcript.strip():
                print(f"📝 USER TRANSCRIPT: {transcript}")
                
                # Log to debug file
                with open("transcript_debug.txt", "a") as f:
                    f.write(f"USER (Whisper): {transcript}\n")
                
                # Send to backend agent immediately
                print("🤖 Sending transcript to Backend Agent...")
                self._send_to_backend_api(f"User said: {transcript}")
                
            else:
                print("🤷 No clear speech detected in audio")
                
        except Exception as e:
            print(f"Transcription processing error: {e}")

    def _send_to_backend_api(self, conversation_turn: str):
        """
        Send conversation to backend agent via API instead of direct call.
        """
        try:
            print(f"🚀 Sending to API: '{conversation_turn[:100]}...' (len: {len(conversation_turn)})")
            
            with httpx.Client() as client:
                payload = {
                    "conversation_history": conversation_turn,
                    "include_image": True
                }
                print(f"📤 API request payload keys: {list(payload.keys())}")
                
                response = client.post(
                    "http://127.0.0.1:8000/process_conversation",
                    json=payload,
                    timeout=30.0
                )
                
                print(f"📥 API response status: {response.status_code}")
                
                if response.status_code == 200:
                    print("✅ Successfully sent conversation to backend API")
                    response_data = response.json()
                    print(f"📊 API response data: {response_data}")
                else:
                    print(f"❌ Backend API error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error calling backend API: {e}")
            import traceback
            print(f"🔍 API call error traceback:\n{traceback.format_exc()}")
            
            # Fallback to direct call if API is unavailable
            print("🔄 Falling back to direct backend agent call")
            if hasattr(self, 'backend_agent') and self.backend_agent:
                self.backend_agent.get_response(conversation_turn)

    def _on_user_transcript(self, transcript):
        """Callback for user transcript - should be called by ElevenLabs SDK."""
        print(f"🎯 SDK CALLBACK: USER TRANSCRIPT RECEIVED")
        print(f"📝 USER TRANSCRIPT (via callback): {transcript}")
        
        if transcript and transcript.strip():
            print("🤖 Sending SDK callback user transcript to Backend Agent...")
            try:
                self._send_to_backend_api(transcript)
            except Exception as e:
                print(f"Error sending SDK user transcript to backend: {e}")

    def _on_agent_response(self, response):
        """Callback for agent response - should be called by ElevenLabs SDK."""
        print(f"🎯 SDK CALLBACK: AGENT RESPONSE RECEIVED")
        print(f"🤖 AGENT RESPONSE (via callback): {response}")
        
        if response and response.strip():
            print("🤖 Sending SDK callback agent response to Backend Agent...")
            try:
                self._send_to_backend_api(f"Agent said: {response}")
            except Exception as e:
                print(f"Error sending SDK agent response to backend: {e}")
        
        # Now that a full turn has completed, trigger Agent B
        conversation_turn = "\n".join(self.full_transcript)
        print("--- Sending to Backend Agent ---")
        print(conversation_turn)
        self._send_to_backend_api(conversation_turn)
        
        # Clear the transcript for the next turn
        self.full_transcript = []

    def _setup_websocket(self):
        """Set up WebSocket connection to monitor real-time events."""
        current_transcript = ""
        current_response = ""
        
        def on_message(ws, message):
            nonlocal current_transcript, current_response
            try:
                data = json.loads(message)
                message_type = data.get("type")
                
                # Log ALL WebSocket messages for debugging
                print(f"--- WEBSOCKET MESSAGE: {message_type} ---")
                print(f"Full message: {message}")
                
                if message_type == "conversation_initiation_metadata":
                    conversation_id = data.get("conversation_initiation_metadata_event", {}).get("conversation_id")
                    print(f"--- WEBSOCKET: CONVERSATION ID: {conversation_id} ---")
                
                elif message_type == "user_transcript":
                    current_transcript = data.get("user_transcription_event", {}).get("user_transcript", "")
                    print(f"USER (WEBSOCKET): {current_transcript}")
                    
                elif message_type == "agent_response":
                    current_response = data.get("agent_response_event", {}).get("agent_response", "")
                    print(f"AGENT A (WEBSOCKET): {current_response}")
                    
                    # Send to backend agent in real-time when we have both user and agent message
                    if current_transcript and current_response:
                        conversation_turn = f"User: {current_transcript}\nAgent A: {current_response}"
                        print("--- WEBSOCKET: Sending to Backend Agent ---")
                        print(conversation_turn)
                        self._send_to_backend_api(conversation_turn)
                        # Reset for next turn
                        current_transcript = ""
                        current_response = ""
                        
            except Exception as e:
                print(f"--- WEBSOCKET ERROR: {e} ---")
                print(f"Raw message: {message}")
        
        def on_error(ws, error):
            print(f"--- WEBSOCKET ERROR: {error} ---")
        
        def on_close(ws, close_status_code, close_msg):
            print("--- WEBSOCKET CLOSED ---")
        
        def on_open(ws):
            print("--- WEBSOCKET CONNECTED ---")
        
        # Create WebSocket connection
        ws_url = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={ELEVENLABS_AGENT_ID}"
        
        try:
            self.ws = websocket.WebSocketApp(
                ws_url,
                header=[f"xi-api-key: {self.api_key}"],
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
        except Exception as e:
            print(f"--- WEBSOCKET SETUP ERROR: {e} ---")
            print("--- Note: You may need to install websocket-client: pip install websocket-client ---")
            self.ws = None

    def start(self):
        """Starts the conversational session with real-time audio capture and transcription."""
        print("Starting conversational agent session with Whisper transcription...")
        
        # Start the ElevenLabs conversation
        self.conversation.start_session()
        self._running = True
        
        # Start audio capture in a separate thread
        self._audio_thread = threading.Thread(target=self._audio_capture_thread, daemon=True)
        self._audio_thread.start()
        
        # Simplified polling - just to keep track of state
        def poll_conversation():
            while self._running:
                try:
                    # Just check if conversation ID is available
                    if hasattr(self.conversation, '_conversation_id') and self.conversation._conversation_id:
                        if not hasattr(self, '_logged_conv_id'):
                            print(f"--- SDK CONVERSATION ID: {self.conversation._conversation_id} ---")
                            self._logged_conv_id = True
                    
                except Exception as e:
                    print(f"--- POLLING ERROR: {e} ---")
                
                time.sleep(5)  # Poll every 5 seconds
        
        # Start polling in a separate thread
        poll_thread = threading.Thread(target=poll_conversation, daemon=True)
        poll_thread.start()
        
        print("🎙️ Ready! Speak to the agent - your speech will be transcribed and sent to the backend agent.")
        
        # Wait for the session to end
        conversation_id = self.conversation.wait_for_session_end()
        print(f"--- CONVERSATION ENDED. ID: {conversation_id} ---")
        
        print("Conversational agent session has ended.")

    def stop(self):
        """Stops the conversational session and audio capture."""
        print("Stopping conversational agent session.")
        self._running = False
        
        # Stop audio capture
        if self._audio_thread and self._audio_thread.is_alive():
            print("Stopping audio capture...")
            # The audio thread will stop when _running becomes False
            
        # Clean up audio resources
        try:
            if hasattr(self, 'audio') and self.audio:
                self.audio.terminate()
        except Exception as e:
            print(f"Error cleaning up audio: {e}")
        
        # Stop ElevenLabs conversation
        try:
            if hasattr(self, 'conversation') and self.conversation:
                self.conversation.end_session()
        except Exception as e:
            print(f"Error ending conversation session: {e}") 