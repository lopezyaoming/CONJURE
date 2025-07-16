"""
Test script for audio capture and OpenAI Whisper transcription.
Run this to verify the components work before testing the full system.
"""
import os
import time
import threading
import pyaudio
import tempfile
import wave
from openai import OpenAI

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
SILENCE_THRESHOLD = 1000
SILENCE_DURATION = 2.0

def detect_silence(audio_data):
    """Simple silence detection."""
    import struct
    import math
    samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    return rms < SILENCE_THRESHOLD

def save_audio_to_file(audio_data):
    """Save audio to temporary WAV file."""
    audio = pyaudio.PyAudio()
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        with wave.open(temp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(audio.get_sample_size(FORMAT))
            wav_file.setframerate(RATE)
            wav_file.writeframes(audio_data)
        audio.terminate()
        return temp_file.name

def transcribe_audio(audio_file_path):
    """Transcribe using OpenAI Whisper."""
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"
            )
            return transcript.text
    except Exception as e:
        print(f"Transcription error: {e}")
        return None
    finally:
        try:
            os.unlink(audio_file_path)
        except:
            pass

def test_audio_capture():
    """Test audio capture and transcription."""
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set!")
        return
    
    print("✅ OpenAI API key found")
    
    # Test audio setup
    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        print("✅ Audio input setup successful")
        
        print("\n🎤 Say something and stop speaking for 2 seconds to trigger transcription...")
        print("Press Ctrl+C to exit\n")
        
        audio_buffer = []
        is_speaking = False
        last_sound_time = time.time()
        
        while True:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                current_time = time.time()
                
                if not detect_silence(data):
                    # Sound detected
                    if not is_speaking:
                        print("🗣️ Speaking detected...")
                        is_speaking = True
                        audio_buffer = []
                    
                    audio_buffer.append(data)
                    last_sound_time = current_time
                    
                elif is_speaking:
                    # Silent chunk while speaking
                    audio_buffer.append(data)
                    
                    # Check for end of speech
                    if current_time - last_sound_time > SILENCE_DURATION:
                        print("🔇 Silence detected, processing...")
                        is_speaking = False
                        
                        if audio_buffer:
                            # Process audio
                            audio_data = b''.join(audio_buffer)
                            duration = len(audio_data) / (RATE * 2)
                            
                            if duration > 0.5:
                                print(f"🎵 Transcribing {duration:.1f}s of audio...")
                                
                                audio_file = save_audio_to_file(audio_data)
                                transcript = transcribe_audio(audio_file)
                                
                                if transcript:
                                    print(f"📝 TRANSCRIPT: {transcript}")
                                else:
                                    print("❌ No transcript received")
                            else:
                                print("⏱️ Audio too short")
                        
                        audio_buffer = []
                        print("\n🎤 Ready for next speech...")
                
            except KeyboardInterrupt:
                print("\n👋 Stopping test...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                break
        
        stream.stop_stream()
        stream.close()
        
    except Exception as e:
        print(f"❌ Audio setup failed: {e}")
    finally:
        audio.terminate()

if __name__ == "__main__":
    test_audio_capture() 