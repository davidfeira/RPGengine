"""
Text-to-Speech module using pyttsx3 for reading game narrative.
"""
import pyttsx3
import threading
from typing import Optional
import re


class TTS:
    """Lightweight TTS wrapper using pyttsx3."""

    def __init__(self):
        self.engine: Optional[pyttsx3.Engine] = None
        self.enabled = False
        self.rate = 175  # Track current rate
        self.voices = []  # Available voices
        self.current_voice_index = 0  # Track current voice
        self._lock = threading.Lock()
        self._speech_id = 0  # Unique ID for each speech session
        self._current_speech_id = 0  # ID of currently allowed speech
        self._init_engine()

    def _init_engine(self):
        """Initialize the TTS engine."""
        try:
            self.engine = pyttsx3.init()
            # Set properties for better performance
            self.engine.setProperty('rate', self.rate)  # Speed (default is ~200)
            self.engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)

            # Get available voices
            self.voices = self.engine.getProperty('voices')
            if self.voices:
                self.engine.setProperty('voice', self.voices[0].id)
        except Exception as e:
            print(f"Warning: Could not initialize TTS: {e}")
            self.engine = None

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

    def speak(self, text: str, blocking: bool = False, interrupt: bool = True):
        """
        Speak the given text.

        Args:
            text: The text to speak
            blocking: If True, wait for speech to complete. If False, return immediately.
            interrupt: If True, stop any current speech before starting new speech.
        """
        if not self.enabled or not self.engine:
            return

        # Clean the text
        clean_text = self._clean_text(text)

        if not clean_text:
            return

        # Assign a unique ID to this speech session
        self._speech_id += 1
        my_speech_id = self._speech_id

        # If interrupting, update the current allowed speech ID
        if interrupt:
            self._current_speech_id = my_speech_id

        if blocking:
            # Block until speech completes
            if my_speech_id != self._current_speech_id:
                return
            try:
                # Create a fresh engine for this speech to avoid state issues
                temp_engine = pyttsx3.init()
                temp_engine.setProperty('rate', self.rate)
                if self.voices and self.current_voice_index < len(self.voices):
                    temp_engine.setProperty('voice', self.voices[self.current_voice_index].id)
                temp_engine.say(clean_text)
                temp_engine.runAndWait()
                del temp_engine
            except Exception as e:
                pass
        else:
            # Speak in background thread
            def _speak():
                # Only speak if this is the current allowed speech
                if my_speech_id != self._current_speech_id:
                    return
                try:
                    # Create a fresh engine for this speech to avoid state issues
                    temp_engine = pyttsx3.init()
                    temp_engine.setProperty('rate', self.rate)
                    if self.voices and self.current_voice_index < len(self.voices):
                        temp_engine.setProperty('voice', self.voices[self.current_voice_index].id)
                    temp_engine.say(clean_text)
                    temp_engine.runAndWait()
                    del temp_engine
                except Exception as e:
                    pass

            thread = threading.Thread(target=_speak, daemon=True)
            thread.start()

    def stop(self):
        """Stop current speech."""
        # Invalidate all current speech by incrementing the ID
        # Any running threads will see their ID doesn't match and exit
        self._speech_id += 1
        self._current_speech_id = self._speech_id

    def adjust_speed(self, delta: int) -> int:
        """
        Adjust TTS speed by delta. Returns new rate.

        Args:
            delta: Amount to change speed (positive = faster, negative = slower)

        Returns:
            New speed rate
        """
        # Clamp rate between 100 (slow) and 300 (very fast)
        self.rate = max(100, min(300, self.rate + delta))
        return self.rate

    def get_speed(self) -> int:
        """Get current TTS speed rate."""
        return self.rate

    def get_voices(self) -> list:
        """Get list of available voices."""
        return self.voices

    def get_current_voice_name(self) -> str:
        """Get the name of the current voice."""
        if not self.voices:
            return "None"
        return self.voices[self.current_voice_index].name.split(' - ')[0]

    def cycle_voice(self) -> str:
        """
        Cycle to the next available voice. Returns the new voice name.
        """
        if not self.voices:
            return "None"

        self.current_voice_index = (self.current_voice_index + 1) % len(self.voices)
        return self.get_current_voice_name()


# Global TTS instance
_tts_instance: Optional[TTS] = None


def get_tts() -> TTS:
    """Get or create the global TTS instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTS()
    return _tts_instance
