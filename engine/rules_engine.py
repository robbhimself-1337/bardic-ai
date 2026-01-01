"""
D&D 5e Rules Engine - Handles dice rolls, skill checks, combat, and game mechanics.

Uses foundation data from data/foundation/ for monster stats, weapons, etc.
"""

import random
import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# DICE ROLLING
# =============================================================================

@dataclass
class DiceResult:
    """Result of a dice roll"""
    total: int
    rolls: List[int]
    modifier: int
    dice_expr: str
    natural_20: bool = False
    natural_1: bool = False
    
    def __str__(self):
        if self.modifier:
            sign = '+' if self.modifier > 0 else ''
            return f"{self.dice_expr} = {self.rolls} {sign}{self.modifier} = {self.total}"
        return f"{self.dice_expr} = {self.rolls} = {self.total}"


class DiceRoller:
    """Handles all dice rolling operations"""
    
    # Pattern for dice expressions: 2d6+3, 1d20-1, d8, etc.
    DICE_PATTERN = re.compile(r'(\d*)d(\d+)([+-]\d+)?')
    
    @staticmethod
    def roll(expression: str) -> DiceResult:
        """
        Roll dice based on expression.
        
        Args:
            expression: Dice expression like "2d6+3", "1d20", "d8-1"
            
        Returns:
            DiceResult with total, individual rolls, and metadata
        """
        expression = expression.lower().replace(' ', '')
        
        match = DiceRoller.DICE_PATTERN.match(expression)
        if not match:
            raise ValueError(f"Invalid dice expression: {expression}")
        
        num_dice = int(match.group(1)) if match.group(1) else 1
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        total = sum(rolls) + modifier
        
        # Check for natural 20/1 on d20 rolls
        natural_20 = die_size == 20 and num_dice == 1 and rolls[0] == 20
        natural_1 = die_size == 20 and num_dice == 1 and rolls[0] == 1
        
        return DiceResult(
            total=total,
            rolls=rolls,
            modifier=modifier,
            dice_expr=expression,
            natural_20=natural_20,
            natural_1=natural_1
        )
    
    @staticmethod
    def roll_with_advantage(expression: str = "1d20") -> Tuple[DiceResult, DiceResult, DiceResult]:
        """
        Roll with advantage (roll twice, take higher).
        
        Returns:
            (final_result, roll1, roll2)
        """
        roll1 = DiceRoller.roll(expression)
        roll2 = DiceRoller.roll(expression)
        final = roll1 if roll1.total >= roll2.total else roll2
        return final, roll1, roll2
    
    @staticmethod
    def roll_with_disadvantage(expression: str = "1d20") -> Tuple[DiceResult, DiceResult, DiceResult]:
        """
        Roll with disadvantage (roll twice, take lower).
        
        Returns:
            (final_result, roll1, roll2)
        """
        roll1 = DiceRoller.roll(expression)
        roll2 = DiceRoller.roll(expression)
        final = roll1 if roll1.total <= roll2.total else roll2
        return final, roll1, roll2


# =============================================================================
# SKILL & ABILITY CHECKS
# =============================================================================

# Mapping of skills to their governing ability
SKILL_ABILITY_MAP = {
    'acrobatics': 'dex',
    'animal-handling': 'wis',
    'arcana': 'int',
    'athletics': 'str',
    'deception': 'cha',
    'history': 'int',
    'insight': 'wis',
    'intimidation': 'cha',
    'investigation': 'int',
    'medicine': 'wis',
    'nature': 'int',
    'perception': 'wis',
    'performance': 'cha',
    'persuasion': 'cha',
    'religion': 'int',
    'sleight-of-hand': 'dex',
    'stealth': 'dex',
    'survival': 'wis'
}


@dataclass
class CheckResult:
    """Result of a skill check, ability check, or saving throw"""
    success: bool
    total: int
    dc: int
    roll: DiceResult
    modifier: int
    check_type: str  # "skill", "ability", "save"
    check_name: str  # "perception", "str", etc.
    critical_success: bool = False
    critical_failure: bool = False
    margin: int = 0  # How much over/under the DC
    
    def __str__(self):
        result = "SUCCESS" if self.success else "FAILURE"
        if self.critical_success:
            result = "CRITICAL SUCCESS"
        elif self.critical_failure:
            result = "CRITICAL FAILURE"
        return f"{self.check_name.title()} Check: {self.roll.rolls[0]} + {self.modifier} = {self.total} vs DC {self.dc} - {result}"


