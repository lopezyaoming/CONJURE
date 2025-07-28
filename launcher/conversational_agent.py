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
try:
    from backend_agent import BackendAgent
except ImportError:
    from launcher.backend_agent import BackendAgent
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
        
        # 🎯 STRUCTURED CONVERSATION TURN TRACKING
        self.current_turn = {
            "user_message": None,
            "agent_message": None,
            "turn_complete": False
        }
        self.conversation_history = []  # Store complete turns
        self._turn_timeout = 30.0  # seconds to wait for complete turn
        self._turn_start_time = None
        
        # 🐛 DEBUGGING AND SOURCE MANAGEMENT
        self.debug_mode = True  # Enable detailed debugging
        self.transcript_sources = {
            "whisper": True,      # PyAudio + Whisper transcription
            "sdk_callbacks": True, # ElevenLabs SDK callbacks  
            "websocket": True,    # WebSocket events
            "message_hooks": True # Message handler hooks
        }
        self._agent_message_buffer = []  # Buffer fragmented agent messages
        self._agent_message_timeout = 3.0  # seconds to wait for complete agent message
        self._last_agent_fragment_time = None
        
        # Load fix configuration if it exists
        self._load_fix_configuration()
        
        self.conversation = self._setup_conversation()
        self.full_transcript = []
        self._logged_conv_id = False
        
        # Initialize debug file
        with open("transcript_debug.txt", "w") as f:
            f.write("=== CONJURE TRANSCRIPT DEBUG LOG WITH WHISPER ===\n")

    def _load_fix_configuration(self):
        """Load fix configuration from conversation_fix_config.json if it exists."""
        try:
            import json
            with open("conversation_fix_config.json", "r") as f:
                fix_config = json.load(f)
            
            print("🔧 Loading conversation fix configuration...")
            
            # Apply transcript source settings
            if "transcript_sources" in fix_config:
                for source, enabled in fix_config["transcript_sources"].items():
                    if source in self.transcript_sources:
                        old_value = self.transcript_sources[source]
                        self.transcript_sources[source] = enabled
                        status = "🟢 ENABLED" if enabled else "🔴 DISABLED"
                        print(f"   {source}: {status}")
            
            # Apply timeout settings
            if "agent_message_timeout" in fix_config:
                self._agent_message_timeout = fix_config["agent_message_timeout"]
                print(f"   Agent message timeout: {self._agent_message_timeout}s")
            
            if "turn_timeout" in fix_config:
                self._turn_timeout = fix_config["turn_timeout"]
                print(f"   Turn timeout: {self._turn_timeout}s")
            
            if "debug_mode" in fix_config:
                self.debug_mode = fix_config["debug_mode"]
                print(f"   Debug mode: {'🟢 ON' if self.debug_mode else '🔴 OFF'}")
            
            print("✅ Fix configuration applied successfully")
            
        except FileNotFoundError:
            print("ℹ️ No fix configuration found - using defaults")
        except Exception as e:
            print(f"⚠️ Error loading fix configuration: {e}")
    
    # 🎯 STRUCTURED CONVERSATION TURN MANAGEMENT
    
    def _add_user_message(self, message: str):
        """Add user message to current conversation turn."""
        self._debug_log("USER_TURN", "MESSAGE", message)
        
        user_msg = message.strip()
        print(f"📝 USER REQUEST: {user_msg}")
        
        # Store user message in current conversation turn
        self.current_turn["user_message"] = user_msg
        
        # Initialize turn timing if this is the start
        if self._turn_start_time is None:
            self._turn_start_time = time.time()
        
        # Check if we have a complete turn (user + agent) to send to backend
        self._check_turn_completion()
    
    def _add_agent_message(self, message: str):
        """Add agent message to current conversation turn."""
        self._debug_log("AGENT_TURN", "MESSAGE", message)
        
        agent_msg = message.strip()
        print(f"🤖 AGENT RESPONSE: {agent_msg}")
        
        # Store agent message in current conversation turn
        self.current_turn["agent_message"] = agent_msg
        
        # Initialize turn timing if this is the start
        if self._turn_start_time is None:
            self._turn_start_time = time.time()
        
        # Check if we have a complete turn (user + agent) to send to backend
        self._check_turn_completion()
    
    def _check_turn_completion(self):
        """Check if current turn is complete (has both user and agent messages)."""
        if (self.current_turn["user_message"] is not None and 
            self.current_turn["agent_message"] is not None and 
            not self.current_turn["turn_complete"]):
            
            print("✅ CONVERSATION TURN COMPLETE - Sending to Backend Agent")
            self._send_complete_turn_to_backend()
            self.current_turn["turn_complete"] = True
    
    def _send_complete_turn_to_backend(self):
        """Send complete conversation turn to backend agent."""
        user_msg = self.current_turn["user_message"]
        agent_msg = self.current_turn["agent_message"]
        
        if not user_msg or not agent_msg:
            print("⚠️ Cannot send incomplete turn to backend agent")
            return
        
        # Format the complete conversation turn
        conversation_turn = f"User: {user_msg}\nAgent: {agent_msg}"
        
        print("\n" + "="*60)
        print("🎯 SENDING COMPLETE TURN TO BACKEND AGENT")
        print("="*60)
        print(conversation_turn)
        print("="*60 + "\n")
        
        # Store in conversation history
        self.conversation_history.append({
            "user": user_msg,
            "agent": agent_msg,
            "timestamp": time.time()
        })
        
        # Send to backend agent via API
        try:
            self._send_to_backend_api(conversation_turn)
        except Exception as e:
            print(f"❌ Error sending complete turn to backend: {e}")
        
        # Reset for next turn after a short delay to prevent immediate new turns
        threading.Timer(2.0, self._reset_current_turn).start()
    
    def _force_turn_completion(self):
        """Force completion of current turn after fragment timeout."""
        if (self.current_turn["user_message"] is not None and 
            self.current_turn["agent_message"] is not None and 
            not self.current_turn["turn_complete"]):
            
            print(f"⏰ Fragment timeout - forcing turn completion")
            print(f"   Final agent message: '{self.current_turn['agent_message']}'")
            self._send_complete_turn_to_backend()
            self.current_turn["turn_complete"] = True
    
    def _reset_current_turn(self):
        """Reset current turn for next conversation."""
        print("🔄 Resetting conversation turn for next interaction")
        
        # Cancel any pending fragment timer
        if hasattr(self, '_fragment_timer'):
            self._fragment_timer.cancel()
            
        self.current_turn = {
            "user_message": None,
            "agent_message": None,
            "turn_complete": False
        }
        self._turn_start_time = None
    
    def _check_turn_timeout(self):
        """Check if current turn has timed out and reset if needed."""
        if (self._turn_start_time and 
            time.time() - self._turn_start_time > self._turn_timeout and
            not self.current_turn["turn_complete"]):
            
            print(f"⏰ Turn timeout ({self._turn_timeout}s) - resetting incomplete turn")
            self._reset_current_turn()

    def get_conversation_status(self):
        """Get current conversation turn status for debugging."""
        return {
            "current_turn": self.current_turn.copy(),
            "turn_start_time": self._turn_start_time,
            "conversation_history_length": len(self.conversation_history),
            "is_running": self._running
        }
    
    def check_current_turn_debug(self):
        """Debug method to check current turn status."""
        print("\n🔍 TURN DEBUG STATUS:")
        print(f"   User message present: {self.current_turn['user_message'] is not None}")
        print(f"   Agent message present: {self.current_turn['agent_message'] is not None}")
        print(f"   Turn complete: {self.current_turn['turn_complete']}")
        if self.current_turn['user_message']:
            print(f"   User: {self.current_turn['user_message'][:100]}...")
        if self.current_turn['agent_message']:
            print(f"   Agent: {self.current_turn['agent_message'][:100]}...")
        print()

    # 🐛 COMPREHENSIVE DEBUGGING METHODS
    
    def print_debug_status(self):
        """Print comprehensive debugging information."""
        print("\n" + "🐛" + "="*70)
        print("🐛 CONVERSATIONAL AGENT DEBUG STATUS")
        print("🐛" + "="*70)
        
        # Current turn status
        print(f"📝 Current Turn Status:")
        print(f"   User Message: {self.current_turn['user_message']}")
        print(f"   Agent Message: {self.current_turn['agent_message']}")
        print(f"   Turn Complete: {self.current_turn['turn_complete']}")
        
        # Agent message buffer
        if self._agent_message_buffer:
            print(f"🤖 Agent Message Buffer ({len(self._agent_message_buffer)} fragments):")
            for i, fragment in enumerate(self._agent_message_buffer):
                print(f"   [{i}]: {fragment[:50]}...")
        
        # Timing information
        if self._turn_start_time:
            elapsed = time.time() - self._turn_start_time
            print(f"⏱️ Turn Elapsed Time: {elapsed:.1f}s (timeout: {self._turn_timeout}s)")
        
        if self._last_agent_fragment_time:
            fragment_elapsed = time.time() - self._last_agent_fragment_time
            print(f"⏱️ Last Agent Fragment: {fragment_elapsed:.1f}s ago (timeout: {self._agent_message_timeout}s)")
        
        # Active sources
        active_sources = [k for k, v in self.transcript_sources.items() if v]
        print(f"📡 Active Sources: {', '.join(active_sources)}")
        
        # Conversation history
        print(f"📚 Conversation History: {len(self.conversation_history)} complete turns")
        
        print("🐛" + "="*70 + "\n")
    
    def disable_transcript_source(self, source_name: str):
        """Disable a specific transcript source to reduce conflicts."""
        if source_name in self.transcript_sources:
            self.transcript_sources[source_name] = False
            print(f"🔇 DISABLED transcript source: {source_name}")
        else:
            print(f"❌ Unknown transcript source: {source_name}")
    
    def _debug_log(self, source: str, message_type: str, content: str):
        """Centralized debug logging."""
        if self.debug_mode:
            timestamp = time.strftime("%H:%M:%S")
            print(f"🐛 [{timestamp}] [{source}] {message_type}: {content[:100]}...")
            
            # Also log to debug file with more detail
            with open("transcript_debug.txt", "a") as f:
                f.write(f"[{timestamp}] [{source}] {message_type}: {content}\n")

    def _add_agent_message_fragment(self, fragment: str):
        """Add agent message fragment and check if message is complete."""
        if not self.transcript_sources.get("message_hooks", True):
            return
            
        self._debug_log("AGENT_BUFFER", "FRAGMENT", fragment)
        
        # Add fragment to buffer
        self._agent_message_buffer.append(fragment.strip())
        self._last_agent_fragment_time = time.time()
        
        # Check if this looks like a complete message (ends with punctuation)
        if fragment.strip().endswith(('.', '!', '?')) and len(' '.join(self._agent_message_buffer)) > 20:
            self._process_complete_agent_message()
        
        # Start timer to process buffered message
        threading.Timer(self._agent_message_timeout, self._check_agent_buffer_timeout).start()
    
    def _process_complete_agent_message(self):
        """Process the complete agent message from buffer."""
        if not self._agent_message_buffer:
            return
            
        complete_message = ' '.join(self._agent_message_buffer).strip()
        self._debug_log("AGENT_COMPLETE", "MESSAGE", complete_message)
        
        # Clear buffer
        self._agent_message_buffer = []
        self._last_agent_fragment_time = None
        
        # Add to conversation turn
        self._add_agent_message(complete_message)
    
    def _check_agent_buffer_timeout(self):
        """Check if agent message buffer has timed out."""
        if (self._last_agent_fragment_time and 
            time.time() - self._last_agent_fragment_time >= self._agent_message_timeout and
            self._agent_message_buffer):
            
            print(f"⏰ Agent message buffer timeout - processing {len(self._agent_message_buffer)} fragments")
            self._process_complete_agent_message()

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
                        # Removed console logging for cleaner output
                        if self.transcript_sources.get("message_hooks", True):
                            try:
                                self._add_agent_message_fragment(agent_text)
                            except Exception as e:
                                print(f"Error adding agent response fragment: {e}")
                        else:
                            pass  # Message hooks disabled
                
                elif message_type == 'user_transcript':
                    print("🎯 FOUND USER_TRANSCRIPT MESSAGE:")
                    user_event = message.get('user_transcription_event', {})
                    user_text = user_event.get('user_transcript', '')
                    if user_text:
                        # Removed console logging for cleaner output
                        try:
                            self._add_user_message(user_text)
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
                                print("🤖 Adding extracted agent text to conversation turn...")
                                try:
                                    self._add_agent_message(extracted_text)
                                except Exception as e:
                                    print(f"Error adding extracted text to turn: {e}")
                
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
                    # Removed console logging for cleaner output
                    try:
                        self._add_agent_message(agent_text)
                    except Exception as e:
                        print(f"Error adding agent transcript to turn: {e}")
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
                # Removed console logging for cleaner output
                
                # Log to debug file
                with open("transcript_debug.txt", "a") as f:
                    f.write(f"USER (Whisper): {transcript}\n")
                
                # Add to structured conversation turn (NO immediate sending)
                # ALWAYS add user messages to turn regardless of transcript source
                self._add_user_message(transcript)
                
                # Only skip the Whisper-specific processing if disabled
                if not self.transcript_sources.get("whisper", True):
                    print("🔇 Whisper source disabled (but message still added to turn)")
                
            else:
                print("🤷 No clear speech detected in audio")
                
        except Exception as e:
            print(f"Transcription processing error: {e}")

    def _send_user_request_to_backend(self, user_message: str):
        """
        SIMPLIFIED APPROACH: Send only user request directly to backend agent.
        No complex conversation turns - just user speech to backend.
        """
        print(f"\n{'='*60}")
        print(f"🎯 SENDING USER REQUEST TO BACKEND AGENT")
        print(f"{'='*60}")
        print(f"User Request: {user_message}")
        print(f"{'='*60}\n")
        
        try:
            # Format as simple user request (not complex conversation)
            request_text = f"User Request: {user_message}"
            
            print(f"🚀 Sending user request to API: '{user_message}'")
            
            with httpx.Client() as client:
                payload = {
                    "conversation_history": request_text,
                    "include_image": True
                }
                
                response = client.post(
                    "http://127.0.0.1:8000/process_conversation",
                    json=payload,
                    timeout=30.0
                )
                
                print(f"📥 API response status: {response.status_code}")
                
                if response.status_code == 200:
                    print("✅ Successfully sent user request to backend API")
                    response_data = response.json()
                    print(f"📊 API response data: {response_data}")
                else:
                    print(f"❌ Backend API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            print(f"❌ Error sending user request to backend: {e}")
            
            # Fallback to direct call if API is unavailable
            print("🔄 Falling back to direct backend agent call")
            if hasattr(self, 'backend_agent') and self.backend_agent:
                self.backend_agent.get_response(f"User Request: {user_message}")

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
            # ALWAYS add user messages to turn regardless of transcript source
            print("📝 Adding SDK user transcript to conversation turn...")
            try:
                self._add_user_message(transcript)
            except Exception as e:
                print(f"Error adding SDK user transcript to turn: {e}")
            
            # Only log if SDK callbacks are disabled
            if not self.transcript_sources.get("sdk_callbacks", True):
                print("🔇 SDK callbacks disabled (but message still added to turn)")

    def _on_agent_response(self, response):
        """Callback for agent response - should be called by ElevenLabs SDK."""
        # Removed console logging for cleaner output
        
        if response and response.strip():
            if self.transcript_sources.get("sdk_callbacks", True):
                try:
                    self._add_agent_message_fragment(response)
                except Exception as e:
                    print(f"Error adding SDK agent response fragment: {e}")
            else:
                pass  # SDK callbacks disabled
        
        # Note: Removed immediate backend sending - now handled by structured turns

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
                    if current_transcript.strip():
                        self._add_user_message(current_transcript)
                    
                elif message_type == "agent_response":
                    current_response = data.get("agent_response_event", {}).get("agent_response", "")
                    print(f"AGENT A (WEBSOCKET): {current_response}")
                    if current_response.strip():
                        self._add_agent_message(current_response)
                    
                    # Note: Structured turn handling now manages complete conversations
                        
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
        
        # Simplified polling - just to keep track of state and check timeouts
        def poll_conversation():
            while self._running:
                try:
                    # Just check if conversation ID is available
                    if hasattr(self.conversation, '_conversation_id') and self.conversation._conversation_id:
                        if not hasattr(self, '_logged_conv_id'):
                            print(f"--- SDK CONVERSATION ID: {self.conversation._conversation_id} ---")
                            self._logged_conv_id = True
                    
                    # Check for conversation turn timeouts
                    self._check_turn_timeout()
                    
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