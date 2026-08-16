"""
Routes — Main Blueprint
========================
Page routes and API endpoints for the World Cup 2026 Player Database.

Page Routes:
    /                   — Home page
    /players            — Player database
    /teams              — All teams
    /teams/<nationality>— Team detail page
    /match-simulator    — Match Simulator wizard

API Routes:
    /api/players        — List/search players (JSON)
    /api/players/<id>   — Single player detail (JSON)
    /api/teams          — List teams with player counts (JSON)
    /api/match-simulator/validate-squad — Validate squad composition (JSON)
    /api/match-simulator/simulate       — Run match simulation (JSON)
"""

from flask import Blueprint, render_template, request, jsonify, current_app
import random
import logging

logger = logging.getLogger(__name__)

# Blueprint for the main site
main_bp = Blueprint('main', __name__)


# ============================================================
# Country flag emoji mapping
# ============================================================
COUNTRY_FLAGS = {
    'Brazil': 'br',
    'Argentina': 'ar',
    'France': 'fr',
    'Germany': 'de',
    'Spain': 'es',
    'England': 'gb-eng',
    'Portugal': 'pt',
    'Netherlands': 'nl',
    'USA': 'us',
    'Mexico': 'mx',
    'Japan': 'jp',
    'South Korea': 'kr',
    'Canada': 'ca',
    'Belgium': 'be',
}


# ============================================================
# PAGE ROUTES
# ============================================================

@main_bp.route('/')
def index():
    """
    Home page — Hero banner, featured players, teams overview.
    Featured players: random selection of 8 players.
    Teams: all distinct nationalities with player counts.
    """
    all_players = current_app.data_loader.players
    featured = random.sample(all_players, min(len(all_players), 8)) if all_players else []
    teams = current_app.data_loader.get_teams(COUNTRY_FLAGS)
    return render_template('index.html', featured=featured, teams=teams, flags=COUNTRY_FLAGS)


@main_bp.route('/players')
def players_page():
    """
    Player database page — Full searchable/filterable grid.
    Initial load shows all players; JS handles live search via API.
    """
    all_players = current_app.data_loader.get_all_players()

    # Get distinct values for filter dropdowns
    nationalities = current_app.data_loader.nationalities
    positions = sorted(list(set(p.primary_position for p in all_players)))
    secondary = sorted(list(set(p.secondary_position for p in all_players if p.secondary_position)))

    # Check for search query from hero redirect
    initial_query = request.args.get('q', '')

    return render_template(
        'players.html',
        players=all_players,
        nationalities=nationalities,
        positions=positions,
        secondary_positions=secondary,
        initial_query=initial_query,
        flags=COUNTRY_FLAGS,
    )


@main_bp.route('/teams')
def teams_page():
    """All teams grid page."""
    teams = current_app.data_loader.get_teams(COUNTRY_FLAGS)
    return render_template('teams.html', teams=teams, flags=COUNTRY_FLAGS)


@main_bp.route('/teams/<nationality>')
def team_detail(nationality):
    """
    Single team detail page — Shows all players for the given nationality.
    """
    players = current_app.data_loader.get_players_by_nationality(nationality)
    if not players:
        teams = current_app.data_loader.get_teams(COUNTRY_FLAGS)
        return render_template('teams.html', teams=teams, flags=COUNTRY_FLAGS), 404

    flag = COUNTRY_FLAGS.get(nationality, '🏳️')
    return render_template(
        'team_detail.html',
        nationality=nationality,
        players=players,
        flag=flag,
        flags=COUNTRY_FLAGS,
    )


@main_bp.route('/champions')
def champions():
    """
    Champions showcase page — Celebrates the World Cup 2026 Champions.
    Data is loaded from the champion_data module.
    """
    import json
    from app.champion_data import get_champion_data

    champion = get_champion_data()

    # Resolve player image URLs for all squad members (starting XI + bench)
    all_squad = champion['starting_xi'] + champion['bench']
    for player_entry in all_squad:
        _resolve_champion_player_images(player_entry)

    # Build a JSON-safe copy for JS injection
    champion_json = json.dumps(champion, default=str)

    return render_template(
        'champions.html',
        champion=champion,
        champion_json=champion_json,
        flags=COUNTRY_FLAGS,
    )


