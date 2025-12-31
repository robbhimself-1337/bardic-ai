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

    def process_custom_action(self, player_input: str) -> dict:
        """
        Handle free-form player action. This is where Ollama is used.
        Detects which NPC is speaking in the response and shows their portrait.
        """
        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)
        char = self.game_state.character

        # Build context with campaign story info
        context_parts = [
            "You are a D&D Dungeon Master running a specific campaign.",
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
        context_parts.append(f'PLAYER ACTION: "{player_input}"')
        context_parts.append("")
        context_parts.append("CRITICAL - YOU MUST START YOUR RESPONSE WITH A SPEAKER TAG:")
        context_parts.append("[DM] if narrating the scene or environment")
        context_parts.append("[NPC_NAME] if an NPC is speaking, using their exact name")
        context_parts.append("")
        context_parts.append("Examples:")
        context_parts.append('[Ameiko] "Welcome, traveler! What brings you here?"')
        context_parts.append('[DM] The tavern falls silent as you enter.')
        context_parts.append('[Guard Captain Marcus] "We need your help with the goblin problem."')
        context_parts.append("")
        context_parts.append("Now respond to the player action. Keep it brief (2-3 sentences). Always start with a speaker tag.")

        prompt = "\n".join(context_parts)

        logger.info("Calling Ollama for custom action...")
        response = call_ollama(prompt)

        # Record action
        self.game_state.add_action(player_input)

        # Parse speaker tag from response
        speaking_npc = None
        narration = response.strip()
        
        # Look for [Speaker] tag at the start
        if narration.startswith('['):
            tag_end = narration.find(']')
            if tag_end > 0:
                speaker_tag = narration[1:tag_end].strip()
                narration = narration[tag_end + 1:].strip()
                
                logger.info(f"Speaker tag found: {speaker_tag}")
                
                # Check if it's an NPC
                if speaker_tag.upper() != 'DM':
                    logger.info(f"Looking for NPC match. NPCs available: {[npc.name for npc in checkpoint.npcs_structured]}")
                    for npc in checkpoint.npcs_structured:
                        logger.info(f"Comparing '{npc.name.lower()}' == '{speaker_tag.lower()}'")
                        if npc.name.lower() == speaker_tag.lower():
                            speaking_npc = npc
                            logger.info(f"MATCH FOUND: {npc.name}")
                            break
                    # Fuzzy match - check if tag contains NPC name
                    if not speaking_npc:
                        for npc in checkpoint.npcs_structured:
                            if npc.name.lower() in speaker_tag.lower() or speaker_tag.lower() in npc.name.lower():
                                speaking_npc = npc
                                logger.info(f"FUZZY MATCH FOUND: {npc.name}")
                                break
                    if not speaking_npc:
                        logger.info(f"NO NPC MATCH for tag: {speaker_tag}")
        
        # Fallback: if no tag found, check if NPC name appears early in response
        # Fallback: if no tag found, check if NPC name appears early in response
        if not speaking_npc:
            narration_lower = narration.lower()
            for npc in checkpoint.npcs_structured:
                if npc.name.lower() in narration_lower[:80]:
                    speaking_npc = npc
                    logger.info(f"Matched NPC '{npc.name}' via fallback (name in first 80 chars)")
                    break

        # Determine display mode and portrait
        if speaking_npc:
            display_mode = "npc"
            portrait = speaking_npc.portrait_url or get_dm_portrait()
            npc_name = speaking_npc.name
            logger.info(f"NPC speaking: {npc_name}, portrait: {portrait}")
        else:
            display_mode = "dm" 
            portrait = get_dm_portrait()
            npc_name = None

        return {
            "narration": narration,  # Use cleaned narration without tag
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
