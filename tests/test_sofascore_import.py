from football_predictor.storage.sofascore_store import (
    import_sofascore_matches,
    sofascore_team_count_rates,
)


def _match(event_id: int, home_corners: int, away_corners: int) -> dict:
    return {
        "event_id": event_id,
        "kickoff_utc": f"2026-01-{event_id:02d}T18:00:00Z",
        "tournament_name": "Test League",
        "season": "2026",
        "status": "finished",
        "home_goals": 1,
        "away_goals": 0,
        "home": {
            "team_id": 10,
            "team_name": "Home FC",
            "statistics": {"corners": home_corners, "yellow_cards": 1, "red_cards": 0},
        },
        "away": {
            "team_id": 20,
            "team_name": "Away FC",
            "statistics": {"corners": away_corners, "yellow_cards": 2, "red_cards": 0},
        },
    }


def test_sofascore_import_and_count_rates_are_isolated(tmp_path):
    database = str(tmp_path / "nested" / "sofascore.sqlite")
    matches = [_match(i, 4 + i, 2 + i) for i in range(1, 6)]

    assert import_sofascore_matches(matches, database) == 5
    rates = sofascore_team_count_rates(10, 20, "corners", database)

    assert rates["provider"] == "sofascore-import"
    assert rates["samples"] == {"home_team_at_home": 5, "away_team_away": 5}
    assert rates["lambda_home"] == 7.0
    assert rates["lambda_away"] == 5.0


def test_sofascore_rates_require_minimum_history(tmp_path):
    database = str(tmp_path / "sofascore.sqlite")
    import_sofascore_matches([_match(1, 5, 4)], database)

    try:
        sofascore_team_count_rates(10, 20, "corners", database)
    except ValueError as exc:
        assert "Historial SofaScore insuficiente" in str(exc)
    else:
        raise AssertionError("Expected insufficient-history error")
