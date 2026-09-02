-- Nextup schema. Applied on every boot; each statement is idempotent.

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
    id              INTEGER PRIMARY KEY,          -- TMDB series id
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
    synced_at       TEXT
);

CREATE TABLE IF NOT EXISTS episode (
    id             INTEGER PRIMARY KEY,           -- TMDB episode id
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
    -- A show on the maybe list is one you are curious about but not following.
    -- It stays out of Next up, the calendar and the coming-soon list.
    shortlist   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watched_episode (
    episode_id  INTEGER PRIMARY KEY REFERENCES episode(id) ON DELETE CASCADE,
    show_id     INTEGER NOT NULL,
    watched_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_watched_show ON watched_episode (show_id);

CREATE TABLE IF NOT EXISTS movie (
    id                   INTEGER PRIMARY KEY,     -- TMDB movie id
    title                TEXT NOT NULL,
    overview             TEXT,
    poster_path          TEXT,
    release_date         TEXT,   -- first release anywhere, usually the cinema
    runtime              INTEGER,
    vote_average         REAL,
    digital_release      TEXT,   -- the date it lands on streaming or download
    providers            TEXT,   -- UK streaming services, one per line
    provider_link        TEXT,   -- TMDB's "where to watch" page
    providers_checked_at TEXT,
    synced_at            TEXT
);

CREATE TABLE IF NOT EXISTS tracked_movie (
    movie_id    INTEGER PRIMARY KEY REFERENCES movie(id) ON DELETE CASCADE,
    added_at    TEXT NOT NULL,
    watched_at  TEXT,
    -- As with shows: a film you like the look of but have not committed to.
    shortlist   INTEGER NOT NULL DEFAULT 0
);

-- Things you said no to on the Discover pages. They stay out of Discover but
-- still turn up in a search, so nothing is ever lost for good.
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
