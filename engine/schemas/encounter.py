"""
Combat Encounter Schema - Defines combat encounters
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EnemyInstance:
    """An enemy in an encounter"""
    enemy_id: str
    monster_id: str  # Reference to foundation monsters.json
    name: str = ""  # Display name (can differ from monster name, e.g., "Goblin Scout")
    count: int = 1
    hp_modifier: int = 0  # Adjust HP from base
    custom_equipment: List[str] = field(default_factory=list)


@dataclass
class EncounterReward:
    xp: int = 0
    gold: str = ""  # "2d6 gp", "15 sp", etc.
    items: List[str] = field(default_factory=list)
    sets_flags: List[str] = field(default_factory=list)


@dataclass
class EncounterEnvironment:
    description: str = ""
    terrain: str = "normal"  # "difficult", "hazardous", "elevated"
    lighting: str = "normal"  # "dim", "dark", "bright"
    cover_available: bool = False
    special_features: List[str] = field(default_factory=list)  # ["pit trap", "collapsing ceiling"]


@dataclass
class Encounter:
    """A combat encounter definition"""
    encounter_id: str
    name: str
    description: str
    
    # Difficulty reference (based on party level)
    difficulty: str = "medium"  # "trivial", "easy", "medium", "hard", "deadly"
    
    # Enemies
    enemies: List[EnemyInstance] = field(default_factory=list)
    
    # Environment
    environment: EncounterEnvironment = field(default_factory=EncounterEnvironment)
    
    # Conditions
    surprise_player_dc: int = 0  # DC for player to avoid surprise (0 = no surprise check)
    surprise_enemy_dc: int = 0   # DC for enemies to avoid surprise
    
    # Narrative
    intro_narration: str = ""  # Read when combat starts
    victory_narration: str = ""
    defeat_narration: str = ""
    flee_narration: str = ""
    
    # Rewards
    rewards: EncounterReward = field(default_factory=EncounterReward)
    
    # Behavior hints for AI
    enemy_tactics: str = ""  # "aggressive", "defensive", "flee at half HP"
    morale_break: float = 0.25  # Enemies flee when this % HP remains (0 = fight to death)
    
    def get_total_xp(self) -> int:
        """Calculate total XP for the encounter"""
        # This would need access to monster data to calculate properly
        return self.rewards.xp


@dataclass
class EncounterRegistry:
    """Collection of all encounters in a campaign"""
    encounters: Dict[str, Encounter] = field(default_factory=dict)
    
    def get(self, encounter_id: str) -> Optional[Encounter]:
        return self.encounters.get(encounter_id)
    
    def add(self, encounter: Encounter):
        self.encounters[encounter.encounter_id] = encounter
