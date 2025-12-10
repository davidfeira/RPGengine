# RPG Engine Playtesting Notes

## Testing Goals
- Test universal system across diverse characters/settings
- Identify game balance issues (difficulty, lethality, death rate)
- Evaluate narrative quality and state tracking
- Brainstorm new mechanics and improvements
- See what complexity 4o can handle

---

## Session 1: Sapient Rat in Sewers
**Date**: 2024-12-10
**Character**: Sapient rat living in city sewers
**Stats**: Mind 3, Body 2, Spirit 4
**Genre**: Romance → Survival Horror
**Outcome**: Death at turn 10

### Summary
The narrator fully embraced the rat concept, creating a romantic storyline with a human (Elara) in a moonlit garden. Story escalated through: armored rat enemy → fleeing to maintenance room → character bonding → new threat → death while escaping.

### What Worked ✓
- **Universal system works!** Narrator handled non-human protagonist naturally
- **Stat assignments accurate**: Mind for investigation/navigation, Body for combat, Spirit for communication
- **Engaging narrative**: Romance angle was unexpected but worked, good escalation
- **Character development**: Elara accepting the rat as intelligent was a nice moment
- **Appropriate actions**: Squeaking, darting, gnawing, using sewer knowledge all felt natural

### Issues Found ⚠️

#### 1. Difficulty Creep (MAJOR)
Difficulty distribution across 10 turns:
- Turn 1: 3
- Turn 2: 2
- Turn 3: 4
- Turn 4: 4
- Turn 5: 4
- Turn 6: 3
- Turn 7: 4
- Turn 8: 2
- Turn 9: 4
- Turn 10: 3

**Average: 3.3** (should be ~2.5-3.0)
**50% were difficulty 4** (should be rare!)

**Problem examples**:
- Navigating home sewer tunnels = Difficulty 4 (I live here!)
- Searching maintenance room = Difficulty 4 (while in danger, but still just searching)

**Insight**: Interpreter seems to default to difficulty 4 for anything with stakes/tension

#### 2. Lethal Flag Misuse (CRITICAL)
- Turn 9: Searching room while danger approaches = **LETHAL**
- Turn 10: Fleeing through crawlspace = **LETHAL**

**Problem**: Both deaths came from non-combat actions
- Searching shouldn't kill you (should lead to being caught)
- Fleeing shouldn't be lethal (being caught should be lethal)

**Pattern**: Interpreter marks actions lethal when danger is NEARBY, not when action itself is deadly

#### 3. Early Death
- Died at turn 10 (borderline early)
- Death felt unfair: rolled 4/10 while fleeing with worst stat (Body 2)
- 40% success chance on escape action with weapon in hand

### Success Rate Analysis
- 10 actions total
- 5 successes, 5 failures (50% success rate)
- Died on a failure (lethal system is unforgiving)

### Narrative Observations
- Combat-focused escalation (armored rat, hulking figure, glowing eyes)
- Constant new threats introduced
- Story never settled into exploration/character moments for long
- Romance angle dropped quickly in favor of survival horror

---

## Potential Mechanics to Test

