"""
Routes — Main Blueprint
========================
Page routes and API endpoints for the World Cup 2026 Player Database.

Page Routes:
    /                   — Home page
    /players            — Player database
    /teams              — All teams
    /teams/<nationality>— Team detail page
    /dashboard          — User dashboard (UI only)

API Routes:
    /api/players        — List/search players (JSON)
    /api/players/<id>   — Single player detail (JSON)
    /api/teams          — List teams with player counts (JSON)
"""

from flask import Blueprint, render_template, request, jsonify, current_app
import random

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


@main_bp.route('/dashboard')
def dashboard():
    """
    User dashboard — UI only, no authentication.
    Shows placeholder Favorite XI, bench, recently viewed, and favorites.
    """
    return render_template('dashboard.html')


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