def _resolve_champion_player_images(player_entry):
    """
    Resolve frame and player image URLs for a champion squad member.
    Uses the existing data_loader image resolution system.
    """
    from flask import url_for
    import os

    nationality = player_entry.get('nationality', '')
    name = player_entry.get('name', '')

    # Use the existing sanitize_filename logic
    from app.data_loader import sanitize_filename

    country_folder = sanitize_filename(nationality)
    player_file = sanitize_filename(name) + '.png'

    player_image_rel = f'teams/{country_folder}/players/{player_file}'
    frame_image_rel = f'teams/{country_folder}/frame.png'

    static_folder = current_app.static_folder
    if not os.path.isabs(static_folder):
        static_folder = os.path.abspath(os.path.join(current_app.root_path, static_folder))
    img_base = os.path.normpath(os.path.join(static_folder, 'img'))

    # Resolve player image
    player_img_path = os.path.normpath(os.path.join(img_base, player_image_rel))
    if os.path.isfile(player_img_path):
        player_entry['player_image_url'] = url_for('static', filename='img/' + player_image_rel)
    else:
        fallback = current_app.config.get('DEFAULT_PLAYER_IMAGE', 'players/default.png')
        player_entry['player_image_url'] = url_for('static', filename='img/' + fallback)

    # Resolve frame image
    frame_img_path = os.path.normpath(os.path.join(img_base, frame_image_rel))
    if os.path.isfile(frame_img_path):
        player_entry['frame_image_url'] = url_for('static', filename='img/' + frame_image_rel)
    else:
        fallback = current_app.config.get('DEFAULT_FRAME_IMAGE', 'teams/default_frame.png')
        player_entry['frame_image_url'] = url_for('static', filename='img/' + fallback)

    # Attach overall rating from data_loader if available and not already set
    if 'overall' not in player_entry or player_entry['overall'] is None:
        country_players = current_app.data_loader.get_players_by_nationality(nationality)
        from app.data_loader import sanitize_filename
        target_sanitized = sanitize_filename(name)
        matched = next((p for p in country_players if sanitize_filename(p.name) == target_sanitized), None)
        if matched and matched.overall is not None:
            player_entry['overall'] = matched.overall


# ============================================================
# API ROUTES
# ============================================================

@main_bp.route('/api/players')
def api_players():
    """
    API: List/search players.

    Query params:
        q           — Search by name (partial match)
        nationality — Filter by exact nationality
        position    — Filter by primary position
        secondary   — Filter by secondary position
    """
    players = current_app.data_loader.players

    # Filter by nationality
    nationality = request.args.get('nationality', '').strip()
    if nationality:
        players = [p for p in players if p.nationality.lower() == nationality.lower()]

    # Filter by primary position
    position = request.args.get('position', '').strip()
    if position:
        players = [p for p in players if p.primary_position.lower() == position.lower()]

    # Filter by secondary position
    secondary = request.args.get('secondary', '').strip()
    if secondary:
        players = [p for p in players if p.secondary_position and p.secondary_position.lower() == secondary.lower()]

    # Search by name / keyword
    search = request.args.get('q', '').strip()
    if search:
        q = search.lower()
        players = [
            p for p in players
            if q in p.name.lower()
            or q in p.nationality.lower()
            or q in p.primary_position.lower()
            or (p.secondary_position and q in p.secondary_position.lower())
        ]

    # Sort players by name
    players = sorted(players, key=lambda p: p.name.lower())
    return jsonify({'players': [p.to_dict() for p in players]})


@main_bp.route('/api/players/<int:player_id>')
def api_player_detail(player_id):
    """API: Single player detail."""
    player = current_app.data_loader.get_player_by_id(player_id)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    return jsonify(player.to_dict())


