"""FastAPI for the Ballon d'Or Statistical Index."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

from ballondor.db import connect

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"

app = FastAPI(title="Ballon d'Or Statistical Index", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    found = _rows(sql, params)
    return found[0] if found else None


def _clean(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            out[key] = float(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


STAT_LABELS = {
    "goals": "Goles",
    "npxg": "xG sin penalti",
    "assists": "Asistencias",
    "xa": "xA",
    "shots_on_target": "Tiros a puerta",
    "key_passes": "Pases clave",
    "dribbles_completed": "Regates completados",
    "touches_opp_box": "Toques en área rival",
    "duels_won": "Duelos ganados",
    "recoveries": "Recuperaciones",
    "passes_final_third": "Pases al último tercio",
    "tackles": "Entradas",
    "interceptions": "Intercepciones",
    "aerial_duels_won": "Aéreos ganados",
    "clearances": "Despejes",
    "blocks": "Bloqueos",
    "goals_prevented": "Goles evitados (PSxG−GA)",
    "saves": "Paradas",
    "save_pct": "% de paradas",
    "high_claim": "Salidas por alto",
    "clean_sheet": "Porterías a cero",
    "saves_inside_box": "Paradas dentro del área",
    "punches": "Puños",
    "acted_as_sweeper": "Salidas de líbero",
    "own_goals": "Goles en propia",
    "red_cards": "Rojas",
    "yellow_cards": "Amarillas",
    "dispossessed": "Pérdidas",
    "dribbled_past": "Regateado",
    "rating": "Rating FotMob",
}


@lru_cache(maxsize=1)
def _model_config() -> dict[str, Any]:
    positions = yaml.safe_load((CONFIG_DIR / "positions.yml").read_text(encoding="utf-8"))
    competitions = yaml.safe_load(
        (CONFIG_DIR / "competitions.yml").read_text(encoding="utf-8")
    )
    return {
        "index": {"individual_weight": 0.82, "trophy_weight": 0.18, "min_matches": 15},
        "rating": positions["rating"],
        "position_groups": positions["position_groups"],
        "penalties": positions["penalties"],
        "competitions": [
            {"code": c["code"], "name": c["name"], "weight": c["weight"]}
            for c in competitions["competitions"]
        ],
        "stages": competitions["stages"],
        "trophies": competitions["trophies"],
        "labels": STAT_LABELS,
        "opponent": {"floor": 0.70, "range": 0.60},
        "formula": "performance × reliability × opponent × competition × stage",
    }


@lru_cache(maxsize=4)
def _season_stats(season: str) -> pd.DataFrame:
    import pyarrow.parquet as pq

    tag = season.replace("/", "-")
    path = ROOT / "data" / "raw" / "fotmob" / f"player_match_stats_full_{tag}.parquet"
    needed = {
        "fotmob_player_id",
        "minutes",
        "rating",
        "started",
        "goals_conceded",
        *STAT_LABELS,
    }
    schema_names = set(pq.read_schema(path).names)
    cols = [c for c in needed if c in schema_names]
    return pd.read_parquet(path, columns=cols)


def _num(series: pd.Series) -> float:
    value = pd.to_numeric(series, errors="coerce").sum()
    if pd.isna(value):
        return 0.0
    return float(value)


def _player_model_stats(
    fotmob_id: str | None,
    position: str | None,
    season: str,
) -> dict[str, Any]:
    config = _model_config()
    group = (position or "MID").upper()
    weights: dict[str, float] = dict(config["position_groups"].get(group) or {})
    penalties: dict[str, float] = dict(config["penalties"])
    empty = {
        "position_group": group,
        "matches": 0,
        "minutes": 0.0,
        "started": 0,
        "mean_rating": None,
        "rating_weight": config["rating"]["weight"],
        "used": [],
        "penalties": [],
    }
    if not fotmob_id:
        return empty
    frame = _season_stats(season)
    rows = frame[frame.fotmob_player_id.astype(str) == str(fotmob_id)]
    if rows.empty:
        return empty
    minutes = _num(rows.minutes)
    per90 = minutes / 90 if minutes else 0.0
    mean_rating = pd.to_numeric(rows.rating, errors="coerce").mean()
    used = []
    for key, weight in weights.items():
        if key == "save_pct" and key not in rows.columns and {"saves", "goals_conceded"} <= set(rows.columns):
            saves = _num(rows.saves)
            conceded = _num(rows.goals_conceded)
            total = saves / (saves + conceded) if (saves + conceded) else 0.0
            per = total
        elif key == "clean_sheet" and key not in rows.columns and "goals_conceded" in rows.columns:
            total = float((pd.to_numeric(rows.goals_conceded, errors="coerce") == 0).sum())
            per = total / per90 if per90 else 0.0
        elif key not in rows.columns:
            continue
        else:
            total = _num(rows[key])
            per = total / per90 if per90 else 0.0
        used.append(
            {
                "key": key,
                "label": STAT_LABELS.get(key, key),
                "weight": float(weight),
                "total": total,
                "per90": per,
            }
        )
    pens = []
    for key, weight in penalties.items():
        if key not in rows.columns:
            continue
        total = _num(rows[key])
        pens.append(
            {
                "key": key,
                "label": STAT_LABELS.get(key, key),
                "weight": float(weight),
                "total": total,
                "per90": total / per90 if per90 else 0.0,
            }
        )
    return {
        "position_group": group,
        "matches": int(len(rows)),
        "minutes": minutes,
        "started": int(pd.to_numeric(rows.started, errors="coerce").fillna(0).sum())
        if "started" in rows.columns
        else 0,
        "mean_rating": None if pd.isna(mean_rating) else float(mean_rating),
        "rating_weight": config["rating"]["weight"],
        "used": used,
        "penalties": pens,
    }


@app.get("/api/model")
def model() -> dict[str, Any]:
    return _model_config()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/seasons")
def seasons() -> dict[str, Any]:
    rows = _rows("SELECT DISTINCT season FROM season_index ORDER BY season DESC")
    return {"seasons": [r["season"] for r in rows]}


_RANKING_FROM = """
        FROM season_index s
        JOIN players p ON p.player_id = s.player_id
        LEFT JOIN LATERAL (
            SELECT external_key
            FROM external_ids
            WHERE entity_type = 'player' AND source = 'fotmob'
              AND entity_id = s.player_id
            LIMIT 1
        ) fm ON true
