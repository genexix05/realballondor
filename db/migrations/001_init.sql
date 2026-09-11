-- Ballon d'Or Index schema v0

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS competitions (
    competition_id   SERIAL PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    type             TEXT NOT NULL,
    country          TEXT,
    weight           NUMERIC(6,3) NOT NULL DEFAULT 1.000,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS teams (
    team_id          SERIAL PRIMARY KEY,
    name             TEXT NOT NULL,
    short_name       TEXT,
    country          TEXT,
    type             TEXT NOT NULL DEFAULT 'club', -- club | national
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, type)
);

CREATE TABLE IF NOT EXISTS players (
    player_id        SERIAL PRIMARY KEY,
    name             TEXT NOT NULL,
    birth_date       DATE,
    nationality      TEXT,
    primary_position TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_players_name ON players (name);

CREATE TABLE IF NOT EXISTS matches (
    match_id         SERIAL PRIMARY KEY,
    date             DATE NOT NULL,
    season           TEXT NOT NULL,          -- e.g. 2025-2026
    competition_id   INTEGER NOT NULL REFERENCES competitions(competition_id),
    stage            TEXT,
    home_team_id     INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id     INTEGER NOT NULL REFERENCES teams(team_id),
    home_score       INTEGER,
    away_score       INTEGER,
    venue            TEXT,
    attendance       INTEGER,
    source           TEXT,
    source_match_id  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (competition_id, date, home_team_id, away_team_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_season ON matches (season);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches (date);

CREATE TABLE IF NOT EXISTS player_match_stats (
    player_match_id      BIGSERIAL PRIMARY KEY,
    match_id             INTEGER NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id            INTEGER NOT NULL REFERENCES players(player_id),
    team_id              INTEGER NOT NULL REFERENCES teams(team_id),
    minutes              NUMERIC(5,1),
    started              BOOLEAN,
    position             TEXT,
    rating               NUMERIC(4,2),

    goals                INTEGER,
    assists              INTEGER,
    shots                INTEGER,
    shots_on_target      INTEGER,
    xg                   NUMERIC(6,3),
    xa                   NUMERIC(6,3),

    passes               INTEGER,
    passes_completed     INTEGER,
    key_passes           INTEGER,
    progressive_passes   INTEGER,
    progressive_carries  INTEGER,

    dribbles             INTEGER,
    dribbles_completed   INTEGER,

    tackles              INTEGER,
    interceptions        INTEGER,
    clearances           INTEGER,
    blocks               INTEGER,

    duels                INTEGER,
    duels_won            INTEGER,
    aerial_duels         INTEGER,
    aerial_duels_won     INTEGER,
    recoveries           INTEGER,

    fouls                INTEGER,
    fouls_won            INTEGER,
    yellow_cards         INTEGER,
    red_cards            INTEGER,

    source               TEXT,
    raw                  JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (match_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_pms_player ON player_match_stats (player_id);
CREATE INDEX IF NOT EXISTS idx_pms_team ON player_match_stats (team_id);

CREATE TABLE IF NOT EXISTS team_rankings (
    ranking_id       BIGSERIAL PRIMARY KEY,
    team_id          INTEGER NOT NULL REFERENCES teams(team_id),
    ranking_date     DATE NOT NULL,
    source           TEXT NOT NULL, -- UEFA | FIFA
    rank             INTEGER,
    points           NUMERIC(10,3),
    coefficient      NUMERIC(10,3),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (team_id, ranking_date, source)
);

CREATE INDEX IF NOT EXISTS idx_team_rankings_asof
    ON team_rankings (team_id, source, ranking_date DESC);

CREATE TABLE IF NOT EXISTS external_ids (
    external_id_id   BIGSERIAL PRIMARY KEY,
    entity_type      TEXT NOT NULL, -- player | team | match | competition
    entity_id        INTEGER NOT NULL,
    source           TEXT NOT NULL, -- fbref | football-data | statsbomb
    external_key     TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, source, external_key)
);

CREATE INDEX IF NOT EXISTS idx_external_ids_lookup
    ON external_ids (entity_type, entity_id, source);

CREATE TABLE IF NOT EXISTS ingest_runs (
    ingest_run_id    BIGSERIAL PRIMARY KEY,
    source           TEXT NOT NULL,
    league           TEXT,
    season           TEXT,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'running', -- running | success | failed
    rows_upserted    INTEGER DEFAULT 0,
    error_message    TEXT,
    meta             JSONB
);