@main_bp.route('/api/teams')
def api_teams():
    """API: List all teams with player counts."""
    teams = current_app.data_loader.get_teams(COUNTRY_FLAGS)
    return jsonify({'teams': teams})


# ============================================================
# MATCH SIMULATOR — PAGE ROUTE
# ============================================================

@main_bp.route('/match-simulator')
def match_simulator():
    """
    Match Simulator wizard page.
    Renders the full single-page wizard for difficulty selection,
    formation picking, squad building, and match simulation.
    """
    import json
    from app.formations import FORMATIONS, POSITION_COMPATIBILITY

    all_players = current_app.data_loader.get_all_players()
    nationalities = current_app.data_loader.nationalities
    positions = sorted(list(set(p.primary_position for p in all_players)))

    # Serialize players, formations, and position compatibility for JS
    players_json = json.dumps([p.to_dict() for p in all_players], default=str)
    formations_json = json.dumps(FORMATIONS, default=str)
    position_compatibility_json = json.dumps(POSITION_COMPATIBILITY, default=str)

    return render_template(
        'match_simulator.html',
        players_json=players_json,
        formations_json=formations_json,
        position_compatibility_json=position_compatibility_json,
        nationalities=nationalities,
        positions=positions,
        flags=COUNTRY_FLAGS,
    )


# ============================================================
# MATCH SIMULATOR — API ROUTES
# ============================================================

@main_bp.route('/api/match-simulator/validate-squad', methods=['POST'])
def api_validate_squad():
    """
    API: Validate a submitted squad (Starting XI + bench).
    Returns {valid: bool, errors: [...]}.
    """
    from app.match_validation import validate_squad
    from app.formations import FORMATIONS

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'valid': False, 'errors': ['Invalid or missing JSON body.']}), 400

    if not data:
        return jsonify({'valid': False, 'errors': ['Empty request body.']}), 400

    formation_name = data.get('formation', '')
    starting_xi = data.get('starting_xi', [])
    bench = data.get('bench', [])

    players_by_id = current_app.data_loader.players_by_id

    result = validate_squad(
        formation_name=formation_name,
        starting_xi=starting_xi,
        bench=bench,
        players_by_id=players_by_id,
        formations_dict=FORMATIONS,
    )

    status = 200 if result['valid'] else 400
    return jsonify(result), status


@main_bp.route('/api/match-simulator/simulate', methods=['POST'])
def api_simulate_match():
    """
    API: Run a full match simulation.
    Accepts difficulty, formation, starting XI, and bench.
    Returns complete match result JSON.
    """
    from app.match_validation import validate_squad
    from app.match_engine import simulate_match
    from app.formations import FORMATIONS

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Invalid or missing JSON body.'}), 400

    if not data:
        return jsonify({'error': 'Empty request body.'}), 400

    difficulty = data.get('difficulty', 'normal').lower()
    formation_name = data.get('formation', '')
    starting_xi_data = data.get('starting_xi', [])
    bench_data = data.get('bench', [])

    # Validate difficulty
    if difficulty not in ('easy', 'normal', 'hard'):
        return jsonify({'error': f"Invalid difficulty '{difficulty}'. Use: easy, normal, hard."}), 400

    # Validate formation
    formation_slots = FORMATIONS.get(formation_name)
    if not formation_slots:
        return jsonify({'error': f"Invalid formation '{formation_name}'."}), 400

    players_by_id = current_app.data_loader.players_by_id

    # Defensive re-validation before simulation
    validation = validate_squad(
        formation_name=formation_name,
        starting_xi=starting_xi_data,
        bench=bench_data,
        players_by_id=players_by_id,
        formations_dict=FORMATIONS,
    )
    if not validation['valid']:
        return jsonify({'error': 'Squad validation failed.', 'errors': validation['errors']}), 400

    # Resolve player objects
    try:
        user_starting_xi = []
        for entry in starting_xi_data:
            pid = entry['player_id']
            player = players_by_id.get(pid)
            if not player:
                return jsonify({'error': f'Player ID {pid} not found.'}), 400
            user_starting_xi.append(player)

        user_bench = []
        for entry in bench_data:
            pid = entry['player_id']
            player = players_by_id.get(pid)
            if not player:
                return jsonify({'error': f'Player ID {pid} not found.'}), 400
            user_bench.append(player)
    except (KeyError, TypeError) as e:
        logger.error(f"[ERROR] Malformed squad data: {e}")
        return jsonify({'error': 'Malformed squad data.'}), 400

    # Run simulation
    try:
        all_players = current_app.data_loader.players
        result = simulate_match(
            user_starting_xi_players=user_starting_xi,
            user_bench_players=user_bench,
            formation_slots=formation_slots,
            difficulty=difficulty,
            all_players=all_players,
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"[ERROR] Match simulation failed: {e}")
        return jsonify({'error': 'An internal error occurred during simulation.'}), 500


