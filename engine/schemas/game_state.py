"""
Game State Schema - Tracks everything about the current game session
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class GameMode(Enum):
    DIALOGUE = "dialogue"
    DM_NARRATION = "dm_narration"
    COMBAT = "combat"
    EXPLORATION = "exploration"


class TimeOfDay(Enum):
    DAWN = "dawn"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


@dataclass
class AbilityScores:
    str: int = 10
    dex: int = 10
    con: int = 10
    int: int = 10
    wis: int = 10
    cha: int = 10
    
    def get_modifier(self, ability: str) -> int:
        """Calculate ability modifier: (score - 10) // 2"""
        score = getattr(self, ability.lower())
        return (score - 10) // 2


@dataclass
class HitPoints:
    current: int
    max: int
    temp: int = 0


@dataclass 
class Currency:
    cp: int = 0  # Copper
    sp: int = 0  # Silver
    gp: int = 0  # Gold
    pp: int = 0  # Platinum
    
    def total_in_gold(self) -> float:
        """Convert all currency to gold equivalent"""
        return self.cp / 100 + self.sp / 10 + self.gp + self.pp * 10


@dataclass
class InventoryItem:
    item_id: str
    quantity: int = 1
    equipped: bool = False
    custom_name: Optional[str] = None  # For renamed/personalized items


@dataclass
class Proficiencies:
    skills: List[str] = field(default_factory=list)
    armor: List[str] = field(default_factory=list)
    weapons: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    saving_throws: List[str] = field(default_factory=list)


@dataclass
class Character:
    name: str
    race: str
    char_class: str
    level: int = 1
    experience: int = 0
    
    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    hp: HitPoints = field(default_factory=lambda: HitPoints(current=10, max=10))
    armor_class: int = 10
    speed: int = 30
    proficiency_bonus: int = 2
    
    proficiencies: Proficiencies = field(default_factory=Proficiencies)
    inventory: List[InventoryItem] = field(default_factory=list)
    gold: Currency = field(default_factory=Currency)
    
    class_features: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)  # "poisoned", "exhaustion_1", etc.
    
    def get_skill_modifier(self, skill: str, skill_ability_map: Dict[str, str]) -> int:
        """Calculate skill modifier including proficiency if applicable"""
        ability = skill_ability_map.get(skill, "int")
        mod = self.ability_scores.get_modifier(ability)
        if skill in self.proficiencies.skills:
            mod += self.proficiency_bonus
        return mod


@dataclass
class Location:
    chapter_id: str
    node_id: str
    previous_node: Optional[str] = None
    entered_at: datetime = field(default_factory=datetime.now)


@dataclass
class QuestObjective:
    id: str
    description: str
    completed: bool = False
    completed_at: Optional[datetime] = None


@dataclass
class Quest:
    quest_id: str
    name: str
    description: str
    status: str = "active"  # "active", "completed", "failed", "abandoned"
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    objectives: List[QuestObjective] = field(default_factory=list)


@dataclass
class StoryProgress:
    flags: Dict[str, bool] = field(default_factory=dict)
    quests: List[Quest] = field(default_factory=list)
    
    def set_flag(self, flag: str, value: bool = True):
        self.flags[flag] = value
    
    def has_flag(self, flag: str) -> bool:
        return self.flags.get(flag, False)
    
    def get_active_quests(self) -> List[Quest]:
        return [q for q in self.quests if q.status == "active"]


@dataclass
class RelationshipEvent:
    event: str
    change: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NPCRelationship:
    npc_id: str
    disposition: int = 50  # -100 to 100, starts neutral
    trust: int = 50
    met: bool = False
    history: List[RelationshipEvent] = field(default_factory=list)
    
    def modify_disposition(self, amount: int, event: str):
        """Change disposition and record the event"""
        self.disposition = max(-100, min(100, self.disposition + amount))
        self.history.append(RelationshipEvent(event=event, change=amount))
    
    def get_attitude(self) -> str:
        """Get general attitude based on disposition"""
        if self.disposition < -50:
            return "hostile"
        elif self.disposition < -20:
            return "unfriendly"
        elif self.disposition < 20:
            return "neutral"
        elif self.disposition < 50:
            return "friendly"
        else:
            return "devoted"