class CheckEngine:
    """Handles skill checks, ability checks, and saving throws"""
    
    def __init__(self, character):
        """
        Initialize with a character.
        
        Args:
            character: Character dataclass with ability_scores, proficiencies, etc.
        """
        self.character = character
    
    def get_ability_modifier(self, ability: str) -> int:
        """Get modifier for an ability score."""
        score = getattr(self.character.ability_scores, ability.lower(), 10)
        return (score - 10) // 2
    
    def get_skill_modifier(self, skill: str) -> int:
        """Get total modifier for a skill (ability mod + proficiency if applicable)."""
        # Normalize skill name
        skill_normalized = skill.lower().replace(' ', '-').replace('_', '-')
        
        # Get governing ability
        ability = SKILL_ABILITY_MAP.get(skill_normalized, 'int')
        modifier = self.get_ability_modifier(ability)
        
        # Add proficiency bonus if proficient
        if skill_normalized in [s.lower().replace('_', '-') for s in self.character.proficiencies.skills]:
            modifier += self.character.proficiency_bonus
        
        return modifier
    
    def ability_check(self, ability: str, dc: int, advantage: bool = False, 
                      disadvantage: bool = False) -> CheckResult:
        """
        Make an ability check.
        
        Args:
            ability: Ability name (str, dex, con, int, wis, cha)
            dc: Difficulty Class
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage
        """
        modifier = self.get_ability_modifier(ability)
        
        if advantage and not disadvantage:
            roll, _, _ = DiceRoller.roll_with_advantage()
        elif disadvantage and not advantage:
            roll, _, _ = DiceRoller.roll_with_disadvantage()
        else:
            roll = DiceRoller.roll("1d20")
        
        total = roll.total + modifier
        success = total >= dc
        
        return CheckResult(
            success=success,
            total=total,
            dc=dc,
            roll=roll,
            modifier=modifier,
            check_type="ability",
            check_name=ability,
            critical_success=roll.natural_20,
            critical_failure=roll.natural_1,
            margin=total - dc
        )
    
    def skill_check(self, skill: str, dc: int, advantage: bool = False,
                    disadvantage: bool = False) -> CheckResult:
        """
        Make a skill check.
        
        Args:
            skill: Skill name (perception, stealth, etc.)
            dc: Difficulty Class
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage
        """
        modifier = self.get_skill_modifier(skill)
        
        if advantage and not disadvantage:
            roll, _, _ = DiceRoller.roll_with_advantage()
        elif disadvantage and not advantage:
            roll, _, _ = DiceRoller.roll_with_disadvantage()
        else:
            roll = DiceRoller.roll("1d20")
        
        total = roll.total + modifier
        success = total >= dc
        
        return CheckResult(
            success=success,
            total=total,
            dc=dc,
            roll=roll,
            modifier=modifier,
            check_type="skill",
            check_name=skill,
            critical_success=roll.natural_20,
            critical_failure=roll.natural_1,
            margin=total - dc
        )
    
    def saving_throw(self, ability: str, dc: int, advantage: bool = False,
                     disadvantage: bool = False) -> CheckResult:
        """
        Make a saving throw.
        
        Args:
            ability: Ability to save with (str, dex, con, int, wis, cha)
            dc: Difficulty Class
        """
        modifier = self.get_ability_modifier(ability)
        
        # Add proficiency if proficient in this save
        # Check multiple formats: "str", "con", "saving-throw-str", etc.
        ability_lower = ability.lower()
        save_profs_normalized = [s.lower().replace('_', '-').replace('saving-throw-', '') 
                                  for s in self.character.proficiencies.saving_throws]
        if ability_lower in save_profs_normalized:
            modifier += self.character.proficiency_bonus
        
        if advantage and not disadvantage:
            roll, _, _ = DiceRoller.roll_with_advantage()
        elif disadvantage and not advantage:
            roll, _, _ = DiceRoller.roll_with_disadvantage()
        else:
            roll = DiceRoller.roll("1d20")
        
        total = roll.total + modifier
        success = total >= dc
        
        return CheckResult(
            success=success,
            total=total,
            dc=dc,
            roll=roll,
            modifier=modifier,
            check_type="save",
            check_name=ability,
            critical_success=roll.natural_20,
            critical_failure=roll.natural_1,
            margin=total - dc
        )


