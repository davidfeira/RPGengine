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

# TTS engines available
TTS_ENGINES = ["openai", "edge"]

# Image generation models (sd-1.5 is local/free, gpt-image-1-mini is cheapest API)
IMAGE_MODELS = ["sd-1.5 (local)", "gpt-image-1-mini", "gpt-image-1", "dall-e-3", "dall-e-2"]

# Image quality options
IMAGE_QUALITIES = ["low", "medium", "high"]

# Local SD resolution options (width x height)
LOCAL_RESOLUTIONS = ["512x512", "512x768", "768x512", "768x768"]

# Local SD guidance scale presets
LOCAL_GUIDANCE = ["low (5)", "medium (7.5)", "high (10)", "very high (15)"]

# Default image styles
IMAGE_STYLES = [
    "fantasy illustration, detailed",
    "dark fantasy art, moody",
    "pixel art, retro game style",
    "watercolor painting",
    "comic book style",
    "oil painting, classical",
    "anime style",
    "realistic, photographic",
]

# Edge TTS voices (curated list of good narrator voices)
EDGE_VOICES = [
    "en-US-GuyNeural",           # Male, casual
    "en-US-ChristopherNeural",   # Male, formal
    "en-US-EricNeural",          # Male, warm
    "en-US-AndrewNeural",        # Male, expressive
    "en-US-JennyNeural",         # Female, casual
    "en-US-AriaNeural",          # Female, professional
    "en-US-SaraNeural",          # Female, warm
    "en-US-MichelleNeural",      # Female, expressive
    "en-GB-RyanNeural",          # British male
    "en-GB-SoniaNeural",         # British female
]

# Default settings
DEFAULTS = {
    "narrator_model": "gpt-4o-mini",
    "interpreter_model": "gpt-4o-mini",
    "suggestions_model": "gpt-4o-mini",
    "tts_enabled": True,
    "tts_engine": "openai",  # "openai" or "edge"
    "tts_model": "tts-1",
    "tts_voice": "onyx",
    "tts_speed": 1.0,  # OpenAI scale: 0.25-4.0
    "edge_voice": "en-US-GuyNeural",  # Edge TTS voice
    # Image generation settings
    "image_enabled": False,  # Disabled by default
    "image_model": "dall-e-3",
    "image_quality": "low",  # low = $0.01/image
    "image_style": "fantasy illustration, detailed",
    # Local SD settings
    "local_resolution": "512x512",
    "local_guidance": "medium (7.5)",
    "local_negative_prompt": "blurry, bad anatomy, ugly, deformed",
}


