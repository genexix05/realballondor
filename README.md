# Ballon d'Or Statistical Index

Índice estadístico partido a partido para valorar candidatos al Balón de Oro de forma transparente y reproducible.

## Arranque rápido (estado actual)

- **Código**: este repo (Mac / Cursor)
- **PostgreSQL**: Docker en `192.168.0.48` (`~/docker/realballondor`)
- **Dataset FBref**: CSV jugador×partido vía **player match logs** (estrategia worldfootballR)

### 1. Variables de entorno

```bash
cp .env.example .env
# Edita DATABASE_URL con la password del servidor
```

### 2. Dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Migraciones

```bash
python scripts/migrate.py
```

### 4. Construir dataset FBref (rápido + completo)

**No** scrapea 380 páginas de partido. Hace como [worldfootballR `fb_player_match_logs`](https://jaseziv.github.io/worldfootballR/articles/extract-fbref-data.html):

1 página por jugador × pestaña = todos sus partidos de la temporada (Liga + Copa + Champions + …).

Por defecto scrapea el **pack completo** y lo fusiona en un CSV ancho:

`summary + passing + passing_types + gca + defense + possession + misc`

Así Big 5 / siguientes ligas no empiezan a medias.

```bash
# Smoke test (2 jugadores, pack completo)
python scripts/build_fbref_dataset.py --scope laliga --limit 2

# La Liga completa (>= 450 min). Reanudable / cacheado.
python scripts/build_fbref_dataset.py --scope laliga --min-minutes 450 --pause 2.5

# Big 5 (sube el umbral)
python scripts/build_fbref_dataset.py --scope big5 --min-minutes 900

# Solo una pestaña (debug)
python scripts/build_fbref_dataset.py --stat-types summary
```

Salida:

- CSV: `data/raw/fbref/player_match_logs_*_full.csv`
- Caché HTML: `data/cache/fbref_player_logs/` (si cortas, al relanzar sigue; el `summary` ya bajado se reutiliza)

Tiempos orientativos (pause 2.5s, ~7 pestañas): La Liga filtrada ~2–4 h la primera vez; luego casi gratis por caché.

#### Alternativa en R (worldfootballR)

Si instalas R:

```bash
brew install r
Rscript -e 'install.packages("devtools"); devtools::install_github("JaseZiv/worldfootballR")'
Rscript scripts/r/build_fbref_matchlogs.R 2026 ESP 450
```

Misma idea; el pipeline Python ya replica esa estrategia sin mezclar stacks.

### 5. Partidos (resultados) + sanity

```bash
# Resultados La Liga (CSV football-data, segundos)
python -c "from ballondor.db import connect, load_env; from ballondor.ingest.seed import seed_competitions; from ballondor.ingest.football_data import ingest_football_data_laliga; load_env();
import ballondor.ingest.football_data as fd
with connect() as c:
    seed_competitions(c); print(ingest_football_data_laliga(c,'2526')); c.commit()"

python scripts/sanity_check.py
```

## Base de datos en el servidor

```bash
ssh genexix05@192.168.0.48
cd ~/docker/realballondor
docker-compose ps
docker-compose logs -f postgres
```

Compose de referencia: [`docker/docker-compose.yml`](docker/docker-compose.yml).

## Estructura

```
config/                 # pesos competición / posición
db/migrations/          # SQL
data/raw/fbref/         # CSV generados
data/cache/fbref_.../   # HTML cacheados
src/ballondor/
  db/
  ingest/               # football_data, fbref_player_logs, ...
  scoring/              # stubs
scripts/
  build_fbref_dataset.py
  r/build_fbref_matchlogs.R
```

## Próximos hitos

1. Importar CSV FBref → `player_match_stats`
2. Big 5 + UCL (vía logs de jugador; UCL ya sale en los logs)
3. Rankings UEFA/FIFA as-of
4. Match Score + Season Score
5. FastAPI + UI
