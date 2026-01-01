"""
Test the Rules Engine - Dice rolls, skill checks, and combat
"""

import sys
sys.path.insert(0, '/home/robbhimself/bardic-ai')

from engine.rules_engine import RulesEngine, DiceRoller, CombatEngine
from engine.schemas import Character, AbilityScores, HitPoints, Proficiencies, InventoryItem


def test_dice_rolling():
    """Test dice rolling functionality"""
    print("\n" + "="*60)
    print("TESTING DICE ROLLING")
    print("="*60)
    
    # Basic rolls
    print("\n1. Basic dice rolls:")
    for expr in ["1d20", "2d6", "1d8+3", "4d6", "1d20-2"]:
        result = DiceRoller.roll(expr)
        print(f"   {expr}: {result}")
    
    # Advantage/Disadvantage
    print("\n2. Advantage roll:")
    final, roll1, roll2 = DiceRoller.roll_with_advantage()
    print(f"   Roll 1: {roll1.total}, Roll 2: {roll2.total}, Using: {final.total}")
    
    print("\n3. Disadvantage roll:")
    final, roll1, roll2 = DiceRoller.roll_with_disadvantage()
    print(f"   Roll 1: {roll1.total}, Roll 2: {roll2.total}, Using: {final.total}")
    
    # Test for natural 20s/1s (roll many times)
    print("\n4. Testing for crits (rolling 100 d20s):")
    nat_20s = 0
    nat_1s = 0
    for _ in range(100):
        result = DiceRoller.roll("1d20")
        if result.natural_20:
            nat_20s += 1
        if result.natural_1:
            nat_1s += 1
    print(f"   Natural 20s: {nat_20s}, Natural 1s: {nat_1s}")
    
    print("\n✓ Dice rolling tests complete!")


def test_skill_checks():
    """Test skill checks and saving throws"""
    print("\n" + "="*60)
    print("TESTING SKILL CHECKS")
    print("="*60)
    
    # Create a test character
    character = Character(
        name="Test Barbarian",
        race="human",
        char_class="barbarian",
        level=1,
        ability_scores=AbilityScores(str=16, dex=14, con=15, int=8, wis=12, cha=10),
        hp=HitPoints(current=14, max=14),
        proficiency_bonus=2,
        proficiencies=Proficiencies(
            skills=["athletics", "intimidation"],
            saving_throws=["str", "con"]
        )
    )
    
    rules = RulesEngine()
    rules.set_character(character)
    
    print(f"\n1. Character: {character.name}")
    print(f"   STR: {character.ability_scores.str} (mod: +{(character.ability_scores.str-10)//2})")
    print(f"   DEX: {character.ability_scores.dex} (mod: +{(character.ability_scores.dex-10)//2})")
    print(f"   Proficient in: {character.proficiencies.skills}")
    
    print("\n2. Ability Checks:")
    for ability in ['str', 'dex', 'int']:
        result = rules.ability_check(ability, dc=12)
        print(f"   {result}")
    
    print("\n3. Skill Checks:")
    for skill in ['athletics', 'stealth', 'perception', 'intimidation']:
        result = rules.skill_check(skill, dc=12)
        prof = "(proficient)" if skill in ['athletics', 'intimidation'] else ""
        print(f"   {skill} {prof}: {result}")
    
    print("\n4. Saving Throws:")
    for ability in ['str', 'dex', 'con']:
        result = rules.saving_throw(ability, dc=13)
        prof = "(proficient)" if ability in ['str', 'con'] else ""
        print(f"   {ability.upper()} save {prof}: {result}")
    
    print("\n5. Advantage/Disadvantage checks:")
    result = rules.skill_check("athletics", dc=15, advantage=True)
    print(f"   Athletics with advantage: {result}")
    
    result = rules.skill_check("stealth", dc=10, disadvantage=True)
    print(f"   Stealth with disadvantage: {result}")
    
    print("\n✓ Skill check tests complete!")


