"""
Campaign Schema - Defines campaign structure, chapters, and nodes
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ImagePrompt:
    """Description for generating images"""
    scene: str
    style: str = "fantasy, detailed, dramatic lighting"
    negative: str = "modern, sci-fi, cartoon"


@dataclass
class NodeDescription:
    short: str  # One line summary
    long: str   # Full atmospheric description for narration
    image_prompt: Optional[ImagePrompt] = None


@dataclass
class NPCPresence:
    """An NPC present at this node"""
    npc_id: str
    role: str  # "quest_giver", "merchant", "information", "ambient"
    required: bool = False  # Must interact to progress?
    topics: List[str] = field(default_factory=list)  # What they can talk about
    initial_disposition_modifier: int = 0  # Adjust from NPC's base disposition


@dataclass
class ItemForSale:
    item_id: str
    cost: str  # "5 gp", "10 sp", etc.
    quantity: int = -1  # -1 means unlimited


@dataclass
class RelationshipUpdate:
    disposition: int = 0
    trust: int = 0


@dataclass
class SignificantAction:
    """An action that matters for story progression"""
    action_id: str
    trigger_description: str  # Human readable description of what triggers this
    
    # Conditions
    requires_flags: List[str] = field(default_factory=list)
    requires_items: List[str] = field(default_factory=list)
    requires_relationship: Optional[Dict[str, int]] = None  # {"npc_id": min_disposition}
    
    # Effects
    sets_flags: List[str] = field(default_factory=list)
    clears_flags: List[str] = field(default_factory=list)
    grants_items: List[str] = field(default_factory=list)
    removes_items: List[str] = field(default_factory=list)
    grants_quest: Optional[str] = None
    completes_objective: Optional[str] = None  # "quest_id.objective_id"
    updates_relationships: Dict[str, RelationshipUpdate] = field(default_factory=dict)
    grants_xp: int = 0
    
    # Narration
    success_prompt: Optional[str] = None  # Prompt for AI to narrate success
    failure_prompt: Optional[str] = None  # Prompt for AI to narrate failure


@dataclass
class SoftGate:
    """A warning before allowing exit, but doesn't prevent it"""
    condition: str  # Expression like "!has_supplies && !talked_to_marcus"
    warning_npc: Optional[str] = None  # NPC to deliver warning, or None for DM
    warning_prompt: str = ""  # What the warning should convey


@dataclass
class NodeExit:
    """An exit from this node to another"""
    target_node: str
    description: str
    direction: str = ""  # "north", "south", "interior", "upstairs", etc.
    
    # Conditions
    always_available: bool = True
    requires_flags: List[str] = field(default_factory=list)
    requires_items: List[str] = field(default_factory=list)
    blocked_message: str = ""  # Shown if requirements not met
    
    # Soft warnings (doesn't prevent, just warns)
    soft_gate: Optional[SoftGate] = None
    
    # Transition
    transition_prompt: Optional[str] = None  # Narration for this specific exit


@dataclass
class EncounterReference:
    """Reference to a combat encounter defined in encounters.json"""
    encounter_id: str
    trigger: str  # "on_enter", "on_exit", "manual", "random"
    chance: float = 1.0  # Probability if random (0.0 to 1.0)
    once_only: bool = True
    requires_flags: List[str] = field(default_factory=list)


@dataclass
class AmbientDetails:
    sounds: List[str] = field(default_factory=list)
    smells: List[str] = field(default_factory=list)
    mood: str = "neutral"


@dataclass
class OnEnterBehavior:
    narration_prompt: str
    auto_approach_npc: Optional[str] = None
    trigger_encounter: Optional[str] = None
    set_flags: List[str] = field(default_factory=list)


@dataclass
class Node:
    """
    A micro-location within a chapter.
    This is the primary context unit for AI interactions.
    """
    node_id: str
    name: str
    chapter_id: str
    
    description: NodeDescription
    
    # What's here
    npcs_present: List[NPCPresence] = field(default_factory=list)
    items_available: List[ItemForSale] = field(default_factory=list)
    items_findable: List[str] = field(default_factory=list)  # Items that can be found by searching
    
    # What can happen
    significant_actions: Dict[str, SignificantAction] = field(default_factory=dict)
    encounters: List[EncounterReference] = field(default_factory=list)
    
    # Where you can go
    exits: Dict[str, NodeExit] = field(default_factory=dict)
    
    # Atmosphere
    ambient: AmbientDetails = field(default_factory=AmbientDetails)
    
    # Entry behavior
    on_enter_first: Optional[OnEnterBehavior] = None
    on_enter_subsequent: Optional[OnEnterBehavior] = None
    
    def get_available_exits(self, flags: Dict[str, bool], inventory: List[str]) -> Dict[str, NodeExit]:
        """Get exits that are currently available based on game state"""
        available = {}
        for exit_id, exit_data in self.exits.items():
            if exit_data.always_available:
                available[exit_id] = exit_data
            else:
                # Check flag requirements
                has_flags = all(flags.get(f, False) for f in exit_data.requires_flags)
                has_items = all(i in inventory for i in exit_data.requires_items)
                if has_flags and has_items:
                    available[exit_id] = exit_data
        return available
    
    def get_present_npc_ids(self) -> List[str]:
        return [npc.npc_id for npc in self.npcs_present]


@dataclass
class ChapterCompletionConditions:
    required_flags: List[str] = field(default_factory=list)
    recommended_flags: List[str] = field(default_factory=list)
    required_quests_complete: List[str] = field(default_factory=list)


@dataclass
class Chapter:
    """A major story section containing multiple nodes"""
    chapter_id: str
    title: str
    summary: str
    chapter_number: int = 1
    
    nodes: List[str] = field(default_factory=list)  # List of node_ids
    starting_node: str = ""
    
    completion_conditions: ChapterCompletionConditions = field(default_factory=ChapterCompletionConditions)
    
    # Narration
    intro_narration: str = ""  # Read when chapter starts
    outro_narration: str = ""  # Read when chapter completes


@dataclass
class CampaignSetting:
    world: str = "generic_fantasy"
    region: str = ""
    starting_location: str = ""


@dataclass
class Campaign:
    """
    Top-level campaign definition
    """
    campaign_id: str
    title: str
    description: str
    author: str = "Unknown"
    version: str = "1.0"
    
    # Requirements
    recommended_level_min: int = 1
    recommended_level_max: int = 5
    estimated_duration: str = "3-4 sessions"
    
    # Setting
    setting: CampaignSetting = field(default_factory=CampaignSetting)
    
    # Structure
    chapters: List[Chapter] = field(default_factory=list)
    
    # External file references (relative to campaign directory)
    npcs_file: str = "npcs.json"
    encounters_file: str = "encounters.json"
    items_file: str = "items.json"
    nodes_file: str = "nodes.json"
    
    def get_starting_chapter(self) -> Optional[Chapter]:
        return self.chapters[0] if self.chapters else None
    
    def get_chapter(self, chapter_id: str) -> Optional[Chapter]:
        for chapter in self.chapters:
            if chapter.chapter_id == chapter_id:
                return chapter
        return None
