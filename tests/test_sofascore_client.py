from datetime import date
import asyncio

import pytest

from football_predictor.data.sofascore import SofaScoreClient, SofaScoreError


def test_normalize_event_and_statistics():
    event = {
        "id": 77,
        "startTimestamp": 1791655200,
        "tournament": {"name": "Test League"},
        "season": {"name": "2026"},
        "status": {"description": "Ended", "type": "finished"},
        "homeTeam": {"id": 1, "name": "Home FC"},
        "awayTeam": {"id": 2, "name": "Away FC"},
        "homeScore": {"current": 2},
        "awayScore": {"current": 1},
    }
    stats = {"statistics": [{"groups": [{"statisticsItems": [
        {"key": "totalCorners", "home": "6", "away": "4"},
        {"key": "yellowCards", "home": "2", "away": "3"},
        {"key": "redCards", "home": "0", "away": "1"},
        {"key": "totalShots", "home": "12", "away": "8"},
    ]}]}]}
    result = SofaScoreClient.normalize_event(event, stats)
    assert result["event_id"] == 77
    assert result["home"]["statistics"]["corners"] == 6
    assert result["away"]["statistics"]["yellow_cards"] == 3
    assert result["home"]["statistics"]["shots_total"] == 12


def test_normalize_missing_statistics_is_safe():
    result = SofaScoreClient.normalize_event({
        "id": 1, "homeTeam": {"id": 2, "name": "A"},
        "awayTeam": {"id": 3, "name": "B"},
    })
    assert result["home"]["statistics"] == {}
    assert result["away"]["statistics"] == {}


def test_http_403_is_not_retried_or_bypassed(monkeypatch):
    class Response:
        status_code = 403
        def json(self):
            return {"message": "Forbidden"}

    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, url):
            return Response()

    monkeypatch.setattr("football_predictor.data.sofascore.httpx.AsyncClient", Client)
    with pytest.raises(SofaScoreError, match="HTTP 403"):
        asyncio.run(SofaScoreClient().scheduled_events(date(2026, 11, 20)))
