"""
Campaign Data Loaders - Load JSON files into dataclass instances
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from engine.schemas.campaign import (
    Campaign, Chapter, Node, NodeDescription, ImagePrompt,
    NPCPresence, ItemForSale, SignificantAction, RelationshipUpdate,
    NodeExit, SoftGate, EncounterReference, AmbientDetails,
    OnEnterBehavior, ChapterCompletionConditions, CampaignSetting
)
from engine.schemas.npc import (
    NPC, NPCRegistry, NPCAppearance, NPCPersonality, NPCVoice,
    KnowledgeTopic, DialogueLines, NPCRelationshipConfig,
    RelationshipThreshold, TradeConfig
)
from engine.schemas.encounter import (
    Encounter, EncounterRegistry, EnemyInstance, EncounterReward,
    EncounterEnvironment
)

logger = logging.getLogger(__name__)


def load_campaign(campaign_path: str) -> Optional[Campaign]:
    """
    Load campaign from campaign.json file.

    Args:
        campaign_path: Path to the campaign directory or campaign.json file

    Returns:
        Campaign object or None if loading fails
    """
    try:
        # Handle both directory and file paths
        path = Path(campaign_path)
        if path.is_dir():
            campaign_file = path / "campaign.json"
        else:
            campaign_file = path

        logger.info(f"Loading campaign from {campaign_file}")

        with open(campaign_file, 'r') as f:
            data = json.load(f)

        # Parse setting
        setting_data = data.get("setting", {})
        setting = CampaignSetting(
            world=setting_data.get("world", "generic_fantasy"),
            region=setting_data.get("region", ""),
            starting_location=setting_data.get("starting_location", "")
        )

        # Parse chapters
        chapters = []
        for chapter_data in data.get("chapters", []):
            # Parse completion conditions
            completion_data = chapter_data.get("completion_conditions", {})
            completion = ChapterCompletionConditions(
                required_flags=completion_data.get("required_flags", []),
                recommended_flags=completion_data.get("recommended_flags", []),
                required_quests_complete=completion_data.get("required_quests_complete", [])
            )

            chapter = Chapter(
                chapter_id=chapter_data["chapter_id"],
                title=chapter_data["title"],
                summary=chapter_data["summary"],
                chapter_number=chapter_data.get("chapter_number", 1),
                nodes=chapter_data.get("nodes", []),
                starting_node=chapter_data.get("starting_node", ""),
                completion_conditions=completion,
                intro_narration=chapter_data.get("intro_narration", ""),
                outro_narration=chapter_data.get("outro_narration", "")
            )
            chapters.append(chapter)

        campaign = Campaign(
            campaign_id=data["campaign_id"],
            title=data["title"],
            description=data["description"],
            author=data.get("author", "Unknown"),
            version=data.get("version", "1.0"),
            recommended_level_min=data.get("recommended_level_min", 1),
            recommended_level_max=data.get("recommended_level_max", 5),
            estimated_duration=data.get("estimated_duration", "3-4 sessions"),
            setting=setting,
            chapters=chapters,
            npcs_file=data.get("npcs_file", "npcs.json"),
            encounters_file=data.get("encounters_file", "encounters.json"),
            items_file=data.get("items_file", "items.json"),
            nodes_file=data.get("nodes_file", "nodes.json")
        )

        logger.info(f"✓ Loaded campaign: {campaign.title}")
        logger.info(f"  Chapters: {len(campaign.chapters)}")

        return campaign

    except FileNotFoundError:
        logger.error(f"Campaign file not found: {campaign_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in campaign file: {e}")
        return None
    except KeyError as e:
        logger.error(f"Missing required field in campaign: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading campaign: {e}")
        return None


def load_nodes(nodes_path: str) -> Dict[str, Node]:
    """
    Load all nodes from nodes JSON file.

    Args:
        nodes_path: Path to the nodes JSON file

    Returns:
        Dictionary mapping node_id to Node objects
    """
    try:
        logger.info(f"Loading nodes from {nodes_path}")

        with open(nodes_path, 'r') as f:
            data = json.load(f)

        nodes = {}
        for node_id, node_data in data.get("nodes", {}).items():
            # Parse description
            desc_data = node_data.get("description", {})
            img_prompt_data = desc_data.get("image_prompt")
            image_prompt = None
            if img_prompt_data:
                image_prompt = ImagePrompt(
                    scene=img_prompt_data.get("scene", ""),
                    style=img_prompt_data.get("style", "fantasy, detailed, dramatic lighting"),
                    negative=img_prompt_data.get("negative", "modern, sci-fi, cartoon")
                )

            description = NodeDescription(
                short=desc_data.get("short", ""),
                long=desc_data.get("long", ""),
                image_prompt=image_prompt
            )

            # Parse NPCs present
            npcs_present = []
            for npc_data in node_data.get("npcs_present", []):
                npcs_present.append(NPCPresence(
                    npc_id=npc_data["npc_id"],
                    role=npc_data.get("role", "ambient"),
                    required=npc_data.get("required", False),
                    topics=npc_data.get("topics", []),
                    initial_disposition_modifier=npc_data.get("initial_disposition_modifier", 0)
                ))

            # Parse items for sale
            items_available = []
            for item_data in node_data.get("items_available", []):
                items_available.append(ItemForSale(
                    item_id=item_data["item_id"],
                    cost=item_data.get("cost", "0 gp"),
                    quantity=item_data.get("quantity", -1)
                ))

            # Parse significant actions
            significant_actions = {}
            for action_id, action_data in node_data.get("significant_actions", {}).items():
                # Parse relationship updates
                rel_updates = {}
                for npc_id, update_data in action_data.get("updates_relationships", {}).items():
                    rel_updates[npc_id] = RelationshipUpdate(
                        disposition=update_data.get("disposition", 0),
                        trust=update_data.get("trust", 0)
                    )

                significant_actions[action_id] = SignificantAction(
                    action_id=action_id,
                    trigger_description=action_data.get("trigger_description", ""),
                    requires_flags=action_data.get("requires_flags", []),
                    requires_items=action_data.get("requires_items", []),
                    requires_relationship=action_data.get("requires_relationship"),
                    sets_flags=action_data.get("sets_flags", []),
                    clears_flags=action_data.get("clears_flags", []),
                    grants_items=action_data.get("grants_items", []),
                    removes_items=action_data.get("removes_items", []),
                    grants_quest=action_data.get("grants_quest"),
                    completes_objective=action_data.get("completes_objective"),
                    updates_relationships=rel_updates,
                    grants_xp=action_data.get("grants_xp", 0),
                    success_prompt=action_data.get("success_prompt"),
                    failure_prompt=action_data.get("failure_prompt")
                )

            # Parse exits
            exits = {}
            for exit_id, exit_data in node_data.get("exits", {}).items():
                # Parse soft gate if present
                soft_gate = None
                sg_data = exit_data.get("soft_gate")
                if sg_data:
                    soft_gate = SoftGate(
                        condition=sg_data.get("condition", ""),
                        warning_npc=sg_data.get("warning_npc"),
                        warning_prompt=sg_data.get("warning_prompt", "")
                    )

                exits[exit_id] = NodeExit(
                    target_node=exit_data["target_node"],
                    description=exit_data.get("description", ""),
                    direction=exit_data.get("direction", ""),
                    always_available=exit_data.get("always_available", True),
                    requires_flags=exit_data.get("requires_flags", []),
                    requires_items=exit_data.get("requires_items", []),
                    blocked_message=exit_data.get("blocked_message", ""),
                    soft_gate=soft_gate,
                    transition_prompt=exit_data.get("transition_prompt")
                )

            # Parse encounters
            encounters = []
            for enc_data in node_data.get("encounters", []):
                encounters.append(EncounterReference(
                    encounter_id=enc_data["encounter_id"],
                    trigger=enc_data.get("trigger", "on_enter"),
                    chance=enc_data.get("chance", 1.0),
                    once_only=enc_data.get("once_only", True),
                    requires_flags=enc_data.get("requires_flags", [])
                ))

            # Parse ambient details
            ambient_data = node_data.get("ambient", {})
            ambient = AmbientDetails(
                sounds=ambient_data.get("sounds", []),
                smells=ambient_data.get("smells", []),
                mood=ambient_data.get("mood", "neutral")
            )

            # Parse on_enter behaviors
            on_enter_first = None
            if "on_enter_first" in node_data:
                oef_data = node_data["on_enter_first"]
                on_enter_first = OnEnterBehavior(
                    narration_prompt=oef_data.get("narration_prompt", ""),
                    auto_approach_npc=oef_data.get("auto_approach_npc"),
                    trigger_encounter=oef_data.get("trigger_encounter"),
                    set_flags=oef_data.get("set_flags", [])
                )

            on_enter_subsequent = None
            if "on_enter_subsequent" in node_data:
                oes_data = node_data["on_enter_subsequent"]
                on_enter_subsequent = OnEnterBehavior(
                    narration_prompt=oes_data.get("narration_prompt", ""),
                    auto_approach_npc=oes_data.get("auto_approach_npc"),
                    trigger_encounter=oes_data.get("trigger_encounter"),
                    set_flags=oes_data.get("set_flags", [])
                )

            # Create node
            node = Node(
                node_id=node_id,
                name=node_data.get("name", node_id),
                chapter_id=node_data.get("chapter_id", ""),
                description=description,
                npcs_present=npcs_present,
                items_available=items_available,
                items_findable=node_data.get("items_findable", []),
                significant_actions=significant_actions,
                encounters=encounters,
                exits=exits,
                ambient=ambient,
                on_enter_first=on_enter_first,
                on_enter_subsequent=on_enter_subsequent
            )

            nodes[node_id] = node

        logger.info(f"✓ Loaded {len(nodes)} nodes")
        return nodes

    except FileNotFoundError:
        logger.error(f"Nodes file not found: {nodes_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in nodes file: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading nodes: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_npcs(npcs_path: str) -> NPCRegistry:
    """
    Load all NPCs from npcs JSON file.

    Args:
        npcs_path: Path to the npcs JSON file

    Returns:
        NPCRegistry containing all NPCs
    """
    try:
        logger.info(f"Loading NPCs from {npcs_path}")

        with open(npcs_path, 'r') as f:
            data = json.load(f)

        registry = NPCRegistry()

        for npc_id, npc_data in data.get("npcs", {}).items():
            # Parse appearance
            app_data = npc_data.get("appearance", {})
            appearance = NPCAppearance(
                short=app_data.get("short", "A person"),
                detailed=app_data.get("detailed", ""),
                portrait_prompt=app_data.get("portrait_prompt", ""),
                portrait_url=app_data.get("portrait_url")
            )

            # Parse personality
            pers_data = npc_data.get("personality", {})
            personality = NPCPersonality(
                traits=pers_data.get("traits", []),
                ideals=pers_data.get("ideals", []),
                bonds=pers_data.get("bonds", []),
                flaws=pers_data.get("flaws", [])
            )

            # Parse voice
            voice_data = npc_data.get("voice", {})
            voice = NPCVoice(
                style=voice_data.get("style", "neutral"),
                speech_patterns=voice_data.get("speech_patterns", []),
                catchphrases=voice_data.get("catchphrases", []),
                voice_sample_file=voice_data.get("voice_sample_file")
            )

            # Parse knowledge topics
            knowledge = {}
            for topic_id, topic_data in npc_data.get("knowledge", {}).items():
                knowledge[topic_id] = KnowledgeTopic(
                    topic_id=topic_id,
                    knows=topic_data.get("knows", True),
                    information=topic_data.get("information", ""),
                    share_condition=topic_data.get("share_condition", "always"),
                    trust_threshold=topic_data.get("trust_threshold", 0),
                    shared=topic_data.get("shared", False)
                )

            # Parse dialogue
            dialogue_data = npc_data.get("dialogue", {})
            dialogue = DialogueLines(
                greeting_first=dialogue_data.get("greeting_first", "Hello there."),
                greeting_friendly=dialogue_data.get("greeting_friendly", "Good to see you again!"),
                greeting_unfriendly=dialogue_data.get("greeting_unfriendly", "What do you want?"),
                greeting_hostile=dialogue_data.get("greeting_hostile", "You have some nerve showing your face here."),
                farewell_friendly=dialogue_data.get("farewell_friendly", "Safe travels!"),
                farewell_neutral=dialogue_data.get("farewell_neutral", "Goodbye."),
                farewell_unfriendly=dialogue_data.get("farewell_unfriendly", "Just go."),
                custom=dialogue_data.get("custom", {})
            )

            # Parse relationship config (use defaults if not specified)
            rel_config = NPCRelationshipConfig()

            # Parse trade config
            trade_data = npc_data.get("trade", {})
            trade = TradeConfig(
                can_trade=trade_data.get("can_trade", False),
                inventory=trade_data.get("inventory", []),
                buys_items=trade_data.get("buys_items", False),
                price_modifier=trade_data.get("price_modifier", 1.0),
                friendly_discount=trade_data.get("friendly_discount", 0.1),
                hostile_markup=trade_data.get("hostile_markup", 0.5)
            )

            # Create NPC
            npc = NPC(
                npc_id=npc_id,
                name=npc_data["name"],
                race=npc_data.get("race", "human"),
                gender=npc_data.get("gender", "unknown"),
                age=npc_data.get("age", "adult"),
                appearance=appearance,
                personality=personality,
                voice=voice,
                role=npc_data.get("role", "commoner"),
                occupation=npc_data.get("occupation", ""),
                faction=npc_data.get("faction"),
                knowledge=knowledge,
                dialogue=dialogue,
                base_disposition=npc_data.get("base_disposition", 50),
                relationship_config=rel_config,
                trade=trade,
                can_fight=npc_data.get("can_fight", False),
                monster_stat_block=npc_data.get("monster_stat_block"),
                is_essential=npc_data.get("is_essential", False)
            )

            registry.add(npc)

        logger.info(f"✓ Loaded {len(registry.npcs)} NPCs")
        return registry

    except FileNotFoundError:
        logger.error(f"NPCs file not found: {npcs_path}")
        return NPCRegistry()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in NPCs file: {e}")
        return NPCRegistry()
    except Exception as e:
        logger.error(f"Error loading NPCs: {e}")
        import traceback
        traceback.print_exc()
        return NPCRegistry()


def load_encounters(encounters_path: str) -> EncounterRegistry:
    """
    Load all encounters from encounters JSON file.

    Args:
        encounters_path: Path to the encounters JSON file

    Returns:
        EncounterRegistry containing all encounters
    """
    try:
        logger.info(f"Loading encounters from {encounters_path}")

        with open(encounters_path, 'r') as f:
            data = json.load(f)

        registry = EncounterRegistry()

        for enc_id, enc_data in data.get("encounters", {}).items():
            # Parse enemies
            enemies = []
            for enemy_data in enc_data.get("enemies", []):
                enemies.append(EnemyInstance(
                    enemy_id=enemy_data["enemy_id"],
                    monster_id=enemy_data["monster_id"],
                    name=enemy_data.get("name", ""),
                    count=enemy_data.get("count", 1),
                    hp_modifier=enemy_data.get("hp_modifier", 0),
                    custom_equipment=enemy_data.get("custom_equipment", [])
                ))

            # Parse environment
            env_data = enc_data.get("environment", {})
            environment = EncounterEnvironment(
                description=env_data.get("description", ""),
                terrain=env_data.get("terrain", "normal"),
                lighting=env_data.get("lighting", "normal"),
                cover_available=env_data.get("cover_available", False),
                special_features=env_data.get("special_features", [])
            )

            # Parse rewards
            reward_data = enc_data.get("rewards", {})
            rewards = EncounterReward(
                xp=reward_data.get("xp", 0),
                gold=reward_data.get("gold", ""),
                items=reward_data.get("items", []),
                sets_flags=reward_data.get("sets_flags", [])
            )

            # Create encounter
            encounter = Encounter(
                encounter_id=enc_id,
                name=enc_data["name"],
                description=enc_data.get("description", ""),
                difficulty=enc_data.get("difficulty", "medium"),
                enemies=enemies,
                environment=environment,
                surprise_player_dc=enc_data.get("surprise_player_dc", 0),
                surprise_enemy_dc=enc_data.get("surprise_enemy_dc", 0),
                intro_narration=enc_data.get("intro_narration", ""),
                victory_narration=enc_data.get("victory_narration", ""),
                defeat_narration=enc_data.get("defeat_narration", ""),
                flee_narration=enc_data.get("flee_narration", ""),
                rewards=rewards,
                enemy_tactics=enc_data.get("enemy_tactics", ""),
                morale_break=enc_data.get("morale_break", 0.25)
            )

            registry.add(encounter)

        logger.info(f"✓ Loaded {len(registry.encounters)} encounters")
        return registry

    except FileNotFoundError:
        logger.error(f"Encounters file not found: {encounters_path}")
        return EncounterRegistry()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in encounters file: {e}")
        return EncounterRegistry()
    except Exception as e:
        logger.error(f"Error loading encounters: {e}")
        import traceback
        traceback.print_exc()
        return EncounterRegistry()


def load_full_campaign(campaign_dir: str) -> tuple[Optional[Campaign], Dict[str, Node], NPCRegistry, EncounterRegistry]:
    """
    Load complete campaign with all associated data.

    Args:
        campaign_dir: Path to campaign directory

    Returns:
        Tuple of (Campaign, nodes_dict, NPCRegistry, EncounterRegistry)
    """
    campaign_path = Path(campaign_dir)

    # Load campaign metadata
    campaign = load_campaign(campaign_path / "campaign.json")
    if not campaign:
        return None, {}, NPCRegistry(), EncounterRegistry()

    # Load associated files
    nodes = load_nodes(campaign_path / campaign.nodes_file)
    npcs = load_npcs(campaign_path / campaign.npcs_file)
    encounters = load_encounters(campaign_path / campaign.encounters_file)

    return campaign, nodes, npcs, encounters
