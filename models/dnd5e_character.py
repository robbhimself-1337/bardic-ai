"""
Enhanced D&D 5e Character Model
Supports full Open5e character creation with all official SRD content.
"""
from typing import Dict, List, Optional
import math


class DnD5eCharacter:
    """Full D&D 5e character with all SRD features."""

    def __init__(
        self,
        # Basic info
        name: str,
        level: int = 1,

        # Race & Class
        race: str = "Human",
        race_traits: Optional[Dict] = None,
        character_class: str = "Fighter",
        subclass: Optional[str] = None,

        # Ability Scores
        strength: int = 10,
        dexterity: int = 10,
        constitution: int = 10,
        intelligence: int = 10,
        wisdom: int = 10,
        charisma: int = 10,

        # HP
        hp: Optional[int] = None,
        max_hp: Optional[int] = None,

        # Skills & Proficiencies
        skill_proficiencies: Optional[List[str]] = None,
        saving_throw_proficiencies: Optional[List[str]] = None,
        tool_proficiencies: Optional[List[str]] = None,
        language_proficiencies: Optional[List[str]] = None,

        # Equipment
        inventory: Optional[List[str]] = None,
        equipped_armor: Optional[str] = None,
        equipped_weapons: Optional[List[str]] = None,

        # Spells (for spellcasters)
        cantrips: Optional[List[str]] = None,
        spells_known: Optional[List[str]] = None,
        spell_slots: Optional[Dict[int, int]] = None,
        spells_prepared: Optional[List[str]] = None,

        # Background
        background: Optional[str] = None,
        background_feature: Optional[str] = None,

        # Additional character data
        alignment: Optional[str] = None,
        personality_traits: Optional[str] = None,
        ideals: Optional[str] = None,
        bonds: Optional[str] = None,
        flaws: Optional[str] = None,

        # Features from race/class
        features: Optional[List[Dict]] = None
    ):
        # Basic info
        self.name = name
        self.level = level

        # Race & Class
        self.race = race
        self.race_traits = race_traits or {}
        self.character_class = character_class
        self.subclass = subclass

        # Ability Scores
        self.strength = strength
        self.dexterity = dexterity
        self.constitution = constitution
        self.intelligence = intelligence
        self.wisdom = wisdom
        self.charisma = charisma

        # Derived stats
        self.proficiency_bonus = self._calculate_proficiency_bonus()
        self.max_hp = max_hp or self._calculate_max_hp()
        self.hp = hp if hp is not None else self.max_hp
        self.ac = self._calculate_ac(equipped_armor)
        self.initiative = self.get_ability_modifier('dexterity')

        # Skills & Proficiencies
        self.skill_proficiencies = skill_proficiencies or []
        self.saving_throw_proficiencies = saving_throw_proficiencies or self._default_saving_throws()
        self.tool_proficiencies = tool_proficiencies or []
        self.language_proficiencies = language_proficiencies or ["Common"]

        # Equipment
        self.inventory = inventory or []
        self.equipped_armor = equipped_armor
        self.equipped_weapons = equipped_weapons or []

        # Spells
        self.cantrips = cantrips or []
        self.spells_known = spells_known or []
        self.spell_slots = spell_slots or {}
        self.spells_prepared = spells_prepared or []

        # Background
        self.background = background
        self.background_feature = background_feature

        # Character details
        self.alignment = alignment
        self.personality_traits = personality_traits
        self.ideals = ideals
        self.bonds = bonds
        self.flaws = flaws

        # Features
        self.features = features or []

    def _calculate_proficiency_bonus(self) -> int:
        """Calculate proficiency bonus based on level."""
        return math.ceil(self.level / 4) + 1

    def _calculate_max_hp(self) -> int:
        """Calculate max HP based on class hit die and CON modifier."""
        # Hit dice by class
        hit_dice = {
            "Barbarian": 12,
            "Fighter": 10,
            "Paladin": 10,
            "Ranger": 10,
            "Bard": 8,
            "Cleric": 8,
            "Druid": 8,
            "Monk": 8,
            "Rogue": 8,
            "Warlock": 8,
            "Sorcerer": 6,
            "Wizard": 6
        }

        hit_die = hit_dice.get(self.character_class, 8)
        con_mod = self.get_ability_modifier('constitution')

        # Level 1: max hit die + CON mod
        # Additional levels: average of hit die + CON mod
        if self.level == 1:
            return hit_die + con_mod
        else:
            avg_per_level = (hit_die // 2) + 1 + con_mod
            return hit_die + con_mod + (avg_per_level * (self.level - 1))

    def _calculate_ac(self, armor: Optional[str]) -> int:
        """Calculate AC based on equipped armor and DEX."""
        if not armor:
            # Unarmored: 10 + DEX modifier
            return 10 + self.get_ability_modifier('dexterity')

        # Simplified armor AC (would need full armor data from Open5e)
        armor_ac = {
            "Leather Armor": 11,
            "Studded Leather": 12,
            "Hide Armor": 12,
            "Chain Shirt": 13,
            "Scale Mail": 14,
            "Breastplate": 14,
            "Half Plate": 15,
            "Ring Mail": 14,
            "Chain Mail": 16,
            "Splint": 17,
            "Plate": 18
        }

        base_ac = armor_ac.get(armor, 10)

        # Light armor: full DEX bonus
        # Medium armor: max +2 DEX bonus
        # Heavy armor: no DEX bonus
        light_armor = ["Leather Armor", "Studded Leather"]
        medium_armor = ["Hide Armor", "Chain Shirt", "Scale Mail", "Breastplate", "Half Plate"]

        if armor in light_armor:
            return base_ac + self.get_ability_modifier('dexterity')
        elif armor in medium_armor:
            return base_ac + min(2, self.get_ability_modifier('dexterity'))
        else:
            return base_ac

    def _default_saving_throws(self) -> List[str]:
        """Get default saving throw proficiencies based on class."""
        saving_throws = {
            "Barbarian": ["strength", "constitution"],
            "Bard": ["dexterity", "charisma"],
            "Cleric": ["wisdom", "charisma"],
            "Druid": ["intelligence", "wisdom"],
            "Fighter": ["strength", "constitution"],
            "Monk": ["strength", "dexterity"],
            "Paladin": ["wisdom", "charisma"],
            "Ranger": ["strength", "dexterity"],
            "Rogue": ["dexterity", "intelligence"],
            "Sorcerer": ["constitution", "charisma"],
            "Warlock": ["wisdom", "charisma"],
            "Wizard": ["intelligence", "wisdom"]
        }
        return saving_throws.get(self.character_class, ["strength", "dexterity"])

    def get_ability_score(self, ability: str) -> int:
        """Get ability score by name."""
        ability_map = {
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma
        }
        return ability_map.get(ability.lower(), 10)

    def get_ability_modifier(self, ability: str) -> int:
        """Calculate ability modifier from ability score."""
        score = self.get_ability_score(ability)
        return (score - 10) // 2

    def get_skill_bonus(self, skill_name: str) -> int:
        """Calculate total bonus for a skill check."""
        # Map skills to abilities
        skill_abilities = {
            "Acrobatics": "dexterity",
            "Animal Handling": "wisdom",
            "Arcana": "intelligence",
            "Athletics": "strength",
            "Deception": "charisma",
            "History": "intelligence",
            "Insight": "wisdom",
            "Intimidation": "charisma",
            "Investigation": "intelligence",
            "Medicine": "wisdom",
            "Nature": "intelligence",
            "Perception": "wisdom",
            "Performance": "charisma",
            "Persuasion": "charisma",
            "Religion": "intelligence",
            "Sleight of Hand": "dexterity",
            "Stealth": "dexterity",
            "Survival": "wisdom"
        }

        ability = skill_abilities.get(skill_name, "strength")
        modifier = self.get_ability_modifier(ability)

        # Add proficiency if proficient
        if skill_name in self.skill_proficiencies:
            modifier += self.proficiency_bonus

        return modifier

    def get_saving_throw_bonus(self, ability: str) -> int:
        """Calculate saving throw bonus for an ability."""
        modifier = self.get_ability_modifier(ability)

        if ability.lower() in self.saving_throw_proficiencies:
            modifier += self.proficiency_bonus

        return modifier

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
        """Remove item from inventory."""
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False

    def has_item(self, item: str) -> bool:
        """Check if character has an item."""
        return item in self.inventory

    def learn_spell(self, spell: str):
        """Add spell to known spells."""
        if spell not in self.spells_known:
            self.spells_known.append(spell)

    def prepare_spell(self, spell: str):
        """Add spell to prepared spells."""
        if spell in self.spells_known and spell not in self.spells_prepared:
            self.spells_prepared.append(spell)

    def to_dict(self) -> Dict:
        """Convert character to dictionary for serialization."""
        return {
            "name": self.name,
            "level": self.level,
            "race": self.race,
            "race_traits": self.race_traits,
            "character_class": self.character_class,
            "subclass": self.subclass,
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "ac": self.ac,
            "initiative": self.initiative,
            "proficiency_bonus": self.proficiency_bonus,
            "skill_proficiencies": self.skill_proficiencies,
            "saving_throw_proficiencies": self.saving_throw_proficiencies,
            "tool_proficiencies": self.tool_proficiencies,
            "language_proficiencies": self.language_proficiencies,
            "inventory": self.inventory,
            "equipped_armor": self.equipped_armor,
            "equipped_weapons": self.equipped_weapons,
            "cantrips": self.cantrips,
            "spells_known": self.spells_known,
            "spell_slots": self.spell_slots,
            "spells_prepared": self.spells_prepared,
            "background": self.background,
            "background_feature": self.background_feature,
            "alignment": self.alignment,
            "personality_traits": self.personality_traits,
            "ideals": self.ideals,
            "bonds": self.bonds,
            "flaws": self.flaws,
            "features": self.features
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DnD5eCharacter':
        """Create character from dictionary."""
        return cls(
            name=data.get("name", "Unnamed"),
            level=data.get("level", 1),
            race=data.get("race", "Human"),
            race_traits=data.get("race_traits"),
            character_class=data.get("character_class", "Fighter"),
            subclass=data.get("subclass"),
            strength=data.get("strength", 10),
            dexterity=data.get("dexterity", 10),
            constitution=data.get("constitution", 10),
            intelligence=data.get("intelligence", 10),
            wisdom=data.get("wisdom", 10),
            charisma=data.get("charisma", 10),
            hp=data.get("hp"),
            max_hp=data.get("max_hp"),
            skill_proficiencies=data.get("skill_proficiencies"),
            saving_throw_proficiencies=data.get("saving_throw_proficiencies"),
            tool_proficiencies=data.get("tool_proficiencies"),
            language_proficiencies=data.get("language_proficiencies"),
            inventory=data.get("inventory"),
            equipped_armor=data.get("equipped_armor"),
            equipped_weapons=data.get("equipped_weapons"),
            cantrips=data.get("cantrips"),
            spells_known=data.get("spells_known"),
            spell_slots=data.get("spell_slots"),
            spells_prepared=data.get("spells_prepared"),
            background=data.get("background"),
            background_feature=data.get("background_feature"),
            alignment=data.get("alignment"),
            personality_traits=data.get("personality_traits"),
            ideals=data.get("ideals"),
            bonds=data.get("bonds"),
            flaws=data.get("flaws"),
            features=data.get("features")
        )
