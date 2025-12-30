from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from services.ollama_client import call_ollama
from services.voice_input import transcribe_audio
from services.voice_output import text_to_speech, AUDIO_OUTPUT_DIR
from services.dm_engine import DMEngine
from models.game_state import GameState, Character
from models.campaign import Campaign
import os
import logging

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active game sessions (in production, use Redis or database)
active_games = {}


@app.route('/')
def index():
    """Landing page with New Game and Load Game options."""
    return render_template('landing.html')


@app.route('/new_game')
def new_game():
    """Start character creation for new game."""
    return render_template('character_creation.html')


@app.route('/character_creation', methods=['POST'])
def character_creation():
    """Handle character creation and proceed to campaign selection."""
    name = request.form.get('name')
    char_class = request.form.get('char_class')

    if not name or not char_class:
        return "Error: Missing character name or class", 400

    # Store character in session
    session['character_name'] = name
    session['character_class'] = char_class

    return redirect(url_for('campaign_select'))


@app.route('/campaign_select')
def campaign_select():
    """Show available campaigns."""
    campaigns = Campaign.list_available_campaigns()
    return render_template('campaign_select.html', campaigns=campaigns)


@app.route('/start_campaign/<campaign_id>')
def start_campaign(campaign_id):
    """Start a new campaign with the created character."""
    # Get character from session
    name = session.get('character_name')
    char_class = session.get('character_class')

    if not name or not char_class:
        return redirect(url_for('new_game'))

    try:
        # Load campaign
        campaign = Campaign.load_campaign(campaign_id)

        # Create character
        character = Character(name=name, char_class=char_class)

        # Create game state
        game_state = GameState(
            character=character,
            campaign_id=campaign_id,
            current_checkpoint=campaign.starting_checkpoint
        )

        # Add starting quests
        checkpoint = campaign.get_checkpoint(campaign.starting_checkpoint)
        if checkpoint and checkpoint.auto_quests:
            for quest in checkpoint.auto_quests:
                game_state.add_quest(quest["name"], quest["description"])

        # Store in session and active games
        session_id = os.urandom(16).hex()
        session['game_session_id'] = session_id
        active_games[session_id] = {
            'game_state': game_state,
            'campaign': campaign
        }

        return redirect(url_for('game'))

    except Exception as e:
        logger.error(f"Error starting campaign: {e}")
        return f"Error starting campaign: {str(e)}", 500


@app.route('/game')
def game():
    """Main game interface."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return redirect(url_for('index'))

    game_data = active_games[session_id]
    game_state = game_data['game_state']
    campaign = game_data['campaign']

    # Get current checkpoint narrative
    checkpoint = campaign.get_checkpoint(game_state.current_checkpoint)
    initial_narrative = checkpoint.description if checkpoint else "Your adventure begins..."

    return render_template(
        'game.html',
        character=game_state.character,
        active_quests=game_state.get_active_quests(),
        combat_active=game_state.combat_active,
        enemies=game_state.enemies,
        initial_narrative=initial_narrative
    )


@app.route('/game_action', methods=['POST'])
def game_action():
    """Process player action through DM engine."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({'error': 'No active game session'}), 400

    data = request.get_json()
    player_action = data.get('action')

    if not player_action:
        return jsonify({'error': 'No action provided'}), 400

    try:
        game_data = active_games[session_id]
        game_state = game_data['game_state']
        campaign = game_data['campaign']

        # Create DM engine
        dm_engine = DMEngine(game_state, campaign)

        # Process action
        result = dm_engine.process_action(player_action)

        # Generate TTS audio
        audio_filename = text_to_speech(result['narrative'])

        # Return result with audio
        return jsonify({
            'narrative': result['narrative'],
            'audio_filename': audio_filename,
            'character_hp': result['character_hp'],
            'character_max_hp': result['character_max_hp'],
            'inventory': result['inventory'],
            'combat_active': result['combat_active'],
            'enemies': result['enemies'],
            'active_quests': result['active_quests']
        })

    except Exception as e:
        logger.error(f"Error processing action: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/save_game')
def save_game():
    """Save current game state."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return redirect(url_for('index'))

    try:
        game_data = active_games[session_id]
        game_state = game_data['game_state']

        # Generate save filename
        filename = f"{game_state.character.name}_{game_state.campaign_id}.json"
        filepath = game_state.save_game(filename)

        return f"""
        <html>
            <head><title>Game Saved</title></head>
            <body>
                <h1>Game Saved Successfully!</h1>
                <p>Your game has been saved to: {filename}</p>
                <a href="/game">Back to Game</a>
            </body>
        </html>
        """

    except Exception as e:
        logger.error(f"Error saving game: {e}")
        return f"Error saving game: {str(e)}", 500


@app.route('/load')
def load_game():
    """Show list of saved games."""
    save_dir = "data/campaigns/saves"
    saved_games = []

    if os.path.exists(save_dir):
        for filename in os.listdir(save_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(save_dir, filename)
                try:
                    # Load game state to get details
                    game_state = GameState.load_game(filename)
                    saved_games.append({
                        'filename': filename,
                        'character_name': game_state.character.name,
                        'char_class': game_state.character.char_class,
                        'level': game_state.character.level,
                        'campaign_id': game_state.campaign_id,
                        'last_saved': game_state.last_saved
                    })
                except Exception as e:
                    logger.error(f"Error loading save file {filename}: {e}")

    return render_template('load_game.html', saved_games=saved_games)


@app.route('/load_game/<filename>')
def load_game_file(filename):
    """Load a specific saved game."""
    try:
        # Load game state
        game_state = GameState.load_game(filename)

        # Load campaign
        campaign = Campaign.load_campaign(game_state.campaign_id)

        # Create new session
        session_id = os.urandom(16).hex()
        session['game_session_id'] = session_id
        active_games[session_id] = {
            'game_state': game_state,
            'campaign': campaign
        }

        return redirect(url_for('game'))

    except Exception as e:
        logger.error(f"Error loading game: {e}")
        return f"Error loading game: {str(e)}", 500


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Transcribe audio to text using Whisper."""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        return jsonify({'error': 'No audio file selected'}), 400

    try:
        transcribed_text = transcribe_audio(audio_file)
        return jsonify({'text': transcribed_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve audio files from the temp directory."""
    return send_from_directory(AUDIO_OUTPUT_DIR, filename)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
