# Training Data for Bardic AI Expert Model

This directory contains extracted training examples from gameplay sessions.

## Data Format

### session_XXX.json (Training Format)
```json
{
  "context": {
    "location": "rusty_dragon_main",
    "npcs_present": ["ameiko"],
    "valid_npcs": ["Ameiko Kaijitsu", "Guard Captain Marcus Thorne", "Old Man Tobias Greenthorn"]
  },
  "input": {
    "intent": "dialogue",
    "target": "ameiko", 
    "dm_addressed": false
  },
  "output": {
    "speaker_tag": "Ameiko Kaijitsu",
    "response": "\"Hello there...\" she says..."
  },
  "metadata": {
    "quality": "good",
    "issues": [],
    "timestamp": "01/Jan/2026 11:27:23"
  }
}
```

### session_XXX_raw.json (Detailed Format)
Contains all extracted data including full analysis for review.

## Quality Labels

- **good**: Correct speaker tag, no hallucinations, story-consistent
- **bad_tag**: Wrong speaker tag for the intent/target
- **hallucination**: References NPCs or facts not in campaign data
- **needs_review**: Has issues but may be salvageable

## Usage

### Extract from new log files:
```bash
python tools/parse_training_logs.py <logfile> data/training/session_XXX.json
```

## Fine-Tuning Notes

### Positive Examples (quality=good)
Use these to train the model on correct behavior:
- Proper `[Speaker Tag]` format
- Responses that stay within campaign NPCs
- Appropriate DM vs NPC responses based on intent

### Negative Examples (quality=hallucination)
Use these to show what NOT to do:
- Inventing NPCs (Aldern, Shalelu, Belka, etc.)
- Changing story facts (who was kidnapped)
- Making up NPC relationships

### Training Approach
1. Collect 1000+ examples from gameplay
2. Balance good/bad examples (80/20 ratio)
3. LoRA fine-tune on 7B base model
4. Evaluate on held-out test set
5. Iterate based on failure modes

## Known Hallucination Patterns

These are NPCs/names Qwen tends to invent:
- Aldern Jorick / Aldern Rockfinder (Pathfinder character bleed)
- Shalelu (Pathfinder NPC)
- Belka (random name)
- Various "sisters" and "brothers" of Ameiko

## Campaign-Specific Valid NPCs

For goblin_kidnapping_v2:
- Ameiko Kaijitsu (tavern owner)
- Guard Captain Marcus Thorne
- Old Man Tobias Greenthorn

The model should NEVER reference any other NPC names.
