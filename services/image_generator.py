"""
Image generation service for campaign visuals.
Generates and caches NPC portraits, scene images, etc. using OpenAI DALL-E 3.
"""
import os
import logging
import hashlib
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = "static/images/generated"
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)

# DM portrait path (you should add a default DM image here)
DM_PORTRAIT_PATH = "/static/images/dm/dm_portrait.png"


def get_cache_path(prompt: str, category: str = "misc") -> str:
    """Generate a cache file path based on prompt hash."""
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:12]
    cache_dir = os.path.join(IMAGE_CACHE_DIR, category)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{prompt_hash}.png")


def generate_image(
    prompt: str,
    category: str = "misc",
    size: str = "1024x1024",
    use_cache: bool = True
) -> Optional[str]:
    """
    Generate an image using DALL-E 3.
    Returns the relative URL path to the image.

    Args:
        prompt: The image generation prompt
        category: Subdirectory for caching (npc, scene, enemy, etc.)
        size: Image size (1024x1024, 1792x1024, 1024x1792)
        use_cache: Whether to use cached images if available
    """
    cache_path = get_cache_path(prompt, category)
    relative_url = "/" + cache_path.replace("\\", "/")

    # Check cache first
    if use_cache and os.path.exists(cache_path):
        logger.info(f"Using cached image: {cache_path}")
        return relative_url

    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("No OpenAI API key found")
            return None

        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        logger.info(f"Generating image for: {prompt[:50]}...")

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality="hd",
            n=1,
        )

        image_url = response.data[0].url

        # Download and save
        img_response = requests.get(image_url)
        img_response.raise_for_status()

        with open(cache_path, 'wb') as f:
            f.write(img_response.content)

        logger.info(f"Image saved to: {cache_path}")
        return relative_url

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return None


def generate_npc_portrait(npc_name: str, prompt: str) -> Optional[str]:
    """Generate an NPC portrait."""
    full_prompt = f"{prompt}. Fantasy portrait, detailed face, dramatic lighting, D&D character art style, head and shoulders, painterly style."
    return generate_image(full_prompt, category="npcs", size="1024x1024")


def generate_scene(checkpoint_name: str, prompt: str) -> Optional[str]:
    """Generate a scene/location image."""
    full_prompt = f"{prompt}. Wide shot, fantasy environment, dramatic lighting, D&D art style, highly detailed, epic landscape."
    return generate_image(full_prompt, category="scenes", size="1792x1024")


def generate_enemy_portrait(enemy_type: str, prompt: str = None) -> Optional[str]:
    """Generate an enemy portrait."""
    if not prompt:
        prompt = f"A menacing {enemy_type}, fantasy monster"
    full_prompt = f"{prompt}. Fantasy creature portrait, threatening pose, dramatic lighting, D&D monster art style, detailed."
    return generate_image(full_prompt, category="enemies", size="1024x1024")


def get_dm_portrait() -> str:
    """Get the DM portrait path."""
    # Check if custom DM portrait exists
    if os.path.exists("static/images/dm/dm_portrait.png"):
        return DM_PORTRAIT_PATH

    # Fallback to a placeholder or generate one
    return "/static/images/dm/dm_default.png"


def generate_intro_scene(title: str, prompt: str) -> Optional[str]:
    """Generate an intro scene image."""
    full_prompt = f"{prompt}. Epic fantasy scene, cinematic composition, dramatic lighting, highly detailed, D&D art style."
    return generate_image(full_prompt, category="intro", size="1792x1024")
