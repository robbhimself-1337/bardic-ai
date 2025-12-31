"""
Character Portrait Generation Service
Uses Stable Diffusion XL for high-quality fantasy character portraits.

SMART VRAM MANAGEMENT:
- Unloads Coqui TTS before generating (it reloads automatically when needed)
- Runs SDXL at full quality (1024x1536) 
- Unloads SDXL after generation to free VRAM for gameplay
"""
import torch
import gc
import os
import logging
import subprocess
from typing import Optional, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global pipeline instance (lazy loaded)
_pipeline = None
_model_loaded = False

# Output directory for generated images
IMAGE_OUTPUT_DIR = "static/images/characters"
os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)


def clear_gpu_memory():
    """Aggressively clear GPU memory."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        torch.cuda.ipc_collect()
    logger.info("GPU memory cleared")


def unload_other_models():
    """
    Attempt to free VRAM by unloading other models.
    Coqui TTS and other services will reload when needed.
    """
    try:
        # Try to unload Coqui TTS if it's loaded
        # The TTS model will reload automatically on next use
        import sys
        for module_name in list(sys.modules.keys()):
            if 'TTS' in module_name or 'coqui' in module_name.lower():
                try:
                    module = sys.modules[module_name]
                    if hasattr(module, 'synthesizer'):
                        del module.synthesizer
                    if hasattr(module, 'tts'):
                        del module.tts
                except:
                    pass
        
        # Tell Ollama to unload any models from VRAM
        try:
            subprocess.run(
                ['ollama', 'stop', 'qwen2.5:14b'],
                capture_output=True,
                timeout=5
            )
            logger.info("Ollama model unloaded")
        except:
            pass  # Ollama might not be running or model not loaded
        
        clear_gpu_memory()
        logger.info("Other models unloaded to free VRAM")
        
    except Exception as e:
        logger.warning(f"Could not unload other models: {e}")


def unload_pipeline():
    """Unload SDXL pipeline to free VRAM for gameplay."""
    global _pipeline, _model_loaded
    if _pipeline is not None:
        del _pipeline
        _pipeline = None
        _model_loaded = False
        clear_gpu_memory()
        logger.info("SDXL pipeline unloaded - VRAM freed for gameplay")


def get_pipeline(high_quality: bool = True):
    """
    Load the SDXL pipeline.
    
    Args:
        high_quality: If True, loads for full quality (no CPU offload).
                     If False, uses memory-saving settings.
    """
    global _pipeline, _model_loaded
    
    if _model_loaded and _pipeline is not None:
        return _pipeline
    
    try:
        from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler
        
        # Free up VRAM first
        unload_other_models()
        clear_gpu_memory()
        
        logger.info(f"Loading SDXL pipeline (high_quality={high_quality})...")
        
        model_id = "stabilityai/stable-diffusion-xl-base-1.0"
        
        _pipeline = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16",
        )
        
        _pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            _pipeline.scheduler.config
        )
        
        if high_quality:
            # Full quality - load entirely on GPU
            _pipeline = _pipeline.to("cuda")
            _pipeline.enable_attention_slicing(slice_size=1)
            logger.info("SDXL loaded in HIGH QUALITY mode (full GPU)")
        else:
            # Memory-saving mode
            _pipeline.enable_sequential_cpu_offload()
            _pipeline.enable_attention_slicing(slice_size="auto")
            _pipeline.enable_vae_slicing()
            _pipeline.enable_vae_tiling()
            logger.info("SDXL loaded in MEMORY-SAVING mode (CPU offload)")
        
        # Try xformers
        try:
            _pipeline.enable_xformers_memory_efficient_attention()
            logger.info("xformers enabled")
        except Exception:
            pass
        
        _model_loaded = True
        return _pipeline
        
    except Exception as e:
        logger.error(f"Failed to load SDXL pipeline: {e}")
        _model_loaded = False
        raise


def get_race_prompt_and_negative(race: str) -> Tuple[str, str]:
    """Get race-specific prompt details and negative prompt additions."""
    race_configs = {
        "Dragonborn": (
            "dragonborn, dragon head, reptilian snout, scales covering entire face and body, "
            "dragon eyes with slit pupils, no hair, lizardfolk, draconic humanoid",
            "human face, human skin, smooth skin, hair, elf ears, mammal"
        ),
        "Elf": (
            "elf, long pointed ears, elegant elven features, slender face, ethereal beauty",
            "round ears, human ears"
        ),
        "Dwarf": (
            "dwarf, short and stocky, thick braided beard, broad nose, sturdy dwarven features",
            "tall, slender, clean shaven, no beard"
        ),
        "Halfling": (
            "halfling, hobbit-like, small cheerful face, curly hair, youthful appearance",
            "tall, large, intimidating"
        ),
        "Human": (
            "human, realistic human features",
            ""
        ),
        "Half-Elf": (
            "half-elf, slightly pointed ears, blend of human and elven features, graceful",
            ""
        ),
        "Half-Orc": (
            "half-orc, prominent lower tusks, greenish gray skin, strong jaw, orcish features",
            "pretty, delicate, pink skin"
        ),
        "Tiefling": (
            "tiefling, curved horns on forehead, solid colored eyes, red or purple skin, "
            "infernal features, devilish",
            "human skin color, no horns, angel"
        ),
        "Gnome": (
            "gnome, small with large expressive eyes, big nose, wild hair",
            "tall, human sized"
        ),
        "Drow": (
            "drow, dark elf, obsidian black skin, stark white hair, pointed ears, red eyes",
            "pale skin, light skin, blonde hair"
        ),
        "Minotaur": (
            "minotaur, bull head, bovine face with snout, large horns, fur covered, beast-like",
            "human face, human head, no horns, smooth skin"
        ),
        "Catfolk": (
            "catfolk, tabaxi, feline face, cat nose, whiskers, fur covered, cat ears, slit pupils",
            "human face, human ears, no fur, no whiskers"
        ),
        "Darakhul": (
            "darakhul, intelligent ghoul, undead, gaunt skeletal features, sunken eyes, corpse-like",
            "alive, healthy skin, rosy cheeks"
        ),
        "Gearforged": (
            "gearforged, warforged, mechanical humanoid, clockwork body, metal plates, glowing eyes",
            "organic, flesh, skin, biological"
        ),
        "Alseid": (
            "alseid, deer centaur, deer-like features, small antlers, fawn ears, forest spirit",
            "human ears, no antlers"
        ),
        "Derro": (
            "derro, pale blue-gray skin, bulging eyes, wild unkempt hair, mad expression",
            "sane, calm, normal skin color"
        ),
        "Erina": (
            "erina, hedgehog humanoid, spines instead of hair, small cute face, button nose",
            "human hair, no spines"
        ),
        "Mushroomfolk": (
            "myconid, mushroom person, fungal humanoid, mushroom cap head, bioluminescent spots",
            "human head, hair, normal skin"
        ),
        "Satarre": (
            "satarre, alien humanoid, elongated bald skull, pale grayish skin, otherworldly",
            "normal skull shape, human proportions"
        ),
        "Shade": (
            "shade, shadow creature, semi-transparent dark form, ethereal shadowy figure, wispy",
            "solid, opaque, bright, colorful"
        ),
    }
    
    return race_configs.get(race, (race, ""))


def build_character_prompt(
    race: str,
    character_class: str,
    gender: str = "male",
    age: str = "adult",
    build: str = "average",
    hair: str = "",
    features: str = "",
    background: str = ""
) -> Tuple[str, str]:
    """Build optimized prompt and negative prompt for character portrait."""
    
    age_map = {
        "young": "young",
        "adult": "",
        "middle-aged": "middle-aged",
        "elderly": "elderly weathered"
    }
    age_desc = age_map.get(age, "")
    
    build_map = {
        "slim": "slim lean",
        "average": "",
        "athletic": "athletic fit",
        "muscular": "muscular powerful",
        "heavyset": "heavyset sturdy"
    }
    build_desc = build_map.get(build, "")
    
    race_positive, race_negative = get_race_prompt_and_negative(race)
    
    class_visuals = {
        "Barbarian": "tribal warrior, fur clothing, fierce expression, war paint",
        "Bard": "performer, colorful ornate clothing, charismatic smile",
        "Cleric": "holy symbol, religious vestments, divine glow",
        "Druid": "natural clothing, leaves and vines, wild appearance",
        "Fighter": "plate armor, battle-hardened veteran, scarred",
        "Monk": "simple robes, martial artist, disciplined calm",
        "Paladin": "shining plate armor, holy warrior, righteous",
        "Ranger": "leather armor, hooded cloak, woodland tracker",
        "Rogue": "hooded dark cloak, daggers, cunning eyes",
        "Sorcerer": "magical energy, flowing robes, arcane power",
        "Warlock": "dark magic, eldritch symbols, haunted eyes",
        "Wizard": "elaborate robes, arcane symbols, scholarly",
    }
    class_visual = class_visuals.get(character_class, character_class)
    
    # Build positive prompt - race and user customizations first for emphasis
    prompt_parts = [
        race_positive,
        f"{age_desc} {gender}".strip(),
    ]
    
    # Add user customizations early (they matter most!)
    hairless_races = ["Dragonborn", "Gearforged", "Mushroomfolk"]
    if hair and race not in hairless_races:
        prompt_parts.append(hair)  # e.g., "orange mohawk"
    if features:
        prompt_parts.append(features)  # e.g., "scar over left eye"
    
    # Then class and build
    prompt_parts.extend([
        character_class,
        build_desc,
        class_visual,
    ])
    
    # Quality boosters (kept short to avoid token limit)
    prompt_parts.extend([
        "single character portrait",
        "fantasy art",
        "detailed face",
    ])
    
    positive_prompt = ", ".join(filter(None, prompt_parts))
    
    # Build negative prompt
    negative_parts = [
        "multiple views", "comic panels", "reference sheet", "collage",
        "comic book style", "cartoon", "anime",
        "blurry", "low quality", "distorted", "extra limbs",
        "bad anatomy", "bad hands", "text", "watermark", "signature",
        "deformed", "ugly", "cropped", "worst quality", "amateur"
    ]
    
    if race_negative:
        negative_parts.insert(0, race_negative)
    
    negative_prompt = ", ".join(negative_parts)
    
    return positive_prompt, negative_prompt


def generate_character_portrait(
    race: str,
    character_class: str,
    gender: str = "male",
    age: str = "adult",
    build: str = "average",
    hair: str = "",
    features: str = "",
    background: str = "",
    character_name: str = "character",
    num_inference_steps: int = 35,
    guidance_scale: float = 7.5,
    high_quality: bool = True,
) -> Optional[str]:
    """
    Generate a character portrait and save it.
    
    Args:
        high_quality: If True, generates at 1024x1536. If False, 512x768.
    
    Returns the filename of the generated image, or None if generation fails.
    """
    try:
        # Try high quality first, fall back to low quality on OOM
        try:
            pipeline = get_pipeline(high_quality=high_quality)
            width, height = (768, 1024) if high_quality else (512, 768)
        except torch.cuda.OutOfMemoryError:
            logger.warning("OOM in high quality mode, falling back to memory-saving mode")
            unload_pipeline()
            clear_gpu_memory()
            pipeline = get_pipeline(high_quality=False)
            width, height = 512, 768
        
        # Build prompts
        prompt, negative_prompt = build_character_prompt(
            race=race,
            character_class=character_class,
            gender=gender,
            age=age,
            build=build,
            hair=hair,
            features=features,
            background=background
        )
        
        logger.info(f"Generating {width}x{height} portrait...")
        logger.info(f"Prompt: {prompt}")
        
        # Generate
        with torch.inference_mode():
            result = pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                width=width,
                height=height,
            )
        
        image = result.images[0]
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in character_name if c.isalnum() or c in "_ -").strip()
        if not safe_name:
            safe_name = "character"
        filename = f"{safe_name}_{timestamp}.png"
        filepath = os.path.join(IMAGE_OUTPUT_DIR, filename)
        
        image.save(filepath)
        logger.info(f"Portrait saved to: {filepath}")
        
        # IMPORTANT: Unload SDXL to free VRAM for gameplay!
        unload_pipeline()
        
        return filename
        
    except Exception as e:
        logger.error(f"Failed to generate portrait: {e}")
        unload_pipeline()
        clear_gpu_memory()
        return None


def get_prompt_preview(
    race: str,
    character_class: str,
    gender: str = "male",
    age: str = "adult",
    build: str = "average",
    hair: str = "",
    features: str = "",
    background: str = ""
) -> str:
    """Get a preview of the prompt without generating."""
    prompt, _ = build_character_prompt(
        race=race,
        character_class=character_class,
        gender=gender,
        age=age,
        build=build,
        hair=hair,
        features=features,
        background=background
    )
    return prompt
