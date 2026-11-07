"""
Match Simulator & Squad Validation Tests
========================================
Comprehensive unit and integration tests for Task 5:
- Squad validation rules (11 starters, 7 bench, 18 total, no duplicates, valid IDs, compatible positions, bench balance)
- Defensive rejection of malformed payloads and invalid slot indexes
- Team strength calculation consistency
- Win / Draw / Loss match probability calculation:
  - Equal strength
  - Moderate advantage / disadvantage
  - Extreme strength differentials
  - Strict 0–100% boundary enforcement and exact 100.0% sum
  - Robust handling of invalid/missing inputs
- Full Match Simulator API endpoint validation and response structure
"""

import pytest
from unittest.mock import patch, MagicMock

from app.match_validation import validate_squad, get_position_category
from app.formations import FORMATIONS
from app.match_engine import (
    calculate_team_strength,
    calculate_match_probabilities,
    simulate_match,
)


def _get_test_players_by_id(app):
    return app.data_loader.players_by_id


def _build_valid_squad(app, formation_name='4-3-3'):
    """Helper that returns a valid (starters, bench) pair for the given formation."""
    loader = app.data_loader
    get_p = lambda pos: [p for p in loader.players if p.primary_position == pos]

    lw = get_p('LW')[0]
    st = get_p('ST')[0]
    rw = get_p('RW')[0]
    cm1 = get_p('CM')[0]
    cam = get_p('CAM')[0]
    cm2 = get_p('CM')[1]
    lb = get_p('LB')[0]
    cb1 = get_p('CB')[0]
    cb2 = get_p('CB')[1]
    rb = get_p('RB')[0]
    gk1 = get_p('GK')[0]

    gk2 = get_p('GK')[1]
    def1 = get_p('CB')[2]
    def2 = get_p('CB')[3]
    mid1 = get_p('CM')[2]
    mid2 = get_p('CM')[3]
    att1 = get_p('ST')[1]
    att2 = get_p('ST')[2]

    starters = [
        {'player_id': lw.id, 'slot_index': 0},
        {'player_id': st.id, 'slot_index': 1},
        {'player_id': rw.id, 'slot_index': 2},
        {'player_id': cm1.id, 'slot_index': 3},
        {'player_id': cam.id, 'slot_index': 4},
        {'player_id': cm2.id, 'slot_index': 5},
        {'player_id': lb.id, 'slot_index': 6},
        {'player_id': cb1.id, 'slot_index': 7},
        {'player_id': cb2.id, 'slot_index': 8},
        {'player_id': rb.id, 'slot_index': 9},
        {'player_id': gk1.id, 'slot_index': 10},
    ]

    bench = [
        {'player_id': gk2.id},
        {'player_id': def1.id},
        {'player_id': def2.id},
        {'player_id': mid1.id},
        {'player_id': mid2.id},
        {'player_id': att1.id},
        {'player_id': att2.id},
    ]

    return starters, bench


# ════════════════════════════════════════════════════════════════
# 1. SQUAD VALIDATION TESTS
# ════════════════════════════════════════════════════════════════

