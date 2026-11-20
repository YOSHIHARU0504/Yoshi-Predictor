from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from typing import Any

from football_predictor.config import settings


def _connect(database_path: str | None = None) -> sqlite3.Connection:
    path = database_path or settings.database_path
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_sofascore_tables(database_path: str | None = None) -> None:
    with closing(_connect(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sofascore_matches (
                event_id INTEGER PRIMARY KEY,
                kickoff_utc TEXT NOT NULL,
                tournament_name TEXT,
                season TEXT,
                home_team_id INTEGER NOT NULL,
                home_team_name TEXT NOT NULL,
                away_team_id INTEGER NOT NULL,
                away_team_name TEXT NOT NULL,
                home_goals INTEGER,
                away_goals INTEGER,
                status TEXT,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sofascore_team_stats (
                event_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('home', 'away')),
                corners INTEGER,
                yellow_cards INTEGER,
                red_cards INTEGER,
                shots_total INTEGER,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (event_id, team_id),
                FOREIGN KEY(event_id) REFERENCES sofascore_matches(event_id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_ss_stats_team_side ON sofascore_team_stats(team_id, side)"
        )
        connection.commit()


def import_sofascore_matches(matches: list[dict[str, Any]], database_path: str | None = None) -> int:
    initialize_sofascore_tables(database_path)
    saved = 0
    with closing(_connect(database_path)) as connection:
        for match in matches:
            event_id = match["event_id"]
            home = match["home"]
            away = match["away"]
            connection.execute(
                """
                INSERT INTO sofascore_matches (
                    event_id, kickoff_utc, tournament_name, season, home_team_id,
                    home_team_name, away_team_id, away_team_name, home_goals,
                    away_goals, status, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    kickoff_utc=excluded.kickoff_utc,
                    tournament_name=excluded.tournament_name,
                    season=excluded.season,
                    home_team_id=excluded.home_team_id,
                    home_team_name=excluded.home_team_name,
                    away_team_id=excluded.away_team_id,
                    away_team_name=excluded.away_team_name,
                    home_goals=excluded.home_goals,
                    away_goals=excluded.away_goals,
                    status=excluded.status,
                    raw_json=excluded.raw_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    event_id, match["kickoff_utc"], match.get("tournament_name"),
                    match.get("season"), home["team_id"], home["team_name"],
                    away["team_id"], away["team_name"], match.get("home_goals"),
                    match.get("away_goals"), match.get("status"),
                    json.dumps(match, ensure_ascii=False),
                ),
            )
            for side, team in (("home", home), ("away", away)):
                stats = team.get("statistics") or {}
                connection.execute(
                    """
                    INSERT INTO sofascore_team_stats (
                        event_id, team_id, team_name, side, corners, yellow_cards,
                        red_cards, shots_total, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id, team_id) DO UPDATE SET
                        team_name=excluded.team_name,
                        side=excluded.side,
                        corners=excluded.corners,
                        yellow_cards=excluded.yellow_cards,
                        red_cards=excluded.red_cards,
                        shots_total=excluded.shots_total,
                        raw_json=excluded.raw_json,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        event_id, team["team_id"], team["team_name"], side,
                        stats.get("corners"), stats.get("yellow_cards"),
                        stats.get("red_cards"), stats.get("shots_total"),
                        json.dumps(team, ensure_ascii=False),
                    ),
                )
            saved += 1
        connection.commit()
    return saved


def sofascore_team_count_rates(
    home_team_id: int, away_team_id: int, market: str,
    database_path: str | None = None, min_sample: int = 5,
) -> dict[str, Any]:
    columns = {"corners": "corners", "yellow_cards": "yellow_cards", "red_cards": "red_cards"}
    if market not in columns:
        raise ValueError("Mercado SofaScore no compatible")
    column = columns[market]
    initialize_sofascore_tables(database_path)
    query = f"""
        SELECT AVG(s.{column}) AS average_count, COUNT(*) AS sample_size
        FROM sofascore_team_stats s
        JOIN sofascore_matches m ON m.event_id = s.event_id
        WHERE s.team_id = ? AND s.side = ?
          AND s.{column} IS NOT NULL
          AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
    """
    with closing(_connect(database_path)) as connection:
        home = connection.execute(query, (home_team_id, "home")).fetchone()
        away = connection.execute(query, (away_team_id, "away")).fetchone()
    if home["sample_size"] < min_sample or away["sample_size"] < min_sample:
        raise ValueError(
            f"Historial SofaScore insuficiente: se requieren {min_sample} partidos "
            f"como local/visitante; muestras actuales {home['sample_size']} y {away['sample_size']}."
        )
    return {
        "provider": "sofascore-import",
        "market": market,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "lambda_home": float(home["average_count"]),
        "lambda_away": float(away["average_count"]),
        "samples": {
            "home_team_at_home": home["sample_size"],
            "away_team_away": away["sample_size"],
        },
        "note": "Datos importados por el usuario; IDs SofaScore separados de los IDs API-Football.",
    }
