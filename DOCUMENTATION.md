# Bardic AI - Technical Documentation

**AI-Powered D&D Dungeon Master with Voice I/O and Cinematic UI**

Local-first AI Dungeon Master using Whisper (speech-to-text), Qwen 2.5 (narrative generation), and Coqui TTS (text-to-speech). Features push-to-talk voice input, player-triggered dice rolls, real-time character sheet, and combat HUD.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Current System (Old Architecture)](#current-system-old-architecture)
3. [New Engine (Built, Pending Integration)](#new-engine-built-pending-integration)
4. [Foundation Data](#foundation-data)
5. [Campaign Formats](#campaign-formats)
6. [UI Components](#ui-components)
7. [API Routes](#api-routes)
8. [File Structure](#file-structure)
9. [Known Issues & Limitations](#known-issues--limitations)
10. [TODO List (Critical)](#todo-list-critical)

---

## Architecture Overview

Bardic AI has **two parallel architectures** currently:

1. **Old System** (currently running): Checkpoint-based campaigns, old DM engine
2. **New Engine** (built, not integrated): Node-based navigation, rich schemas, rules engine

### Core Pipeline (Both Systems)

```
Player speaks → Whisper STT → Text → DM Engine → Narrative + Actions → Qwen LLM →
  → Coqui TTS → Audio + Subtitles → Player hears
```

### Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Voice Input** | Whisper (OpenAI) | Speech-to-text transcription |
| **Voice Output** | Coqui TTS XTTS v2 | Text-to-speech with voice cloning |
| **LLM** | Qwen 2.5 14B (Ollama) | Narrative generation, NPC dialogue |
| **D&D Data** | Open5e API + D&D 5e SRD | Rules, monsters, spells, items |
| **Frontend** | Flask + Jinja2 | Game UI, character creation |
| **Backend** | Python 3.13 | Game logic, state management |

### Why Two Systems Exist

- **Old system** (~5 checkpoints/campaign): Simple, working, but limited locations
- **New engine** (20-30+ nodes/chapter): Rich state tracking, validation, not integrated yet
- Migration pending - new engine addresses location context and validation issues

---

## Current System (Old Architecture)

**Status:** ✅ Currently running in production

### DM Engine ([services/dm_engine.py](services/dm_engine.py))

**Hybrid approach**: Scripted content + AI fallback

- **Pre-scripted content** (instant): Checkpoint narration, NPC dialogue, choices
- **Ollama calls** (slower): Only for unexpected player actions

#### Key Methods

```python
enter_checkpoint(checkpoint_id)  # Pre-scripted narration, instant
make_choice(choice_index)        # Pre-scripted transitions, instant
talk_to_npc(npc_name)           # Pre-scripted dialogue topics
ask_about(topic)                # Scripted if available, Ollama fallback
process_custom_action(input)    # Full Ollama call for free-form actions
```

#### Recent Additions (for UI)

- `detect_roll_needed(player_input, narration)` - Detects when dice rolls are needed
- Returns `awaiting_roll` object with `{type, skill, ability, dc, reason}`
- Integrated into `/game/action` and `/game/voice_action` responses

#### DM Addressing Detection

Player can address DM explicitly to trigger action narration:
- "Joe, I walk to the door"
- "Okay DM, let's attack"
- Strips DM name, narrates action instead of NPC dialogue

### Campaign System (Old Format)

**Checkpoint-based**: ~5-12 locations per campaign

File: Single JSON at `data/campaigns/{name}.json`

```json
{
  "id": "campaign_id",
  "title": "Campaign Title",
  "category": "one-shot|short|medium|epic",
  "starting_checkpoint": "checkpoint_id",
  "checkpoints": {
    "checkpoint_id": {
      "name": "Location Name",
      "description": "Full description",
      "entrance_narration": "What DM says when entering",
      "choices": [
        {"text": "Go north", "next_checkpoint": "forest", "narration": "You head north..."}
      ],
      "npcs_structured": [
        {"name": "Marcus", "role": "quest_giver", "dialogue_topics": {...}}
      ],
      "items_available": ["sword", "potion"],
      "enemies": ["goblin", "wolf"],
      "auto_quests": [{"name": "Quest", "description": "..."}]
    }
  }
}
```

### Current Campaigns

1. **The Goblin's Gambit** - One-shot, 2hrs (12 checkpoints) ✅
2. **Curse of Ravenmoor Manor** - Short, 4-6hrs (17 checkpoints) ✅
3. **Shadow of the Crimson Drake** - Medium, 15hrs (23 checkpoints) ✅
4. **Rise of the Lich King Ch.1** - Epic, ongoing (24 checkpoints) ✅

### Game State ([models/game_state.py](models/game_state.py))

Simple character tracking:

```python
class Character:
    name: str
    char_class: str
    hp: int
    max_hp: int
    strength, dexterity, constitution, intelligence, wisdom, charisma: int
    inventory: List[str]
    gold: int
```

```python
class GameState:
    character: Character
    campaign_id: str
    current_checkpoint: str
    quests: List[Quest]
    combat_active: bool
    enemies: List[Dict]
    current_speaker: Optional[str]  # NPC currently talking
```

### Limitations of Old System

1. **Location Context Lost**: Only ~5 checkpoints means vague locations
   - "You're in the forest" vs "You're at the ancient oak by the stream bend"
2. **No Validation**: No checks for impossible actions (talking to absent NPCs)
3. **No Soft Gates**: Can't warn player before leaving (e.g., "Sure you want to leave without supplies?")
4. **Dice Rolls After Response**: Roll happens AFTER narrative, doesn't affect story
5. **Keyword Detection Too Aggressive**: "buy supplies" triggers Deception check

---

## New Engine (Built, Pending Integration)

**Status:** 🔨 Built, tested, NOT integrated into Flask app

**Location:** `/home/robbhimself/bardic-ai/engine/`

### Architecture

```
StateManager (game_state.py)
    ↓
┌───────────────┬────────────────┬──────────────┬─────────────────┐
│   Loaders     │  Rules Engine  │  DM Engine   │  Schemas        │
│  (loaders.py) │(rules_engine.py)│(dm_engine_v2)│ (schemas/*.py)  │
└───────────────┴────────────────┴──────────────┴─────────────────┘
    ↑                                                      ↑
Foundation Data                                    Campaign Data
(data/foundation/)                           (data/campaigns/*/*)
```

### Key Components

#### 1. StateManager ([engine/state_manager.py](engine/state_manager.py))

Centralized game state orchestration:

```python
class StateManager:
    def __init__(self, campaign, nodes, npcs, encounters, character):
        # Loads everything, initializes state

    def get_current_node(self) -> Node
    def get_available_exits(self) -> Dict[str, NodeExit]
    def move_to_node(self, node_id) -> Tuple[bool, str]
    def execute_significant_action(self, action_id) -> Tuple[bool, str, Dict]

    # NPC Relationships
    def get_npc_disposition(self, npc_id) -> int
    def get_npc_attitude(self, npc_id) -> str  # "hostile", "friendly", etc.
    def modify_relationship(self, npc_id, disposition, trust, event)
    def get_npc_greeting(self, npc_id) -> str
    def get_npc_knowledge(self, npc_id, topic) -> Optional[str]

    # Conditions & Quests
    def check_condition(self, condition_expr) -> bool  # "flag1 && flag2"
    def set_flag(self, flag, value=True)
    def has_flag(self, flag) -> bool
    def start_quest(self, quest_id, name, description)

    # AI Context
    def get_context_for_ai(self) -> Dict
```

#### 2. Schemas ([engine/schemas/](engine/schemas/))

Rich dataclasses for everything:

**[game_state.py](engine/schemas/game_state.py):**
```python
@dataclass
class Character:
    name, race, char_class, level, experience
    ability_scores: AbilityScores  # str, dex, con, int, wis, cha
    hp: HitPoints  # current, max, temp
    armor_class, speed, proficiency_bonus
    proficiencies: Proficiencies  # skills, armor, weapons, tools
    inventory: List[InventoryItem]
    gold: Currency  # cp, sp, gp, pp
    class_features, conditions

@dataclass
class GameState:
    session_id, campaign_id, started_at, last_saved
    character: Character
    location: Location  # chapter_id, node_id, previous_node
    story_progress: StoryProgress  # flags, quests
    relationships: Dict[str, NPCRelationship]
    conversation: ConversationState
    combat: CombatState
    world: WorldState  # time_of_day, weather, days_elapsed
    action_history, nodes_visited
```

**[campaign.py](engine/schemas/campaign.py):**
```python
@dataclass
class Node:
    node_id, name
    description: NodeDescription  # short, long, image_prompt
    chapter_id
    npcs_present: List[NPCPresence]  # role, required, topics
    items_available: List[ItemForSale]
    encounters_possible: List[str]
    exits: Dict[str, NodeExit]  # target_node, conditions, soft_gates
    significant_actions: Dict[str, SignificantAction]  # story events

@dataclass
class SignificantAction:
    action_id, trigger_description
    requires_flags, requires_items, requires_relationship
    sets_flags, grants_items, grants_quest, completes_objective
    updates_relationships, grants_xp
    success_prompt, failure_prompt
```

**[npc.py](engine/schemas/npc.py):**
```python
@dataclass
class NPC:
    npc_id, name, role
    appearance: NPCAppearance  # short, detailed, portrait_prompt
    personality: NPCPersonality  # traits, ideals, bonds, flaws
    voice: NPCVoice  # style, speech_patterns, catchphrases
    base_disposition: int  # -100 to 100
    knowledge: Dict[str, KnowledgeTopic]  # what they know
    dialogue: DialogueLines  # greetings, farewells, custom
    relationship_thresholds: NPCRelationshipConfig
    quests_can_give: List[str]
```

**[encounter.py](engine/schemas/encounter.py):**
```python
@dataclass
class Encounter:
    encounter_id, name
    difficulty: str  # "easy", "medium", "hard", "deadly"
    enemies: List[EnemyInstance]
    environment_effects: List[str]
    victory_conditions, defeat_conditions
    rewards: CombatRewards  # xp, gold, items
```

#### 3. Loaders ([engine/loaders.py](engine/loaders.py))

Load campaign JSON → dataclasses:

```python
def load_campaign(campaign_dir) -> Campaign
def load_nodes(nodes_file, campaign_id) -> Dict[str, Node]
def load_npcs(npcs_file) -> NPCDatabase
def load_encounters(encounters_file) -> EncounterDatabase
def load_full_campaign(campaign_dir) -> Tuple[Campaign, Dict[Node], NPCDatabase, EncounterDatabase]
```

#### 4. Rules Engine ([engine/rules_engine.py](engine/rules_engine.py))

D&D 5e mechanics:

```python
class DiceRoller:
    @staticmethod
    def roll(expression: str) -> DiceResult  # "2d6+3", "1d20"
    def roll_with_advantage() -> Tuple[DiceResult, DiceResult, DiceResult]
    def roll_with_disadvantage() -> ...

class CheckEngine:
    def __init__(self, character: Character)
    def skill_check(skill, dc, advantage=False) -> CheckResult
    def ability_check(ability, dc, advantage=False) -> CheckResult
    def saving_throw(ability, dc, advantage=False) -> CheckResult

class CombatEngine:
    def roll_initiative(combatants) -> List[Tuple[str, int]]
    def roll_attack(attacker, target, advantage=False) -> AttackResult
    def apply_damage(target, damage, damage_type)
```

**CheckResult includes:**
- `success: bool`, `total: int`, `dc: int`
- `roll: DiceResult`, `modifier: int`
- `critical_success`, `critical_failure`, `margin`

#### 5. NewDMEngine ([engine/dm_engine_v2.py](engine/dm_engine_v2.py))

Next-gen DM with validation and intent detection:

```python
class NewDMEngine:
    def __init__(self, state_manager, ollama_client)

    def process_player_input(self, player_input: str) -> DMResponse
        # 1. Parse intent (movement, talk, action, examine)
        # 2. Validate (can't talk to absent NPC, can't use missing item)
        # 3. Check conditions (flags, items, relationships)
        # 4. Execute or generate narrative
        # 5. Return DMResponse

    def validate_action(self, intent) -> Tuple[bool, str]
    def generate_narration(self, context, intent) -> str
```

---

## Foundation Data

**Location:** `/home/robbhimself/bardic-ai/data/foundation/` (3.1 MB)

**Source:** D&D 5e SRD via [Open5e API](https://open5e.com/) (built with `build_foundation_data.py`)

### Directory Structure

```
foundation/
├── entities/
│   ├── backgrounds.json   # 13 backgrounds (Acolyte, Criminal, etc.)
│   ├── classes.json       # 12 classes with features
│   ├── monsters.json      # 400+ creatures (stats, abilities, CR)
│   └── races.json         # 20 playable races
├── items/
│   ├── armor.json         # Light, medium, heavy armor
│   ├── equipment.json     # Adventuring gear, tools
│   ├── magic_items.json   # 600+ magic items
│   └── weapons.json       # Simple, martial, ranged weapons
├── mechanics/
│   ├── ability_scores.json
│   ├── damage_types.json
│   ├── proficiencies.json
│   └── skills.json
├── rules/
│   ├── adventuring.json
│   ├── conditions.json
│   └── features.json
└── spells/
    └── spells.json        # 440+ spells with full descriptions
```

### Usage

```python
from engine import RulesEngine

rules = RulesEngine(foundation_path="data/foundation")
# Uses foundation data for combat calculations, spell lookups, etc.
```

---

## Campaign Formats

### Old Format (Single JSON)

**File:** `data/campaigns/{name}.json`

- All checkpoints in one file
- ~5-12 locations total
- Simple structure

### New Format (Separate Files)

**Directory:** `data/campaigns/{campaign_name}/`

```
goblin_kidnapping_v2/
├── campaign.json          # Metadata, chapters, starting location
├── chapter_1_nodes.json   # All nodes for Chapter 1 (32 KB)
├── npcs.json              # All NPCs (19 KB)
├── encounters.json        # Combat encounters (11 KB)
└── README.md              # Design notes
```

#### campaign.json

```json
{
  "campaign_id": "goblin_kidnapping_v2",
  "title": "The Goblin Kidnapping",
  "author": "Bardic AI",
  "description": "...",
  "starting_chapter": "chapter_1",
  "starting_node": "sandpoint_town_square",
  "chapters": [
    {
      "chapter_id": "chapter_1",
      "title": "Trouble in Sandpoint",
      "description": "Ameiko Kaijitsu has been kidnapped...",
      "nodes_file": "chapter_1_nodes.json",
      "estimated_duration": "3-4 hours"
    }
  ]
}
```

#### chapter_1_nodes.json

```json
{
  "nodes": {
    "sandpoint_town_square": {
      "node_id": "sandpoint_town_square",
      "name": "Sandpoint Town Square",
      "description": {
        "short": "The bustling heart of Sandpoint",
        "long": "The town square is alive with activity..."
      },
      "chapter_id": "chapter_1",
      "npcs_present": [
        {"npc_id": "sheriff_hemlock", "role": "quest_giver", "required": true}
      ],
      "exits": {
        "rusty_dragon": {
          "target_node": "rusty_dragon_interior",
          "description": "Enter the Rusty Dragon Inn",
          "direction": "interior"
        },
        "south_gate": {
          "target_node": "south_gate",
          "description": "Head to the south gate",
          "direction": "south"
        }
      },
      "significant_actions": {
        "talk_to_sheriff": {
          "action_id": "talk_to_sheriff",
          "trigger_description": "Talk to Sheriff Hemlock about the kidnapping",
          "requires_flags": [],
          "sets_flags": ["knows_about_kidnapping"],
          "grants_quest": "rescue_ameiko",
          "success_prompt": "Sheriff tells you about Ameiko's disappearance"
        }
      }
    }
  }
}
```

#### npcs.json

```json
{
  "npcs": {
    "sheriff_hemlock": {
      "npc_id": "sheriff_hemlock",
      "name": "Sheriff Belor Hemlock",
      "role": "quest_giver",
      "appearance": {
        "short": "A stern middle-aged man in worn armor",
        "detailed": "Sheriff Hemlock is a weathered veteran..."
      },
      "personality": {
        "traits": ["serious", "protective", "pragmatic"],
        "ideals": ["Duty above all", "Protect the innocent"],
        "bonds": ["Sandpoint is his responsibility"],
        "flaws": ["Struggles to ask for help", "Overworks himself"]
      },
      "voice": {
        "style": "gruff",
        "speech_patterns": ["direct", "no-nonsense", "military terminology"]
      },
      "base_disposition": 50,
      "knowledge": {
        "kidnapping": {
          "topic_id": "kidnapping",
          "information": "Ameiko was taken last night by goblins...",
          "share_condition": "always"
        }
      },
      "dialogue": {
        "greeting_first": "Ah, an adventurer. Good timing. We have a problem.",
        "greeting_friendly": "Good to see you. Any progress on finding Ameiko?"
      },
      "quests_can_give": ["rescue_ameiko"]
    }
  }
}
```

#### encounters.json

```json
{
  "encounters": {
    "forest_ambush": {
      "encounter_id": "forest_ambush",
      "name": "Goblin Ambush",
      "difficulty": "medium",
      "enemies": [
        {"monster_id": "goblin", "count": 3, "hp_override": null},
        {"monster_id": "goblin-boss", "count": 1, "hp_override": 15}
      ],
      "environment_effects": ["Dense foliage provides half cover"],
      "victory_conditions": ["All enemies defeated or fled"],
      "rewards": {
        "xp": 150,
        "gold": 25,
        "items": ["crude_map", "rusty_dagger"]
      }
    }
  }
}
```

### Current Campaign Status

**goblin_kidnapping_v2:** ✅ Built, 7 nodes in Chapter 1

**Nodes:**
1. sandpoint_town_square
2. rusty_dragon_interior
3. sandpoint_general_store
4. south_gate
5. forest_path_1
6. goblin_hideout_entrance
7. goblin_hideout_interior

**NPCs:** sheriff_hemlock, ameiko, shalelu, aldern

**Encounters:** forest_ambush, hideout_guards, final_confrontation

**⚠️ Needs expansion:** Should have 20-30+ nodes for full Chapter 1

---

## UI Components

### Cinematic Interface (Recently Added)

All implemented in [templates/game.html](templates/game.html)

#### 1. Push-to-Talk Voice Input (Spacebar)

**How it works:**
- Hold spacebar → record
- Release spacebar → submit
- Visual feedback: edge glow + floating mic with waveform
- Prevents recording when typing in input fields
- Prevents spacebar from scrolling page

**Implementation:**
- `startPushToTalkRecording()` - Starts MediaRecorder
- `stopPushToTalkRecording()` - Stops, sends to `/game/voice_action`
- `isTypingInInput()` - Checks if focus is on input/textarea

#### 2. Player-Triggered Dice Rolls (R Key)

**Flow:**
1. Player types: "I try to sneak past the guards"
2. Backend detects "sneak" → returns `awaiting_roll: {type, skill, dc}`
3. Frontend shows: "Press [R] to roll STEALTH CHECK"
4. Player presses R → calls `/game/roll_dice`
5. Backend executes roll using CheckEngine
6. Frontend shows spinning dice → result with success/failure

**Visual:**
- 1 second spin animation
- 3 second result display
- Critical success: ✨ gold glow
- Critical failure: 💀 red flash
- Shows: roll + modifier = total vs DC

#### 3. Character Sheet Modal (C Key)

**Displays:**
- Core stats (name, race, class, level)
- All 6 ability scores with modifiers
- HP bar (current/max)
- AC, speed, proficiency bonus
- Inventory (expandable)
- Gold
- Active quests
- Conditions

**Slide-in from right side, press C or ESC to close**

#### 4. Combat HUD

**Shows when `combat.active == true`:**
- Round number
- Turn order with HP bars
- Current turn highlighted (gold border)
- Fixed position (top-left)
- Auto-hides when combat ends

#### 5. Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Spacebar** | Push-to-talk (hold to record) |
| **R** | Execute pending dice roll |
| **C** | Toggle character sheet |
| **ESC** | Close modals |
| **?** | Show keyboard hints |

#### 6. Visual Style

- Dark fantasy aesthetic
- Semi-transparent overlays (rgba backgrounds)
- Gold (#ffd700) highlights
- Parchment (#f0e6d2) text
- Georgia serif font
- Smooth CSS animations
- Z-index layers: 900-2000

---

## API Routes

### Game Flow

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Landing page (new game / load game) |
| `/new_game` | GET | Redirect to character creation |
| `/start` | GET/POST | Select character for new game |
| `/character_creation` | POST | Handle character creation |
| `/campaign_select` | GET | Show available campaigns |
| `/start_campaign/<id>` | GET | Start campaign with character |
| `/game` | GET | **Main game interface** |
| `/game/intro` | GET | Campaign intro cinematic |

### Game Actions

| Route | Method | Description | Speed |
|-------|--------|-------------|-------|
| `/game/choice` | POST | Pre-defined choice (instant) | ⚡ Instant |
| `/game/talk` | POST | Start NPC conversation (instant) | ⚡ Instant |
| `/game/ask` | POST | Ask NPC about topic (scripted or AI) | ⚡/🐌 Mixed |
| `/game/end_conversation` | POST | End NPC conversation | ⚡ Instant |
| `/game/action` | POST | Custom player action | 🐌 Slow (Ollama) |
| `/game/voice_action` | POST | Voice input → transcribe → action | 🐌 Slow (Whisper + Ollama) |
| `/game/attack` | POST | Attack enemy in combat | ⚡ Instant |

### New Routes (Cinematic UI)

| Route | Method | Description | Added |
|-------|--------|-------------|-------|
| `/game/roll_dice` | POST | Execute dice roll (R key) | ✅ Jan 2026 |
| `/game/character` | GET | Get character data (C key) | ✅ Jan 2026 |

#### POST /game/roll_dice

**Request:**
```json
{
  "type": "ability_check",
  "skill": "Perception",
  "dc": 15
}
```

**Response:**
```json
{
  "success": true,
  "type": "ability_check",
  "skill": "Perception",
  "ability": "wis",
  "roll": 12,
  "modifier": 3,
  "total": 15,
  "dc": 15,
  "success": true,
  "critical": false,
  "natural_20": false,
  "natural_1": false
}
```

#### GET /game/character

**Response:**
```json
{
  "name": "Smite",
  "race": "Human",
  "char_class": "Fighter",
  "level": 1,
  "hp": {"current": 12, "max": 12},
  "armor_class": 16,
  "ability_scores": {
    "str": 16, "dex": 14, "con": 15,
    "int": 10, "wis": 12, "cha": 8
  },
  "inventory": [...],
  "gold": {"gp": 15},
  "skill_proficiencies": [...]
}
```

### Persistence

| Route | Method | Description |
|-------|--------|-------------|
| `/save_game` | GET | Save current game state |
| `/load` | GET | List saved games |
| `/load_game/<filename>` | GET | Load specific save file |

### Character Creation Wizard

| Route | Method | Description |
|-------|--------|-------------|
| `/character/new` | GET | Initialize wizard |
| `/character/step1` | GET/POST | Race selection |
| `/character/step2` | GET/POST | Class selection |
| `/character/step4` | GET/POST | Ability scores |
| `/character/step5` | GET/POST | Background |
| `/character/step6` | GET/POST | Equipment (auto-assigned) |
| `/character/step7` | GET/POST | Skill proficiencies |
| `/character/step8` | GET/POST | Spells (casters only) |
| `/character/step9` | GET/POST | Review and finalize |
| `/character/generate_portrait` | POST | AI portrait generation |

### Utility

| Route | Method | Description |
|-------|--------|-------------|
| `/transcribe` | POST | Whisper speech-to-text |
| `/audio/<filename>` | GET | Serve TTS audio files |

---

## File Structure

```
bardic-ai/
├── app.py                          # Flask application (1067 lines)
│
├── engine/                         # NEW ENGINE (not integrated)
│   ├── __init__.py                 # Exports
│   ├── loaders.py                  # Load campaign JSON → dataclasses
│   ├── state_manager.py            # StateManager class
│   ├── rules_engine.py             # DiceRoller, CheckEngine, CombatEngine
│   ├── dm_engine_v2.py             # NewDMEngine with validation
│   ├── test_campaign_loader.py     # Test script
│   └── schemas/
│       ├── __init__.py
│       ├── game_state.py           # GameState, Character, Combat
│       ├── campaign.py             # Campaign, Chapter, Node, NodeExit
│       ├── npc.py                  # NPC, NPCPersonality, Knowledge
│       └── encounter.py            # Encounter, EnemyInstance, Rewards
│
├── services/                       # OLD SYSTEM (currently running)
│   ├── dm_engine.py                # Old DM engine (hybrid scripted + AI)
│   ├── ollama_client.py            # LLM integration (Qwen 2.5)
│   ├── open5e_client.py            # D&D 5e API + 7-day cache
│   ├── voice_input.py              # Whisper speech-to-text
│   ├── voice_output.py             # Coqui TTS text-to-speech
│   ├── image_generator.py          # Stable Diffusion (scenes, portraits)
│   └── image_gen.py                # Character portrait generation
│
├── models/                         # OLD MODELS
│   ├── campaign.py                 # Old Campaign/Checkpoint system
│   ├── game_state.py               # Old GameState/Character
│   └── dnd5e_character.py          # Full D&D 5e character builder
│
├── templates/
│   ├── landing.html                # Landing page
│   ├── start_game.html             # Character selection
│   ├── campaign_select.html        # Campaign selection
│   ├── game.html                   # Main game UI (2267 lines, cinematic UI)
│   ├── game_intro.html             # Campaign intro cinematic
│   ├── load_game.html              # Load saved games
│   └── character/                  # Character creation wizard
│       ├── step1_race.html
│       ├── step2_class.html
│       ├── step4_abilities.html
│       ├── step5_background.html
│       ├── step6_equipment.html
│       ├── step7_skills.html
│       ├── step8_spells.html
│       └── step9_review.html
│
├── static/
│   ├── images/
│   │   ├── races/                  # 20 race portraits
│   │   ├── dm/                     # DM portrait
│   │   └── portraits/              # Generated character portraits
│   └── css/
│       └── styles.css
│
├── data/
│   ├── foundation/                 # D&D 5e SRD data (3.1 MB)
│   │   ├── entities/               # monsters, classes, races, backgrounds
│   │   ├── items/                  # armor, weapons, magic items, equipment
│   │   ├── mechanics/              # skills, abilities, proficiencies
│   │   ├── rules/                  # conditions, features, adventuring
│   │   └── spells/                 # 440+ spells
│   │
│   ├── campaigns/
│   │   ├── goblins_gambit.json             # OLD FORMAT (12 checkpoints)
│   │   ├── ravenmoor_manor.json            # OLD FORMAT (17 checkpoints)
│   │   ├── crimson_drake.json              # OLD FORMAT (23 checkpoints)
│   │   ├── lich_king_ch1.json              # OLD FORMAT (24 checkpoints)
│   │   │
│   │   └── goblin_kidnapping_v2/           # NEW FORMAT
│   │       ├── campaign.json               # Metadata, chapters
│   │       ├── chapter_1_nodes.json        # 7 nodes (needs 20-30+)
│   │       ├── npcs.json                   # 4 NPCs
│   │       ├── encounters.json             # 3 encounters
│   │       └── README.md
│   │
│   ├── characters/                 # Saved character files
│   ├── cache/                      # Open5e API cache
│   └── saves/                      # Saved game states
│
├── voice_samples/                  # TTS voice cloning samples
├── build_foundation_data.py        # Fetches D&D 5e SRD data
├── record_voice_sample.py          # Record TTS voice sample
├── requirements.txt
├── .env                            # Ollama settings
└── DOCUMENTATION.md                # This file
```

---

## Known Issues & Limitations

### Critical Issues

#### 1. Dice Rolls Don't Affect Narrative

**Problem:** Rolls happen AFTER LLM generates response

**Current Flow:**
```
Player: "I sneak past guards"
  ↓
LLM: "You sneak past the guards successfully"  [generates narration]
  ↓
Frontend: "Press [R] to roll Stealth"
  ↓
Player presses R → rolls 5 (failure)
  ↓
❌ Narrative already said success, but roll failed!
```

**Needed Flow:**
```
Player: "I sneak past guards"
  ↓
DM Engine: Detects "sneak" → needs Stealth check
  ↓
DM: "You attempt to sneak. Make a Stealth check." [wait for roll]
  ↓
Player presses R → rolls 18 (success)
  ↓
LLM: [receives roll result in context] "You slip past silently..."
```

**Fix:** DM engine must:
1. Detect roll needed BEFORE calling LLM
2. Return `awaiting_roll` WITHOUT narrative
3. Wait for `/game/roll_dice` response
4. Include roll result in LLM context
5. Generate narrative that matches roll outcome

#### 2. Keyword Detection Too Aggressive

**Problem:** False positives trigger unwanted rolls

**Examples:**
- "I want to **buy** supplies" → triggers Deception check (contains "buy")
- "I **search** for the inn" → triggers Perception check (movement, not searching)
- "Can **I** go north?" → triggers generic check ("can I" pattern)

**Fix:**
- Context-aware detection (verb + object)
- Whitelist safe phrases ("buy", "go to", "talk to")
- DM should narrate WHY roll is needed before prompting

#### 3. Location Context Gets Lost

**Problem:** Only ~5 checkpoints per campaign = vague locations

**Example:**
- "You're in the forest" (which part? near town? deep in?)
- "You're at the tavern" (upstairs? downstairs? kitchen?)

**Fix:** Use new engine with 20-30+ nodes per chapter
- "You're at the ancient oak near the stream bend"
- "You're in the Rusty Dragon's common room"

#### 4. No Validation

**Problem:** Player can do impossible things

**Examples:**
- Talk to NPC not present in location
- Use item they don't have
- Leave area without meeting requirements

**Fix:** NewDMEngine.validate_action() checks:
- NPC presence
- Item possession
- Flag requirements
- Relationship thresholds

### Minor Issues

#### 5. Combat HUD Not Implemented

- `/game/action` and `/game/voice_action` don't return `combat` object
- Frontend expects `combat.active`, `combat.combatants`, `combat.turn_order`
- Need to add combat state to responses

#### 6. Character Sheet Styling

- Works but could be prettier
- Inventory section basic
- No spell slots for casters
- No class features shown

#### 7. Location Not Prominent in UI

- Current location shown in small text
- Should be more visible (large header?)
- No visual indicator when location changes

#### 8. Multi-Voice NPC Support

- All NPCs use same TTS voice
- No per-NPC voice samples yet
- `NPCVoice.voice_sample_file` defined but not used

---

## TODO List (Critical)

### 🔴 High Priority - Integration

**These must be done to use the new engine:**

- [ ] **Integrate new engine into Flask app startup**
  - [ ] Add `load_full_campaign()` call in `start_campaign()` route
  - [ ] Store `StateManager` in `active_games[session_id]`
  - [ ] Keep old system running in parallel initially

- [ ] **Replace old GameState with new StateManager**
  - [ ] Convert `active_games` structure to use `StateManager`
  - [ ] Update all routes to call `state_manager` methods
  - [ ] Migrate save/load to use new `GameState.to_dict()` / `from_dict()`

- [ ] **Wire new dm_engine_v2.py into routes**
  - [ ] Use `NewDMEngine.process_player_input()` in `/game/action`
  - [ ] Handle validation errors gracefully
  - [ ] Return proper `DMResponse` format

- [ ] **Fix dice roll flow**
  - [ ] **Detect roll BEFORE calling LLM**
  - [ ] Return `awaiting_roll` without narrative
  - [ ] Wait for `/game/roll_dice` callback
  - [ ] Include roll result in LLM prompt
  - [ ] Generate narrative that respects roll outcome

- [ ] **Make dice results affect narrative**
  - [ ] Success roll → success narrative
  - [ ] Failure roll → failure narrative (combat? alert guards?)
  - [ ] Critical success → extra reward
  - [ ] Critical failure → extra consequence

### 🟡 High Priority - Content

**Campaign needs more nodes:**

- [ ] **Expand goblin_kidnapping_v2 Chapter 1**
  - [ ] Currently: 7 nodes
  - [ ] Target: 20-30 nodes
  - [ ] Add:
    - [ ] Forest sections (clearing, stream, dense woods, goblin tracks)
    - [ ] Cave approach (entrance, guard post, tunnels)
    - [ ] Cave interior (prison, goblin lair, boss chamber)
    - [ ] Sandpoint areas (market, temple, docks, homes)

- [ ] **Add Chapter 2+ structure**
  - [ ] Create `chapter_2_nodes.json`
  - [ ] Define new NPCs for chapter 2
  - [ ] Add new encounters
  - [ ] Link chapters together

### 🟠 Medium Priority - Dice Rolls

**Improve roll detection and flow:**

- [ ] **Fix keyword detection**
  - [ ] Whitelist safe phrases ("buy", "go to", "talk to")
  - [ ] Context-aware detection (verb + object)
  - [ ] Stop triggering on "buy", "search" in wrong context

- [ ] **DM should narrate WHY roll is needed**
  - [ ] Before showing "Press [R]", explain the challenge
  - [ ] Example: "The guards are alert. You'll need to be very quiet. Make a Stealth check."

- [ ] **Roll results should gate progression**
  - [ ] Failed stealth → combat encounter
  - [ ] Failed persuasion → NPC refuses
  - [ ] Failed lockpick → alarm triggered

### 🟠 Medium Priority - UI

**Polish the interface:**

- [ ] **Character sheet improvements**
  - [ ] Better inventory styling
  - [ ] Show spell slots for casters
  - [ ] Display class features
  - [ ] Show conditions with descriptions

- [ ] **Show location more prominently**
  - [ ] Large header with current location name
  - [ ] Visual transition when moving (fade, slide)
  - [ ] Breadcrumb trail (Town Square > Rusty Dragon > Upstairs)

- [ ] **Combat HUD integration**
  - [ ] Add `combat` object to `/game/action` responses
  - [ ] Include `combatants`, `turn_order`, `current_turn_index`
  - [ ] Test combat flow end-to-end

### 🟢 Lower Priority

**Future enhancements:**

- [ ] **Multi-voice NPC support**
  - [ ] Record voice samples for key NPCs
  - [ ] Use `NPCVoice.voice_sample_file` in TTS calls
  - [ ] Different voice per character

- [ ] **Multiplayer support**
  - [ ] Multiple players, one DM
  - [ ] Shared game state
  - [ ] Turn-based input

- [ ] **Campaign editor UI**
  - [ ] Web interface to edit nodes, NPCs, encounters
  - [ ] Visual node graph
  - [ ] Live testing

- [ ] **Save/load with new engine**
  - [ ] Implement `GameState.to_dict()` and `from_dict()`
  - [ ] Support old save format migration
  - [ ] Auto-save every N minutes

---

## Quick Start

### Installation

```bash
# Clone repository
git clone <repo>
cd bardic-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Pull LLM model
ollama pull qwen2.5:14b
```

### Configuration

Create `.env` file:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

### Optional: Voice Cloning

Record a 10-second voice sample for TTS:

```bash
python record_voice_sample.py
# Saves to voice_samples/dm_voice.wav
```

### Run the App

```bash
python app.py
# Visit http://localhost:5000
```

### Test New Engine (Without Integration)

```bash
cd engine
python test_campaign_loader.py
# Tests campaign loading, state manager, rules engine
```

---

## Testing Checklist

### Before Starting a Session

- [ ] Ollama running (`ollama serve`)
- [ ] Flask app running (`python app.py`)
- [ ] Browser at http://localhost:5000

### Test Old System (Currently Running)

- [ ] Create character
- [ ] Start goblin_gambit campaign
- [ ] Make a choice (instant)
- [ ] Talk to NPC (instant)
- [ ] Custom action (slow, Ollama)
- [ ] Voice input (hold click to record)

### Test New UI Components

- [ ] Hold spacebar → record → release → submit ✅
- [ ] Type "I search the room" → see roll prompt ✅
- [ ] Press R → see dice animation → result ✅
- [ ] Press C → character sheet opens ✅
- [ ] Press ESC → character sheet closes ✅

### Test New Engine (CLI Only)

```bash
cd engine
python test_campaign_loader.py
```

Expected output:
- ✓ Campaign loaded
- ✓ 7 nodes loaded
- ✓ 4 NPCs loaded
- ✓ 3 encounters loaded
- ✓ State manager initialized
- ✓ Dice rolls working

---

## Architecture Decision Log

### Why Two Systems?

**Old system** was built quickly to get a working prototype. It works but has limitations:
- Only ~5 checkpoints = vague locations
- No validation of player actions
- Dice rolls don't affect narrative

**New engine** was built to address these issues:
- Node-based navigation (20-30+ nodes/chapter)
- Rich schemas with validation
- Proper D&D 5e rules engine

**Why not integrated yet?**
- Significant refactoring required
- Old system works for testing
- New engine needs more campaign content

### Why Separate Campaign Files?

**Old:** Single JSON file (1000+ lines)
**New:** Separate files (campaign.json, nodes.json, npcs.json, encounters.json)

**Benefits:**
- Easier to edit (find specific node)
- Better Git diffs
- Can load chapters on-demand
- Multiple people can edit different files

### Why Foundation Data?

Instead of calling Open5e API every time:
- **3.1 MB local cache** = offline play
- Faster lookups (no network calls)
- Consistent data (API won't change mid-game)
- Combat calculations need monster stats immediately

---

## Contributing

When adding features:

1. **Document in this file** - Update relevant sections
2. **Test both systems** - Old and new (if applicable)
3. **Update TODO list** - Mark completed, add new tasks
4. **Keep backward compatibility** - Don't break saves

---

## License & Credits

**D&D 5e SRD Data:** Open Game License (OGL) via Open5e API
**Code:** MIT License
**LLM:** Qwen 2.5 14B (Alibaba Cloud)
**TTS:** Coqui TTS XTTS v2
**STT:** OpenAI Whisper

---

**Last Updated:** January 2026
**Version:** 2.0 (New engine built, pending integration)
