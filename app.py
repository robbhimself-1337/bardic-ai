from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from services.ollama_client import call_ollama
from services.voice_input import transcribe_audio
from services.voice_output import text_to_speech, text_to_speech_with_chunks, AUDIO_OUTPUT_DIR
from services.dm_engine import DMEngine
from services.image_generator import generate_intro_scene
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


@app.template_filter('format_class_desc')
def format_class_desc_filter(text):
    """
    Extract first ### header as feature name and format description.
    Returns dict with 'feature' and 'description' keys.
    """
    if not text:
        return {'feature': '', 'description': ''}

    # Look for first ### header
    match = re.search(r'^###\s+(.+?)$', text, flags=re.MULTILINE)

    if match:
        feature = match.group(1).strip()
        # Remove the feature header from description
        description = re.sub(r'^###\s+.+?$', '', text, flags=re.MULTILINE, count=1)
        # Strip remaining markdown
        description = strip_markdown_filter(description)
    else:
        # No feature found, just clean the text
        feature = ''
        description = strip_markdown_filter(text)

    return {
        'feature': feature,
        'description': description.strip()
    }


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
    # Load existing characters
    characters = []
    char_dir = 'data/characters'
    if os.path.exists(char_dir):
        for filename in os.listdir(char_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(char_dir, filename)) as f:
                        char_data = json.load(f)
                        characters.append(char_data)
                except Exception as e:
                    logger.error(f"Error loading character {filename}: {e}")

    return render_template('landing.html', characters=characters)


@app.route('/new_game')
def new_game():
    """Start character creation wizard for new game."""
    return redirect(url_for('character_new'))


@app.route('/start', methods=['GET', 'POST'])
def start_game_setup():
    """Setup a new game - select players and characters."""

    # Load available characters
    characters = []
    char_dir = 'data/characters'
    if os.path.exists(char_dir):
        for filename in os.listdir(char_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(char_dir, filename)) as f:
                        characters.append(json.load(f))
                except Exception as e:
                    logger.error(f"Error loading character {filename}: {e}")

    if not characters:
        # No characters exist, redirect to create one first
        return redirect(url_for('character_new'))

    if request.method == 'POST':
        # Get selected character
        selected_char_name = request.form.get('character')

        # Find and load the character file
        char_file = f"data/characters/{selected_char_name.replace(' ', '_')}.json"
        if os.path.exists(char_file):
            # Store in session
            session['character_name'] = selected_char_name
            session['character_file'] = char_file

            # Go to campaign selection
            return redirect(url_for('campaign_select'))
        else:
            logger.error(f"Character file not found: {char_file}")
            return "Character not found", 404

    return render_template('start_game.html', characters=characters)


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
    character_name = session.get('character_name')
    character_file = session.get('character_file')

    if not character_name or not character_file:
        # No character in session, redirect to character creation
        return redirect(url_for('character_new'))

    try:
        # Load the full character data from file
        with open(character_file, 'r') as f:
            char_data = json.load(f)

        # Load campaign
        campaign = Campaign.load_campaign(campaign_id)

        # Create character for game (using simplified Character model for now)
        character = Character(
            name=char_data.get('name', character_name),
            char_class=char_data.get('character_class', 'Fighter')
        )

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

        # Create DM Engine
        dm_engine = DMEngine(game_state, campaign)

        # Store in session and active games
        session_id = os.urandom(16).hex()
        session['game_session_id'] = session_id
        active_games[session_id] = {
            'game_state': game_state,
            'campaign': campaign,
            'dm_engine': dm_engine,
            'character_data': char_data  # Store full character data for reference
        }

        logger.info(f"Started campaign {campaign_id} with character {character_name}")

        # Check if campaign has intro scenes
        if campaign.intro_scenes and len(campaign.intro_scenes) > 0:
            return redirect(url_for('game_intro'))
        else:
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
    dm_engine = game_data['dm_engine']

    # Enter the current checkpoint to get initial state
    checkpoint_info = dm_engine.enter_checkpoint()

    # Generate TTS for initial narration (with error handling)
    audio_url = None
    subtitle_chunks = []
    if checkpoint_info.get('narration'):
        try:
            tts_result = text_to_speech_with_chunks(checkpoint_info['narration'])
            if tts_result['audio']:
                # Pass raw filenames - frontend handles /audio/ prefix
                audio_url = tts_result['audio']
                subtitle_chunks = tts_result['chunks']
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            # Continue without audio - don't crash the game

    checkpoint_info['audio_url'] = audio_url
    checkpoint_info['subtitle_chunks'] = subtitle_chunks

    return render_template(
        'game.html',
        character=game_data['game_state'].character,
        **checkpoint_info
    )


