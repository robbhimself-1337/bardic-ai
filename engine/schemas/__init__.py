"""
Bardic AI Engine Schemas

These dataclasses define the structure of all game data.
"""

from .game_state import (
    GameState,
    GameMode,
    Character,
    AbilityScores,
    HitPoints,
    Currency,
    InventoryItem,
    Proficiencies,
    Location,
    Quest,
    QuestObjective,
    StoryProgress,
    NPCRelationship,
    RelationshipEvent,
    ConversationState,
    DialogueExchange,
    CombatState,
    CombatantState,
    WorldState,
    TimeOfDay,
    ActionRecord,
)

from .campaign import (
    Campaign,
    Chapter,
    Node,
    NodeDescription,
    NPCPresence,
    ItemForSale,
    SignificantAction,
    NodeExit,
    SoftGate,
    EncounterReference,
    AmbientDetails,
    OnEnterBehavior,
    ChapterCompletionConditions,
    CampaignSetting,
    ImagePrompt,
    RelationshipUpdate,
)

from .npc import (
    NPC,
    NPCAppearance,
    NPCPersonality,
    NPCVoice,
    KnowledgeTopic,
    DialogueLines,
    NPCRelationshipConfig,
    RelationshipThreshold,
    TradeConfig,
    NPCRegistry,
)

from .encounter import (
    Encounter,
    EnemyInstance,
    EncounterReward,
    EncounterEnvironment,
    EncounterRegistry,
)

__all__ = [
    # Game State
    "GameState",
    "GameMode", 
    "Character",
    "AbilityScores",
    "HitPoints",
    "Currency",
    "InventoryItem",
    "Proficiencies",
    "Location",
    "Quest",
    "QuestObjective",
    "StoryProgress",
    "NPCRelationship",
    "RelationshipEvent",
    "ConversationState",
    "DialogueExchange",
    "CombatState",
    "CombatantState",
    "WorldState",
    "TimeOfDay",
    "ActionRecord",
    
    # Campaign
    "Campaign",
    "Chapter",
    "Node",
    "NodeDescription",
    "NPCPresence",
    "ItemForSale",
    "SignificantAction",
    "NodeExit",
    "SoftGate",
    "EncounterReference",
    "AmbientDetails",
    "OnEnterBehavior",
    "ChapterCompletionConditions",
    "CampaignSetting",
    "ImagePrompt",
    "RelationshipUpdate",
    
    # NPC
    "NPC",
    "NPCAppearance",
    "NPCPersonality",
    "NPCVoice",
    "KnowledgeTopic",
    "DialogueLines",
    "NPCRelationshipConfig",
    "RelationshipThreshold",
    "TradeConfig",
    "NPCRegistry",
    
    # Encounter
    "Encounter",
    "EnemyInstance",
    "EncounterReward",
    "EncounterEnvironment",
    "EncounterRegistry",
]
