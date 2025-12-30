import os
import logging
from TTS.api import TTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AUDIO_OUTPUT_DIR = "/tmp/bardic_audio"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

# Load TTS model
logger.info("Loading Coqui TTS model...")
tts = TTS("tts_models/en/ljspeech/tacotron2-DDC").to("cuda")  # Use a simpler model for now
logger.info("TTS model loaded successfully")

def text_to_speech(text, filename="dm_response.wav"):
    """
    Convert text to speech and save as audio file.
    
    Args:
        text: Text to convert to speech
        filename: Output filename
    
    Returns:
        str: Filename of generated audio
    """
    try:
        output_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
        logger.info(f"Generating speech for: {text[:50]}...")
        
        # Simple TTS without voice cloning
        tts.tts_to_file(text=text, file_path=output_path)
        
        logger.info(f"Audio saved to {output_path}")
        return filename
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise