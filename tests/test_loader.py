"""
CSV Data Loader & Player Key Stability Tests
============================================
Verifies stable player identity keys and ensures integer ID shifts
do not compromise player key identity.
"""

import os
import tempfile
import shutil
from app.data_loader import CSVDataLoader, make_player_key, slugify


def test_player_key_slugification():
    assert slugify("Kylian Mbappé") == "kylian-mbappe"
    assert slugify("Antonio Rüdiger") == "antonio-rudiger"
    assert slugify("Lionel Messi") == "lionel-messi"
    assert slugify("O'Brien") == "o-brien"
    assert make_player_key("France", "Kylian Mbappé") == "france:kylian-mbappe"


def test_all_players_have_unique_keys(app):
    loader = app.data_loader
    assert len(loader.players) > 0
    assert len(loader.players) == len(loader.players_by_key)


def test_key_stability_when_earlier_team_csv_added(tmp_path):
    # Create mock teams directory
    data_dir = tmp_path / "data"
    teams_dir = data_dir / "teams"
    teams_dir.mkdir(parents=True)

    # Team Z: sorts last
    team_z = teams_dir / "zzz_team.csv"
    team_z.write_text(
        "name,primary_position,secondary_position,nationality,overall\n"
        "Star Player,ST,,ZZZ Country,85\n",
        encoding="utf-8"
    )

    loader1 = CSVDataLoader(str(data_dir))
    player_initial = loader1.players[0]
    initial_id = player_initial.id
    initial_key = player_initial.key
    assert initial_id == 1
    assert initial_key == "zzz-country:star-player"

    # Now add Team A which sorts earlier alphabetically (aaa_team.csv)
    team_a = teams_dir / "aaa_team.csv"
    team_a.write_text(
        "name,primary_position,secondary_position,nationality,overall\n"
        "Early Player,GK,,AAA Country,80\n",
        encoding="utf-8"
    )

    loader2 = CSVDataLoader(str(data_dir))
    # Star Player's integer ID shifted from 1 to 2 because aaa_team.csv was loaded first!
    star_player_new = loader2.get_player_by_key(initial_key)
    assert star_player_new is not None
    assert star_player_new.id == 2  # Integer ID shifted!
    assert star_player_new.key == initial_key  # Key remained rock solid!

