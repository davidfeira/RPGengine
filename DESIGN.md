# RPG Engine - Design Document

A minimalist, universal text-based RPG powered by LLMs. Players type freeform actions, and the system determines outcomes through simple dice mechanics while an LLM narrates the results.

## Core Philosophy

- **Universally generic** - Play as anyone (caveman, astronaut, dog, wizard) in any setting
- **Minimal mechanics** - Only track what's absolutely necessary
- **LLM as narrator, not referee** - Code handles mechanics, LLM handles storytelling
- **No state bloat** - No HP, conditions, or inventory to hallucinate or lose track of

## Architecture

```
Player Input (freeform text)
        ↓
[Interpreter LLM]
  - Parses intent
  - Determines relevant stat
  - Assigns difficulty (1-5)
        ↓
[Game Engine (Code)]
  - Performs dice roll
  - Determines SUCCESS/FAILURE
        ↓
[Narrator LLM]
  - Receives structured outcome
  - Writes narrative result
  - Presents new situation
        ↓
Player sees narrative output
```

## Stats

Three stats, each ranging from 1-5:

| Stat | Governs |
|------|---------|
| **Mind** | Intelligence, perception, knowledge, cunning, problem-solving, memory |
| **Body** | Strength, agility, endurance, combat, athletics, physical feats |
| **Spirit** | Willpower, charisma, luck, social influence, intuition, (magic if applicable) |

## Character Creation

Players have **9 points** to distribute across the three stats.
- Minimum 1 in each stat
- Maximum 5 in any stat

### Quick Archetypes (Optional)

| Archetype | Mind | Body | Spirit |
|-----------|------|------|--------|
| Clever | 4 | 2 | 3 |
| Tough | 2 | 4 | 3 |
| Charismatic | 3 | 2 | 4 |
| Balanced | 3 | 3 | 3 |

After stats, the player defines who they are and where they start. The LLM takes it from there.

## Resolution Mechanic

```
1d10 + stat - difficulty > 5 = SUCCESS
```

### Difficulty Scale

| Difficulty | Meaning | Example |
|------------|---------|---------|
| 1 | Easy | Climbing a ladder, searching an empty room |
| 2 | Moderate | Picking a simple lock, intimidating a coward |
| 3 | Challenging | Haggling with a shrewd merchant, climbing a slick wall |
| 4 | Hard | Recalling obscure knowledge, outrunning a predator |
| 5 | Extreme | Dodging an arrow, convincing an enemy to switch sides |

### Probability Table

| Stat - Difficulty | Roll Needed | Success % |
|-------------------|-------------|-----------|
| +4 | 2+ | 90% |
| +3 | 3+ | 80% |
| +2 | 4+ | 70% |
| +1 | 5+ | 60% |
| 0 | 6+ | 50% |
| -1 | 7+ | 40% |
| -2 | 8+ | 30% |
| -3 | 9+ | 20% |
| -4 | 10 | 10% |

No action is guaranteed. No action is impossible.

## Game Loop

1. Narrator presents the current situation
2. Player types what they want to do (freeform)
3. Interpreter LLM extracts: `{ stat, difficulty }`
4. Engine rolls dice, determines outcome
5. Narrator LLM receives outcome + context, writes result
6. Loop back to step 1

## What We Don't Track

- **HP** - The narrative decides if you're hurt or dead
- **Conditions** - No poison/tired/injured flags to drift or fixate on
- **Inventory** - If the narrative says you have it, you have it
- **Turns/Time** - Stories end when they end

The narrative IS the game state.

## LLM Responsibilities

### Interpreter LLM
- Parse player's freeform input
- Identify which stat applies (Mind, Body, or Spirit)
- Assign difficulty 1-5
- Should be fast and consistent (can be a smaller model)

**Input:** Player action + brief context
**Output:** `{ "stat": "body", "difficulty": 3 }`

### Narrator LLM
- Receive structured outcome (action, stat, difficulty, SUCCESS/FAILURE)
- Write compelling narrative for the outcome
- Present the new situation and implicit choices
- Maintain tone and setting consistency

**Input:** Structured prompt with context + outcome
**Output:** Narrative paragraph(s) + new situation

## Future Considerations (Not MVP)

- Leveling / stat progression
- Inventory system (code-tracked, not LLM-tracked)
- Branching scenario structures
- Local LLM support (8B models for interpreter, larger for narrator)
- Multiplayer / shared narratives

## Technical Notes

- Build for API first (OpenAI/Anthropic), abstract for easy swap to local
- Interpreter can be a smaller/faster model
- Keep context windows minimal - feed fresh state each turn
- Validate interpreter output (stat must be valid, difficulty must be 1-5)

---

*The goal: the simplest possible RPG that works for any scenario.*
