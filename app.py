from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from services.ollama_client import call_ollama
from services.voice_input import transcribe_audio
from services.voice_output import text_to_speech, AUDIO_OUTPUT_DIR
from services.dm_engine import DMEngine
from models.game_state import GameState, Character
from models.campaign import Campaign
from models.dnd5e_character import DnD5eCharacter
from services import open5e_client
import os
import json
import logging
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Custom Jinja2 filters
@app.template_filter('strip_markdown')
def strip_markdown_filter(text):
    """Strip markdown headers and formatting from text."""
    if not text:
        return ""
    # Remove markdown headers (## Header, ### Header, etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)  # Bold+italic
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # Italic
    text = re.sub(r'___(.+?)___', r'\1', text)  # Bold+italic alt
    text = re.sub(r'__(.+?)__', r'\1', text)  # Bold alt
    text = re.sub(r'_(.+?)_', r'\1', text)  # Italic alt
    return text.strip()


# Store active game sessions (in production, use Redis or database)
active_games = {}


# Initialize Open5e cache on startup
def initialize_cache():
    """Initialize Open5e cache if empty."""
    cache_status = open5e_client.get_cache_status()

    # Check if any cache files are missing
    missing_cache = any(not status.get('cached', False) for status in cache_status.values())

    if missing_cache:
        logger.info("Open5e cache is empty or incomplete. Initializing...")
        try:
            open5e_client.refresh_cache()
            logger.info("Open5e cache initialized successfully!")
        except Exception as e:
            logger.error(f"Failed to initialize Open5e cache: {e}")
            logger.info("App will continue with partial/empty cache")
    else:
        logger.info("Open5e cache found and loaded")


# Initialize cache on app startup
initialize_cache()


@app.route('/')
def index():
    """Landing page with New Game and Load Game options."""
    return render_template('landing.html')


@app.route('/new_game')
def new_game():
    """Start character creation wizard for new game."""
    return redirect(url_for('character_new'))


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


# Character Creation Wizard Routes

@app.route('/character/new')
def character_new():
    """Initialize character creation wizard."""
    # Clear any existing wizard data
    session.pop('character_wizard_data', None)

    # Initialize wizard data
    session['character_wizard_data'] = {
        'step': 1,
        'race': None,
        'character_class': None,
        'subclass': None,
        'strength': 10,
        'dexterity': 10,
        'constitution': 10,
        'intelligence': 10,
        'wisdom': 10,
        'charisma': 10,
        'background': None,
        'skill_proficiencies': [],
        'equipment': [],
        'spells_known': [],
        'cantrips': []
    }

    return redirect(url_for('character_step1'))


@app.route('/character/step1', methods=['GET', 'POST'])
def character_step1():
    """Step 1: Race Selection."""
    from services.open5e_client import get_races

    if request.method == 'POST':
        # Save race selection
        wizard_data = session.get('character_wizard_data', {})
        wizard_data['race'] = request.form.get('race')
        wizard_data['step'] = 2
        session['character_wizard_data'] = wizard_data
        return redirect(url_for('character_step2'))

    # GET request - show race selection
    races = get_races()

    return render_template(
        'character/step1_race.html',
        races=races,
        current_step=1,
        progress=11
    )


@app.route('/character/step2', methods=['GET', 'POST'])
def character_step2():
    """Step 2: Class Selection."""
    from services.open5e_client import get_classes

    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Save class selection
        wizard_data['character_class'] = request.form.get('character_class')
        wizard_data['step'] = 3
        session['character_wizard_data'] = wizard_data

        # Skip subclass step for now, go to abilities
        return redirect(url_for('character_step4'))

    # GET request - show class selection
    classes = get_classes()
    selected_race = wizard_data.get('race', 'Unknown')

    return render_template(
        'character/step2_class.html',
        classes=classes,
        selected_race=selected_race,
        current_step=2,
        progress=22
    )


