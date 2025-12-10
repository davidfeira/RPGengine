"""
Headless RPG Game Engine - No I/O, pure game logic.
Can be used by UI, CLI, or Claude for testing.
"""

import random
import json
import os
from openai import OpenAI
from prompts import INTERPRETER_PROMPT, NARRATOR_PROMPT, SETUP_PROMPT, SUGGESTIONS_PROMPT
from config import get_config

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def roll_check(stat_value: int, difficulty: int) -> tuple[bool, int]:
    """Roll 1d10 + stat - difficulty > 5 = success"""
    roll = random.randint(1, 10)
    result = roll + stat_value - difficulty
    return result > 5, roll


def call_llm(prompt: str, system: str = None, json_mode: bool = False, task: str = "narrator") -> str:
    """Call OpenAI API with token tracking.

    Args:
        prompt: The user prompt to send
        system: Optional system prompt
        json_mode: Whether to request JSON response
        task: "narrator", "interpreter", or "suggestions" - determines which model to use
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

    response = client.chat.completions.create(**kwargs)

    # Track token usage
    if response.usage:
        config.add_tokens(response.usage.prompt_tokens, response.usage.completion_tokens)

    return response.choices[0].message.content


def interpret_action(action: str, context: str) -> dict:
    """Use LLM to determine stat and difficulty for an action"""
    prompt = f"Context: {context}\n\nPlayer action: {action}"
    response = call_llm(prompt, system=INTERPRETER_PROMPT, json_mode=True, task="interpreter")

    try:
        result = json.loads(response)
        if not result.get("valid", True):
            return {"valid": False, "reason": result.get("reason", "That's not possible.")}
        if result.get("stat") not in ["mind", "body", "spirit"]:
            result["stat"] = "body"
        result["difficulty"] = max(1, min(5, int(result.get("difficulty", 3))))
        result["lethal"] = result.get("lethal", False)
        result["valid"] = True
        return result
    except:
        return {"valid": True, "stat": "body", "difficulty": 3, "lethal": False}


def narrate(context: str, character: str, stats: dict, action: str,
            stat: str, difficulty: int, success: bool, died: bool = False,
            forced: bool = False) -> str:
    """Generate narrative for the outcome"""
    if died:
        outcome = "DEATH"
        special_note = "THIS IS A DEATH SCENE. The character dies here."
    elif forced and success:
        outcome = "MIRACULOUS"
        special_note = "THIS WAS A FORCED IMPOSSIBLE ACTION THAT SUCCEEDED. Reality bent to the character's will."
    elif forced and not success:
        outcome = "FAILURE"
        special_note = "The character attempted the impossible and failed."
    else:
        outcome = "SUCCESS" if success else "FAILURE"
        special_note = ""

    prompt = NARRATOR_PROMPT.format(
        context=context,
        character=character,
        mind=stats["mind"],
        body=stats["body"],
        spirit=stats["spirit"],
        action=action,
        stat=stat,
        difficulty=difficulty,
        outcome=outcome,
        special_note=special_note
    )
    return call_llm(prompt)


def opening_scene(character: str, stats: dict) -> str:
    """Generate the opening scene. Tone is inferred from character concept."""
    prompt = SETUP_PROMPT.format(
        character=character,
        mind=stats["mind"],
        body=stats["body"],
        spirit=stats["spirit"]
    )
    return call_llm(prompt)


def generate_suggestions(character: str, narrative: str) -> list[str]:
    """Generate 3 action suggestions for the current situation.

    Handles multiple response formats from different LLM models:
    - Array: ["action1", "action2", "action3"]
    - Dict with string keys: {"0": "action1", "1": "action2", "2": "action3"}
    - Dict with suggestions key: {"suggestions": ["action1", ...]}
    - Any dict with 3+ values
    """
    prompt = SUGGESTIONS_PROMPT.format(
        character=character,
        narrative=narrative
    )
    response = call_llm(prompt, json_mode=True, task="suggestions")
    fallback = ["Continue forward", "Look around carefully", "Wait and observe"]

    try:
        data = json.loads(response)

        # Handle array format (expected)
        if isinstance(data, list) and len(data) >= 3:
            return [str(s) for s in data[:3]]

        # Handle dict formats
        if isinstance(data, dict):
            # Dict with numeric string keys ("0", "1", "2")
            if all(str(i) in data for i in range(3)):
                return [str(data[str(i)]) for i in range(3)]
            # Dict with "suggestions" key
            if "suggestions" in data and isinstance(data["suggestions"], list):
                sug = data["suggestions"]
                if len(sug) >= 3:
                    return [str(s) for s in sug[:3]]
            # Any dict with 3+ values - take first 3
            values = list(data.values())
            if len(values) >= 3:
                return [str(v) for v in values[:3]]

        return fallback
    except:
        return fallback


class RPGGame:
    """Headless RPG game engine - no I/O, all state accessible."""

    def __init__(self):
        self.character = None
        self.stats = None
        self.context = ""
        self.alive = True
        self.history = []  # List of (context, roll_info) tuples
        self.last_roll = None
        self.last_action = None
        self.last_invalid = False

    def start(self, character: str, mind: int, body: int, spirit: int, with_suggestions: bool = False) -> dict:
        """Initialize game with character. Returns opening narrative."""
        # Validate stats
        if not (1 <= mind <= 5 and 1 <= body <= 5 and 1 <= spirit <= 5):
            return {"error": "Each stat must be between 1 and 5"}
        if mind + body + spirit != 9:
            return {"error": f"Stats must total 9, got {mind + body + spirit}"}

        self.character = character
        self.stats = {"mind": mind, "body": body, "spirit": spirit}
        self.context = opening_scene(character, self.stats)
        self.alive = True
        self.history = []
        self.last_roll = None

        result = {
            "status": "started",
            "character": self.character,
            "stats": self.stats,
            "narrative": self.context
        }

        if with_suggestions:
            result["suggestions"] = generate_suggestions(self.character, self.context)

        return result

    def take_action(self, action: str, force: bool = False, god_mode: bool = False, with_suggestions: bool = False) -> dict:
        """Execute a player action. Returns result with roll info and new narrative."""
        if not self.alive:
            return {"error": "Game over - character is dead"}
        if not self.character:
            return {"error": "Game not started - call start() first"}

        # Handle force mode
        if force and self.last_action and self.last_invalid:
            action = self.last_action
            interpretation = {"valid": True, "stat": "spirit", "difficulty": 5, "lethal": False}
        elif god_mode:
            interpretation = {"valid": True, "stat": "spirit", "difficulty": 1, "lethal": False}
        else:
            interpretation = interpret_action(action, self.context)

        # Check if action is valid
        if not interpretation.get("valid", True):
            reason = interpretation.get("reason", "That's not possible.")
            self.last_action = action
            self.last_invalid = True
            return {
                "status": "invalid",
                "reason": reason,
                "action": action
            }

        self.last_invalid = False

        stat = interpretation["stat"]
        difficulty = interpretation["difficulty"]
        lethal = interpretation.get("lethal", False)
        stat_value = self.stats[stat]

        # Save state for undo
        self.history.append((self.context, self.last_roll))

        # Roll the dice
        if god_mode:
            success, roll = True, 10
        else:
            success, roll = roll_check(stat_value, difficulty)

        died = lethal and not success
        total = roll + stat_value - difficulty

        self.last_roll = {
            "action": action,
            "stat": stat,
            "stat_value": stat_value,
            "difficulty": difficulty,
            "lethal": lethal,
            "roll": roll,
            "total": total,
            "success": success,
            "died": died,
            "forced": force,
            "miraculous": (force or god_mode) and success
        }

        # Narrate the outcome
        is_miraculous = force or god_mode
        self.context = narrate(
            self.context, self.character, self.stats,
            action, stat, difficulty, success, died, is_miraculous
        )

        if died:
            self.alive = False

        result = {
            "status": "death" if died else ("success" if success else "failure"),
            "roll": self.last_roll,
            "narrative": self.context
        }

        if with_suggestions and self.alive:
            result["suggestions"] = generate_suggestions(self.character, self.context)

        return result

    def get_state(self) -> dict:
        """Return current game state for inspection."""
        return {
            "character": self.character,
            "stats": self.stats,
            "alive": self.alive,
            "narrative": self.context,
            "last_roll": self.last_roll,
            "can_undo": len(self.history) > 0,
            "can_force": self.last_invalid and self.last_action is not None
        }

    def undo(self) -> dict:
        """Undo the last action. Returns previous state."""
        if not self.history:
            return {"error": "Nothing to undo"}

        self.context, self.last_roll = self.history.pop()
        self.alive = True  # Resurrect if we undo a death

        return {
            "status": "undone",
            "narrative": self.context,
            "last_roll": self.last_roll
        }
