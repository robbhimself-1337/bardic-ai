import requests
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.open5e.com/v1/"
CACHE_DIR = "data/cache"
CACHE_DURATION = timedelta(days=7)  # Refresh cache after 7 days


class Open5eClient:
    """Client for fetching D&D 5e data from Open5e API with caching."""

    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _get_cache_path(self, endpoint: str) -> str:
        """Get cache file path for endpoint."""
        filename = endpoint.replace("/", "_") + ".json"
        return os.path.join(CACHE_DIR, filename)

    def _is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache file exists and is not expired."""
        if not os.path.exists(cache_path):
            return False

        # Check modification time
        mod_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        return datetime.now() - mod_time < CACHE_DURATION

    def _load_cache(self, endpoint: str) -> Optional[List[Dict]]:
        """Load data from cache if valid."""
        cache_path = self._get_cache_path(endpoint)

        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {endpoint} from cache")
                    return data
            except Exception as e:
                logger.error(f"Error loading cache for {endpoint}: {e}")

        return None

    def _save_cache(self, endpoint: str, data: List[Dict]):
        """Save data to cache."""
        cache_path = self._get_cache_path(endpoint)

        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
                logger.info(f"Saved {endpoint} to cache")
        except Exception as e:
            logger.error(f"Error saving cache for {endpoint}: {e}")

    def _fetch_paginated(self, endpoint: str) -> List[Dict]:
        """
        Fetch all pages from a paginated API endpoint.
        Open5e returns 50 results per page.
        """
        all_results = []
        url = BASE_URL + endpoint

        while url:
            try:
                logger.info(f"Fetching: {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                data = response.json()
                all_results.extend(data.get('results', []))

                # Check for next page
                url = data.get('next')

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching {endpoint}: {e}")
                break

        return all_results

    def _get_data(self, endpoint: str, force_refresh: bool = False) -> List[Dict]:
        """
        Get data from cache or API.
        Falls back to cache if API is unavailable.
        """
        # Try cache first (unless force refresh)
        if not force_refresh:
            cached_data = self._load_cache(endpoint)
            if cached_data is not None:
                return cached_data

        # Fetch from API
        data = self._fetch_paginated(endpoint)

        if data:
            # Save to cache
            self._save_cache(endpoint, data)
            return data

        # Fallback to cache even if expired
        logger.warning(f"API unavailable for {endpoint}, using old cache")
        cache_path = self._get_cache_path(endpoint)
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        return []

    def get_races(self, force_refresh: bool = False) -> List[Dict]:
        """Get all playable races."""
        return self._get_data("races", force_refresh)

    def get_classes(self, force_refresh: bool = False) -> List[Dict]:
        """Get all character classes."""
        return self._get_data("classes", force_refresh)

    def get_backgrounds(self, force_refresh: bool = False) -> List[Dict]:
        """Get all character backgrounds."""
        return self._get_data("backgrounds", force_refresh)

    def get_spells(self, force_refresh: bool = False) -> List[Dict]:
        """Get all spells."""
        return self._get_data("spells", force_refresh)

    def get_weapons(self, force_refresh: bool = False) -> List[Dict]:
        """Get all weapons."""
        return self._get_data("weapons", force_refresh)

    def get_armor(self, force_refresh: bool = False) -> List[Dict]:
        """Get all armor."""
        return self._get_data("armor", force_refresh)

    def get_magic_items(self, force_refresh: bool = False) -> List[Dict]:
        """Get all magic items."""
        return self._get_data("magicitems", force_refresh)

    def get_spells_by_class(self, class_name: str) -> List[Dict]:
        """Get spells filtered by class spell list."""
        all_spells = self.get_spells()

        # Filter spells that include this class in their dnd_class field
        class_spells = []
        for spell in all_spells:
            dnd_class = spell.get('dnd_class', '')
            if class_name.lower() in dnd_class.lower():
                class_spells.append(spell)

        return class_spells

    def get_spells_by_level(self, class_name: str, level: int) -> List[Dict]:
        """Get spells of specific level for a class."""
        class_spells = self.get_spells_by_class(class_name)
        return [s for s in class_spells if s.get('level_int') == level]

    def get_class_details(self, class_name: str) -> Optional[Dict]:
        """Get detailed information for a specific class."""
        classes = self.get_classes()
        for cls in classes:
            if cls.get('name', '').lower() == class_name.lower():
                return cls
        return None

    def get_race_details(self, race_name: str) -> Optional[Dict]:
        """Get detailed information for a specific race."""
        races = self.get_races()
        for race in races:
            if race.get('name', '').lower() == race_name.lower():
                return race
        return None

    def refresh_all_cache(self):
        """Refresh all cached data from API."""
        logger.info("Refreshing all Open5e cache...")

        endpoints = [
            "races",
            "classes",
            "backgrounds",
            "spells",
            "weapons",
            "armor",
            "magicitems"
        ]

        for endpoint in endpoints:
            self._get_data(endpoint, force_refresh=True)

        logger.info("Cache refresh complete!")

    def get_cache_status(self) -> Dict:
        """Get information about cached data."""
        status = {}

        endpoints = [
            "races",
            "classes",
            "backgrounds",
            "spells",
            "weapons",
            "armor",
            "magicitems"
        ]

        for endpoint in endpoints:
            cache_path = self._get_cache_path(endpoint)
            if os.path.exists(cache_path):
                mod_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
                age = datetime.now() - mod_time

                # Count items
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                    count = len(data)

                status[endpoint] = {
                    "cached": True,
                    "last_updated": mod_time.isoformat(),
                    "age_hours": int(age.total_seconds() / 3600),
                    "count": count,
                    "valid": self._is_cache_valid(cache_path)
                }
            else:
                status[endpoint] = {
                    "cached": False,
                    "last_updated": None,
                    "age_hours": None,
                    "count": 0,
                    "valid": False
                }

        return status


# Global client instance
client = Open5eClient()


# Convenience functions
def get_races():
    return client.get_races()


def get_classes():
    return client.get_classes()


def get_backgrounds():
    return client.get_backgrounds()


def get_spells():
    return client.get_spells()


def get_weapons():
    return client.get_weapons()


def get_armor():
    return client.get_armor()


def get_magic_items():
    return client.get_magic_items()


def refresh_cache():
    client.refresh_all_cache()


def get_cache_status():
    return client.get_cache_status()
