"""
Formations Module
==================
Defines the five supported formations for the Match Simulator.

Each formation maps to a list of 11 slot definitions with:
    - position:        Tactical position label (GK/CB/LB/RB/CDM/CM/CAM/LW/RW/ST)
    - formation_row:   Vertical row on the pitch (1 = top/strikers, highest = GK)
    - formation_order: Left-to-right ordering within a row (1 = leftmost)

Row numbering follows the existing Champions page convention where
row 1 is the topmost (attackers) and the last row is GK.
"""

FORMATIONS = {
    "4-3-3": [
        {"position": "LW",  "formation_row": 1, "formation_order": 1},
        {"position": "ST",  "formation_row": 1, "formation_order": 2},
        {"position": "RW",  "formation_row": 1, "formation_order": 3},
        {"position": "CM",  "formation_row": 2, "formation_order": 1},
        {"position": "CM",  "formation_row": 2, "formation_order": 2},
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
        {"position": "LW",  "formation_row": 2, "formation_order": 1},
        {"position": "CM",  "formation_row": 2, "formation_order": 2},
        {"position": "CM",  "formation_row": 2, "formation_order": 3},
        {"position": "RW",  "formation_row": 2, "formation_order": 4},
        {"position": "LB",  "formation_row": 3, "formation_order": 1},
        {"position": "CB",  "formation_row": 3, "formation_order": 2},
        {"position": "CB",  "formation_row": 3, "formation_order": 3},
        {"position": "RB",  "formation_row": 3, "formation_order": 4},
        {"position": "GK",  "formation_row": 4, "formation_order": 1},
    ],
    "3-5-2": [
        {"position": "ST",  "formation_row": 1, "formation_order": 1},
        {"position": "ST",  "formation_row": 1, "formation_order": 2},
        {"position": "LW",  "formation_row": 2, "formation_order": 1},
        {"position": "CM",  "formation_row": 2, "formation_order": 2},
        {"position": "CM",  "formation_row": 2, "formation_order": 3},
        {"position": "CM",  "formation_row": 2, "formation_order": 4},
        {"position": "RW",  "formation_row": 2, "formation_order": 5},
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
