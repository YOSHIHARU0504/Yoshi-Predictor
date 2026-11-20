from __future__ import annotations

import httpx

from football_predictor.config import settings


class ApiFootballError(RuntimeError):
    """Raised when API-Football returns an unsuccessful response."""


class ApiFootballClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else settings.api_football_key
        self.base_url = (base_url or settings.api_football_base_url).rstrip("/")

    async def _get(self, endpoint: str, params: dict):
        if not self.api_key:
            raise ApiFootballError("API_FOOTBALL_KEY no está configurada.")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/{endpoint.lstrip('/')}",
                params=params,
                headers={"x-apisports-key": self.api_key},
            )
        if response.is_error:
            raise ApiFootballError(f"API-Football respondió HTTP {response.status_code}.")
        payload = response.json()
        if payload.get("errors"):
            raise ApiFootballError(f"API-Football reportó errores: {payload['errors']}")
        return payload

    async def fixtures(self, date: str, league_id: int | None = None, season: int | None = None):
        params: dict[str, str | int] = {"date": date}
        if league_id is not None:
            params["league"] = league_id
        if season is not None:
            params["season"] = season
        return await self._get("fixtures", params)

    async def fixtures_by_league_season(self, league_id: int, season: int):
        """Fetch a league season's fixtures; API plan coverage and quotas still apply."""
        return await self._get("fixtures", {"league": league_id, "season": season})

    async def leagues(self, country: str | None = None, season: int | None = None):
        params = {}
        if country:
            params["country"] = country
        if season is not None:
            params["season"] = season
        return await self._get("leagues", params)
