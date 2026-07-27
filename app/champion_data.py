"""
Champion Data Module
=====================
Single source of truth for the World Cup Champions page.

To update the champion (e.g. replace Spain with another nation),
edit the CHAMPION_DATA dictionary below. No template or route
changes are required.

Structure:
    nation       — Champion country details
    stats        — Tournament statistics
    starting_xi  — 11 starting players with formation positions
    bench        — 7 substitute players
    journey      — Knockout stage results (Road to Glory)
    hero_image   — Relative path to hero background image
"""


CHAMPION_DATA = {

    # ─── Nation ───────────────────────────────────────────────
    "nation": {
        "name": "Spain",
        "flag_code": "es",
        "subtitle": "La Roja",
        "captain": "Rodri",
        "coach": "Luis de la Fuente",
    },

    # ─── Hero Background ─────────────────────────────────────
    # Relative to static/img/  — swap this path to change the hero image
    "hero_image": "champions/hero-bg.jpg",

    # ─── Tournament Statistics ────────────────────────────────
    "stats": {
        "matches_played": 8,
        "wins": 7,
        "draws": 1,
        "losses": 0,
        "goals_scored": 14,
        "goals_conceded": 1,
        "clean_sheets": 7,
    },

    # ─── Starting XI ─────────────────────────────────────────
    # Formation: 4-2-3-1
    #
    #              ST
    #     LW      CAM      RW
    #         CM      CM
    #    LB  CB      CB  RB
    #             GK
    #
    # Each player has:
    #   name, number, position, nationality, formation_row, formation_order,
    #   tournament stats, awards list, is_captain flag
    "starting_xi": [
        {
            "name": "Unai Simón",
            "number": 1,
            "position": "GK",
            "nationality": "Spain",
            "formation_row": 5,  # Bottom row (GK)
            "formation_order": 1,
            "is_captain": False,
            "stats": {
                "matches": 8,
                "goals": 0,
                "assists": 0,
                "minutes": 720,
                "avg_rating": 7.2,
            },
            "awards": [],
        },
        {
            "name": "Pedro Porro",
            "number": 2,
            "position": "RB",
            "nationality": "Spain",
            "formation_row": 4,  # Defense
            "formation_order": 4,
            "is_captain": False,
            "stats": {
                "matches": 7,
                "goals": 1,
                "assists": 2,
                "minutes": 598,
                "avg_rating": 7.0,
            },
            "awards": [],
        },
        {
            "name": "Pau Cubarsí",
            "number": 4,
            "position": "CB",
            "nationality": "Spain",
            "formation_row": 4,
            "formation_order": 3,
            "is_captain": False,
            "stats": {
                "matches": 8,
                "goals": 0,
                "assists": 0,
                "minutes": 720,
                "avg_rating": 7.3,
            },
            "awards": ["Best Young Player"],
        },
        {
            "name": "Aymeric Laporte",
            "number": 5,
            "position": "CB",
            "nationality": "Spain",
            "formation_row": 4,
            "formation_order": 2,
            "is_captain": False,
            "stats": {
                "matches": 8,
                "goals": 1,
                "assists": 0,
                "minutes": 720,
                "avg_rating": 7.4,
            },
            "awards": [],
        },
        {
            "name": "Marc Cucurella",
            "number": 3,
            "position": "LB",
            "nationality": "Spain",
            "formation_row": 4,
            "formation_order": 1,
            "is_captain": False,
            "stats": {
                "matches": 7,
                "goals": 0,
                "assists": 3,
                "minutes": 612,
                "avg_rating": 7.1,
            },
            "awards": [],
        },
        {
            "name": "Rodri",
            "number": 6,
            "position": "CDM",
            "nationality": "Spain",
            "formation_row": 3,  # Midfield
            "formation_order": 1,
            "is_captain": True,
            "stats": {
                "matches": 8,
                "goals": 2,
                "assists": 3,
                "minutes": 720,
                "avg_rating": 8.3,
            },
            "awards": ["Golden Ball"],
        },
        {
            "name": "Fabian Ruiz",
            "number": 8,
            "position": "CM",
            "nationality": "Spain",
            "formation_row": 3,
            "formation_order": 2,
            "is_captain": False,
            "stats": {
                "matches": 8,
                "goals": 2,
                "assists": 4,
                "minutes": 680,
                "avg_rating": 7.9,
            },
            "awards": [],
        },
        {
            "name": "Alex Baena",
            "number": 11,
            "position": "LW",
            "nationality": "Spain",
            "formation_row": 2,  # Attacking midfield / wings
            "formation_order": 1,
            "is_captain": False,
            "stats": {
                "matches": 8,
                "goals": 3,
                "assists": 3,
                "minutes": 650,
                "avg_rating": 7.8,
            },
            "awards": [],
        },
        {
            "name": "Dani Olmo",
            "number": 10,
            "position": "CAM",
            "nationality": "Spain",
            "formation_row": 2,
            "formation_order": 2,
            "is_captain": False,
            "stats": {
                "matches": 8,
                "goals": 4,
                "assists": 2,
                "minutes": 590,
                "avg_rating": 7.7,
            },
            "awards": [],
        },
        {
            "name": "Lamine Yamal",
            "number": 7,
            "position": "RW",
            "nationality": "Spain",
            "formation_row": 2,
            "formation_order": 3,
            "is_captain": False,
            "stats": {
                "matches": 8,
                "goals": 3,
                "assists": 4,
                "minutes": 670,
                "avg_rating": 8.1,
            },
            "awards": ["Best Young Player Runner-Up"],
        },
        {
            "name": "Mikel Oyarzabal",
            "number": 9,
            "position": "ST",
            "nationality": "Spain",
            "formation_row": 1,  # Top row (Striker)
            "formation_order": 1,
            "is_captain": False,
            "stats": {
                "matches": 7,
                "goals": 3,
                "assists": 1,
                "minutes": 510,
                "avg_rating": 7.3,
            },
            "awards": [],
        },
    ],

    # ─── Bench (7 substitutes) ────────────────────────────────
    "bench": [
        {
            "name": "David Raya",
            "number": 13,
            "position": "GK",
            "nationality": "Spain",
            "is_captain": False,
            "stats": {
                "matches": 0,
                "goals": 0,
                "assists": 0,
                "minutes": 0,
                "avg_rating": 0.0,
            },
            "awards": [],
        },
        {
            "name": "Alejandro Grimaldo",
            "number": 14,
            "position": "LB",
            "nationality": "Spain",
            "is_captain": False,
            "stats": {
                "matches": 4,
                "goals": 0,
                "assists": 1,
                "minutes": 178,
                "avg_rating": 6.8,
            },
            "awards": [],
        },
        {
            "name": "Eric García",
            "number": 15,
            "position": "CB",
            "nationality": "Spain",
            "is_captain": False,
            "stats": {
                "matches": 2,
                "goals": 0,
                "assists": 0,
                "minutes": 110,
                "avg_rating": 6.7,
            },
            "awards": [],
        },
        {
            "name": "Nico Williams",
            "number": 11,
            "position": "LW",
            "nationality": "Spain",
            "is_captain": False,
            "stats": {
                "matches": 5,
                "goals": 0,
                "assists": 1,
                "minutes": 245,
                "avg_rating": 7.0,
            },
            "awards": [],
        },
        {
            "name": "Pedri",
            "number": 20,
            "position": "CM",
            "nationality": "Spain",
            "is_captain": False,
            "stats": {
                "matches": 6,
                "goals": 1,
                "assists": 2,
                "minutes": 320,
                "avg_rating": 7.2,
            },
            "awards": [],
        },
        {
            "name": "Ferran Torres",
            "number": 18,
            "position": "ST",
            "nationality": "Spain",
            "is_captain": False,
            "stats": {
                "matches": 5,
                "goals": 2,
                "assists": 0,
                "minutes": 215,
                "avg_rating": 6.9,
            },
            "awards": [],
        },
        {
            "name": "Mikel Merino",
            "number": 19,
            "position": "CM",
            "nationality": "Spain",
            "is_captain": False,
            "stats": {
                "matches": 4,
                "goals": 1,
                "assists": 0,
                "minutes": 190,
                "avg_rating": 6.8,
            },
            "awards": [],
        },
    ],

    # ─── Road to Glory (Knockout Journey) ─────────────────────
    "journey": [
        {
            "round": "Round of 32",
            "opponent": "Austria",
            "opponent_flag": "at",
            "result": "W",
            "score": "3  0",
            "date": "July 03, 2026",
        },
        {
            "round": "Round of 16",
            "opponent": "Portugal",
            "opponent_flag": "pt",
            "result": "W",
            "score": "1  0",
            "date": "July 07, 2026",
        },
        {
            "round": "Quarter Final",
            "opponent": "Belgium",
            "opponent_flag": "be",
            "result": "W",
            "score": "2  1",
            "date": "July 11, 2026",
        },
        {
            "round": "Semi Final",
            "opponent": "France",
            "opponent_flag": "fr",
            "result": "W",
            "score": "2  0",
            "date": "July 15, 2026",
        },
        {
            "round": "Final",
            "opponent": "Argentina",
            "opponent_flag": "ar",
            "result": "W",
            "score": "1 0",
            "date": "July 20, 2026",
            "is_final": True,
        },
    ],
}


def get_champion_data():
    """
    Return a copy of the champion data dictionary.
    Used by the route handler to pass data to the template.
    """
    return CHAMPION_DATA.copy()
