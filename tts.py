"""
Text-to-Speech module using OpenAI TTS with streaming playback.
"""
import re
import threading
from typing import Optional

import pyaudio
from openai import OpenAI

from config import get_config, TTS_VOICES


class TTS:
    """TTS wrapper using OpenAI's text-to-speech API with streaming."""

    def __init__(self):
        self.client = None
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._audio = None
        self._stream = None
        self._stream_lock = threading.Lock()
        self._config = get_config()
        self._init_engine()

    def _init_engine(self):
        """Initialize the OpenAI client and pyaudio."""
        try:
            self.client = OpenAI()
            self._audio = pyaudio.PyAudio()
        except Exception as e:
            print(f"Warning: Could not initialize TTS: {e}")
            self.client = None

    @property
    def enabled(self) -> bool:
        return self._config.tts_enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._config.tts_enabled = value
        if not value:
            self.stop()

    @property
    def speed(self) -> float:
        return self._config.tts_speed

    @speed.setter
    def speed(self, value: float):
        self._config.tts_speed = value

    @property
    def voice(self) -> str:
        return self._config.tts_voice

    @voice.setter
    def voice(self, value: str):
        self._config.tts_voice = value

    @property
    def model(self) -> str:
        return self._config.tts_model

    @model.setter
    def model(self, value: str):
        self._config.tts_model = value

    def toggle(self) -> bool:
        """Toggle TTS on/off. Returns new state."""
        self.enabled = not self.enabled
        return self.enabled

    def set_enabled(self, enabled: bool):
        """Set TTS enabled state."""
        self.enabled = enabled

    def _clean_text(self, text: str) -> str:
        """Remove Rich markup and clean text for TTS."""
        # Remove Rich markup tags like [bold], [dim], [/], etc.
        text = re.sub(r'\[/?[^\]]+\]', '', text)
        # Remove markdown-style formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _stream_and_play(self, text: str):
        """Stream speech from OpenAI and play it with minimal latency."""
        if not self.client or not self._audio:
            return

        stream = None
        try:
            # Request streaming response with PCM format for lower latency
            with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=self.voice,
                input=text,
                speed=self.speed,
                response_format="pcm"  # Raw PCM: 24kHz, 16-bit, mono
            ) as response:
                # Check stop flag before opening stream
                if self._stop_flag.is_set():
                    return

                # Open audio stream for PCM playback
                # OpenAI PCM is 24000 Hz, 16-bit signed, mono
                with self._stream_lock:
                    stream = self._audio.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=24000,
                        output=True,
                        frames_per_buffer=1024
                    )
                    self._stream = stream

                # Stream and play chunks as they arrive
                for chunk in response.iter_bytes(chunk_size=4096):
                    if self._stop_flag.is_set():
                        break
                    if chunk and stream:
                        try:
                            stream.write(chunk)
                        except OSError:
                            # Stream was closed
                            break

        except Exception as e:
            if not self._stop_flag.is_set():
                print(f"TTS error: {e}")
        finally:
            with self._stream_lock:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass
                self._stream = None

    def speak(self, text: str, blocking: bool = False, interrupt: bool = True):
        """
        Speak the given text with streaming playback.

        Args:
            text: The text to speak
            blocking: If True, wait for speech to complete. If False, return immediately.
            interrupt: If True, stop any current speech before starting new speech.
        """
        if not self.enabled or not self.client:
            return

        # Clean the text
        clean_text = self._clean_text(text)
        if not clean_text:
            return

        # Track TTS character usage for cost calculation (do this before async call)
        self._config.add_tts_chars(len(clean_text))

        if interrupt:
            self.stop()

        # Clear the stop flag for new speech
        self._stop_flag.clear()

        if blocking:
            self._stream_and_play(clean_text)
        else:
            # Run in background thread
            self._playback_thread = threading.Thread(
                target=self._stream_and_play,
                args=(clean_text,),
                daemon=True
            )
            self._playback_thread.start()

    def stop(self):
        """Stop current speech immediately."""
        self._stop_flag.set()
        with self._stream_lock:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except:
                    pass
                self._stream = None
        # Wait for playback thread to finish
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=0.5)

    def adjust_speed(self, delta: int) -> int:
        """
        Adjust TTS speed by delta. Returns new rate for display.

        Args:
            delta: Amount to change speed (positive = faster, negative = slower)
                   Expected: ±25 steps on 100-300 scale

        Returns:
            New speed rate in display scale (100-300)
        """
        # Convert delta from 100-300 scale to OpenAI's scale
        # 100-300 maps to 0.5-1.5, so delta of 25 = 0.125 in OpenAI scale
        openai_delta = delta / 200  # 25/200 = 0.125

        # Clamp speed between 0.5 and 1.5 (reasonable range for narration)
        self.speed = max(0.5, min(1.5, self.speed + openai_delta))

        return self._speed_to_display()

    def get_speed(self) -> int:
        """Get current TTS speed rate in display scale (100-300)."""
        return self._speed_to_display()

    def _speed_to_display(self) -> int:
        """Convert OpenAI speed (0.5-1.5) to display rate (100-300)."""
        # Map 0.5 to 100, 1.0 to 200, 1.5 to 300
        return int(self.speed * 200)

    def get_voices(self) -> list:
        """Get list of available voices."""
        return TTS_VOICES.copy()

    def get_current_voice_name(self) -> str:
        """Get the name of the current voice."""
        return self.voice.capitalize()

    def set_voice(self, voice: str):
        """Set the current voice by name."""
        if voice.lower() in TTS_VOICES:
            self.voice = voice.lower()

    def cycle_voice(self) -> str:
        """
        Cycle to the next available voice. Returns the new voice name.
        """
        try:
            current_idx = TTS_VOICES.index(self.voice)
        except ValueError:
            current_idx = 0
        next_idx = (current_idx + 1) % len(TTS_VOICES)
        self.voice = TTS_VOICES[next_idx]
        return self.get_current_voice_name()

    def __del__(self):
        """Clean up pyaudio on destruction."""
        if self._audio:
            try:
                self._audio.terminate()
            except:
                pass


# Global TTS instance
_tts_instance: Optional[TTS] = None


def get_tts() -> TTS:
    """Get or create the global TTS instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTS()
    return _tts_instance