@app.route('/character/step4', methods=['GET', 'POST'])
def character_step4():
    """Step 4: Ability Scores."""
    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Save ability scores
        wizard_data['strength'] = int(request.form.get('strength', 10))
        wizard_data['dexterity'] = int(request.form.get('dexterity', 10))
        wizard_data['constitution'] = int(request.form.get('constitution', 10))
        wizard_data['intelligence'] = int(request.form.get('intelligence', 10))
        wizard_data['wisdom'] = int(request.form.get('wisdom', 10))
        wizard_data['charisma'] = int(request.form.get('charisma', 10))
        wizard_data['step'] = 5
        session['character_wizard_data'] = wizard_data

        # Skip to step 7 (skills) for now
        return redirect(url_for('character_step7'))

    return render_template(
        'character/step4_abilities.html',
        wizard_data=wizard_data,
        current_step=4,
        progress=44
    )


@app.route('/character/step7', methods=['GET', 'POST'])
def character_step7():
    """Step 7: Skill Selection."""
    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Save skills
        skills = request.form.getlist('skills')
        wizard_data['skill_proficiencies'] = skills
        wizard_data['step'] = 9
        session['character_wizard_data'] = wizard_data

        return redirect(url_for('character_step9'))

    # Determine number of skills based on class
    class_skills = {
        'Fighter': 2,
        'Rogue': 4,
        'Wizard': 2,
        'Cleric': 2,
        'Bard': 3,
        'Ranger': 3,
        'Paladin': 2,
        'Barbarian': 2,
        'Druid': 2,
        'Monk': 2,
        'Sorcerer': 2,
        'Warlock': 2
    }

    char_class = wizard_data.get('character_class', 'Fighter')
    num_skills = class_skills.get(char_class, 2)

    all_skills = [
        'Acrobatics', 'Animal Handling', 'Arcana', 'Athletics',
        'Deception', 'History', 'Insight', 'Intimidation',
        'Investigation', 'Medicine', 'Nature', 'Perception',
        'Performance', 'Persuasion', 'Religion', 'Sleight of Hand',
        'Stealth', 'Survival'
    ]

    return render_template(
        'character/step7_skills.html',
        wizard_data=wizard_data,
        all_skills=all_skills,
        num_skills=num_skills,
        current_step=7,
        progress=77
    )


@app.route('/character/step9', methods=['GET', 'POST'])
def character_step9():
    """Step 9: Review and Finalize."""
    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Create final character
        char_name = request.form.get('character_name')

        character = DnD5eCharacter(
            name=char_name,
            race=wizard_data.get('race', 'Human'),
            character_class=wizard_data.get('character_class', 'Fighter'),
            strength=wizard_data.get('strength', 10),
            dexterity=wizard_data.get('dexterity', 10),
            constitution=wizard_data.get('constitution', 10),
            intelligence=wizard_data.get('intelligence', 10),
            wisdom=wizard_data.get('wisdom', 10),
            charisma=wizard_data.get('charisma', 10),
            background=wizard_data.get('background'),
            skill_proficiencies=wizard_data.get('skill_proficiencies', []),
            inventory=wizard_data.get('equipment', []),
            spells_known=wizard_data.get('spells_known', []),
            cantrips=wizard_data.get('cantrips', [])
        )

        # Save character to file
        char_file = f"data/characters/{char_name.replace(' ', '_')}.json"
        os.makedirs('data/characters', exist_ok=True)

        with open(char_file, 'w') as f:
            json.dump(character.to_dict(), f, indent=2)

        # Store character name in session for campaign selection
        session['character_name'] = char_name
        session['character_file'] = char_file

        # Clear wizard data
        session.pop('character_wizard_data', None)

        # Redirect to campaign selection
        return redirect(url_for('campaign_select'))

    # Calculate display stats
    con_mod = (wizard_data.get('constitution', 10) - 10) // 2

    # HP calculation (simplified)
    class_hit_dice = {
        'Barbarian': 12, 'Fighter': 10, 'Paladin': 10, 'Ranger': 10,
        'Bard': 8, 'Cleric': 8, 'Druid': 8, 'Monk': 8, 'Rogue': 8, 'Warlock': 8,
        'Sorcerer': 6, 'Wizard': 6
    }
    hit_die = class_hit_dice.get(wizard_data.get('character_class'), 8)
    hp = hit_die + con_mod

    # AC calculation (unarmored)
    dex_mod = (wizard_data.get('dexterity', 10) - 10) // 2
    ac = 10 + dex_mod
    initiative = dex_mod

    return render_template(
        'character/step9_review.html',
        wizard_data=wizard_data,
        hp=hp,
        ac=ac,
        initiative=initiative,
        current_step=9,
        progress=100
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
