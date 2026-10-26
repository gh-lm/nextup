
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    encrypted   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS admin_user (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS show (
    id              INTEGER PRIMARY KEY,          -- series id: TheTVDB id plus 10^9, or an older number
    name            TEXT NOT NULL,
    overview        TEXT,
    poster_path     TEXT,
    backdrop_path   TEXT,
    first_air_date  TEXT,
    last_air_date   TEXT,
    status          TEXT,
    network         TEXT,
    episode_runtime INTEGER,
    vote_average    REAL,
    original_language TEXT,
    synced_at       TEXT
);

CREATE TABLE IF NOT EXISTS episode (
    id             INTEGER PRIMARY KEY,           -- episode id
    show_id        INTEGER NOT NULL REFERENCES show(id) ON DELETE CASCADE,
    season_number  INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    name           TEXT,
    overview       TEXT,
    air_date       TEXT,
    runtime        INTEGER,
    still_path     TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_unique
    ON episode (show_id, season_number, episode_number);
CREATE INDEX IF NOT EXISTS idx_episode_air ON episode (air_date);

CREATE TABLE IF NOT EXISTS tracked_show (
    show_id     INTEGER PRIMARY KEY REFERENCES show(id) ON DELETE CASCADE,
    added_at    TEXT NOT NULL,
    archived    INTEGER NOT NULL DEFAULT 0,
    favourite   INTEGER NOT NULL DEFAULT 0,
    shortlist   INTEGER NOT NULL DEFAULT 0,
    auto_unarchive INTEGER NOT NULL DEFAULT 1,
    archived_season INTEGER
);

CREATE TABLE IF NOT EXISTS watched_episode (
    episode_id  INTEGER PRIMARY KEY REFERENCES episode(id) ON DELETE CASCADE,
    show_id     INTEGER NOT NULL,
    watched_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_watched_show ON watched_episode (show_id);

CREATE TABLE IF NOT EXISTS movie (
    id                   INTEGER PRIMARY KEY,     -- movie id: as for shows
    title                TEXT NOT NULL,
    overview             TEXT,
    poster_path          TEXT,
    release_date         TEXT,   -- first release anywhere, usually the cinema
    runtime              INTEGER,
    vote_average         REAL,
    original_language    TEXT,
    digital_release      TEXT,   -- no longer used
    providers            TEXT,   -- no longer used
    provider_link        TEXT,   -- no longer used
    providers_checked_at TEXT,
    synced_at            TEXT
);

CREATE TABLE IF NOT EXISTS tracked_movie (
    movie_id    INTEGER PRIMARY KEY REFERENCES movie(id) ON DELETE CASCADE,
    added_at    TEXT NOT NULL,
    watched_at  TEXT,
    shortlist   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dismissed (
    kind         TEXT NOT NULL CHECK (kind IN ('tv', 'movie')),
    item_id      INTEGER NOT NULL,
    dismissed_at TEXT NOT NULL,
    PRIMARY KEY (kind, item_id)
);

CREATE TABLE IF NOT EXISTS sync_run (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    shows_done  INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'running',
    message     TEXT
);