# ============================================================
# SAVED SQUADS — API ROUTES
# ============================================================

@main_bp.route('/api/saved-squads', methods=['GET'])
def api_list_saved_squads():
    """
    API: List all saved squads with metadata and player counts.
    Returns JSON list sorted by last updated (newest first).
    """
    from app.saved_squads_db import list_squads, get_db_path
    db_path = get_db_path(current_app)
    squads = list_squads(db_path)
    return jsonify({'squads': squads})


@main_bp.route('/api/saved-squads/<int:squad_id>', methods=['GET'])
def api_get_saved_squad(squad_id):
    """
    API: Retrieve one saved squad with fully resolved player data.
    Each player includes an 'available' flag — False if the player
    no longer exists in the current CSV data.
    """
    from app.saved_squads_db import get_squad_raw, get_db_path
    db_path = get_db_path(current_app)

    squad_data = get_squad_raw(db_path, squad_id)
    if not squad_data:
        return jsonify({'error': f'Saved squad with ID {squad_id} not found.'}), 404

    players_by_id = current_app.data_loader.players_by_id

    # Resolve player data, marking unavailable players
    starters = []
    bench_players = []

    for p_ref in squad_data['players']:
        player_obj = players_by_id.get(p_ref['player_id'])

        if player_obj:
            resolved = player_obj.to_dict()
            resolved['available'] = True
            resolved['role'] = p_ref['role']
            resolved['slot'] = p_ref['slot']
        else:
            # Player no longer exists in CSV data
            resolved = {
                'id': p_ref['player_id'],
                'name': f'Unknown Player (ID: {p_ref["player_id"]})',
                'nationality': '',
                'primary_position': '',
                'secondary_position': None,
                'overall': 0,
                'player_image_url': '',
                'frame_image_url': '',
                'available': False,
                'role': p_ref['role'],
                'slot': p_ref['slot'],
            }

        if p_ref['role'] == 'starter':
            starters.append(resolved)
        else:
            bench_players.append(resolved)

    return jsonify({
        'id': squad_data['id'],
        'name': squad_data['name'],
        'formation': squad_data['formation'],
        'created_at': squad_data['created_at'],
        'updated_at': squad_data['updated_at'],
        'starters': starters,
        'bench': bench_players,
    })


@main_bp.route('/api/saved-squads', methods=['POST'])
def api_create_saved_squad():
    """
    API: Create a new saved squad.
    Validates via the existing validate_squad() before inserting.
    """
    from app.match_validation import validate_squad, get_position_category
    from app.formations import FORMATIONS
    from app.saved_squads_db import create_squad, get_db_path

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Invalid or missing JSON body.'}), 400

    if not data:
        return jsonify({'error': 'Empty request body.'}), 400

    # Extract and validate name
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Squad name is required.'}), 400

    formation_name = data.get('formation', '')
    starting_xi_data = data.get('starting_xi', [])
    bench_data = data.get('bench', [])

    players_by_id = current_app.data_loader.players_by_id

    # Reuse existing squad validation
    validation = validate_squad(
        formation_name=formation_name,
        starting_xi=starting_xi_data,
        bench=bench_data,
        players_by_id=players_by_id,
        formations_dict=FORMATIONS,
    )
    if not validation['valid']:
        return jsonify({'error': 'Squad validation failed.', 'errors': validation['errors']}), 400

    # Build DB-ready player lists
    starters = []
    for entry in starting_xi_data:
        starters.append({
            'player_id': entry['player_id'],
            'slot': str(entry['slot_index']),
        })

    bench_players = []
    for entry in bench_data:
        pid = entry['player_id']
        player = players_by_id.get(pid)
        category = get_position_category(player.primary_position) if player else 'MID'
        bench_players.append({
            'player_id': pid,
            'slot': category,
        })

    db_path = get_db_path(current_app)
    squad_id = create_squad(db_path, name, formation_name, starters, bench_players)

    return jsonify({'id': squad_id, 'message': f"Squad '{name}' saved successfully."}), 201


