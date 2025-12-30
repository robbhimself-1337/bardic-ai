# D&D 5e Character Creation System

Complete integration with Open5e API for full SRD-compliant character creation.

## Implemented Components

### 1. Open5e API Client ([services/open5e_client.py](services/open5e_client.py))

**Features:**
- ✅ Fetch all races, classes, backgrounds, spells, weapons, armor
- ✅ Automatic pagination handling (50 results per page)
- ✅ 7-day local caching system
- ✅ Graceful fallback to cache if API unavailable
- ✅ Cache refresh functionality
- ✅ Spells filtered by class and level

**API Endpoints:**
```python
client.get_races()          # All playable races
client.get_classes()        # All 12 classes
client.get_backgrounds()    # Character backgrounds
client.get_spells()         # All SRD spells
client.get_weapons()        # Weapons list
client.get_armor()          # Armor list
client.get_magic_items()    # Magic items

# Filtered queries
client.get_spells_by_class("Wizard")
client.get_spells_by_level("Wizard", 1)
client.get_class_details("Fighter")
client.get_race_details("Elf")
```

**Cache System:**
- Location: `data/cache/`
- Files: `races.json`, `classes.json`, `backgrounds.json`, etc.
- Auto-refresh after 7 days
- Manual refresh: `client.refresh_all_cache()`

### 2. Enhanced Character Model ([models/dnd5e_character.py](models/dnd5e_character.py))

**Full D&D 5e Support:**

```python
class DnD5eCharacter:
    # Basic Info
    name: str
    level: int = 1

    # Race & Class
    race: str
    race_traits: dict
    character_class: str
    subclass: str

    # Ability Scores (3-18 range)
    strength, dexterity, constitution: int
    intelligence, wisdom, charisma: int

    # Derived Stats
    hp, max_hp: int
    ac: int  # Calculated from armor + DEX
    initiative: int
    proficiency_bonus: int

    # Proficiencies
    skill_proficiencies: list
    saving_throw_proficiencies: list
    tool_proficiencies: list
    language_proficiencies: list

    # Equipment
    inventory: list
    equipped_armor: str
    equipped_weapons: list

    # Spells (if spellcaster)
    cantrips: list
    spells_known: list
    spell_slots: dict
    spells_prepared: list

    # Background
    background: str
    background_feature: str

    # Character Details
    alignment: str
    personality_traits: str
    ideals, bonds, flaws: str

    # Features
    features: list
```

**Methods:**
- `get_ability_modifier(ability)` - Calculate +/- modifier
- `get_skill_bonus(skill_name)` - Total skill bonus with proficiency
- `get_saving_throw_bonus(ability)` - Saving throw bonus
- `take_damage(amount)`, `heal(amount)`
- `learn_spell(spell)`, `prepare_spell(spell)`

## To Complete: Multi-Step Character Creation Wizard

### Step 1: Race Selection

Create `templates/character_creation_step1_race.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Step 1: Choose Race</title>
    <style>
        /* Progress bar */
        .progress { width: 100%; height: 10px; background: #333; }
        .progress-fill { width: 11%; height: 100%; background: #ffd700; }

        /* Race cards */
        .race-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .race-card { border: 2px solid #ffd700; padding: 20px; cursor: pointer; }
        .race-card:hover { background: rgba(255, 215, 0, 0.1); }

        /* Filters */
        .filters { margin: 20px 0; }
        .filter-btn { padding: 10px 20px; margin: 5px; border: 1px solid #ffd700; background: transparent; color: #ffd700; cursor: pointer; }
        .filter-btn.active { background: #ffd700; color: #000; }
    </style>
</head>
<body>
    <div class="progress"><div class="progress-fill"></div></div>
    <h1>Step 1: Choose Your Race</h1>

    <div class="filters">
        <button class="filter-btn active" onclick="filterRaces('all')">All Races</button>
        <button class="filter-btn" onclick="filterRaces('common')">Common</button>
        <button class="filter-btn" onclick="filterRaces('exotic')">Exotic</button>
        <input type="text" id="search" placeholder="Search races..." onkeyup="searchRaces()">
    </div>

    <div class="race-grid" id="raceGrid">
        {% for race in races %}
        <div class="race-card" data-type="{{ race.type }}" onclick="selectRace('{{ race.name }}')">
            <h3>{{ race.name }}</h3>
            <p>{{ race.desc | truncate(100) }}</p>
            <div class="traits">
                <strong>Traits:</strong>
                <ul>
                    <li>Speed: {{ race.speed }}</li>
                    <li>Size: {{ race.size }}</li>
                    {% if race.asi %}
                    <li>ASI: {{ race.asi }}</li>
                    {% endif %}
                </ul>
            </div>
            <button>Choose {{ race.name }}</button>
        </div>
        {% endfor %}
    </div>

    <script>
        function filterRaces(type) {
            // Filter logic
        }

        function searchRaces() {
            // Search logic
        }

        function selectRace(raceName) {
            // Store in session and redirect to step 2
            window.location.href = `/character_creation/step2?race=${raceName}`;
        }
    </script>
</body>
</html>
```

### Step 2: Class Selection

Similar structure, show all 12 classes with:
- Hit Die
- Primary Ability
- Saving Throws
- Complexity Rating (Beginner/Intermediate/Advanced)
- Role tags (Tank, DPS, Support, Healer, etc.)

### Step 3: Subclass/Archetype

- Only show if level >= when subclass is chosen
- For level 1 characters, can be selected later

### Step 4: Ability Scores

Three methods:
1. **Standard Array**: 15, 14, 13, 12, 10, 8 (drag and drop to abilities)
2. **Point Buy**: 27 points, min 8, max 15 (calculator)
3. **Roll**: 4d6 drop lowest x6 (with button)

