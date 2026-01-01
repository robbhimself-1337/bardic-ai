"""
Hybrid DM Engine - Combines scripted content with AI fallbacks
- Pre-scripted content for checkpoint entrances, NPC dialogue, and choices
- Ollama ONLY for unexpected player actions
- Much faster response times and cleaner output
"""
import logging
from typing import Dict, List, Optional
from models.game_state import GameState, Character
from models.campaign import Campaign, NPCDialogue
from services.ollama_client import call_ollama
from services.image_generator import (
    generate_scene,
    generate_npc_portrait,
    get_dm_portrait
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DMEngine:
    """
    Hybrid DM engine that uses scripted content when available,
    falls back to Ollama for unexpected actions.
    """

    def __init__(self, game_state: GameState, campaign: Campaign):
        self.game_state = game_state
        self.campaign = campaign
        self.conversation_history = []
        self.current_npc = None  # Currently talking to this NPC

    def enter_checkpoint(self, checkpoint_id: str = None) -> dict:
        """
        Returns pre-scripted narration for a checkpoint.
        NO Ollama call needed - instant response.
        """
        if checkpoint_id:
            self.game_state.current_checkpoint = checkpoint_id

        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)

        if not checkpoint:
            return {"error": "Invalid checkpoint"}

        # Use entrance_narration if available, fall back to description
        narration = checkpoint.entrance_narration or checkpoint.description or "You arrive at a new location."

        # Auto-add quests for this checkpoint
        if checkpoint.auto_quests:
            for quest in checkpoint.auto_quests:
                self.game_state.add_quest(quest["name"], quest["description"])

        # Generate scene image if not already cached
        scene_url = checkpoint.scene_url
        if checkpoint.scene_prompt and not scene_url:
            logger.info(f"Generating scene image for {checkpoint.name}")
            scene_url = generate_scene(checkpoint.checkpoint_id, checkpoint.scene_prompt)
            if scene_url:
                checkpoint.scene_url = scene_url

        return {
            "narration": narration,
            "location": checkpoint.name,
            "checkpoint_id": checkpoint.checkpoint_id,
            "choices": [{"text": c.text, "index": i} for i, c in enumerate(checkpoint.choices)],
            "npcs": [{"name": n.name, "role": n.role} for n in checkpoint.npcs_structured],
            "items": checkpoint.items_available,
            "enemies": checkpoint.enemies,
            "scene_image": scene_url,
            "dm_portrait": get_dm_portrait(),
            "display_mode": "scene"
        }

    def make_choice(self, choice_index: int) -> dict:
        """
        Player selected a pre-defined choice. NO Ollama call needed.
        Instant response with transition narration.
        """
        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)

        if not checkpoint or choice_index < 0 or choice_index >= len(checkpoint.choices):
            return {"error": "Invalid choice"}

        choice = checkpoint.choices[choice_index]
        transition = choice.narration or "You continue onward..."

        # Record the action
        self.game_state.add_action(f"Chose: {choice.text}")

        # Move to next checkpoint
        new_location = self.enter_checkpoint(choice.next_checkpoint)

        return {
            "transition": transition,
            **new_location
        }

    def talk_to_npc(self, npc_name: str) -> dict:
        """
        Start conversation with an NPC. Returns greeting. NO Ollama needed.
        """
        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)

        if not checkpoint:
            return {"error": "Invalid location"}

        # Find NPC in structured NPCs
        for npc in checkpoint.npcs_structured:
            if npc.name.lower() == npc_name.lower():
                self.current_npc = npc
                self.game_state.add_npc_met(npc.name)
                self.game_state.add_action(f"Talked to {npc.name}")

                greeting = npc.greeting or f"{npc.name} acknowledges you."

                # Generate NPC portrait if not already cached
                portrait_url = npc.portrait_url
                if npc.portrait_prompt and not portrait_url:
                    logger.info(f"Generating portrait for {npc.name}")
                    portrait_url = generate_npc_portrait(npc.name, npc.portrait_prompt)
                    if portrait_url:
                        npc.portrait_url = portrait_url

                return {
                    "narration": greeting,
                    "npc_name": npc.name,
                    "npc_role": npc.role,
                    "topics": list(npc.dialogue_topics.keys()) if npc.dialogue_topics else [],
                    "in_conversation": True,
                    "npc_portrait": portrait_url,
                    "display_mode": "npc"
                }

        return {"error": f"There's no one named {npc_name} here."}

    def ask_about(self, topic: str) -> dict:
        """
        Ask current NPC about a topic. Uses pre-written dialogue if available.
        Falls back to Ollama only if topic not found.
        """
        if not self.current_npc:
            return {"error": "You're not talking to anyone."}

        # Check pre-written topics
        topics = self.current_npc.dialogue_topics or {}

        # Try exact match first
        if topic in topics:
            response_text = topics[topic]
            self.game_state.add_action(f"Asked {self.current_npc.name} about {topic}")

            return {
                "narration": f'{self.current_npc.name} says, "{response_text}"',
                "npc_name": self.current_npc.name,
                "topics": list(topics.keys()),
                "in_conversation": True,
                "npc_portrait": self.current_npc.portrait_url,
                "display_mode": "npc"
            }

        # Try fuzzy match (case-insensitive substring)
        for key, response_text in topics.items():
            if key.lower() in topic.lower() or topic.lower() in key.lower():
                self.game_state.add_action(f"Asked {self.current_npc.name} about {topic}")

                return {
                    "narration": f'{self.current_npc.name} says, "{response_text}"',
                    "npc_name": self.current_npc.name,
                    "topics": list(topics.keys()),
                    "in_conversation": True,
                    "npc_portrait": self.current_npc.portrait_url,
                    "display_mode": "npc"
                }

        # Fallback to Ollama for unexpected questions
        logger.info(f"No scripted response for topic '{topic}', using Ollama fallback")
        return self._ollama_npc_response(topic)

    def _ollama_npc_response(self, player_input: str) -> dict:
        """
        Ollama fallback for NPC dialogue not in script.
        Keep prompt minimal for speed.
        """
        npc = self.current_npc
        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)

        prompt = f"""You are {npc.name}, {npc.role}.
Location: {checkpoint.name}
The player asks: "{player_input}"

Respond in character, 1-2 sentences only. Be helpful but brief.
Do not use asterisks or action descriptions, just speak."""

        logger.info("Calling Ollama for NPC response...")
        response = call_ollama(prompt)

        # Clean up response
        response = response.strip().strip('"').strip("'")

        self.game_state.add_action(f"Asked {npc.name} about {player_input}")

        return {
            "narration": f'{npc.name} says, "{response}"',
            "npc_name": npc.name,
            "topics": list(npc.dialogue_topics.keys()) if npc.dialogue_topics else [],
            "in_conversation": True,
            "npc_portrait": npc.portrait_url,
            "display_mode": "npc"
        }

    def end_conversation(self) -> dict:
        """End NPC conversation and return to checkpoint choices."""
        if self.current_npc:
            self.game_state.add_action(f"Ended conversation with {self.current_npc.name}")

        self.current_npc = None
        return self.enter_checkpoint()

    def detect_roll_needed(self, player_input: str, narration: str) -> Optional[dict]:
        """
        Detect if player action requires a dice roll.
        Returns awaiting_roll dict if a roll is needed, None otherwise.
        """
        player_lower = player_input.lower()
        narration_lower = narration.lower()

        # Keywords that indicate rolls might be needed
        roll_indicators = {
            'perception': {'type': 'ability_check', 'skill': 'Perception', 'ability': 'wis'},
            'investigate': {'type': 'ability_check', 'skill': 'Investigation', 'ability': 'int'},
            'search': {'type': 'ability_check', 'skill': 'Perception', 'ability': 'wis'},
            'look for': {'type': 'ability_check', 'skill': 'Perception', 'ability': 'wis'},
            'stealth': {'type': 'ability_check', 'skill': 'Stealth', 'ability': 'dex'},
            'sneak': {'type': 'ability_check', 'skill': 'Stealth', 'ability': 'dex'},
            'hide': {'type': 'ability_check', 'skill': 'Stealth', 'ability': 'dex'},
            'persuade': {'type': 'ability_check', 'skill': 'Persuasion', 'ability': 'cha'},
            'convince': {'type': 'ability_check', 'skill': 'Persuasion', 'ability': 'cha'},
            'deceive': {'type': 'ability_check', 'skill': 'Deception', 'ability': 'cha'},
            'lie': {'type': 'ability_check', 'skill': 'Deception', 'ability': 'cha'},
            'intimidate': {'type': 'ability_check', 'skill': 'Intimidation', 'ability': 'cha'},
            'threaten': {'type': 'ability_check', 'skill': 'Intimidation', 'ability': 'cha'},
            'athletics': {'type': 'ability_check', 'skill': 'Athletics', 'ability': 'str'},
            'climb': {'type': 'ability_check', 'skill': 'Athletics', 'ability': 'str'},
            'jump': {'type': 'ability_check', 'skill': 'Athletics', 'ability': 'str'},
            'acrobatics': {'type': 'ability_check', 'skill': 'Acrobatics', 'ability': 'dex'},
            'insight': {'type': 'ability_check', 'skill': 'Insight', 'ability': 'wis'},
            'sleight of hand': {'type': 'ability_check', 'skill': 'Sleight of Hand', 'ability': 'dex'},
            'pick': {'type': 'ability_check', 'skill': 'Sleight of Hand', 'ability': 'dex'},
            'arcana': {'type': 'ability_check', 'skill': 'Arcana', 'ability': 'int'},
            'nature': {'type': 'ability_check', 'skill': 'Nature', 'ability': 'int'},
            'survival': {'type': 'ability_check', 'skill': 'Survival', 'ability': 'wis'},
            'track': {'type': 'ability_check', 'skill': 'Survival', 'ability': 'wis'},
        }

        # Check if any skill keyword appears in player input or narration
        for keyword, roll_info in roll_indicators.items():
            if keyword in player_lower or keyword in narration_lower:
                # Determine DC based on complexity
                dc = 12  # Default moderate DC
                if 'difficult' in narration_lower or 'hard' in narration_lower:
                    dc = 15
                elif 'easy' in narration_lower or 'simple' in narration_lower:
                    dc = 10
                elif 'very hard' in narration_lower or 'nearly impossible' in narration_lower:
                    dc = 18

                logger.info(f"Detected roll needed: {roll_info['skill']} (DC {dc})")

                return {
                    'type': roll_info['type'],
                    'skill': roll_info['skill'],
                    'ability': roll_info['ability'],
                    'dc': dc,
                    'reason': f"to {keyword}"
                }

        # Check for "try to" or "attempt to" patterns
        attempt_patterns = ['try to', 'attempt to', 'can i', 'could i']
        for pattern in attempt_patterns:
            if pattern in player_lower:
                # Generic check, default to ability check
                logger.info(f"Detected attempt pattern: {pattern}")
                return {
                    'type': 'ability_check',
                    'skill': 'Perception',
                    'ability': 'wis',
                    'dc': 12,
                    'reason': 'for this action'
                }

        return None

    def process_custom_action(self, player_input: str) -> dict:
        """
        Handle free-form player action. This is where Ollama is used.
        
        Players can either:
        - Speak directly to an NPC (in character): "Where is the forest?"
        - Address the DM for actions (out of character): "Joe, I walk to the door"
        """
        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)
        char = self.game_state.character
        
        # Detect if player is addressing the DM directly (contains "Joe" or similar)
        # Can appear anywhere: "Joe, I go", "Ok Joe, let's go", "Alright Joe I attack"
        import re
        dm_patterns = [
            r'\bjoe\b',           # "joe" as a word
            r'\bdm\b',            # "dm" as a word  
            r'dungeon master',    # full phrase
        ]
        player_input_lower = player_input.lower().strip()
        
        is_dm_action = any(re.search(pattern, player_input_lower) for pattern in dm_patterns)
        
        if is_dm_action:
            # Strip the DM address from the input
            cleaned_input = player_input
            for pattern in dm_patterns:
                cleaned_input = re.sub(pattern, '', cleaned_input.lower()).strip()
            # Also clean up common filler words left behind
            cleaned_input = re.sub(r'^(ok|okay|alright|hey|so|well|um|uh)[,\s]*', '', cleaned_input).strip()
            # Clean up any leftover commas/spaces at the start
            cleaned_input = re.sub(r'^[,\s]+', '', cleaned_input).strip()
            if cleaned_input:
                player_input = cleaned_input
            # Clear current speaker - this is a DM action, not NPC dialogue
            self.game_state.current_speaker = None
            logger.info(f"DM action detected: {player_input}")
        
        current_speaker = self.game_state.current_speaker

        # Build context with campaign story info
        context_parts = [
            "You are a D&D Dungeon Master named Joe running a specific campaign.",
            "Stay on theme with the campaign story. Keep responses brief (2-3 sentences).",
            "",
            f"CAMPAIGN: {self.campaign.title}",
            f"STORY: {self.campaign.description}",
            "",
            f"CURRENT LOCATION: {checkpoint.name}",
            f"LOCATION DESCRIPTION: {checkpoint.description}",
        ]
        
        # Add all NPCs with their knowledge so AI can have any of them respond appropriately
        if checkpoint.npcs_structured:
            context_parts.append("\nNPCs PRESENT:")
            for npc in checkpoint.npcs_structured:
                npc_info = f"- {npc.name} ({npc.role})"
                if npc.dialogue_topics:
                    topics_summary = "; ".join([f"{k}: {v[:80]}" for k, v in list(npc.dialogue_topics.items())[:3]])
                    npc_info += f" - knows about: {topics_summary}"
                context_parts.append(npc_info)
        
        # Add current conversation context based on whether this is DM action or NPC dialogue
        if is_dm_action:
            context_parts.append("\nPLAYER IS ADDRESSING THE DM: This is an action/narration request, not NPC dialogue.")
            context_parts.append("Respond as [DM] narrating the action. If player approaches an NPC, describe the approach and the NPC can speak.")
        elif current_speaker:
            context_parts.append(f"\nCURRENT CONVERSATION: Player is speaking IN CHARACTER to {current_speaker}")
            context_parts.append(f"{current_speaker} should respond to this dialogue.")
        else:
            context_parts.append("\nPLAYER IS NOT IN CONVERSATION: Respond as [DM] or have an NPC initiate.")
        
        # Add available choices as story hooks
        if checkpoint.choices:
            choice_texts = [c.text for c in checkpoint.choices]
            context_parts.append(f"\nSTORY OPTIONS: {'; '.join(choice_texts)}")
        
        # Add active quests
        active_quests = self.game_state.get_active_quests()
        if active_quests:
            quest_strs = [f"{q['name']}: {q['description']}" for q in active_quests]
            context_parts.append(f"ACTIVE QUESTS: {'; '.join(quest_strs)}")

        context_parts.append("")
        context_parts.append(f"PLAYER: {char.name} the {char.char_class} (HP: {char.hp}/{char.max_hp})")

        if self.game_state.combat_active:
            enemies_str = ", ".join([e['name'] for e in self.game_state.enemies if not e.get('defeated', False)])
            context_parts.append(f"COMBAT ACTIVE WITH: {enemies_str}")

        if char.inventory:
            context_parts.append(f"INVENTORY: {', '.join(char.inventory[:5])}")

        context_parts.append("")
        context_parts.append(f'PLAYER INPUT: "{player_input}"')
        context_parts.append("")
        context_parts.append("RESPONSE RULES:")
        context_parts.append("1. Use ONE speaker tag at the start: [DM] or [NPC_NAME]")
        context_parts.append("2. Only ONE person speaks per response")
        if is_dm_action:
            context_parts.append("3. This is a DM ACTION REQUEST - respond as [DM] narrating what happens")
            context_parts.append("4. If the player approaches/talks to an NPC, narrate the approach and show the NPC responding")
        elif current_speaker:
            context_parts.append(f"3. Player is speaking to {current_speaker} - have them respond")
        else:
            context_parts.append("3. No active conversation - use [DM] or have an NPC initiate")
        context_parts.append("")
        context_parts.append("Keep responses brief (2-3 sentences). Always start with a speaker tag.")

        # Check if player is trying to move to a new location
        # Look for movement keywords and match against available choices
        movement_keywords = ['go to', 'head to', 'travel to', 'walk to', 'leave for', 'make my way to', 'visit', 'head towards', 'go towards']
        player_input_lower = player_input.lower()
        
        location_change = None
        for choice in checkpoint.choices:
            choice_text_lower = choice.text.lower()
            # Check if any movement keyword + destination matches a choice
            for keyword in movement_keywords:
                if keyword in player_input_lower:
                    # Extract what comes after the keyword
                    destination = player_input_lower.split(keyword)[-1].strip()
                    # Check if destination matches choice text or next checkpoint
                    if (destination in choice_text_lower or 
                        choice.next_checkpoint.replace('_', ' ') in destination or
                        any(word in destination for word in choice_text_lower.split() if len(word) > 3)):
                        location_change = choice
                        logger.info(f"Detected location change: {choice.text} -> {choice.next_checkpoint}")
                        break
            if location_change:
                break
        
        # If player is moving to a new location, handle it like a choice
        if location_change:
            self.game_state.add_action(f"Traveled: {player_input}")
            transition = location_change.narration or f"You make your way to {location_change.next_checkpoint.replace('_', ' ')}..."
            new_location = self.enter_checkpoint(location_change.next_checkpoint)
            return {
                "transition": transition,
                **new_location
            }

        prompt = "\n".join(context_parts)

        logger.info("Calling Ollama for custom action...")
        response = call_ollama(prompt)

        # Record action
        self.game_state.add_action(player_input)

        # Parse response - expect ONE speaker tag at the start
        import re
        narration = response.strip()
        
        # Extract the speaker tag from the start
        speaker_tag = None
        clean_narration = narration
        
        if narration.startswith('['):
            tag_end = narration.find(']')
            if tag_end > 0:
                speaker_tag = narration[1:tag_end].strip()
                clean_narration = narration[tag_end + 1:].strip()
                logger.info(f"Speaker tag: {speaker_tag}")
        
        # Remove any additional tags that slipped through (LLM sometimes ignores instructions)
        clean_narration = re.sub(r'\[[^\]]+\]', '', clean_narration).strip()
        clean_narration = re.sub(r'  +', ' ', clean_narration)
        
        # Find the speaking NPC (if any)
        speaking_npc = None
        original_current_speaker = self.game_state.current_speaker
        
        # Bug fix: If LLM used [DM] tag but response starts with dialogue (quote) 
        # and we have a current speaker, the LLM probably made a mistake
        # Keep the current speaker in that case
        if (speaker_tag and speaker_tag.upper() == 'DM' and 
            clean_narration.startswith('"') and 
            original_current_speaker and
            not is_dm_action):
            # LLM messed up - this looks like NPC dialogue, not DM narration
            logger.info(f"Detected misattributed dialogue - keeping current speaker: {original_current_speaker}")
            for npc in checkpoint.npcs_structured:
                if npc.name == original_current_speaker:
                    speaking_npc = npc
                    speaker_tag = npc.name
                    break
        
        # Normal NPC lookup if not already found via bug fix
        if not speaking_npc and speaker_tag and speaker_tag.upper() != 'DM':
            for npc in checkpoint.npcs_structured:
                if npc.name.lower() == speaker_tag.lower():
                    speaking_npc = npc
                    break
                # Fuzzy match
                if npc.name.lower() in speaker_tag.lower() or speaker_tag.lower() in npc.name.lower():
                    speaking_npc = npc
                    break
        
        # If DM narration, check if an NPC is being introduced/speaking in the text
        # This handles cases like: [DM] Marcus approaches. "What can I do for you?"
        introduced_npc = None
        if not speaking_npc and speaker_tag and speaker_tag.upper() == 'DM':
            for npc in checkpoint.npcs_structured:
                # Check if NPC name appears in the narration (they're being introduced)
                if npc.name.lower() in clean_narration.lower():
                    introduced_npc = npc
                    logger.info(f"NPC introduced in DM narration: {npc.name}")
                    break
        
        # Update current speaker tracking
        if speaking_npc:
            self.game_state.current_speaker = speaking_npc.name
            logger.info(f"Updated current_speaker to: {speaking_npc.name}")
        elif introduced_npc:
            # NPC was introduced in DM narration - set them as current speaker for next turn
            self.game_state.current_speaker = introduced_npc.name
            logger.info(f"Set current_speaker to introduced NPC: {introduced_npc.name}")
        elif speaker_tag and speaker_tag.upper() == 'DM':
            # Pure DM narration with no NPC - clear current speaker
            self.game_state.current_speaker = None
            logger.info("Cleared current_speaker (DM narration)")
        
        # Determine display mode and portrait
        if speaking_npc:
            display_mode = "npc"
            portrait = speaking_npc.portrait_url or get_dm_portrait()
            npc_name = speaking_npc.name
            logger.info(f"NPC speaking: {npc_name}, portrait: {portrait}")
        elif introduced_npc:
            # Show the introduced NPC's portrait
            display_mode = "npc"
            portrait = introduced_npc.portrait_url or get_dm_portrait()
            npc_name = introduced_npc.name
            logger.info(f"Showing introduced NPC: {npc_name}, portrait: {portrait}")
        else:
            display_mode = "dm"
            portrait = get_dm_portrait()
            npc_name = None
            logger.info(f"DM narrating")

        # Check if a dice roll is needed
        awaiting_roll = self.detect_roll_needed(player_input, clean_narration)

        result = {
            "narration": clean_narration,
            "npc_portrait": portrait if display_mode == "npc" else None,
            "dm_portrait": portrait if display_mode == "dm" else None,
            "npc_name": npc_name,
            "display_mode": display_mode,
            "character_hp": char.hp,
            "character_max_hp": char.max_hp,
            "location": checkpoint.name,
            "inventory": char.inventory,
            "combat_active": self.game_state.combat_active
        }

        # Add awaiting_roll if a roll is needed
        if awaiting_roll:
            result["awaiting_roll"] = awaiting_roll

        return result

    def start_combat(self, enemy_names: List[str]) -> dict:
        """
        Start combat with specified enemies.
        """
        enemies = []
        for name in enemy_names:
            # Default HP based on enemy type
            hp = 15 if "elite" in name.lower() or "chief" in name.lower() else 8
            enemies.append({"name": name, "hp": hp, "defeated": False})

        self.game_state.start_combat(enemies)
        self.game_state.add_action(f"Combat started with: {', '.join(enemy_names)}")

        narration = f"Combat begins! You face {', '.join(enemy_names)}!"

        return {
            "narration": narration,
            "combat_active": True,
            "enemies": self.game_state.enemies
        }

    def attack_enemy(self, enemy_index: int, damage: int) -> dict:
        """
        Attack an enemy in combat.
        """
        if not self.game_state.combat_active:
            return {"error": "No combat active"}

        if enemy_index < 0 or enemy_index >= len(self.game_state.enemies):
            return {"error": "Invalid enemy"}

        enemy = self.game_state.enemies[enemy_index]

        if enemy.get("defeated", False):
            return {"error": f"{enemy['name']} is already defeated"}

        defeated = self.game_state.damage_enemy(enemy_index, damage)

        if defeated:
            narration = f"You strike {enemy['name']} for {damage} damage! {enemy['name']} has been defeated!"

            # Check if all enemies defeated
            all_defeated = all(e.get("defeated", False) for e in self.game_state.enemies)
            if all_defeated:
                self.game_state.end_combat()
                narration += " Victory! Combat has ended."
        else:
            narration = f"You strike {enemy['name']} for {damage} damage! ({enemy['hp']} HP remaining)"

        self.game_state.add_action(f"Attacked {enemy['name']} for {damage} damage")

        return {
            "narration": narration,
            "combat_active": self.game_state.combat_active,
            "enemies": self.game_state.enemies
        }

    def get_game_status(self) -> dict:
        """
        Get current game status for UI updates.
        """
        char = self.game_state.character
        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)

        return {
            "character_name": char.name,
            "character_class": char.char_class,
            "character_hp": char.hp,
            "character_max_hp": char.max_hp,
            "character_level": char.level,
            "inventory": char.inventory,
            "location": checkpoint.name if checkpoint else "Unknown",
            "combat_active": self.game_state.combat_active,
            "enemies": self.game_state.enemies,
            "active_quests": self.game_state.get_active_quests(),
            "npcs_met": list(self.game_state.npcs_met)
        }
