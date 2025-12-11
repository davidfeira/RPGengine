"""
Text-to-Speech module supporting multiple engines:
- OpenAI TTS (paid, low latency)
- Edge TTS (free, Microsoft neural voices)
"""
import asyncio
import io
import re
import threading
from typing import Optional

import pyaudio
from openai import OpenAI

from config import get_config, TTS_VOICES, EDGE_VOICES


class OpenAITTS:
    """TTS using OpenAI's text-to-speech API with streaming."""

    def __init__(self, audio: pyaudio.PyAudio):
        self.client = None
        self._audio = audio
        self._stream = None
        self._stream_lock = threading.Lock()
        self._stop_flag = threading.Event()
        self._config = get_config()
        self._init_client()

    def _init_client(self):
        """Initialize the OpenAI client."""
        try:
            self.client = OpenAI()
        except Exception as e:
            print(f"Warning: Could not initialize OpenAI TTS: {e}")
            self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def stream_and_play(self, text: str, stop_flag: threading.Event):
        """Stream speech from OpenAI and play it."""
        if not self.client or not self._audio:
            return

        stream = None
        try:
            config = self._config
            with self.client.audio.speech.with_streaming_response.create(
                model=config.tts_model,
                voice=config.tts_voice,
                input=text,
                speed=config.tts_speed,
                response_format="pcm"
            ) as response:
                if stop_flag.is_set():
                    return

                with self._stream_lock:
                    stream = self._audio.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=24000,
                        output=True,
                        frames_per_buffer=1024
                    )
                    self._stream = stream

                for chunk in response.iter_bytes(chunk_size=4096):
                    if stop_flag.is_set():
                        break
                    if chunk and stream:
                        try:
                            stream.write(chunk)
                        except OSError:
                            break

        except Exception as e:
            if not stop_flag.is_set():
                print(f"OpenAI TTS error: {e}")
        finally:
            with self._stream_lock:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass
                self._stream = None

    def stop(self):
        """Stop current playback."""
        with self._stream_lock:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except:
                    pass
                self._stream = None


class EdgeTTSEngine:
    """TTS using Microsoft Edge's free neural voices."""

    def __init__(self, audio: pyaudio.PyAudio):
        self._audio = audio
        self._stream = None
        self._stream_lock = threading.Lock()
        self._config = get_config()
        self._edge_tts = None
        self._init_edge()

    def _init_edge(self):
        """Try to import edge-tts."""
        try:
            import edge_tts
            self._edge_tts = edge_tts
        except ImportError:
            print("Warning: edge-tts not installed. Run: pip install edge-tts")
            self._edge_tts = None

    def is_available(self) -> bool:
        return self._edge_tts is not None

    def _speed_to_edge_rate(self) -> str:
        """Convert speed (0.5-1.5) to Edge TTS rate string."""
        # Edge TTS uses percentage: -50% to +100%
        # 0.5 -> -50%, 1.0 -> +0%, 1.5 -> +50%
        speed = self._config.tts_speed
        percent = int((speed - 1.0) * 100)
        if percent >= 0:
            return f"+{percent}%"
        return f"{percent}%"

    def stream_and_play(self, text: str, stop_flag: threading.Event):
        """Generate audio using Edge TTS and play it."""
        if not self._edge_tts or not self._audio:
            return

        try:
            # Run async code in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                audio_data = loop.run_until_complete(
                    self._generate_audio(text, stop_flag)
                )
            finally:
                loop.close()

            if stop_flag.is_set() or not audio_data:
                return

            # Play the audio (MP3 format from Edge TTS)
            self._play_mp3(audio_data, stop_flag)

        except Exception as e:
            if not stop_flag.is_set():
                print(f"Edge TTS error: {e}")

    async def _generate_audio(self, text: str, stop_flag: threading.Event) -> bytes:
        """Generate audio data using edge-tts."""
        communicate = self._edge_tts.Communicate(
            text=text,
            voice=self._config.edge_voice,
            rate=self._speed_to_edge_rate()
        )

        audio_data = b""
        async for chunk in communicate.stream():
            if stop_flag.is_set():
                return b""
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        return audio_data

    def _play_mp3(self, mp3_data: bytes, stop_flag: threading.Event):
        """Play MP3 audio data using miniaudio for decoding."""
        try:
            import miniaudio
        except ImportError:
            print("Edge TTS requires miniaudio. Run: pip install miniaudio")
            return

        stream = None
        try:
            # Decode MP3 to raw PCM using miniaudio
            decoded = miniaudio.decode(mp3_data)
            raw_data = decoded.samples.tobytes()
            sample_rate = decoded.sample_rate
            channels = decoded.nchannels

            if stop_flag.is_set():
                return

            # Play through pyaudio
            with self._stream_lock:
                stream = self._audio.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    output=True,
                    frames_per_buffer=1024
                )
                self._stream = stream

            # Play in chunks
            chunk_size = 4096
            for i in range(0, len(raw_data), chunk_size):
                if stop_flag.is_set():
                    break
                chunk = raw_data[i:i + chunk_size]
                try:
                    stream.write(chunk)
                except OSError:
                    break

        except Exception as e:
            if not stop_flag.is_set():
                print(f"Edge TTS playback error: {e}")
        finally:
            with self._stream_lock:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass
                self._stream = None

    def stop(self):
        """Stop current playback."""
        with self._stream_lock:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except:
                    pass
                self._stream = None


