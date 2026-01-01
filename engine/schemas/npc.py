"""
NPC Schema - Defines NPCs with personality, knowledge, and relationship mechanics
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class NPCAppearance:
    short: str  # One line description
    detailed: str = ""  # Full description if needed
    portrait_prompt: str = ""  # For image generation
    portrait_url: Optional[str] = None  # Cached generated portrait


@dataclass
class NPCPersonality:
    traits: List[str] = field(default_factory=list)  # ["caring", "gruff", "suspicious"]
    ideals: List[str] = field(default_factory=list)  # What they believe in
    bonds: List[str] = field(default_factory=list)   # What they're connected to
    flaws: List[str] = field(default_factory=list)   # Weaknesses/quirks


@dataclass
class NPCVoice:
    style: str = "neutral"  # "warm", "gruff", "formal", "nervous"
    speech_patterns: List[str] = field(default_factory=list)  # ["direct", "uses metaphors", "stutters"]
    catchphrases: List[str] = field(default_factory=list)
    voice_sample_file: Optional[str] = None  # Path to voice sample for TTS


@dataclass
class KnowledgeTopic:
    """Something the NPC knows about"""
    topic_id: str
    knows: bool = True
    information: str = ""  # What they know
    share_condition: str = "always"  # "always", "if_asked", "requires_trust", "requires_flag:flag_name"
    trust_threshold: int = 0  # Minimum trust to share
    shared: bool = False  # Has this been shared with player?


@dataclass
class DialogueLines:
    """Pre-written dialogue for common situations"""
    greeting_first: str = "Hello there."
    greeting_friendly: str = "Good to see you again!"
    greeting_unfriendly: str = "What do you want?"
    greeting_hostile: str = "You have some nerve showing your face here."
    
    farewell_friendly: str = "Safe travels!"
    farewell_neutral: str = "Goodbye."
    farewell_unfriendly: str = "Just go."
    
    # These can be extended per-NPC
    custom: Dict[str, str] = field(default_factory=dict)


@dataclass
class RelationshipThreshold:
    min_value: int
    max_value: int
    behavior_description: str


@dataclass
class NPCRelationshipConfig:
    """How this NPC responds to different relationship levels"""
    hostile: RelationshipThreshold = field(default_factory=lambda: RelationshipThreshold(
        min_value=-100, max_value=-50,
        behavior_description="Refuses to help, may be aggressive, wants player gone"
    ))
    unfriendly: RelationshipThreshold = field(default_factory=lambda: RelationshipThreshold(
        min_value=-50, max_value=-20,
        behavior_description="Curt responses, minimal information, clearly dislikes player"
    ))
    neutral: RelationshipThreshold = field(default_factory=lambda: RelationshipThreshold(
        min_value=-20, max_value=20,
        behavior_description="Polite but distant, shares basic information"
    ))
    friendly: RelationshipThreshold = field(default_factory=lambda: RelationshipThreshold(
        min_value=20, max_value=60,
        behavior_description="Warm, helpful, shares extra details"
    ))
    devoted: RelationshipThreshold = field(default_factory=lambda: RelationshipThreshold(
        min_value=60, max_value=100,
        behavior_description="Goes out of way to help, may offer gifts or discounts"
    ))
    
    def get_behavior(self, disposition: int) -> str:
        """Get behavior description for a given disposition value"""
        if disposition <= self.hostile.max_value:
            return self.hostile.behavior_description
        elif disposition <= self.unfriendly.max_value:
            return self.unfriendly.behavior_description
        elif disposition <= self.neutral.max_value:
            return self.neutral.behavior_description
        elif disposition <= self.friendly.max_value:
            return self.friendly.behavior_description
        else:
            return self.devoted.behavior_description


@dataclass
class TradeConfig:
    can_trade: bool = False
    inventory: List[str] = field(default_factory=list)  # item_ids they sell
    buys_items: bool = False  # Will they buy from player?
    price_modifier: float = 1.0  # Base price multiplier
    
    # Relationship affects prices
    friendly_discount: float = 0.1  # 10% off when friendly
    hostile_markup: float = 0.5  # 50% more when hostile


@dataclass
class NPC:
    """
    Complete NPC definition
    """
    npc_id: str
    name: str
    race: str = "human"
    gender: str = "unknown"
    age: str = "adult"  # "child", "young", "adult", "middle-aged", "elderly"
    
    # Visual
    appearance: NPCAppearance = field(default_factory=lambda: NPCAppearance(short="A person"))
    
    # Personality
    personality: NPCPersonality = field(default_factory=NPCPersonality)
    voice: NPCVoice = field(default_factory=NPCVoice)
    
    # Role
    role: str = "commoner"  # "innkeeper", "guard", "merchant", "quest_giver", etc.
    occupation: str = ""
    faction: Optional[str] = None
    
    # What they know
    knowledge: Dict[str, KnowledgeTopic] = field(default_factory=dict)
    
    # Dialogue
    dialogue: DialogueLines = field(default_factory=DialogueLines)
    
    # Relationship
    base_disposition: int = 50  # Starting disposition toward strangers
    relationship_config: NPCRelationshipConfig = field(default_factory=NPCRelationshipConfig)
    
    # Trading
    trade: TradeConfig = field(default_factory=TradeConfig)
    
    # Combat (if applicable)
    can_fight: bool = False
    monster_stat_block: Optional[str] = None  # Reference to monster in foundation
    is_essential: bool = False  # Cannot be killed if True
    
    def get_greeting(self, disposition: int) -> str:
        """Get appropriate greeting based on disposition"""
        if disposition < -50:
            return self.dialogue.greeting_hostile
        elif disposition < -20:
            return self.dialogue.greeting_unfriendly
        elif disposition < 40:
            return self.dialogue.greeting_first  # Neutral uses first meeting
        else:
            return self.dialogue.greeting_friendly
    
    def get_farewell(self, disposition: int) -> str:
        """Get appropriate farewell based on disposition"""
        if disposition < -20:
            return self.dialogue.farewell_unfriendly
        elif disposition < 40:
            return self.dialogue.farewell_neutral
        else:
            return self.dialogue.farewell_friendly
    
    def can_share_topic(self, topic_id: str, trust: int, flags: Dict[str, bool]) -> bool:
        """Check if NPC will share information on a topic"""
        if topic_id not in self.knowledge:
            return False
        
        topic = self.knowledge[topic_id]
        if not topic.knows:
            return False
        
        condition = topic.share_condition
        
        if condition == "always":
            return True
        elif condition == "if_asked":
            return True
        elif condition == "requires_trust":
            return trust >= topic.trust_threshold
        elif condition.startswith("requires_flag:"):
            flag_name = condition.split(":", 1)[1]
            return flags.get(flag_name, False)
        
        return False
    
    def get_topic_info(self, topic_id: str) -> Optional[str]:
        """Get the information for a topic"""
        if topic_id in self.knowledge:
            return self.knowledge[topic_id].information
        return None
    
    def get_trade_price_modifier(self, disposition: int) -> float:
        """Get price modifier based on relationship"""
        if not self.trade.can_trade:
            return 1.0
        
        base = self.trade.price_modifier
        
        if disposition >= 60:
            return base * (1 - self.trade.friendly_discount)
        elif disposition <= -50:
            return base * (1 + self.trade.hostile_markup)
        
        return base


@dataclass
class NPCRegistry:
    """Collection of all NPCs in a campaign"""
    npcs: Dict[str, NPC] = field(default_factory=dict)
    
    def get(self, npc_id: str) -> Optional[NPC]:
        return self.npcs.get(npc_id)
    
    def add(self, npc: NPC):
        self.npcs[npc.npc_id] = npc
    
    def get_by_role(self, role: str) -> List[NPC]:
        return [npc for npc in self.npcs.values() if npc.role == role]