"""


@app.get("/api/ranking")
def ranking(
    season: str = Query("2025/2026"),
    position: str | None = None,
    under23: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    where = ["s.season = %s"]
    params: list[Any] = [season]
    if position:
        where.append("s.position_group = %s")
        params.append(position.upper())
    if under23:
        where.append("p.age IS NOT NULL AND p.age < 23")
    clause = " AND ".join(where)
    total = _one(
        f"SELECT count(*) AS n FROM season_index s JOIN players p ON p.player_id = s.player_id WHERE {clause}",
        tuple(params),
    )
    rows = _rows(
        f"""
        SELECT s.rank, s.player_id, p.name AS player, s.club, s.position_group,
               s.matches, s.minutes, s.goals, s.assists, s.mean_rating,
               s.individual_score, s.trophies, s.trophy_score, s.index_value,
               p.country, p.country_code, p.age, fm.external_key AS fotmob_player_id
        {_RANKING_FROM}
        WHERE {clause}
        ORDER BY s.rank
        LIMIT %s OFFSET %s
        """,
        (*params, limit, offset),
    )
    by_position = _rows(
        """
        SELECT s.position_group, count(*) AS n,
               avg(s.index_value) AS mean_index
        FROM season_index s
        WHERE s.season = %s
        GROUP BY s.position_group
        ORDER BY n DESC
        """,
        (season,),
    )
    return {
        "season": season,
        "total": int(total["n"]) if total else 0,
        "by_position": [_clean(r) for r in by_position],
        "items": [_clean(r) for r in rows],
    }


@app.get("/api/players/{player_id}")
def player_detail(player_id: int, season: str = Query("2025/2026")) -> dict[str, Any]:
    player = _one(
        """
        SELECT p.player_id, p.name, p.country, p.country_code, p.primary_position,
               p.age, fm.external_key AS fotmob_player_id,
               s.rank, s.club, s.position_group, s.matches, s.minutes, s.goals,
               s.assists, s.mean_rating, s.season_score, s.mean_match_score,
               s.consistency, s.individual_score, s.trophies, s.trophy_score,
               s.index_value, s.season
        FROM players p
        LEFT JOIN season_index s ON s.player_id = p.player_id AND s.season = %s
        LEFT JOIN LATERAL (
            SELECT external_key
            FROM external_ids
            WHERE entity_type = 'player' AND source = 'fotmob'
              AND entity_id = p.player_id
            LIMIT 1
        ) fm ON true
        WHERE p.player_id = %s
        """,
        (season, player_id),
    )
    if player is None:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    trophies = _rows(
        """
        SELECT c.code, c.name, t.role, t.share, t.points
        FROM player_trophy_credit t
        JOIN competitions c ON c.competition_id = t.competition_id
        WHERE t.player_id = %s AND t.season = %s
        ORDER BY t.points DESC
        """,
        (player_id, season),
    )
    return {
        "player": _clean(player),
        "trophies": [_clean(t) for t in trophies],
        "model_stats": _player_model_stats(
            player.get("fotmob_player_id"),
            player.get("position_group") or player.get("primary_position"),
            season,
        ),
    }


@app.get("/api/players/{player_id}/matches")
def player_matches(
    player_id: int,
    season: str = Query("2025/2026"),
    limit: int = Query(80, ge=1, le=200),
) -> dict[str, Any]:
    rows = _rows(
        """
        SELECT m.match_id, m.kickoff_utc, m.date, m.stage, m.home_score, m.away_score,
               c.code AS competition_code, c.name AS competition_name,
               ht.name AS home_team, at.name AS away_team,
               s.position_group, s.minutes, s.rating, s.goals, s.assists,
               s.opponent, s.performance, s.opponent_strength, s.opponent_multiplier,
               s.competition_weight, s.stage_weight, s.match_score, s.coverage_level
        FROM player_match_scores s
        JOIN matches m ON m.match_id = s.match_id
        JOIN competitions c ON c.competition_id = m.competition_id
        JOIN teams ht ON ht.team_id = m.home_team_id
        JOIN teams at ON at.team_id = m.away_team_id
        WHERE s.player_id = %s AND s.season = %s
        ORDER BY COALESCE(m.kickoff_utc, m.date::timestamptz) DESC
        LIMIT %s
        """,
        (player_id, season, limit),
    )
    return {"items": [_clean(r) for r in rows]}


@app.get("/api/trophies")
def trophies(season: str = Query("2025/2026")) -> dict[str, Any]:
    rows = _rows(
        """
        SELECT c.code, c.name, t.winner, t.runner_up, t.decided_by
        FROM season_trophies t
        JOIN competitions c ON c.competition_id = t.competition_id
        WHERE t.season = %s
        ORDER BY c.weight DESC, c.name
        """,
        (season,),
    )
    return {"season": season, "items": [_clean(r) for r in rows]}
