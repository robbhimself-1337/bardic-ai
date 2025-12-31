import whisper
import numpy as np
import io
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Whisper model once on module import
logger.info("Loading Whisper base model...")
model = whisper.load_model("base")
logger.info("Whisper model loaded successfully")


def transcribe_audio(audio_input):
    """
    Transcribe audio using Whisper base model.

    Args:
        audio_input: Either a file path (str) or file-like object with .save() method

    Returns:
        str: Transcribed text, or None on error
    """
    try:
        temp_path = "/tmp/temp_audio.wav"
        
        # Handle both file paths and file objects
        if isinstance(audio_input, str):
            # It's already a file path
            temp_path = audio_input
        else:
            # It's a file-like object, save it
            audio_input.save(temp_path)

        # Transcribe using Whisper
        logger.info(f"Starting transcription of {temp_path}...")
        result = model.transcribe(temp_path)
        transcribed_text = result["text"].strip()

        logger.info(f"Transcription complete: {transcribed_text[:50]}...")
        return transcribed_text

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return None
