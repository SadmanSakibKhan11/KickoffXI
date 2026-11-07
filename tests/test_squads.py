"""
Saved Squads & Structural Ownership Tests
=========================================
Tests squad CRUD, structural ownership isolation, player-key boundary,
11 starters + 7 bench integrity, and unavailable-player handling.
"""


def _build_valid_433_payload(loader):
    """Helper to build a valid 4-3-3 starting XI and bench from CSVDataLoader."""
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


def test_squad_crud_and_player_keys(client, app, mock_firebase_auth):
    mock_firebase_auth.verify_session_cookie.return_value = {
        'uid': 'user_A',
        'sub': 'user_A',
        'name': 'Alice',
        'email': 'alice@example.com'
    }
    client.set_cookie('kxi_session', 'mock_cookie_user_A')

    starters_input, bench_input = _build_valid_433_payload(app.data_loader)

    # 1. Create Squad
    create_res = client.post(
        '/api/saved-squads',
        json={
            'name': 'My Dream Team',
            'formation': '4-3-3',
            'starting_xi': starters_input,
            'bench': bench_input
        }
    )

    assert create_res.status_code == 201
    squad_id = create_res.get_json()['id']
    assert isinstance(squad_id, str)

    # 2. List Squads
    list_res = client.get('/api/saved-squads')
    assert list_res.status_code == 200
    squads = list_res.get_json()['squads']
    assert len(squads) == 1
    assert squads[0]['id'] == squad_id
    assert squads[0]['starter_count'] == 11
    assert squads[0]['bench_count'] == 7
    assert squads[0]['total_count'] == 18

    # 3. Retrieve Squad with player resolution
    get_res = client.get(f'/api/saved-squads/{squad_id}')
    assert get_res.status_code == 200
    squad_data = get_res.get_json()
    assert squad_data['name'] == 'My Dream Team'
    assert len(squad_data['starters']) == 11
    assert len(squad_data['bench']) == 7
    assert all(p['available'] is True for p in squad_data['starters'])

    # 4. Duplicate Squad
    dup_res = client.post(f'/api/saved-squads/{squad_id}/duplicate', json={'name': 'My Dream Team Clone'})
    assert dup_res.status_code == 201
    dup_id = dup_res.get_json()['id']
    assert dup_id != squad_id

    # 5. Delete Squad
    del_res = client.delete(f'/api/saved-squads/{dup_id}')
    assert del_res.status_code == 200

    # Ensure deleted squad returns 404
    get_del = client.get(f'/api/saved-squads/{dup_id}')
    assert get_del.status_code == 404


def test_cross_user_structural_isolation(client, in_memory_squad_store, mock_firebase_auth):
    """
    Ensure User B cannot read, update, delete, or duplicate User A's squad,
    even if User B guesses the squad ID.
    """
    # User A creates a squad directly in store
    squad_id_a = in_memory_squad_store.create_squad(
        uid="user_A",
        name="User A Squad",
        formation="4-3-3",
        players=[{'player_key': 'germany:manuel-neuer', 'role': 'starter', 'slot': '10'}]
    )

    # Now request as User B
    mock_firebase_auth.verify_session_cookie.return_value = {
        'uid': 'user_B',
        'sub': 'user_B',
        'name': 'Bob',
        'email': 'bob@example.com'
    }
    client.set_cookie('kxi_session', 'mock_cookie_user_B')

    # 1. User B tries to GET User A's squad -> 404
    res_get = client.get(f'/api/saved-squads/{squad_id_a}')
    assert res_get.status_code == 404

    # 2. User B tries to PUT User A's squad -> 404
    res_put = client.put(f'/api/saved-squads/{squad_id_a}', json={'name': 'Hacked'})
    assert res_put.status_code == 404

    # 3. User B tries to DELETE User A's squad -> 404
    res_del = client.delete(f'/api/saved-squads/{squad_id_a}')
    assert res_del.status_code == 404

    # 4. User B tries to DUPLICATE User A's squad -> 404
    res_dup = client.post(f'/api/saved-squads/{squad_id_a}/duplicate', json={})
    assert res_dup.status_code == 404

    # Confirm User A's squad is still completely intact
    mock_firebase_auth.verify_session_cookie.return_value = {
        'uid': 'user_A',
        'sub': 'user_A',
        'name': 'Alice',
        'email': 'alice@example.com'
    }
    client.set_cookie('kxi_session', 'mock_cookie_user_A')
    res_verify_a = client.get(f'/api/saved-squads/{squad_id_a}')
    assert res_verify_a.status_code == 200
    assert res_verify_a.get_json()['name'] == "User A Squad"


def test_unavailable_player_handling(client, in_memory_squad_store, mock_firebase_auth):
    mock_firebase_auth.verify_session_cookie.return_value = {
        'uid': 'user_A',
        'sub': 'user_A',
        'name': 'Alice',
        'email': 'alice@example.com'
    }
    client.set_cookie('kxi_session', 'mock_cookie_user_A')

    # Squad containing a player key that does not exist in CSV
    squad_id = in_memory_squad_store.create_squad(
        uid="user_A",
        name="Vintage Squad",
        formation="4-3-3",
        players=[
            {'player_key': 'nonexistent-country:retired-legend', 'role': 'starter', 'slot': '9'}
        ]
    )

    res = client.get(f'/api/saved-squads/{squad_id}')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data['starters']) == 1
    unavail = data['starters'][0]
    assert unavail['available'] is False
    assert unavail['id'] is None
    assert 'Unknown Player' in unavail['name']