def test_combat():
    """Test combat system"""
    print("\n" + "="*60)
    print("TESTING COMBAT")
    print("="*60)
    
    # Create player character
    character = Character(
        name="Smite",
        race="human",
        char_class="barbarian",
        level=1,
        ability_scores=AbilityScores(str=16, dex=14, con=15, int=8, wis=12, cha=10),
        hp=HitPoints(current=14, max=14),
        armor_class=14,
        proficiency_bonus=2,
        proficiencies=Proficiencies(
            skills=["athletics", "intimidation"],
            saving_throws=["str", "con"]
        ),
        inventory=[
            InventoryItem(item_id="greataxe", equipped=True)
        ]
    )
    
    combat = CombatEngine()
    
    print("\n1. Loading monster data:")
    goblin_stats = combat.get_monster_stats("goblin")
    if goblin_stats:
        print(f"   ✓ Found goblin: HP {goblin_stats['hit_points']}, AC {goblin_stats['armor_class']}")
    else:
        print("   ✗ Goblin not found in foundation data")
        return
    
    print("\n2. Creating combatants:")
    player = combat.create_player_combatant(character)
    print(f"   Player: {player.name}, HP: {player.hp_current}/{player.hp_max}, AC: {player.armor_class}")
    print(f"   Attacks: {[a['name'] for a in player.attacks]}")
    
    goblin1 = combat.create_monster_combatant("goblin", "Goblin Scout")
    goblin2 = combat.create_monster_combatant("goblin", "Goblin Warrior")
    print(f"   Enemy 1: {goblin1.name}, HP: {goblin1.hp_current}, AC: {goblin1.armor_class}")
    print(f"   Enemy 2: {goblin2.name}, HP: {goblin2.hp_current}, AC: {goblin2.armor_class}")
    
    print("\n3. Starting combat:")
    start_narration = combat.start_combat(player, [goblin1, goblin2])
    print(start_narration)
    
    print("\n4. Combat status:")
    print(combat.get_combat_status())
    
    print("\n5. Simulating combat rounds:")
    max_rounds = 10
    round_count = 0
    
    while round_count < max_rounds:
        current = combat.get_current_combatant()
        if not current:
            break
        
        # Skip unconscious/dead
        if not current.is_alive or not current.is_conscious:
            combat.next_turn()
            continue
        
        # Find a valid target
        if current.is_player:
            targets = [c for c in combat.combatants.values() if not c.is_player and c.is_alive]
        else:
            targets = [c for c in combat.combatants.values() if c.is_player and c.is_alive]
        
        if not targets:
            break
        
        target = targets[0]
        
        # Make attack
        result = combat.attack(current.id, target.id)
        print(f"   {result}")
        
        # Check combat end
        ended, message = combat.check_combat_end()
        if ended:
            print(f"\n   {message}")
            break
        
        # Next turn
        turn_msg = combat.next_turn()
        if combat.round > round_count + 1:
            round_count = combat.round
            print(f"\n   --- {turn_msg} ---")
    
    print("\n6. Combat summary:")
    summary = combat.end_combat()
    print(f"   Rounds: {summary['rounds']}")
    print(f"   Enemies defeated: {summary['enemies_defeated']}")
    print(f"   XP earned: {summary['xp_earned']}")
    print(f"   Player HP remaining: {summary['player_hp_remaining']}")
    
    print("\n✓ Combat tests complete!")


def test_common_checks():
    """Test common check scenarios with narrative prompts"""
    print("\n" + "="*60)
    print("TESTING COMMON CHECK SCENARIOS")
    print("="*60)
    
    character = Character(
        name="Test Rogue",
        race="elf",
        char_class="rogue",
        level=1,
        ability_scores=AbilityScores(str=10, dex=16, con=12, int=14, wis=12, cha=14),
        hp=HitPoints(current=9, max=9),
        proficiency_bonus=2,
        proficiencies=Proficiencies(
            skills=["stealth", "perception", "persuasion", "deception"]
        )
    )
    
    rules = RulesEngine()
    rules.set_character(character)
    
    print(f"\n1. Perception Check (DC 15):")
    result, prompt = rules.perception_check(dc=15)
    print(f"   {result}")
    print(f"   AI Prompt: {prompt}")
    
    print(f"\n2. Stealth Check (DC 12):")
    result, prompt = rules.stealth_check(dc=12)
    print(f"   {result}")
    print(f"   AI Prompt: {prompt}")
    
    print(f"\n3. Persuasion vs Friendly NPC (DC 15, disposition +60):")
    result, prompt = rules.persuasion_check(dc=15, npc_disposition=60)
    print(f"   {result}")
    print(f"   AI Prompt: {prompt}")
    
    print(f"\n4. Persuasion vs Hostile NPC (DC 15, disposition -40):")
    result, prompt = rules.persuasion_check(dc=15, npc_disposition=-40)
    print(f"   {result}")
    print(f"   AI Prompt: {prompt}")
    
    print("\n✓ Common check scenario tests complete!")


if __name__ == "__main__":
    print("="*60)
    print("RULES ENGINE TEST SUITE")
    print("="*60)
    
    test_dice_rolling()
    test_skill_checks()
    test_combat()
    test_common_checks()
    
    print("\n" + "="*60)
    print("ALL RULES ENGINE TESTS COMPLETE ✓")
    print("="*60)
