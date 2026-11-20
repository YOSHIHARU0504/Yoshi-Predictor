from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from football_predictor.data.api_football import ApiFootballClient, ApiFootballError
from football_predictor.models.poisson import predict_goal_markets
from football_predictor.models.elo import run_elo_backtest
from football_predictor.models.counts import count_market
from football_predictor.storage.sqlite_store import (\n    list_fixtures, save_fixtures, save_fixture_statistics, list_team_statistics\n)

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


@app.get("/v1/statistics/teams")
async def team_statistics(
    team_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=1000, ge=1, le=5000),
):
    return {"statistics": list_team_statistics(team_id=team_id, limit=limit)}
