"""
Configuration management for RPG Engine settings.
Persists settings to a JSON file.
"""
import json
import os
from pathlib import Path
from typing import Optional

# Config file location (in user's home directory)
CONFIG_DIR = Path.home() / ".rpgengine"
CONFIG_FILE = CONFIG_DIR / "settings.json"

# Available models for each task type
# Curated list of recommended models (not exhaustive)
LLM_MODELS = [
    # GPT-5.x series (latest)
    "gpt-5.1",
    "gpt-5",
    "gpt-5-pro",
    "gpt-5-mini",
    "gpt-5-nano",
    # GPT-4.x series
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    # Reasoning models
    "o4-mini",
    "o3",
    "o3-mini",
    "o1",
    "o1-pro",
    # Legacy
    "gpt-3.5-turbo",
]

TTS_MODELS = [
    "tts-1",
    "tts-1-hd",
    "gpt-4o-mini-tts",
]

TTS_VOICES = [
    "onyx",
    "fable",
    "nova",
    "alloy",
    "echo",
    "shimmer",
]

# Default settings
DEFAULTS = {
    "narrator_model": "gpt-4o-mini",
    "interpreter_model": "gpt-4o-mini",
    "suggestions_model": "gpt-4o-mini",
    "tts_enabled": True,
    "tts_model": "tts-1",
    "tts_voice": "onyx",
    "tts_speed": 1.0,  # OpenAI scale: 0.25-4.0
}


class Config:
    """Manages application settings with JSON persistence."""

    _instance: Optional["Config"] = None

    def __init__(self):
        self._settings = DEFAULTS.copy()
        self._session_tokens = {"prompt": 0, "completion": 0}
        self._session_tts_chars = 0
        self._load()

    @classmethod
    def get(cls) -> "Config":
        """Get the singleton config instance."""
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

    def _load(self):
        """Load settings from disk."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                # Merge with defaults (in case new settings were added)
                for key, value in saved.items():
                    if key in DEFAULTS:
                        self._settings[key] = value
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config: {e}")

    def save(self):
        """Save current settings to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._settings, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")

    # Narrator model
    @property
    def narrator_model(self) -> str:
        return self._settings["narrator_model"]

    @narrator_model.setter
    def narrator_model(self, value: str):
        self._settings["narrator_model"] = value
        self.save()

    # Interpreter model
    @property
    def interpreter_model(self) -> str:
        return self._settings["interpreter_model"]

    @interpreter_model.setter
    def interpreter_model(self, value: str):
        self._settings["interpreter_model"] = value
        self.save()

    # Suggestions model
    @property
    def suggestions_model(self) -> str:
        return self._settings.get("suggestions_model", self._settings["narrator_model"])

    @suggestions_model.setter
    def suggestions_model(self, value: str):
        self._settings["suggestions_model"] = value
        self.save()

    # TTS enabled
    @property
    def tts_enabled(self) -> bool:
        return self._settings["tts_enabled"]

    @tts_enabled.setter
    def tts_enabled(self, value: bool):
        self._settings["tts_enabled"] = value
        self.save()

    # TTS model
    @property
    def tts_model(self) -> str:
        return self._settings["tts_model"]

    @tts_model.setter
    def tts_model(self, value: str):
        self._settings["tts_model"] = value
        self.save()

    # TTS voice
    @property
    def tts_voice(self) -> str:
        return self._settings["tts_voice"]

    @tts_voice.setter
    def tts_voice(self, value: str):
        self._settings["tts_voice"] = value
        self.save()

    # TTS speed (OpenAI scale: 0.25-4.0)
    @property
    def tts_speed(self) -> float:
        return self._settings["tts_speed"]

    @tts_speed.setter
    def tts_speed(self, value: float):
        self._settings["tts_speed"] = max(0.25, min(4.0, value))
        self.save()

    # Session token tracking (not persisted - resets each run)
    def add_tokens(self, prompt: int, completion: int):
        """Add tokens from an API call to the session total."""
        self._session_tokens["prompt"] += prompt
        self._session_tokens["completion"] += completion

    def add_tts_chars(self, chars: int):
        """Add TTS characters to the session total."""
        self._session_tts_chars += chars

    def get_session_tokens(self) -> dict:
        """Get the current session token counts."""
        return self._session_tokens.copy()

    def get_session_cost(self) -> float:
        """Calculate approximate session cost based on token and TTS usage.

        Prices per 1M tokens (from OpenAI pricing docs Dec 2025):
        """
        # LLM pricing per 1M tokens: (input, output)
        llm_prices = {
            # GPT-5.x series
            "gpt-5.1": (1.25, 10.00),
            "gpt-5": (1.25, 10.00),
            "gpt-5-pro": (15.00, 120.00),
            "gpt-5-mini": (0.25, 2.00),
            "gpt-5-nano": (0.05, 0.40),
            # GPT-4.1 series
            "gpt-4.1": (2.00, 8.00),
            "gpt-4.1-mini": (0.40, 1.60),
            "gpt-4.1-nano": (0.10, 0.40),
            # GPT-4o series
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            # Reasoning models
            "o4-mini": (1.10, 4.40),
            "o3": (2.00, 8.00),
            "o3-mini": (1.10, 4.40),
            "o1": (15.00, 60.00),
            "o1-pro": (150.00, 600.00),
            # Legacy
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-4": (30.00, 60.00),
            "gpt-3.5-turbo": (0.50, 1.50),
        }

        # Get price for current narrator model (used for most calls)
        input_price, output_price = llm_prices.get(self.narrator_model, (0.15, 0.60))
        prompt_cost = self._session_tokens["prompt"] / 1_000_000 * input_price
        completion_cost = self._session_tokens["completion"] / 1_000_000 * output_price

        # TTS pricing per 1M characters
        tts_prices = {
            "tts-1": 15.0,
            "tts-1-hd": 30.0,
            "gpt-4o-mini-tts": 12.0,  # $12/1M audio output tokens (~$0.015/min)
        }
        tts_price = tts_prices.get(self.tts_model, 15.0)
        tts_cost = self._session_tts_chars / 1_000_000 * tts_price

        return prompt_cost + completion_cost + tts_cost

    def reset_session_tokens(self):
        """Reset the session token counters."""
        self._session_tokens = {"prompt": 0, "completion": 0}
        self._session_tts_chars = 0


def get_config() -> Config:
    """Convenience function to get the config singleton."""
    return Config.get()
