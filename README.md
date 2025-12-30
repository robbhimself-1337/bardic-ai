# Bardic AI

Local AI-powered D&D DM with voice input/output. Ollama + Whisper + Coqui TTS for offline tabletop adventures

## Setup

### Prerequisites
- Python 3.9+
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

# Run the app
python app.py
```

Visit `http://localhost:5000` to start your adventure!

## Roadmap
- [x] Basic Ollama integration
- [ ] Voice input (Whisper)
- [ ] Voice output (Coqui TTS)
- [ ] Game state persistence
- [ ] Combat system
- [ ] Campaign structure
- [ ] Multi-voice NPC support