import random
import json
import os
from openai import OpenAI
from colorama import init, Fore, Style
from prompts import INTERPRETER_PROMPT, NARRATOR_PROMPT, SETUP_PROMPT

init()  # Initialize colorama
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def roll_check(stat_value: int, difficulty: int) -> tuple[bool, int]:
    """Roll 1d10 + stat - difficulty > 5 = success"""
    roll = random.randint(1, 10)
    result = roll + stat_value - difficulty
    return result > 5, roll

def call_llm(prompt: str, system: str = None, json_mode: bool = False) -> str:
    """Call OpenAI API"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": "gpt-4o-mini",
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content

def interpret_action(action: str, context: str) -> dict:
    """Use LLM to determine stat and difficulty for an action"""
    prompt = f"Context: {context}\n\nPlayer action: {action}"
    response = call_llm(prompt, system=INTERPRETER_PROMPT, json_mode=True)

    try:
        result = json.loads(response)
        # Check if invalid action
        if not result.get("valid", True):
            return {"valid": False, "reason": result.get("reason", "That's not possible.")}
        # Validate fields
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
        special_note = "THIS WAS A FORCED IMPOSSIBLE ACTION THAT SUCCEEDED. Reality bent to the character's will. Narrate this as supernatural, absurd, or cosmically lucky."
    elif forced and not success:
        outcome = "FAILURE"
        special_note = "The character attempted the impossible and failed. Reality reasserted itself."
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
    """Generate the opening scene"""
    prompt = SETUP_PROMPT.format(
        character=character,
        mind=stats["mind"],
        body=stats["body"],
        spirit=stats["spirit"]
    )
    return call_llm(prompt)

def create_character() -> tuple[str, dict]:
    """Interactive character creation"""
    print("\n=== CHARACTER CREATION ===\n")

    # Get character concept
    character = input("Who are you? (e.g., 'a stray dog in Tokyo', 'a Roman gladiator', 'a Mars colonist')\n> ").strip()
    if not character:
        character = "a wandering adventurer"

    print(f"\nYou have 9 points to distribute among Mind, Body, and Spirit.")
    print("Each stat must be between 1 and 5.\n")

    while True:
        try:
            mind = int(input("Mind (intelligence, perception, knowledge): "))
            body = int(input("Body (strength, agility, endurance): "))
            spirit = int(input("Spirit (willpower, charisma, luck): "))

            if mind < 1 or body < 1 or spirit < 1:
                print("Each stat must be at least 1. Try again.\n")
                continue
            if mind > 5 or body > 5 or spirit > 5:
                print("Each stat can be at most 5. Try again.\n")
                continue
            if mind + body + spirit != 9:
                print(f"Points must total 9 (you used {mind + body + spirit}). Try again.\n")
                continue

            break
        except ValueError:
            print("Please enter numbers. Try again.\n")

    stats = {"mind": mind, "body": body, "spirit": spirit}
    print(f"\nCharacter created: {character}")
    print(f"Mind: {mind} | Body: {body} | Spirit: {spirit}\n")

    return character, stats

def print_narrative(text: str, dim: bool = False):
    """Print narrative text, optionally dimmed"""
    if dim:
        print(f"{Fore.LIGHTBLACK_EX}{text}{Style.RESET_ALL}")
    else:
        print(text)

def print_roll(stat: str, difficulty: int, roll: int, stat_value: int, result_str: str, lethal: bool):
    """Print the roll result with colors"""
    lethal_warning = f" {Fore.RED}LETHAL{Style.RESET_ALL}" if lethal else ""

    if result_str == "DEATH":
        color = Fore.RED
    elif result_str == "SUCCESS":
        color = Fore.GREEN
    else:
        color = Fore.YELLOW

    total = roll + stat_value - difficulty
    print(f"\n{Fore.CYAN}[{stat.upper()} check, difficulty {difficulty}{lethal_warning}{Fore.CYAN}: rolled {roll} + {stat_value} - {difficulty} = {total} → {color}{result_str}{Style.RESET_ALL}{Fore.CYAN}]{Style.RESET_ALL}\n")

def game_loop():
    """Main game loop"""
    print("\n" + "="*50)
    print(f"  {Fore.CYAN}UNIVERSAL RPG ENGINE{Style.RESET_ALL}")
    print("="*50)

    character, stats = create_character()

    print("\nGenerating your adventure...\n")
    context = opening_scene(character, stats)
    print(context)
    print()

    alive = True
    last_action = None  # Track last action for ! override
    last_invalid = False  # Track if last action was invalid

    while alive:
        action = input(f"{Fore.WHITE}> {Style.RESET_ALL}").strip()

        if not action:
            continue
        if action.lower() in ["quit", "exit", "q"]:
            print("\nThanks for playing!")
            break

        # Check for god mode
        god_mode = False
        if action.lower().startswith("/god "):
            action = action[5:]  # Strip "/god "
            god_mode = True
            print(f"\n{Fore.YELLOW}[GOD MODE]{Style.RESET_ALL}")

        # Check for force override
        force_mode = False
        if action == "!" and last_action and last_invalid:
            action = last_action
            force_mode = True
            print(f"\n{Fore.MAGENTA}[FORCING: {action}]{Style.RESET_ALL}")

        # Interpret the action (skip if forcing)
        if force_mode:
            # Force mode: spirit check, difficulty 5, always possible
            interpretation = {"valid": True, "stat": "spirit", "difficulty": 5, "lethal": False}
        elif god_mode:
            # God mode: skip interpreter, auto-success spirit check
            interpretation = {"valid": True, "stat": "spirit", "difficulty": 1, "lethal": False}
        else:
            interpretation = interpret_action(action, context)

        # Check if action is valid
        if not interpretation.get("valid", True):
            reason = interpretation.get("reason", "That's not possible.")
            print(f"\n{Fore.YELLOW}[INVALID: {reason}]{Style.RESET_ALL}")
            print(f"{Fore.LIGHTBLACK_EX}(Type ! to force attempt anyway){Style.RESET_ALL}\n")
            last_action = action
            last_invalid = True
            continue

        last_invalid = False

        stat = interpretation["stat"]
        difficulty = interpretation["difficulty"]
        lethal = interpretation.get("lethal", False)

        # Roll the dice
        stat_value = stats[stat]
        if god_mode:
            success, roll = True, 10  # Auto-success
        else:
            success, roll = roll_check(stat_value, difficulty)
        died = lethal and not success

        # Show the roll
        result_str = "DEATH" if died else ("SUCCESS" if success else "FAILURE")
        print_roll(stat, difficulty, roll, stat_value, result_str, lethal)

        # Dim the previous context, show new narrative
        # (The new narrative becomes the context for next turn)
        old_context = context
        is_miraculous = force_mode or god_mode
        context = narrate(context, character, stats, action, stat, difficulty, success, died, is_miraculous)
        print(context)
        print()

        # Check for death
        if died:
            print(f"{Fore.RED}{'=' * 50}")
            print(f"  GAME OVER")
            print(f"{'=' * 50}{Style.RESET_ALL}")
            alive = False

if __name__ == "__main__":
    game_loop()
