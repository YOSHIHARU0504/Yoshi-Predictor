from __future__ import annotations

from datetime import date
from typing import Any

import httpx


class SofaScoreError(RuntimeError):
    pass


class SofaScoreClient:
    """Experimental read-only client for SofaScore's undocumented public web endpoints.

    No proxy rotation, browser impersonation, CAPTCHA handling, or retry-on-block logic.
    A 403/429 is surfaced immediately and the caller must stop the experiment.
    """

    BASE_URL = "https://www.sofascore.com/api/v1"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "FOOTBALL-PREDICTOR-personal-experiment/0.1"},
            ) as client:
                response = await client.get(f"{self.BASE_URL}{path}")
        except httpx.HTTPError as exc:
            raise SofaScoreError(f"Error de red SofaScore: {exc}") from exc

        if response.status_code in (403, 429):
            raise SofaScoreError(
                f"SofaScore respondió HTTP {response.status_code}. "
                "Se detuvo la consulta; no se intentará eludir el bloqueo ni reintentar."
            )
        if response.status_code >= 400:
            raise SofaScoreError(f"SofaScore respondió HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SofaScoreError("SofaScore devolvió una respuesta que no es JSON.") from exc
        if not isinstance(payload, dict):
            raise SofaScoreError("Formato de respuesta SofaScore no reconocido.")
        return payload

    async def scheduled_events(self, day: date) -> list[dict[str, Any]]:
        payload = await self._get(f"/sport/football/scheduled-events/{day.isoformat()}")
        events = payload.get("events")
        if not isinstance(events, list):
            raise SofaScoreError("La respuesta no contiene la lista esperada de partidos.")
        return events

    async def event_statistics(self, event_id: int) -> dict[str, Any]:
        return await self._get(f"/event/{event_id}/statistics")

    @staticmethod
    def normalize_event(event: dict[str, Any], statistics: dict[str, Any] | None = None) -> dict[str, Any]:
        home = event.get("homeTeam") or {}
        away = event.get("awayTeam") or {}
        tournament = event.get("tournament") or {}
        status = event.get("status") or {}
        scores = event.get("homeScore") or {}
        away_scores = event.get("awayScore") or {}
        home_goals = scores.get("current")
        away_goals = away_scores.get("current")
        normalized_stats = {"home": {}, "away": {}}

        def canonical(name: str) -> str | None:
            key = name.lower().replace(" ", "").replace("_", "")
            if "corner" in key:
                return "corners"
            if "yellowcard" in key:
                return "yellow_cards"
            if "redcard" in key:
                return "red_cards"
            if "totalshots" in key or key == "shots":
                return "shots_total"
            return None

        if statistics:
            for group in statistics.get("statistics", []) or []:
                for item in group.get("groups", []) or []:
                    for stat in item.get("statisticsItems", []) or []:
                        metric = canonical(str(stat.get("key") or stat.get("name") or ""))
                        if metric:
                            for side, key in (("home", "home"), ("away", "away")):
                                value = stat.get(key)
                                try:
                                    normalized_stats[side][metric] = int(float(value))
                                except (TypeError, ValueError):
                                    pass

        start = event.get("startTimestamp")
        from datetime import datetime, timezone
        kickoff = datetime.fromtimestamp(start, timezone.utc).isoformat() if start else ""
        return {
            "event_id": int(event.get("id") or 0),
            "kickoff_utc": kickoff,
            "tournament_name": tournament.get("name"),
            "season": str((event.get("season") or {}).get("name") or ""),
            "status": status.get("description") or status.get("type"),
            "home_goals": home_goals if isinstance(home_goals, int) else None,
            "away_goals": away_goals if isinstance(away_goals, int) else None,
            "home": {"team_id": int(home.get("id") or 0), "team_name": home.get("name") or "Local",
                     "statistics": normalized_stats["home"]},
            "away": {"team_id": int(away.get("id") or 0), "team_name": away.get("name") or "Visitante",
                     "statistics": normalized_stats["away"]},
        }
