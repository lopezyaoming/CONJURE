"""
Phase 2 Voice Processor - Simplified voice-to-prompt updates
Handles continuous voice capture and immediate prompt updates without conversation.
"""

import os
import time
import threading
import pyaudio
import tempfile
import wave
from collections import deque
from openai import OpenAI
from pathlib import Path
from launcher.backend_agent import BackendAgent

# Audio capture settings optimized for voice
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
SILENCE_THRESHOLD = 1000  # Adjust based on environment
SILENCE_DURATION = 1.5  # Seconds of silence before processing (faster than conversation)

class VoiceProcessor:
    """
    PHASE 2: Simplified voice processor for continuous prompt updates.
    No conversation - just voice → structured prompt updates.
    """
    
    def __init__(self, backend_agent: BackendAgent):
        """Initialize voice processor with backend agent for prompt updates."""
        self.backend_agent = backend_agent
        
        # OpenAI setup for Whisper transcription
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("⚠️ OPENAI_API_KEY not set - voice processing disabled")
            self.openai_client = None
            self.voice_enabled = False
        else:
            self.openai_client = OpenAI(api_key=openai_api_key)
            self.voice_enabled = True
            print("✅ Voice processor initialized with Whisper transcription")
        
        # Audio capture setup
        if self.voice_enabled:
            try:
                self.audio = pyaudio.PyAudio()
                self._running = False
                self._audio_thread = None
                self._audio_queue = deque(maxlen=50)  # Smaller buffer for faster processing
                print("✅ Audio capture system ready")
            except Exception as e:
                print(f"❌ Audio capture setup failed: {e}")
                self.voice_enabled = False
    
    def start(self):
        """Start continuous voice processing."""
        if not self.voice_enabled:
            print("⚠️ Voice processing disabled - skipping voice capture")
            return
        
        if self._running:
            print("⚠️ Voice processor already running")
            return
        
        print("🎤 Starting continuous voice processing...")
        self._running = True
        
        # Start audio capture thread
        self._audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self._audio_thread.start()
        
        print("✅ Voice processor started - listening for speech")
    
    def stop(self):
        """Stop voice processing."""
        if not self._running:
            return
        
        print("🔇 Stopping voice processor...")
        self._running = False
        
        # Wait for audio thread to finish
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=2.0)
        
        # Cleanup audio
        if hasattr(self, 'audio'):
            try:
                self.audio.terminate()
            except:
                pass
        
        print("✅ Voice processor stopped")
    
    def _audio_capture_loop(self):
        """Main audio capture loop - detects speech and processes it."""
        try:
            # Open audio stream
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            print("🎤 Audio capture started - speak to update prompts")
            
            audio_buffer = []
            is_speaking = False
            last_speech_time = time.time()
            
            while self._running:
                try:
                    # Read audio chunk
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    current_time = time.time()
                    
                    if not self._detect_silence(data):
                        # Speech detected
                        if not is_speaking:
                            print("🗣️ Speech detected...")
                            is_speaking = True
                        
                        audio_buffer.append(data)
                        last_speech_time = current_time
                    else:
                        # Silence detected
                        if is_speaking and (current_time - last_speech_time) > SILENCE_DURATION:
                            print("🔇 Speech ended - processing...")
                            duration = len(audio_buffer) * CHUNK / RATE
                            print(f"🎵 Processing {duration:.1f}s of audio...")
                            
                            # Process audio in separate thread to avoid blocking
                            processing_thread = threading.Thread(
                                target=self._process_speech_audio,
                                args=(audio_buffer.copy(),),
                                daemon=True
                            )
                            processing_thread.start()
                            
                            # Reset for next speech
                            audio_buffer.clear()
                            is_speaking = False
                
                except Exception as e:
                    if self._running:
                        print(f"❌ Audio capture error: {e}")
                    break
            
            # Cleanup
            stream.stop_stream()
            stream.close()
            print("🔇 Audio capture stopped")
            
        except Exception as e:
            print(f"❌ Audio capture setup error: {e}")
    
    def _detect_silence(self, audio_data):
        """Simple silence detection based on audio amplitude."""
        import audioop
        try:
            rms = audioop.rms(audio_data, 2)  # 2 bytes per sample for paInt16
            return rms < SILENCE_THRESHOLD
        except:
            return True  # Assume silence on error
    
    def _process_speech_audio(self, audio_buffer):
        """Process captured speech through Whisper and update prompt."""
        try:
            if not audio_buffer:
                print("⚠️ Empty audio buffer - skipping processing")
                return
            
            # Convert audio buffer to WAV format for Whisper
            wav_data = self._audio_buffer_to_wav(audio_buffer)
            if not wav_data:
                print("❌ Failed to convert audio to WAV")
                return
            
            # Transcribe with Whisper
            transcript = self._transcribe_with_whisper(wav_data)
            if not transcript or len(transcript.strip()) < 3:
                print("⚠️ No meaningful speech detected")
                return
            
            print(f"📝 Transcribed: '{transcript}'")
            
            # Update prompt using backend agent
            self._update_prompt_with_speech(transcript)
            
        except Exception as e:
            print(f"❌ Speech processing error: {e}")
    
    def _audio_buffer_to_wav(self, audio_buffer):
        """Convert audio buffer to WAV format for Whisper API."""
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                wav_file = wave.open(temp_wav, 'wb')
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(self.audio.get_sample_size(FORMAT))
                wav_file.setframerate(RATE)
                
                # Write all audio chunks
                for chunk in audio_buffer:
                    wav_file.writeframes(chunk)
                
                wav_file.close()
                temp_wav_path = temp_wav.name
            
            return temp_wav_path
            
        except Exception as e:
            print(f"❌ WAV conversion error: {e}")
            return None
    
    def _transcribe_with_whisper(self, wav_file_path):
        """Transcribe audio using OpenAI Whisper API."""
        try:
            with open(wav_file_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"  # Optimize for English
                )
            
            # Cleanup temp file
            try:
                os.unlink(wav_file_path)
            except:
                pass
            
            return transcript.text.strip()
            
        except Exception as e:
            print(f"❌ Whisper transcription error: {e}")
            # Cleanup temp file on error
            try:
                os.unlink(wav_file_path)
            except:
                pass
            return None
    
    def _update_prompt_with_speech(self, transcript):
        """Update prompt using backend agent voice processing."""
        try:
            # Use backend agent to process voice input
            # This will update userPrompt.txt with the new structured prompt
            gesture_render_path = Path(__file__).parent.parent / "data" / "generated_images" / "gestureCamera" / "render.png"
            
            result = self.backend_agent.process_voice_input(
                speech_transcript=transcript,
                current_prompt_state=None,  # Let backend agent read current state
                gesture_render_path=str(gesture_render_path) if gesture_render_path.exists() else None
            )
            
            if result:
                print("✅ Prompt updated successfully from voice input")
            else:
                print("⚠️ Voice processing completed but no update made")
                
        except Exception as e:
            print(f"❌ Prompt update error: {e}")
    
    def is_running(self):
        """Check if voice processor is currently running."""
        return self._running and self.voice_enabled
    
    def get_status(self):
        """Get current voice processor status."""
        return {
            "enabled": self.voice_enabled,
            "running": self._running,
            "has_openai_key": self.openai_client is not None,
            "has_audio": hasattr(self, 'audio')
        }
