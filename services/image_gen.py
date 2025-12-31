"""
Character Portrait Generation Service
Supports multiple backends:
- OpenAI DALL-E 3 (primary - best quality and prompt adherence)
- Local SDXL (fallback - free but lower quality)

API keys are loaded from environment variables for security.
"""
import os
import logging
import requests
from typing import Optional, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output directory for generated images
IMAGE_OUTPUT_DIR = "static/images/characters"
os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)

# Check for API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


def get_provider() -> str:
    """Determine which image generation provider to use."""
    if OPENAI_API_KEY:
        return "openai"
    else:
        return "local"


def get_race_details(race: str) -> Tuple[str, str]:
    """
    Get race-specific description for the prompt.
    Returns (description, style_notes)
    """
    race_details = {
        "Dragonborn": (
            "a dragonborn with a full dragon head, reptilian snout, scales covering the entire face and body, "
            "dragon eyes with slit pupils, no hair",
            "draconic, lizard-like, NOT human"
        ),
        "Elf": (
            "an elf with long pointed ears, elegant refined features, slender face, ethereal beauty",
            "graceful, otherworldly"
        ),
        "Dwarf": (
            "a dwarf with a stocky build, magnificent thick beard, broad nose, sturdy features",
            "stout, powerful"
        ),
        "Halfling": (
            "a halfling with a small stature, youthful cheerful face, curly hair",
            "friendly, warm"
        ),
        "Human": (
            "a human with realistic features",
            ""
        ),
        "Half-Elf": (
            "a half-elf with slightly pointed ears, a blend of human and elven features",
            "graceful yet approachable"
        ),
        "Half-Orc": (
            "a half-orc with prominent lower tusks protruding from the mouth, greenish-gray skin, "
            "strong heavy jaw, brutish orcish features",
            "intimidating, powerful"
        ),
        "Tiefling": (
            "a tiefling with curved horns on the forehead, solid-colored eyes (no whites), "
            "reddish or purple skin, infernal demonic features, possibly a pointed tail visible",
            "devilish, exotic"
        ),
        "Gnome": (
            "a gnome with a small stature, large expressive eyes, prominent nose, wild untamed hair",
            "curious, eccentric"
        ),
        "Drow": (
            "a drow (dark elf) with obsidian black skin, stark white hair, pointed ears, red or purple eyes",
            "mysterious, elegant"
        ),
        "Minotaur": (
            "a minotaur with a full bull head, bovine face with a snout, large curved horns, fur-covered body",
            "bestial, powerful, NOT human face"
        ),
        "Catfolk": (
            "a catfolk/tabaxi with a feline face, cat nose, whiskers, fur-covered body, cat ears, slit pupils",
            "graceful, predatory"
        ),
        "Darakhul": (
            "a darakhul (intelligent ghoul) with undead rotting features, gaunt skeletal face, sunken eyes",
            "corpse-like, unsettling"
        ),
        "Gearforged": (
            "a gearforged/warforged with a fully mechanical body, clockwork parts, brass and copper plates, "
            "glowing eyes, visible gears, NO organic parts",
            "steampunk, robotic"
        ),
        "Alseid": (
            "an alseid with deer-like features, small antlers, fawn-like ears, gentle forest spirit appearance",
            "nature-touched, serene"
        ),
        "Derro": (
            "a derro with pale blue-gray skin, bulging wild eyes, unkempt hair, mad unsettling expression",
            "insane, creepy"
        ),
        "Erina": (
            "an erina (hedgehog humanoid) with brown quills/spines covering the head instead of hair, "
            "small mammal face, black button nose, small round ears, whiskers",
            "cute but wild, woodland creature"
        ),
        "Mushroomfolk": (
            "a myconid/mushroom person with a large mushroom cap as a head, fungal body, "
            "possibly bioluminescent spots, alien plant-like creature",
            "strange, otherworldly"
        ),
        "Satarre": (
            "a satarre with an elongated bald skull, pale grayish skin, sunken alien features, "
            "otherworldly proportions",
            "xenomorph-like, unsettling"
        ),
        "Shade": (
            "a shade made of living shadow, semi-transparent dark smoky form, ethereal wispy edges, "
            "glowing eyes emerging from darkness",
            "ghostly, incorporeal"
        ),
    }
    
    return race_details.get(race, (f"a {race}", ""))


