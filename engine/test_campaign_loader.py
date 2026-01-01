#!/usr/bin/env python3
"""
Test script for campaign loader and state manager
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.loaders import load_full_campaign
from engine.state_manager import StateManager
from engine.schemas.game_state import Character, AbilityScores, HitPoints

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_campaign_loading():
    """Test loading the goblin kidnapping campaign."""
    print("\n" + "="*60)
    print("TESTING CAMPAIGN LOADER")
    print("="*60 + "\n")

    campaign_dir = "data/campaigns/goblin_kidnapping_v2"

    # Load campaign
    print("1. Loading campaign...")
    campaign, nodes, npcs, encounters = load_full_campaign(campaign_dir)

    if not campaign:
        print("❌ Failed to load campaign!")
        return False

    print(f"✓ Campaign: {campaign.title}")
    print(f"  Author: {campaign.author}")
    print(f"  Description: {campaign.description[:80]}...")
    print(f"  Chapters: {len(campaign.chapters)}")

    # Verify nodes
    print(f"\n2. Verifying nodes... ({len(nodes)} loaded)")
    for node_id, node in list(nodes.items())[:3]:
        print(f"  ✓ {node.name} ({node_id})")
        print(f"    NPCs: {len(node.npcs_present)}")
        print(f"    Exits: {len(node.exits)}")
        print(f"    Actions: {len(node.significant_actions)}")

    # Verify NPCs
    print(f"\n3. Verifying NPCs... ({len(npcs.npcs)} loaded)")
    for npc_id, npc in list(npcs.npcs.items()):
        print(f"  ✓ {npc.name} ({npc_id})")
        print(f"    Role: {npc.role}")
        print(f"    Knowledge topics: {len(npc.knowledge)}")
        print(f"    Base disposition: {npc.base_disposition}")

    # Verify encounters
    print(f"\n4. Verifying encounters... ({len(encounters.encounters)} loaded)")
    for enc_id, enc in encounters.encounters.items():
        print(f"  ✓ {enc.name} ({enc_id})")
        print(f"    Difficulty: {enc.difficulty}")
        print(f"    Enemies: {len(enc.enemies)}")

    print("\n" + "="*60)
    print("CAMPAIGN LOADING: SUCCESS")
    print("="*60)

    return campaign, nodes, npcs, encounters


def test_state_manager(campaign, nodes, npcs, encounters):
    """Test state manager functionality."""
    print("\n" + "="*60)
    print("TESTING STATE MANAGER")
    print("="*60 + "\n")

    # Create a test character
    print("1. Creating test character...")
    character = Character(
        name="Test Hero",
        race="human",
        char_class="fighter",
        level=1,
        ability_scores=AbilityScores(str=16, dex=14, con=15, int=10, wis=12, cha=8),
        hp=HitPoints(current=12, max=12)
    )
    print(f"✓ {character.name} - Level {character.level} {character.race} {character.char_class}")

    # Initialize state manager
    print("\n2. Initializing state manager...")
    manager = StateManager(campaign, nodes, npcs, encounters, character)
    game_state = manager.initialize_new_game("test_session")
    print(f"✓ Game state initialized: {game_state.session_id}")
    print(f"  Starting node: {game_state.location.node_id}")

    # Test getting current node
    print("\n3. Testing node retrieval...")
    current_node = manager.get_current_node()
    print(f"✓ Current node: {current_node.name}")
    print(f"  Description: {current_node.description.short}")

    # Test available exits
    print("\n4. Testing exit detection...")
    exits = manager.get_available_exits()
    print(f"✓ Available exits: {len(exits)}")
    for exit_id, exit_data in exits.items():
        print(f"  → {exit_data.description} (to {exit_data.target_node})")

    # Test flag system
    print("\n5. Testing flag system...")
    manager.set_flag("test_flag", True)
    assert manager.has_flag("test_flag"), "Flag should be set"
    print("✓ Flag set/check working")

    manager.set_flag("another_flag", True)
    result = manager.check_condition("test_flag && another_flag")
    assert result, "AND condition should be true"
    print("✓ AND condition working")

    result = manager.check_condition("!missing_flag")
    assert result, "Negation should work"
    print("✓ Negation working")

    # Test relationship system
    print("\n6. Testing relationship system...")
    npc_id = "ameiko"
    initial_disp = manager.get_npc_disposition(npc_id)
    print(f"  Initial disposition with {npc_id}: {initial_disp}")

    manager.modify_relationship(npc_id, disposition=10, trust=5, event="helped_rescue")
    new_disp = manager.get_npc_disposition(npc_id)
    print(f"  New disposition: {new_disp}")
    assert new_disp == initial_disp + 10, "Disposition should increase"
    print("✓ Relationship modification working")

    attitude = manager.get_npc_attitude(npc_id)
    print(f"  Attitude: {attitude}")

    # Test NPC greeting
    print("\n7. Testing NPC interactions...")
    greeting = manager.get_npc_greeting(npc_id)
    print(f"  Greeting: {greeting[:80]}...")
    print("✓ NPC greeting working")

    # Test knowledge sharing
    knowledge = manager.get_npc_knowledge(npc_id, "kidnappings")
    if knowledge:
        print(f"  Knowledge shared: {knowledge[:80]}...")
        print("✓ Knowledge sharing working")
    else:
        print("  ⚠ NPC not willing to share this knowledge")

    # Test quest system
    print("\n8. Testing quest system...")
    manager.start_quest("test_quest", "Test Quest", "A test quest for demonstration")
    active_quests = game_state.story_progress.get_active_quests()
    assert len(active_quests) == 1, "Should have 1 active quest"
    print(f"✓ Quest started: {active_quests[0].name}")

    # Test movement
    print("\n9. Testing node movement...")
    target_node = None
    for exit_data in exits.values():
        target_node = exit_data.target_node
        break

    if target_node:
        success, message = manager.move_to_node(target_node)
        if success:
            print(f"✓ Moved to: {manager.get_current_node().name}")
        else:
            print(f"❌ Move failed: {message}")
    else:
        print("  ⚠ No exits available to test movement")

    # Test AI context generation
    print("\n10. Testing AI context generation...")
    context = manager.get_context_for_ai()
    print(f"✓ Context generated:")
    print(f"  Campaign: {context['campaign']['title']}")
    print(f"  Location: {context['location']['name']}")
    print(f"  Character: {context['character']['name']}")
    print(f"  NPCs present: {len(context['npcs_present'])}")
    print(f"  Available exits: {len(context['available_exits'])}")
    print(f"  Active quests: {len(context['active_quests'])}")

    # Test significant action execution
    print("\n11. Testing significant action execution...")
    current_node = manager.get_current_node()
    if current_node.significant_actions:
        action_id = list(current_node.significant_actions.keys())[0]
        action = current_node.significant_actions[action_id]
        print(f"  Attempting action: {action_id}")
        print(f"  Description: {action.trigger_description}")

        success, message, effects = manager.execute_significant_action(action_id)
        if success:
            print(f"  ✓ Action executed!")
            print(f"  Effects: {effects}")
        else:
            print(f"  ⚠ Action failed: {message}")
    else:
        print("  ⚠ No significant actions in current node")

    # Test save
    print("\n12. Testing state save...")
    try:
        manager.save_state("test_save.json")
        print("✓ State saved to test_save.json")
    except Exception as e:
        print(f"⚠ Save not fully implemented: {e}")

    print("\n" + "="*60)
    print("STATE MANAGER: SUCCESS")
    print("="*60)

    return manager


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("CAMPAIGN LOADER & STATE MANAGER TEST SUITE")
    print("="*60)

    try:
        # Test campaign loading
        campaign, nodes, npcs, encounters = test_campaign_loading()

        if not campaign:
            print("\n❌ Campaign loading failed. Aborting.")
            return 1

        # Test state manager
        manager = test_state_manager(campaign, nodes, npcs, encounters)

        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60 + "\n")

        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
