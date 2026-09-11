# Ballon d'Or Statistical Index

Índice estadístico partido a partido para valorar candidatos al Balón de Oro de forma transparente y reproducible.

## Fuentes de datos

Estado comprobado en septiembre de 2026:

| Fuente | Qué aporta | Estado |
|---|---|---|
| **FotMob** | jugador×partido con rating, xG/xA, duelos, acciones defensivas, distancias. Todas las competiciones | ✅ **fuente principal** |
| football-data.co.uk | resultados de las grandes ligas, para validar | ✅ funciona |
| FBref (directo) | métricas avanzadas (SCA/GCA, tipos de pase) | ⚠️ 403 sin navegador real; 10 peticiones/min |
| FBref (pre-scrapeado, `worldfootballR_data`) | lo mismo, ya descargado | ⚠️ completo solo hasta 2023/24 |
| StatsBomb Open Data | event data | ℹ️ no cubre las temporadas del índice; sirve para validar métricas |
| **kassiesa.net** | coeficiente UEFA de club a 5 años (427 clubes) | ✅ fuerza del rival en Europa |
| **Transfermarkt** | ranking FIFA con fecha de publicación, 368 ediciones desde 1992 | ✅ fuerza del rival en selecciones |

La API oficial de UEFA devuelve solo 20 clubes, y la de FIFA dejó de servir las ediciones
posteriores a septiembre de 2025 (los `dateId` nuevos responden vacío), de ahí las dos
fuentes alternativas. Transfermarkt está cotejado contra FIFA para el 18/09/2025: España
1875 frente a 1875,37, es decir las mismas cifras redondeadas a puntos enteros.

**FotMob es la espina dorsal del proyecto.** Una petición sin autenticar por partido
(`/_next/data/{buildId}/en/match/{id}.json`) devuelve alineaciones, rating y ~40 estadísticas
por jugador, el shotmap y el contexto del partido. Cubre ligas, copas, Champions y torneos
de selecciones, con temporadas desde 2010/11. Es además la única fuente viable del campo
`rating`, que **FBref no publica**.

FBref queda como capa de enriquecimiento opcional para pases/conducciones progresivas y
SCA/GCA en las Big 5, unible por `opta_player_id`.

## Arranque rápido

- **Código**: este repo
- **PostgreSQL**: Docker en `192.168.0.48` (`~/docker/realballondor`)

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

### 4. Construir el dataset jugador×partido (FotMob)

```bash
# Smoke test
python scripts/build_fotmob_dataset.py --league laliga --season 2025/2026 --limit 5

# Todo: Big 5 + Europa + copas + supercopas + Mundial (~3.200 partidos)
python scripts/build_fotmob_dataset.py --scope full --season 2025/2026

# Grupos sueltos: big5 | europe | cups | super-cups | intercontinental | mvp
python scripts/build_fotmob_dataset.py --scope cups --season 2025/2026
```

**La temporada se indica siempre como ventana agosto–julio** (`2025/2026`), también
para torneos de una sola sede: el Mundial 2026 y la Supercopa de enero de 2026 pertenecen
a 2025/2026. Las etiquetas de temporada de FotMob son inconsistentes — la Supercopa
jugada en enero de 2026 está archivada como "2024/2025" — así que los partidos se
seleccionan **por fecha de saque inicial**, no por etiqueta. El listado de partidos ya
trae la hora, de modo que el filtrado ocurre antes de descargar ningún payload.

Salida en `data/raw/fotmob/`, en Parquet y CSV:

- `matches_*` — un registro por partido: fecha, competición, **fase normalizada**, marcador, estadio, aforo, asistencia, árbitro.
- `player_match_stats_*` — un registro por jugador y partido, ~109 columnas.

#### Dataset ingerido (temporada 2025/26)

**3.201 partidos, 87.982 filas jugador×partido, 10.067 jugadores, 109 columnas.**

| Competición | Partidos | Filas | | Competición | Partidos | Filas |
|---|---:|---:|---|---|---:|---:|
| La Liga | 380 | 11.953 | | FA Cup | 123 | 2.533 |
| Premier League | 380 | 11.492 | | Copa del Rey | 117 | 2.864 |
| Serie A | 380 | 11.928 | | Mundial 2026 | 104 | 3.288 |
| Coupe de France | 362 | 1.928 | | EFL Cup | 91 | 2.856 |
| Ligue 1 | 306 | 9.408 | | DFB-Pokal | 63 | 1.980 |
| Bundesliga | 306 | 9.555 | | Coppa Italia | 45 | 1.308 |
| Champions League | 189 | 5.850 | | Intercontinental | 5 | 158 |
| Europa League | 189 | 5.899 | | Supercopa ESP | 3 | 96 |
| Conference League | 153 | 4.736 | | 5 supercopas más | 5 | 150 |