def get_class_description(character_class: str) -> str:
    """Get class-specific visual description."""
    class_visuals = {
        "Barbarian": "wearing tribal furs and leather, fierce warrior with war paint, battle-ready",
        "Bard": "in colorful performer's clothing, charismatic expression, possibly with an instrument",
        "Cleric": "wearing religious vestments, holy symbol visible, divine aura",
        "Druid": "in natural clothing with leaves and vines, wild untamed appearance",
        "Fighter": "in well-worn armor, battle-scarred veteran, weapons visible",
        "Monk": "in simple robes, disciplined martial artist, serene but deadly",
        "Paladin": "in shining plate armor, holy warrior, righteous noble bearing",
        "Ranger": "in practical leather armor, hooded cloak, rugged wilderness tracker",
        "Rogue": "in dark hooded cloak, daggers visible, cunning shadowy look",
        "Sorcerer": "with magical energy crackling around them, flowing robes, wild magic aura",
        "Warlock": "with eldritch symbols, dark mysterious presence, haunted eyes",
        "Wizard": "in elaborate robes with arcane symbols, scholarly, wise appearance",
    }
    
    return class_visuals.get(character_class, f"as a {character_class}")


def build_dalle_prompt(
    race: str,
    character_class: str,
    gender: str = "male",
    age: str = "adult",
    build: str = "average",
    skin_tone: str = "fair",
    expression: str = "neutral",
    eye_color: str = "brown",
    hair_style: str = "short",
    hair_color: str = "brown",
    facial_hair: str = "none",
    features: list = None,
    hair: str = "",  # Legacy fallback
) -> str:
    """
    Build a rich, detailed natural language prompt optimized for DALL-E 3.
    DALL-E 3 prefers descriptive sentences over comma-separated keywords.
    """
    if features is None:
        features = []

    # Age description
    age_desc = {
        "young": "young",
        "adult": "",
        "middle-aged": "middle-aged",
        "elderly": "elderly"
    }.get(age, "")

    # Build description
    build_desc = {
        "slim": "with a slim lean build",
        "average": "",
        "athletic": "with an athletic build",
        "muscular": "with a powerful muscular build",
        "heavyset": "with a heavyset sturdy build"
    }.get(build, "")

    # Get race and class details
    race_desc, race_style = get_race_details(race)
    class_desc = get_class_description(character_class)

    # Build the prompt as natural sentences
    prompt_parts = [
        f"A breathtaking fantasy character portrait of {race_desc}.",
        f"This {age_desc} {gender} {character_class} is {class_desc}.".replace("  ", " "),
    ]

    # Physical appearance details
    appearance_details = []

    if build_desc:
        appearance_details.append(build_desc)

    # Skin tone
    appearance_details.append(f"{skin_tone} skin tone")

    # Hair details (use structured fields if available, fallback to legacy)
    if hair_style and hair_style != "bald":
        hair_desc = f"{hair_color} {hair_style} hair"
        appearance_details.append(hair_desc)
    elif hair_style == "bald":
        appearance_details.append("bald head")
    elif hair:  # Legacy fallback
        appearance_details.append(f"hair: {hair}")

    # Facial hair
    if facial_hair and facial_hair != "none" and gender != "female":
        appearance_details.append(f"with {facial_hair}")

    # Eye color
    appearance_details.append(f"{eye_color} eyes")

    # Expression
    appearance_details.append(f"{expression} expression")

    if appearance_details:
        prompt_parts.append(f"They have {', '.join(appearance_details)}.")

    # Distinguishing features
    if features:
        features_str = ", ".join(features)
        prompt_parts.append(f"Notable features: {features_str}.")

    # Quality boosters and style guidance
    prompt_parts.append(
        "Epic masterwork quality, award-winning fantasy art, highly detailed, 8k resolution. "
        "Digital fantasy art style, dramatic cinematic lighting, detailed face, "
        "D&D character portrait, painterly style, single character, head and shoulders portrait."
    )

    if race_style:
        prompt_parts.append(f"Important: {race_style}.")

    return " ".join(prompt_parts)


