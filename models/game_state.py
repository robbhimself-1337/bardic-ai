import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class Character:
    """Represents a player character with stats, inventory, and state."""

    def __init__(
        self,
        name: str,
        char_class: str = "Fighter",
        level: int = 1,
        hp: Optional[int] = None,
        max_hp: int = 20,
        inventory: Optional[List[str]] = None,
        stats: Optional[Dict[str, int]] = None
    ):
        self.name = name
        self.char_class = char_class
        self.level = level
        self.max_hp = max_hp
        self.hp = hp if hp is not None else max_hp
        self.inventory = inventory if inventory is not None else []
        self.stats = stats if stats is not None else self._default_stats(char_class)

    def _default_stats(self, char_class: str) -> Dict[str, int]:
        """Generate default stats based on class."""
        base_stats = {
            "Fighter": {"strength": 16, "dexterity": 12, "constitution": 14, "intelligence": 10, "wisdom": 11, "charisma": 10},
            "Rogue": {"strength": 10, "dexterity": 16, "constitution": 12, "intelligence": 12, "wisdom": 13, "charisma": 14},
            "Wizard": {"strength": 8, "dexterity": 12, "constitution": 12, "intelligence": 16, "wisdom": 14, "charisma": 10}
        }
        return base_stats.get(char_class, base_stats["Fighter"])

    def take_damage(self, amount: int) -> bool:
        """
        Apply damage to character.
        Returns True if character is still alive, False if dead.
        """
        self.hp = max(0, self.hp - amount)
        return self.hp > 0

    def heal(self, amount: int):
        """Heal character, up to max HP."""
        self.hp = min(self.max_hp, self.hp + amount)

    def add_item(self, item: str):
        """Add item to inventory."""
        self.inventory.append(item)

    def remove_item(self, item: str) -> bool:
        """
        Remove item from inventory.
        Returns True if successful, False if item not found.
        """
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False

    def has_item(self, item: str) -> bool:
        """Check if character has an item."""
        return item in self.inventory

    def to_dict(self) -> dict:
        """Convert character to dictionary for serialization."""
        return {
            "name": self.name,
            "char_class": self.char_class,
            "level": self.level,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "inventory": self.inventory,
            "stats": self.stats
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        """Create character from dictionary."""
        return cls(
            name=data["name"],
            char_class=data["char_class"],
            level=data["level"],
            hp=data["hp"],
            max_hp=data["max_hp"],
            inventory=data["inventory"],
            stats=data["stats"]
        )


class GameState:
    """Manages the complete game state including character, progress, and narrative."""

    def __init__(
        self,
        character: Character,
        campaign_id: str,
        current_checkpoint: str,
        quest_log: Optional[List[Dict]] = None,
        npcs_met: Optional[List[str]] = None,
        decisions_made: Optional[List[str]] = None,
        combat_active: bool = False,
        enemies: Optional[List[Dict]] = None,
        narrative_summary: Optional[str] = None,
        action_history: Optional[List[str]] = None,
        current_speaker: Optional[str] = None  # Track who player is talking to
    ):
        self.character = character
        self.campaign_id = campaign_id
        self.current_checkpoint = current_checkpoint
        self.quest_log = quest_log if quest_log is not None else []
        self.npcs_met = npcs_met if npcs_met is not None else []
        self.decisions_made = decisions_made if decisions_made is not None else []
        self.combat_active = combat_active
        self.enemies = enemies if enemies is not None else []
        self.narrative_summary = narrative_summary if narrative_summary is not None else ""
        self.action_history = action_history if action_history is not None else []
        self.current_speaker = current_speaker  # None means DM/scene, string means NPC name
        self.created_at = datetime.now().isoformat()
        self.last_saved = datetime.now().isoformat()

    def add_quest(self, quest_name: str, description: str):
        """Add a new quest to the quest log."""
        quest = {
            "name": quest_name,
            "description": description,
            "completed": False,
            "added_at": datetime.now().isoformat()
        }
        self.quest_log.append(quest)

    def complete_quest(self, quest_name: str) -> bool:
        """
        Mark a quest as completed.
        Returns True if quest found and completed, False otherwise.
        """
        for quest in self.quest_log:
            if quest["name"] == quest_name and not quest["completed"]:
                quest["completed"] = True
                quest["completed_at"] = datetime.now().isoformat()
                return True
        return False

    def add_npc(self, npc_name: str):
        """Record that player has met an NPC."""
        if npc_name not in self.npcs_met:
            self.npcs_met.append(npc_name)

    def add_decision(self, decision: str):
        """Record a significant decision made by the player."""
        self.decisions_made.append({
            "decision": decision,
            "timestamp": datetime.now().isoformat()
        })

    def start_combat(self, enemies: List[Dict]):
        """Initialize combat with given enemies."""
        self.combat_active = True
        self.enemies = enemies

    def end_combat(self):
        """End combat and clear enemies."""
        self.combat_active = False
        self.enemies = []

    def damage_enemy(self, enemy_id: int, amount: int) -> bool:
        """
        Damage an enemy in combat.
        Returns True if enemy defeated, False otherwise.
        """
        if 0 <= enemy_id < len(self.enemies):
            enemy = self.enemies[enemy_id]
            enemy["hp"] = max(0, enemy["hp"] - amount)
            if enemy["hp"] <= 0:
                enemy["defeated"] = True
                return True
        return False

    def advance_checkpoint(self, next_checkpoint: str, summary: str):
        """
        Move to next checkpoint and save summary of previous events.
        """
        self.current_checkpoint = next_checkpoint
        if summary:
            self.narrative_summary += f"\n[Checkpoint: {next_checkpoint}] {summary}"

    def add_action(self, action: str):
        """Add player action to history (for context)."""
        self.action_history.append({
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 10 actions for context
        if len(self.action_history) > 10:
            self.action_history = self.action_history[-10:]

    def save_game(self, filename: str) -> str:
        """
        Save game state to JSON file.
        Returns the full path to the saved file.
        """
        save_dir = "data/campaigns/saves"
        os.makedirs(save_dir, exist_ok=True)

        # Update last saved timestamp
        self.last_saved = datetime.now().isoformat()

        save_data = {
            "character": self.character.to_dict(),
            "campaign_id": self.campaign_id,
            "current_checkpoint": self.current_checkpoint,
            "quest_log": self.quest_log,
            "npcs_met": self.npcs_met,
            "decisions_made": self.decisions_made,
            "combat_active": self.combat_active,
            "enemies": self.enemies,
            "narrative_summary": self.narrative_summary,
            "action_history": self.action_history,
            "current_speaker": self.current_speaker,
            "created_at": self.created_at,
            "last_saved": self.last_saved
        }

        filepath = os.path.join(save_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)

        return filepath

    @classmethod
    def load_game(cls, filename: str) -> 'GameState':
        """Load game state from JSON file."""
        filepath = os.path.join("data/campaigns/saves", filename)

        with open(filepath, 'r') as f:
            data = json.load(f)

        character = Character.from_dict(data["character"])

        game_state = cls(
            character=character,
            campaign_id=data["campaign_id"],
            current_checkpoint=data["current_checkpoint"],
            quest_log=data.get("quest_log", []),
            npcs_met=data.get("npcs_met", []),
            decisions_made=data.get("decisions_made", []),
            combat_active=data.get("combat_active", False),
            enemies=data.get("enemies", []),
            narrative_summary=data.get("narrative_summary", ""),
            action_history=data.get("action_history", []),
            current_speaker=data.get("current_speaker", None)
        )

        game_state.created_at = data.get("created_at", datetime.now().isoformat())
        game_state.last_saved = data.get("last_saved", datetime.now().isoformat())

        return game_state

    def get_active_quests(self) -> List[Dict]:
        """Get list of active (incomplete) quests."""
        return [q for q in self.quest_log if not q["completed"]]

    def get_completed_quests(self) -> List[Dict]:
        """Get list of completed quests."""
        return [q for q in self.quest_log if q["completed"]]