# =============================================================================
# COMBAT ENGINE
# =============================================================================

class CombatPhase(Enum):
    NOT_IN_COMBAT = "not_in_combat"
    ROLLING_INITIATIVE = "rolling_initiative"
    COMBAT_ACTIVE = "combat_active"
    COMBAT_ENDED = "combat_ended"


@dataclass
class Combatant:
    """A participant in combat"""
    id: str
    name: str
    hp_current: int
    hp_max: int
    armor_class: int
    initiative: int = 0
    initiative_modifier: int = 0
    is_player: bool = False
    
    # Combat stats
    attacks: List[Dict] = field(default_factory=list)
    speed: int = 30
    
    # Status
    conditions: List[str] = field(default_factory=list)
    is_conscious: bool = True
    death_saves_success: int = 0
    death_saves_failure: int = 0
    
    @property
    def is_alive(self) -> bool:
        return self.hp_current > 0 or (self.is_player and self.death_saves_failure < 3)
    
    def take_damage(self, amount: int) -> Tuple[int, str]:
        """
        Take damage and return actual damage taken and status.
        
        Returns:
            (actual_damage, status_message)
        """
        actual = min(amount, self.hp_current)
        self.hp_current -= actual
        
        if self.hp_current <= 0:
            self.hp_current = 0
            self.is_conscious = False
            if self.is_player:
                return actual, f"{self.name} falls unconscious!"
            else:
                return actual, f"{self.name} is defeated!"
        
        return actual, f"{self.name} takes {actual} damage ({self.hp_current}/{self.hp_max} HP)"
    
    def heal(self, amount: int) -> Tuple[int, str]:
        """Heal and return actual amount healed."""
        actual = min(amount, self.hp_max - self.hp_current)
        self.hp_current += actual
        
        if not self.is_conscious and self.hp_current > 0:
            self.is_conscious = True
            self.death_saves_success = 0
            self.death_saves_failure = 0
            return actual, f"{self.name} regains consciousness! ({self.hp_current}/{self.hp_max} HP)"
        
        return actual, f"{self.name} heals {actual} HP ({self.hp_current}/{self.hp_max} HP)"


@dataclass
class AttackResult:
    """Result of an attack"""
    hit: bool
    critical: bool
    fumble: bool
    attack_roll: DiceResult
    attack_total: int
    target_ac: int
    damage: int = 0
    damage_roll: Optional[DiceResult] = None
    damage_type: str = ""
    attacker: str = ""
    target: str = ""
    
    def __str__(self):
        if self.fumble:
            return f"{self.attacker} fumbles their attack!"
        if not self.hit:
            return f"{self.attacker} misses {self.target} (rolled {self.attack_total} vs AC {self.target_ac})"
        
        crit_str = " CRITICAL HIT!" if self.critical else ""
        return f"{self.attacker} hits {self.target} for {self.damage} {self.damage_type} damage!{crit_str}"


