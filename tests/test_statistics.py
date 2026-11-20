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


def test_team_rates_require_and_use_home_away_history(tmp_path):
    from football_predictor.storage.sqlite_store import save_fixtures, team_count_rates

    db = str(tmp_path / "rates.sqlite3")
    fixtures = []
    for fixture_id in range(1, 7):
        fixtures.append({
            "fixture": {"id": fixture_id, "date": f"2026-01-{fixture_id:02d}T18:00:00Z",
                        "status": {"short": "FT"}},
            "league": {"id": 39, "name": "League", "country": "England", "season": 2026},
            "teams": {"home": {"id": 10, "name": "Home"},
                      "away": {"id": 20, "name": "Away"}},
            "goals": {"home": 1, "away": 0},
        })
    save_fixtures(fixtures, db)
    for fixture_id in range(1, 7):
        stats = [
            {"team": {"id": 10, "name": "Home"},
             "statistics": [{"type": "Corner Kicks", "value": 6}]},
            {"team": {"id": 20, "name": "Away"},
             "statistics": [{"type": "Corner Kicks", "value": 4}]},
        ]
        save_fixture_statistics(fixture_id, stats, db)
    rates = team_count_rates(10, 20, "corners", db, min_sample=5)
    assert rates["lambda_home"] == 6
    assert rates["lambda_away"] == 4
    assert rates["samples"]["home_team_at_home"] == 6
