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


def transcribe_audio(audio_file):
    """
    Transcribe audio using Whisper base model.

    Args:
        audio_file: File-like object containing audio data (WAV format)

    Returns:
        str: Transcribed text
    """
    try:
        # Save the uploaded file temporarily
        temp_path = "/tmp/temp_audio.wav"
        audio_file.save(temp_path)

        # Transcribe using Whisper
        logger.info("Starting transcription...")
        result = model.transcribe(temp_path)
        transcribed_text = result["text"].strip()

        logger.info(f"Transcription complete: {transcribed_text[:50]}...")
        return transcribed_text

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return f"Error: Could not transcribe audio - {str(e)}"
