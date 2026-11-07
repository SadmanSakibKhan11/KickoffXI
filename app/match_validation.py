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

from app.formations import is_player_compatible

# ── Position Category Mapping ──────────────────────────────────
POSITION_CATEGORIES = {
    'GK': 'GK',
    'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF', 'LWB': 'DEF', 'RWB': 'DEF',
    'CDM': 'MID', 'CM': 'MID', 'CAM': 'MID', 'LM': 'MID', 'RM': 'MID',
    'LW': 'ATT', 'RW': 'ATT', 'ST': 'ATT', 'CF': 'ATT',
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
    Validate a submitted squad for the Match Simulator and Saved Squads.

    Requirements enforced:
    - Formation must be valid and supported.
    - Exactly 11 starting players in valid dictionary format.
    - Exactly 7 bench players in valid dictionary format.
    - Exactly 18 players in total.
    - Every starter must have a valid integer slot_index (0..10) without duplicates.
    - Every player must have a valid integer player_id existing in the database.
    - No duplicate player IDs anywhere in the squad.
    - Starters must be position-compatible with their assigned formation slots.
    - Bench must consist of exactly 1 GK, 2 DEF, 2 MID, 2 ATT.

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
    if not isinstance(formation_name, str) or not formation_name:
        errors.append("Formation name is required.")
        return {'valid': False, 'errors': errors}

    formation = formations_dict.get(formation_name)
    if not formation:
        errors.append(f"Invalid formation '{formation_name}'. Supported: {', '.join(formations_dict.keys())}.")
        return {'valid': False, 'errors': errors}

    # ── Rule 1: Exactly 11 starting players ────────────────────
    if not isinstance(starting_xi, list):
        errors.append("Starting XI must be a list.")
    elif len(starting_xi) != 11:
        errors.append(f"Starting XI requires exactly 11 players, got {len(starting_xi)}.")

    # ── Rule 2: Exactly 7 bench players ────────────────────────
    if not isinstance(bench, list):
        errors.append("Bench must be a list.")
    elif len(bench) != 7:
        errors.append(f"Bench requires exactly 7 players, got {len(bench)}.")

    # Validate structure and extract slots/IDs from starting XI
    xi_ids = []
    has_starter_type_error = False
    if isinstance(starting_xi, list):
        slot_indices = []
        for idx, entry in enumerate(starting_xi):
            if not isinstance(entry, dict):
                errors.append(f"Starting XI entry at index {idx} must be an object.")
                has_starter_type_error = True
                continue

            # Slot index validation
            slot_idx = entry.get('slot_index')
            if slot_idx is None or type(slot_idx) is not int or not (0 <= slot_idx <= 10):
                errors.append(f"Starting XI entry at index {idx} has invalid slot_index '{slot_idx}'. Must be an integer 0–10.")
            else:
                slot_indices.append(slot_idx)

            # Player ID validation
            pid = entry.get('player_id')
            if pid is None or type(pid) is not int or pid <= 0:
                errors.append(f"Starting XI entry at index {idx} has invalid or missing player_id.")
            else:
                xi_ids.append(pid)

        # Check all 11 slots are uniquely covered
        if len(starting_xi) == 11 and not has_starter_type_error:
            expected_slots = set(range(11))
            actual_slots = set(slot_indices)
            if actual_slots != expected_slots:
                missing = expected_slots - actual_slots
                if missing:
                    errors.append(f"Missing formation slot(s): {sorted(missing)}.")
                if len(slot_indices) != len(actual_slots):
                    errors.append("Duplicate slot_index found in starting XI.")

    # Validate structure and extract IDs from bench
    bench_ids = []
    if isinstance(bench, list):
        for idx, entry in enumerate(bench):
            if not isinstance(entry, dict):
                errors.append(f"Bench entry at index {idx} must be an object.")
                continue

            pid = entry.get('player_id')
            if pid is None or type(pid) is not int or pid <= 0:
                errors.append(f"Bench entry at index {idx} has invalid or missing player_id.")
            else:
                bench_ids.append(pid)

    all_ids = xi_ids + bench_ids

    # ── Rule 3: Total player count must be exactly 18 ──────────
    if isinstance(starting_xi, list) and isinstance(bench, list):
        if len(starting_xi) == 11 and len(bench) == 7 and len(all_ids) != 18:
            errors.append(f"Squad must contain exactly 18 valid players, got {len(all_ids)}.")

    # ── Rule 4: All player IDs must exist in database ──────────
    invalid_ids = [pid for pid in all_ids if pid not in players_by_id]
    if invalid_ids:
        errors.append(f"Unknown player ID(s): {invalid_ids}.")

    # ── Rule 5: No duplicate player IDs anywhere in squad ──────
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

    # ── Rule 6: Starting XI Position Compatibility ─────────────
    if isinstance(starting_xi, list) and len(starting_xi) == 11 and formation and not invalid_ids:
        for entry in starting_xi:
            if isinstance(entry, dict):
                slot_idx = entry.get('slot_index')
                pid = entry.get('player_id')
                if type(slot_idx) is int and 0 <= slot_idx < len(formation) and type(pid) is int:
                    slot_pos = formation[slot_idx]['position']
                    player = players_by_id.get(pid)
                    if player:
                        if not is_player_compatible(player.primary_position, player.secondary_position, slot_pos):
                            errors.append(
                                f"Player '{player.name}' ({player.primary_position}) is not position-compatible with slot '{slot_pos}'."
                            )

    # ── Rule 7: Bench composition (1 GK / 2 DEF / 2 MID / 2 ATT) ──
    if isinstance(bench, list) and len(bench) == 7 and not invalid_ids and len(bench_ids) == 7:
        bench_categories = {'GK': 0, 'DEF': 0, 'MID': 0, 'ATT': 0}
        for pid in bench_ids:
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
