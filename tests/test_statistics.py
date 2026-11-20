from football_predictor.storage.sqlite_store import list_team_statistics, save_fixture_statistics


def test_save_team_corners_and_cards(tmp_path):
    db = str(tmp_path / "stats.sqlite3")
    response = [
        {
            "team": {"id": 10, "name": "Home FC"},
            "statistics": [
                {"type": "Corner Kicks", "value": 7},
                {"type": "Yellow Cards", "value": 2},
                {"type": "Red Cards", "value": 0},
                {"type": "Total Shots", "value": 14},
            ],
        },
        {
            "team": {"id": 20, "name": "Away FC"},
            "statistics": [
                {"type": "Corner Kicks", "value": 4},
                {"type": "Yellow Cards", "value": 3},
                {"type": "Red Cards", "value": 1},
                {"type": "Total Shots", "value": 8},
            ],
        },
    ]
    assert save_fixture_statistics(555, response, db) == 2
    rows = list_team_statistics(database_path=db)
    assert len(rows) == 2
    home = next(row for row in rows if row["team_id"] == 10)
    assert home["corners"] == 7
    assert home["yellow_cards"] == 2
    assert home["red_cards"] == 0