class CombatEngine:
    """Manages combat encounters"""
    
    def __init__(self, foundation_path: str = "data/foundation"):
        """
        Initialize combat engine.
        
        Args:
            foundation_path: Path to foundation data (monsters, weapons, etc.)
        """
        self.foundation_path = Path(foundation_path)
        self.monsters_data = self._load_monsters()
        self.weapons_data = self._load_weapons()
        
        # Combat state
        self.phase = CombatPhase.NOT_IN_COMBAT
        self.combatants: Dict[str, Combatant] = {}
        self.turn_order: List[str] = []
        self.current_turn_index: int = 0
        self.round: int = 0
    
    def _load_monsters(self) -> Dict:
        """Load monster data from foundation."""
        try:
            with open(self.foundation_path / "entities" / "monsters.json") as f:
                monsters = json.load(f)
                return {m['index']: m for m in monsters}
        except Exception as e:
            logger.error(f"Failed to load monsters: {e}")
            return {}
    
    def _load_weapons(self) -> Dict:
        """Load weapon data from foundation."""
        try:
            with open(self.foundation_path / "items" / "weapons.json") as f:
                weapons = json.load(f)
                return {w['index']: w for w in weapons}
        except Exception as e:
            logger.error(f"Failed to load weapons: {e}")
            return {}
    
    def get_monster_stats(self, monster_id: str) -> Optional[Dict]:
        """Get monster stats from foundation data."""
        return self.monsters_data.get(monster_id)
    
    def create_monster_combatant(self, monster_id: str, name: Optional[str] = None,
                                  hp_modifier: int = 0) -> Optional[Combatant]:
        """
        Create a combatant from monster data.
        
        Args:
            monster_id: Monster index from foundation data
            name: Display name (defaults to monster name)
            hp_modifier: Adjust HP from base
        """
        monster = self.get_monster_stats(monster_id)
        if not monster:
            logger.warning(f"Monster not found: {monster_id}")
            return None
        
        # Parse armor class (can be complex in 5e data)
        ac = 10
        if monster.get('armor_class'):
            if isinstance(monster['armor_class'], list):
                ac = monster['armor_class'][0].get('value', 10)
            else:
                ac = monster['armor_class']
        
        # Get initiative modifier (DEX modifier)
        dex = monster.get('dexterity', 10)
        init_mod = (dex - 10) // 2
        
        # Build attacks list
        attacks = []
        for action in monster.get('actions', []):
            if action.get('attack_bonus') is not None:
                attacks.append({
                    'name': action['name'],
                    'attack_bonus': action['attack_bonus'],
                    'damage': action.get('damage', [{}])[0].get('damage_dice', '1d4'),
                    'damage_type': action.get('damage', [{}])[0].get('damage_type', {}).get('name', 'bludgeoning')
                })
        
        hp = monster.get('hit_points', 10) + hp_modifier
        
        return Combatant(
            id=f"{monster_id}_{len(self.combatants)}",
            name=name or monster['name'],
            hp_current=hp,
            hp_max=hp,
            armor_class=ac,
            initiative_modifier=init_mod,
            attacks=attacks,
            speed=self._parse_speed(monster.get('speed', {}))
        )
    
    def _parse_speed(self, speed_data: Dict) -> int:
        """Parse speed from monster data."""
        if isinstance(speed_data, dict):
            walk = speed_data.get('walk', '30 ft.')
            if isinstance(walk, str):
                return int(walk.replace(' ft.', '').replace('ft.', '') or 30)
            return walk
        return 30
    
    def create_player_combatant(self, character) -> Combatant:
        """Create a combatant from player character."""
        # Get DEX modifier for initiative
        dex_mod = (character.ability_scores.dex - 10) // 2
        
        # Build attacks from equipped weapons
        attacks = []
        for item in character.inventory:
            if item.equipped:
                weapon = self.weapons_data.get(item.item_id)
                if weapon and weapon.get('damage'):
                    # Calculate attack bonus
                    if 'finesse' in [p.get('index', '') for p in weapon.get('properties', [])]:
                        # Can use STR or DEX
                        str_mod = (character.ability_scores.str - 10) // 2
                        attack_mod = max(str_mod, dex_mod)
                    elif weapon.get('weapon_range') == 'Ranged':
                        attack_mod = dex_mod
                    else:
                        attack_mod = (character.ability_scores.str - 10) // 2
                    
                    attack_bonus = attack_mod + character.proficiency_bonus
                    
                    attacks.append({
                        'name': weapon['name'],
                        'attack_bonus': attack_bonus,
                        'damage': weapon['damage']['damage_dice'],
                        'damage_type': weapon['damage']['damage_type']['name'],
                        'damage_modifier': attack_mod
                    })
        
        # Default unarmed strike if no weapons
        if not attacks:
            str_mod = (character.ability_scores.str - 10) // 2
            attacks.append({
                'name': 'Unarmed Strike',
                'attack_bonus': str_mod + character.proficiency_bonus,
                'damage': '1',
                'damage_type': 'bludgeoning',
                'damage_modifier': str_mod
            })
        
        return Combatant(
            id="player",
            name=character.name,
            hp_current=character.hp.current,
            hp_max=character.hp.max,
            armor_class=character.armor_class,
            initiative_modifier=dex_mod,
            is_player=True,
            attacks=attacks,
            speed=character.speed
        )
    
    # =========================================================================
    # COMBAT FLOW
    # =========================================================================
    
    def start_combat(self, player_combatant: Combatant, 
                     enemy_combatants: List[Combatant]) -> str:
        """
        Start a combat encounter.
        
        Args:
            player_combatant: The player's combatant
            enemy_combatants: List of enemy combatants
            
        Returns:
            Narration of combat start with initiative order
        """
        self.phase = CombatPhase.ROLLING_INITIATIVE
        self.combatants = {}
        self.round = 1
        
        # Add player
        self.combatants[player_combatant.id] = player_combatant
        
        # Add enemies
        for enemy in enemy_combatants:
            self.combatants[enemy.id] = enemy
        
        # Roll initiative for everyone
        initiative_results = []
        for combatant in self.combatants.values():
            roll = DiceRoller.roll("1d20")
            combatant.initiative = roll.total + combatant.initiative_modifier
            initiative_results.append(
                f"  {combatant.name}: {roll.rolls[0]} + {combatant.initiative_modifier} = {combatant.initiative}"
            )
        
        # Sort by initiative (highest first)
        self.turn_order = sorted(
            self.combatants.keys(),
            key=lambda x: self.combatants[x].initiative,
            reverse=True
        )
        self.current_turn_index = 0
        self.phase = CombatPhase.COMBAT_ACTIVE
        
        # Build narration
        lines = [
            "⚔️ COMBAT BEGINS! ⚔️",
            "",
            "Initiative Rolls:",
            *initiative_results,
            "",
            "Turn Order:"
        ]
        for i, cid in enumerate(self.turn_order):
            c = self.combatants[cid]
            marker = "→" if i == 0 else " "
            lines.append(f"  {marker} {c.name} (Initiative: {c.initiative})")
        
        current = self.get_current_combatant()
        lines.extend(["", f"Round {self.round} - {current.name}'s turn!"])
        
        return "\n".join(lines)
    
    def get_current_combatant(self) -> Optional[Combatant]:
        """Get the combatant whose turn it is."""
        if not self.turn_order:
            return None
        return self.combatants.get(self.turn_order[self.current_turn_index])
    
    def next_turn(self) -> str:
        """
        Advance to next turn.
        
        Returns:
            Narration of turn change
        """
        self.current_turn_index += 1
        
        # Check if round is over
        if self.current_turn_index >= len(self.turn_order):
            self.current_turn_index = 0
            self.round += 1
        
        # Skip dead combatants
        attempts = 0
        while attempts < len(self.turn_order):
            current = self.get_current_combatant()
            if current and current.is_alive and current.is_conscious:
                break
            self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
            if self.current_turn_index == 0:
                self.round += 1
            attempts += 1
        
        current = self.get_current_combatant()
        if current:
            return f"Round {self.round} - {current.name}'s turn!"
        return "Combat has ended!"
    
    def attack(self, attacker_id: str, target_id: str, 
               attack_index: int = 0) -> AttackResult:
        """
        Make an attack.
        
        Args:
            attacker_id: ID of attacking combatant
            target_id: ID of target combatant
            attack_index: Which attack to use (if multiple)
            
        Returns:
            AttackResult with all details
        """
        attacker = self.combatants.get(attacker_id)
        target = self.combatants.get(target_id)
        
        if not attacker or not target:
            raise ValueError("Invalid attacker or target")
        
        if not attacker.attacks:
            raise ValueError(f"{attacker.name} has no attacks!")
        
        attack_data = attacker.attacks[min(attack_index, len(attacker.attacks) - 1)]
        
        # Roll attack
        attack_roll = DiceRoller.roll("1d20")
        attack_total = attack_roll.total + attack_data['attack_bonus']
        
        # Check for critical/fumble
        critical = attack_roll.natural_20
        fumble = attack_roll.natural_1
        
        # Determine hit (crits always hit, fumbles always miss)
        hit = critical or (not fumble and attack_total >= target.armor_class)
        
        result = AttackResult(
            hit=hit,
            critical=critical,
            fumble=fumble,
            attack_roll=attack_roll,
            attack_total=attack_total,
            target_ac=target.armor_class,
            attacker=attacker.name,
            target=target.name,
            damage_type=attack_data.get('damage_type', 'bludgeoning')
        )
        
        if hit:
            # Roll damage
            damage_expr = attack_data['damage']
            damage_mod = attack_data.get('damage_modifier', 0)
            
            # Handle simple damage (like "1" for unarmed)
            if damage_expr.isdigit():
                damage = int(damage_expr) + damage_mod
                result.damage = max(1, damage)
                result.damage_roll = DiceResult(
                    total=result.damage,
                    rolls=[int(damage_expr)],
                    modifier=damage_mod,
                    dice_expr=damage_expr
                )
            else:
                # Add modifier to expression if not already there
                if damage_mod and '+' not in damage_expr and '-' not in damage_expr:
                    damage_expr = f"{damage_expr}+{damage_mod}"
                
                result.damage_roll = DiceRoller.roll(damage_expr)
                
                # Double dice on crit
                if critical:
                    crit_roll = DiceRoller.roll(attack_data['damage'])
                    result.damage = result.damage_roll.total + crit_roll.total
                else:
                    result.damage = result.damage_roll.total
            
            result.damage = max(1, result.damage)  # Minimum 1 damage on hit
            
            # Apply damage to target
            target.take_damage(result.damage)
        
        return result
    
    def check_combat_end(self) -> Tuple[bool, str]:
        """
        Check if combat should end.
        
        Returns:
            (combat_ended, result_message)
        """
        player_alive = any(
            c.is_alive for c in self.combatants.values() if c.is_player
        )
        enemies_alive = any(
            c.is_alive for c in self.combatants.values() if not c.is_player
        )
        
        if not player_alive:
            self.phase = CombatPhase.COMBAT_ENDED
            return True, "DEFEAT! The player has fallen!"
        
        if not enemies_alive:
            self.phase = CombatPhase.COMBAT_ENDED
            return True, "VICTORY! All enemies have been defeated!"
        
        return False, ""
    
    def get_combat_status(self) -> str:
        """Get current combat status summary."""
        if self.phase != CombatPhase.COMBAT_ACTIVE:
            return "Not in combat"
        
        lines = [f"⚔️ Combat - Round {self.round}"]
        
        for cid in self.turn_order:
            c = self.combatants[cid]
            marker = "→" if cid == self.turn_order[self.current_turn_index] else " "
            status = "💀" if not c.is_alive else "😵" if not c.is_conscious else ""
            hp_str = f"{c.hp_current}/{c.hp_max}"
            lines.append(f"  {marker} {c.name}: {hp_str} HP {status}")
        
        return "\n".join(lines)
    
    def end_combat(self) -> Dict:
        """
        End combat and return summary.
        
        Returns:
            Dict with combat results
        """
        self.phase = CombatPhase.NOT_IN_COMBAT
        
        defeated_enemies = [
            c for c in self.combatants.values() 
            if not c.is_player and not c.is_alive
        ]
        
        # Calculate XP (simplified - would normally come from monster data)
        total_xp = len(defeated_enemies) * 50  # Placeholder
        
        result = {
            'rounds': self.round,
            'enemies_defeated': [e.name for e in defeated_enemies],
            'xp_earned': total_xp,
            'player_hp_remaining': next(
                (c.hp_current for c in self.combatants.values() if c.is_player), 0
            )
        }
        
        # Clear combat state
        self.combatants = {}
        self.turn_order = []
        self.current_turn_index = 0
        self.round = 0
        
        return result


