# FOOTBALL PREDICTOR

Motor modular de análisis estadístico de fútbol. Esta implementación se encuentra en la rama `feature/integral-prediction-engine`; no modifica `main` ni despliega a producción.

## Qué incluye esta versión

- API FastAPI y almacenamiento local SQLite.
- Integración con API-Football mediante `x-apisports-key` y variable de entorno.
- Catálogo de ligas/competiciones según cobertura del proveedor.
- Importación de fixtures por fecha o por liga y temporada.
- Modelo Poisson de goles: 1X2, ambos marcan, totales y marcadores probables.
- Modelo Elo cronológico con backtest exploratorio.
- Importación y persistencia de estadísticas por equipo: córners, amarillas, rojas y tiros.
- Modelo Poisson de conteos para líneas over/under/push de córners y tarjetas.
- Estimación de tasas por equipo y sede (local en casa, visitante fuera), si hay al menos cinco partidos terminados con estadísticas para cada muestra.
- Panel web en español y pruebas automatizadas de los modelos y almacenamiento.

## Límites importantes

Esta es una base funcional de investigación, no un sistema de apuestas validado ni un pronosticador infalible. Los cálculos Poisson con lambdas introducidas manualmente son demostraciones matemáticas. La estimación automática de córners/tarjetas usa promedios históricos simples, no un modelo entrenado con árbitro, rival, ritmo, alineaciones o contexto. Elo es exploratorio y todavía requiere calibración y validación walk-forward por liga. No se deben interpretar sus probabilidades como garantía ni como recomendación de apuesta.

La cobertura de ligas, temporadas y estadísticas depende del plan, permisos y cuota de API-Football. El plan gratuito puede no incluir temporadas actuales de algunas competiciones. La aplicación no puede saltarse esas restricciones.

## Requisitos

- Python 3.11+
- Node.js 20+ (solo para comprobar sintaxis del panel)
- Clave API-Football activa para importar datos

## Instalación en Windows (PowerShell)

```powershell
git clone https://github.com/YOSHIHARU0504/Yoshi-Predictor.git
cd Yoshi-Predictor
git switch feature/integral-prediction-engine
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edita `.env` localmente y coloca tu clave en `API_FOOTBALL_KEY`. No compartas el archivo ni subas la clave a GitHub. Puedes definir `DATABASE_PATH`; por defecto se usa SQLite local.

En una terminal inicia la API:

```powershell
uvicorn football_predictor.api:app --reload
```

En otra terminal, desde la raíz del proyecto, inicia el panel:

```powershell
python -m http.server 5500 --directory web
```

Abre http://127.0.0.1:5500. La documentación interactiva de la API está en http://127.0.0.1:8000/docs y el estado en http://127.0.0.1:8000/health.

## Flujo recomendado para preparar datos

1. En el panel, busca competiciones por país/temporada o introduce el ID de liga conocido.
2. Importa una liga y temporada disponibles en tu plan. Esto guarda fixtures y resultados en SQLite.
3. Consulta el historial y ejecuta el backtest Elo cuando existan al menos 30 partidos finalizados.
4. Para córners/tarjetas, usa el botón **Importar estadísticas (20)** del panel o llama a `POST /v1/sync/statistics-batch?league_id=ID&season=AAAA&limit=20`. Cada partido consume una solicitud API. También puedes importar uno por uno con `POST /v1/sync/statistics?fixture_id=ID`. La importación de fixtures por sí sola no incluye estadísticas.
5. Repite la importación de estadísticas para una muestra suficiente. El endpoint `GET /v1/markets/team-counts` exige al menos cinco partidos estadísticos como local para el equipo local y cinco como visitante para el equipo visitante.
6. Compara las estimaciones con resultados futuros no usados en el cálculo antes de considerar cualquier uso real.

## Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/health` | Estado del servicio |
| GET | `/v1/leagues?season=2024&country=England` | Competiciones disponibles |
| GET | `/v1/fixtures?date=YYYY-MM-DD` | Fixtures de una fecha |
| POST | `/v1/sync/fixtures?date=YYYY-MM-DD` | Guarda fixtures de una fecha |
| POST | `/v1/sync/league-season?league_id=39&season=2024` | Importa una temporada |
| GET | `/v1/history?league_id=39&season=2024` | Consulta historial local |
| POST | `/v1/markets/goals` | Calcula mercados de goles desde lambdas explícitas |
| GET | `/v1/models/elo/backtest?league_id=39&season=2024` | Backtest cronológico Elo |
| POST | `/v1/sync/statistics?fixture_id=123456` | Importa estadísticas de un partido |
| GET | `/v1/statistics/teams?team_id=33` | Consulta estadísticas guardadas |
| POST | `/v1/markets/counts` | Calcula línea de conteos desde lambdas explícitas |
| GET | `/v1/markets/team-counts?home_team_id=33&away_team_id=34&market=corners&line=8.5` | Tasas por sede y probabilidades históricas |

## Pruebas

```powershell
python -m pytest -q
node --check web/app.js
```

GitHub Actions ejecuta ambas comprobaciones en pushes a ramas `feature/**` y en pull requests hacia `main`.

## Licencia y atribución

La referencia investigada [JanoTheDev/football-prediction-engine](https://github.com/JanoTheDev/football-prediction-engine) publica código bajo MIT. Esta rama contiene una implementación propia basada en métodos estadísticos generales; no copia archivos de ese proyecto.

Proyecto de investigación estadística. Las probabilidades no garantizan resultados ni rentabilidad.
