"""
Manages voice input, recording, and transcription using Whisper.
"""

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
from openai import OpenAI
import threading
import io
import time

class VoiceInputManager:
    """Handles recording audio and transcribing it using Whisper."""
    def __init__(self, api_key, sample_rate=16000):
        self.client = OpenAI(api_key=api_key)
        self.sample_rate = sample_rate
        self.is_recording = False
        self.recording_thread = None
        self.frames = []

    def _trim_silence(self, audio, threshold_level=0.01, chunk_size=1024):
        """
        Trims silence from the beginning and end of a NumPy audio array.
        """
        if audio.size == 0:
            return audio
            
        # Find the first chunk above the threshold
        first_chunk = -1
        for i in range(0, len(audio), chunk_size):
            if np.max(np.abs(audio[i:i+chunk_size])) > threshold_level:
                first_chunk = i
                break
        
        # If all chunks are silent, return an empty array
        if first_chunk == -1:
            return np.array([])
            
        # Find the last chunk above the threshold
        last_chunk = -1
        for i in range(len(audio) - chunk_size, -1, -chunk_size):
            if np.max(np.abs(audio[i:i+chunk_size])) > threshold_level:
                last_chunk = i + chunk_size
                break
        
        # Return the trimmed audio
        start_index = max(0, first_chunk)
        end_index = min(len(audio), last_chunk)
        return audio[start_index:end_index]


    def _record_audio(self):
        """Callback-based audio recording to avoid blocking."""
        self.frames = []
        
        def callback(indata, frames, time, status):
            if status:
                print(f"Sounddevice status: {status}")
            self.frames.append(indata.copy())

        # The 'with' statement ensures the stream is properly closed.
        with sd.InputStream(callback=callback, samplerate=self.sample_rate, channels=1, dtype='float32'):
            while self.is_recording:
                sd.sleep(100) # Check the is_recording flag every 100ms

    def start_recording(self):
        """Starts the audio recording in a background thread."""
        if not self.is_recording:
            print(">>> REC: Starting voice recording...")
            self.is_recording = True
            self.recording_thread = threading.Thread(target=self._record_audio)
            self.recording_thread.start()

    def stop_recording_and_transcribe(self):
        """Stops recording, saves the audio, and sends it to Whisper for transcription."""
        if self.is_recording:
            # Give the recording a brief moment to capture the last sounds
            time.sleep(0.25)
            self.is_recording = False
            if self.recording_thread:
                self.recording_thread.join()
            print(">>> REC: Recording stopped. Transcribing...")

            if not self.frames:
                print(">>> Whisper: No audio recorded.")
                return ""

            # 1. Concatenate all recorded frames
            recording = np.concatenate(self.frames, axis=0)
            
            # 2. Trim silence from the start and end of the recording
            trimmed_recording = self._trim_silence(recording)
            
            if trimmed_recording.size == 0:
                print(">>> Whisper: Audio was all silence. Nothing to transcribe.")
                return ""
            
            print(f">>> REC: Original duration: {len(recording)/self.sample_rate:.2f}s, Trimmed duration: {len(trimmed_recording)/self.sample_rate:.2f}s")

            # 3. Prepare the audio data in an in-memory WAV buffer
            buffer = io.BytesIO()
            # Whisper prefers 16-bit PCM WAV
            wav.write(buffer, self.sample_rate, (trimmed_recording * 32767).astype(np.int16))
            buffer.seek(0)
            
            # The OpenAI API needs a file tuple: (filename, file-like-object)
            file_tuple = ("user_speech.wav", buffer)

            try:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=file_tuple
                )
                text = response.text
                print(f">>> Whisper: Transcription successful: '{text}'")
                return text
            except Exception as e:
                print(f"--- ERROR: Whisper transcription failed: {e} ---")
                return ""
        return "" 