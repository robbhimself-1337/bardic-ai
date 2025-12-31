import os
import logging
import uuid
import re
from TTS.api import TTS
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AUDIO_OUTPUT_DIR = "/tmp/bardic_audio"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

# Character limit for XTTS v2
MAX_CHARS = 240  # Slightly under 250 to be safe

# Load XTTS v2 model for voice cloning
logger.info("Loading Coqui TTS XTTS v2 model...")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
logger.info("TTS model loaded successfully on CUDA")


def split_text_into_chunks(text: str, max_chars: int = MAX_CHARS) -> List[str]:
    """
    Split text into chunks that fit within the character limit.
    Tries to split at sentence boundaries, then clause boundaries, then word boundaries.
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    remaining = text.strip()
    
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        
        # Find the best split point within max_chars
        chunk = remaining[:max_chars]
        
        # Try to split at sentence boundary (. ! ?)
        split_point = -1
        for punct in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
            idx = chunk.rfind(punct)
            if idx > split_point:
                split_point = idx + 1  # Include the punctuation
        
        # If no sentence boundary, try clause boundary (, ; :)
        if split_point < max_chars // 2:  # Only if we'd lose too much text
            for punct in [', ', '; ', ': ', '— ', ' - ']:
                idx = chunk.rfind(punct)
                if idx > split_point:
                    split_point = idx + len(punct) - 1
        
        # If still no good split, try word boundary
        if split_point < max_chars // 2:
            split_point = chunk.rfind(' ')
        
        # Last resort: hard split
        if split_point <= 0:
            split_point = max_chars
        
        chunks.append(remaining[:split_point].strip())
        remaining = remaining[split_point:].strip()
    
    return chunks


def text_to_speech(text: str, voice_sample: str = "voice_samples/dm_narrator.wav", speed: float = 1.0) -> Optional[str]:
    """
    Convert text to speech using voice cloning with XTTS v2.
    For short text, returns a single filename.
    For long text, generates multiple files and returns a comma-separated list.

    Args:
        text: Text to convert to speech
        voice_sample: Path to WAV file for voice cloning
        speed: Speech speed multiplier (0.5=slow, 1.0=normal, 1.5=fast)

    Returns:
        str: Filename(s) of generated audio (comma-separated if multiple)
    """
    try:
        # Check if voice sample exists
        if not os.path.exists(voice_sample):
            logger.warning(f"Voice sample not found: {voice_sample}")
            raise FileNotFoundError(f"Voice sample not found: {voice_sample}")

        # Clean up text
        text = text.strip()
        if not text:
            return None
        
        # Split into chunks if needed
        chunks = split_text_into_chunks(text)
        logger.info(f"Text split into {len(chunks)} chunk(s)")
        
        filenames = []
        
        for i, chunk in enumerate(chunks):
            filename = f"{uuid.uuid4()}.wav"
            output_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
            
            logger.info(f"Generating chunk {i+1}/{len(chunks)}: {chunk[:50]}...")
            
            tts.tts_to_file(
                text=chunk,
                speaker_wav=voice_sample,
                language="en",
                file_path=output_path,
                speed=speed
            )
            
            filenames.append(filename)
            logger.info(f"Chunk {i+1} saved to {output_path}")
        
        # Return comma-separated list of filenames
        return ",".join(filenames)
        
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise


def text_to_speech_single(text: str, voice_sample: str = "voice_samples/dm_narrator.wav", speed: float = 1.0) -> Optional[str]:
    """
    Generate speech for a single chunk (under 250 chars).
    Use this for pre-generating individual segments.
    """
    try:
        if not os.path.exists(voice_sample):
            raise FileNotFoundError(f"Voice sample not found: {voice_sample}")
        
        if len(text) > MAX_CHARS:
            logger.warning(f"Text too long ({len(text)} chars), truncating to {MAX_CHARS}")
            text = text[:MAX_CHARS]
        
        filename = f"{uuid.uuid4()}.wav"
        output_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
        
        tts.tts_to_file(
            text=text,
            speaker_wav=voice_sample,
            language="en",
            file_path=output_path,
            speed=speed
        )
        
        return filename
        
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        return None