def generate_with_dalle(
    prompt: str,
    character_name: str = "character"
) -> Optional[str]:
    """Generate image using OpenAI DALL-E 3 API."""
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        logger.info(f"Generating with DALL-E 3: {prompt[:100]}...")
        
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1792",  # Portrait orientation
            quality="hd",      # High quality
            n=1,
        )
        
        image_url = response.data[0].url
        
        # Download the image
        img_response = requests.get(image_url)
        img_response.raise_for_status()
        
        # Save it
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in character_name if c.isalnum() or c in "_ -").strip()
        if not safe_name:
            safe_name = "character"
        filename = f"{safe_name}_{timestamp}.png"
        filepath = os.path.join(IMAGE_OUTPUT_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(img_response.content)
        
        logger.info(f"DALL-E 3 portrait saved to: {filepath}")
        return filename
        
    except Exception as e:
        logger.error(f"DALL-E 3 generation failed: {e}")
        return None


def generate_with_local_sdxl(
    race: str,
    character_class: str,
    gender: str,
    age: str,
    build: str,
    skin_tone: str,
    expression: str,
    eye_color: str,
    hair_style: str,
    hair_color: str,
    facial_hair: str,
    features: list,
    character_name: str
) -> Optional[str]:
    """Fallback to local SDXL generation."""
    try:
        # Import the local generation function
        from services.image_gen_local import generate_character_portrait as local_generate

        # Build combined hair string for legacy compatibility
        hair = f"{hair_color} {hair_style}" if hair_style != "bald" else "bald"
        features_str = ", ".join(features) if features else ""

        return local_generate(
            race=race,
            character_class=character_class,
            gender=gender,
            age=age,
            build=build,
            hair=hair,
            features=features_str,
            character_name=character_name,
        )
    except Exception as e:
        logger.error(f"Local SDXL generation failed: {e}")
        return None


def generate_character_portrait(
    race: str,
    character_class: str,
    gender: str = "male",
    age: str = "adult",
    build: str = "average",
    skin_tone: str = "fair",
    expression: str = "neutral",
    eye_color: str = "brown",
    hair_style: str = "short",
    hair_color: str = "brown",
    facial_hair: str = "none",
    features: list = None,
    background: str = "",
    character_name: str = "character",
    hair: str = "",  # Legacy fallback
    **kwargs  # Accept extra args for compatibility
) -> Optional[str]:
    """
    Generate a character portrait using the best available method.

    Priority:
    1. DALL-E 3 (if API key available) - best quality
    2. Local SDXL (fallback) - free but lower quality
    """
    if features is None:
        features = []

    provider = get_provider()
    logger.info(f"Using image provider: {provider}")

    if provider == "openai":
        # Build DALL-E optimized prompt with all new detailed parameters
        prompt = build_dalle_prompt(
            race=race,
            character_class=character_class,
            gender=gender,
            age=age,
            build=build,
            skin_tone=skin_tone,
            expression=expression,
            eye_color=eye_color,
            hair_style=hair_style,
            hair_color=hair_color,
            facial_hair=facial_hair,
            features=features,
            hair=hair,
        )

        logger.info(f"DALL-E 3 prompt: {prompt}")

        result = generate_with_dalle(prompt, character_name)

        if result:
            return result
        else:
            logger.warning("DALL-E failed, falling back to local SDXL")
            provider = "local"

    if provider == "local":
        return generate_with_local_sdxl(
            race=race,
            character_class=character_class,
            gender=gender,
            age=age,
            build=build,
            skin_tone=skin_tone,
            expression=expression,
            eye_color=eye_color,
            hair_style=hair_style,
            hair_color=hair_color,
            facial_hair=facial_hair,
            features=features,
            character_name=character_name,
        )

    return None


def get_prompt_preview(
    race: str,
    character_class: str,
    gender: str = "male",
    age: str = "adult",
    build: str = "average",
    skin_tone: str = "fair",
    expression: str = "neutral",
    eye_color: str = "brown",
    hair_style: str = "short",
    hair_color: str = "brown",
    facial_hair: str = "none",
    features: list = None,
    background: str = "",
    hair: str = ""
) -> str:
    """Get a preview of the prompt that will be used."""
    if features is None:
        features = []

    return build_dalle_prompt(
        race=race,
        character_class=character_class,
        gender=gender,
        age=age,
        build=build,
        skin_tone=skin_tone,
        expression=expression,
        eye_color=eye_color,
        hair_style=hair_style,
        hair_color=hair_color,
        facial_hair=facial_hair,
        features=features,
        hair=hair,
    )
