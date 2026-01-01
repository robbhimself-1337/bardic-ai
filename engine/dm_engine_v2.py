"""
New DM Engine - Uses StateManager and node-based context for reliable AI responses.

This replaces the old dm_engine.py with a cleaner architecture that:
1. Builds focused prompts from node context
2. Validates AI responses against known data
3. Handles portraits/images deterministically
4. Updates state through StateManager
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass

from engine.state_manager import StateManager
from engine.schemas import Node, NPC, GameMode

logger = logging.getLogger(__name__)


class PlayerIntentType(Enum):
    """What the player is trying to do"""
    DIALOGUE = "dialogue"           # Talking to an NPC
    ACTION = "action"               # Doing something (search, use item, etc.)
    MOVEMENT = "movement"           # Going somewhere
    COMBAT = "combat"               # Fighting
    SYSTEM = "system"               # Meta commands (save, inventory, etc.)


@dataclass
class PlayerIntent:
    """Parsed player intent"""
    type: PlayerIntentType
    target: Optional[str] = None    # NPC id, exit id, item id, etc.
    raw_input: str = ""
    cleaned_input: str = ""
    is_dm_addressed: bool = False   # Player said "Joe" or "DM"


@dataclass 
class DMResponse:
    """Structured response from the DM engine"""
    narration: str                  # The text to speak/display
    speaker: str                    # "dm" or npc_id
    portrait_type: str              # "dm", "npc", "scene"
    portrait_source: str            # Path/URL or generation prompt
    
    # State changes to apply
    set_flags: List[str] = None
    clear_flags: List[str] = None
    relationship_changes: Dict[str, Dict] = None
    xp_gained: int = 0
    items_gained: List[str] = None
    items_lost: List[str] = None
    
    # Navigation
    move_to_node: Optional[str] = None
    trigger_encounter: Optional[str] = None
    
    def __post_init__(self):
        self.set_flags = self.set_flags or []
        self.clear_flags = self.clear_flags or []
        self.relationship_changes = self.relationship_changes or {}
        self.items_gained = self.items_gained or []
        self.items_lost = self.items_lost or []


class NewDMEngine:
    """
    DM Engine that uses node-based context for reliable responses.
    """
    
    # Patterns for detecting DM-addressed input
    DM_ADDRESS_PATTERNS = [
        r'\bjoe\b',
        r'\bdm\b', 
        r'\bdungeon\s*master\b',
    ]
    
    # Words to strip from cleaned input
    FILLER_WORDS = ['ok', 'okay', 'alright', 'hey', 'so', 'well', 'um', 'uh']
    
    def __init__(self, state_manager: StateManager, ollama_caller):
        """
        Initialize the DM engine.
        
        Args:
            state_manager: The StateManager instance
            ollama_caller: Function to call Ollama (text) -> response
        """
        self.state_manager = state_manager
        self.call_ollama = ollama_caller
        
        # Cache for generated images
        self.portrait_cache: Dict[str, str] = {}
        self.scene_cache: Dict[str, str] = {}
    
    # =========================================================================
    # INPUT PARSING
    # =========================================================================
    
    def parse_player_input(self, raw_input: str) -> PlayerIntent:
        """
        Parse player input to determine intent.
        
        Args:
            raw_input: What the player said/typed
            
        Returns:
            PlayerIntent with type and cleaned input
        """
        input_lower = raw_input.lower().strip()
        
        # Check if addressing DM
        is_dm_addressed = any(
            re.search(pattern, input_lower) 
            for pattern in self.DM_ADDRESS_PATTERNS
        )
        
        # Clean the input
        cleaned = self._clean_input(raw_input)
        
        # Determine intent type
        intent_type = self._classify_intent(cleaned, is_dm_addressed)
        
        # Find target if applicable
        target = self._find_target(cleaned, intent_type)
        
        return PlayerIntent(
            type=intent_type,
            target=target,
            raw_input=raw_input,
            cleaned_input=cleaned,
            is_dm_addressed=is_dm_addressed
        )
    
    def _clean_input(self, raw_input: str) -> str:
        """Remove DM address and filler words from input."""
        cleaned = raw_input.lower()
        
        # Remove DM address patterns
        for pattern in self.DM_ADDRESS_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned)
        
        # Remove filler words at start
        words = cleaned.split()
        while words and words[0].strip('.,!?') in self.FILLER_WORDS:
            words.pop(0)
        
        # Remove leading punctuation/commas
        cleaned = ' '.join(words).strip()
        cleaned = re.sub(r'^[,.\s]+', '', cleaned)
        
        return cleaned.strip()
    
    def _classify_intent(self, cleaned_input: str, is_dm_addressed: bool) -> PlayerIntentType:
        """Classify what type of action the player wants."""
        input_lower = cleaned_input.lower()
        
        # Movement keywords
        movement_keywords = [
            'go to', 'head to', 'walk to', 'travel to', 'leave', 
            'exit', 'enter', 'move to', 'go back', 'return to'
        ]
        if any(kw in input_lower for kw in movement_keywords):
            return PlayerIntentType.MOVEMENT
        
        # If DM addressed, it's an action request
        if is_dm_addressed:
            return PlayerIntentType.ACTION
        
        # Combat keywords
        combat_keywords = ['attack', 'fight', 'strike', 'hit', 'cast', 'shoot']
        if any(kw in input_lower for kw in combat_keywords):
            return PlayerIntentType.COMBAT
        
        # System keywords
        system_keywords = ['save', 'load', 'inventory', 'character', 'stats', 'help']
        if any(kw in input_lower for kw in system_keywords):
            return PlayerIntentType.SYSTEM
        
        # Default: if there's a current speaker, assume dialogue
        if self.state_manager.game_state.conversation.current_speaker:
            return PlayerIntentType.DIALOGUE
        
        # Otherwise, it's a general action
        return PlayerIntentType.ACTION
    
    def _find_target(self, cleaned_input: str, intent_type: PlayerIntentType) -> Optional[str]:
        """Find the target of the player's action."""
        input_lower = cleaned_input.lower()
        node = self.state_manager.get_current_node()
        
        if intent_type == PlayerIntentType.MOVEMENT:
            # Check exits
            for exit_id, exit_data in self.state_manager.get_available_exits().items():
                # Check if target node name or direction mentioned
                if exit_data.target_node.lower() in input_lower:
                    return exit_data.target_node
                if exit_data.direction and exit_data.direction.lower() in input_lower:
                    return exit_data.target_node
                # Check description keywords
                desc_words = exit_data.description.lower().split()
                if any(word in input_lower for word in desc_words if len(word) > 3):
                    return exit_data.target_node
        
        elif intent_type == PlayerIntentType.DIALOGUE:
            # Check NPCs present
            for npc_presence in node.npcs_present:
                npc = self.state_manager.npcs.get(npc_presence.npc_id)
                if npc and npc.name.lower() in input_lower:
                    return npc_presence.npc_id
            
            # Default to current speaker
            return self.state_manager.game_state.conversation.current_speaker
        
        return None
    
    # =========================================================================
    # PROMPT BUILDING
    # =========================================================================
    
    def build_prompt(self, intent: PlayerIntent) -> str:
        """
        Build a focused prompt for Ollama based on intent and context.
        """
        context = self.state_manager.get_context_for_ai()
        node = self.state_manager.get_current_node()
        
        # Base system context
        prompt_parts = [
            "You are the Dungeon Master for a D&D game.",
            f"Campaign: {context['campaign']['title']}",
            "",
            f"CURRENT LOCATION: {context['location']['name']}",
            f"Description: {context['location']['description']}",
            f"Atmosphere: {context['location']['atmosphere']['mood']}",
            ""
        ]
        
        # Add NPCs present
        if context['npcs_present']:
            prompt_parts.append("NPCs PRESENT:")
            for npc in context['npcs_present']:
                prompt_parts.append(
                    f"  - {npc['name']} ({npc['npc_id']}): {npc['description']}"
                )
                prompt_parts.append(f"    Attitude toward player: {npc['attitude']}")
            prompt_parts.append("")
        else:
            prompt_parts.append("No NPCs present at this location.")
            prompt_parts.append("")
        
        # Add current conversation context
        current_speaker = self.state_manager.game_state.conversation.current_speaker
        if current_speaker:
            npc = self.state_manager.npcs.get(current_speaker)
            if npc:
                prompt_parts.append(f"CURRENT CONVERSATION: Player is talking to {npc.name}")
                prompt_parts.append(f"  Personality: {', '.join(npc.personality.traits)}")
                prompt_parts.append(f"  Voice style: {npc.voice.style}")
                if npc.voice.speech_patterns:
                    prompt_parts.append(f"  Speech patterns: {', '.join(npc.voice.speech_patterns)}")
                prompt_parts.append("")
        
        # Intent-specific instructions
        if intent.type == PlayerIntentType.DIALOGUE:
            prompt_parts.extend(self._build_dialogue_instructions(intent, current_speaker))
        elif intent.type == PlayerIntentType.ACTION:
            prompt_parts.extend(self._build_action_instructions(intent))
        elif intent.type == PlayerIntentType.MOVEMENT:
            prompt_parts.extend(self._build_movement_instructions(intent))
        
        # Response format
        prompt_parts.extend([
            "",
            "RESPONSE FORMAT:",
            "Start your response with a speaker tag: [DM] for narration or [NpcName] for dialogue.",
            "Use ONLY ONE speaker tag at the start.",
            f"Valid speakers: [DM], {', '.join(f'[{npc['name']}]' for npc in context['npcs_present'])}",
            "",
            "Keep responses concise (2-4 sentences for dialogue, 3-5 for narration).",
            "",
            f"Player says: \"{intent.cleaned_input}\""
        ])
        
        return "\n".join(prompt_parts)
    
    def _build_dialogue_instructions(self, intent: PlayerIntent, current_speaker: Optional[str]) -> List[str]:
        """Build instructions for dialogue responses."""
        instructions = ["INSTRUCTION: The player is speaking in character."]
        
        if current_speaker:
            npc = self.state_manager.npcs.get(current_speaker)
            if npc:
                instructions.append(f"Respond as {npc.name}.")
                
                # Add relevant knowledge if topic seems related
                for topic_id, knowledge in npc.knowledge.items():
                    if knowledge.knows and not knowledge.shared:
                        # Check if player might be asking about this
                        if any(word in intent.cleaned_input.lower() 
                               for word in topic_id.split('_')):
                            instructions.append(
                                f"The player might be asking about {topic_id}. "
                                f"{npc.name} knows: {knowledge.information[:100]}..."
                            )
        else:
            instructions.append("No active conversation. Have an NPC present approach or use [DM] narration.")
        
        return instructions
    
    def _build_action_instructions(self, intent: PlayerIntent) -> List[str]:
        """Build instructions for action responses."""
        node = self.state_manager.get_current_node()
        
        instructions = [
            "INSTRUCTION: The player is performing an action.",
            "Respond as [DM] describing the result of their action.",
        ]
        
        # Check for significant actions that might trigger
        for action_id, action in node.significant_actions.items():
            # Simple keyword matching to hint at significant actions
            trigger_words = action.trigger_description.lower().split()
            if any(word in intent.cleaned_input.lower() 
                   for word in trigger_words if len(word) > 3):
                instructions.append(
                    f"NOTE: This might trigger significant action '{action_id}': {action.trigger_description}"
                )
        
        return instructions
    
    def _build_movement_instructions(self, intent: PlayerIntent) -> List[str]:
        """Build instructions for movement responses."""
        instructions = [
            "INSTRUCTION: The player wants to move to a new location.",
            "Respond as [DM] describing their movement.",
        ]
        
        if intent.target:
            target_node = self.state_manager.nodes.get(intent.target)
            if target_node:
                instructions.append(f"They are heading to: {target_node.name}")
                instructions.append("Describe the transition briefly.")
        
        return instructions
    
    # =========================================================================
    # RESPONSE PARSING & VALIDATION  
    # =========================================================================
    
    def parse_response(self, raw_response: str, intent: PlayerIntent) -> DMResponse:
        """
        Parse and validate the AI response.
        """
        node = self.state_manager.get_current_node()
        
        # Extract speaker tag
        speaker_tag, narration = self._extract_speaker_tag(raw_response)
        
        # Validate speaker
        validated_speaker = self._validate_speaker(speaker_tag, node, intent)
        
        # Determine portrait
        portrait_type, portrait_source = self._determine_portrait(validated_speaker, node)
        
        # Check for state changes based on content
        state_changes = self._detect_state_changes(narration, intent, node)
        
        return DMResponse(
            narration=narration,
            speaker=validated_speaker,
            portrait_type=portrait_type,
            portrait_source=portrait_source,
            **state_changes
        )
    
    def _extract_speaker_tag(self, response: str) -> Tuple[str, str]:
        """Extract speaker tag from response."""
        response = response.strip()
        
        if response.startswith('['):
            tag_end = response.find(']')
            if tag_end > 0:
                tag = response[1:tag_end].strip()
                narration = response[tag_end + 1:].strip()
                
                # Clean up any extra tags that slipped through
                narration = re.sub(r'\[[^\]]+\]', '', narration).strip()
                
                return tag, narration
        
        # No tag found, default to DM
        return "DM", response
    
    def _validate_speaker(self, speaker_tag: str, node: Node, intent: PlayerIntent) -> str:
        """
        Validate and correct speaker tag against known NPCs.
        """
        tag_lower = speaker_tag.lower()
        
        # DM is always valid
        if tag_lower == 'dm':
            return 'dm'
        
        # Check if it matches an NPC present at this node
        for npc_presence in node.npcs_present:
            npc = self.state_manager.npcs.get(npc_presence.npc_id)
            if not npc:
                continue
                
            # Exact match on ID
            if tag_lower == npc_presence.npc_id.lower():
                return npc_presence.npc_id
            
            # Match on name
            if tag_lower == npc.name.lower():
                return npc_presence.npc_id
            
            # Partial match (e.g., "NPC_Ameiko" -> "ameiko")
            if npc_presence.npc_id.lower() in tag_lower or tag_lower in npc.name.lower():
                return npc_presence.npc_id
        
        # Invalid speaker - fall back to current speaker or DM
        current = self.state_manager.game_state.conversation.current_speaker
        if current and any(npc.npc_id == current for npc in node.npcs_present):
            logger.warning(f"Invalid speaker '{speaker_tag}', falling back to current: {current}")
            return current
        
        logger.warning(f"Invalid speaker '{speaker_tag}', falling back to DM")
        return 'dm'
    
    def _determine_portrait(self, speaker: str, node: Node) -> Tuple[str, str]:
        """
        Determine what portrait/image to show.
        
        Returns:
            (portrait_type, portrait_source)
            portrait_type: "dm", "npc", "scene"
            portrait_source: file path or generation prompt
        """
        if speaker == 'dm':
            # Check if this is a scene transition (first time entering)
            if node.node_id not in self.state_manager.game_state.nodes_visited:
                # Show scene image for new locations
                if node.description.image_prompt:
                    return ("scene", node.description.image_prompt.scene)
            
            # Otherwise show DM portrait
            return ("dm", "static/images/dm/dm_portrait.png")
        
        # NPC speaker - show their portrait
        npc = self.state_manager.npcs.get(speaker)
        if npc:
            if npc.appearance.portrait_url:
                return ("npc", npc.appearance.portrait_url)
            else:
                return ("npc", npc.appearance.portrait_prompt)
        
        # Fallback to DM
        return ("dm", "static/images/dm/dm_portrait.png")
    
    def _detect_state_changes(self, narration: str, intent: PlayerIntent, node: Node) -> Dict:
        """
        Detect state changes that should be applied based on the response.
        
        This is where significant actions get triggered.
        """
        changes = {
            'set_flags': [],
            'clear_flags': [],
            'relationship_changes': {},
            'xp_gained': 0,
            'items_gained': [],
            'items_lost': [],
            'move_to_node': None,
            'trigger_encounter': None
        }
        
        # Check if any significant action was triggered
        for action_id, action in node.significant_actions.items():
            if self._action_triggered(action, intent, narration):
                logger.info(f"Significant action triggered: {action_id}")
                
                # Apply action effects
                changes['set_flags'].extend(action.sets_flags)
                changes['clear_flags'].extend(action.clears_flags)
                changes['xp_gained'] += action.grants_xp
                changes['items_gained'].extend(action.grants_items)
                changes['items_lost'].extend(action.removes_items)
                
                # Relationship updates
                for npc_id, update in action.updates_relationships.items():
                    if npc_id not in changes['relationship_changes']:
                        changes['relationship_changes'][npc_id] = {'disposition': 0, 'trust': 0}
                    changes['relationship_changes'][npc_id]['disposition'] += update.get('disposition', 0)
                    changes['relationship_changes'][npc_id]['trust'] += update.get('trust', 0)
        
        # Check for movement
        if intent.type == PlayerIntentType.MOVEMENT and intent.target:
            changes['move_to_node'] = intent.target
        
        return changes
    
    def _action_triggered(self, action, intent: PlayerIntent, narration: str) -> bool:
        """
        Determine if a significant action was triggered.
        
        This is a heuristic - we check if the player input + AI response
        suggests the action occurred.
        """
        # Check requirements first
        for flag in action.requires_flags:
            if not self.state_manager.has_flag(flag):
                return False
        
        # Simple keyword matching against trigger description
        trigger_words = set(action.trigger_description.lower().split())
        input_words = set(intent.cleaned_input.lower().split())
        
        # If significant overlap, consider it triggered
        overlap = trigger_words & input_words
        meaningful_overlap = [w for w in overlap if len(w) > 3]
        
        return len(meaningful_overlap) >= 2
    
    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================
    
    def process_input(self, player_input: str) -> DMResponse:
        """
        Main entry point - process player input and return response.
        
        Args:
            player_input: What the player said/typed
            
        Returns:
            DMResponse with narration, speaker, portrait, and state changes
        """
        # Parse intent
        intent = self.parse_player_input(player_input)
        logger.info(f"Player intent: {intent.type.value}, target: {intent.target}, dm_addressed: {intent.is_dm_addressed}")
        
        # Handle system commands locally
        if intent.type == PlayerIntentType.SYSTEM:
            return self._handle_system_command(intent)
        
        # Build prompt
        prompt = self.build_prompt(intent)
        logger.debug(f"Prompt:\n{prompt}")
        
        # Call Ollama
        raw_response = self.call_ollama(prompt)
        logger.info(f"Raw response: {raw_response[:100]}...")
        
        # Parse and validate response
        response = self.parse_response(raw_response, intent)
        
        # Apply state changes
        self._apply_state_changes(response, intent)
        
        return response
    
    def _handle_system_command(self, intent: PlayerIntent) -> DMResponse:
        """Handle system commands without calling AI."""
        input_lower = intent.cleaned_input.lower()
        
        if 'inventory' in input_lower:
            items = self.state_manager.game_state.character.inventory
            item_list = ', '.join(f"{i.quantity}x {i.item_id}" for i in items) or "nothing"
            return DMResponse(
                narration=f"You are carrying: {item_list}",
                speaker="dm",
                portrait_type="dm",
                portrait_source="static/images/dm/dm_portrait.png"
            )
        
        # Add more system commands as needed
        
        return DMResponse(
            narration="I didn't understand that command.",
            speaker="dm", 
            portrait_type="dm",
            portrait_source="static/images/dm/dm_portrait.png"
        )
    
    def _apply_state_changes(self, response: DMResponse, intent: PlayerIntent):
        """Apply all state changes from the response."""
        
        # Update current speaker
        if response.speaker != 'dm':
            self.state_manager.set_current_speaker(response.speaker)
        elif intent.is_dm_addressed:
            self.state_manager.set_current_speaker(None)
        
        # Set/clear flags
        for flag in response.set_flags:
            self.state_manager.set_flag(flag)
        for flag in response.clear_flags:
            self.state_manager.set_flag(flag, False)
        
        # Relationship changes
        for npc_id, changes in response.relationship_changes.items():
            self.state_manager.modify_relationship(
                npc_id,
                disposition=changes.get('disposition', 0),
                trust=changes.get('trust', 0),
                event=f"action_{intent.type.value}"
            )
        
        # XP
        if response.xp_gained > 0:
            self.state_manager.game_state.character.experience += response.xp_gained
            logger.info(f"Gained {response.xp_gained} XP")
        
        # Movement
        if response.move_to_node:
            success, msg = self.state_manager.move_to_node(response.move_to_node)
            if success:
                logger.info(f"Moved to {response.move_to_node}")
            else:
                logger.warning(f"Failed to move: {msg}")
        
        # Add to conversation history
        self.state_manager.add_dialogue("player", intent.cleaned_input)
        self.state_manager.add_dialogue(response.speaker, response.narration)
        
        # Record action
        self.state_manager.game_state.record_action(
            f"{intent.type.value}_{intent.target or 'general'}",
            details={
                'input': intent.cleaned_input,
                'speaker': response.speaker,
                'flags_set': response.set_flags
            }
        )
