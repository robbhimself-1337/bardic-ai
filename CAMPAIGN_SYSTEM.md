# Bardic AI Campaign System

Comprehensive checkpoint-based narrative system with context management and function calling.

## Architecture Overview

### Core Components

1. **Campaign Templates** (`data/campaigns/templates/`)
   - JSON-based campaign definitions
   - Checkpoint/node structure with branching paths
   - NPCs, items, enemies, and quests per checkpoint

2. **Game State Management** (`models/game_state.py`)
   - Character class: HP, inventory, stats, level
   - GameState class: Progress, quests, combat, decisions
   - Save/load to JSON files

3. **Campaign Engine** (`models/campaign.py`)
   - Load and parse campaign templates
   - Checkpoint navigation and validation
   - Context generation for Ollama

4. **DM Engine** (`services/dm_engine.py`)
   - Integrates Ollama with game state
   - Function calling system
   - Context building and management
   - Checkpoint transition handling

## User Flow

1. **Landing Page** → New Game or Load Game
2. **Character Creation** → Name + Class (Fighter/Rogue/Wizard)
3. **Campaign Selection** → Choose from available campaigns
4. **Game Interface** → Voice-driven gameplay with stats sidebar
5. **Save/Load** → Persistent game state

## Function Calling System

The DM can call functions to affect game state:

### Available Functions

- `damage_player(amount)` - Deal damage to player
- `damage_enemy(enemy_id, amount)` - Deal damage to enemy
- `add_item(item_name)` - Add item to inventory
- `remove_item(item_name)` - Remove item from inventory
- `start_combat(enemies)` - Initialize combat
- `end_combat()` - End current combat
- `advance_checkpoint(next_checkpoint_id, summary)` - Move to next location
- `add_quest(quest_name, description)` - Add new quest
- `complete_quest(quest_name)` - Mark quest as complete

### Function Call Format

Functions are embedded in Ollama responses:

```
"The goblin strikes you with his club! [FUNCTION: damage_player(5)] You stumble backward..."
```

The DM engine parses and executes these automatically.

## Context Management

### At Each Checkpoint

1. Save summary of previous events
2. Build fresh context with:
   - Current checkpoint description
   - Character state (HP, inventory, stats)
   - Active quests
   - Combat state (if active)
   - Recent actions (last 3)
   - Narrative summary

3. Send to Ollama for DM response

### Checkpoint Transitions

When advancing to a new checkpoint:
- Validate transition is allowed
- Save compressed summary
- Auto-add checkpoint quests
- Reset Ollama context with new location

## Campaign Template Structure

```json
{
  "id": "campaign_id",
  "title": "Campaign Title",
  "description": "Brief description",
  "starting_checkpoint": "checkpoint_id",
  "checkpoints": {
    "checkpoint_id": {
      "description": "Location/situation description",
      "npcs": ["npc1", "npc2"],
      "items_available": ["item1", "item2"],
      "enemies": ["enemy_type"],
      "next_checkpoints": ["next_id1", "next_id2"],
      "auto_quests": [
        {
          "name": "Quest Name",
          "description": "Quest description"
        }
      ]
    }
  }
}
```

## Example Campaign

**The Goblin's Gambit** (`goblin_cave.json`)

A classic D&D adventure with 11 checkpoints demonstrating:
- Branching paths (investigation vs direct action)
- Combat encounters
- NPC interactions
- Treasure hunting
- Multiple routes to victory

### Checkpoint Flow

```
tavern_start → town_investigation (optional)
            → forest_path → hidden_grove (optional)
                         → cave_entrance → sneak_entrance (optional)
                                        → cave_tunnels
            → prisoner_chamber → escape_route (optional)
                              → goblin_throne_room
            → treasure_vault → victory
```

## File Structure

```
bardic-ai/
├── data/
│   └── campaigns/
│       ├── templates/
│       │   └── goblin_cave.json
│       └── saves/
│           └── [character_campaign.json]
├── models/
│   ├── __init__.py
│   ├── campaign.py
│   └── game_state.py
├── services/
│   ├── dm_engine.py
│   ├── ollama_client.py
│   ├── voice_input.py
│   └── voice_output.py
├── templates/
│   ├── landing.html
│   ├── character_creation.html
│   ├── campaign_select.html
│   ├── game.html
│   └── load_game.html
└── app.py
```

## API Routes

### Game Flow
- `GET /` - Landing page
- `GET /new_game` - Character creation
- `POST /character_creation` - Process character
- `GET /campaign_select` - Choose campaign
- `GET /start_campaign/<campaign_id>` - Start campaign
- `GET /game` - Main game interface
- `POST /game_action` - Process player action

### Persistence
- `GET /save_game` - Save current game
- `GET /load` - List saved games
- `GET /load_game/<filename>` - Load specific game

### Voice Integration
- `POST /transcribe` - Whisper speech-to-text
- `GET /audio/<filename>` - Serve TTS audio

## Session Management

Active games stored in memory dictionary:
```python
active_games = {
    'session_id': {
        'game_state': GameState,
        'campaign': Campaign
    }
}
```

For production: Use Redis or database for persistent sessions.

## Creating New Campaigns

1. Create JSON file in `data/campaigns/templates/`
2. Follow the template structure
3. Define checkpoints with:
   - Descriptive text
   - NPCs present
   - Available items
   - Enemies
   - Valid next checkpoints
   - Auto-quests (optional)

4. Test by starting new game and selecting campaign

## Character Classes

### Fighter
- STR: 16, DEX: 12, CON: 14
- High HP, melee combat focus

### Rogue
- STR: 10, DEX: 16, CON: 12
- High DEX, stealth and precision

### Wizard
- STR: 8, DEX: 12, INT: 16
- High INT, arcane magic focus

## Voice Integration

All existing voice features preserved:
- **Voice Input**: Whisper transcription via push-to-talk
- **Voice Output**: Coqui TTS with voice cloning
- DM responses auto-play with audio player
- Text fallback always available

## Future Enhancements

Roadmap items:
- Multi-voice NPC support (different voices per character)
- Real-time voice conversation mode
- Combat system improvements (initiative, spell casting)
- Multiplayer support
- Campaign editor UI
- Persistent Redis session storage
- Character leveling system
- Equipment and magic items

## Testing

To test the campaign system:

1. Start the app: `python app.py`
2. Click "New Campaign"
3. Create a character
4. Select "The Goblin's Gambit"
5. Use voice or text input to play
6. Test save/load functionality

Try different paths through the campaign to test branching narratives!
