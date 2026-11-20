from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from football_predictor.data.api_football import ApiFootballClient, ApiFootballError
from football_predictor.models.poisson import predict_goal_markets
from football_predictor.models.elo import run_elo_backtest
from football_predictor.models.counts import count_market
from football_predictor.storage.sqlite_store import list_fixtures, save_fixtures, save_fixture_statistics, list_team_statistics, team_count_rates

app = FastAPI(
    title="FOOTBALL PREDICTOR",
    version="0.1.0",
    description="Motor modular de probabilidades de fútbol. Los mercados se habilitan según cobertura y validación.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class GoalMarketRequest(BaseModel):
    lambda_home: float = Field(ge=0, le=10, description="Goles esperados del local")
    lambda_away: float = Field(ge=0, le=10, description="Goles esperados del visitante")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "football-predictor", "version": "0.1.0"}


@app.post("/v1/markets/goals")
async def goals_markets(request: GoalMarketRequest):
    try:
        return predict_goal_markets(request.lambda_home, request.lambda_away)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/fixtures")
async def fixtures(
    date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    league_id: int | None = Query(default=None, ge=1),
    season: int | None = Query(default=None, ge=1900, le=2100),
):
    try:
        return await ApiFootballClient().fixtures(date, league_id, season)
    except ApiFootballError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/sync/fixtures")
async def sync_fixtures(
    date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    league_id: int | None = Query(default=None, ge=1),
    season: int | None = Query(default=None, ge=1900, le=2100),
):
    """Fetch fixtures from API-Football and upsert normalized rows into local SQLite."""
    try:
        payload = await ApiFootballClient().fixtures(date, league_id, season)
        items = payload.get("response") or []
        saved = save_fixtures(items)
        return {
            "date": date,
            "received": len(items),
            "saved_or_updated": saved,
            "provider": "api-football",
        }
    except ApiFootballError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/history")
async def history(
    league_id: int | None = Query(default=None, ge=1),
    season: int | None = Query(default=None, ge=1900, le=2100),
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"fixtures": list_fixtures(league_id=league_id, season=season, limit=limit)}


@app.post("/v1/sync/league-season")
async def sync_league_season(
    league_id: int = Query(ge=1),
    season: int = Query(ge=1900, le=2100),
):
    """Import all fixtures returned by API-Football for one league and season."""
    try:
        payload = await ApiFootballClient().fixtures_by_league_season(league_id, season)
        items = payload.get("response") or []
        saved = save_fixtures(items)
        return {
            "league_id": league_id,
            "season": season,
            "received": len(items),
            "saved_or_updated": saved,
            "provider": "api-football",
            "coverage_note": "La disponibilidad depende del plan, temporada y cuota de API-Football.",
        }
    except ApiFootballError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/models/elo/backtest")
async def elo_backtest(
    league_id: int = Query(ge=1),
    season: int | None = Query(default=None, ge=1900, le=2100),
):
    matches = list_fixtures(league_id=league_id, season=season, limit=500)
    finished = [
        match for match in matches
        if match.get("home_goals") is not None
        and match.get("away_goals") is not None
        and match.get("home_team_id") is not None
        and match.get("away_team_id") is not None
    ]
    if len(finished) < 30:
        raise HTTPException(
            status_code=422,
            detail=f"Historial insuficiente: se necesitan al menos 30 partidos terminados; hay {len(finished)}.",
        )
    return run_elo_backtest(finished)



class CountMarketRequest(BaseModel):
    market: str = Field(pattern=r"^(corners|yellow_cards|red_cards)$")
    lambda_home: float = Field(ge=0, le=40)
    lambda_away: float = Field(ge=0, le=40)
    line: float = Field(ge=0, le=40)