# =============================================================================
# MAIN RULES ENGINE
# =============================================================================

class RulesEngine:
    """
    Main rules engine that coordinates all game mechanics.
    """
    
    def __init__(self, foundation_path: str = "data/foundation"):
        """
        Initialize rules engine.
        
        Args:
            foundation_path: Path to foundation data
        """
        self.foundation_path = Path(foundation_path)
        self.dice = DiceRoller()
        self.combat = CombatEngine(foundation_path)
        self._check_engine: Optional[CheckEngine] = None
        
        # Load foundation data
        self.conditions = self._load_conditions()
    
    def _load_conditions(self) -> Dict:
        """Load condition definitions."""
        try:
            with open(self.foundation_path / "rules" / "conditions.json") as f:
                conditions = json.load(f)
                return {c['index']: c for c in conditions}
        except Exception as e:
            logger.error(f"Failed to load conditions: {e}")
            return {}
    
    def set_character(self, character):
        """Set the character for skill/ability checks."""
        self._check_engine = CheckEngine(character)
    
    @property
    def checks(self) -> CheckEngine:
        """Get the check engine."""
        if not self._check_engine:
            raise RuntimeError("Character not set. Call set_character() first.")
        return self._check_engine
    
    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================
    
    def roll(self, expression: str) -> DiceResult:
        """Roll dice."""
        return self.dice.roll(expression)
    
    def skill_check(self, skill: str, dc: int, **kwargs) -> CheckResult:
        """Make a skill check."""
        return self.checks.skill_check(skill, dc, **kwargs)
    
    def ability_check(self, ability: str, dc: int, **kwargs) -> CheckResult:
        """Make an ability check."""
        return self.checks.ability_check(ability, dc, **kwargs)
    
    def saving_throw(self, ability: str, dc: int, **kwargs) -> CheckResult:
        """Make a saving throw."""
        return self.checks.saving_throw(ability, dc, **kwargs)
    
    def get_condition_effects(self, condition: str) -> Optional[Dict]:
        """Get the effects of a condition."""
        return self.conditions.get(condition.lower())
    
    # =========================================================================
    # COMMON CHECK SCENARIOS
    # =========================================================================
    
    def perception_check(self, dc: int, **kwargs) -> Tuple[CheckResult, str]:
        """
        Make a perception check with narrative result.
        
        Returns:
            (CheckResult, narrative_prompt)
        """
        result = self.skill_check("perception", dc, **kwargs)
        
        if result.critical_success:
            prompt = "The player notices everything with exceptional clarity. Describe what they find in great detail."
        elif result.success:
            if result.margin >= 5:
                prompt = "The player notices the important details clearly."
            else:
                prompt = "The player notices something, but might miss finer details."
        elif result.critical_failure:
            prompt = "The player is completely oblivious and might even notice something misleading."
        else:
            prompt = "The player doesn't notice anything unusual."
        
        return result, prompt
    
    def stealth_check(self, dc: int, **kwargs) -> Tuple[CheckResult, str]:
        """Make a stealth check with narrative result."""
        result = self.skill_check("stealth", dc, **kwargs)
        
        if result.critical_success:
            prompt = "The player moves like a shadow, completely undetected."
        elif result.success:
            prompt = "The player successfully stays hidden."
        elif result.critical_failure:
            prompt = "The player makes a loud noise and is definitely noticed!"
        else:
            prompt = "The player fails to stay hidden and is spotted."
        
        return result, prompt
    
    def persuasion_check(self, dc: int, npc_disposition: int = 50, **kwargs) -> Tuple[CheckResult, str]:
        """
        Make a persuasion check, modified by NPC disposition.
        
        Args:
            dc: Base DC
            npc_disposition: NPC's disposition (-100 to 100), modifies DC
        """
        # Adjust DC based on disposition
        # Friendly NPCs are easier to persuade, hostile harder
        dc_modifier = -(npc_disposition // 20)  # -5 to +5 modifier
        adjusted_dc = max(5, dc + dc_modifier)
        
        result = self.skill_check("persuasion", adjusted_dc, **kwargs)
        
        if result.critical_success:
            prompt = "The NPC is completely won over by the player's words."
        elif result.success:
            prompt = "The NPC is persuaded by the player's argument."
        elif result.critical_failure:
            prompt = "The player's words backfire spectacularly, possibly offending the NPC."
        else:
            prompt = "The NPC remains unconvinced."
        
        return result, prompt