#### Calidad del dato

`coverage_level` en la tabla `matches` indica qué trae cada partido:

| Nivel | Partidos | Qué hay |
|---|---:|---|
| `xG` | 2.821 | pack completo: rating, xG/xA, duelos, distancias |
| `ratings` | 6 | rating y básicas, sin xG |
| `lower` | 374 | sin datos por jugador (rondas de aficionados de copa) |

Los 374 sin datos son casi todos rondas 6-8 de la Coupe de France y rondas iniciales
de FA Cup y Copa del Rey. Desde dieciseisavos la cobertura es del 100% en todas las copas,
así que no afecta a ningún candidato al Balón de Oro. Usa `player_rows > 0` para filtrarlos.

Cobertura de `rating`: 92,4%. El resto son suplentes de menos de ~10 minutos, a los que
FotMob no puntúa.

Control de integridad: sobre los partidos con datos, la suma de `goals` + `own_goals`
de los jugadores reproduce los marcadores con un desfase de 4 goles sobre 8.106 (0,05%).
Los goles en propia puerta y los de penalti no aparecen en las estadísticas por jugador
de FotMob, así que se extraen de los eventos del partido.

La caché de payloads vive en `data/cache/fotmob/matches/*.json.gz`, así que la ingesta es
reanudable y **re-parsear no vuelve a descargar** (la Champions entera se re-parsea en ~4 s).
Ningún nombre de estadística se pierde: los conocidos se renombran a nombres canónicos
(`rating`, `xg`, `key_passes`…) y cualquiera nuevo aparece como columna extra.

#### Enriquecimiento opcional con FBref

Solo si necesitas SCA/GCA y pases/conducciones progresivas. Requiere navegador real
(`pip install -e ".[fbref]"`) y respetar el límite de 10 peticiones/min.

```bash
python scripts/build_fbref_dataset.py --scope laliga --min-minutes 450 --pause 6
```

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

### 6. Fuerza del rival (`opponent_strength`)

```bash
python scripts/build_opponent_strength.py --season 2025/2026
```

Genera `data/processed/opponent_strength_2025-2026.parquet`: 6.402 filas, un lado por equipo
y partido, con la fuerza propia y la del rival en una escala 0..1 común.

**Por qué no basta el coeficiente UEFA.** Solo 113 de los 489 clubes del dataset juegan
competición europea, así que en el **87% de los partidos domésticos** el coeficiente no
distingue a los rivales. La fuerza se compone por tanto de dos partes:

| Componente | Qué mide | Cobertura |
|---|---|---|
| `uefa_score` | coeficiente de club a 5 años, con raíz cuadrada para que el Madrid (143,5) no aplaste a la mediana (<5) | 53 de los 96 clubes de las Big 5 |
| `domestic_score` | puntos por partido en su liga, escalados por el coeficiente de país | todos |

**Todo se lee as-of el saque inicial.** El coeficiente UEFA vigente durante 2025/26 es el
calculado al cierre de 2024/25 (ventana 20/21..24/25); usar el de 2026 metería los propios
resultados europeos de la temporada en la valoración de quien los produjo. La forma
doméstica solo cuenta partidos terminados *estrictamente antes* del saque, mezclada con la
tabla del año anterior mediante un encogimiento de 8 partidos.

Para selecciones se usa la edición del ranking FIFA publicada antes del partido. El caso
extremo: **España era 2ª antes del Mundial 2026 y 1ª después de ganarlo**; valorar la final
con el ranking posterior sería puntuar el partido con su propio resultado.

Parámetros ajustables (`StrengthConfig`): `--uefa-weight` (0.35), `--prior-matches` (8.0),
`--league-exponent` (0.5).

### 7. Match Score y ranking de temporada

```bash
python scripts/build_scores.py --season 2025/2026
python scripts/build_scores.py --minutes-damping 0.5 --rating-weight 0.25
```

```
Match Score = Performance × Fiabilidad × Rival × Competición × Fase
```

**Performance** mezcla contribuciones absolutas con el rating, no métricas por 90.
Normalizar por 90 y luego amortiguar con `sqrt(min/90)` parece un castigo a los suplentes
pero se compone en `stat × sqrt(90/min)`: un gol en 30 minutos valdría 1,73 goles y uno en
5 minutos, 4,24. Los minutos ya están dentro de los recuentos, así que se dejan estar.