### State Tracking Observations
**What 4o handled well:**
- Character concept (sapient rat)
- Companion NPC (Elara's relationship progression)
- Setting consistency (sewers, tunnels, maintenance room)
- Threat escalation (multiple enemies)

**What wasn't tracked:**
- Pipe wrench (found it, dropped it when fleeing - did we even use it?)
- Environmental details (hidden crawlspace appeared conveniently)
- Previous threats (armored rat disappeared, glowing eyes replaced it)

**Complexity 4o could potentially handle:**
- Simple inventory (3-5 items max, code-tracked, passed to narrator)
- Injury state (wounded/healthy flag)
- NPC relationship tracker (Elara's trust level)

### Mechanic Ideas

#### 1. Injury System (HIGH PRIORITY)
**Problem**: Instant death on failed lethal check feels bad
**Solution**: Two-stage system
- First failed lethal check = Injured (-1 to all stats or disadvantage)
- Second failed lethal check while injured = Death
- Successful rest/healing action removes injury

**Benefits**:
- Gives players chance to recover from bad luck
- Creates tension (one more failure = death)
- Encourages retreat/healing actions

#### 2. Luck/Fate Points
**Concept**: Limited resource for rerolls or auto-success
- Start with Spirit stat worth of points (3-5)
- Spend 1 point to reroll a failed check
- Spend 2 points for automatic success
- Regenerate 1 point per significant story milestone?

**Benefits**: Reduces frustration from bad rolls

#### 3. Advantage/Disadvantage (D&D style)
**Concept**: Roll 2d10, take higher (advantage) or lower (disadvantage)
- Advantage: Using character's specialty, good tactics, helpful circumstances
- Disadvantage: Injured, poor positioning, unfavorable conditions

**Benefits**:
- Rewards smart play
- Adds mechanical depth without complex tracking
- 4o just needs to decide advantage/disadvantage per action

#### 4. Success Tiers
**Current**: Pass/Fail binary
**Proposal**: Beat check by 5+ = Critical Success
- Critical Success: Exceptional outcome, bonus effect
- Normal Success: Standard outcome
- Failure: Setback, complication
- Critical Failure (natural 1?): Disaster

**Benefits**: Rewards high rolls, adds variety

#### 5. Context Bonuses
**Concept**: +1 or advantage if action builds on previous success
- Example: Successful stealth → next ambush attack gets bonus
- Example: Successfully convince NPC → next social check with them easier

**Benefits**:
- Encourages strategic sequencing
- Rewards momentum
- Not too complex for 4o to track

---

## Prompt Fix Ideas

### Interpreter Prompt - Difficulty Recalibration
Add to INTERPRETER_PROMPT:
```
Difficulty Guidelines:
1 = TRIVIAL: Routine actions with minor obstacles (climbing a ladder, searching an empty room, basic conversation)
2 = EASY: Simple challenges that trained individuals usually pass (picking a basic lock, recalling common knowledge, persuading a friendly NPC)
3 = MODERATE: Standard challenge requiring skill (DEFAULT for most actions - investigating a scene, haggling with merchants, climbing a rough wall)
4 = HARD: Difficult tasks that often fail without expertise (recalling obscure lore, convincing a hostile NPC, performing acrobatics under pressure)
5 = EXTREME: Heroic feats that rarely succeed (dodging an arrow mid-flight, out-debating a master rhetorician, nearly impossible physical feats)

Default to difficulty 2-3 for most actions. Reserve 4-5 for truly exceptional circumstances.
```

### Interpreter Prompt - Lethal Flag Restriction
Add to INTERPRETER_PROMPT:
```
Lethal Flag Guidelines:
ONLY mark actions as lethal when FAILURE would directly cause death:
- Attacking a deadly enemy in combat
- Falling from lethal height
- Exposure to immediately deadly environment (fire, poison gas, vacuum)
- Performing action where failure = instant death

DO NOT mark as lethal:
- Fleeing or hiding (failure = caught, not dead)
- Searching or investigating (failure = miss clues or get detected)
- Social actions (failure = anger NPC, not death)
- Environmental puzzles (failure = no progress)

When in doubt, mark as non-lethal. Failures should create complications, not instant death.
```

### Narrator Prompt - Variety Reminder
Consider adding:
```
Vary your narrative outcomes:
- Failures can be: setbacks, complications, discoveries, escalations, or partial successes
- Not every encounter needs to be combat
- Include exploration, social, puzzle, and character moments
- Respect the character's concept and setting tone
```

---

## Next Test Sessions

### Session 2 Options:
- **Prehistoric Caveman** (Mind 1, Body 5, Spirit 3) - Test low-Mind character, physical play style
- **Moon Colonist Engineer** (Mind 4, Body 2, Spirit 3) - Test sci-fi setting, technology handling
- **Ghost Haunting Mansion** (Mind 2, Body 1, Spirit 5) - Test non-corporeal, Spirit-focused character

### Questions to Answer:
1. Is difficulty creep consistent across all sessions?
2. Does combat focus happen with all characters or just "dangerous" settings?
3. How does interpreter handle tech vs magic vs mundane?
4. Do high-Mind or high-Spirit characters have better survival rates?
5. Can we get 20+ turn sessions without fixes?

---

---

## Session 2: Prehistoric Caveman Hunter
**Date**: 2024-12-10
**Character**: Prehistoric caveman hunter
**Stats**: Mind 1, Body 5, Spirit 3
**Genre**: Romance → Combat Escalation
**Outcome**: Death at turn 8

### Summary
Romance opening with Ayla (fellow hunter). Immediately transitioned to hunting wild boar, then mountain lion, then dire wolf at sacred altar. Died dodging wolf attack.

### What Worked ✓
- **Body 5 felt powerful**: Succeeded on all Body checks (spear attacks, tactical movement, carrying)
- **Low Mind didn't hurt much**: Only used Mind 1 once (never got tested)
- **Tactical options worked**: Bracing spear, positioning with Ayla
- **NPC tracking**: Ayla's presence maintained throughout
- **Setting appropriate**: Prehistoric vibes, sacred altar, primal combat

### Issues Found ⚠️

#### 1. Combat Treadmill (MAJOR PATTERN)
**Combat escalation sequence:**
1. Wild boar appears → killed
2. Mountain lion appears → killed
3. "Something else" rustling →
4. Fled to glade (success!)
5. Dire wolf appears immediately → died

**Observation**: Every combat victory immediately spawned new enemy
- Tried to escape → still got new enemy in new location
- No breathing room for exploration, dialogue, or character moments
- Feels like endless combat survival mode

**Is this intentional design or interpreter/narrator pushing combat?**

#### 2. Difficulty Still Too High
Difficulty distribution (8 turns):
- Difficulty 2: 25% (2 actions)
- Difficulty 3: 12.5% (1 action)
- Difficulty 4: 62.5% (5 actions)

**Worse than Session 1!** Average 3.38 vs 3.3

**Examples**:
- Attacking boar with Body 5 = Difficulty 4
- Bracing spear defensively with Body 5 = Difficulty 4
- Making spiritual offering with Spirit 3 = Difficulty 4
- Dodging wolf with Body 5 = Difficulty 4

**Pattern**: Any action with stakes = Difficulty 4

#### 3. Died on Best Stat
- Body 5 (highest possible stat)
- Difficulty 4 (standard combat)
- Rolled 4 (40th percentile)
- 4 + 5 - 4 = 5 (FAIL - need >5, not ≥5)
- **50% success chance on defensive action with best stat**

This feels bad! Expert hunter dies dodging.

### Success Rate: 75% (6/8 actions succeeded)
But the 2 failures included death.

### Lethal Flag Rate: 37.5% (3/8 actions)
- All lethal flags on combat actions (appropriate!)
- Better than Session 1's misuse

---

---

## Session 3: Victorian Detective
**Date**: 2024-12-10
**Character**: Victorian detective investigating disappearances
**Stats**: Mind 4, Body 2, Spirit 3
**Genre**: Mystery → Supernatural Horror
**Outcome**: Death at turn 14

### Summary
Found cryptic note, met mysterious figure "the Shadow", formed partnership. Shadow revealed their sister vanished - built strong emotional bond. Investigated supernatural fissure and cursed locket. Died navigating pit after critical fail (rolled 1).

### What Worked ✓
- **NO COMBAT TREADMILL!** 14 turns without endless enemy spawning
- **Relationship persistence confirmed!** Shadow tracked across all turns:
  - Turn 2: Named "the Shadow"
  - Turn 5: Revealed sister's disappearance, grasped hands in solidarity
  - Turn 8: Shadow transformed into "more humanoid figure, a protector"
  - Turn 10: **Bond saved my life** - tendrils recognized our connection
  - Turn 12-13: Shadow wrapped around me protectively
  - Turn 14: Shadow's "desperate clutch" trying to save me as I died
- **Narrative variety**: Mystery, environmental puzzles, relationship building
- **Mind 4 valuable**: Investigation skills used successfully
- **Environmental dangers** instead of constant combat

### Issues Found ⚠️

#### 1. Difficulty Still High
- Difficulty 2: 14% (2 actions)
- Difficulty 3: 36% (5 actions)
- Difficulty 4: 50% (7 actions)
- **Average: 3.36** (still too high)

#### 2. Death on Best Stat (Third Time!)
- Mind 4 (best stat) navigating with partner
- Difficulty 4
- Rolled 1 (critical fail - 10% chance)
- Death felt unlucky, not earned

#### 3. Relationship Breakthrough! ✅
**MAJOR FINDING**: 4o CAN track complex relationships!
- NPC name and identity maintained
- Backstory (sister's disappearance)
- Emotional progression (stranger → ally → protector)
- Physical manifestations (hand-holding, protective wrapping)
- **Mechanical impact**: Bond literally saved life on turn 10
- Character evolution tied to relationship depth

### Success Rate: 64% (9/14 actions)

### Lethal Flag Rate: 21% (3/14 actions)
- Better than combat sessions
- Mostly appropriate (fissure, escaping entity)

---

## Session 4: Lonely Ghost ⭐ BREAKTHROUGH SESSION
**Date**: 2024-12-10
**Character**: Lonely ghost haunting Victorian mansion
**Stats**: Mind 2, Body 2, Spirit 5
**Genre**: Gothic Romance / Emotional Horror
**Outcome**: ✅ **ALIVE** after 26 turns!

### Summary
Discovered music box and locket. Met Elara (spirit keeper), formed deep partnership. Encountered awakening spirits, shadow figure, and Lydia (Elara's great-great-grandmother trapped in anguish). **Resolved entirely through compassion and empathy** - guided Lydia to peace. Loneliness transformed to companionship. New adventures await (shimmering mirror).

### What Worked ✓✓✓

#### 1. RELATIONSHIP PERSISTENCE PERFECTED ✅
**Elara** - Complete character arc across 26 turns:
- Turn 3: Introduced, named "Elara, last of the Keepers"
- Turn 4: Shared knowledge about the Raven
- Turn 5: Extended hand - **"Together, then"** - partnership formed
- Turn 6-13: Gripped hand tighter, maintained barrier, evolved as partner
- Turn 17: **Backstory deepened** - Lydia is her great-great-grandmother!
- Turn 19-21: Flickering but never abandoned despite failures
- Turn 22: **"Intertwining your spirits"** - bond enabled healing breakthrough
- Turn 24: **"As you and Elara"** - inseparable partnership
- Turn 26: **"Loneliness lift, replaced by companionship"** - core theme resolved!

**What 4o successfully tracked:**
- Name, identity, backstory
- Emotional progression and reactions
- Physical connection (hand-holding throughout)
- Family relationship (Lydia as ancestor)
- **Mechanical impact**: Partnership essential to multiple successes

#### 2. NON-COMBAT GAMEPLAY WORKS PERFECTLY ✅
**26 turns of pure social/emotional/investigative play:**
- Investigation: lockets, journals, portraits, runes
- Social interaction: spirits, Elara, Lydia
- Emotional resolution: compassion, empathy, shared pain
- Environmental puzzles: doors, barriers, curses
- **ZERO traditional combat!**

**Conflict resolution methods:**
- Shadow figure: Curse-breaking, not fighting
- Lydia's rage: Embracing her pain, not combat
- Lost souls: Compassion and guidance
- Everything solved via Spirit/Mind

#### 3. COMPLETE NARRATIVE ARC ✅
**Act 1 - Loneliness** (Turns 1-5):
- Discover locket and music box
- Meet Elara
- Form partnership

**Act 2 - Investigation** (Turns 6-16):
- Awaken other spirits
- Face shadow threat with protective barrier
- Discover Lydia's tragic story
- Learn about cursed locket

**Act 3 - Resolution** (Turns 17-26):
- Reveal Lydia's identity (Elara's ancestor)
- Read journal of tragic love
- Embrace Lydia's pain instead of fighting
- Guide her to peace through compassion
- **Transform loneliness into companionship**
- Hint at continuing adventures

#### 4. DIFFICULTY IMPROVED! ✅
Distribution (26 turns):
- Difficulty 2: 42% (11 actions)
- Difficulty 3: 35% (9 actions)
- Difficulty 4: 23% (6 actions)

**Average: 2.8** - MUCH BETTER than combat sessions (3.3-3.4)!

**Why the improvement:**
- Spirit 5 dominated (17/26 actions = 65%)
- Social/emotional actions got lower difficulty
- Combat actions (difficulty 4) were rare
- Character optimized for non-combat approach

#### 5. SURVIVED BAD LUCK CLUSTER ✅
**Rolled six terrible results:**
- Turn 2: 2
- Turn 6: 1 (critical fail)
- Turn 12: 2
- Turn 19: 1 (critical fail)
- Turn 20: 1 (critical fail - THREE natural 1s!)
- Turn 21: 2

**Survived because:**
- Most weren't lethal
- Elara helped recover
- Failures created story complications, not deaths
- Non-combat setting more forgiving

#### 6. LONGEST SESSION BY FAR ✅
- 26 turns (vs 8-14 previous)
- Reached natural story resolution
- Still alive with new adventures beckoning
- Proved 20+ turn sessions ARE possible

### Issues Found ⚠️

#### 1. Invalid Action Detection
- Turn 13: "Pause to catch breath and thank Shadow" rejected
- System wants active choices, not reflective moments
- Could be feature or bug - limits roleplay moments?

#### 2. Critical Fail Clustering
- Three natural 1s in four turns (19, 20, 21)
- 10% probability each, getting multiple is brutal
- Consider: Reroll on natural 1? Or "fail forward" mechanic?

### Success Rate: 69% (18/26 actions)
Lower than combat sessions but survived!

### Lethal Flag Rate: 8% (2/26 actions)
- Turn 11: Protecting barrier (appropriate)
- Turn 12: Reaching for ancient soul (appropriate)
- Much lower than combat sessions

---

## Running Tally

### Sessions Completed: 4
- Sapient Rat: Death turn 10
- Prehistoric Caveman: Death turn 8
- Victorian Detective: Death turn 14
- **Lonely Ghost: ALIVE turn 26** ⭐

### Average Session Length: 14.5 turns (was 9 after 2 sessions)

### Death Rate: 75% (3/4) - Down from 100%!

### Difficulty Distribution (Combined 64 actions):
- Difficulty 1: 0% (0 actions)
- Difficulty 2: 27% (17 actions) - Improving!
- Difficulty 3: 30% (19 actions)
- Difficulty 4: 44% (28 actions) - Down from 56%!
- Difficulty 5: 0% (0 actions)

**Average: 3.17** (down from 3.35)

### Lethal Flag Rate: 16% (10/64 actions)
- Session 1: 20% (2/10, both inappropriate)
- Session 2: 37.5% (3/8, all appropriate)
- Session 3: 21% (3/14, mostly appropriate)
- Session 4: 8% (2/26, all appropriate)

---

## Design Philosophy Notes

**What makes this system special:**
- Universal (any character, any setting)
- Minimal state (just stats + narrative)
- LLM handles story, code handles mechanics
- Simple but deep

**Core tension to balance:**
- Too easy = boring, no tension
- Too hard = frustrating, unfair deaths
- Sweet spot = tense but winnable, deaths feel earned

**Current state**: Balance depends on character build
- Combat characters: Slightly too hard, deaths can feel unlucky
- Social/Spirit characters: Well-balanced, engaging stories possible

---

## Emerging Patterns

### Pattern 1: Combat Treadmill (CONDITIONAL)
**Sessions 1-2**: Kill enemy → new enemy appears → repeat
**Sessions 3-4**: Environmental/social challenges instead

**KEY FINDING**: Combat treadmill appears with combat-focused characters!
- Rat (Body 2) & Caveman (Body 5): Combat escalation
- Detective (Mind 4) & Ghost (Spirit 5): Mystery/social focus

**Character design influences narrative!**
- High Body → more combat scenarios
- High Mind/Spirit → more investigation/social scenarios
- Ghost with Body 2 physically CAN'T fight → narrator adapted!

### Pattern 2: Difficulty Scales With Gameplay Type
**Combat-focused sessions (Rat, Caveman):**
- Average difficulty: 3.3-3.4
- 50-62% difficulty 4

**Social/Investigation sessions (Detective, Ghost):**
- Average difficulty: 2.8-3.4
- 23-50% difficulty 4

**Ghost session specifically (Spirit 5 optimized):**
- Average difficulty: 2.8
- Only 23% difficulty 4
- 42% difficulty 2

**Conclusion**: System rewards stat specialization!

### Pattern 3: Stat Specialization Matters
**Combat characters using combat stats:**
- Narrow margins (stat 5 vs difficulty 4 = coin flip)
- Dies on best stat

**Specialized non-combat character:**
- Spirit 5 ghost survived 26 turns
- Used Spirit 65% of the time
- Lower difficulties on specialty

**Implication**: Min-maxing > balanced stats

### Pattern 4: Relationship Mechanics Work!
**Confirmed across Sessions 3-4:**
- 4o tracks NPC names, backstory, emotions
- Relationships progress and deepen
- **Mechanical impact**: Bonds affect outcomes
- Partnerships persist through failures
- Character evolution tied to relationships

**This is a HUGE feature!**
- Opens up romance, betrayal, faction play
- Companions can be central to gameplay
- Emotional stakes as compelling as physical

### Pattern 5: Non-Combat Gameplay Viable
**Ghost session proved:**
- 26 turns without combat
- Complete story arc
- Engaging throughout
- Resolution through empathy, not violence

**Requirements:**
- Character built for it (high Spirit/Mind)
- Player leans into social/investigation
- Narrator adapts to character concept

### Pattern 6: Session Length Correlation
**Death sessions:** 8-14 turns (average: 10.7)
**Survival session:** 26 turns

**Hypothesis**:
- Deaths cut stories short
- Successful characters reach natural conclusions
- Non-combat has more "breathing room"

---

## Session 5: Moon Colonist Engineer ⚠️ TONE PROBLEM
**Date**: 2024-12-10
**Character**: Pragmatic engineer maintaining life support at Moonbase Tycho
**Stats**: Mind 4, Body 2, Spirit 3
**Genre**: **Absurd Comedy** (FORCED BY RANDOM TONE)
**Outcome**: Abandoned at turn 6 (testing issue, not game issue)

### Summary
Random tone generator selected "absurd comedy" - entire session became: inflatable oxygen dome turns into balloon animal, sentient broccoli staging rebellion, Dr. Ramirez negotiating with vegetables, rogue tomatoes, luminescent spores, hidden bio-engineering lab. While technically functional, tone felt jarring and disconnected from "pragmatic engineer" character concept.

### What Worked ✓
- **Dr. Ramirez tracked** (biologist NPC maintained)
- **Mind 4 used correctly** (6/6 actions used Mind)
- **Mystery escalation** (balloon animal → broccoli revolt → hidden lab → Sector Theta)
- **No combat!** Investigation/problem-solving focus
- **Difficulty reasonable**: 2, 2, 3, 4, 4, 3 (avg 3.0)

### Critical Issue Found ⚠️⚠️⚠️

#### Random Tone Selection is Harmful
**Problem**: SETUP_PROMPT randomly picks tone from:
- Epic Fantasy
- Gritty Noir
- Whimsical Adventure
- Cosmic Horror
- **Absurd Comedy** ← Got this one

**What went wrong:**
- "Pragmatic engineer at moonbase" concept suggests hard sci-fi
- Random "absurd comedy" tone made it silly (sentient vegetables)
- Tone felt **scripted and forced**, not emergent
- Disconnect between character concept and narrative style
- No way for player to influence or change tone

**Examples of tone mismatch:**
- Opening: "air smelled of recycled pizza and something decidedly more questionable"
- Oxygen dome → "balloon animal" → cat trying to swat it
- Communications: "broccoli's staging a revolt again"
- Cafeteria: "Broccoli figures barricading entrance with salad tongs as weapons"

**Why it's a problem:**
1. **Player agency removed** - Can't steer tone, stuck with random selection
2. **Character concept ignored** - "Pragmatic" doesn't fit "absurd"
3. **Setting broken** - Hard sci-fi → wacky comedy ruins immersion
4. **Unpredictable experience** - Same character gets wildly different games

### Recommendations

#### Option 1: Remove Random Tone (RECOMMENDED)
- Let narrator choose tone based on character concept
- "Pragmatic engineer" → realistic/technical
- "Haunted ghost" → gothic/atmospheric
- "Caveman hunter" → primal/survival
- Trust 4o to match tone to concept

#### Option 2: Let Player Choose Tone
At character creation:
```
What tone would you like?
1. Realistic/Serious
2. Light/Humorous
3. Dark/Horror
4. Epic/Dramatic
5. Let narrator decide
```

#### Option 3: Dynamic Tone (Advanced)
- Start neutral
- Let player's actions influence tone
- Serious choices → serious narrative
- Silly choices → lighter narrative
- Tone emerges from gameplay

### What This Session Taught Us

**Positive findings:**
- System handles sci-fi setting fine (technology, moonbase, hydroponics)
- Mind-focused character works (all 6 actions used Mind)
- Investigation/problem-solving can drive story without combat
- NPC relationships still track in non-fantasy settings

**But tone override ruined it:**
- Even good mechanics feel bad with wrong tone
- Immersion matters more than we thought
- Random elements should enhance, not hijack experience

### Session Stats (for completeness)
- **Turns**: 6 (abandoned due to tone issue)
- **Difficulty avg**: 3.0 (reasonable!)
- **Mind usage**: 100% (6/6 actions)
- **Lethal flags**: 0% (0/6)
- **Success rate**: 100% (6/6)
- **NPC tracking**: Yes (Dr. Ramirez)

**Note**: Stats look fine mechanically, but tone made session unplayable from enjoyment perspective.

---

## Running Tally (UPDATED)

### Sessions Completed: 5 (4 full, 1 abandoned)
- Sapient Rat: Death turn 10
- Prehistoric Caveman: Death turn 8
- Victorian Detective: Death turn 14
- Lonely Ghost: ALIVE turn 26 ⭐
- Moon Engineer: Abandoned turn 6 (tone issue)

### Death Rate: 60% (3/5 completed sessions)

### NEW CRITICAL FINDING: Random Tone System Must Go
**Priority**: HIGH
**Impact**: Ruins otherwise functional game
**Fix**: Remove tone randomization from SETUP_PROMPT

---

## IMPLEMENTED FIX: Removed Random Tone System
**Date**: 2024-12-10

### Changes Made
1. **engine.py**: Removed `STORY_TONES` list and `random.choice()` call
2. **prompts.py**: Updated `SETUP_PROMPT` to infer tone from character concept
3. **New approach**: LLM matches tone to character naturally
   - "Pragmatic engineer" → technical/realistic
   - "Lonely ghost" → gothic/atmospheric
   - "Caveman hunter" → primal/survival

### Rationale
- Random tone selection caused jarring mismatches (engineer + comedy = broccoli revolt)
- Character concept already implies appropriate tone
- Trust 4o-mini to match tone based on context
- Ghost session (Session 4) worked perfectly without explicit tone guidance
- Removes forced, scripted feeling
- Increases immersion and player agency

### Testing Needed
- Retry moon engineer scenario to see if tone improves
- Test if LLM consistently picks appropriate tones
- Verify variety still exists (not all stories same tone)

---

## IMPLEMENTED FIX: Lethal Flags & Non-Combat Emphasis
**Date**: 2024-12-10

### Changes Made to INTERPRETER_PROMPT
1. **Difficulty recalibration**: Added "DEFAULT for most actions" to difficulty 3, emphasized 4-5 should be rare
2. **Strict lethal guidelines**:
   - ONLY mark lethal when failure = direct death
   - Explicitly exclude: fleeing (caught, not dead), hiding (detected, not dead), searching in danger (found, not dead)
   - "When in doubt, mark as NON-lethal"

### Changes Made to NARRATOR_PROMPT
Added "VARY YOUR NARRATIVE APPROACH" section:
- Not every conflict needs combat
- Failures create complications, not just new enemies
- Respect character concepts (low Body = offer non-combat solutions)
- High Mind/Spirit should face mental/social challenges
- Encourage negotiation, discovery, relationships, problem-solving

### Rationale
**From user feedback**: "i was running into the issue of like failing a roll 3 times while pinned down and extremely injured. like what am i supposed to do there."
- Problem isn't difficulty being too hard
- Problem is getting into unwinnable "pinned down" situations
- Caused by marking fleeing/searching as lethal when should just get caught
- **Combat should be hard** - but you shouldn't be trapped with no escape

**Design direction**: "lean in on non combat situations so its fine if combat is hard"
- Ghost session (non-combat) was most successful and engaging
- System's strength is social/emotional/investigation gameplay
- Combat can be deadly if non-combat alternatives exist

### Testing Plan
Need to verify non-combat success wasn't a fluke:
1. **One combat test** (warrior/fighter) - verify combat is still challenging but fair
2. **Multiple non-combat tests**:
   - Social/political intrigue (diplomat, noble, politician)
   - Investigation/mystery (journalist, researcher, private eye)
   - Exploration/survival (explorer, scientist, wanderer)
   - Relationship-focused (therapist, matchmaker, social worker)
   - Creative problem-solving (inventor, artist, con artist)

### Success Metrics
- Lethal flags only on actual death actions (not fleeing/hiding)
- Non-combat sessions reach 15+ turns consistently
- Variety of narrative types (not all defaulting to combat)
- Clear escape routes from dangerous situations
- Failures create interesting complications, not death spirals

---

## COMPREHENSIVE FINDINGS SUMMARY

### What Works ✅
1. **Universal System** - Any character concept works (rat, caveman, detective, ghost, engineer)
2. **Relationship Persistence** - 4o-mini tracks NPCs across 26+ turns (names, backstory, emotions, mechanical impact)
3. **Non-Combat Gameplay** - 26-turn social/emotional story proved it's viable and engaging
4. **Stat Specialization** - High stat in one area (Spirit 5) performs better than balanced stats
5. **Character Design Influences Narrative** - High Body → combat, High Mind/Spirit → investigation/social
6. **Technology Consistency** - System handles fantasy, prehistoric, Victorian, supernatural, and sci-fi settings
7. **Investigation/Mystery Works** - Detective and engineer sessions showed problem-solving gameplay
8. **Variety Possible** - Successfully tested romance, horror, mystery, comedy (when appropriate)

### Major Issues ⚠️

#### 1. Difficulty Too High (CRITICAL)
- **Average across all sessions: 3.17** (should be ~2.5)
- **44% of actions are difficulty 4** (should be ~20%)
- **Pattern**: Interpreter defaults to difficulty 4 whenever stakes are present
- **Impact**: Even specialists (stat 5) have only ~50% success on their specialty
- **Examples**:
  - Navigating home territory = Difficulty 4
  - Expert hunter dodging = Difficulty 4
  - Caveman with Body 5 attacking = Difficulty 4

**Proposed Fix**: Add explicit difficulty calibration to INTERPRETER_PROMPT
```
Default to difficulty 2-3 for most actions. Reserve 4-5 for truly exceptional circumstances.
Difficulty 4 = Hard (often fails without expertise)
Difficulty 5 = Extreme (heroic feat, rarely succeeds)
```

#### 2. Deaths Feel Unlucky, Not Earned (HIGH PRIORITY)
- **75% of deaths occurred on character's BEST stat**
- All death sessions ended 8-14 turns (average 10.7)
- Deaths from single bad rolls (40-50% success rate)
- No recovery mechanic from near-death experiences

**Examples**:
- Detective (Mind 4) rolled 1 navigating with partner (critical fail)
- Caveman (Body 5) rolled 4 dodging (coin flip failed)
- Rat (Body 2) rolled 4 fleeing through crawlspace (40% success, died)

**Proposed Fix Options**:
- **Injury System** (two-stage death): First lethal fail = wounded (-1 all stats), second = death
- **Luck Points** (Spirit stat worth of rerolls)
- **Advantage/Disadvantage** (roll 2d10, take higher/lower based on circumstances)
- **Critical Fail Protection** (natural 1 = failure but not death, or reroll once per session)

#### 3. Lethal Flag Misuse (IMPROVING)
- Session 1: Misused (fleeing/searching marked lethal)
- Sessions 2-4: Improved (mostly appropriate)
- **Root issue**: Interpreter marks actions lethal when danger is NEARBY, not when the action itself causes death

**Proposed Fix**: Add explicit guidelines to INTERPRETER_PROMPT
```
ONLY mark lethal when FAILURE would directly cause death:
- Attacking deadly enemy in combat
- Falling from lethal height
- Immediate deadly environment

DO NOT mark lethal:
- Fleeing/hiding (failure = caught, not dead)
- Searching (failure = detected, not dead)
```

#### 4. Random Tone System (FIXED ✅)
- **Was**: Randomly assigned tone caused mismatches (engineer + comedy = broccoli revolt)
- **Now**: LLM infers tone from character concept
- **Testing needed**: Verify this works consistently

#### 5. Combat Treadmill (CONDITIONAL - Character Dependent)
- High Body characters → endless combat spawns
- High Mind/Spirit characters → investigation/social focus
- **Root cause**: Character design signals narrator to create certain scenarios
- **Not necessarily a bug**: System adapts to character archetype
- **Consider**: Is this desirable? Or should low-Body characters still face combat?

### Medium Issues 🔶

#### 6. No Difficulty 1 Actions (54 actions, zero difficulty 1)
- Suggests calibration is off
- Even trivial actions get difficulty 2+
- May contribute to overall difficulty being too high

#### 7. Session Length Disparity
- Death sessions: 8-14 turns (feels short, stories cut off)
- Survival session: 26 turns (felt complete)
- **Question**: Should we aim for longer sessions? Or is 8-14 acceptable?

#### 8. Success Rate Inconsistency
- Combat characters: 50-75% success (tense but frustrating)
- Social characters: 69% success (challenging but fair)
- Specialists survive, generalists die

### Minor Issues 📝

#### 9. Invalid Action Detection
- "Pause to catch breath and thank Shadow" rejected (Turn 13, ghost session)
- System wants active choices, not reflective moments
- **Question**: Feature or bug? Should we allow reflective roleplay?

#### 10. Critical Fail Clustering
- Ghost session: Three natural 1s in four turns (19, 20, 21)
- 10% chance each, getting multiple is brutal
- Consider critical fail mitigation?

---

## Key Insights for Design Direction

### 1. Stat Specialization > Balanced Stats
- Ghost (Spirit 5): Survived 26 turns
- Caveman (Body 5): Died turn 8 using Body constantly
- Detective (Mind 4): Died turn 14 using Mind
- **Pattern**: High stats aren't enough if difficulty is too high

### 2. Non-Combat is the Breakthrough
- Longest session (26 turns) had zero combat
- Most engaging narrative (Elara relationship arc)
- Lower difficulty average (2.8 vs 3.3+)
- **Implication**: System excels at social/emotional/investigation gameplay

### 3. Character Design Guides Narrative Type
- This might be a feature, not a bug
- Gives players agency to choose gameplay style via stats
- Body 5 = combat-heavy, Spirit 5 = social-heavy
- **Question**: Should we lean into this or fight it?

### 4. Relationship Mechanics are Gold
- Most memorable moments involved NPCs (Elara, Shadow, Dr. Ramirez)
- Emotional stakes as compelling as survival stakes
- 4o-mini handles complexity surprisingly well
- **Opportunity**: Could add light inventory/relationship tracking to prompts

### 5. Difficulty Calibration is the Priority Fix
- Single biggest issue affecting all sessions
- Makes specialists feel weak (stat 5 = coin flip)
- Easy to fix (just update INTERPRETER_PROMPT)
- Would immediately improve game feel

---

## Proposed Changes (Priority Order)

### Priority 1: MUST FIX
1. ✅ **Remove random tone** (DONE)
2. **Recalibrate difficulty** (update INTERPRETER_PROMPT with explicit guidelines)
3. **Fix lethal flag guidelines** (update INTERPRETER_PROMPT)

### Priority 2: STRONGLY CONSIDER
4. **Injury system** (two-stage death to reduce frustration)
5. **Luck points** (Spirit stat worth of rerolls)
6. **Test tone fix** (retry moon engineer, verify consistency)

### Priority 3: EVALUATE LATER
7. Advantage/disadvantage system
8. Success tiers (critical success = bonus effect)
9. Context bonuses (chain successes)
10. Critical fail mitigation
11. Invalid action policy (allow reflective moments?)
12. Light inventory tracking

---

## Next Steps

**Option A - Implement Core Fixes Now**:
1. Update INTERPRETER_PROMPT (difficulty + lethal guidelines)
2. Add injury system
3. Add luck points
4. Test with 2-3 sessions to verify improvements

**Option B - More Testing First**:
1. Test tone fix (retry moon engineer)
2. Run 2-3 more varied scenarios (modern, sci-fi, fantasy)
3. Gather more data on difficulty patterns
4. Then implement fixes

**Option C - Targeted Testing**:
1. Test one scenario with manually adjusted difficulty (use god mode to simulate)
2. See if lowering difficulty to 2-3 average improves experience
3. If yes, implement INTERPRETER_PROMPT fix
4. If no, consider different solutions
