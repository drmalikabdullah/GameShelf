CREATE TABLE IF NOT EXISTS games (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    gog_id        TEXT,                      -- NULL if we couldn't detect one. This is the
                                              -- build/version number from the source folder
                                              -- listing, taken verbatim - NOT a GOG catalog
                                              -- product id (folder-naming schemes sometimes
                                              -- reuse/collide numbers across different games).
    gog_catalog_id TEXT,                     -- the real GOG catalog product id, looked up from
                                              -- GOG's public catalog by title.
    steam_app_id  TEXT,                      -- Steam app ID for fetching screenshots and metadata
    platform      TEXT NOT NULL DEFAULT 'gog', -- gog | steam | ps3 | ps4
    title         TEXT NOT NULL,
    size_bytes    INTEGER DEFAULT 0,
    folder_path   TEXT,                      -- path to the game's install folder on disk; when
                                              -- set, size_bytes is calculated from it instead of
                                              -- being typed in by hand
    exe_path      TEXT,                      -- path to the game's launch executable; lets the
                                              -- Play button start it directly (gog/steam only)
    raw_paths     TEXT,                      -- JSON array of original folder/file names
    status        TEXT DEFAULT 'backlog',    -- backlog | playing | completed | abandoned
    rating        INTEGER,                   -- 1-10, nullable
    notes         TEXT,
    tags          TEXT,                      -- comma-separated, user-defined
    cover_url     TEXT,
    hero_url      TEXT,                      -- wide banner art for the detail modal
    logo_url      TEXT,                      -- official logo from SteamGridDB
    trailer_url   TEXT,                      -- local /trailers/<game_id>.webm microtrailer
    genres        TEXT,                      -- comma-separated, from enrichment
    description   TEXT,
    system_requirements TEXT,                -- minimum/recommended PC requirements
    developer     TEXT,                      -- comma-separated, from enrichment
    release_date  TEXT,
    latest_build  TEXT,                      -- newest known build id for this title, from
                                              -- check_latest_builds.py comparing against a GOG
                                              -- gamelist.txt snapshot; NULL means unverified,
                                              -- not confirmed up to date
    build_checked_at TEXT,                   -- when latest_build was last refreshed
    case_color    TEXT,                      -- hex color auto-detected from cover_url's dominant
                                              -- color, used to tint the shelf's case-shaped tile
    case_color_override TEXT,                -- hex color the user picked by hand; wins over
                                              -- case_color when set, and survives cover re-fetches
    added_at      TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bonus_content (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,             -- extras | patch
    title         TEXT NOT NULL,
    size_bytes    INTEGER DEFAULT 0,
    raw_paths     TEXT,
    game_id       INTEGER REFERENCES games(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_title ON games(title);

CREATE TABLE IF NOT EXISTS game_screenshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       INTEGER REFERENCES games(id) ON DELETE CASCADE,
    path          TEXT NOT NULL,             -- local /screenshots/<game_id>/<n>.jpg path
    position      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_screenshots_game ON game_screenshots(game_id);

CREATE TABLE IF NOT EXISTS deleted_games (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id   INTEGER,                     -- the game's id before deletion, for reference only
    gog_id        TEXT,
    gog_catalog_id TEXT,
    steam_app_id  TEXT,
    platform      TEXT,
    title         TEXT,
    size_bytes    INTEGER,
    folder_path   TEXT,
    exe_path      TEXT,
    raw_paths     TEXT,
    status        TEXT,
    rating        INTEGER,
    notes         TEXT,
    tags          TEXT,
    cover_url     TEXT,
    hero_url      TEXT,
    logo_url      TEXT,
    trailer_url   TEXT,
    genres        TEXT,
    description   TEXT,
    system_requirements TEXT,
    developer     TEXT,
    release_date  TEXT,
    case_color    TEXT,
    case_color_override TEXT,
    added_at      TEXT,
    updated_at    TEXT,
    deleted_at    TEXT DEFAULT (datetime('now'))
);
