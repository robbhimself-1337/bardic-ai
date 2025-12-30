import re
import logging
from typing import Dict, List, Tuple, Optional
from models.game_state import GameState, Character
from models.campaign import Campaign
from services.ollama_client import call_ollama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DMEngine:
    """
    Core DM engine that manages narrative, context, and function calling.
    Integrates Ollama with game state management.
    """

    def __init__(self, game_state: GameState, campaign: Campaign):
        self.game_state = game_state
        self.campaign = campaign

    def build_context(self) -> str:
        """
        Build complete context for Ollama including checkpoint, character state,
        quests, and recent events.
        """
        context_parts = []

        # System instructions
        context_parts.append(
            "You are an expert Dungeon Master running a D&D adventure. "
            "Narrate the story vividly and react to player actions naturally. "
            "You can call functions to affect game state using the format: [FUNCTION: function_name(args)]"
        )

        # Available functions
        context_parts.append(
            "\nAvailable Functions:\n"
            "- damage_player(amount) - Deal damage to player\n"
            "- damage_enemy(enemy_id, amount) - Deal damage to enemy (use enemy_id 0 for first enemy, 1 for second, etc)\n"
            "- add_item(item_name) - Add item to player inventory\n"
            "- remove_item(item_name) - Remove item from player inventory\n"
            "- start_combat(enemies) - Enemies should be in format: 'enemy1,enemy2'\n"
            "- end_combat() - End current combat\n"
            "- advance_checkpoint(next_checkpoint_id, summary) - Move to next location with summary\n"
            "- add_quest(quest_name, description) - Add new quest\n"
            "- complete_quest(quest_name) - Mark quest as complete\n"
        )

        # Current checkpoint context
        checkpoint = self.campaign.get_checkpoint(self.game_state.current_checkpoint)
        if checkpoint:
            context_parts.append(f"\n{self.campaign.get_checkpoint_context(self.game_state.current_checkpoint)}")

        # Character state
        char = self.game_state.character
        context_parts.append(
            f"\nPlayer Character: {char.name} the {char.char_class}\n"
            f"HP: {char.hp}/{char.max_hp}\n"
            f"Level: {char.level}\n"
            f"Inventory: {', '.join(char.inventory) if char.inventory else 'Empty'}"
        )

        # Active quests
        active_quests = self.game_state.get_active_quests()
        if active_quests:
            context_parts.append("\nActive Quests:")
            for quest in active_quests:
                context_parts.append(f"- {quest['name']}: {quest['description']}")

        # Combat state
        if self.game_state.combat_active:
            context_parts.append("\nCombat Active! Enemies:")
            for i, enemy in enumerate(self.game_state.enemies):
                status = "DEFEATED" if enemy.get("defeated", False) else f"HP: {enemy['hp']}"
                context_parts.append(f"  [{i}] {enemy['name']} - {status}")

        # NPCs met
        if self.game_state.npcs_met:
            context_parts.append(f"\nNPCs Met: {', '.join(self.game_state.npcs_met)}")

        # Narrative summary (compressed history)
        if self.game_state.narrative_summary:
            context_parts.append(f"\nStory So Far: {self.game_state.narrative_summary}")

        # Recent actions (last few for immediate context)
        if self.game_state.action_history:
            context_parts.append("\nRecent Actions:")
            for action in self.game_state.action_history[-3:]:
                context_parts.append(f"- {action['action']}")

        return "\n".join(context_parts)

    def parse_function_calls(self, response: str) -> Tuple[str, List[Dict]]:
        """
        Parse Ollama response for function calls.
        Returns (narrative_text, function_calls)

        Function call format: [FUNCTION: function_name(arg1, arg2)]
        """
        function_calls = []
        narrative = response

        # Find all function calls
        pattern = r'\[FUNCTION:\s*(\w+)\((.*?)\)\]'
        matches = re.findall(pattern, response)

        for match in matches:
            function_name = match[0]
            args_str = match[1].strip()

            # Parse arguments
            args = []
            if args_str:
                # Handle both quoted and unquoted arguments
                args = [arg.strip().strip('"').strip("'") for arg in args_str.split(',')]

            function_calls.append({
                "function": function_name,
                "args": args
            })

        # Remove function calls from narrative
        narrative = re.sub(pattern, '', narrative).strip()

        return narrative, function_calls

    def execute_function(self, function_name: str, args: List[str]) -> str:
        """
        Execute a function call and return result message.
        """
        try:
            if function_name == "damage_player":
                amount = int(args[0])
                alive = self.game_state.character.take_damage(amount)
                if alive:
                    return f"Player took {amount} damage. HP: {self.game_state.character.hp}/{self.game_state.character.max_hp}"
                else:
                    return f"Player has been defeated!"

            elif function_name == "damage_enemy":
                enemy_id = int(args[0])
                amount = int(args[1])
                defeated = self.game_state.damage_enemy(enemy_id, amount)
                if defeated:
                    enemy_name = self.game_state.enemies[enemy_id]['name']
                    return f"{enemy_name} has been defeated!"
                return f"Enemy took {amount} damage."

            elif function_name == "add_item":
                item_name = args[0]
                self.game_state.character.add_item(item_name)
                return f"Added {item_name} to inventory."

            elif function_name == "remove_item":
                item_name = args[0]
                self.game_state.character.remove_item(item_name)
                return f"Removed {item_name} from inventory."

            elif function_name == "start_combat":
                enemy_names = args[0].split(',')
                enemies = []
                for name in enemy_names:
                    name = name.strip()
                    # Default HP based on enemy type
                    hp = 15 if "elite" in name.lower() or "chief" in name.lower() else 8
                    enemies.append({"name": name, "hp": hp, "defeated": False})
                self.game_state.start_combat(enemies)
                return f"Combat started with: {', '.join(enemy_names)}"

            elif function_name == "end_combat":
                self.game_state.end_combat()
                return "Combat ended."

            elif function_name == "advance_checkpoint":
                next_checkpoint = args[0]
                summary = args[1] if len(args) > 1 else ""
                self.game_state.advance_checkpoint(next_checkpoint, summary)
                return f"Advanced to checkpoint: {next_checkpoint}"

            elif function_name == "add_quest":
                quest_name = args[0]
                description = args[1] if len(args) > 1 else ""
                self.game_state.add_quest(quest_name, description)
                return f"Quest added: {quest_name}"

            elif function_name == "complete_quest":
                quest_name = args[0]
                self.game_state.complete_quest(quest_name)
                return f"Quest completed: {quest_name}"

            else:
                return f"Unknown function: {function_name}"

        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return f"Error executing {function_name}: {str(e)}"

    def process_action(self, player_action: str) -> Dict:
        """
        Process player action through Ollama and execute any function calls.
        Returns dict with narrative, function_results, and game_state updates.
        """
        # Add action to history
        self.game_state.add_action(player_action)

        # Build context
        context = self.build_context()

        # Create DM prompt
        prompt = f"{context}\n\nPlayer Action: {player_action}\n\nDM Response:"

        # Call Ollama
        logger.info("Calling Ollama for DM response...")
        response = call_ollama(prompt)

        # Parse function calls
        narrative, function_calls = self.parse_function_calls(response)

        # Execute function calls
        function_results = []
        for func_call in function_calls:
            result = self.execute_function(func_call["function"], func_call["args"])
            function_results.append({
                "function": func_call["function"],
                "args": func_call["args"],
                "result": result
            })
            logger.info(f"Function executed: {func_call['function']} -> {result}")

        return {
            "narrative": narrative,
            "function_calls": function_calls,
            "function_results": function_results,
            "character_hp": self.game_state.character.hp,
            "character_max_hp": self.game_state.character.max_hp,
            "inventory": self.game_state.character.inventory,
            "combat_active": self.game_state.combat_active,
            "enemies": self.game_state.enemies,
            "active_quests": self.game_state.get_active_quests()
        }

    def checkpoint_transition(self, next_checkpoint_id: str, summary: str):
        """
        Handle checkpoint transition with context reset.
        """
        if not self.campaign.validate_checkpoint_transition(
            self.game_state.current_checkpoint,
            next_checkpoint_id
        ):
            logger.warning(f"Invalid checkpoint transition: {self.game_state.current_checkpoint} -> {next_checkpoint_id}")
            return False

        # Advance checkpoint
        self.game_state.advance_checkpoint(next_checkpoint_id, summary)

        # Auto-add quests for new checkpoint
        checkpoint = self.campaign.get_checkpoint(next_checkpoint_id)
        if checkpoint and checkpoint.auto_quests:
            for quest in checkpoint.auto_quests:
                self.game_state.add_quest(quest["name"], quest["description"])

        logger.info(f"Transitioned to checkpoint: {next_checkpoint_id}")
        return True
