from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer, Container, Center
from textual.widgets import Static, Input, Button, Select, Switch
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
import random
import json
import os
import logging
import asyncio
from io import BytesIO
from openai import OpenAI
from prompts import INTERPRETER_PROMPT, NARRATOR_PROMPT, SETUP_PROMPT, SUGGESTIONS_PROMPT, IMAGE_SUBJECT_PROMPT
from tts import get_tts
from config import get_config, LLM_MODELS, TTS_MODELS, TTS_VOICES, TTS_ENGINES, EDGE_VOICES, IMAGE_MODELS, IMAGE_QUALITIES, IMAGE_STYLES, LOCAL_RESOLUTIONS, LOCAL_GUIDANCE
from image_gen import generate_scene_image, generate_visual_prompt, preload_local_model, is_local_model_ready, is_local_model, generate_test_image, get_last_error, clear_last_error

# Try to import textual-image for Sixel graphics (full resolution on Windows Terminal 1.22+)
# Windows Terminal has issues with escape sequence detection - pre-fill the cache
IMAGES_AVAILABLE = False
SixelImage = None
HalfcellImage = None
try:
    # Pre-fill the cell size cache to avoid timeout on Windows Terminal
    from textual_image._terminal import get_cell_size, CellSize
    # Set a default cell size (10x20 is VT340 standard) to skip terminal detection
    setattr(get_cell_size, "_result", CellSize(10, 20))

    # Now import the widgets
    from textual_image.widget import SixelImage, HalfcellImage
    IMAGES_AVAILABLE = True
except Exception as e:
    SixelImage = None
    HalfcellImage = None
    # Fallback to rich-pixels if textual-image not available
    try:
        from rich_pixels import Pixels
        IMAGES_AVAILABLE = True
    except ImportError:
        pass

STAT_COLORS = {"mind": "#0af", "body": "#fa0", "spirit": "#f0a"}