@app.route('/game/intro')
def game_intro():
    """Campaign intro cinematic sequence."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return redirect(url_for('index'))

    game_data = active_games[session_id]
    campaign = game_data['campaign']

    # Generate images for intro scenes if they have prompts but no URLs
    for scene in campaign.intro_scenes:
        if scene.image_prompt and not scene.image_url:
            logger.info(f"Generating intro scene image: {scene.image_prompt[:50]}...")
            image_url = generate_intro_scene(campaign.title, scene.image_prompt)
            if image_url:
                scene.image_url = image_url

        # Generate TTS for scene narration if needed
        if scene.narration and not scene.audio_url:
            audio_file = text_to_speech(scene.narration)
            if audio_file:
                scene.audio_url = f'/audio/{audio_file}'

    # Convert intro scenes to dict for template
    intro_scenes_dict = [scene.to_dict() for scene in campaign.intro_scenes]

    return render_template(
        'game_intro.html',
        campaign=campaign,
        intro_scenes=intro_scenes_dict
    )


@app.route('/game/choice', methods=['POST'])
def game_choice():
    """Handle pre-defined choice selection (instant, no Ollama)."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({'error': 'No active game session'}), 400

    try:
        dm_engine = active_games[session_id]['dm_engine']
        data = request.get_json()
        choice_index = data.get('choice_index', 0)

        result = dm_engine.make_choice(choice_index)

        # Generate TTS for narration
        if 'transition' in result:
            full_narration = result['transition'] + " " + result.get('narration', '')
        else:
            full_narration = result.get('narration', '')

        if full_narration:
            audio_files = text_to_speech(full_narration)
            if audio_files:
                # audio_files may be comma-separated for long text
                result['audio'] = audio_files

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error processing choice: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/game/talk', methods=['POST'])
def game_talk_to_npc():
    """Start conversation with NPC (instant, no Ollama)."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({'error': 'No active game session'}), 400

    try:
        dm_engine = active_games[session_id]['dm_engine']
        data = request.get_json()
        npc_name = data.get('npc_name', '')

        result = dm_engine.talk_to_npc(npc_name)

        if result.get('narration'):
            audio_file = text_to_speech(result['narration'])
            result['audio'] = audio_file if audio_file else None

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error talking to NPC: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/game/ask', methods=['POST'])
def game_ask_topic():
    """Ask NPC about a topic (scripted if available, Ollama fallback)."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({'error': 'No active game session'}), 400

    try:
        dm_engine = active_games[session_id]['dm_engine']
        data = request.get_json()
        topic = data.get('topic', '')

        result = dm_engine.ask_about(topic)

        if result.get('narration'):
            audio_file = text_to_speech(result['narration'])
            result['audio'] = audio_file if audio_file else None

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error asking about topic: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/game/end_conversation', methods=['POST'])
def game_end_conversation():
    """End NPC conversation."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({'error': 'No active game session'}), 400

    try:
        dm_engine = active_games[session_id]['dm_engine']
        result = dm_engine.end_conversation()
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error ending conversation: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/game/action', methods=['POST'])
def game_custom_action():
    """Handle free-form player action (uses Ollama, slower)."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({'error': 'No active game session'}), 400

    try:
        dm_engine = active_games[session_id]['dm_engine']
        data = request.get_json()
        action = data.get('action', '')

        if not action:
            return jsonify({'error': 'No action provided'}), 400

        result = dm_engine.process_custom_action(action)

        if result.get('narration'):
            # Use new function that returns both audio and text chunks for subtitle sync
            tts_result = text_to_speech_with_chunks(result['narration'])
            result['audio'] = tts_result['audio']
            result['subtitle_chunks'] = tts_result['chunks']

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error processing custom action: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/game/voice_action', methods=['POST'])
def game_voice_action():
    """Handle voice input from the player."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({"error": "No active game"}), 400

    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400

    audio_file = request.files['audio']

    # Save temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Transcribe with Whisper
        transcription = transcribe_audio(tmp_path)

        if not transcription:
            return jsonify({"error": "Could not transcribe audio"}), 400

        # Process as custom action
        game_data = active_games[session_id]
        dm_engine = game_data['dm_engine']

        result = dm_engine.process_custom_action(transcription)
        result['transcription'] = transcription

        # Generate TTS
        if result.get('narration'):
            audio_file = text_to_speech(result['narration'])
            if audio_file:
                result['audio'] = audio_file if audio_file else None

        return jsonify(result)
    except Exception as e:
        logger.error(f"Voice input error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up temp file
        import os
        os.unlink(tmp_path)


@app.route('/game/attack', methods=['POST'])
def game_attack():
    """Attack an enemy in combat."""
    session_id = session.get('game_session_id')
    if not session_id or session_id not in active_games:
        return jsonify({'error': 'No active game session'}), 400

    try:
        dm_engine = active_games[session_id]['dm_engine']
        data = request.get_json()
        enemy_index = data.get('enemy_index', 0)
        damage = data.get('damage', 5)  # Default weapon damage

        result = dm_engine.attack_enemy(enemy_index, damage)

        if result.get('narration'):
            audio_file = text_to_speech(result['narration'])
            result['audio'] = audio_file if audio_file else None

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error attacking enemy: {e}")
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

        return redirect(url_for('character_step5'))

    return render_template(
        'character/step4_abilities.html',
        wizard_data=wizard_data,
        current_step=4,
        progress=44
    )


@app.route('/character/step5', methods=['GET', 'POST'])
def character_step5():
    """Step 5: Background Selection."""
    from services.open5e_client import get_backgrounds

    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Save background selection
        wizard_data['background'] = request.form.get('background')
        wizard_data['step'] = 6
        session['character_wizard_data'] = wizard_data
        return redirect(url_for('character_step6'))

    # GET request - show background selection
    backgrounds = get_backgrounds()

    return render_template(
        'character/step5_background.html',
        backgrounds=backgrounds,
        wizard_data=wizard_data,
        current_step=5,
        progress=55
    )


@app.route('/character/step6', methods=['GET', 'POST'])
def character_step6():
    """Step 6: Equipment."""
    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Save equipment (auto-assigned, no user selection needed)
        wizard_data['step'] = 7
        session['character_wizard_data'] = wizard_data
        return redirect(url_for('character_step7'))

    # Equipment dict based on class
    class_equipment = {
        'Fighter': ["Chain Mail", "Shield", "Longsword", "Light Crossbow", "20 Bolts"],
        'Rogue': ["Leather Armor", "Shortsword", "Shortbow", "20 Arrows", "Thieves' Tools"],
        'Wizard': ["Quarterstaff", "Spellbook", "Component Pouch"],
        'Cleric': ["Scale Mail", "Shield", "Mace", "Holy Symbol"],
        'Barbarian': ["Greataxe", "2 Handaxes", "Explorer's Pack"],
        'Bard': ["Leather Armor", "Rapier", "Lute", "Entertainer's Pack"],
        'Druid': ["Leather Armor", "Wooden Shield", "Scimitar", "Druidic Focus"],
        'Monk': ["Shortsword", "10 Darts", "Explorer's Pack"],
        'Paladin': ["Chain Mail", "Shield", "Longsword", "Holy Symbol"],
        'Ranger': ["Scale Mail", "Longbow", "20 Arrows", "2 Shortswords"],
        'Sorcerer': ["Light Crossbow", "20 Bolts", "Component Pouch", "Dagger"],
        'Warlock': ["Light Crossbow", "20 Bolts", "Arcane Focus", "Leather Armor", "Dagger"]
    }

    background_equipment = ["Common Clothes", "Pouch with 15 gold pieces", "A memento from your past"]

    char_class = wizard_data.get('character_class', 'Fighter')
    background = wizard_data.get('background', 'Unknown')

    equipment = class_equipment.get(char_class, ["Dagger", "Backpack"])

    # Store equipment in session
    wizard_data['equipment'] = equipment + background_equipment
    session['character_wizard_data'] = wizard_data

    return render_template(
        'character/step6_equipment.html',
        wizard_data=wizard_data,
        char_class=char_class,
        background=background,
        class_equipment=equipment,
        background_equipment=background_equipment,
        current_step=6,
        progress=66
    )


@app.route('/character/step7', methods=['GET', 'POST'])
def character_step7():
    """Step 7: Skill Selection."""
    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Save skills
        skills = request.form.getlist('skills')
        wizard_data['skill_proficiencies'] = skills
        wizard_data['step'] = 8
        session['character_wizard_data'] = wizard_data

        return redirect(url_for('character_step8'))

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


@app.route('/character/step8', methods=['GET', 'POST'])
def character_step8():
    """Step 8: Spell Selection (for spellcasters only)."""
    from services.open5e_client import get_spells_for_class

    wizard_data = session.get('character_wizard_data', {})
    char_class = wizard_data.get('character_class', '')

    # Classes that get spells at level 1
    spellcaster_info = {
        'Cleric': {'cantrips': 3, 'spells': 2, 'note': 'Prepare WIS modifier + 1 spells'},
        'Wizard': {'cantrips': 3, 'spells': 6, 'note': 'Learn 6 spells in spellbook, prepare INT modifier + 1'},
        'Bard': {'cantrips': 2, 'spells': 4, 'note': 'Know 4 spells'},
        'Druid': {'cantrips': 2, 'spells': 2, 'note': 'Prepare WIS modifier + 1 spells'},
        'Sorcerer': {'cantrips': 4, 'spells': 2, 'note': 'Know 2 spells'},
        'Warlock': {'cantrips': 2, 'spells': 2, 'note': 'Know 2 spells'},
    }

    # Skip for non-casters
    if char_class not in spellcaster_info:
        wizard_data['step'] = 9
        session['character_wizard_data'] = wizard_data
        return redirect(url_for('character_step9'))

    if request.method == 'POST':
        wizard_data['cantrips'] = request.form.getlist('cantrips')
        wizard_data['spells_known'] = request.form.getlist('spells')
        wizard_data['step'] = 9
        session['character_wizard_data'] = wizard_data
        return redirect(url_for('character_step9'))

    # Get spells from Open5e
    cantrips = get_spells_for_class(char_class, level=0)  # Level 0 = cantrips
    level_1_spells = get_spells_for_class(char_class, level=1)

    caster_data = spellcaster_info[char_class]

    return render_template(
        'character/step8_spells.html',
        wizard_data=wizard_data,
        char_class=char_class,
        cantrips=cantrips,
        spells=level_1_spells,
        num_cantrips=caster_data['cantrips'],
        num_spells=caster_data['spells'],
        spell_note=caster_data['note'],
        current_step=8,
        progress=88
    )


@app.route('/character/step9', methods=['GET', 'POST'])
def character_step9():
    """Step 9: Review and Finalize."""
    wizard_data = session.get('character_wizard_data', {})

    if request.method == 'POST':
        # Create final character
        char_name = request.form.get('character_name')
        portrait_filename = request.form.get('portrait_filename', '')

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

        char_dict = character.to_dict()
        # Add portrait filename to the saved data
        if portrait_filename:
            char_dict['portrait'] = portrait_filename

        with open(char_file, 'w') as f:
            json.dump(char_dict, f, indent=2)

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


@app.route('/character/generate_portrait', methods=['POST'])
def generate_portrait():
    """Generate a character portrait using AI."""
    from services.image_gen import generate_character_portrait

    try:
        wizard_data = session.get('character_wizard_data', {})
        data = request.get_json()

        # Extract all appearance data from new structured fields
        character_name = data.get('character_name', 'character')
        gender = data.get('gender', 'male')
        age = data.get('age', 'adult')
        build = data.get('build', 'average')
        skin_tone = data.get('skin_tone', 'fair')
        expression = data.get('expression', 'neutral')
        eye_color = data.get('eye_color', 'brown')
        hair_style = data.get('hair_style', 'short')
        hair_color = data.get('hair_color', 'brown')
        facial_hair = data.get('facial_hair', 'none')
        features = data.get('features', [])  # Array of selected features

        # Get character data from wizard
        race = wizard_data.get('race', 'Human')
        character_class = wizard_data.get('character_class', 'Fighter')
        background = wizard_data.get('background', '')

        logger.info(f"Generating portrait for {character_name} ({race} {character_class})")
        logger.info(f"Appearance: {gender}, {age}, {skin_tone} skin, {hair_color} {hair_style} hair")

        # Generate the portrait
        filename = generate_character_portrait(
            race=race,
            character_class=character_class,
            gender=gender,
            age=age,
            build=build,
            skin_tone=skin_tone,
            expression=expression,
            eye_color=eye_color,
            hair_style=hair_style,
            hair_color=hair_color,
            facial_hair=facial_hair,
            features=features,
            background=background,
            character_name=character_name
        )

        if filename:
            return jsonify({
                'success': True,
                'filename': filename
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate portrait'
            }), 500

    except Exception as e:
        logger.error(f"Error generating portrait: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
