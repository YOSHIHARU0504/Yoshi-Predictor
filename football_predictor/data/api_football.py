from __future__ import annotations

import httpx

from football_predictor.config import settings


class ApiFootballError(RuntimeError):
    """Raised when API-Football returns an unsuccessful response."""


class ApiFootballClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else settings.api_football_key
        self.base_url = (base_url or settings.api_football_base_url).rstrip("/")

    async def fixtures(self, date: str, league_id: int | None = None, season: int | None = None):
        if not self.api_key:
            raise ApiFootballError("API_FOOTBALL_KEY no está configurada.")
        params: dict[str, str | int] = {"date": date}
        if league_id is not None:
            params["league"] = league_id
        if season is not None:
            params["season"] = season

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self.base_url}/fixtures",
                params=params,
                headers={"x-apisports-key": self.api_key},
            )
        if response.is_error:
            raise ApiFootballError(f"API-Football respondió HTTP {response.status_code}.")
        payload = response.json()
        if payload.get("errors"):
            raise ApiFootballError(f"API-Football reportó errores: {payload['errors']}")
        return payload
