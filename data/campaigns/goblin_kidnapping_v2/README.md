# Goblin Kidnapping Campaign v2.0

This campaign uses the new modular schema system with separate files for different components.

## Files Structure

- **campaign.json** - Campaign metadata, chapter definitions, and file references
- **npcs.json** - All NPCs with full personality, knowledge, dialogue, and relationship systems
- **chapter_1_nodes.json** - All nodes (locations) for Chapter 1
- **encounters.json** - Combat encounter definitions
- **items.json** - (Not yet created) Item definitions for loot and equipment

## Chapter 1: A Desperate Plea

### Summary
You arrive at the Rusty Dragon Tavern in Sandpoint to find the town gripped by fear. Innkeeper Ameiko Kaijitsu begs for your help - children have been taken by goblins. You must gather information, prepare supplies, and locate the goblin hideout before more innocents are lost.

### Nodes (Locations)

1. **rusty_dragon_main** - Starting location, meet Ameiko and accept the quest
2. **rusty_dragon_bar** - Purchase supplies (rations, torches, rope, potions)
3. **town_square** - Central hub connecting different locations
4. **guard_post** - Talk to Captain Marcus for tactical information
5. **tobias_cottage_exterior** - Approach the hermit's cottage
6. **tobias_cottage_interior** - Learn the cave location from Tobias
7. **forest_edge** - Chapter 1 exit point, optional goblin scout encounter

### NPCs

#### Ameiko Kaijitsu (Quest Giver)
- **Role:** Innkeeper, quest giver
- **Personality:** Caring, resilient, protective, takes too much responsibility
- **Knowledge:** Kidnappings, victims, goblins, reward, Old Man Tobias
- **Starting Disposition:** 50 (neutral, but desperate for help)
- **Voice:** Warm but strained, speaks quickly when worried

#### Guard Captain Marcus Thorne (Tactical Advisor)
- **Role:** Military information source
- **Personality:** Dutiful, pragmatic, haunted by guilt, gruff exterior
- **Knowledge:** Forest dangers, goblin tactics, guard situation, equipment advice
- **Starting Disposition:** 40 (professional but cautious)
- **Voice:** Gruff, military directness, speaks in short sentences

#### Old Man Tobias Greenthorn (Witness)
- **Role:** Key information source for cave location
- **Personality:** Observant, reclusive, kind beneath gruff exterior, lonely
- **Knowledge:** Cave location (REQUIRES TRUST), goblin sighting, forest lore, late wife
- **Starting Disposition:** 30 (suspicious of strangers)
- **Voice:** Scratchy but warm, rambles when comfortable
- **Special:** Requires building trust (disposition 5+) before sharing cave location

### Quest Flow

1. **Enter Rusty Dragon** → Meet Ameiko → Learn about kidnappings
2. **Accept Quest** → "Rescue the Kidnapped Children"
3. **Optional: Visit Guard Post** → Talk to Marcus → Learn combat tactics
4. **Optional: Buy Supplies** → Rusty Dragon bar → Stock up for journey
5. **Travel to Tobias's Cottage** → Meet the hermit
6. **Build Trust with Tobias** → Listen to his story → Earn cave location
7. **Head to Forest Edge** → Prepare for Chapter 2
8. **Optional Combat** → Goblin scout encounter (40% chance)

### Key Flags

- `has_quest` - Player accepted the rescue mission
- `knows_about_kidnapping` - Player learned details from Ameiko
- `talked_to_ameiko` - Met the innkeeper
- `talked_to_marcus` - Spoke with the guard captain
- `knows_forest_dangers` - Learned tactical information
- `has_supplies` - Purchased travel supplies
- `met_tobias` - Encountered the hermit
- `tobias_trusts_player` - Built trust with Tobias
- `knows_cave_location` - **CRITICAL** - Required to progress to Chapter 2
- `ready_for_chapter_2` - Player has prepared and is ready to enter forest

### Completion Conditions

**Required:**
- `has_quest` - Must accept the mission
- `knows_cave_location` - Must learn where to go

**Recommended:**
- `has_supplies` - Should buy equipment
- `knows_forest_dangers` - Should learn tactics from Marcus
- `talked_to_marcus` - Should gather information

### Encounters

#### Goblin Scout (Easy - Optional)
- **Location:** Forest edge
- **Enemies:** 2 Goblin Scouts
- **Trigger:** 40% random chance when entering forest_edge node
- **Difficulty:** Easy (CR 1/4 each)
- **Tactics:** Hit and run with shortbows, use Nimble Escape
- **Rewards:** 100 XP, goblin map fragment, crude weapons
- **Morale:** Break at 50% HP

#### Goblin Revenge Party (Medium)
- **Enemies:** 3 Goblin Warriors + 1 Goblin Leader
- **Difficulty:** Medium
- **For future chapters**

#### Cave Entrance Guards (Medium)
- **Enemies:** 2 Goblin Guards + 1 Archer + 1 Worg
- **Difficulty:** Medium
- **For Chapter 2 start**

### Design Notes

**Relationship System:**
- NPCs track disposition (-100 to +100) and trust separately
- Different greetings/farewells based on relationship level
- Some knowledge requires minimum trust levels
- Actions and dialogue choices affect relationships

**Soft Gates:**
- Players can proceed without supplies/information, but get warnings
- Tobias will call out if you enter forest unprepared
- Ameiko reminds you about the quest if you try to leave without accepting

**Multiple Paths:**
- Can skip Marcus entirely (but miss valuable intel)
- Can skip buying supplies (but harder survival)
- Must talk to Tobias to get cave location (hard gate)

**Atmospheric Design:**
- Each node has detailed sensory information (sounds, smells, mood)
- Image generation prompts for visual consistency
- Entry narration changes between first and subsequent visits

### Next Steps for Development

1. **Create items.json** - Define all purchasable and findable items
2. **Create Chapter 2** - Inside Mosswood Forest, journey to cave
3. **Create Chapter 3** - The goblin cave and rescue
4. **Implement quest system** - Track objectives and completion
5. **Build relationship tracker** - Track NPC dispositions across chapters
6. **Add combat system integration** - Use foundation data for monster stats

### Schema Compliance

All JSON files match the dataclass schemas in `/home/robbhimself/bardic-ai/engine/schemas/`:
- `campaign.py` - Campaign, Chapter, Node structures
- `npc.py` - NPC, Knowledge, Dialogue, Personality
- `encounter.py` - Encounter, Enemy, Rewards

Files are ready to be loaded by Python dataclass loaders with `from_dict()` methods.