# Set up logging
logging.basicConfig(
    filename='rpg_engine.log',
    level=logging.DEBUG,
    format='%(asctime)s │ %(levelname)s │ %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# Deferred client initialization - will be set when API key is provided
client = None

def init_openai_client(api_key: str) -> bool:
    """Initialize OpenAI client with the given API key. Returns True if successful."""
    global client
    try:
        client = OpenAI(api_key=api_key)
        # Test the key with a minimal request
        client.models.list()
        return True
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        client = None
        return False

def get_api_key() -> str | None:
    """Get API key from environment or return None."""
    return os.environ.get("OPENAI_API_KEY")


def roll_check(stat_value: int, difficulty: int) -> tuple[bool, int]:
    roll = random.randint(1, 10)
    result = roll + stat_value - difficulty
    return result > 5, roll


def call_llm(prompt: str, system: str = None, json_mode: bool = False, task: str = "narrator") -> str:
    """Call OpenAI LLM API.

    Args:
        prompt: The user prompt
        system: Optional system prompt
        json_mode: Whether to request JSON response
        task: "narrator", "interpreter", or "suggestions" to select model from config
    """
    config = get_config()
    if task == "interpreter":
        model = config.interpreter_model
    elif task == "suggestions":
        model = config.suggestions_model
    else:
        model = config.narrator_model

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {"model": model, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    logger.debug(f"LLM request ({model}): {prompt[:200]}...")
    try:
        response = client.chat.completions.create(**kwargs)

        # Track token usage by task type
        if response.usage:
            config.add_tokens(response.usage.prompt_tokens, response.usage.completion_tokens, task)

        result = response.choices[0].message.content
        logger.debug(f"LLM response: {result[:200]}...")
        return result
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        raise


def interpret_action(action: str, context: str) -> dict:
    prompt = f"Context: {context}\n\nPlayer action: {action}"
    response = call_llm(prompt, system=INTERPRETER_PROMPT, json_mode=True, task="interpreter")

    try:
        result = json.loads(response)
        if not result.get("valid", True):
            logger.info(f"Invalid action: {action} - {result.get('reason')}")
            return {"valid": False, "reason": result.get("reason", "That's not possible.")}
        if result.get("stat") not in ["mind", "body", "spirit"]:
            result["stat"] = "body"
        result["difficulty"] = max(1, min(5, int(result.get("difficulty", 3))))
        result["lethal"] = result.get("lethal", False)
        result["valid"] = True
        logger.info(f"Action interpreted: {action} -> {result['stat']} diff {result['difficulty']} lethal={result['lethal']}")
        return result
    except Exception as e:
        logger.error(f"Failed to parse interpreter response: {e}")
        return {"valid": True, "stat": "body", "difficulty": 3, "lethal": False}


def narrate(context: str, character: str, stats: dict, action: str,
            stat: str, difficulty: int, success: bool, died: bool = False,
            forced: bool = False) -> str:
    if died:
        outcome = "DEATH"
        special_note = "THIS IS A DEATH SCENE. The character dies here."
    elif forced and success:
        outcome = "MIRACULOUS"
        special_note = "THIS WAS A FORCED IMPOSSIBLE ACTION THAT SUCCEEDED. Reality bent to the character's will. Narrate this as supernatural, absurd, or cosmically lucky."
    elif forced and not success:
        outcome = "FAILURE"
        special_note = "The character attempted the impossible and failed. Reality reasserted itself."
    else:
        outcome = "SUCCESS" if success else "FAILURE"
        special_note = ""

    prompt = NARRATOR_PROMPT.format(
        context=context, character=character,
        mind=stats["mind"], body=stats["body"], spirit=stats["spirit"],
        action=action, stat=stat, difficulty=difficulty,
        outcome=outcome, special_note=special_note
    )
    return call_llm(prompt)


STORY_TONES = [
    "mystery",
    "adventure",
    "drama",
    "comedy",
    "romance",
    "horror",
    "slice of life",
]


def opening_scene(character: str, stats: dict) -> str:
    prompt = SETUP_PROMPT.format(
        character=character,
        mind=stats["mind"], body=stats["body"], spirit=stats["spirit"]
    )
    return call_llm(prompt)


def generate_suggestions(character: str, narrative: str) -> list[str]:
    """Generate 3 action suggestions for the current situation."""
    prompt = SUGGESTIONS_PROMPT.format(
        character=character,
        narrative=narrative
    )

    try:
        response = call_llm(prompt, json_mode=True, task="suggestions")
        logger.debug(f"Suggestions response: {response}")

        data = json.loads(response)

        # Handle both direct array and wrapped object formats
        if isinstance(data, list) and len(data) == 3:
            logger.info(f"Generated suggestions: {data}")
            return data
        elif isinstance(data, dict):
            # Try common wrapper keys
            for key in ['actions', 'suggestions', 'options']:
                if key in data and isinstance(data[key], list) and len(data[key]) == 3:
                    logger.info(f"Generated suggestions: {data[key]}")
                    return data[key]

        logger.warning(f"Invalid suggestions format: {data}")
        return ["Continue forward", "Look around carefully", "Wait and observe"]
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return ["Continue forward", "Look around carefully", "Wait and observe"]


IDENTITY_PROMPTS = [
    "Who are you?",
    "What are you?",
    "Where do you come from?",
    "What is your name?",
]


class SettingsScreen(ModalScreen):
    """Modal screen for settings - compact two-column layout."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 100;
        height: auto;
        background: #1a1a2e;
        border: solid #0af;
        padding: 1 2;
    }

    #settings-header {
        height: 3;
        margin-bottom: 1;
    }

    #settings-back-btn {
        width: 8;
        min-width: 8;
        height: 3;
        background: #0f0f23;
        color: #888;
        border: round #444;
    }

    #settings-back-btn:hover {
        background: #16213e;
        border: round #0af;
        color: #0af;
    }

    #settings-title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: #0af;
        padding-top: 1;
    }

    #settings-columns {
        height: auto;
    }

    .settings-column {
        width: 1fr;
        padding: 0 1;
    }

    .settings-section-title {
        color: #fa0;
        text-style: bold;
        margin-bottom: 0;
    }

    .settings-row {
        height: 3;
    }

    .settings-label {
        width: 12;
        padding-top: 1;
    }

    .settings-control {
        width: 1fr;
    }

    .compact-select {
        width: 100%;
    }

    #settings-footer {
        height: auto;
        margin-top: 1;
        border-top: solid #333;
        padding-top: 1;
    }

    #cost-estimate {
        width: 1fr;
        color: #888;
    }

    #settings-close {
        width: 16;
    }

    .speed-btn {
        width: 4;
        min-width: 4;
        height: 3;
    }

    #tts-speed-display {
        width: 6;
        text-align: center;
        padding-top: 1;
    }

    #tts-speed-controls {
        width: 1fr;
    }

    .local-sd-row {
        height: 3;
    }

    #local-negative-input {
        width: 100%;
        height: 3;
        background: #16213e;
        border: round #444;
    }

    #test-image-row {
        height: auto;
        margin-top: 1;
    }

    #test-image-btn {
        width: 14;
        min-width: 14;
    }

    #test-image-result {
        width: 1fr;
        padding-left: 1;
        padding-top: 1;
        color: #888;
    }
    """

    BINDINGS = [
        Binding("escape", "close_settings", "Close"),
    ]

    def on_mount(self) -> None:
        """Initialize UI state based on current config."""
        self._update_model_row_visibility()
        self._update_local_sd_visibility()
        self._update_cost_estimate()

    def compose(self) -> ComposeResult:
        config = get_config()
        tts = get_tts()

        # Build model options
        llm_options = [(m, m) for m in LLM_MODELS]
        tts_model_options = [(m, m) for m in TTS_MODELS]
        engine_options = [("OpenAI", "openai"), ("Edge (free)", "edge")]

        # Voice options depend on engine
        if config.tts_engine == "edge":
            voice_options = [(v.split("-")[2].replace("Neural", ""), v) for v in EDGE_VOICES]
            current_voice = config.edge_voice
        else:
            voice_options = [(v.capitalize(), v) for v in TTS_VOICES]
            current_voice = config.tts_voice

        with Container(id="settings-container"):
            # Header with back button and title
            with Horizontal(id="settings-header"):
                yield Button("← Back", id="settings-back-btn")
                yield Static("⚙ SETTINGS", id="settings-title")

            # Two-column layout
            with Horizontal(id="settings-columns"):
                # LEFT COLUMN: LLM + TTS
                with Vertical(classes="settings-column"):
                    yield Static("LLM Models", classes="settings-section-title")
                    with Horizontal(classes="settings-row"):
                        yield Static("Narrator:", classes="settings-label")
                        yield Select(llm_options, value=config.narrator_model,
                                     id="narrator-model-select", classes="compact-select")
                    with Horizontal(classes="settings-row"):
                        yield Static("Interpreter:", classes="settings-label")
                        yield Select(llm_options, value=config.interpreter_model,
                                     id="interpreter-model-select", classes="compact-select")
                    with Horizontal(classes="settings-row"):
                        yield Static("Suggestions:", classes="settings-label")
                        yield Select(llm_options, value=config.suggestions_model,
                                     id="suggestions-model-select", classes="compact-select")
                    with Horizontal(classes="settings-row"):
                        yield Static("Visual Dir:", classes="settings-label")
                        yield Select(llm_options, value=config.visual_director_model,
                                     id="visual-director-model-select", classes="compact-select")

                    yield Static("Text-to-Speech", classes="settings-section-title")
                    with Horizontal(classes="settings-row"):
                        yield Static("Enabled:", classes="settings-label")
                        yield Switch(value=config.tts_enabled, id="tts-enabled-switch")
                    with Horizontal(classes="settings-row"):
                        yield Static("Engine:", classes="settings-label")
                        yield Select(engine_options, value=config.tts_engine,
                                     id="tts-engine-select", classes="compact-select")
                    with Horizontal(classes="settings-row", id="tts-model-row"):
                        yield Static("Model:", classes="settings-label")
                        yield Select(tts_model_options, value=config.tts_model,
                                     id="tts-model-select", classes="compact-select")
                    with Horizontal(classes="settings-row"):
                        yield Static("Voice:", classes="settings-label")
                        yield Select(voice_options, value=current_voice,
                                     id="tts-voice-select", classes="compact-select")
                    with Horizontal(classes="settings-row"):
                        yield Static("Speed:", classes="settings-label")
                        with Horizontal(id="tts-speed-controls"):
                            yield Button("-", id="settings-tts-slower", classes="speed-btn")
                            yield Static(str(tts.get_speed()), id="tts-speed-display")
                            yield Button("+", id="settings-tts-faster", classes="speed-btn")

                # RIGHT COLUMN: Image Generation + Cost
                with Vertical(classes="settings-column"):
                    yield Static("Image Generation", classes="settings-section-title")
                    with Horizontal(classes="settings-row"):
                        yield Static("Enabled:", classes="settings-label")
                        yield Switch(value=config.image_enabled, id="image-enabled-switch")
                    with Horizontal(classes="settings-row"):
                        yield Static("Model:", classes="settings-label")
                        yield Select([(m, m) for m in IMAGE_MODELS], value=config.image_model,
                                     id="image-model-select", classes="compact-select")
                    with Horizontal(classes="settings-row"):
                        yield Static("Quality:", classes="settings-label")
                        yield Select([(q.capitalize(), q) for q in IMAGE_QUALITIES],
                                     value=config.image_quality,
                                     id="image-quality-select", classes="compact-select")
                    with Horizontal(classes="settings-row"):
                        yield Static("Style:", classes="settings-label")
                        yield Select([(s.split(",")[0], s) for s in IMAGE_STYLES],
                                     value=config.image_style,
                                     id="image-style-select", classes="compact-select")

                    # Local SD settings (only shown when local model selected)
                    yield Static("Local SD Settings", classes="settings-section-title", id="local-sd-title")
                    with Horizontal(classes="settings-row local-sd-row", id="local-resolution-row"):
                        yield Static("Resolution:", classes="settings-label")
                        yield Select([(r, r) for r in LOCAL_RESOLUTIONS],
                                     value=config.local_resolution,
                                     id="local-resolution-select", classes="compact-select")
                    with Horizontal(classes="settings-row local-sd-row", id="local-guidance-row"):
                        yield Static("Guidance:", classes="settings-label")
                        yield Select([(g, g) for g in LOCAL_GUIDANCE],
                                     value=config.local_guidance,
                                     id="local-guidance-select", classes="compact-select")
                    with Horizontal(classes="settings-row local-sd-row", id="local-negative-row"):
                        yield Static("Negative:", classes="settings-label")
                        yield Input(value=config.local_negative_prompt,
                                    placeholder="blurry, bad anatomy...",
                                    id="local-negative-input")
                    with Horizontal(id="test-image-row"):
                        yield Button("Test Image", id="test-image-btn")
                        yield Static("", id="test-image-result")

                    yield Static("Cost Estimate", classes="settings-section-title")
                    yield Static(self._get_cost_estimate(), id="cost-estimate")

            # Footer with close button
            with Horizontal(id="settings-footer"):
                yield Button("Close", id="settings-close", variant="primary")

    def _get_cost_estimate(self) -> str:
        """Calculate estimated cost per message based on current settings."""
        config = get_config()

        # LLM pricing per 1M tokens: (input, output)
        llm_prices = {
            "gpt-5.1": (1.25, 10.00), "gpt-5": (1.25, 10.00),
            "gpt-5-pro": (15.00, 120.00), "gpt-5-mini": (0.25, 2.00),
            "gpt-5-nano": (0.05, 0.40),
            "gpt-4.1": (2.00, 8.00), "gpt-4.1-mini": (0.40, 1.60),
            "gpt-4.1-nano": (0.10, 0.40),
            "gpt-4o": (2.50, 10.00), "gpt-4o-mini": (0.15, 0.60),
            "o4-mini": (1.10, 4.40), "o3": (2.00, 8.00),
            "o3-mini": (1.10, 4.40), "o1": (15.00, 60.00),
            "o1-pro": (150.00, 600.00),
            "gpt-4-turbo": (10.00, 30.00), "gpt-4": (30.00, 60.00),
            "gpt-3.5-turbo": (0.50, 1.50),
        }

        # TTS pricing per 1M characters (Edge is free!)
        tts_prices = {"tts-1": 15.0, "tts-1-hd": 30.0, "gpt-4o-mini-tts": 12.0}

        # Estimated tokens per call (approximations)
        # Narrator: ~500 input, ~150 output
        # Interpreter: ~300 input, ~50 output
        # Suggestions: ~200 input, ~50 output
        # TTS: ~500 characters per response

        narrator_in, narrator_out = llm_prices.get(config.narrator_model, (0.15, 0.60))
        interp_in, interp_out = llm_prices.get(config.interpreter_model, (0.15, 0.60))
        suggest_in, suggest_out = llm_prices.get(config.suggestions_model, (0.15, 0.60))
        visual_in, visual_out = llm_prices.get(config.visual_director_model, (0.15, 0.60))

        # Per-message costs (in dollars)
        narrator_cost = (500 * narrator_in + 150 * narrator_out) / 1_000_000
        interp_cost = (300 * interp_in + 50 * interp_out) / 1_000_000
        suggest_cost = (200 * suggest_in + 50 * suggest_out) / 1_000_000
        # Visual director: ~400 input (prompt + context), ~80 output (image prompt)
        visual_cost = (400 * visual_in + 80 * visual_out) / 1_000_000 if config.image_enabled else 0

        # TTS cost: Edge is free, OpenAI is paid
        if not config.tts_enabled:
            tts_cost = 0
            tts_note = ""
        elif config.tts_engine == "edge":
            tts_cost = 0
            tts_note = " (free)"
        else:
            tts_price = tts_prices.get(config.tts_model, 15.0)
            tts_cost = (500 * tts_price) / 1_000_000
            tts_note = ""

        # Image generation cost per action
        image_prices = {
            "gpt-image-1-mini": {"low": 0.001, "medium": 0.003, "high": 0.013},
            "gpt-image-1": {"low": 0.01, "medium": 0.04, "high": 0.17},
            "dall-e-3": {"low": 0.04, "medium": 0.08, "high": 0.12},
            "dall-e-2": {"low": 0.02, "medium": 0.02, "high": 0.02},
        }
        if not config.image_enabled:
            image_cost = 0
            image_note = ""
        elif "local" in config.image_model.lower():
            image_cost = 0
            image_note = " (free)"
        else:
            model_prices = image_prices.get(config.image_model, {"low": 0.01})
            image_cost = model_prices.get(config.image_quality, 0.01)
            image_note = ""

        total = narrator_cost + interp_cost + suggest_cost + visual_cost + tts_cost + image_cost

        # Visual director note
        visual_note = "" if config.image_enabled else " (off)"

        return (
            f"[dim]Est. per action: [#0f9]${total:.4f}[/]\n"
            f"  Narrator: ${narrator_cost:.5f}\n"
            f"  Interpreter: ${interp_cost:.5f}\n"
            f"  Suggestions: ${suggest_cost:.5f}\n"
            f"  Visual Dir: ${visual_cost:.5f}{visual_note}\n"
            f"  TTS: ${tts_cost:.5f}{tts_note}\n"
            f"  Image: ${image_cost:.2f}{image_note}[/]"
        )

    def _update_cost_estimate(self) -> None:
        """Update the cost estimate display."""
        try:
            cost_display = self.query_one("#cost-estimate", Static)
            cost_display.update(self._get_cost_estimate())
        except:
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle dropdown changes."""
        config = get_config()
        select_id = event.select.id
        value = event.value

        # Ignore blank/empty selections
        if value == Select.BLANK:
            return

        if select_id == "narrator-model-select":
            config.narrator_model = value
            self._update_cost_estimate()
        elif select_id == "interpreter-model-select":
            config.interpreter_model = value
            self._update_cost_estimate()
        elif select_id == "suggestions-model-select":
            config.suggestions_model = value
            self._update_cost_estimate()
        elif select_id == "visual-director-model-select":
            config.visual_director_model = value
            self._update_cost_estimate()
        elif select_id == "tts-engine-select":
            config.tts_engine = value
            self._update_voice_options()
            self._update_model_row_visibility()
            self._update_cost_estimate()
        elif select_id == "tts-model-select":
            config.tts_model = value
            self._update_cost_estimate()
        elif select_id == "tts-voice-select":
            tts = get_tts()
            tts.set_voice(value)
        elif select_id == "image-model-select":
            config.image_model = value
            self._update_local_sd_visibility()
            self._update_cost_estimate()
        elif select_id == "image-quality-select":
            config.image_quality = value
            self._update_cost_estimate()
        elif select_id == "image-style-select":
            config.image_style = value
        elif select_id == "local-resolution-select":
            config.local_resolution = value
        elif select_id == "local-guidance-select":
            config.local_guidance = value

    def _update_voice_options(self) -> None:
        """Update the voice dropdown options based on the selected engine."""
        config = get_config()
        voice_select = self.query_one("#tts-voice-select", Select)

        if config.tts_engine == "edge":
            voice_options = [(v.split("-")[2].replace("Neural", ""), v) for v in EDGE_VOICES]
            current_voice = config.edge_voice
        else:
            voice_options = [(v.capitalize(), v) for v in TTS_VOICES]
            current_voice = config.tts_voice

        voice_select.set_options(voice_options)
        voice_select.value = current_voice

    def _update_model_row_visibility(self) -> None:
        """Show/hide the TTS model row based on engine (only OpenAI has models)."""
        config = get_config()
        try:
            model_row = self.query_one("#tts-model-row", Horizontal)
            if config.tts_engine == "edge":
                model_row.display = False
            else:
                model_row.display = True
        except:
            pass

    def _update_local_sd_visibility(self) -> None:
        """Show/hide local SD settings based on whether a local model is selected."""
        config = get_config()
        show_local = is_local_model(config.image_model)
        try:
            self.query_one("#local-sd-title", Static).display = show_local
            self.query_one("#local-resolution-row", Horizontal).display = show_local
            self.query_one("#local-guidance-row", Horizontal).display = show_local
            self.query_one("#local-negative-row", Horizontal).display = show_local
            self.query_one("#test-image-row", Horizontal).display = show_local
        except:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input field changes."""
        if event.input.id == "local-negative-input":
            config = get_config()
            config.local_negative_prompt = event.value

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch changes."""
        if event.switch.id == "tts-enabled-switch":
            tts = get_tts()
            tts.set_enabled(event.value)
            self._update_cost_estimate()
        elif event.switch.id == "image-enabled-switch":
            config = get_config()
            config.image_enabled = event.value
            self._update_cost_estimate()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "settings-close" or button_id == "settings-back-btn":
            self.app.pop_screen()
        elif button_id == "settings-tts-slower":
            tts = get_tts()
            new_rate = tts.adjust_speed(-25)
            self.query_one("#tts-speed-display", Static).update(str(new_rate))
        elif button_id == "settings-tts-faster":
            tts = get_tts()
            new_rate = tts.adjust_speed(25)
            self.query_one("#tts-speed-display", Static).update(str(new_rate))
        elif button_id == "test-image-btn":
            self.app.run_worker(self._run_test_image(), exclusive=False)

    async def _run_test_image(self) -> None:
        """Run a test image generation and display timing."""
        config = get_config()
        result_label = self.query_one("#test-image-result", Static)
        test_btn = self.query_one("#test-image-btn", Button)

        # Disable button during generation
        test_btn.disabled = True

        # Get settings
        model = config.image_model
        quality = config.image_quality
        resolution = config.local_resolution
        guidance = config.local_guidance
        negative = config.local_negative_prompt

        # Get total steps based on model type
        is_turbo = "sdxl" in model.lower() or "turbo" in model.lower()
        if is_turbo:
            steps_map = {"low": 1, "medium": 2, "high": 4}
            time_per_step = 2.0  # SDXL Turbo is slower per step but fewer steps
        else:
            steps_map = {"low": 10, "medium": 20, "high": 35}
            time_per_step = 0.5
        total_steps = steps_map.get(quality, 2 if is_turbo else 15)

        # Progress tracking
        progress_state = {"step": 0}

        def update_progress(step, _total):
            progress_state["step"] = step

        # Progress updater task
        async def progress_updater():
            while progress_state["step"] < total_steps:
                step = progress_state["step"]
                remaining = total_steps - step
                est_remaining = int(remaining * time_per_step)
                bar_width = 10
                filled = int((step / total_steps) * bar_width) if total_steps > 0 else 0
                bar = "█" * filled + "░" * (bar_width - filled)
                result_label.update(f"[dim]{bar} {step}/{total_steps} (~{est_remaining}s)[/]")
                await asyncio.sleep(0.3)

        progress_task = asyncio.create_task(progress_updater())

        # Run generation in thread pool
        loop = asyncio.get_event_loop()
        image_data, elapsed = await loop.run_in_executor(
            None,
            lambda: generate_test_image(
                model=model,
                quality=quality,
                local_resolution=resolution,
                local_guidance=guidance,
                local_negative_prompt=negative,
                progress_callback=update_progress
            )
        )

        # Cancel progress updater
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass

        # Show result
        if image_data:
            result_label.update(f"[#0f9]✓ {elapsed:.1f}s[/] [dim]({len(image_data)//1024}KB)[/]")
        else:
            result_label.update("[#f00]✗ Failed[/]")

        test_btn.disabled = False

    def action_close_settings(self) -> None:
        """Close settings screen."""
        self.app.pop_screen()


class RPGApp(App):
    CSS = """
    Screen {
        background: #1a1a2e;
    }

    #main-container {
        height: 100%;
        padding: 1 2;
    }

    #main-container.hidden {
        display: none;
    }

    #stats-bar {
        height: 1;
        background: #16213e;
        color: #0f9;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 1;
    }

    #story-row {
        height: 1fr;
        margin-bottom: 1;
    }

    #story-scroll {
        width: 2fr;
        height: 100%;
        border: round #0f9;
        background: #0f0f23;
        padding: 1 2;
    }

    #image-container {
        width: 1fr;
        min-width: 40;
        max-width: 80;
        height: 100%;
        border: round #0af;
        background: #0f0f23;
        margin-left: 1;
        align: center middle;
        overflow: hidden;
    }

    #image-container.hidden {
        display: none;
    }

    #image-placeholder {
        text-align: center;
        color: #444;
    }

    #scene-image {
        width: 100%;
        height: 100%;
    }

    #story-content {
        color: #e0e0e0;
    }

    .player-action {
        width: 100%;
        text-align: right;
        color: #0af;
        text-style: italic;
        margin: 1 0;
    }

    #roll-bar {
        height: auto;
        min-height: 1;
        background: #16213e;
        color: #888;
        padding: 0 1;
        margin-bottom: 1;
    }

    #input-row {
        height: auto;
        align: center middle;
    }

    #action-input {
        width: 1fr;
        height: 3;
        background: #0f0f23;
        border: round #0f9;
        color: #fff;
    }

    #action-input:focus {
        border: round #0f9;
    }

    .suggestion-btn {
        width: 1fr;
        min-width: 20;
        height: 4;
        margin-left: 1;
        background: #0f0f23;
        border: round #444;
        color: #888;
        text-align: left;
        padding: 0 1;
    }

    .suggestion-btn:hover {
        background: #16213e;
        border: round #0af;
        color: #0af;
    }

    .suggestion-btn:focus {
        background: #16213e;
        border: round #0f9;
        color: #0f9;
    }

    Button {
        margin-left: 1;
        min-width: 8;
        height: 3;
    }

    #undo-btn {
        height: 4;
        background: #0f0f23;
        color: #888;
        border: round #444;
    }

    #undo-btn:hover {
        background: #16213e;
        border: round #0af;
        color: #0af;
    }

    #undo-btn:focus {
        background: #16213e;
        border: round #0f9;
        color: #0f9;
    }

    #force-btn {
        height: 4;
        background: #300;
        color: #f66;
        border: round #a00;
    }

    #force-btn:hover {
        background: #400;
        border: round #f00;
        color: #fff;
    }

    #force-btn:focus {
        background: #400;
        border: round #f00;
        color: #fff;
    }

    #force-btn.hidden {
        display: none;
    }

    #settings-btn {
        width: 5;
        min-width: 5;
        height: 4;
        background: #0f0f23;
        color: #888;
        border: round #444;
        padding: 0;
    }

    #settings-btn:hover {
        background: #16213e;
        border: round #0af;
        color: #0af;
    }

    #settings-btn:focus {
        background: #16213e;
        border: round #0f9;
        color: #0f9;
    }

    .dim {
        color: #666;
    }

    .success {
        color: #0f9;
    }

    .failure {
        color: #fa0;
    }

    .death {
        color: #f00;
    }

    .roll-info {
        color: #0af;
    }

    /* Stat allocation screen */
    #stat-screen {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #stat-screen.hidden {
        display: none;
    }

    #stat-container {
        width: 60;
        height: auto;
        background: #0f0f23;
        border: round #0f9;
        padding: 2 3;
    }

    #stat-title {
        text-align: center;
        margin-bottom: 1;
        text-style: bold;
        color: #0f9;
    }

    #char-display {
        text-align: center;
        margin-bottom: 2;
        color: #fff;
    }

    .stat-row {
        height: 3;
        margin: 1 0;
        align: center middle;
    }

    .stat-label {
        width: 8;
        text-style: bold;
    }

    .stat-label.mind { color: #0af; }
    .stat-label.body { color: #fa0; }
    .stat-label.spirit { color: #f0a; }

    .stat-btn {
        width: 3;
        min-width: 3;
        height: 3;
        margin: 0 1;
        border: none;
    }

    .stat-btn-minus {
        background: #600;
        color: #fff;
    }

    .stat-btn-minus:hover {
        background: #900;
    }

    .stat-btn-plus {
        background: #060;
        color: #fff;
    }

    .stat-btn-plus:hover {
        background: #090;
    }

    .stat-bar-container {
        width: 25;
        height: 1;
        background: #222;
    }

    .stat-fill {
        height: 1;
    }

    .stat-fill.mind { background: #0af; }
    .stat-fill.body { background: #fa0; }
    .stat-fill.spirit { background: #f0a; }

    .stat-value {
        width: 3;
        text-align: center;
        margin-left: 1;
    }

    #points-remaining {
        text-align: center;
        margin: 2 0;
        height: 1;
    }

    #confirm-btn {
        margin-top: 1;
        width: 100%;
        background: #0f9;
        color: #000;
        text-style: bold;
    }

    #confirm-btn:hover {
        background: #0fa;
    }

    #confirm-btn.disabled-btn {
        background: #333;
        color: #666;
    }

    /* Name input screen */
    #name-screen {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #name-screen.hidden {
        display: none;
    }

    #name-container {
        width: 60;
        height: auto;
        background: #0f0f23;
        border: round #0f9;
        padding: 2 3;
    }

    #name-title {
        text-align: center;
        margin-bottom: 1;
        text-style: bold;
        color: #0f9;
    }

    #name-subtitle {
        text-align: center;
        margin-bottom: 2;
        color: #666;
    }

    #name-input {
        width: 100%;
        background: #16213e;
        border: round #0f9;
        margin-bottom: 1;
    }

    /* API Key screen */
    #apikey-screen {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #apikey-screen.hidden {
        display: none;
    }

    #apikey-container {
        width: 70;
        height: auto;
        background: #0f0f23;
        border: round #0f9;
        padding: 2 3;
    }

    #apikey-title {
        text-align: center;
        margin-bottom: 1;
        text-style: bold;
        color: #0f9;
    }

    #apikey-subtitle {
        text-align: center;
        margin-bottom: 2;
        color: #666;
    }

    #apikey-input {
        width: 100%;
        background: #16213e;
        border: round #0f9;
        margin-bottom: 1;
    }

    #apikey-error {
        text-align: center;
        color: #f00;
        height: 1;
        margin-top: 1;
    }

    #apikey-hint {
        text-align: center;
        color: #444;
        margin-top: 1;
    }

    /* Title screen */
    #title-screen {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #title-screen.hidden {
        display: none;
    }

    #title-container {
        width: 60;
        height: auto;
        background: #0f0f23;
        border: round #0f9;
        padding: 3 4;
        align: center middle;
    }

    #title-logo {
        text-align: center;
        text-style: bold;
        color: #0f9;
        margin-bottom: 2;
    }

    #title-status {
        text-align: center;
        color: #888;
        height: 2;
    }

    #title-prompt {
        text-align: center;
        margin-top: 2;
    }

    #title-settings-btn {
        margin-top: 2;
        width: 20;
        background: #16213e;
        color: #888;
        border: round #444;
    }

    #title-settings-btn:hover {
        background: #1a1a2e;
        border: round #0af;
        color: #0af;
    }

    #title-settings-btn:focus {
        background: #1a1a2e;
        border: round #0f9;
        color: #0f9;
    }
    """

    BINDINGS = [
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+t", "toggle_tts", "Toggle TTS"),
        Binding("ctrl+s", "open_settings", "Settings"),
        Binding("escape", "quit", "Quit"),
        Binding("ctrl+left", "focus_previous", "Previous", show=False),
        Binding("ctrl+right", "focus_next", "Next", show=False),
    ]

    TITLE = "Universal RPG Engine"

    # Reactive stats for the allocation screen
    alloc_mind = reactive(3)
    alloc_body = reactive(3)
    alloc_spirit = reactive(3)

    def __init__(self):
        super().__init__()
        self.character = ""
        self.character_visual = ""  # Visual description for consistent image generation
        self.stats = {"mind": 3, "body": 3, "spirit": 3}
        self.context = ""
        self.history = []  # Stack of (context, roll_text) for undo
        self.last_roll_text = ""
        self.last_action = None
        self.last_invalid = False
        self.alive = True
        self.game_started = False
        self._prompt_animation_task = None
        self.suggestions = ["...", "...", "..."]  # Current action suggestions
        self._scroll_positions = [0, 0, 0]  # Track scroll position for each button
        self._scroll_timer = None

        # Initialize TTS (enabled by default)
        get_tts().set_enabled(True)

        # Check if API key is already set
        existing_key = get_api_key()
        self._has_api_key = existing_key and init_openai_client(existing_key)

        # Always start at title screen
        self.creation_phase = "title"  # "title", "apikey", "name", "stats", "game"
        self._model_loading = False
        self._model_ready = False
        self._game_starting = False  # Prevent multiple start_game calls

    def compose(self) -> ComposeResult:
        # Title screen (shows while loading)
        yield Center(
            Container(
                Static("UNIVERSAL RPG ENGINE", id="title-logo"),
                Static("", id="title-status"),
                Static("[dim]Press ENTER to start[/]", id="title-prompt"),
                Button("⚙ Settings", id="title-settings-btn"),
                id="title-container"
            ),
            id="title-screen",
            classes="" if self.creation_phase == "title" else "hidden"
        )

        # API Key entry screen
        yield Center(
            Container(
                Static("UNIVERSAL RPG ENGINE", id="apikey-title"),
                Static("Enter your OpenAI API key to begin", id="apikey-subtitle"),
                Input(placeholder="sk-...", id="apikey-input", password=True),
                Static("", id="apikey-error"),
                Static("Get your key at platform.openai.com/api-keys", id="apikey-hint"),
                id="apikey-container"
            ),
            id="apikey-screen",
            classes="hidden"
        )

        # Name entry screen
        yield Center(
            Container(
                Static("UNIVERSAL RPG ENGINE", id="name-title"),
                Static("Examples: 'a stray dog in Tokyo', 'a Roman gladiator'", id="name-subtitle"),
                Input(placeholder="Who are you?", id="name-input"),
                id="name-container"
            ),
            id="name-screen",
            classes="hidden"
        )

        # Stat allocation screen (Fallout-style)
        yield Center(
            Container(
                Static("ALLOCATE YOUR STATS", id="stat-title"),
                Static("", id="char-display"),
                Horizontal(
                    Static("MIND", classes="stat-label mind"),
                    Button("-", id="mind-minus", classes="stat-btn stat-btn-minus"),
                    Static("", id="mind-bar", classes="stat-bar-container"),
                    Button("+", id="mind-plus", classes="stat-btn stat-btn-plus"),
                    Static("3", id="mind-value", classes="stat-value"),
                    classes="stat-row"
                ),
                Horizontal(
                    Static("BODY", classes="stat-label body"),
                    Button("-", id="body-minus", classes="stat-btn stat-btn-minus"),
                    Static("", id="body-bar", classes="stat-bar-container"),
                    Button("+", id="body-plus", classes="stat-btn stat-btn-plus"),
                    Static("3", id="body-value", classes="stat-value"),
                    classes="stat-row"
                ),
                Horizontal(
                    Static("SPIRIT", classes="stat-label spirit"),
                    Button("-", id="spirit-minus", classes="stat-btn stat-btn-minus"),
                    Static("", id="spirit-bar", classes="stat-bar-container"),
                    Button("+", id="spirit-plus", classes="stat-btn stat-btn-plus"),
                    Static("3", id="spirit-value", classes="stat-value"),
                    classes="stat-row"
                ),
                Static("Points remaining: 0", id="points-remaining"),
                Button("BEGIN ADVENTURE", id="confirm-btn"),
                id="stat-container"
            ),
            id="stat-screen",
            classes="hidden"
        )

        # Main game screen
        yield Vertical(
            Static("", id="stats-bar"),
            Horizontal(
                ScrollableContainer(Static("", id="story-content"), id="story-scroll"),
                Container(
                    Static("[dim]No image[/]", id="image-placeholder"),
                    id="image-container"
                ),
                id="story-row"
            ),
            Static("", id="roll-bar"),
            Horizontal(
                Input(placeholder="Type anything...", id="action-input"),
                Button("...", id="suggestion-1", classes="suggestion-btn"),
                Button("...", id="suggestion-2", classes="suggestion-btn"),
                Button("...", id="suggestion-3", classes="suggestion-btn"),
                Button("Undo", id="undo-btn"),
                Button("Force!", id="force-btn", classes="hidden"),
                Button("⚙", id="settings-btn"),
                id="input-row"
            ),
            id="main-container",
            classes="hidden"
        )

    def on_mount(self) -> None:
        if self.creation_phase == "title":
            # Start preloading local model if configured
            self.run_worker(self._preload_model_async(), exclusive=False)
        elif self.creation_phase == "apikey":
            self.query_one("#apikey-input", Input).focus()
        else:
            self.query_one("#name-input", Input).focus()
            self._prompt_animation_task = self.run_worker(self._animate_name_prompt(), exclusive=False)
        self.update_stat_bars()

    async def _preload_model_async(self) -> None:
        """Preload the local SD model in the background if configured."""
        config = get_config()
        status = self.query_one("#title-status", Static)
        prompt = self.query_one("#title-prompt", Static)

        # Check if we're using a local model
        if config.image_enabled and is_local_model(config.image_model):
            self._model_loading = True
            status.update("[#fa0]Loading local Stable Diffusion model...[/]")
            prompt.update("[dim]Please wait...[/]")

            # Run preloading in a thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, preload_local_model)

            self._model_loading = False
            self._model_ready = True
            status.update("[#0f9]Model loaded![/]")
            prompt.update("[dim]Press ENTER to start[/]")
        else:
            # No local model to load
            self._model_ready = True
            if config.image_enabled:
                status.update(f"[dim]Using {config.image_model}[/]")
            else:
                status.update("[dim]Image generation disabled[/]")
            prompt.update("[dim]Press ENTER to start[/]")

    async def _animate_name_prompt(self) -> None:
        """Glitchy cycling through identity questions on name screen."""
        input_widget = self.query_one("#name-input", Input)
        glitch_chars = "░▒▓█▄▀─│┌┐└┘├┤┬┴┼"

        while self.creation_phase == "name":
            prompt = random.choice(IDENTITY_PROMPTS)

            if random.random() < 0.3:
                glitched = list(prompt)
                for _ in range(random.randint(1, 3)):
                    pos = random.randint(0, len(glitched) - 1)
                    glitched[pos] = random.choice(glitch_chars)
                display = ''.join(glitched)
                input_widget.placeholder = display
                await asyncio.sleep(0.08)
            else:
                input_widget.placeholder = prompt
                await asyncio.sleep(random.uniform(0.8, 2.0))

    def update_stat_bars(self) -> None:
        """Update the visual stat bars based on current allocation."""
        try:
            for stat_name in ["mind", "body", "spirit"]:
                value = getattr(self, f"alloc_{stat_name}")
                bar = self.query_one(f"#{stat_name}-bar", Static)
                value_label = self.query_one(f"#{stat_name}-value", Static)

                # Create visual bar: filled portion + empty portion
                filled = "█" * (value * 5)  # 5 chars per point
                empty = "░" * ((5 - value) * 5)  # Max 5 points
                color = STAT_COLORS[stat_name]
                bar.update(f"[{color}]{filled}[/][#333]{empty}[/]")
                value_label.update(str(value))

            # Update points remaining
            remaining = 9 - (self.alloc_mind + self.alloc_body + self.alloc_spirit)
            points_label = self.query_one("#points-remaining", Static)
            confirm_btn = self.query_one("#confirm-btn", Button)

            if remaining == 0:
                points_label.update("[#0f9]Ready to begin![/]")
                confirm_btn.remove_class("disabled-btn")
            elif remaining > 0:
                points_label.update(f"[#fa0]Points remaining: {remaining}[/]")
                confirm_btn.add_class("disabled-btn")
            else:
                points_label.update(f"[#f00]Too many points! Remove {-remaining}[/]")
                confirm_btn.add_class("disabled-btn")
        except Exception:
            pass  # Widgets not yet mounted

    def watch_alloc_mind(self, value: int) -> None:
        self.update_stat_bars()

    def watch_alloc_body(self, value: int) -> None:
        self.update_stat_bars()

    def watch_alloc_spirit(self, value: int) -> None:
        self.update_stat_bars()

    def update_stats_bar(self) -> None:
        bar = self.query_one("#stats-bar", Static)
        cost = get_config().get_session_cost()
        bar.update(
            f"[bold #0f9]{self.character}[/]  │  "
            f"[#0af]Mind[/] {self.stats['mind']}  "
            f"[#fa0]Body[/] {self.stats['body']}  "
            f"[#f0a]Spirit[/] {self.stats['spirit']}  │  "
            f"[dim]${cost:.4f}[/]"
        )

    def update_suggestions(self, suggestions: list[str]) -> None:
        """Update the suggestion buttons with new text."""
        self.suggestions = suggestions
        self._scroll_positions = [0, 0, 0]  # Reset scroll positions

        # Stop existing timer
        if self._scroll_timer:
            self._scroll_timer.stop()

        # Start scrolling timer (faster scroll)
        self._scroll_timer = self.set_interval(0.15, self._scroll_suggestions)

    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text to fit within width, breaking at word boundaries."""
        import textwrap
        lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=True)
        # Return exactly 2 lines, padding if needed
        if len(lines) == 0:
            return "\n"
        elif len(lines) == 1:
            return lines[0] + "\n"
        else:
            return lines[0] + "\n" + lines[1]

    def _scroll_suggestions(self) -> None:
        """Scroll text in suggestion buttons, snaking across 2 rows with word wrap."""
        for i, suggestion in enumerate(self.suggestions):
            try:
                btn = self.query_one(f"#suggestion-{i + 1}", Button)

                # Calculate max width based on button's actual size (subtract padding)
                max_width = max(20, btn.size.width - 4)

                # Use textwrap to check if it fits in 2 lines
                import textwrap
                wrapped = textwrap.wrap(suggestion, width=max_width, break_long_words=False, break_on_hyphens=True)

                if len(wrapped) <= 2:
                    # Fits in 2 rows, no scrolling needed
                    display_text = self._wrap_text(suggestion, max_width)
                else:
                    # Need to scroll - show a sliding window
                    pos = self._scroll_positions[i]
                    # Add separator between end and start
                    padded = suggestion + "  ···  "
                    padded_len = len(padded)

                    # Create a sliding window view and wrap it
                    extended = padded * 3
                    # Take enough chars to potentially fill 2 lines
                    window_size = max_width * 3  # Extra chars for word wrap flexibility
                    window = extended[pos:pos + window_size]

                    # Wrap the window and take first 2 lines
                    display_text = self._wrap_text(window, max_width)

                    # Advance position
                    self._scroll_positions[i] = (pos + 1) % padded_len

                btn.label = display_text
            except:
                pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        action = event.value.strip()
        if not action:
            return

        # Handle API key input
        if event.input.id == "apikey-input":
            error_label = self.query_one("#apikey-error", Static)
            error_label.update("[dim]Validating...[/]")
            self.refresh()

            if init_openai_client(action):
                # Success - move to name screen
                self.creation_phase = "name"
                self.query_one("#apikey-screen").add_class("hidden")
                self.query_one("#name-screen").remove_class("hidden")
                self.query_one("#name-input", Input).focus()
                self._prompt_animation_task = self.run_worker(self._animate_name_prompt(), exclusive=False)
            else:
                # Failed - show error
                error_label.update("[#f00]Invalid API key. Please try again.[/]")
                event.input.value = ""
            return

        # Handle name input
        if event.input.id == "name-input":
            self.character = action
            self.creation_phase = "stats"

            # Hide name screen, show stat screen
            self.query_one("#name-screen").add_class("hidden")
            self.query_one("#stat-screen").remove_class("hidden")

            # Update character display
            self.query_one("#char-display", Static).update(f"[bold]{self.character}[/]")
            return

        # Note: game action input is now handled via on_key for TextArea

    def start_game(self) -> None:
        """Transition from stat allocation to the actual game."""
        # Prevent multiple calls
        if self._game_starting:
            return
        self._game_starting = True

        # Disable the button and show loading state
        try:
            confirm_btn = self.query_one("#confirm-btn", Button)
            confirm_btn.disabled = True
            confirm_btn.label = "Starting..."
        except Exception:
            pass

        # Run the actual game start in a worker
        self.run_worker(self._start_game_async(), exclusive=True)

    async def _start_game_async(self) -> None:
        """Async game start to prevent UI blocking."""
        self.stats = {
            "mind": self.alloc_mind,
            "body": self.alloc_body,
            "spirit": self.alloc_spirit
        }
        self.game_started = True
        self.creation_phase = "game"

        logger.info(f"Game started: {self.character} (M:{self.stats['mind']} B:{self.stats['body']} S:{self.stats['spirit']})")

        # Hide stat screen, show game screen
        self.query_one("#stat-screen").add_class("hidden")
        self.query_one("#main-container").remove_class("hidden")

        # Show/hide image panel based on settings
        config = get_config()
        image_container = self.query_one("#image-container", Container)
        if config.image_enabled and IMAGES_AVAILABLE:
            image_container.remove_class("hidden")
        else:
            image_container.add_class("hidden")

        # Update game UI
        self.update_stats_bar()
        story = self.query_one("#story-content", Static)
        story.update("[dim]Generating your adventure...[/]")
        self.refresh()

        # Generate opening scene (run in executor to not block)
        loop = asyncio.get_event_loop()
        self.context = await loop.run_in_executor(
            None, lambda: opening_scene(self.character, self.stats)
        )
        story.update(self.context)
        self.scroll_story()

        # Generate visual description for consistent images (if images enabled)
        if config.image_enabled and IMAGES_AVAILABLE:
            prompt = IMAGE_SUBJECT_PROMPT.format(character=self.character, scene=self.context)
            self.character_visual = await loop.run_in_executor(
                None, lambda: call_llm(prompt, task="interpreter")
            )
            logger.info(f"Character visual: {self.character_visual}")

        # Generate initial suggestions
        suggestions = await loop.run_in_executor(
            None, lambda: generate_suggestions(self.character, self.context)
        )
        self.update_suggestions(suggestions)

        # Speak the opening scene (non-blocking, will be interrupted by first action)
        tts = get_tts()
        tts.speak(self.context, blocking=False, interrupt=True)

        # Generate opening scene image if enabled
        if config.image_enabled and IMAGES_AVAILABLE:
            self.run_worker(self._generate_image_async(), exclusive=False)

        # Update cost display after LLM calls and TTS chars are added
        self.update_stats_bar()

        # Focus the action input
        self.query_one("#action-input", Input).focus()

        # Reset the starting flag (though we're now in game phase)
        self._game_starting = False

    def handle_action(self, action: str) -> None:
        """Start the async action handler."""
        self.run_worker(self._handle_action_async(action), exclusive=True)

    async def _handle_action_async(self, action: str) -> None:
        story = self.query_one("#story-content", Static)
        roll_bar = self.query_one("#roll-bar", Static)
        force_btn = self.query_one("#force-btn", Button)
        input_widget = self.query_one("#action-input", Input)
        input_widget.disabled = True

        god_mode = False
        if action.lower().startswith("/god "):
            action = action[5:]
            god_mode = True

        force_mode = False
        if action == "!" and self.last_action and self.last_invalid:
            action = self.last_action
            force_mode = True
            force_btn.add_class("hidden")

        if force_mode:
            interpretation = {"valid": True, "stat": "spirit", "difficulty": 5, "lethal": False}
        elif god_mode:
            interpretation = {"valid": True, "stat": "spirit", "difficulty": 1, "lethal": False}
        else:
            roll_bar.update("[dim]Thinking...[/]")
            interpretation = interpret_action(action, self.context)

        if not interpretation.get("valid", True):
            reason = interpretation.get("reason", "That's not possible.")
            roll_bar.update(f"[#fa0]INVALID:[/] {reason}  [dim]│ Click Force! or type ! to attempt anyway[/]")
            self.last_action = action
            self.last_invalid = True
            force_btn.remove_class("hidden")
            input_widget.disabled = False
            input_widget.focus()
            return

        self.last_invalid = False
        force_btn.add_class("hidden")

        stat = interpretation["stat"]
        difficulty = interpretation["difficulty"]
        lethal = interpretation.get("lethal", False)

        # Save state for undo
        self.history.append((self.context, self.last_roll_text))

        # === DISPLAY PLAYER ACTION ===
        # Show the player's action as a chat bubble on the right
        story.update(f"{self.context}\n\n[dim italic right]> {action}[/]")
        self.scroll_story()

        stat_value = self.stats[stat]
        stat_color = STAT_COLORS.get(stat, "#fff")
        lethal_text = " [#f00]⚠ LETHAL[/]" if lethal else ""

        # Roll the dice (but don't reveal yet)
        if god_mode:
            final_roll = 10
            success = True
        else:
            success, final_roll = roll_check(stat_value, difficulty)

        # === CALCULATE SUCCESS CHANCE ===
        # Success if: roll + stat - difficulty > 5
        # So need: roll > 5 - stat + difficulty
        threshold = 5 - stat_value + difficulty
        # Chance = number of winning rolls / 10
        if threshold < 1:
            chance_pct = 100  # Always succeed
        elif threshold > 10:
            chance_pct = 0  # Always fail
        else:
            winning_rolls = 10 - threshold + 1
            chance_pct = winning_rolls * 10

        # === DICE ANIMATION ===
        animation_frames = 8
        frame_delay = 0.12

        for i in range(animation_frames):
            fake_roll = random.randint(1, 10)
            roll_bar.update(
                f"[{stat_color}]{stat.upper()}[/] {stat_value} vs DC {difficulty}{lethal_text} │ "
                f"{chance_pct}% chance │ Rolling..."
            )
            await asyncio.sleep(frame_delay)

        # === FINAL RESULT ===
        died = lethal and not success
        total = final_roll + stat_value - difficulty

        logger.info(f"Roll: {stat} d10={final_roll} +{stat_value} -{difficulty} = {total} -> {'SUCCESS' if success else 'FAILURE'}{' DEATH' if died else ''}")

        if died:
            result_text = "[bold #f00]💀 DEATH[/]"
        elif success:
            result_text = "[bold #0f9]✓ SUCCESS[/]"
        else:
            result_text = "[bold #fa0]✗ FAILURE[/]"

        miracle_text = " [#f0a]✦ MIRACULOUS[/]" if (force_mode or god_mode) and success else ""

        # Final roll display
        self.last_roll_text = (
            f"[{stat_color}]{stat.upper()}[/] {stat_value} vs DC {difficulty}{lethal_text} │ "
            f"{chance_pct}% chance │ {result_text}{miracle_text}"
        )
        roll_bar.update(self.last_roll_text)

        # Narrate
        story.update(f"{self.context}\n\n[dim]...[/]")

        is_miraculous = force_mode or god_mode
        self.context = narrate(self.context, self.character, self.stats, action, stat, difficulty, success, died, is_miraculous)
        story.update(self.context)
        self.scroll_story()

        # Speak the narrative (non-blocking, interrupt any old speech)
        tts = get_tts()
        tts.speak(self.context, blocking=False, interrupt=True)

        # Generate scene image if enabled
        config = get_config()
        if config.image_enabled and IMAGES_AVAILABLE:
            self.run_worker(self._generate_image_async(), exclusive=False)

        # Update cost display (after TTS chars are added)
        self.update_stats_bar()

        if died:
            self.alive = False
            roll_bar.update(f"{self.last_roll_text}  │  [bold #f00]GAME OVER[/]")
        else:
            # Generate new suggestions for the next action
            suggestions = generate_suggestions(self.character, self.context)
            self.update_suggestions(suggestions)

        input_widget.disabled = False
        input_widget.focus()

    def scroll_story(self) -> None:
        container = self.query_one("#story-scroll", ScrollableContainer)
        container.scroll_end(animate=False)

    async def _generate_image_async(self) -> None:
        """Generate and display a scene image asynchronously in a background thread."""
        logger.info("Starting image generation async")
        clear_last_error()  # Clear any previous error
        config = get_config()

        # Capture values for the thread (avoid accessing self in thread)
        narrative = self.context
        # Use visual description if available, otherwise fall back to character name
        character = self.character_visual if self.character_visual else self.character
        style = config.image_style
        model = config.image_model
        quality = config.image_quality
        is_local = is_local_model(model)
        logger.debug(f"Image gen params: model={model}, quality={quality}, is_local={is_local}")

        # Get total steps for local model progress bar
        steps_map = {"low": 10, "medium": 20, "high": 35}
        total_steps = steps_map.get(quality, 15) if is_local else 0
        # Approximate time per step (seconds) - adjust based on your GPU
        time_per_step = 0.5  # ~0.5s per step on RTX 5050

        # Show loading state - remove old image and show/update placeholder
        try:
            container = self.query_one("#image-container", Container)
            # Remove old image if exists
            try:
                old_image = self.query_one("#scene-image")
                old_image.remove()
                logger.debug("Removed old scene image")
            except:
                pass

            # Determine placeholder text
            if is_local:
                est_time = int(total_steps * time_per_step)
                placeholder_text = f"[dim]Generating... 0/{total_steps} (~{est_time}s)[/]"
            else:
                placeholder_text = "[dim]Generating...[/]"

            # Try to update existing placeholder, or create new one
            try:
                old_placeholder = self.query_one("#image-placeholder", Static)
                old_placeholder.update(placeholder_text)
                logger.debug("Updated existing placeholder")
            except:
                # No placeholder exists, create one
                container.mount(Static(placeholder_text, id="image-placeholder"))
                logger.debug("Mounted new placeholder")
        except Exception as e:
            logger.error(f"Failed to manage image container: {e}")

        # Progress tracking for local models
        progress_state = {"step": 0}

        def update_progress(step, _total):
            progress_state["step"] = step

        # For local models, use a separate task to update progress
        if is_local:
            async def progress_updater():
                while progress_state["step"] < total_steps:
                    try:
                        step = progress_state["step"]
                        remaining = total_steps - step
                        est_remaining = int(remaining * time_per_step)
                        # Build progress bar: ████░░░░░░
                        bar_width = 10
                        filled = int((step / total_steps) * bar_width) if total_steps > 0 else 0
                        bar = "█" * filled + "░" * (bar_width - filled)
                        placeholder = self.query_one("#image-placeholder", Static)
                        placeholder.update(f"[dim]{bar} {step}/{total_steps} (~{est_remaining}s)[/]")
                    except:
                        pass
                    await asyncio.sleep(0.3)

            progress_task = asyncio.create_task(progress_updater())

        # Get local SD settings
        local_resolution = config.local_resolution
        local_guidance = config.local_guidance
        local_negative = config.local_negative_prompt
        visual_director_model = config.visual_director_model

        # Use visual director to generate optimized image prompt
        # Extract recent narrative (last ~1500 chars for context)
        recent_narrative = narrative[-1500:] if len(narrative) > 1500 else narrative

        loop = asyncio.get_event_loop()

        # Generate optimized prompt using visual director
        visual_prompt, vd_tokens = await loop.run_in_executor(
            None,
            lambda: generate_visual_prompt(
                character_visual=character,
                recent_narrative=recent_narrative,
                style=style,
                client=client,
                model=visual_director_model,
            )
        )

        # Track visual director tokens
        if vd_tokens["prompt"] > 0 or vd_tokens["completion"] > 0:
            config.add_tokens(vd_tokens["prompt"], vd_tokens["completion"], task="visual_director")

        logger.info(f"Visual director prompt: {visual_prompt[:100]}...")

        # Run the blocking image generation in a thread pool
        image_data = await loop.run_in_executor(
            None,  # Use default thread pool
            lambda: generate_scene_image(
                narrative=narrative,
                character=character,
                style=style,
                client=client,
                model=model,
                quality=quality,
                progress_callback=update_progress if is_local else None,
                local_resolution=local_resolution,
                local_guidance=local_guidance,
                local_negative_prompt=local_negative,
                visual_prompt=visual_prompt,  # Pass optimized prompt from visual director
            )
        )

        # Cancel progress updater if running
        if is_local:
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        logger.info(f"Image generation returned: {len(image_data) if image_data else 0} bytes")

        if image_data:
            # Track the image generation
            config.add_image()
            self.update_stats_bar()

            # Display the image
            self._display_image(image_data)
        else:
            logger.warning("Image generation returned None")
            try:
                placeholder = self.query_one("#image-placeholder", Static)
                error_msg = get_last_error()
                if error_msg:
                    placeholder.update(f"[red]Failed: {error_msg}[/]")
                else:
                    placeholder.update("[dim]Image failed[/]")
            except:
                pass

    def _display_image(self, image_data: bytes) -> None:
        """Display an image using Sixel (full resolution) or fallback to rich-pixels."""
        if not IMAGES_AVAILABLE:
            return

        try:
            container = self.query_one("#image-container", Container)

            # Remove old image/placeholder
            try:
                old_placeholder = self.query_one("#image-placeholder", Static)
                old_placeholder.remove()
            except:
                pass
            try:
                old_image = self.query_one("#scene-image")
                old_image.remove()
            except:
                pass

            # Create image from bytes
            from PIL import Image as PILImage
            pil_image = PILImage.open(BytesIO(image_data))

            # Try to use SixelImage for full-resolution display (Windows Terminal 1.22+)
            if SixelImage is not None:
                # SixelImage handles its own sizing - pass the PIL image directly
                image_widget = SixelImage(pil_image, id="scene-image")
                container.mount(image_widget)
                logger.info("Scene image displayed successfully with Sixel (full resolution)")
            else:
                # Fallback to rich-pixels (lower resolution but universal)
                from rich_pixels import Pixels

                # Get container size in characters (account for border/padding)
                container_width = (container.size.width - 4) or 60
                container_height = ((container.size.height - 2) or 30) * 2

                # Scale image to fit container while maintaining aspect ratio
                img_width, img_height = pil_image.size
                scale = min(container_width / img_width, container_height / img_height)
                new_width = max(1, int(img_width * scale))
                new_height = max(1, int(img_height * scale))

                pixels = Pixels.from_image(pil_image, resize=(new_width, new_height))
                image_static = Static(pixels, id="scene-image")
                container.mount(image_static)
                logger.info("Scene image displayed with rich-pixels fallback")

        except Exception as e:
            logger.error(f"Failed to display image: {e}")
            # Show error in placeholder
            try:
                container = self.query_one("#image-container", Container)
                container.mount(Static(f"[dim]Display error[/]", id="image-placeholder"))
            except:
                pass

    def on_key(self, event) -> None:
        """Handle key presses for TextArea submission and title screen."""
        # Handle title screen
        if event.key == "enter" and self.creation_phase == "title":
            # Don't proceed if model is still loading
            if self._model_loading:
                return
            # Transition to next screen
            self.query_one("#title-screen").add_class("hidden")
            if self._has_api_key:
                self.creation_phase = "name"
                self.query_one("#name-screen").remove_class("hidden")
                self.query_one("#name-input", Input).focus()
                self._prompt_animation_task = self.run_worker(self._animate_name_prompt(), exclusive=False)
            else:
                self.creation_phase = "apikey"
                self.query_one("#apikey-screen").remove_class("hidden")
                self.query_one("#apikey-input", Input).focus()
            event.prevent_default()
            event.stop()
            return

        # Handle stat screen - Enter to begin adventure
        if event.key == "enter" and self.creation_phase == "stats":
            # Don't proceed if already starting
            if self._game_starting:
                event.prevent_default()
                event.stop()
                return
            remaining = 9 - (self.alloc_mind + self.alloc_body + self.alloc_spirit)
            if remaining == 0:
                self.start_game()
                event.prevent_default()
                event.stop()
            return

        # Submit on Enter for game input
        if event.key == "enter":
            try:
                input_widget = self.query_one("#action-input", Input)
                if input_widget.has_focus:
                    action = input_widget.value.strip()
                    if action and self.alive and self.game_started:
                        input_widget.value = ""
                        self.handle_action(action)
                        event.prevent_default()
                        event.stop()
            except Exception:
                pass  # Widget not mounted or wrong screen

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        # Stat allocation buttons
        if button_id == "mind-minus" and self.alloc_mind > 1:
            self.alloc_mind -= 1
        elif button_id == "mind-plus" and self.alloc_mind < 5:
            self.alloc_mind += 1
        elif button_id == "body-minus" and self.alloc_body > 1:
            self.alloc_body -= 1
        elif button_id == "body-plus" and self.alloc_body < 5:
            self.alloc_body += 1
        elif button_id == "spirit-minus" and self.alloc_spirit > 1:
            self.alloc_spirit -= 1
        elif button_id == "spirit-plus" and self.alloc_spirit < 5:
            self.alloc_spirit += 1

        # Confirm button - start the game
        elif button_id == "confirm-btn":
            if self._game_starting:
                return  # Already starting, ignore
            remaining = 9 - (self.alloc_mind + self.alloc_body + self.alloc_spirit)
            if remaining == 0:
                self.start_game()

        # Game buttons
        elif button_id == "undo-btn":
            self.action_undo()
        elif button_id == "force-btn":
            if self.last_action and self.last_invalid:
                self.handle_action("!")

        # Suggestion buttons
        elif button_id == "suggestion-1":
            self.handle_action(self.suggestions[0])
        elif button_id == "suggestion-2":
            self.handle_action(self.suggestions[1])
        elif button_id == "suggestion-3":
            self.handle_action(self.suggestions[2])

        # Settings button (game and title screen)
        elif button_id == "settings-btn" or button_id == "title-settings-btn":
            self.action_open_settings()

    def action_undo(self) -> None:
        if self.history:
            self.context, self.last_roll_text = self.history.pop()
            self.query_one("#story-content", Static).update(self.context)
            self.query_one("#roll-bar", Static).update(self.last_roll_text if self.last_roll_text else "")
            self.alive = True
            self.query_one("#force-btn", Button).add_class("hidden")
            self.scroll_story()

    def action_toggle_tts(self) -> None:
        """Toggle TTS on/off."""
        tts = get_tts()
        enabled = tts.toggle()
        roll_bar = self.query_one("#roll-bar", Static)
        status = "[#0f0]ON[/]" if enabled else "[#f00]OFF[/]"
        roll_bar.update(f"TTS: {status}")

    def action_open_settings(self) -> None:
        """Open settings screen."""
        self.push_screen(SettingsScreen(), callback=self._on_settings_closed)

    def _on_settings_closed(self, result=None) -> None:
        """Called when settings screen closes. Refresh title screen if needed."""
        if self.creation_phase == "title":
            # Re-check if we need to load local model after settings change
            self.run_worker(self._preload_model_async(), exclusive=False)


if __name__ == "__main__":
    app = RPGApp()
    app.run()
