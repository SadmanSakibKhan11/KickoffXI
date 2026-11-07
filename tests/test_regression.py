"""
Existing Site Behavior Regression Tests
=======================================
Verifies that existing routes (home, players, teams, match simulator,
player APIs, and match simulation) continue to function identically.
"""


def test_index_page(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b"KickoffXI" in res.data


def test_players_page(client):
    res = client.get('/players')
    assert res.status_code == 200
    assert b"Player Database" in res.data


def test_teams_page_and_detail(client):
    res_teams = client.get('/teams')
    assert res_teams.status_code == 200
    assert b"Participating Teams" in res_teams.data

    res_detail = client.get('/teams/germany')
    assert res_detail.status_code == 200
    assert b"Germany" in res_detail.data


def test_match_simulator_page(client):
    res = client.get('/match-simulator')
    assert res.status_code == 200
    assert b"Match Simulator" in res.data


def test_player_api_endpoints(client):
    res_players = client.get('/api/players')
    assert res_players.status_code == 200
    data = res_players.get_json()
    assert 'players' in data
    assert len(data['players']) > 0

    res_teams = client.get('/api/teams')
    assert res_teams.status_code == 200
    teams_data = res_teams.get_json()
    assert 'teams' in teams_data


def test_match_simulator_validation_api(client, app):
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

    res = client.post('/api/match-simulator/validate-squad', json={
        'formation': '4-3-3',
        'starting_xi': starters,
        'bench': bench
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('valid') is True
