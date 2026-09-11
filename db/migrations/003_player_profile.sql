-- Age from FotMob lineups, for U23 boards.

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS age SMALLINT;

CREATE INDEX IF NOT EXISTS idx_players_age ON players (age);
