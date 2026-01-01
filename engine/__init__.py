"""
Bardic AI Engine

New architecture for D&D game management with robust state tracking,
node-based navigation, and AI-assisted narration.
"""

from .schemas import *
from .loaders import (
    load_campaign,
    load_nodes,
    load_npcs,
    load_encounters,
    load_full_campaign,
)
from .state_manager import StateManager
from .rules_engine import (
    RulesEngine,
    DiceRoller,
    DiceResult,
    CheckEngine,
    CheckResult,
    CombatEngine,
    CombatPhase,
    Combatant,
    AttackResult,
    SKILL_ABILITY_MAP,
)
from .dm_engine_v2 import (
    NewDMEngine,
    DMResponse,
    PlayerIntent,
    PlayerIntentType,
)

__version__ = "2.0.0"

__all__ = [
    # Loaders
    "load_campaign",
    "load_nodes", 
    "load_npcs",
    "load_encounters",
    "load_full_campaign",
    
    # State Management
    "StateManager",
    
    # Rules Engine
    "RulesEngine",
    "DiceRoller",
    "DiceResult",
    "CheckEngine",
    "CheckResult",
    "CombatEngine",
    "CombatPhase",
    "Combatant",
    "AttackResult",
    "SKILL_ABILITY_MAP",
    
    # DM Engine
    "NewDMEngine",
    "DMResponse",
    "PlayerIntent",
    "PlayerIntentType",
]
