"""
State Manager - Manages game state and provides context for AI
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from datetime import datetime

from engine.schemas.campaign import Campaign, Node, NodeExit
from engine.schemas.npc import NPCRegistry, NPC
from engine.schemas.encounter import EncounterRegistry
from engine.schemas.game_state import (
    GameState, Character, Location, StoryProgress, NPCRelationship,
    Quest, QuestObjective, ConversationState, GameMode
)

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages game state and provides context for AI narration.
    """

    def __init__(
        self,
        campaign: Campaign,
        nodes: Dict[str, Node],
        npcs: NPCRegistry,
        encounters: EncounterRegistry,
        character: Optional[Character] = None
    ):
        self.campaign = campaign
        self.nodes = nodes
        self.npcs = npcs
        self.encounters = encounters
        self.character = character or Character(name="Unknown", race="human", char_class="fighter")
        self.game_state: Optional[GameState] = None

    # ===== Core State Operations =====

    def initialize_new_game(self, session_id: str = None) -> GameState:
        """
        Initialize a new game state.

        Args:
            session_id: Optional session ID, generated if not provided

        Returns:
            Fresh GameState
        """
        if session_id is None:
            session_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get starting location from campaign
        starting_chapter = self.campaign.get_starting_chapter()
        if not starting_chapter:
            raise ValueError("Campaign has no chapters defined")

        location = Location(
            chapter_id=starting_chapter.chapter_id,
            node_id=starting_chapter.starting_node
        )

        self.game_state = GameState(
            session_id=session_id,
            campaign_id=self.campaign.campaign_id,
            character=self.character,
            location=location,
            story_progress=StoryProgress(),
            relationships={},
            nodes_visited=[starting_chapter.starting_node]  # Mark starting node as visited
        )

        logger.info(f"✓ Initialized new game: {session_id}")
        logger.info(f"  Starting at: {starting_chapter.starting_node}")

        return self.game_state

    def save_state(self, filepath: str):
        """
        Save game state to JSON file.

        Args:
            filepath: Path to save file
        """
        if not self.game_state:
            raise ValueError("No game state to save")

        # TODO: Implement proper serialization
        # For now, just save a placeholder
        data = {
            "session_id": self.game_state.session_id,
            "campaign_id": self.game_state.campaign_id,
            "saved_at": datetime.now().isoformat(),
            "character_name": self.game_state.character.name,
            "current_node": self.game_state.location.node_id,
            "flags": self.game_state.story_progress.flags,
            "note": "Full serialization not yet implemented"
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"✓ Saved game state to {filepath}")

    def load_state(self, filepath: str) -> GameState:
        """
        Load game state from JSON file.

        Args:
            filepath: Path to save file

        Returns:
            Loaded GameState

        Note:
            Full deserialization not yet implemented
        """
        # TODO: Implement proper deserialization
        raise NotImplementedError("State loading not yet implemented")

    # ===== Location Management =====

    def move_to_node(self, node_id: str) -> Tuple[bool, str]:
        """
        Move player to a new node.

        Args:
            node_id: Target node ID

        Returns:
            Tuple of (success, message)
        """
        if not self.game_state:
            return False, "No active game state"

        # Check if node exists
        if node_id not in self.nodes:
            return False, f"Node '{node_id}' does not exist"

        # Check if move is valid from current location
        current_node = self.get_current_node()
        if current_node:
            available_exits = self.get_available_exits()
            # Check if this is a valid exit
            valid_exit = any(
                exit_data.target_node == node_id
                for exit_data in available_exits.values()
            )

            if not valid_exit:
                logger.warning(f"Moving to {node_id} without valid exit from {current_node.node_id}")

        # Perform the move
        self.game_state.move_to_node(node_id)
        target_node = self.nodes[node_id]

        logger.info(f"✓ Moved to {node_id}: {target_node.name}")

        return True, f"Moved to {target_node.name}"

    def get_current_node(self) -> Optional[Node]:
        """Get the current node."""
        if not self.game_state:
            return None

        node_id = self.game_state.location.node_id
        return self.nodes.get(node_id)

    def get_available_exits(self) -> Dict[str, NodeExit]:
        """
        Get exits available from current node based on game state.

        Returns:
            Dictionary of available exits
        """
        current_node = self.get_current_node()
        if not current_node:
            return {}

        # Get character inventory for exit requirements
        inventory = [item.item_id for item in self.game_state.character.inventory]

        return current_node.get_available_exits(
            self.game_state.story_progress.flags,
            inventory
        )

    # ===== Flags & Progress =====

    def set_flag(self, flag: str, value: bool = True):
        """Set a story flag."""
        if not self.game_state:
            raise ValueError("No active game state")

        self.game_state.story_progress.set_flag(flag, value)
        logger.info(f"Flag set: {flag} = {value}")

    def has_flag(self, flag: str) -> bool:
        """Check if a flag is set."""
        if not self.game_state:
            return False

        return self.game_state.story_progress.has_flag(flag)

    def check_condition(self, condition: str) -> bool:
        """
        Parse and evaluate a condition string.

        Supports:
        - Flag checks: "has_supplies"
        - Negation: "!has_supplies"
        - AND: "has_supplies && talked_to_marcus"
        - OR: "has_supplies || talked_to_tobias"

        Args:
            condition: Condition string to evaluate

        Returns:
            True if condition is met
        """
        if not self.game_state:
            return False

        # Simple expression parser
        condition = condition.strip()

        # Handle OR (||)
        if "||" in condition:
            parts = condition.split("||")
            return any(self.check_condition(p.strip()) for p in parts)

        # Handle AND (&&)
        if "&&" in condition:
            parts = condition.split("&&")
            return all(self.check_condition(p.strip()) for p in parts)

        # Handle negation (!)
        if condition.startswith("!"):
            flag = condition[1:].strip()
            return not self.has_flag(flag)

        # Simple flag check
        return self.has_flag(condition)

    # ===== Relationships =====

    def modify_relationship(
        self,
        npc_id: str,
        disposition: int = 0,
        trust: int = 0,
        event: str = ""
    ):
        """
        Modify relationship with an NPC.

        Args:
            npc_id: NPC identifier
            disposition: Change to disposition (-100 to 100)
            trust: Change to trust
            event: Description of what caused the change
        """
        if not self.game_state:
            raise ValueError("No active game state")

        relationship = self.game_state.get_relationship(npc_id)

        if disposition != 0:
            relationship.modify_disposition(disposition, event or "player_action")

        if trust != 0:
            old_trust = relationship.trust
            relationship.trust = max(0, min(100, relationship.trust + trust))
            logger.info(f"Trust with {npc_id}: {old_trust} -> {relationship.trust}")

        logger.info(f"Relationship with {npc_id}: disposition={relationship.disposition}, trust={relationship.trust}")

    def get_npc_attitude(self, npc_id: str) -> str:
        """
        Get NPC's attitude toward player.

        Returns:
            Attitude string: "hostile", "unfriendly", "neutral", "friendly", "devoted"
        """
        if not self.game_state:
            return "neutral"

        relationship = self.game_state.get_relationship(npc_id)
        return relationship.get_attitude()

    def get_npc_disposition(self, npc_id: str) -> int:
        """Get NPC's disposition value."""
        if not self.game_state:
            # Return NPC's base disposition
            npc = self.npcs.get(npc_id)
            return npc.base_disposition if npc else 50

        relationship = self.game_state.get_relationship(npc_id)
        return relationship.disposition

    # ===== Quests =====

    def start_quest(self, quest_id: str, name: str = None, description: str = ""):
        """
        Start a new quest.

        Args:
            quest_id: Quest identifier
            name: Quest name (defaults to quest_id)
            description: Quest description
        """
        if not self.game_state:
            raise ValueError("No active game state")

        quest = Quest(
            quest_id=quest_id,
            name=name or quest_id,
            description=description,
            status="active"
        )

        self.game_state.story_progress.quests.append(quest)
        logger.info(f"✓ Started quest: {quest.name}")

    def complete_objective(self, quest_id: str, objective_id: str):
        """
        Complete a quest objective.

        Args:
            quest_id: Quest identifier
            objective_id: Objective identifier
        """
        if not self.game_state:
            raise ValueError("No active game state")

        for quest in self.game_state.story_progress.quests:
            if quest.quest_id == quest_id:
                for objective in quest.objectives:
                    if objective.id == objective_id:
                        objective.completed = True
                        objective.completed_at = datetime.now()
                        logger.info(f"✓ Completed objective: {quest.name} - {objective.description}")
                        return

        logger.warning(f"Objective not found: {quest_id}.{objective_id}")

    # ===== Conversation =====

    def set_current_speaker(self, npc_id: Optional[str]):
        """Set the current NPC being spoken to."""
        if not self.game_state:
            raise ValueError("No active game state")

        self.game_state.conversation.current_speaker = npc_id
        if npc_id:
            self.game_state.conversation.mode = GameMode.DIALOGUE
            logger.info(f"Now speaking with: {npc_id}")
        else:
            self.game_state.conversation.mode = GameMode.EXPLORATION
            logger.info("Conversation ended")

    def add_dialogue(self, speaker: str, text: str):
        """
        Add dialogue to conversation history.

        Args:
            speaker: Who is speaking ("player", "dm", or npc_id)
            text: What was said
        """
        if not self.game_state:
            raise ValueError("No active game state")

        self.game_state.conversation.add_exchange(speaker, text)

    # ===== Context for AI =====

    def get_context_for_ai(self) -> Dict:
        """
        Build focused context for AI narration.

        Returns:
            Dictionary with all relevant context for the current situation
        """
        if not self.game_state:
            raise ValueError("No active game state")

        current_node = self.get_current_node()
        if not current_node:
            return {"error": "No current node"}

        # Build context
        context = {
            # Campaign info
            "campaign": {
                "title": self.campaign.title,
                "description": self.campaign.description
            },

            # Current location
            "location": {
                "node_id": current_node.node_id,
                "name": current_node.name,
                "description": current_node.description.long,
                "atmosphere": {
                    "sounds": current_node.ambient.sounds,
                    "smells": current_node.ambient.smells,
                    "mood": current_node.ambient.mood
                }
            },

            # Character
            "character": {
                "name": self.game_state.character.name,
                "race": self.game_state.character.race,
                "class": self.game_state.character.char_class,
                "level": self.game_state.character.level,
                "hp": self.game_state.character.hp.current,
                "max_hp": self.game_state.character.hp.max
            },

            # NPCs present
            "npcs_present": [],

            # Available actions
            "available_exits": {},

            # Story state
            "flags": self.game_state.story_progress.flags.copy(),
            "active_quests": [],

            # Conversation state
            "conversation": {
                "mode": self.game_state.conversation.mode.value,
                "current_speaker": self.game_state.conversation.current_speaker
            }
        }

        # Add NPCs present with relationship info
        for npc_presence in current_node.npcs_present:
            npc = self.npcs.get(npc_presence.npc_id)
            if npc:
                disposition = self.get_npc_disposition(npc_presence.npc_id)
                attitude = self.get_npc_attitude(npc_presence.npc_id)

                context["npcs_present"].append({
                    "npc_id": npc.npc_id,
                    "name": npc.name,
                    "role": npc.role,
                    "description": npc.appearance.short,
                    "attitude": attitude,
                    "disposition": disposition,
                    "topics": npc_presence.topics
                })

        # Add available exits
        for exit_id, exit_data in self.get_available_exits().items():
            context["available_exits"][exit_id] = {
                "description": exit_data.description,
                "direction": exit_data.direction,
                "target": exit_data.target_node
            }

        # Add active quests
        for quest in self.game_state.story_progress.get_active_quests():
            context["active_quests"].append({
                "name": quest.name,
                "description": quest.description
            })

        return context

    def get_npc_knowledge(self, npc_id: str, topic_id: str) -> Optional[str]:
        """
        Get NPC's knowledge on a topic if they're willing to share.

        Args:
            npc_id: NPC identifier
            topic_id: Topic identifier

        Returns:
            Information string or None if NPC won't share
        """
        npc = self.npcs.get(npc_id)
        if not npc:
            return None

        relationship = self.game_state.get_relationship(npc_id)

        if npc.can_share_topic(topic_id, relationship.trust, self.game_state.story_progress.flags):
            return npc.get_topic_info(topic_id)

        return None

    def get_npc_greeting(self, npc_id: str) -> str:
        """Get appropriate greeting for NPC based on relationship."""
        npc = self.npcs.get(npc_id)
        if not npc:
            return "Hello."

        disposition = self.get_npc_disposition(npc_id)
        relationship = self.game_state.get_relationship(npc_id)

        # First meeting vs subsequent
        if not relationship.met:
            relationship.met = True
            return npc.dialogue.greeting_first

        return npc.get_greeting(disposition)

    def execute_significant_action(self, action_id: str) -> Tuple[bool, str, Dict]:
        """
        Execute a significant action and apply its effects.

        Args:
            action_id: Action identifier from current node

        Returns:
            Tuple of (success, message, effects_applied)
        """
        current_node = self.get_current_node()
        if not current_node or action_id not in current_node.significant_actions:
            return False, f"Action '{action_id}' not available", {}

        action = current_node.significant_actions[action_id]

        # Check requirements
        # Check flags
        for flag in action.requires_flags:
            if not self.has_flag(flag):
                return False, f"Missing required flag: {flag}", {}

        # Check items
        inventory_ids = [item.item_id for item in self.game_state.character.inventory]
        for item_id in action.requires_items:
            if item_id not in inventory_ids:
                return False, f"Missing required item: {item_id}", {}

        # Check relationships
        if action.requires_relationship:
            for npc_id, min_disp in action.requires_relationship.items():
                current_disp = self.get_npc_disposition(npc_id)
                if current_disp < min_disp:
                    return False, f"Insufficient relationship with {npc_id}", {}

        # Execute effects
        effects = {}

        # Set flags
        for flag in action.sets_flags:
            self.set_flag(flag, True)
            effects.setdefault("flags_set", []).append(flag)

        # Clear flags
        for flag in action.clears_flags:
            self.set_flag(flag, False)
            effects.setdefault("flags_cleared", []).append(flag)

        # Update relationships
        for npc_id, update in action.updates_relationships.items():
            self.modify_relationship(
                npc_id,
                disposition=update.disposition,
                trust=update.trust,
                event=action_id
            )
            effects.setdefault("relationships_modified", []).append(npc_id)

        # Start quest
        if action.grants_quest:
            self.start_quest(action.grants_quest)
            effects["quest_started"] = action.grants_quest

        # Complete objective
        if action.completes_objective:
            quest_id, obj_id = action.completes_objective.split(".", 1)
            self.complete_objective(quest_id, obj_id)
            effects["objective_completed"] = action.completes_objective

        # Grant XP
        if action.grants_xp > 0:
            self.game_state.character.experience += action.grants_xp
            effects["xp_granted"] = action.grants_xp

        # Record action
        self.game_state.record_action(action_id, {"effects": effects})

        message = action.success_prompt or f"Successfully executed {action_id}"
        logger.info(f"✓ Executed action: {action_id}")

        return True, message, effects