def test_squad_validation_valid_squad(app):
    """Test that a correctly configured 11+7 squad passes all validation rules."""
    starters, bench = _build_valid_squad(app)
    result = validate_squad('4-3-3', starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert result['valid'] is True
    assert result['errors'] == []


def test_squad_validation_missing_or_extra_starters(app):
    """Test rejection when starting XI count is not exactly 11."""
    starters, bench = _build_valid_squad(app)

    # 10 starters
    res_10 = validate_squad('4-3-3', starters[:10], bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_10['valid'] is False
    assert any("Starting XI requires exactly 11 players" in e for e in res_10['errors'])

    # 12 starters
    extra_starter = {'player_id': starters[0]['player_id'], 'slot_index': 0}
    res_12 = validate_squad('4-3-3', starters + [extra_starter], bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_12['valid'] is False
    assert any("Starting XI requires exactly 11 players" in e for e in res_12['errors'])


def test_squad_validation_missing_or_extra_bench(app):
    """Test rejection when bench count is not exactly 7."""
    starters, bench = _build_valid_squad(app)

    # 6 bench players
    res_6 = validate_squad('4-3-3', starters, bench[:6], _get_test_players_by_id(app), FORMATIONS)
    assert res_6['valid'] is False
    assert any("Bench requires exactly 7 players" in e for e in res_6['errors'])

    # 8 bench players
    extra_bench = {'player_id': bench[0]['player_id']}
    res_8 = validate_squad('4-3-3', starters, bench + [extra_bench], _get_test_players_by_id(app), FORMATIONS)
    assert res_8['valid'] is False
    assert any("Bench requires exactly 7 players" in e for e in res_8['errors'])


def test_squad_validation_duplicate_players(app):
    """Test rejection of duplicates within starting XI, within bench, or cross-squad."""
    starters, bench = _build_valid_squad(app)

    # Duplicate within starters: replace slot 1 with player from slot 0
    dup_starters = [dict(s) for s in starters]
    dup_starters[1]['player_id'] = dup_starters[0]['player_id']
    res_dup_xi = validate_squad('4-3-3', dup_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_dup_xi['valid'] is False
    assert any("Duplicate player(s) in squad" in e for e in res_dup_xi['errors'])

    # Starter also present on bench
    dup_bench = [dict(b) for b in bench]
    dup_bench[0]['player_id'] = starters[0]['player_id']
    res_cross_dup = validate_squad('4-3-3', starters, dup_bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_cross_dup['valid'] is False
    assert any("Duplicate player(s) in squad" in e for e in res_cross_dup['errors'])


def test_squad_validation_unknown_player_ids(app):
    """Test rejection when player IDs do not exist in the database."""
    starters, bench = _build_valid_squad(app)
    bad_starters = [dict(s) for s in starters]
    bad_starters[0]['player_id'] = 999999  # Non-existent ID

    res = validate_squad('4-3-3', bad_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res['valid'] is False
    assert any("Unknown player ID(s): [999999]" in e for e in res['errors'])


def test_squad_validation_malformed_payloads(app):
    """Test rejection of malformed structures (non-dict items, non-list, missing fields)."""
    starters, bench = _build_valid_squad(app)

    # Starting XI not a list
    res_not_list = validate_squad('4-3-3', "not-a-list", bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_not_list['valid'] is False

    # Starter entry is not a dict
    bad_starters = [dict(s) for s in starters]
    bad_starters[0] = "just a string"
    res_not_dict = validate_squad('4-3-3', bad_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_not_dict['valid'] is False
    assert any("must be an object" in e for e in res_not_dict['errors'])

    # Missing player_id in starting XI
    no_id_starters = [dict(s) for s in starters]
    del no_id_starters[0]['player_id']
    res_no_id = validate_squad('4-3-3', no_id_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_no_id['valid'] is False
    assert any("invalid or missing player_id" in e for e in res_no_id['errors'])

    # Missing slot_index in starting XI
    no_slot_starters = [dict(s) for s in starters]
    del no_slot_starters[0]['slot_index']
    res_no_slot = validate_squad('4-3-3', no_slot_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_no_slot['valid'] is False
    assert any("invalid slot_index" in e for e in res_no_slot['errors'])


def test_squad_validation_slot_index_rules(app):
    """Test validation of slot_index data types and duplicates."""
    starters, bench = _build_valid_squad(app)

    # Boolean slot_index (True == 1 in Python, must be rejected as invalid slot structure)
    bad_slot_starters = [dict(s) for s in starters]
    bad_slot_starters[0]['slot_index'] = True
    res_bool_slot = validate_squad('4-3-3', bad_slot_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_bool_slot['valid'] is False

    # Out of range slot_index (e.g. 15)
    bad_range_starters = [dict(s) for s in starters]
    bad_range_starters[0]['slot_index'] = 15
    res_range = validate_squad('4-3-3', bad_range_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_range['valid'] is False

    # Duplicate slot_index (two starters assigned to slot 0)
    dup_slot_starters = [dict(s) for s in starters]
    dup_slot_starters[1]['slot_index'] = 0
    res_dup_slot = validate_squad('4-3-3', dup_slot_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res_dup_slot['valid'] is False
    assert any("Missing formation slot" in e or "Duplicate slot_index" in e for e in res_dup_slot['errors'])


def test_squad_validation_position_compatibility(app):
    """Test rejection when a player is placed in an incompatible formation slot."""
    starters, bench = _build_valid_squad(app)
    incompat_starters = [dict(s) for s in starters]

    # Swap goalkeeper (slot 10) into striker slot (slot 1)
    gk_entry = incompat_starters[10]
    st_entry = incompat_starters[1]
    incompat_starters[1] = {'player_id': gk_entry['player_id'], 'slot_index': 1}
    incompat_starters[10] = {'player_id': st_entry['player_id'], 'slot_index': 10}

    res = validate_squad('4-3-3', incompat_starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res['valid'] is False
    assert any("not position-compatible" in e for e in res['errors'])


def test_squad_validation_bench_composition(app):
    """Test rejection when bench composition violates 1 GK / 2 DEF / 2 MID / 2 ATT."""
    starters, bench = _build_valid_squad(app)
    loader = app.data_loader

    # Replace the bench GK with a third attacker (0 GK / 3 ATT)
    att3 = [p for p in loader.players if p.primary_position == 'ST'][5]
    bad_bench = [dict(b) for b in bench]
    bad_bench[0] = {'player_id': att3.id}

    res = validate_squad('4-3-3', starters, bad_bench, _get_test_players_by_id(app), FORMATIONS)
    assert res['valid'] is False
    assert any("Bench requires 1 Goalkeeper" in e for e in res['errors'])


def test_squad_validation_invalid_formation(app):
    """Test rejection of non-existent formation names."""
    starters, bench = _build_valid_squad(app)
    res = validate_squad('9-9-9', starters, bench, _get_test_players_by_id(app), FORMATIONS)
    assert res['valid'] is False
    assert any("Invalid formation '9-9-9'" in e for e in res['errors'])


# ════════════════════════════════════════════════════════════════
# 2. SQUAD STRENGTH & PROBABILITY CALCULATION TESTS
# ════════════════════════════════════════════════════════════════

def test_calculate_team_strength_consistency():
    """Verify calculate_team_strength handles Player objects, dicts, and bounds."""
    # Mock player objects
    p1 = MagicMock(overall=85)
    p2 = MagicMock(overall=87)
    p3 = MagicMock(overall=88)

    strength = calculate_team_strength([p1, p2, p3], difficulty='normal')
    # Normal difficulty modifier range is [-2, +2], mean overall is 86.67
    assert 84.0 <= strength <= 89.0

    # With dicts
    dict_players = [{'overall': 80}, {'overall': 90}]
    dict_strength = calculate_team_strength(dict_players, difficulty='hard')
    assert 83.0 <= dict_strength <= 87.0

    # Empty list fallback
    assert calculate_team_strength([], difficulty='normal') == 50.0


def test_calculate_match_probabilities_equal_strength():
    """
    At parity (user_strength == ai_strength), user_win and ai_win must be equal,
    draw must be reasonable (~26%), and the sum must be exactly 100.0%.
    """
    probs = calculate_match_probabilities(85.0, 85.0)

    assert probs['user_win'] == probs['ai_win']
    assert 35.0 <= probs['user_win'] <= 39.0
    assert 24.0 <= probs['draw'] <= 28.0
    # Strict 100.0% sum check
    total = round(probs['user_win'] + probs['draw'] + probs['ai_win'], 1)
    assert total == 100.0


def test_calculate_match_probabilities_user_advantage():
    """When user has a +10 rating advantage, user win should be dominant."""
    probs = calculate_match_probabilities(90.0, 80.0)

    assert probs['user_win'] > probs['ai_win']
    assert probs['user_win'] > probs['draw']
    assert probs['user_win'] > 60.0
    assert probs['ai_win'] < 25.0

    total = round(probs['user_win'] + probs['draw'] + probs['ai_win'], 1)
    assert total == 100.0


def test_calculate_match_probabilities_ai_advantage():
    """When AI has a +10 rating advantage, AI win should be dominant."""
    probs = calculate_match_probabilities(75.0, 85.0)

    assert probs['ai_win'] > probs['user_win']
    assert probs['ai_win'] > probs['draw']
    assert probs['ai_win'] > 60.0
    assert probs['user_win'] < 25.0

    total = round(probs['user_win'] + probs['draw'] + probs['ai_win'], 1)
    assert total == 100.0


def test_calculate_match_probabilities_extreme_differences():
    """
    Test extreme rating differentials (+50 and -50):
    - Probabilities must remain within 0% and 100%
    - Heavily favored team capped at 95.0% (upset chance preserved)
    - Underdog has non-zero probability (>= 0.5%)
    - Total must equal 100.0%
    """
    # Extreme user advantage
    probs_favored = calculate_match_probabilities(99.0, 45.0)
    assert probs_favored['user_win'] <= 95.0
    assert probs_favored['user_win'] >= 90.0
    assert probs_favored['ai_win'] >= 0.5
    assert probs_favored['draw'] >= 4.0
    assert round(probs_favored['user_win'] + probs_favored['draw'] + probs_favored['ai_win'], 1) == 100.0

    # Extreme AI advantage
    probs_underdog = calculate_match_probabilities(45.0, 99.0)
    assert probs_underdog['ai_win'] <= 95.0
    assert probs_underdog['ai_win'] >= 90.0
    assert probs_underdog['user_win'] >= 0.5
    assert probs_underdog['draw'] >= 4.0
    assert round(probs_underdog['user_win'] + probs_underdog['draw'] + probs_underdog['ai_win'], 1) == 100.0


def test_calculate_match_probabilities_safe_with_invalid_inputs():
    """Invalid or None inputs must default gracefully and return valid probabilities."""
    probs_none = calculate_match_probabilities(None, None)
    assert round(probs_none['user_win'] + probs_none['draw'] + probs_none['ai_win'], 1) == 100.0

    probs_str = calculate_match_probabilities("not-a-number", "invalid")
    assert round(probs_str['user_win'] + probs_str['draw'] + probs_str['ai_win'], 1) == 100.0


# ════════════════════════════════════════════════════════════════
# 3. MATCH SIMULATOR API INTEGRATION TESTS
# ════════════════════════════════════════════════════════════════

def test_api_validate_squad_endpoint(client, app):
    """Test POST /api/match-simulator/validate-squad returns 200 for valid squad."""
    starters, bench = _build_valid_squad(app)

    res = client.post('/api/match-simulator/validate-squad', json={
        'formation': '4-3-3',
        'starting_xi': starters,
        'bench': bench
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['valid'] is True
    assert data['errors'] == []


def test_api_simulate_match_endpoint(client, app):
    """
    Test POST /api/match-simulator/simulate executes complete match simulation
    and returns score, statistics, player ratings, and win/draw/loss probabilities.
    """
    starters, bench = _build_valid_squad(app)

    res = client.post('/api/match-simulator/simulate', json={
        'difficulty': 'normal',
        'formation': '4-3-3',
        'starting_xi': starters,
        'bench': bench
    })

    assert res.status_code == 200
    data = res.get_json()

    # Core response structure
    assert 'result' in data
    assert data['result'] in ('win', 'draw', 'loss')
    assert 'user_team' in data
    assert 'ai_team' in data
    assert 'motm' in data
    assert 'match_analysis' in data

    # Probabilities verification
    assert 'probabilities' in data
    probs = data['probabilities']
    assert 'user_win' in probs
    assert 'draw' in probs
    assert 'ai_win' in probs
    assert 0.0 <= probs['user_win'] <= 100.0
    assert 0.0 <= probs['draw'] <= 100.0
    assert 0.0 <= probs['ai_win'] <= 100.0
    assert round(probs['user_win'] + probs['draw'] + probs['ai_win'], 1) == 100.0


def test_api_simulate_match_rejects_invalid_squad(client, app):
    """Test POST /api/match-simulator/simulate defensive re-validation rejects invalid squad."""
    starters, bench = _build_valid_squad(app)

    # Incomplete bench (6 players)
    res = client.post('/api/match-simulator/simulate', json={
        'difficulty': 'normal',
        'formation': '4-3-3',
        'starting_xi': starters,
        'bench': bench[:6]
    })
    assert res.status_code == 400
    data = res.get_json()
    assert 'Squad validation failed' in data['error']

