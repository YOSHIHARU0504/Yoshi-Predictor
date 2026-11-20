from football_predictor.storage.sqlite_store import list_fixtures, save_fixtures


def sample_fixture(fixture_id=123):
    return {
        "fixture": {"id": fixture_id, "date": "2026-11-20T20:00:00+00:00", "status": {"short": "FT"}},
        "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2026},
        "teams": {
            "home": {"id": 1, "name": "Arsenal"},
            "away": {"id": 2, "name": "Chelsea"},
        },
        "goals": {"home": 2, "away": 1},
    }


def test_save_and_list_fixture(tmp_path):
    db = str(tmp_path / "test.sqlite3")
    assert save_fixtures([sample_fixture()], db) == 1
    rows = list_fixtures(db, league_id=39, season=2026)
    assert len(rows) == 1
    assert rows[0]["home_team"] == "Arsenal"
    assert rows[0]["home_goals"] == 2


def test_fixture_upsert_does_not_duplicate(tmp_path):
    db = str(tmp_path / "test.sqlite3")
    save_fixtures([sample_fixture()], db)
    updated = sample_fixture()
    updated["goals"] = {"home": 3, "away": 1}
    assert save_fixtures([updated], db) == 1
    rows = list_fixtures(db)
    assert len(rows) == 1
    assert rows[0]["home_goals"] == 3
