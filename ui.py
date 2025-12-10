from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer, Container, Center
from textual.widgets import Header, Footer, Static, Input, Button, Rule, ProgressBar
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
import random
import json
import os
import logging
import asyncio
from openai import OpenAI
from prompts import INTERPRETER_PROMPT, NARRATOR_PROMPT, SETUP_PROMPT, SUGGESTIONS_PROMPT
from tts import get_tts

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


def call_llm(prompt: str, system: str = None, json_mode: bool = False) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {"model": "gpt-4o-mini", "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    logger.debug(f"LLM request: {prompt[:200]}...")
    try:
        response = client.chat.completions.create(**kwargs)
        result = response.choices[0].message.content
        logger.debug(f"LLM response: {result[:200]}...")
        return result
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        raise


def interpret_action(action: str, context: str) -> dict:
    prompt = f"Context: {context}\n\nPlayer action: {action}"
    response = call_llm(prompt, system=INTERPRETER_PROMPT, json_mode=True)

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
        response = call_llm(prompt, json_mode=True)
        logger.debug(f"Suggestions response: {response}")

        suggestions = json.loads(response)
        if isinstance(suggestions, list) and len(suggestions) == 3:
            logger.info(f"Generated suggestions: {suggestions}")
            return suggestions

        logger.warning(f"Invalid suggestions format: {suggestions}")
        return ["Continue forward", "Look around carefully", "Wait and observe"]
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return ["Continue forward", "Look around carefully", "Wait and observe"]


IDENTITY_PROMPTS = [
    "Who are you?",
    "What are you?",
    "Where do you come from?",
    "Who will you become?",
    "What is your name?",
    "What do you seek?",
    "Who do you serve?",
    "What haunts you?",
    "Why are you here?",
]


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

    #story-scroll {
        height: 1fr;
        border: round #0f9;
        background: #0f0f23;
        padding: 1 2;
        margin-bottom: 1;
    }

    #story-content {
        color: #e0e0e0;
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
        height: 3;
        margin-left: 1;
        background: #0f0f23;
        border: round #444;
        color: #888;
        text-align: left;
        padding: 0 1;
        overflow-x: auto;
        text-overflow: ellipsis;
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
        background: #444;
        color: #fff;
        border: none;
    }

    #undo-btn:hover {
        background: #666;
    }

    #force-btn {
        background: #a00;
        color: #fff;
        border: none;
    }

    #force-btn:hover {
        background: #c00;
    }

    #force-btn.hidden {
        display: none;
    }

    #tts-controls {
        width: auto;
        height: 3;
        align: center middle;
    }

    #tts-slower, #tts-faster, #tts-voice {
        width: 3;
        min-width: 3;
        height: 3;
        background: #444;
        color: #fff;
        border: none;
        padding: 0;
    }

    #tts-slower:hover, #tts-faster:hover, #tts-voice:hover {
        background: #666;
    }

    #tts-speed {
        width: 5;
        height: 3;
        content-align: center middle;
        background: #222;
        color: #0af;
        padding: 0 1;
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
    """

    BINDINGS = [
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+t", "toggle_tts", "Toggle TTS"),
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

        # Initialize TTS (enabled by default)
        get_tts().set_enabled(True)

        # Check if API key is already set
        existing_key = get_api_key()
        if existing_key and init_openai_client(existing_key):
            self.creation_phase = "name"  # Skip API key screen
        else:
            self.creation_phase = "apikey"  # "apikey", "name", "stats", "game"

    def compose(self) -> ComposeResult:
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
            classes="" if self.creation_phase == "apikey" else "hidden"
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
            classes="hidden" if self.creation_phase == "apikey" else ""
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
            ScrollableContainer(Static("", id="story-content"), id="story-scroll"),
            Static("", id="roll-bar"),
            Horizontal(
                Input(placeholder="What do you do?", id="action-input"),
                Button("...", id="suggestion-1", classes="suggestion-btn"),
                Button("...", id="suggestion-2", classes="suggestion-btn"),
                Button("...", id="suggestion-3", classes="suggestion-btn"),
                Button("Undo", id="undo-btn"),
                Button("Force!", id="force-btn", classes="hidden"),
                Horizontal(
                    Button("◀", id="tts-slower"),
                    Static("200", id="tts-speed"),
                    Button("▶", id="tts-faster"),
                    Button("🎤", id="tts-voice"),
                    id="tts-controls"
                ),
                id="input-row"
            ),
            id="main-container",
            classes="hidden"
        )

    def on_mount(self) -> None:
        if self.creation_phase == "apikey":
            self.query_one("#apikey-input", Input).focus()
        else:
            self.query_one("#name-input", Input).focus()
            self._prompt_animation_task = self.run_worker(self._animate_name_prompt(), exclusive=False)
        self.update_stat_bars()

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
        bar.update(
            f"[bold #0f9]{self.character}[/]  │  "
            f"[#0af]Mind[/] {self.stats['mind']}  "
            f"[#fa0]Body[/] {self.stats['body']}  "
            f"[#f0a]Spirit[/] {self.stats['spirit']}"
        )

    def update_suggestions(self, suggestions: list[str]) -> None:
        """Update the suggestion buttons with new text."""
        self.suggestions = suggestions
        for i, suggestion in enumerate(suggestions, 1):
            try:
                btn = self.query_one(f"#suggestion-{i}", Button)
                btn.label = suggestion
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

        # Handle game action input
        if event.input.id == "action-input":
            input_widget = self.query_one("#action-input", Input)
            input_widget.value = ""

            if self.alive:
                self.handle_action(action)

    def start_game(self) -> None:
        """Transition from stat allocation to the actual game."""
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

        # Update game UI
        self.update_stats_bar()
        story = self.query_one("#story-content", Static)
        story.update("[dim]Generating your adventure...[/]")
        self.refresh()

        # Generate opening scene
        self.context = opening_scene(self.character, self.stats)
        story.update(self.context)
        self.scroll_story()

        # Generate initial suggestions
        suggestions = generate_suggestions(self.character, self.context)
        self.update_suggestions(suggestions)

        # Speak the opening scene (non-blocking, will be interrupted by first action)
        tts = get_tts()
        tts.speak(self.context, blocking=False, interrupt=True)

        # Focus the action input
        self.query_one("#action-input", Input).focus()

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

        stat_value = self.stats[stat]
        stat_color = STAT_COLORS.get(stat, "#fff")
        lethal_text = " [#f00]⚠ LETHAL[/]" if lethal else ""

        # Roll the dice (but don't reveal yet)
        if god_mode:
            final_roll = 10
            success = True
        else:
            success, final_roll = roll_check(stat_value, difficulty)

        # === DICE ANIMATION ===
        animation_frames = 8
        frame_delay = 0.12

        for i in range(animation_frames):
            fake_roll = random.randint(1, 10)
            roll_bar.update(
                f"🎲 [{stat_color}]{stat.upper()}[/] ({stat_value}) vs Difficulty {difficulty}{lethal_text} │ "
                f"Rolling... [{fake_roll}]"
            )
            await asyncio.sleep(frame_delay)

        # === FINAL RESULT ===
        died = lethal and not success
        total = final_roll + stat_value - difficulty

        logger.info(f"Roll: {stat} d10={final_roll} +{stat_value} -{difficulty} = {total} -> {'SUCCESS' if success else 'FAILURE'}{' DEATH' if died else ''}")

        if died:
            result_text = "[#f00]DEATH[/]"
        elif success:
            result_text = "[#0f9]SUCCESS[/]"
        else:
            result_text = "[#fa0]FAILURE[/]"

        miracle_text = " [#f0a]✦ MIRACULOUS[/]" if (force_mode or god_mode) and success else ""

        # Final roll display: 🎲 BODY (3) vs Difficulty 2 │ Rolled [8] + 3 - 2 = 9 → SUCCESS
        self.last_roll_text = (
            f"🎲 [{stat_color}]{stat.upper()}[/] ({stat_value}) vs Difficulty {difficulty}{lethal_text} │ "
            f"Rolled [{final_roll}] + {stat_value} - {difficulty} = {total} → {result_text}{miracle_text}"
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
            remaining = 9 - (self.alloc_mind + self.alloc_body + self.alloc_spirit)
            if remaining == 0:
                self.start_game()

        # Game buttons
        elif button_id == "undo-btn":
            self.action_undo()
        elif button_id == "force-btn":
            if self.last_action and self.last_invalid:
                input_widget = self.query_one("#action-input", Input)
                input_widget.value = "!"
                input_widget.action_submit()

        # Suggestion buttons
        elif button_id == "suggestion-1":
            self.handle_action(self.suggestions[0])
        elif button_id == "suggestion-2":
            self.handle_action(self.suggestions[1])
        elif button_id == "suggestion-3":
            self.handle_action(self.suggestions[2])

        # TTS speed controls
        elif button_id == "tts-slower":
            tts = get_tts()
            new_rate = tts.adjust_speed(-25)
            self.query_one("#tts-speed", Static).update(str(new_rate))
        elif button_id == "tts-faster":
            tts = get_tts()
            new_rate = tts.adjust_speed(25)
            self.query_one("#tts-speed", Static).update(str(new_rate))
        elif button_id == "tts-voice":
            tts = get_tts()
            voice_name = tts.cycle_voice()
            roll_bar = self.query_one("#roll-bar", Static)
            roll_bar.update(f"Voice: [#0af]{voice_name}[/]")

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


if __name__ == "__main__":
    app = RPGApp()
    app.run()