@dataclass
class DialogueExchange:
    speaker: str  # "player", npc_id, or "dm"
    text: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationState:
    current_speaker: Optional[str] = None
    mode: GameMode = GameMode.EXPLORATION
    recent_exchanges: List[DialogueExchange] = field(default_factory=list)
    
    def add_exchange(self, speaker: str, text: str):
        self.recent_exchanges.append(DialogueExchange(speaker=speaker, text=text))
        # Keep only last 10 exchanges for context
        if len(self.recent_exchanges) > 10:
            self.recent_exchanges = self.recent_exchanges[-10:]


@dataclass
class CombatantState:
    id: str
    name: str
    hp_current: int
    hp_max: int
    armor_class: int
    initiative: int = 0
    is_player: bool = False
    conditions: List[str] = field(default_factory=list)
    defeated: bool = False


@dataclass
class CombatState:
    active: bool = False
    round: int = 0
    turn_order: List[str] = field(default_factory=list)  # List of combatant IDs
    current_turn_index: int = 0
    combatants: Dict[str, CombatantState] = field(default_factory=dict)
    environment: Optional[str] = None
    
    def get_current_combatant(self) -> Optional[CombatantState]:
        if not self.turn_order:
            return None
        current_id = self.turn_order[self.current_turn_index]
        return self.combatants.get(current_id)
    
    def next_turn(self):
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        if self.current_turn_index == 0:
            self.round += 1


@dataclass
class WorldState:
    time_of_day: TimeOfDay = TimeOfDay.MORNING
    weather: str = "clear"
    days_elapsed: int = 0
    global_events: List[str] = field(default_factory=list)


@dataclass
class ActionRecord:
    action: str
    details: Optional[Dict] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GameState:
    """
    Master game state - contains everything about the current session
    """
    # Session info
    session_id: str
    campaign_id: str
    started_at: datetime = field(default_factory=datetime.now)
    last_saved: datetime = field(default_factory=datetime.now)
    
    # Core state
    character: Character = field(default_factory=lambda: Character(name="Unknown", race="human", char_class="fighter"))
    location: Location = field(default_factory=lambda: Location(chapter_id="", node_id=""))
    story_progress: StoryProgress = field(default_factory=StoryProgress)
    relationships: Dict[str, NPCRelationship] = field(default_factory=dict)
    
    # Current context
    conversation: ConversationState = field(default_factory=ConversationState)
    combat: CombatState = field(default_factory=CombatState)
    world: WorldState = field(default_factory=WorldState)
    
    # History
    action_history: List[ActionRecord] = field(default_factory=list)
    nodes_visited: List[str] = field(default_factory=list)
    
    def record_action(self, action: str, details: Optional[Dict] = None):
        """Record an action in history"""
        self.action_history.append(ActionRecord(action=action, details=details))
        self.last_saved = datetime.now()
    
    def get_relationship(self, npc_id: str) -> NPCRelationship:
        """Get or create relationship with an NPC"""
        if npc_id not in self.relationships:
            self.relationships[npc_id] = NPCRelationship(npc_id=npc_id)
        return self.relationships[npc_id]
    
    def move_to_node(self, node_id: str):
        """Move to a new node"""
        self.location.previous_node = self.location.node_id
        self.location.node_id = node_id
        self.location.entered_at = datetime.now()
        if node_id not in self.nodes_visited:
            self.nodes_visited.append(node_id)
        self.record_action(f"moved_to_{node_id}")
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary for JSON storage"""
        # TODO: Implement full serialization
        pass
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GameState':
        """Deserialize from dictionary"""
        # TODO: Implement full deserialization
        pass