@app.post("/v1/markets/counts")
async def count_markets(request: CountMarketRequest):
    try:
        return count_market(
            request.lambda_home, request.lambda_away, request.line, request.market
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/sync/statistics")
async def sync_statistics(fixture_id: int = Query(ge=1)):
    try:
        payload = await ApiFootballClient().fixture_statistics(fixture_id)
        items = payload.get("response") or []
        saved = save_fixture_statistics(fixture_id, items)
        return {
            "fixture_id": fixture_id,
            "teams_received": len(items),
            "team_rows_saved": saved,
            "provider": "api-football",
        }
    except ApiFootballError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/sync/statistics-batch")
async def sync_statistics_batch(
    league_id: int = Query(ge=1),
    season: int = Query(ge=1900, le=2100),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Import statistics sequentially for the most recent finished fixtures in local history.

    Each fixture consumes a provider request. The limit is deliberately capped to
    protect API quotas; repeat calls to continue filling the sample.
    """
    fixtures = list_fixtures(league_id=league_id, season=season, limit=500)
    finished = [
        item for item in fixtures
        if item.get("home_goals") is not None
        and item.get("away_goals") is not None
        and item.get("status_short") in {"FT", "AET", "PEN"}
    ][:limit]
    client = ApiFootballClient()
    results = []
    for item in finished:
        fixture_id = item["fixture_id"]
        try:
            payload = await client.fixture_statistics(fixture_id)
            saved = save_fixture_statistics(fixture_id, payload.get("response") or [])
            results.append({"fixture_id": fixture_id, "saved": saved, "status": "ok"})
        except ApiFootballError as exc:
            results.append({"fixture_id": fixture_id, "saved": 0, "status": "error", "detail": str(exc)})
            if "quota" in str(exc).lower() or "rate" in str(exc).lower():
                break
    return {
        "league_id": league_id,
        "season": season,
        "requested_limit": limit,
        "processed": len(results),
        "successful": sum(item["status"] == "ok" for item in results),
        "saved_team_rows": sum(item["saved"] for item in results),
        "results": results,
        "quota_warning": "Cada fixture consume una solicitud de API-Football. Revisa tu cuota antes de repetir.",
    }

@app.get("/v1/statistics/teams")
async def team_statistics(
    team_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=1000, ge=1, le=5000),
):
    return {"statistics": list_team_statistics(team_id=team_id, limit=limit)}



@app.get("/v1/markets/team-counts")
async def team_count_markets(
    home_team_id: int = Query(ge=1),
    away_team_id: int = Query(ge=1),
    market: str = Query(pattern=r"^(corners|yellow_cards|red_cards)$"),
    line: float = Query(ge=0, le=40),
):
    try:
        rates = team_count_rates(home_team_id, away_team_id, market)
        probabilities = count_market(
            rates["lambda_home"], rates["lambda_away"], line, market
        )
        return {**rates, "probabilities": probabilities}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



@app.get("/v1/leagues")
async def available_leagues(
    season: int | None = Query(default=None, ge=1900, le=2100),
    country: str | None = Query(default=None, min_length=2, max_length=80),
):
    try:
        payload = await ApiFootballClient().leagues(country=country, season=season)
        return {
            "results": payload.get("results", 0),
            "leagues": payload.get("response") or [],
            "provider": "api-football",
            "coverage_note": "La lista depende de la cobertura de tu plan y de la temporada solicitada.",
        }
    except ApiFootballError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# SofaScore data is imported from a user-provided export. No scraping or direct
# requests to undocumented SofaScore endpoints are performed by this application.
from football_predictor.storage.sofascore_store import (
    import_sofascore_matches,
    sofascore_team_count_rates,
)


class SofaScoreTeamImport(BaseModel):
    team_id: int = Field(gt=0)
    team_name: str = Field(min_length=1, max_length=120)
    statistics: dict[str, int | None] = Field(default_factory=dict)


class SofaScoreMatchImport(BaseModel):
    event_id: int = Field(gt=0)
    kickoff_utc: str = Field(min_length=10, max_length=40)
    tournament_name: str | None = Field(default=None, max_length=160)
    season: str | None = Field(default=None, max_length=40)
    home: SofaScoreTeamImport
    away: SofaScoreTeamImport
    home_goals: int | None = Field(default=None, ge=0, le=50)
    away_goals: int | None = Field(default=None, ge=0, le=50)
    status: str | None = Field(default=None, max_length=40)


class SofaScoreImportRequest(BaseModel):
    matches: list[SofaScoreMatchImport] = Field(min_length=1, max_length=1000)


@app.post("/v1/sofascore/import")
async def import_sofascore_export(request: SofaScoreImportRequest):
    """Import a normalized SofaScore export supplied by the user; no network scraping."""
    saved = import_sofascore_matches(
        [match.model_dump() for match in request.matches]
    )
    return {
        "provider": "sofascore-import",
        "received": len(request.matches),
        "saved_or_updated": saved,
        "note": "Los IDs SofaScore se guardan separados de API-Football. Solo importa datos que tengas derecho a reutilizar.",
    }


@app.get("/v1/sofascore/team-counts")
async def sofascore_team_count_markets(
    home_team_id: int = Query(ge=1),
    away_team_id: int = Query(ge=1),
    market: str = Query(pattern=r"^(corners|yellow_cards|red_cards)$"),
    line: float = Query(ge=0, le=40),
):
    try:
        rates = sofascore_team_count_rates(home_team_id, away_team_id, market)
        probabilities = count_market(
            rates["lambda_home"], rates["lambda_away"], line, market
        )
        return {**rates, "probabilities": probabilities}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# Experimental direct SofaScore connector. This is read-only and does not bypass blocks.
from datetime import date as date_type
from football_predictor.data.sofascore import SofaScoreClient, SofaScoreError


@app.get("/v1/sofascore/status")
async def sofascore_status():
    return {
        "provider": "sofascore-experimental",
        "mode": "direct-read-only",
        "warning": "Endpointos internos no oficiales; pueden cambiar o bloquearse.",
    }


@app.get("/v1/sofascore/events")
async def sofascore_events(day: date_type = Query(description="Fecha local YYYY-MM-DD")):
    try:
        events = await SofaScoreClient().scheduled_events(day)
        return {
            "provider": "sofascore-experimental",
            "date": day.isoformat(),
            "events": [
                SofaScoreClient.normalize_event(event)
                for event in events
                if (event.get("homeTeam") or {}).get("id")
                and (event.get("awayTeam") or {}).get("id")
            ],
        }
    except SofaScoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/v1/sofascore/sync")
async def sofascore_sync(
    day: date_type = Query(description="Fecha YYYY-MM-DD"),
    limit: int = Query(default=10, ge=1, le=20),
):
    client = SofaScoreClient()
    try:
        events = await client.scheduled_events(day)
        selected = [
            event for event in events
            if (event.get("homeTeam") or {}).get("id")
            and (event.get("awayTeam") or {}).get("id")
        ][:limit]
        normalized = []
        for event in selected:
            event_id = int(event.get("id") or 0)
            if not event_id:
                continue
            try:
                stats = await client.event_statistics(event_id)
            except SofaScoreError:
                # Stop immediately on a provider block or unexpected response.
                raise
            normalized.append(client.normalize_event(event, stats))
        saved = import_sofascore_matches(normalized)
        return {
            "provider": "sofascore-experimental",
            "date": day.isoformat(),
            "events_found": len(events),
            "events_requested": len(selected),
            "saved_or_updated": saved,
            "note": "Consulta directa experimental. Si el proveedor bloquea o limita, se detiene sin reintentos.",
        }
    except SofaScoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
