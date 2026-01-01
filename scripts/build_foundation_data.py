#!/usr/bin/env python3
"""
D&D 5e Foundation Data Builder

Pulls data from the D&D 5e SRD API (https://www.dnd5eapi.co/api/2014)
and organizes it into local JSON files for game engine foundation.

Usage:
    python scripts/build_foundation_data.py
"""

import os
import json
import requests
import time
import logging
from pathlib import Path
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "https://www.dnd5eapi.co/api/2014"
REQUEST_DELAY = 0.1  # 100ms between requests to be respectful

# Output directory
FOUNDATION_DIR = Path("data/foundation")


class SRDDataFetcher:
    """Fetches and organizes D&D 5e SRD data."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Bardic-AI/1.0 (D&D Foundation Data Builder)'
        })

    def fetch_endpoint(self, endpoint: str) -> Dict[str, Any]:
        """Fetch data from an API endpoint with rate limiting."""
        # If endpoint already has full base URL path, use it as-is
        if endpoint.startswith('/api/'):
            url = f"https://www.dnd5eapi.co{endpoint}"
        else:
            url = f"{BASE_URL}{endpoint}"

        logger.info(f"Fetching: {url}")

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return {}

    def fetch_all_details(self, endpoint: str, item_name: str = "items") -> List[Dict[str, Any]]:
        """
        Fetch a list endpoint, then fetch full details for each item.

        Args:
            endpoint: API endpoint (e.g., "/monsters")
            item_name: Name for logging purposes

        Returns:
            List of full detail objects
        """
        logger.info(f"Fetching all {item_name}...")

        # Get the list
        list_data = self.fetch_endpoint(endpoint)
        if not list_data or "results" not in list_data:
            logger.warning(f"No results found for {endpoint}")
            return []

        results = list_data["results"]
        logger.info(f"Found {list_data['count']} {item_name}")

        # Fetch details for each item
        details = []
        for i, item in enumerate(results, 1):
            logger.info(f"  [{i}/{len(results)}] Fetching {item['name']}...")
            detail = self.fetch_endpoint(item['url'])
            if detail:
                details.append(detail)

        return details

    def save_json(self, data: Any, filepath: Path):
        """Save data to JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved: {filepath} ({len(json.dumps(data))} bytes)")

    def fetch_rules(self):
        """Fetch all rules and rule sections."""
        logger.info("=" * 60)
        logger.info("FETCHING RULES")
        logger.info("=" * 60)

        rules_dir = FOUNDATION_DIR / "rules"

        # Get all rules
        rules_list = self.fetch_endpoint("/rules")
        if rules_list and "results" in rules_list:
            for rule in rules_list["results"]:
                rule_detail = self.fetch_endpoint(rule["url"])
                if rule_detail:
                    # Save each rule as a separate file
                    filename = f"{rule['index']}.json"
                    self.save_json(rule_detail, rules_dir / filename)

        # Get all rule sections
        sections_list = self.fetch_endpoint("/rule-sections")
        if sections_list and "results" in sections_list:
            all_sections = []
            for section in sections_list["results"]:
                section_detail = self.fetch_endpoint(section["url"])
                if section_detail:
                    all_sections.append(section_detail)

            # Save all sections together
            self.save_json(all_sections, rules_dir / "rule_sections.json")

        # Get conditions (important for combat)
        conditions = self.fetch_all_details("/conditions", "conditions")
        self.save_json(conditions, rules_dir / "conditions.json")

    def fetch_mechanics(self):
        """Fetch core game mechanics data."""
        logger.info("=" * 60)
        logger.info("FETCHING MECHANICS")
        logger.info("=" * 60)

        mechanics_dir = FOUNDATION_DIR / "mechanics"

        # Ability scores
        ability_scores = self.fetch_all_details("/ability-scores", "ability scores")
        self.save_json(ability_scores, mechanics_dir / "ability_scores.json")

        # Skills
        skills = self.fetch_all_details("/skills", "skills")
        self.save_json(skills, mechanics_dir / "skills.json")

        # Damage types
        damage_types = self.fetch_all_details("/damage-types", "damage types")
        self.save_json(damage_types, mechanics_dir / "damage_types.json")

        # Proficiencies
        proficiencies = self.fetch_all_details("/proficiencies", "proficiencies")
        self.save_json(proficiencies, mechanics_dir / "proficiencies.json")

    def fetch_entities(self):
        """Fetch character/NPC entities."""
        logger.info("=" * 60)
        logger.info("FETCHING ENTITIES")
        logger.info("=" * 60)

        entities_dir = FOUNDATION_DIR / "entities"

        # Classes
        classes = self.fetch_all_details("/classes", "classes")
        self.save_json(classes, entities_dir / "classes.json")

        # Races
        races = self.fetch_all_details("/races", "races")
        self.save_json(races, entities_dir / "races.json")

        # Backgrounds
        backgrounds = self.fetch_all_details("/backgrounds", "backgrounds")
        self.save_json(backgrounds, entities_dir / "backgrounds.json")

        # Monsters (this is the big one!)
        logger.info("Fetching monsters (this will take a while)...")
        monsters = self.fetch_all_details("/monsters", "monsters")
        self.save_json(monsters, entities_dir / "monsters.json")

    def fetch_items(self):
        """Fetch all equipment and items."""
        logger.info("=" * 60)
        logger.info("FETCHING ITEMS")
        logger.info("=" * 60)

        items_dir = FOUNDATION_DIR / "items"

        # Get all equipment first
        all_equipment = self.fetch_all_details("/equipment", "equipment")

        # Categorize equipment
        weapons = []
        armor = []
        gear = []

        for item in all_equipment:
            category = item.get("equipment_category", {}).get("index", "")

            if category == "weapon":
                weapons.append(item)
            elif category == "armor":
                armor.append(item)
            else:
                gear.append(item)

        self.save_json(weapons, items_dir / "weapons.json")
        self.save_json(armor, items_dir / "armor.json")
        self.save_json(gear, items_dir / "equipment.json")

        # Magic items
        magic_items = self.fetch_all_details("/magic-items", "magic items")
        self.save_json(magic_items, items_dir / "magic_items.json")

    def fetch_spells(self):
        """Fetch all spells."""
        logger.info("=" * 60)
        logger.info("FETCHING SPELLS")
        logger.info("=" * 60)

        spells_dir = FOUNDATION_DIR / "spells"

        spells = self.fetch_all_details("/spells", "spells")
        self.save_json(spells, spells_dir / "spells.json")

    def build_all(self):
        """Build complete foundation data."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("D&D 5e FOUNDATION DATA BUILDER")
        logger.info("=" * 60)
        logger.info("")

        start_time = time.time()

        try:
            # Create directory structure
            logger.info("Creating directory structure...")
            (FOUNDATION_DIR / "rules").mkdir(parents=True, exist_ok=True)
            (FOUNDATION_DIR / "mechanics").mkdir(parents=True, exist_ok=True)
            (FOUNDATION_DIR / "entities").mkdir(parents=True, exist_ok=True)
            (FOUNDATION_DIR / "items").mkdir(parents=True, exist_ok=True)
            (FOUNDATION_DIR / "spells").mkdir(parents=True, exist_ok=True)

            # Fetch all data
            self.fetch_rules()
            self.fetch_mechanics()
            self.fetch_entities()
            self.fetch_items()
            self.fetch_spells()

            elapsed = time.time() - start_time
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"COMPLETE! Built foundation data in {elapsed:.1f} seconds")
            logger.info(f"Data saved to: {FOUNDATION_DIR.absolute()}")
            logger.info("=" * 60)

        except KeyboardInterrupt:
            logger.warning("\n\nInterrupted by user. Partial data may be saved.")
        except Exception as e:
            logger.error(f"\n\nFatal error: {e}")
            raise


def main():
    """Main entry point."""
    fetcher = SRDDataFetcher()
    fetcher.build_all()


if __name__ == "__main__":
    main()