class Config:
    """Manages application settings with JSON persistence."""

    _instance: Optional["Config"] = None

    def __init__(self):
        self._settings = DEFAULTS.copy()
        # Track tokens per task type for accurate cost calculation
        self._session_tokens = {
            "narrator": {"prompt": 0, "completion": 0},
            "interpreter": {"prompt": 0, "completion": 0},
            "suggestions": {"prompt": 0, "completion": 0},
        }
        self._session_tts_chars = 0
        self._session_images = 0
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

    # TTS engine
    @property
    def tts_engine(self) -> str:
        return self._settings.get("tts_engine", "openai")

    @tts_engine.setter
    def tts_engine(self, value: str):
        self._settings["tts_engine"] = value
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

    # Edge TTS voice
    @property
    def edge_voice(self) -> str:
        return self._settings.get("edge_voice", "en-US-GuyNeural")

    @edge_voice.setter
    def edge_voice(self, value: str):
        self._settings["edge_voice"] = value
        self.save()

    # Image generation enabled
    @property
    def image_enabled(self) -> bool:
        return self._settings.get("image_enabled", False)

    @image_enabled.setter
    def image_enabled(self, value: bool):
        self._settings["image_enabled"] = value
        self.save()

    # Image model
    @property
    def image_model(self) -> str:
        return self._settings.get("image_model", "dall-e-3")

    @image_model.setter
    def image_model(self, value: str):
        self._settings["image_model"] = value
        self.save()

    # Image quality
    @property
    def image_quality(self) -> str:
        return self._settings.get("image_quality", "low")

    @image_quality.setter
    def image_quality(self, value: str):
        self._settings["image_quality"] = value
        self.save()

    # Image style
    @property
    def image_style(self) -> str:
        return self._settings.get("image_style", "fantasy illustration, detailed")

    @image_style.setter
    def image_style(self, value: str):
        self._settings["image_style"] = value
        self.save()

    # Local SD resolution
    @property
    def local_resolution(self) -> str:
        return self._settings.get("local_resolution", "512x512")

    @local_resolution.setter
    def local_resolution(self, value: str):
        self._settings["local_resolution"] = value
        self.save()

    # Local SD guidance scale
    @property
    def local_guidance(self) -> str:
        return self._settings.get("local_guidance", "medium (7.5)")

    @local_guidance.setter
    def local_guidance(self, value: str):
        self._settings["local_guidance"] = value
        self.save()

    # Local SD negative prompt
    @property
    def local_negative_prompt(self) -> str:
        return self._settings.get("local_negative_prompt", "blurry, bad anatomy, ugly, deformed")

    @local_negative_prompt.setter
    def local_negative_prompt(self, value: str):
        self._settings["local_negative_prompt"] = value
        self.save()

    # Session token tracking (not persisted - resets each run)
    def add_tokens(self, prompt: int, completion: int, task: str = "narrator"):
        """Add tokens from an API call to the session total.

        Args:
            prompt: Number of prompt tokens used
            completion: Number of completion tokens used
            task: "narrator", "interpreter", or "suggestions"
        """
        if task not in self._session_tokens:
            task = "narrator"
        self._session_tokens[task]["prompt"] += prompt
        self._session_tokens[task]["completion"] += completion

    def add_tts_chars(self, chars: int):
        """Add TTS characters to the session total."""
        self._session_tts_chars += chars

    def add_image(self):
        """Add one image generation to the session total."""
        self._session_images += 1

    def get_session_images(self) -> int:
        """Get the current session image count."""
        return self._session_images

    def get_session_tokens(self) -> dict:
        """Get the current session token counts by task type."""
        return {
            task: counts.copy()
            for task, counts in self._session_tokens.items()
        }

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

        # Calculate cost for each task type using its configured model
        llm_cost = 0.0
        task_models = {
            "narrator": self.narrator_model,
            "interpreter": self.interpreter_model,
            "suggestions": self.suggestions_model,
        }
        for task, model in task_models.items():
            tokens = self._session_tokens[task]
            input_price, output_price = llm_prices.get(model, (0.15, 0.60))
            llm_cost += tokens["prompt"] / 1_000_000 * input_price
            llm_cost += tokens["completion"] / 1_000_000 * output_price

        # TTS pricing per 1M characters (Edge TTS is free)
        if self.tts_engine == "edge":
            tts_cost = 0.0
        else:
            tts_prices = {
                "tts-1": 15.0,
                "tts-1-hd": 30.0,
                "gpt-4o-mini-tts": 12.0,
            }
            tts_price = tts_prices.get(self.tts_model, 15.0)
            tts_cost = self._session_tts_chars / 1_000_000 * tts_price

        # Image generation pricing per image (square 1024x1024)
        # Local models (sd-1.5) are free
        if "local" in self.image_model.lower():
            image_cost = 0.0
        else:
            image_prices = {
                "gpt-image-1-mini": {"low": 0.001, "medium": 0.003, "high": 0.013},
                "gpt-image-1": {"low": 0.01, "medium": 0.04, "high": 0.17},
                "dall-e-3": {"low": 0.04, "medium": 0.08, "high": 0.12},
                "dall-e-2": {"low": 0.02, "medium": 0.02, "high": 0.02},
            }
            model_prices = image_prices.get(self.image_model, {"low": 0.01, "medium": 0.04, "high": 0.17})
            image_price = model_prices.get(self.image_quality, 0.01)
            image_cost = self._session_images * image_price

        return llm_cost + tts_cost + image_cost

    def reset_session_tokens(self):
        """Reset the session token counters."""
        self._session_tokens = {
            "narrator": {"prompt": 0, "completion": 0},
            "interpreter": {"prompt": 0, "completion": 0},
            "suggestions": {"prompt": 0, "completion": 0},
        }
        self._session_tts_chars = 0
        self._session_images = 0


def get_config() -> Config:
    """Convenience function to get the config singleton."""
    return Config.get()
