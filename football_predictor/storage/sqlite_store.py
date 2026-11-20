from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from football_predictor.config import settings


def _connect(database_path: str | None = None) -> sqlite3.Connection:
    path = Path(database_path or settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(database_path: str | None = None) -> None:
    with _connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fixtures (
                fixture_id INTEGER PRIMARY KEY,
                kickoff_utc TEXT,
                status_short TEXT,
                league_id INTEGER,
                league_name TEXT,
                country TEXT,
                season INTEGER,
                home_team_id INTEGER,
                home_team TEXT,
                away_team_id INTEGER,
                away_team TEXT,
                home_goals INTEGER,
                away_goals INTEGER,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_fixtures_date ON fixtures(kickoff_utc)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_fixtures_league ON fixtures(league_id, season)"
        )


def save_fixtures(fixtures: list[dict[str, Any]], database_path: str | None = None) -> int:
    initialize_database(database_path)
    rows = []
    for item in fixtures:
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        goals = item.get("goals") or {}
        fixture_id = fixture.get("id")
        if fixture_id is None:
            continue
        rows.append(
            (
                fixture_id,
                fixture.get("date"),
                (fixture.get("status") or {}).get("short"),
                league.get("id"),
                league.get("name"),
                league.get("country"),
                league.get("season"),
                home.get("id"),
                home.get("name"),
                away.get("id"),
                away.get("name"),
                goals.get("home"),
                goals.get("away"),
                json.dumps(item, ensure_ascii=False),
            )
        )

    with _connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO fixtures (
                fixture_id, kickoff_utc, status_short, league_id, league_name, country,
                season, home_team_id, home_team, away_team_id, away_team, home_goals,
                away_goals, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fixture_id) DO UPDATE SET
                kickoff_utc=excluded.kickoff_utc,
                status_short=excluded.status_short,
                league_id=excluded.league_id,
                league_name=excluded.league_name,
                country=excluded.country,
                season=excluded.season,
                home_team_id=excluded.home_team_id,
                home_team=excluded.home_team,
                away_team_id=excluded.away_team_id,
                away_team=excluded.away_team,
                home_goals=excluded.home_goals,
                away_goals=excluded.away_goals,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            rows,
        )
    return len(rows)


def list_fixtures(
    database_path: str | None = None,
    league_id: int | None = None,
    season: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    initialize_database(database_path)
    clauses: list[str] = []
    params: list[Any] = []
    if league_id is not None:
        clauses.append("league_id = ?")
        params.append(league_id)
    if season is not None:
        clauses.append("season = ?")
        params.append(season)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 500)))
    with _connect(database_path) as connection:
        rows = connection.execute(
            f"SELECT fixture_id, kickoff_utc, status_short, league_id, league_name, "
            f"country, season, home_team, away_team, home_goals, away_goals, updated_at "
            f"FROM fixtures {where} ORDER BY kickoff_utc DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]
