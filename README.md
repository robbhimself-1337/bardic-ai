# Bardic AI

Local AI-powered D&D DM with voice input/output. Ollama + Whisper + Coqui TTS for offline tabletop adventures.

## Features

- **Voice Input**: Speak your actions using Whisper speech-to-text
- **Voice Output**: DM responses with voice cloning using Coqui TTS XTTS v2
- **Offline**: Runs completely locally on your machine
- **Customizable Voices**: Clone your own voice or create unique NPC voices
- **GPU Accelerated**: Uses CUDA for fast TTS and Whisper transcription

## Setup

### Prerequisites
- Python 3.9+
- CUDA-capable GPU (12GB+ VRAM recommended)
- [Ollama](https://ollama.ai) installed and running
- Qwen 2.5 14B model: `ollama pull qwen2.5:14b`

### Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/bardic-ai.git
cd bardic-ai

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

### Recording Your Voice Sample

Before running the app, record a voice sample for voice cloning:

```bash
python record_voice_sample.py
```

This will:
1. Record 30 seconds of audio from your microphone
2. Show a countdown timer while recording
3. Save to `voice_samples/dm_narrator.wav`

**Tips for best results:**
- Speak naturally and clearly
- Vary your tone and intonation
- Record in a quiet room with minimal background noise
- Position microphone 6-8 inches from your mouth

See [voice_samples/README.md](voice_samples/README.md) for detailed voice recording guidelines.

### Running the App

```bash
python app.py
```

Visit `http://localhost:5000` to start your adventure!

- Use text input for traditional gameplay
- Click "Use Voice Input" for voice-powered gameplay

## Voice Cloning

### Speed Adjustment

Adjust speech speed in [services/voice_output.py](services/voice_output.py:17):

```python
text_to_speech(text, voice_sample="voice_samples/dm_narrator.wav", speed=1.2)
```

- `speed=0.5` - Very slow (dramatic moments)
- `speed=1.0` - Normal speaking pace
- `speed=1.2` - Slightly faster (default, keeps gameplay moving)
- `speed=1.5` - Fast narration

### Multiple Voice Samples for NPCs

Create different voice samples for different characters:

```bash
# Record and rename for specific NPCs
python record_voice_sample.py
mv voice_samples/dm_narrator.wav voice_samples/npc_merchant.wav

python record_voice_sample.py
mv voice_samples/dm_narrator.wav voice_samples/npc_villain.wav
```

Then update your code to use different voices for different NPCs by passing the `voice_sample` parameter.

## Technical Details

- **LLM**: Ollama (Qwen 2.5 14B)
- **Speech-to-Text**: OpenAI Whisper (base model)
- **Text-to-Speech**: Coqui TTS XTTS v2 with voice cloning
- **Web Framework**: Flask
- **Audio Processing**: sounddevice, scipy, numpy

## Roadmap

- [x] Basic Ollama integration
- [x] Voice input (Whisper)
- [x] Voice output (Coqui TTS with voice cloning)
- [ ] Game state persistence
- [ ] Combat system
- [ ] Campaign structure
- [ ] Multi-voice NPC support
- [ ] Real-time voice conversation mode