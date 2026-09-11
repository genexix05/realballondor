-- Scoring, trophies and extra FotMob context. Additive on top of 001_init.

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS kickoff_utc TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS coverage_level TEXT,
    ADD COLUMN IF NOT EXISTS player_rows INTEGER,
    ADD COLUMN IF NOT EXISTS referee TEXT,
    ADD COLUMN IF NOT EXISTS venue_city TEXT,
    ADD COLUMN IF NOT EXISTS venue_country TEXT,
    ADD COLUMN IF NOT EXISTS venue_capacity INTEGER;

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS country TEXT,
    ADD COLUMN IF NOT EXISTS country_code TEXT;

ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_source_key;
ALTER TABLE matches ADD CONSTRAINT matches_source_key UNIQUE (source, source_match_id);

CREATE TABLE IF NOT EXISTS player_match_scores (
    player_match_score_id BIGSERIAL PRIMARY KEY,
    match_id              INTEGER NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id             INTEGER NOT NULL REFERENCES players(player_id),
    team_id               INTEGER NOT NULL REFERENCES teams(team_id),
    season                TEXT NOT NULL,
    position_group        TEXT,
    opponent              TEXT,
    minutes               NUMERIC(5,1),
    rating                NUMERIC(4,2),
    goals                 INTEGER,
    assists               INTEGER,
    stats_score           NUMERIC(10,6),
    rating_score          NUMERIC(10,6),
    penalty_score         NUMERIC(10,6),
    performance           NUMERIC(10,6),
    reliability           NUMERIC(10,6),
    opponent_strength     NUMERIC(10,6),
    opponent_multiplier   NUMERIC(10,6),
    competition_weight    NUMERIC(6,3),
    stage_weight          NUMERIC(6,3),
    match_score           NUMERIC(12,6) NOT NULL,
    coverage_level        TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (match_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_pmscores_player_season
    ON player_match_scores (player_id, season);
CREATE INDEX IF NOT EXISTS idx_pmscores_match
    ON player_match_scores (match_id);

CREATE TABLE IF NOT EXISTS season_index (
    season_index_id     BIGSERIAL PRIMARY KEY,
    season              TEXT NOT NULL,
    player_id           INTEGER NOT NULL REFERENCES players(player_id),
    rank                INTEGER NOT NULL,
    club_team_id        INTEGER REFERENCES teams(team_id),
    club                TEXT,
    position_group      TEXT,
    matches             INTEGER,
    minutes             NUMERIC(8,1),
    goals               INTEGER,
    assists             INTEGER,
    mean_rating         NUMERIC(4,2),
    season_score        NUMERIC(12,5),
    mean_match_score    NUMERIC(10,5),
    consistency         NUMERIC(8,5),
    individual_score    NUMERIC(10,5),
    trophies            INTEGER NOT NULL DEFAULT 0,
    trophy_score        NUMERIC(10,5),
    index_value         NUMERIC(10,5) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (season, player_id)
);

CREATE INDEX IF NOT EXISTS idx_season_index_rank
    ON season_index (season, rank);

CREATE TABLE IF NOT EXISTS season_trophies (
    season_trophy_id    SERIAL PRIMARY KEY,
    season              TEXT NOT NULL,
    competition_id      INTEGER NOT NULL REFERENCES competitions(competition_id),
    winner_team_id      INTEGER REFERENCES teams(team_id),
    runner_up_team_id   INTEGER REFERENCES teams(team_id),
    winner              TEXT,
    runner_up           TEXT,
    decided_by          TEXT,
    UNIQUE (season, competition_id)
);

CREATE TABLE IF NOT EXISTS player_trophy_credit (
    player_trophy_id    BIGSERIAL PRIMARY KEY,
    season              TEXT NOT NULL,
    player_id           INTEGER NOT NULL REFERENCES players(player_id),
    competition_id      INTEGER NOT NULL REFERENCES competitions(competition_id),
    team_id             INTEGER REFERENCES teams(team_id),
    role                TEXT NOT NULL,
    share               NUMERIC(8,5),
    points              NUMERIC(10,5),
    UNIQUE (season, player_id, competition_id, role)
);