Cada estadística se divide por su percentil 95 dentro del grupo de posición, **no** se
convierte a z-score: un z-score le daría un valor muy negativo a cualquier suplente en cada
recuento, que es una penalización por minutos colada por la puerta de atrás. Dividir deja el
cero en cero.

**Fiabilidad** es el único sitio donde los minutos aparecen explícitamente, como
`(min/90) ** damping`. Con `damping=0` la actuación se sostiene sola. El ranking resulta
robusto a este parámetro: entre 0 y 0,5 el top 10 solo intercambia los puestos 1-2 y saca a
Dembélé, que se perdió media temporada.

Salidas en `data/processed/`: `match_scores_*.parquet` (87.982 filas con todos los
componentes visibles) y `season_scores_*.parquet`.

### 8. Índice final (rendimiento + palmarés)

```bash
python scripts/build_index.py --season 2025/2026
python scripts/build_index.py --trophy-weight 0.30 --balance-components
```

```
Índice = 82% × Rendimiento + 18% × Palmarés
```

**Los campeones se deducen de los datos**, no se escriben a mano: las copas por su final
y las ligas por la tabla construida desde los resultados. De las 17 finales de 2025/26,
**6 acabaron en empate y se decidieron por penaltis**, la de Champions incluida, así que el
marcador no basta. La tanda está en `matchFacts.events.penaltyShootoutEvents` del payload
cacheado, y hay que contar los eventos de tipo `Goal`: el marcador que arrastra cada evento
cierra la final de Champions en 5-4 cuando los penaltis marcados fueron 4-3.

El crédito por título se escala por los minutos que el jugador disputó en esa competición,
medidos contra el jugador más usado de su propia plantilla, para que un suplente no cobre
lo mismo que el capitán.

**No se aplica factor de disponibilidad.** El Season Score es una suma sobre partidos, así
que quien estuvo sano todo el año ya acumuló más; multiplicar por disponibilidad encima
cobraría las lesiones dos veces. La **regularidad** sí se aplica (`1 - coeficiente de
variación`), porque dos temporadas con el mismo total pueden venir de aportar siempre o de
tres explosiones y mucho silencio, y la suma no las distingue.

**Peso declarado vs peso real.** El script lo informa en cada ejecución. Con 18% declarado,
el palmarés aporta el **15,6% del valor** del índice en el top 25 (fiel a lo pedido) pero el
**32% de la varianza** del top 100, porque arriba el rendimiento se comprime mientras los
títulos siguen usando todo el rango. `--balance-components` pondera por poder de
discriminación en vez de por valor.

Salidas: `ballondor_index_*.parquet`, `champions_*.csv`, `trophy_detail_*.parquet`.

### 9. Postgres, API y UI

```bash
python scripts/migrate.py
python scripts/load_season.py --season 2025/2026

# API
uvicorn ballondor.api.app:app --reload --port 8000

# UI (http://localhost:3000)
cd web && npm install && npm run dev
```

El loader resuelve identidades por `external_ids` (FotMob / Opta), no por nombre:
`Vitinha` y `Vítinha` son el mismo jugador. Reutiliza los partidos del piloto
football-data cuando coinciden competición, fecha y equipos.

Endpoints: `/api/ranking`, `/api/players/{id}`, `/api/players/{id}/matches`, `/api/trophies`.

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
config/                    # pesos competición / posición
db/migrations/             # SQL
data/raw/fotmob/           # datasets generados (parquet + csv)
data/processed/            # opponent_strength
data/cache/fotmob/         # payloads de partido cacheados
data/cache/rankings/       # UEFA y FIFA cacheados
src/ballondor/
  db/
  ingest/                  # fotmob, rankings, load_season, football_data, fbref_*
  scoring/                 # strength, match_score, trophies
  api/                     # FastAPI
web/                       # Next.js (ranking, ficha, títulos)
scripts/
  build_fotmob_dataset.py
  build_opponent_strength.py
  build_scores.py
  build_index.py
  load_season.py
  migrate.py
  build_fbref_dataset.py
```

## Próximos hitos

1. ~~Rankings UEFA y FIFA con join *as-of* para evitar data leakage~~ ✅
2. ~~Motor de scoring: Performance → multiplicadores → Match Score → Season Score~~ ✅
3. ~~Componente de títulos y factor de regularidad~~ ✅
4. ~~Cargar Parquet → Postgres + FastAPI + UI~~ ✅
5. Temporadas históricas (2024/25 hacia atrás) y comparación con el Balón de Oro real
6. Ajustes del modelo (pesos de ligas, porteros) y más detalle en la UI