Apply racial bonuses automatically.

### Step 5: Background

List all backgrounds with:
- Skill proficiencies
- Tool proficiencies
- Feature description

### Step 6: Equipment

- Show class starting equipment
- Allow customization
- Calculate AC based on armor

### Step 7: Skills & Proficiencies

- Choose N skills based on class (Fighter=2, Rogue=4, etc.)
- Show background skills (auto-applied)
- Display which ability each skill uses

### Step 8: Spells (if spellcaster)

- Show cantrips (if applicable)
- Show 1st level spells
- Filter by class spell list
- Tooltips with spell descriptions

### Step 9: Review & Finalize

- Character sheet preview
- Final HP roll or take average
- Name character
- Confirm and save

## App.py Routes to Add

```python
@app.route('/character_creation/step1')
def char_creation_step1():
    from services.open5e_client import get_races
    races = get_races()
    return render_template('character_creation_step1_race.html', races=races)

@app.route('/character_creation/step2')
def char_creation_step2():
    from services.open5e_client import get_classes
    classes = get_classes()
    race = request.args.get('race')
    # Store race in session
    session['char_race'] = race
    return render_template('character_creation_step2_class.html', classes=classes, race=race)

@app.route('/character_creation/step3')
def char_creation_step3():
    # Subclass selection
    pass

@app.route('/character_creation/step4')
def char_creation_step4():
    # Ability scores
    pass

@app.route('/character_creation/step5')
def char_creation_step5():
    # Background
    from services.open5e_client import get_backgrounds
    backgrounds = get_backgrounds()
    return render_template('character_creation_step5_background.html', backgrounds=backgrounds)

@app.route('/character_creation/step6')
def char_creation_step6():
    # Equipment
    from services.open5e_client import get_weapons, get_armor
    weapons = get_weapons()
    armor = get_armor()
    return render_template('character_creation_step6_equipment.html', weapons=weapons, armor=armor)

@app.route('/character_creation/step7')
def char_creation_step7():
    # Skills
    pass

@app.route('/character_creation/step8')
def char_creation_step8():
    # Spells (if applicable)
    char_class = session.get('char_class')
    if is_spellcaster(char_class):
        from services.open5e_client import client
        cantrips = client.get_spells_by_level(char_class, 0)
        level1_spells = client.get_spells_by_level(char_class, 1)
        return render_template('character_creation_step8_spells.html',
                             cantrips=cantrips, spells=level1_spells)
    else:
        return redirect(url_for('char_creation_step9'))

@app.route('/character_creation/step9')
def char_creation_step9():
    # Review and finalize
    # Gather all from session
    # Create DnD5eCharacter instance
    # Display character sheet
    pass

@app.route('/character_creation/finalize', methods=['POST'])
def char_creation_finalize():
    # Create final character from session data
    from models.dnd5e_character import DnD5eCharacter

    char = DnD5eCharacter(
        name=request.form.get('name'),
        race=session.get('char_race'),
        character_class=session.get('char_class'),
        # ... all other fields from session
    )

    # Store in active games
    # Redirect to campaign select
    pass

@app.route('/admin/refresh_cache')
def refresh_cache():
    from services.open5e_client import refresh_cache, get_cache_status

    if request.args.get('confirm') == 'yes':
        refresh_cache()
        return "Cache refreshed!"

    status = get_cache_status()
    return render_template('admin_cache.html', status=status)
```

## Cache Management

### Admin Route

Create `templates/admin_cache.html`:

```html
<html>
<head><title>Open5e Cache Management</title></head>
<body>
    <h1>Open5e Cache Status</h1>
    <table>
        <tr>
            <th>Endpoint</th>
            <th>Cached</th>
            <th>Count</th>
            <th>Last Updated</th>
            <th>Age (hours)</th>
            <th>Valid</th>
        </tr>
        {% for endpoint, info in status.items() %}
        <tr>
            <td>{{ endpoint }}</td>
            <td>{{ info.cached }}</td>
            <td>{{ info.count }}</td>
            <td>{{ info.last_updated }}</td>
            <td>{{ info.age_hours }}</td>
            <td>{{ info.valid }}</td>
        </tr>
        {% endfor %}
    </table>

    <a href="/admin/refresh_cache?confirm=yes">
        <button>Refresh All Cache</button>
    </a>
</body>
</html>
```

## Testing

1. **Test Open5e Client**:
```bash
python
>>> from services.open5e_client import get_races, get_classes
>>> races = get_races()
>>> print(f"Found {len(races)} races")
>>> classes = get_classes()
>>> print(f"Found {len(classes)} classes")
```

2. **Test Character Creation**:
```python
from models.dnd5e_character import DnD5eCharacter

char = DnD5eCharacter(
    name="Thorin",
    race="Dwarf",
    character_class="Fighter",
    strength=16,
    dexterity=12,
    constitution=15,
    intelligence=10,
    wisdom=11,
    charisma=8
)

print(f"HP: {char.hp}/{char.max_hp}")
print(f"AC: {char.ac}")
print(f"STR Modifier: {char.get_ability_modifier('strength')}")
print(f"Athletics: +{char.get_skill_bonus('Athletics')}")
```

## Validation

Before finalizing character, validate:
- Ability scores are 3-18 (after racial bonuses)
- Correct number of skills chosen
- Equipment fits class restrictions
- Spells are from class spell list
- Subclass chosen at appropriate level

## Next Steps

1. Create all 9 step templates
2. Add routes to app.py
3. JavaScript for interactive elements
4. CSS styling for visual polish
5. Integration with existing game system

The foundation is built - Open5e client and enhanced character model are ready!
