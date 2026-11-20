from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from football_predictor.data.api_football import ApiFootballClient, ApiFootballError
from football_predictor.models.poisson import predict_goal_markets

app = FastAPI(
    title="FOOTBALL PREDICTOR",
    version="0.1.0",
    description="Motor modular de probabilidades de fútbol. Los mercados se habilitan según cobertura y validación.",
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
