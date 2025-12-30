"""
Add these routes to app.py for the character creation wizard.
Place after the existing routes.
"""

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
    from models.dnd5e_character import DnD5eCharacter
    import json

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


# Placeholder template for Step 7 Skills
# Create templates/character/step7_skills.html:
"""
{% extends "character/base_wizard.html" %}
{% block title %}Step 7: Choose Skills{% endblock %}
{% block content %}
<h2 style="text-align: center; color: #d4af37;">Choose {{ num_skills }} Skills</h2>
<form method="POST" id="skillsForm">
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin: 20px 0;">
        {% for skill in all_skills %}
        <label style="display: flex; align-items: center; gap: 10px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 5px; cursor: pointer;">
            <input type="checkbox" name="skills" value="{{ skill }}" class="skill-check">
            <span style="color: #f0e6d2;">{{ skill }}</span>
        </label>
        {% endfor %}
    </div>
    <div class="navigation">
        <a href="/character/step4" class="btn btn-secondary">← Back</a>
        <button type="submit" class="btn btn-primary" id="nextBtn" disabled>Next: Review →</button>
    </div>
</form>
<script>
    const maxSkills = {{ num_skills }};
    const checkboxes = document.querySelectorAll('.skill-check');

    checkboxes.forEach(cb => {
        cb.addEventListener('change', () => {
            const checked = document.querySelectorAll('.skill-check:checked').length;
            document.getElementById('nextBtn').disabled = checked !== maxSkills;

            checkboxes.forEach(box => {
                if (!box.checked && checked >= maxSkills) {
                    box.disabled = true;
                } else {
                    box.disabled = false;
                }
            });
        });
    });
</script>
{% endblock %}
"""
