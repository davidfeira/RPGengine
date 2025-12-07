#!/usr/bin/env python
"""
CLI interface for Claude Code to play the RPG.
Persists game state between calls.

Usage:
    python play_cli.py start "a curious goblin" 3 3 3
    python play_cli.py action "look around"
    python play_cli.py state
    python play_cli.py undo
    python play_cli.py force   # Force last invalid action
    python play_cli.py god "fly to the moon"  # God mode action
"""

import sys
import json
import pickle
from pathlib import Path
from engine import RPGGame

STATE_FILE = Path(__file__).parent / ".game_state.pkl"


def load_game() -> RPGGame:
    """Load game state from file, or create new game."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "rb") as f:
            return pickle.load(f)
    return RPGGame()


def save_game(game: RPGGame):
    """Save game state to file."""
    with open(STATE_FILE, "wb") as f:
        pickle.dump(game, f)


def output(data: dict):
    """Print JSON output for Claude to parse."""
    print(json.dumps(data, indent=2))


def cmd_start(args: list):
    """Start a new game: start "character" mind body spirit"""
    if len(args) < 4:
        output({"error": "Usage: start 'character name' mind body spirit"})
        return

    character = args[0]
    try:
        mind, body, spirit = int(args[1]), int(args[2]), int(args[3])
    except ValueError:
        output({"error": "Stats must be integers"})
        return

    game = RPGGame()
    result = game.start(character, mind, body, spirit)
    save_game(game)
    output(result)


def cmd_action(args: list):
    """Take an action: action "do something" """
    if not args:
        output({"error": "Usage: action 'your action'"})
        return

    action = " ".join(args)
    game = load_game()

    if not game.character:
        output({"error": "No game in progress. Use 'start' first."})
        return

    result = game.take_action(action)
    save_game(game)
    output(result)


def cmd_force(args: list):
    """Force the last invalid action."""
    game = load_game()

    if not game.character:
        output({"error": "No game in progress. Use 'start' first."})
        return

    if not game.last_invalid:
        output({"error": "No invalid action to force"})
        return

    result = game.take_action("", force=True)
    save_game(game)
    output(result)


def cmd_god(args: list):
    """God mode action (auto-success): god "do something" """
    if not args:
        output({"error": "Usage: god 'your action'"})
        return

    action = " ".join(args)
    game = load_game()

    if not game.character:
        output({"error": "No game in progress. Use 'start' first."})
        return

    result = game.take_action(action, god_mode=True)
    save_game(game)
    output(result)


def cmd_state(args: list):
    """Get current game state."""
    game = load_game()
    output(game.get_state())


def cmd_undo(args: list):
    """Undo the last action."""
    game = load_game()
    result = game.undo()
    save_game(game)
    output(result)


def cmd_help(args: list):
    """Show help."""
    output({
        "commands": {
            "start": "start 'character' mind body spirit - Start new game",
            "action": "action 'text' - Take an action",
            "force": "force - Force last invalid action (spirit check diff 5)",
            "god": "god 'text' - God mode action (auto-success)",
            "state": "state - Show current game state",
            "undo": "undo - Undo last action"
        }
    })


COMMANDS = {
    "start": cmd_start,
    "action": cmd_action,
    "force": cmd_force,
    "god": cmd_god,
    "state": cmd_state,
    "undo": cmd_undo,
    "help": cmd_help,
}


def main():
    if len(sys.argv) < 2:
        cmd_help([])
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    if cmd in COMMANDS:
        COMMANDS[cmd](args)
    else:
        output({"error": f"Unknown command: {cmd}", "valid_commands": list(COMMANDS.keys())})


if __name__ == "__main__":
    main()
