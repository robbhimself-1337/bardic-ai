import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class IntroScene:
    """Represents a single scene in the campaign intro sequence."""
    narration: str
    image_prompt: str = ""
    image_url: str = ""
    audio_url: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "narration": self.narration,
            "image_prompt": self.image_prompt,
            "image_url": self.image_url,
            "audio_url": self.audio_url
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IntroScene':
        """Create IntroScene from dictionary."""
        return cls(
            narration=data.get("narration", ""),
            image_prompt=data.get("image_prompt", ""),
            image_url=data.get("image_url", ""),
            audio_url=data.get("audio_url", "")
        )


@dataclass
class NPCDialogue:
    """Represents an NPC with scripted dialogue."""
    name: str
    role: str = ""
    greeting: str = ""
    dialogue_topics: Dict[str, str] = field(default_factory=dict)
    portrait_prompt: str = ""
    portrait_url: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "role": self.role,
            "greeting": self.greeting,
            "dialogue_topics": self.dialogue_topics,
            "portrait_prompt": self.portrait_prompt,
            "portrait_url": self.portrait_url
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NPCDialogue':
        """Create NPCDialogue from dictionary."""
        return cls(
            name=data.get("name", ""),
            role=data.get("role", ""),
            greeting=data.get("greeting", ""),
            dialogue_topics=data.get("dialogue_topics", {}),
            portrait_prompt=data.get("portrait_prompt", ""),
            portrait_url=data.get("portrait_url", "")
        )


@dataclass
class Choice:
    """Represents a player choice with transition narration."""
    text: str  # What the player sees: "Head to the forest"
    next_checkpoint: str  # Internal ID: "forest_path"
    narration: str = ""  # Transition text when chosen

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "next_checkpoint": self.next_checkpoint,
            "narration": self.narration
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Choice':
        """Create Choice from dictionary."""
        return cls(
            text=data.get("text", ""),
            next_checkpoint=data.get("next_checkpoint", ""),
            narration=data.get("narration", "")
        )