@main_bp.route('/api/saved-squads/<int:squad_id>', methods=['PUT'])
def api_update_saved_squad(squad_id):
    """
    API: Update an existing saved squad (rename and/or replace players).
    Validates via the existing validate_squad() before updating.
    """
    from app.match_validation import validate_squad, get_position_category
    from app.formations import FORMATIONS
    from app.saved_squads_db import update_squad, get_squad_raw, get_db_path

    db_path = get_db_path(current_app)

    # Verify squad exists
    existing = get_squad_raw(db_path, squad_id)
    if not existing:
        return jsonify({'error': f'Saved squad with ID {squad_id} not found.'}), 404

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Invalid or missing JSON body.'}), 400

    if not data:
        return jsonify({'error': 'Empty request body.'}), 400

    # Extract and validate name
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Squad name is required.'}), 400

    formation_name = data.get('formation', '')
    starting_xi_data = data.get('starting_xi', [])
    bench_data = data.get('bench', [])

    players_by_id = current_app.data_loader.players_by_id

    # Reuse existing squad validation
    validation = validate_squad(
        formation_name=formation_name,
        starting_xi=starting_xi_data,
        bench=bench_data,
        players_by_id=players_by_id,
        formations_dict=FORMATIONS,
    )
    if not validation['valid']:
        return jsonify({'error': 'Squad validation failed.', 'errors': validation['errors']}), 400

    # Build DB-ready player lists
    starters = []
    for entry in starting_xi_data:
        starters.append({
            'player_id': entry['player_id'],
            'slot': str(entry['slot_index']),
        })

    bench_players = []
    for entry in bench_data:
        pid = entry['player_id']
        player = players_by_id.get(pid)
        category = get_position_category(player.primary_position) if player else 'MID'
        bench_players.append({
            'player_id': pid,
            'slot': category,
        })

    update_squad(db_path, squad_id, name, formation_name, starters, bench_players)

    return jsonify({'id': squad_id, 'message': f"Squad '{name}' updated successfully."})


@main_bp.route('/api/saved-squads/<int:squad_id>', methods=['DELETE'])
def api_delete_saved_squad(squad_id):
    """
    API: Delete a saved squad (cascades to player associations).
    """
    from app.saved_squads_db import delete_squad, get_db_path

    db_path = get_db_path(current_app)
    deleted = delete_squad(db_path, squad_id)

    if not deleted:
        return jsonify({'error': f'Saved squad with ID {squad_id} not found.'}), 404

    return jsonify({'message': f'Squad deleted successfully.'})


@main_bp.route('/api/saved-squads/<int:squad_id>/duplicate', methods=['POST'])
def api_duplicate_saved_squad(squad_id):
    """
    API: Duplicate an existing saved squad under a new name.
    """
    from app.saved_squads_db import duplicate_squad, get_db_path

    db_path = get_db_path(current_app)

    # Optional new name from request body
    new_name = None
    try:
        data = request.get_json(silent=True)
        if data:
            new_name = (data.get('name') or '').strip() or None
    except Exception:
        pass

    new_id = duplicate_squad(db_path, squad_id, new_name)

    if new_id is None:
        return jsonify({'error': f'Saved squad with ID {squad_id} not found.'}), 404

    return jsonify({'id': new_id, 'message': 'Squad duplicated successfully.'}), 201


