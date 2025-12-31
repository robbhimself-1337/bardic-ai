# Bardic AI - Documentation

Local AI-powered D&D Dungeon Master with voice input/output.

## Architecture Overview

### Core Components

1. **Voice Pipeline**
   - **Input**: Whisper speech-to-text transcribes player speech
   - **Output**: Coqui TTS XTTS v2 with voice cloning for DM responses

2. **DM Engine** (`services/dm_engine.py`)
   - Builds context from game state, quests, combat, NPCs
   - Uses Qwen 2.5 14B via Ollama for narrative generation
   - Parses `[FUNCTION: name(args)]` calls from LLM to affect game state

3. **Game State** (`models/game_state.py`, `models/campaign.py`)
   - Character stats, inventory, HP tracking
   - Campaign checkpoint system with branching paths
   - Quest tracking, combat management
   - Save/load persistence to JSON

4. **Open5e Integration** (`services/open5e_client.py`)
   - Fetches D&D 5e SRD content (races, classes, spells, etc.)
   - 7-day local caching for offline play
   - ~20 races, 12 classes, full spell lists

---

## Campaign System

### Campaign Categories

| Category | Duration | Checkpoints | Best For |
|----------|----------|-------------|----------|
| **One-Shot** | 2-3 hours | 5-12 | Single session |
| **Short** | 4-6 hours | 10-17 | Weekend adventure |
| **Medium** | 10-20 hours | 20-30 | Multi-session arc |
| **Epic** | Ongoing | 50+ | Long campaign |

### Campaign Template Structure

```json
{
  "id": "campaign_id",
  "title": "Campaign Title",
  "description": "Brief description",
  "category": "one-shot|short|medium|epic",
  "estimated_duration": "2 hours",
  "difficulty": "beginner|intermediate|advanced",
  "starting_checkpoint": "checkpoint_id",
  "checkpoints": {
    "checkpoint_id": {
      "description": "Location description",
      "npcs": ["npc1"],
      "items_available": ["item1"],
      "enemies": ["enemy_type"],
      "next_checkpoints": ["next_id1", "next_id2"],
      "auto_quests": [{"name": "Quest", "description": "..."}]
    }
  }
}
```

### Included Campaigns

1. **The Goblin's Gambit** - One-shot, 2hrs, beginner (12 checkpoints)
2. **Curse of Ravenmoor Manor** - Short, 4-6hrs, intermediate (17 checkpoints)
3. **Shadow of the Crimson Drake** - Medium, 15hrs, intermediate (23 checkpoints)
4. **Rise of the Lich King Ch.1** - Epic, ongoing, advanced (24 checkpoints)

---

## Character Creation

### Wizard Flow

```
/character/new → Step 1: Race → Step 2: Class → Step 4: Abilities 
              → Step 7: Skills → Step 9: Review → Campaign Select
```

### Character Data

Characters save to `data/characters/{name}.json` with full D&D 5e stats:
- 6 ability scores with modifiers
- HP, AC, initiative calculations
- Skill and saving throw proficiencies
- Spell slots (for casters)
- Equipment and inventory

### Race Images

All 20 Open5e races have portrait images in `/static/images/races/`:
- Common: Human, Elf, Dwarf, Halfling, Half-Elf, Half-Orc, Gnome
- Exotic: Dragonborn, Tiefling, Drow, Minotaur
- Rare: Alseid, Catfolk, Darakhul, Derro, Erina, Gearforged, Mushroomfolk, Satarre, Shade

---

## DM Function Calling

The DM can embed function calls in responses:

```
"The goblin strikes! [FUNCTION: damage_player(5)] You stumble back..."
```

### Available Functions

- `damage_player(amount)` - Deal damage to player
- `damage_enemy(enemy_id, amount)` - Deal damage to enemy
- `add_item(item_name)` / `remove_item(item_name)` - Inventory management
- `start_combat(enemies)` / `end_combat()` - Combat state
- `advance_checkpoint(id, summary)` - Location transitions
- `add_quest(name, desc)` / `complete_quest(name)` - Quest tracking

---

## API Routes

### Game Flow
- `GET /` - Landing page
- `GET /character/new` - Start character wizard
- `GET /campaign_select` - Choose campaign
- `GET /game` - Main game interface
- `POST /game_action` - Process player action

### Persistence
- `GET /save_game` - Save current game
- `GET /load` - List saved games
- `GET /load_game/<filename>` - Load specific game

### Voice
- `POST /transcribe` - Whisper speech-to-text
- `GET /audio/<filename>` - Serve TTS audio

---

## File Structure

```
bardic-ai/
├── app.py                 # Flask application
├── services/
│   ├── dm_engine.py       # DM narrative + function calling
│   ├── ollama_client.py   # LLM integration
│   ├── open5e_client.py   # D&D 5e API + caching
│   ├── voice_input.py     # Whisper STT
│   └── voice_output.py    # Coqui TTS
├── models/
│   ├── campaign.py        # Campaign/checkpoint system
│   ├── game_state.py      # Game state management
│   └── dnd5e_character.py # Full D&D 5e character
├── templates/
│   ├── landing.html
│   ├── game.html
│   ├── campaign_select.html
│   └── character/         # Wizard steps
├── static/images/races/   # Race portraits
├── data/
│   ├── cache/             # Open5e API cache
│   ├── campaigns/templates/  # Campaign JSON files
│   └── characters/        # Saved characters
└── voice_samples/         # TTS voice cloning samples
```

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Pull Ollama model
ollama pull qwen2.5:14b

# Record voice sample for TTS
python record_voice_sample.py

# Run the app
python app.py
# Visit http://localhost:5000
```

---

## Future Roadmap

- [ ] Multi-voice NPC support (different voices per character)
- [ ] Real-time voice conversation mode
- [ ] Combat system improvements (initiative, spell casting)
- [ ] Character leveling system
- [ ] Campaign editor UI
- [ ] Multiplayer support