class Checkpoint:
    """Represents a story checkpoint/node in the campaign."""

    def __init__(
        self,
        checkpoint_id: str,
        description: str,
        name: str = "",
        entrance_narration: str = "",
        npcs_structured: Optional[List[NPCDialogue]] = None,
        choices: Optional[List[Choice]] = None,
        items_available: Optional[List[str]] = None,
        enemies: Optional[List[str]] = None,
        scene_prompt: str = "",
        scene_url: str = "",
        # Backwards compatibility fields
        npcs: Optional[List[str]] = None,
        next_checkpoints: Optional[List[str]] = None,
        auto_quests: Optional[List[Dict]] = None
    ):
        self.checkpoint_id = checkpoint_id
        self.name = name or checkpoint_id
        self.description = description
        self.entrance_narration = entrance_narration

        # New structured fields
        self.npcs_structured = npcs_structured if npcs_structured is not None else []
        self.choices = choices if choices is not None else []

        # Image fields
        self.scene_prompt = scene_prompt
        self.scene_url = scene_url

        # Backwards compatibility fields
        self.npcs = npcs if npcs is not None else []
        self.items_available = items_available if items_available is not None else []
        self.enemies = enemies if enemies is not None else []
        self.next_checkpoints = next_checkpoints if next_checkpoints is not None else []
        self.auto_quests = auto_quests if auto_quests is not None else []

    def to_dict(self) -> dict:
        """Convert checkpoint to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "name": self.name,
            "description": self.description,
            "entrance_narration": self.entrance_narration,
            "npcs_structured": [npc.to_dict() for npc in self.npcs_structured],
            "choices": [choice.to_dict() for choice in self.choices],
            "items_available": self.items_available,
            "enemies": self.enemies,
            "scene_prompt": self.scene_prompt,
            "scene_url": self.scene_url,
            # Backwards compatibility
            "npcs": self.npcs,
            "next_checkpoints": self.next_checkpoints,
            "auto_quests": self.auto_quests
        }

    @classmethod
    def from_dict(cls, checkpoint_id: str, data: dict) -> 'Checkpoint':
        """Create checkpoint from dictionary."""
        # Parse new structured NPCs
        npcs_structured = []
        if "npcs_structured" in data:
            for npc_data in data["npcs_structured"]:
                npcs_structured.append(NPCDialogue.from_dict(npc_data))

        # Parse choices
        choices = []
        if "choices" in data:
            for choice_data in data["choices"]:
                choices.append(Choice.from_dict(choice_data))

        return cls(
            checkpoint_id=checkpoint_id,
            name=data.get("name", checkpoint_id),
            description=data.get("description", ""),
            entrance_narration=data.get("entrance_narration", ""),
            npcs_structured=npcs_structured,
            choices=choices,
            items_available=data.get("items_available", []),
            enemies=data.get("enemies", []),
            scene_prompt=data.get("scene_prompt", ""),
            scene_url=data.get("scene_url", ""),
            # Backwards compatibility
            npcs=data.get("npcs", []),
            next_checkpoints=data.get("next_checkpoints", []),
            auto_quests=data.get("auto_quests", [])
        )


class Campaign:
    """Manages campaign template and checkpoint navigation."""

    def __init__(
        self,
        campaign_id: str,
        title: str,
        description: str,
        starting_checkpoint: str,
        checkpoints: Dict[str, Checkpoint],
        category: str = "short",
        estimated_duration: str = "4-6 hours",
        difficulty: str = "intermediate",
        intro_scenes: Optional[List[IntroScene]] = None
    ):
        self.campaign_id = campaign_id
        self.title = title
        self.description = description
        self.starting_checkpoint = starting_checkpoint
        self.checkpoints = checkpoints
        self.category = category
        self.estimated_duration = estimated_duration
        self.difficulty = difficulty
        self.intro_scenes = intro_scenes if intro_scenes is not None else []

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        return self.checkpoints.get(checkpoint_id)

    def get_checkpoint_context(self, checkpoint_id: str) -> str:
        """
        Get condensed context for a checkpoint to send to Ollama.
        Includes checkpoint description, NPCs, available items, and enemies.
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return ""

        context = f"Current Location: {checkpoint.description}\n"

        if checkpoint.npcs:
            context += f"NPCs Present: {', '.join(checkpoint.npcs)}\n"

        if checkpoint.items_available:
            context += f"Items Available: {', '.join(checkpoint.items_available)}\n"

        if checkpoint.enemies:
            context += f"Potential Threats: {', '.join(checkpoint.enemies)}\n"

        if checkpoint.next_checkpoints:
            context += f"Possible Paths: {', '.join(checkpoint.next_checkpoints)}\n"

        return context

    def validate_checkpoint_transition(
        self,
        current_checkpoint: str,
        next_checkpoint: str
    ) -> bool:
        """
        Check if transition from current to next checkpoint is valid.
        """
        checkpoint = self.get_checkpoint(current_checkpoint)
        if not checkpoint:
            return False

        return next_checkpoint in checkpoint.next_checkpoints

    @classmethod
    def load_campaign(cls, campaign_id: str) -> 'Campaign':
        """Load campaign from JSON template file."""
        template_path = os.path.join(
            "data/campaigns/templates",
            f"{campaign_id}.json"
        )

        with open(template_path, 'r') as f:
            data = json.load(f)

        # Parse checkpoints
        checkpoints = {}
        for cp_id, cp_data in data.get("checkpoints", {}).items():
            checkpoints[cp_id] = Checkpoint.from_dict(cp_id, cp_data)

        # Parse intro scenes
        intro_scenes = []
        if "intro_scenes" in data:
            for scene_data in data["intro_scenes"]:
                intro_scenes.append(IntroScene.from_dict(scene_data))

        return cls(
            campaign_id=data["id"],
            title=data["title"],
            description=data["description"],
            starting_checkpoint=data["starting_checkpoint"],
            checkpoints=checkpoints,
            category=data.get("category", "short"),
            estimated_duration=data.get("estimated_duration", "4-6 hours"),
            difficulty=data.get("difficulty", "intermediate"),
            intro_scenes=intro_scenes
        )

    @classmethod
    def list_available_campaigns(cls) -> List[Dict[str, str]]:
        """
        List all available campaign templates.
        Returns list of dicts with id, title, description.
        """
        templates_dir = "data/campaigns/templates"
        campaigns = []

        if not os.path.exists(templates_dir):
            return campaigns

        for filename in os.listdir(templates_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(templates_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        campaigns.append({
                            "id": data.get("id", ""),
                            "title": data.get("title", ""),
                            "description": data.get("description", ""),
                            "category": data.get("category", "short"),
                            "estimated_duration": data.get("estimated_duration", "4-6 hours"),
                            "difficulty": data.get("difficulty", "intermediate")
                        })
                except Exception:
                    continue

        return campaigns

    def to_dict(self) -> dict:
        """Convert campaign to dictionary."""
        return {
            "id": self.campaign_id,
            "title": self.title,
            "description": self.description,
            "starting_checkpoint": self.starting_checkpoint,
            "checkpoints": {
                cp_id: cp.to_dict()
                for cp_id, cp in self.checkpoints.items()
            }
        }
