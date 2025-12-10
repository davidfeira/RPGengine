"""
Text-to-Speech module using Windows SAPI for reading game narrative.
"""
import win32com.client
from typing import Optional
import re


class TTS:
    """Lightweight TTS wrapper using Windows SAPI."""

    def __init__(self):
        self.speaker = None
        self.enabled = False
        self.rate = 0  # SAPI uses -10 to 10 scale
        self.voices = None
        self.current_voice_index = 0
        self._init_engine()

    def _init_engine(self):
        """Initialize the SAPI speech engine."""
        try:
            self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
            # Set initial properties
            self.speaker.Rate = self.rate
            self.speaker.Volume = 90  # 0-100 scale

            # Get available voices
            self.voices = self.speaker.GetVoices()
            if self.voices.Count > 0:
                self.speaker.Voice = self.voices.Item(0)
        except Exception as e:
            print(f"Warning: Could not initialize TTS: {e}")
            self.speaker = None

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
        if not self.enabled or not self.speaker:
            return

        # Clean the text
        clean_text = self._clean_text(text)

        if not clean_text:
            return

        if interrupt:
            # Purge any existing speech immediately
            # Flags: 1=Async, 2=PurgeBeforeSpeak
            self.speaker.Speak("", 1 | 2)

        # Speak with flags
        if blocking:
            self.speaker.Speak(clean_text, 0)  # Synchronous (0)
        else:
            self.speaker.Speak(clean_text, 1)  # Asynchronous (1)

    def stop(self):
        """Stop current speech immediately."""
        if self.speaker:
            # Immediate stop with queue purge
            # Flags: 1=Async, 2=PurgeBeforeSpeak
            self.speaker.Speak("", 1 | 2)

    def adjust_speed(self, delta: int) -> int:
        """
        Adjust TTS speed by delta. Returns new rate for display.

        Args:
            delta: Amount to change speed (positive = faster, negative = slower)

        Returns:
            New speed rate in display scale (100-300)
        """
        if not self.speaker:
            return self._sapi_to_display(self.rate)

        # Convert delta from our 25-unit steps to SAPI's 1-unit steps
        # Our scale: 100-300 (delta ±25) -> SAPI scale: -10 to 10 (delta ±1)
        sapi_delta = delta // 25

        # Clamp rate between -10 (slow) and 10 (fast)
        self.rate = max(-10, min(10, self.rate + sapi_delta))
        self.speaker.Rate = self.rate

        return self._sapi_to_display(self.rate)

    def get_speed(self) -> int:
        """Get current TTS speed rate in display scale (100-300)."""
        return self._sapi_to_display(self.rate)

    def _sapi_to_display(self, sapi_rate: int) -> int:
        """Convert SAPI rate (-10 to 10) to display rate (100-300)."""
        # Map -10 to 100, 0 to 200, 10 to 300
        return 200 + (sapi_rate * 10)

    def get_voices(self) -> list:
        """Get list of available voices."""
        if not self.voices:
            return []
        return [self.voices.Item(i) for i in range(self.voices.Count)]

    def get_current_voice_name(self) -> str:
        """Get the name of the current voice."""
        if not self.voices or self.voices.Count == 0:
            return "None"
        try:
            voice = self.voices.Item(self.current_voice_index)
            # Get description and strip extra info
            desc = voice.GetDescription()
            # Usually format is "Name - Extra info", we just want the name
            return desc.split(' - ')[0] if ' - ' in desc else desc
        except:
            return "Unknown"

    def cycle_voice(self) -> str:
        """
        Cycle to the next available voice. Returns the new voice name.
        """
        if not self.speaker or not self.voices or self.voices.Count == 0:
            return "None"

        self.current_voice_index = (self.current_voice_index + 1) % self.voices.Count
        self.speaker.Voice = self.voices.Item(self.current_voice_index)

        return self.get_current_voice_name()


# Global TTS instance
_tts_instance: Optional[TTS] = None


def get_tts() -> TTS:
    """Get or create the global TTS instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTS()
    return _tts_instance
