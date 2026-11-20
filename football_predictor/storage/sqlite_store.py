from __future__ import annotations

import json
import sqlite3
from contextlib import closing
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
    with closing(_connect(database_path)) as connection:
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fixture_team_stats (
                fixture_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                team_name TEXT,
                corners INTEGER,
                yellow_cards INTEGER,
                red_cards INTEGER,
                shots_total INTEGER,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (fixture_id, team_id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_team_stats_team ON fixture_team_stats(team_id)"
        )
        connection.commit()


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

    with closing(_connect(database_path)) as connection:
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
        connection.commit()
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
    with closing(_connect(database_path)) as connection:
        rows = connection.execute(
            f"SELECT fixture_id, kickoff_utc, status_short, league_id, league_name, "
            f"country, season, home_team_id, home_team, away_team_id, away_team, home_goals, away_goals, updated_at "
            f"FROM fixtures {where} ORDER BY kickoff_utc DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]



def _stat_value(statistics: list[dict[str, Any]], *names: str) -> int | None:
    wanted = {name.casefold() for name in names}
    for item in statistics:
        if str(item.get("type", "")).casefold() in wanted:
            value = item.get("value")
            if value is None:
                return None
            try:
                return int(str(value).replace("%", ""))
            except (TypeError, ValueError):
                return None
    return None


def save_fixture_statistics(fixture_id: int, response: list[dict[str, Any]],
                            database_path: str | None = None) -> int:
    initialize_database(database_path)
    rows = []
    for team_block in response:
        team = team_block.get("team") or {}
        team_id = team.get("id")
        if team_id is None:
            continue
        stats = team_block.get("statistics") or []
        rows.append((
            fixture_id,
            team_id,
            team.get("name"),
            _stat_value(stats, "Corner Kicks", "Corners"),
            _stat_value(stats, "Yellow Cards"),
            _stat_value(stats, "Red Cards"),
            _stat_value(stats, "Total Shots"),
            json.dumps(team_block, ensure_ascii=False),
        ))
    with closing(_connect(database_path)) as connection:
        connection.executemany(
            """
            INSERT INTO fixture_team_stats (
                fixture_id, team_id, team_name, corners, yellow_cards, red_cards,
                shots_total, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fixture_id, team_id) DO UPDATE SET
                team_name=excluded.team_name,
                corners=excluded.corners,
                yellow_cards=excluded.yellow_cards,
                red_cards=excluded.red_cards,
                shots_total=excluded.shots_total,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            rows,
        )
        connection.commit()
    return len(rows)


def list_team_statistics(team_id: int | None = None, database_path: str | None = None,
                          limit: int = 1000) -> list[dict[str, Any]]:
    initialize_database(database_path)
    where = "WHERE team_id = ?" if team_id is not None else ""
    params: list[Any] = [team_id] if team_id is not None else []
    params.append(max(1, min(limit, 5000)))
    with closing(_connect(database_path)) as connection:
        rows = connection.execute(
            f"SELECT fixture_id, team_id, team_name, corners, yellow_cards, red_cards, "
            f"shots_total, updated_at FROM fixture_team_stats {where} "
            f"ORDER BY fixture_id DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def team_count_rates(home_team_id: int, away_team_id: int, market: str,
                     database_path: str | None = None, min_sample: int = 5) -> dict[str, Any]:
    columns = {"corners": "corners", "yellow_cards": "yellow_cards", "red_cards": "red_cards"}
    if market not in columns:
        raise ValueError("Unsupported count market")
    column = columns[market]
    initialize_database(database_path)
    query = f"""
        SELECT AVG(s.{column}) AS average_count, COUNT(*) AS sample_size
        FROM fixture_team_stats s
        JOIN fixtures f ON f.fixture_id = s.fixture_id
        WHERE s.team_id = ? AND f.home_team_id = s.team_id
          AND f.away_team_id IS NOT NULL
          AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
          AND s.{column} IS NOT NULL
    """
    away_query = f"""
        SELECT AVG(s.{column}) AS average_count, COUNT(*) AS sample_size
        FROM fixture_team_stats s
        JOIN fixtures f ON f.fixture_id = s.fixture_id
        WHERE s.team_id = ? AND f.away_team_id = s.team_id
          AND f.home_team_id IS NOT NULL
          AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
          AND s.{column} IS NOT NULL
    """
    with closing(_connect(database_path)) as connection:
        home = connection.execute(query, (home_team_id,)).fetchone()
        away = connection.execute(away_query, (away_team_id,)).fetchone()
    if home["sample_size"] < min_sample or away["sample_size"] < min_sample:
        raise ValueError(
            f"Historial insuficiente: se requieren {min_sample} partidos como local/visitante; "
            f"muestras actuales {home['sample_size']} y {away['sample_size']}."
        )
    return {
        "market": market,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "lambda_home": float(home["average_count"]),
        "lambda_away": float(away["average_count"]),
        "samples": {"home_team_at_home": home["sample_size"], "away_team_away": away["sample_size"]},
    }
