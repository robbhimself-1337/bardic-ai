import json
import os
from typing import Dict, List, Optional


class Checkpoint:
    """Represents a story checkpoint/node in the campaign."""

    def __init__(
        self,
        checkpoint_id: str,
        description: str,
        npcs: Optional[List[str]] = None,
        items_available: Optional[List[str]] = None,
        enemies: Optional[List[str]] = None,
        next_checkpoints: Optional[List[str]] = None,
        auto_quests: Optional[List[Dict]] = None
    ):
        self.checkpoint_id = checkpoint_id
        self.description = description
        self.npcs = npcs if npcs is not None else []
        self.items_available = items_available if items_available is not None else []
        self.enemies = enemies if enemies is not None else []
        self.next_checkpoints = next_checkpoints if next_checkpoints is not None else []
        self.auto_quests = auto_quests if auto_quests is not None else []

    def to_dict(self) -> dict:
        """Convert checkpoint to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "description": self.description,
            "npcs": self.npcs,
            "items_available": self.items_available,
            "enemies": self.enemies,
            "next_checkpoints": self.next_checkpoints,
            "auto_quests": self.auto_quests
        }

    @classmethod
    def from_dict(cls, checkpoint_id: str, data: dict) -> 'Checkpoint':
        """Create checkpoint from dictionary."""
        return cls(
            checkpoint_id=checkpoint_id,
            description=data.get("description", ""),
            npcs=data.get("npcs", []),
            items_available=data.get("items_available", []),
            enemies=data.get("enemies", []),
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
        checkpoints: Dict[str, Checkpoint]
    ):
        self.campaign_id = campaign_id
        self.title = title
        self.description = description
        self.starting_checkpoint = starting_checkpoint
        self.checkpoints = checkpoints

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

        return cls(
            campaign_id=data["id"],
            title=data["title"],
            description=data["description"],
            starting_checkpoint=data["starting_checkpoint"],
            checkpoints=checkpoints
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
                            "description": data.get("description", "")
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
