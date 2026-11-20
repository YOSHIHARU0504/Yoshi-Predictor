# FOOTBALL PREDICTOR

Motor modular de análisis y probabilidades de fútbol. Esta rama introduce una base nueva y aislada; no modifica `main`.

## Estado de esta fase

- API FastAPI con comprobación de salud.
- Motor Poisson independiente para probabilidades 1X2, goles, BTTS y marcadores.
- Adaptador inicial para API-Football (credencial solo por variable de entorno).
- Pruebas de invariantes matemáticos.
- Arquitectura preparada para incorporar Elo, Dixon-Coles, modelos de córners, tarjetas, entrenamiento y backtesting cronológico.

**Importante:** la primera versión calcula mercados de goles a partir de goles esperados (`lambda_home` y `lambda_away`). No genera pronósticos de partidos reales hasta conectar datos históricos suficientes y validar los modelos por competición. Córners y tarjetas permanecerán deshabilitados hasta disponer de datos fiables.

## Requisitos

Python 3.11 o superior.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn football_predictor.api:app --reload
```

API local: http://127.0.0.1:8000  
Documentación: http://127.0.0.1:8000/docs

## Variables

Configura `API_FOOTBALL_KEY` y, opcionalmente, `DATABASE_PATH` localmente. Nunca publiques claves reales.

## Endpoints

- `GET /health`
- `POST /v1/markets/goals` (cálculo matemático con lambdas explícitas)
- `GET /v1/fixtures?date=YYYY-MM-DD&league_id=...` (requiere API key)
- `POST /v1/sync/fixtures?date=YYYY-MM-DD&league_id=...` (sincroniza fixtures en SQLite)
- `GET /v1/history?league_id=...&season=...&limit=100` (consulta el historial local)
- `POST /v1/sync/league-season?league_id=...&season=...` (importa el historial de una competición)
- `POST /v1/sync/statistics?fixture_id=...` (importa estadísticas de córners y tarjetas)
- `GET /v1/statistics/teams?team_id=...` (consulta estadísticas almacenadas)
- `GET /v1/markets/team-counts?home_team_id=...&away_team_id=...&market=corners&line=8.5` (estima tasas con historial local, mínimo cinco partidos por sede)
- `GET /v1/models/elo/backtest?league_id=...&season=...` (valida Elo cronológicamente)
- `POST /v1/markets/counts` (calcula líneas de córners/tarjetas a partir de tasas explícitas)

## Diseño

```
football_predictor/
  api.py
  config.py
  data/
    api_football.py
  models/
    poisson.py
tests/
  test_poisson.py
```

## Hoja de ruta

1. Ingesta y normalización de fixtures, resultados y estadísticas.
2. Historial persistente y deduplicación de partidos.
3. Features pre-partido con replay cronológico sin filtración futura.
4. Modelos separados por mercado y competición: Elo, Dixon-Coles, Poisson, ML.
5. Modelos de córners y tarjetas solo donde exista cobertura suficiente.
6. Calibración, backtesting walk-forward y monitorización.
7. Interfaz de usuario e integración con las fuentes disponibles.

## Panel web

Abre una terminal en la carpeta del proyecto y ejecuta `python -m http.server 5500 --directory web`. Inicia la API en otra terminal con `uvicorn football_predictor.api:app --reload` y visita http://127.0.0.1:5500. Configura la URL del backend en el panel si es diferente.

## Licencia y atribución

El repositorio de referencia [JanoTheDev/football-prediction-engine](https://github.com/JanoTheDev/football-prediction-engine) publica su código bajo MIT. Esta fase implementa una base propia inspirada en principios estadísticos generales; no copia archivos de ese proyecto. Antes de portar módulos concretos se registrarán procedencia, licencia y avisos de copyright.

Proyecto de investigación estadística. Las probabilidades no garantizan resultados ni rentabilidad.
