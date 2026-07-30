"""
Match Validation Module
========================
Framework-agnostic squad validation for the Match Simulator.
No Flask-specific imports — takes plain Python data in, returns
structured validation results.

Position category mapping:
    GK  → GK
    CB, LB, RB → DEF
    CDM, CM, CAM → MID
    LW, RW, ST → ATT

Unknown positions default to MID with a log warning.
"""

import logging

logger = logging.getLogger(__name__)

# ── Position Category Mapping ──────────────────────────────────
POSITION_CATEGORIES = {
    'GK': 'GK',
    'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF',
    'CDM': 'MID', 'CM': 'MID', 'CAM': 'MID',
    'LW': 'ATT', 'RW': 'ATT', 'ST': 'ATT',
}

# Required bench composition
BENCH_COMPOSITION = {
    'GK': 1,
    'DEF': 2,
    'MID': 2,
    'ATT': 2,
}


def get_position_category(position):
    """
    Map a position string to its category (GK/DEF/MID/ATT).
    Unknown positions default to MID with a warning.
    """
    category = POSITION_CATEGORIES.get(position)
    if category is None:
        logger.warning(f"[WARNING] Unknown position '{position}' — defaulting to MID category.")
        return 'MID'
    return category


def validate_squad(formation_name, starting_xi, bench, players_by_id, formations_dict):
    """
    Validate a submitted squad for the Match Simulator.

    Args:
        formation_name: Name of the selected formation (e.g. '4-3-3').
        starting_xi:    List of dicts with 'player_id' and 'slot_index' keys.
        bench:          List of dicts with 'player_id' key.
        players_by_id:  Dict mapping player ID (int) → Player object.
        formations_dict: The FORMATIONS dict from formations.py.

    Returns:
        Dict with 'valid' (bool) and 'errors' (list of str).
    """
    errors = []

    # ── Rule 0: Formation must exist ───────────────────────────
    formation = formations_dict.get(formation_name)
    if not formation:
        errors.append(f"Invalid formation '{formation_name}'. Supported: {', '.join(formations_dict.keys())}.")
        # Can't validate further without a valid formation
        return {'valid': False, 'errors': errors}

    # ── Rule 1: Exactly 11 starting players ────────────────────
    if not isinstance(starting_xi, list):
        errors.append("Starting XI must be a list.")
    elif len(starting_xi) != 11:
        errors.append(f"Starting XI requires exactly 11 players, got {len(starting_xi)}.")

    # Check slot indices are valid (0–10, one per slot)
    if isinstance(starting_xi, list) and len(starting_xi) == 11:
        slot_indices = [entry.get('slot_index') for entry in starting_xi if isinstance(entry, dict)]
        expected_slots = set(range(11))
        actual_slots = set(slot_indices)
        if actual_slots != expected_slots:
            missing = expected_slots - actual_slots
            if missing:
                errors.append(f"Missing formation slot(s): {sorted(missing)}.")

    # ── Rule 2: Exactly 7 bench players ────────────────────────
    if not isinstance(bench, list):
        errors.append("Bench must be a list.")
    elif len(bench) != 7:
        errors.append(f"Bench requires exactly 7 players, got {len(bench)}.")

    # ── Collect all player IDs ─────────────────────────────────
    xi_ids = []
    if isinstance(starting_xi, list):
        for entry in starting_xi:
            if isinstance(entry, dict) and 'player_id' in entry:
                xi_ids.append(entry['player_id'])

    bench_ids = []
    if isinstance(bench, list):
        for entry in bench:
            if isinstance(entry, dict) and 'player_id' in entry:
                bench_ids.append(entry['player_id'])

    all_ids = xi_ids + bench_ids

    # ── Rule 5: All player IDs must exist ──────────────────────
    invalid_ids = [pid for pid in all_ids if pid not in players_by_id]
    if invalid_ids:
        errors.append(f"Unknown player ID(s): {invalid_ids}.")

    # ── Rule 4: No duplicate player IDs ────────────────────────
    seen = set()
    duplicates = set()
    for pid in all_ids:
        if pid in seen:
            duplicates.add(pid)
        seen.add(pid)
    if duplicates:
        dup_names = []
        for pid in duplicates:
            player = players_by_id.get(pid)
            dup_names.append(player.name if player else f"ID {pid}")
        errors.append(f"Duplicate player(s) in squad: {', '.join(dup_names)}.")

    # ── Rule 3: Bench composition (1 GK / 2 DEF / 2 MID / 2 ATT) ──
    if isinstance(bench, list) and len(bench) == 7 and not invalid_ids:
        bench_categories = {'GK': 0, 'DEF': 0, 'MID': 0, 'ATT': 0}
        for entry in bench:
            if isinstance(entry, dict) and 'player_id' in entry:
                pid = entry['player_id']
                player = players_by_id.get(pid)
                if player:
                    cat = get_position_category(player.primary_position)
                    bench_categories[cat] = bench_categories.get(cat, 0) + 1

        for cat, required in BENCH_COMPOSITION.items():
            actual = bench_categories.get(cat, 0)
            if actual != required:
                cat_label = {'GK': 'Goalkeeper', 'DEF': 'Defender', 'MID': 'Midfielder', 'ATT': 'Attacker'}.get(cat, cat)
                errors.append(
                    f"Bench requires {required} {cat_label}(s), got {actual}."
                )

    return {
        'valid': len(errors) == 0,
        'errors': errors,
    }