class TTS:
    """TTS wrapper that delegates to the appropriate engine based on config."""

    def __init__(self):
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._audio = None
        self._config = get_config()

        # Initialize pyaudio
        try:
            self._audio = pyaudio.PyAudio()
        except Exception as e:
            print(f"Warning: Could not initialize audio: {e}")

        # Initialize engines
        self._openai = OpenAITTS(self._audio) if self._audio else None
        self._edge = EdgeTTSEngine(self._audio) if self._audio else None

    def _get_engine(self):
        """Get the currently selected TTS engine."""
        if self._config.tts_engine == "edge":
            return self._edge
        return self._openai

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

    @property
    def engine(self) -> str:
        return self._config.tts_engine

    @engine.setter
    def engine(self, value: str):
        self._config.tts_engine = value

    def toggle(self) -> bool:
        """Toggle TTS on/off. Returns new state."""
        self.enabled = not self.enabled
        return self.enabled

    def set_enabled(self, enabled: bool):
        """Set TTS enabled state."""
        self.enabled = enabled

    def _clean_text(self, text: str) -> str:
        """Remove Rich markup and clean text for TTS."""
        text = re.sub(r'\[/?[^\]]+\]', '', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def speak(self, text: str, blocking: bool = False, interrupt: bool = True):
        """
        Speak the given text.

        Args:
            text: The text to speak
            blocking: If True, wait for speech to complete
            interrupt: If True, stop any current speech first
        """
        engine = self._get_engine()
        if not self.enabled or not engine or not engine.is_available():
            return

        clean_text = self._clean_text(text)
        if not clean_text:
            return

        # Track TTS character usage (only for OpenAI - Edge is free)
        if self._config.tts_engine == "openai":
            self._config.add_tts_chars(len(clean_text))

        if interrupt:
            self.stop()

        self._stop_flag.clear()

        if blocking:
            engine.stream_and_play(clean_text, self._stop_flag)
        else:
            self._playback_thread = threading.Thread(
                target=engine.stream_and_play,
                args=(clean_text, self._stop_flag),
                daemon=True
            )
            self._playback_thread.start()

    def stop(self):
        """Stop current speech immediately."""
        self._stop_flag.set()

        # Stop both engines (whichever is playing)
        if self._openai:
            self._openai.stop()
        if self._edge:
            self._edge.stop()

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=0.5)

    def adjust_speed(self, delta: int) -> int:
        """Adjust TTS speed. Returns new rate in display scale (100-300)."""
        openai_delta = delta / 200
        self.speed = max(0.5, min(1.5, self.speed + openai_delta))
        return self._speed_to_display()

    def get_speed(self) -> int:
        """Get current TTS speed rate in display scale (100-300)."""
        return self._speed_to_display()

    def _speed_to_display(self) -> int:
        """Convert speed (0.5-1.5) to display rate (100-300)."""
        return int(self.speed * 200)

    def get_voices(self) -> list:
        """Get list of available voices for current engine."""
        if self._config.tts_engine == "edge":
            return EDGE_VOICES.copy()
        return TTS_VOICES.copy()

    def get_current_voice_name(self) -> str:
        """Get the name of the current voice."""
        if self._config.tts_engine == "edge":
            # Return just the voice name part (e.g., "Guy" from "en-US-GuyNeural")
            voice = self._config.edge_voice
            if "-" in voice:
                parts = voice.split("-")
                if len(parts) >= 3:
                    return parts[2].replace("Neural", "")
            return voice
        return self.voice.capitalize()

    def set_voice(self, voice: str):
        """Set the current voice."""
        if self._config.tts_engine == "edge":
            if voice in EDGE_VOICES:
                self._config.edge_voice = voice
        else:
            if voice.lower() in TTS_VOICES:
                self.voice = voice.lower()

    def cycle_voice(self) -> str:
        """Cycle to the next available voice. Returns the new voice name."""
        voices = self.get_voices()
        if self._config.tts_engine == "edge":
            current = self._config.edge_voice
            try:
                idx = voices.index(current)
            except ValueError:
                idx = 0
            next_idx = (idx + 1) % len(voices)
            self._config.edge_voice = voices[next_idx]
        else:
            try:
                idx = TTS_VOICES.index(self.voice)
            except ValueError:
                idx = 0
            next_idx = (idx + 1) % len(TTS_VOICES)
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
