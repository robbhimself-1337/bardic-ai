import os
import logging
import uuid
from TTS.api import TTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AUDIO_OUTPUT_DIR = "/tmp/bardic_audio"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

# Load XTTS v2 model for voice cloning
logger.info("Loading Coqui TTS XTTS v2 model...")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
logger.info("TTS model loaded successfully on CUDA")

def text_to_speech(text, voice_sample="voice_samples/dm_narrator.wav", speed=1.2):
    """
    Convert text to speech using voice cloning with XTTS v2.

    Args:
        text: Text to convert to speech
        voice_sample: Path to WAV file for voice cloning (default: voice_samples/dm_narrator.wav)
        speed: Speech speed multiplier (0.5=slow, 1.0=normal, 1.5=fast, default=1.2)

    Returns:
        str: Filename of generated audio
    """
    try:
        # Generate unique filename
        filename = f"{uuid.uuid4()}.wav"
        output_path = os.path.join(AUDIO_OUTPUT_DIR, filename)

        logger.info(f"Generating speech for: {text[:50]}...")
        logger.info(f"Using voice sample: {voice_sample}, speed: {speed}")

        # Check if voice sample exists
        if not os.path.exists(voice_sample):
            logger.warning(f"Voice sample not found: {voice_sample}")
            logger.warning("Please record a voice sample using: python record_voice_sample.py")
            raise FileNotFoundError(f"Voice sample not found: {voice_sample}")

        # Voice cloning with XTTS v2
        tts.tts_to_file(
            text=text,
            speaker_wav=voice_sample,
            language="en",
            file_path=output_path,
            speed=speed
        )

        logger.info(f"Audio saved to {output_path}")
        return filename
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise