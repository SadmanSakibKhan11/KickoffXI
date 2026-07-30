"""
Formations & Position Compatibility Module
===========================================
Defines the five supported formations and the centralized Position Compatibility
System for the Match Simulator.

Position Compatibility System:
    Maps tactical slot positions to compatible player positions.
    Reused across frontend player picking, backend squad validation,
    and AI squad generation.

Formations map to a list of 11 slot definitions with:
    - position:        Tactical position label (GK/CB/LB/RB/CDM/CM/CAM/LW/RW/ST)
    - formation_row:   Vertical row on the pitch (1 = top/strikers, highest = GK)
    - formation_order: Left-to-right ordering within a row (1 = leftmost)
"""

POSITION_COMPATIBILITY = {
    'GK': ['GK'],
    'LB': ['LB', 'LWB', 'RB', 'RWB', 'CB'],
    'LWB': ['LWB', 'LB', 'RB', 'RWB', 'CB'],
    'RB': ['RB', 'RWB', 'LB', 'LWB', 'CB'],
    'RWB': ['RWB', 'RB', 'LB', 'LWB', 'CB'],
    'CB': ['CB', 'RB', 'LB'],
    'CDM': ['CDM', 'CM'],
    'CM': ['CM', 'CDM', 'CAM'],
    'CAM': ['CAM', 'CM', 'CF', "ST"],
    'LW': ['LW', 'LM','RW'],
    'LM': ['LM', 'LW','RM',],
    'RW': ['RW', 'RM','LW'],
    'RM': ['RM', 'RW','LM'],
    'ST': ['ST', 'CF', "CAM","LW", "RW"],
    'CF': ['CF', 'ST', 'CAM'],
}

FORMATIONS = {
    "4-3-3": [
        {"position": "LW",  "formation_row": 1, "formation_order": 1},
        {"position": "ST",  "formation_row": 1, "formation_order": 2},
        {"position": "RW",  "formation_row": 1, "formation_order": 3},
        {"position": "CM",  "formation_row": 2, "formation_order": 1},
        {"position": "CAM",  "formation_row": 2, "formation_order": 2},
        {"position": "CM",  "formation_row": 2, "formation_order": 3},
        {"position": "LB",  "formation_row": 3, "formation_order": 1},
        {"position": "CB",  "formation_row": 3, "formation_order": 2},
        {"position": "CB",  "formation_row": 3, "formation_order": 3},
        {"position": "RB",  "formation_row": 3, "formation_order": 4},
        {"position": "GK",  "formation_row": 4, "formation_order": 1},
    ],
    "4-2-3-1": [
        {"position": "ST",  "formation_row": 1, "formation_order": 1},
        {"position": "LW",  "formation_row": 2, "formation_order": 1},
        {"position": "CAM", "formation_row": 2, "formation_order": 2},
        {"position": "RW",  "formation_row": 2, "formation_order": 3},
        {"position": "CDM", "formation_row": 3, "formation_order": 1},
        {"position": "CDM", "formation_row": 3, "formation_order": 2},
        {"position": "LB",  "formation_row": 4, "formation_order": 1},
        {"position": "CB",  "formation_row": 4, "formation_order": 2},
        {"position": "CB",  "formation_row": 4, "formation_order": 3},
        {"position": "RB",  "formation_row": 4, "formation_order": 4},
        {"position": "GK",  "formation_row": 5, "formation_order": 1},
    ],
    "4-4-2": [
        {"position": "ST",  "formation_row": 1, "formation_order": 1},
        {"position": "ST",  "formation_row": 1, "formation_order": 2},
        {"position": "LM",  "formation_row": 2, "formation_order": 1},
        {"position": "CM",  "formation_row": 2, "formation_order": 2},
        {"position": "CM",  "formation_row": 2, "formation_order": 3},
        {"position": "RM",  "formation_row": 2, "formation_order": 4},
        {"position": "LB",  "formation_row": 3, "formation_order": 1},
        {"position": "CB",  "formation_row": 3, "formation_order": 2},
        {"position": "CB",  "formation_row": 3, "formation_order": 3},
        {"position": "RB",  "formation_row": 3, "formation_order": 4},
        {"position": "GK",  "formation_row": 4, "formation_order": 1},
    ],
    "3-5-2": [
        {"position": "ST",  "formation_row": 1, "formation_order": 1},
        {"position": "ST",  "formation_row": 1, "formation_order": 2},
        {"position": "LM",  "formation_row": 2, "formation_order": 1},
        {"position": "CM",  "formation_row": 2, "formation_order": 2},
        {"position": "CAM",  "formation_row": 2, "formation_order": 3},
        {"position": "CM",  "formation_row": 2, "formation_order": 4},
        {"position": "RM",  "formation_row": 2, "formation_order": 5},
        {"position": "CB",  "formation_row": 3, "formation_order": 1},
        {"position": "CB",  "formation_row": 3, "formation_order": 2},
        {"position": "CB",  "formation_row": 3, "formation_order": 3},
        {"position": "GK",  "formation_row": 4, "formation_order": 1},
    ],
    "4-1-2-1-2": [
        {"position": "ST",  "formation_row": 1, "formation_order": 1},
        {"position": "ST",  "formation_row": 1, "formation_order": 2},
        {"position": "CAM", "formation_row": 2, "formation_order": 1},
        {"position": "CM",  "formation_row": 3, "formation_order": 1},
        {"position": "CM",  "formation_row": 3, "formation_order": 2},
        {"position": "CDM", "formation_row": 4, "formation_order": 1},
        {"position": "LB",  "formation_row": 5, "formation_order": 1},
        {"position": "CB",  "formation_row": 5, "formation_order": 2},
        {"position": "CB",  "formation_row": 5, "formation_order": 3},
        {"position": "RB",  "formation_row": 5, "formation_order": 4},
        {"position": "GK",  "formation_row": 6, "formation_order": 1},
    ],
}


def get_formation(name):
    """
    Retrieve a formation by name.

    Args:
        name: Formation name string (e.g. '4-3-3').

    Returns:
        List of 11 slot dicts if found, None otherwise.
    """
    return FORMATIONS.get(name)


def get_formation_names():
    """Return list of all supported formation names."""
    return list(FORMATIONS.keys())


def parse_player_positions(primary_pos, secondary_pos=None):
    """
    Parse a player's primary and secondary positions into a clean list of position strings.
    Handles comma-separated secondary positions like 'CM,RM'.
    """
    positions = []
    if primary_pos:
        positions.append(primary_pos.strip())
    if secondary_pos:
        for p in secondary_pos.split(','):
            p_clean = p.strip()
            if p_clean and p_clean not in positions:
                positions.append(p_clean)
    return positions


def get_compatible_positions(pos):
    """
    Return list of compatible position strings for a given slot position.
    """
    if not pos:
        return []
    pos_clean = pos.strip()
    return POSITION_COMPATIBILITY.get(pos_clean, [pos_clean] if pos_clean else [])


def is_player_compatible(primary_pos, secondary_pos, required_slot_pos):
    """
    Returns True if any of the player's positions (primary or secondary)
    is compatible with required_slot_pos.
    """
    player_positions = parse_player_positions(primary_pos, secondary_pos)
    compatible_targets = set(get_compatible_positions(required_slot_pos))
    return any(p in compatible_targets for p in player_positions)
