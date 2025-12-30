import os
import logging
import uuid
from TTS.api import TTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output directory for audio files
AUDIO_OUTPUT_DIR = "/tmp/bardic_ai_audio"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

# Load XTTS v2 model once on module import
logger.info("Loading Coqui TTS XTTS v2 model...")
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
logger.info("TTS model loaded successfully on CUDA")


def text_to_speech(text, speaker_wav=None):
    """
    Convert text to speech using Coqui TTS XTTS v2.

    Args:
        text (str): The text to convert to speech
        speaker_wav (str, optional): Path to a WAV file for voice cloning.
                                     If None, uses default voice.

    Returns:
        str: Path to the generated audio file
    """
    try:
        # Generate unique filename
        audio_filename = f"{uuid.uuid4()}.wav"
        audio_path = os.path.join(AUDIO_OUTPUT_DIR, audio_filename)

        logger.info(f"Generating TTS for text: {text[:50]}...")

        if speaker_wav:
            # Voice cloning mode
            tts.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language="en",
                file_path=audio_path
            )
        else:
            # Use default speaker from the model
            # XTTS v2 has built-in speakers we can use
            tts.tts_to_file(
                text=text,
                language="en",
                file_path=audio_path
            )

        logger.info(f"TTS audio generated: {audio_path}")
        return audio_filename

    except Exception as e:
        logger.error(f"Error generating TTS: {str(e)}")
        raise


def cleanup_old_audio_files(max_age_seconds=3600):
    """
    Remove audio files older than max_age_seconds.

    Args:
        max_age_seconds (int): Maximum age of files to keep in seconds (default: 1 hour)
    """
    try:
        import time
        current_time = time.time()

        for filename in os.listdir(AUDIO_OUTPUT_DIR):
            file_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    logger.info(f"Removed old audio file: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning up audio files: {str(e)}")
