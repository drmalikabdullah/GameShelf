#!/usr/bin/env python3
"""
GOG Catalogue - local Flask app.

Run:
    python3 app.py
Then open http://127.0.0.1:5000
"""
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, g, jsonify, request, send_from_directory

import steamgriddb
import gog_catalog
import check_latest_builds

SIZE_RE = re.compile(r'^([\d.]+)\s*([KMGT]?)B?$', re.IGNORECASE)
UNIT_MULT = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
NON_ALNUM_RE = re.compile(r'[^a-z0-9]+')
PLATFORM_EXPORT_LABEL = {"gog": "GOG", "steam": "Steam", "ps3": "PS3", "ps4": "PS4"}
VALID_PLATFORMS = set(PLATFORM_EXPORT_LABEL)


def normalize_search(text):
    """Lowercase and strip all non-alphanumeric characters, so searching
    "stalker" finds "S.T.A.L.K.E.R." and punctuation/spacing differences
    elsewhere (colons, apostrophes, hyphens) don't block a match either."""
    return NON_ALNUM_RE.sub('', (text or '').lower())


def parse_size_input(token):
    m = SIZE_RE.match((token or '').strip())
    if not m:
        return None
    value, unit = m.groups()
    return int(float(value) * UNIT_MULT.get(unit.upper(), 1))


def dominant_color(image_path):
    """The single most common color in the image, as '#rrggbb' - used to
    tint a game's case tile so the shelf isn't uniformly blue. Quantizing
    down to a handful of buckets first (rather than counting every exact
    pixel value) means near-identical shades of the "same" color merge into
    one bucket instead of splitting the vote and losing to a smaller but
    more uniform patch (e.g. a logo)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(image_path).convert("RGB").resize((64, 64))
        quantized = im.quantize(colors=6, method=Image.MEDIANCUT)
        counts = quantized.getcolors()
        if not counts:
            return None
        counts.sort(reverse=True)
        _, idx = counts[0]
        palette = quantized.getpalette()
        r, g, b = palette[idx * 3:idx * 3 + 3]
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None


def calculate_folder_size(folder_path):
    """Recursively sum file sizes under folder_path. Returns None if the
    path doesn't exist or isn't a directory, so the caller can reject the
    save with a clear error instead of silently storing a bad path."""
    path = Path(folder_path)
    if not path.is_dir():
        return None
    total = 0
    for entry in path.rglob('*'):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            continue
    return total

if getattr(sys, "frozen", False):
    # Running as a PyInstaller-built exe - games.db/static/config live next to
    # the exe itself (not the temp dir it unpacks into), so they stay
    # writable and persist across runs when the whole folder is copied.
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "games.db"
COVERS_DIR = BASE_DIR / "static" / "covers"
HEROES_DIR = BASE_DIR / "static" / "heroes"
LOGOS_DIR = BASE_DIR / "static" / "logos"
TRAILERS_DIR = BASE_DIR / "static" / "trailers"
OVERRIDES_PATH = BASE_DIR / "cover_overrides.json"

if not DB_PATH.exists():
    # First run on this machine (e.g. a friend's copy of the packaged app) -
    # create an empty library from schema.sql instead of leaving a
    # tableless sqlite file, so "+ Add Game" works immediately with no
    # separate setup step.
    _init_db = sqlite3.connect(DB_PATH)
    _init_db.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    _init_db.commit()
    _init_db.close()

def ensure_columns(db, table, columns):
    """Add optional columns without rebuilding an existing personal database."""
    existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    for name, column_type in columns.items():
        if name not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


# Keep existing personal databases compatible when optional metadata columns
# are introduced. The recycle-bin table deliberately mirrors every editable
# game field so a restore is lossless.
_migration_db = sqlite3.connect(DB_PATH)
ensure_columns(_migration_db, "games", {
    "system_requirements": "TEXT",
    "trailer_url": "TEXT",
})
ensure_columns(_migration_db, "deleted_games", {
    "steam_app_id": "TEXT",
    "exe_path": "TEXT",
    "logo_url": "TEXT",
    "case_color": "TEXT",
    "case_color_override": "TEXT",
    "system_requirements": "TEXT",
    "trailer_url": "TEXT",
})
_migration_db.commit()
_migration_db.close()


def load_overrides():
    if OVERRIDES_PATH.exists():
        return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return {}

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")


@app.after_request
def set_cache_policy(response):
    """Keep code/API responses fresh while allowing local artwork to cache."""
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.path.lower().endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".webm")
    ):
        response.headers["Cache-Control"] = "private, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-cache"
    return response


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def human_size(num_bytes):
    size = float(num_bytes or 0)
    for unit in ["B", "K", "M", "G", "T"]:
        if size < 1024 or unit == "T":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def serialize_game(row):
    d = dict(row)
    d["size_human"] = human_size(d["size_bytes"])
    try:
        d["raw_paths"] = json.loads(d["raw_paths"]) if d["raw_paths"] else []
    except (TypeError, json.JSONDecodeError):
        d["raw_paths"] = []
    d["tags_list"] = [t.strip() for t in (d.get("tags") or "").split(",") if t.strip()]
    return d


def static_file_from_url(url):
    """Resolve a local artwork URL without allowing it to escape static/."""
    if not url:
        return None
    static_root = (BASE_DIR / "static").resolve()
    candidate = (static_root / str(url).lstrip("/\\")).resolve()
    if candidate == static_root or static_root not in candidate.parents:
        return None
    return candidate


def unlink_static_url(url):
    path = static_file_from_url(url)
    if path is not None:
        path.unlink(missing_ok=True)


def save_cover(db, game_id, data, ext):
    old_cover = db.execute("SELECT cover_url FROM games WHERE id = ?", (game_id,)).fetchone()["cover_url"]
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    dest = COVERS_DIR / f"{game_id}.{ext}"
    dest.write_bytes(data)
    if old_cover and Path(old_cover).name != dest.name:
        unlink_static_url(old_cover)

    color = dominant_color(dest)
    db.execute(
        "UPDATE games SET cover_url = ?, case_color = ? WHERE id = ?",
        (f"/covers/{game_id}.{ext}", color, game_id),
    )
    db.commit()


def save_logo(db, game_id, data, ext):
    """Download and store official SteamGridDB logo image."""
    old_logo = db.execute("SELECT logo_url FROM games WHERE id = ?", (game_id,)).fetchone()["logo_url"]
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    dest = LOGOS_DIR / f"{game_id}.{ext}"
    dest.write_bytes(data)
    if old_logo and Path(old_logo).name != dest.name:
        unlink_static_url(old_logo)

    db.execute("UPDATE games SET logo_url = ? WHERE id = ?", (f"/logos/{game_id}.{ext}", game_id))
    db.commit()


def save_hero(db, game_id, data, ext):
    old_hero = db.execute("SELECT hero_url FROM games WHERE id = ?", (game_id,)).fetchone()["hero_url"]
    HEROES_DIR.mkdir(parents=True, exist_ok=True)
    dest = HEROES_DIR / f"{game_id}.{ext}"
    dest.write_bytes(data)
    if old_hero and Path(old_hero).name != dest.name:
        unlink_static_url(old_hero)

    db.execute("UPDATE games SET hero_url = ? WHERE id = ?", (f"/heroes/{game_id}.{ext}", game_id))
    db.commit()


def refresh_hero(db, game_id, title):
    """Best-effort hero banner fetch - no-op (not an error) if no API key or
    nothing matches, same philosophy as cover fetching."""
    api_key = steamgriddb.get_api_key()
    if not api_key:
        return
    data, ext = steamgriddb.fetch_hero(title, api_key)
    if data is not None:
        save_hero(db, game_id, data, ext)


def verify_gog_id(db, game_id, title):
    """Look up the real GOG catalog product id for `title` from GOG's public
    catalog and store it in gog_catalog_id. gog_id is a separate field -
    the user's own build-version number from their folder naming, not a
    catalog id, so there's no "match/mismatch" between the two to check.
    Also fetches the release year and GOG's public user rating while we
    have a confirmed catalog id - the rating only fills in when the game
    doesn't already have one, so it never overwrites a rating the user set
    themselves by clicking stars."""
    real_id, _ = gog_catalog.find_catalog_id(title)
    year, public_rating = gog_catalog.find_release_year_and_rating(real_id) if real_id else (None, None)
    requirements = gog_catalog.fetch_system_requirements(real_id) if real_id else None
    db.execute(
        """UPDATE games
           SET gog_catalog_id = ?,
               release_date = ?,
               system_requirements = COALESCE(?, system_requirements)
           WHERE id = ?""",
        (real_id, year, requirements, game_id),
    )
    if public_rating is not None:
        db.execute("UPDATE games SET rating = ? WHERE id = ? AND rating IS NULL", (public_rating, game_id))
    db.commit()


def refresh_steam_release_year(db, game_id, title):
    """Best-effort Steam metadata lookup for a Steam-platform game.

    Saves the app id, release year, review score, and short description used
    as the story in Big Picture mode.
    """
    match = steamgriddb.find_steam_appid(title)
    year, public_rating, description, requirements = None, None, None, None
    if match:
        year = steamgriddb.fetch_steam_release_year(match["id"])
        public_rating = steamgriddb.fetch_steam_review_score(match["id"])
        description, requirements = steamgriddb.fetch_steam_description_and_requirements(match["id"])
        db.execute("UPDATE games SET steam_app_id = ? WHERE id = ?", (match["id"], game_id))
    db.execute(
        """UPDATE games
           SET release_date = ?,
               description = COALESCE(?, description),
               system_requirements = COALESCE(?, system_requirements)
           WHERE id = ?""",
        (year, description, requirements, game_id),
    )
    if public_rating is not None:
        db.execute("UPDATE games SET rating = ? WHERE id = ? AND rating IS NULL", (public_rating, game_id))
    db.commit()


def apply_title(db, game_id, raw_title, platform="gog"):
    """Given raw user input for a game's title - a plain title, or a pasted
    SteamGridDB game URL (e.g. https://www.steamgriddb.com/game/5209422) -
    fetch matching cover art and return the title that should actually be
    stored. A pasted URL resolves to that exact game with certainty, which is
    how a user can disambiguate cases where title search alone can't tell
    apart e.g. a base game from a same-named spin-off. No-op on the cover
    (not an error) if nothing matches - the title/game save itself should
    never fail because of this.

    SteamGridDB needs an API key the user has to sign up for separately, so
    a fresh install (e.g. a friend's copy with no key configured yet) would
    otherwise show zero cover art for every game added. GOG's own public
    catalog (gog_catalog.fetch_cover) needs no key at all, so it's tried as
    a fallback for platform='gog' titles whenever SteamGridDB isn't
    available or came up empty - covering the common case of adding an
    actual GOG game by its real title with no setup required."""
    api_key = steamgriddb.get_api_key()

    if api_key:
        sgdb_id = steamgriddb.parse_game_url(raw_title)
        if sgdb_id is not None:
            data, ext = steamgriddb.fetch_cover_by_id(sgdb_id, api_key)
            if data is not None:
                save_cover(db, game_id, data, ext)
            hero_data, hero_ext = steamgriddb.fetch_hero_by_id(sgdb_id, api_key)
            if hero_data is not None:
                save_hero(db, game_id, hero_data, hero_ext)
            logo_data, logo_ext = steamgriddb.find_logo_by_id(sgdb_id, api_key)
            if logo_data is not None:
                save_logo(db, game_id, logo_data, logo_ext)
            return steamgriddb.fetch_game_name(sgdb_id, api_key) or raw_title

        override = load_overrides().get(raw_title)
        if override:
            if "steam_appid" in override:
                data, ext = steamgriddb.fetch_steam_official(override["steam_appid"])
                hero_data = steamgriddb.fetch_steam_hero(override["steam_appid"])
                hero_ext = "jpg"
            else:
                data, ext = steamgriddb.fetch_cover_by_id(override["sgdb_id"], api_key)
                hero_data, hero_ext = steamgriddb.fetch_hero_by_id(override["sgdb_id"], api_key)
            if data is not None:
                save_cover(db, game_id, data, ext)
            if hero_data is not None:
                save_hero(db, game_id, hero_data, hero_ext)
            if "steam_appid" not in override:
                logo_data, logo_ext = steamgriddb.find_logo_by_id(override["sgdb_id"], api_key)
                if logo_data is not None:
                    save_logo(db, game_id, logo_data, logo_ext)
            return raw_title

        data, ext = steamgriddb.fetch_cover(raw_title, api_key)
        if data is not None:
            save_cover(db, game_id, data, ext)
            refresh_hero(db, game_id, raw_title)
            logo_data, logo_ext = steamgriddb.fetch_logo(raw_title, api_key)
            if logo_data is not None:
                save_logo(db, game_id, logo_data, logo_ext)
            return raw_title

    if platform == "gog":
        data, ext = gog_catalog.fetch_cover(raw_title)
        if data is not None:
            save_cover(db, game_id, data, ext)

    return raw_title


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/steam")
def steam_page():
    return send_from_directory(app.static_folder, "steam.html")


@app.route("/ps3")
def ps3_page():
    return send_from_directory(app.static_folder, "ps3.html")


@app.route("/ps4")
def ps4_page():
    return send_from_directory(app.static_folder, "ps4.html")


@app.route("/dashboard")
def dashboard_page():
    return send_from_directory(app.static_folder, "dashboard.html")


@app.route("/settings")
def settings_page():
    return send_from_directory(app.static_folder, "settings.html")




@app.route("/api/settings/steamgriddb_key", methods=["GET"])
def get_steamgriddb_key():
    """Never echoes the actual key back to the page - just whether one is
    configured and where it came from, enough for the settings UI to show
    status without putting the secret in a GET response/devtools history."""
    env_key = os.environ.get("STEAMGRIDDB_API_KEY")
    if env_key:
        return jsonify({"configured": True, "source": "environment variable"})
    if steamgriddb.KEY_FILE.exists() and steamgriddb.KEY_FILE.read_text(encoding="utf-8").strip():
        return jsonify({"configured": True, "source": "steamgriddb_key.txt"})
    return jsonify({"configured": False, "source": None})


@app.route("/api/settings/steamgriddb_key", methods=["POST"])
def save_steamgriddb_key():
    data = request.get_json(force=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        steamgriddb.KEY_FILE.unlink(missing_ok=True)
        return jsonify({"configured": False, "source": None})
    steamgriddb.KEY_FILE.write_text(key, encoding="utf-8")
    return jsonify({"configured": True, "source": "steamgriddb_key.txt"})


@app.route("/api/games")
def list_games():
    db = get_db()
    platform = request.args.get("platform", "gog")
    status = request.args.get("status")
    q = request.args.get("q")
    tag = request.args.get("tag")
    sort = request.args.get("sort", "title")

    sql = "SELECT * FROM games WHERE 1=1"
    params = []
    if platform != "all":
        sql += " AND platform = ?"
        params.append(platform)
    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)
    if tag:
        sql += " AND (',' || tags || ',') LIKE ?"
        params.append(f"%,{tag},%")
    if sort == "missing":
        sql += " AND (folder_path IS NULL OR folder_path = '')"

    sort_columns = {
        "title": "title COLLATE NOCASE ASC",
        "size": "size_bytes DESC",
        "rating": "rating DESC",
        "added": "added_at DESC",
        "missing": "title COLLATE NOCASE ASC",
    }
    sql += " ORDER BY " + sort_columns.get(sort, sort_columns["title"])

    rows = db.execute(sql, params).fetchall()
    games = [serialize_game(r) for r in rows]
    if q:
        # Plain substring matching fails on stylized titles like
        # "S.T.A.L.K.E.R." - searching "stalker" would never match because
        # of the literal periods between every letter. Strip non-alnum
        # characters from both sides before comparing instead.
        needle = normalize_search(q)
        games = [g for g in games if needle in normalize_search(g["title"])]
    return jsonify(games)


@app.route("/api/games/<int:game_id>", methods=["PATCH"])
def update_game(game_id):
    db = get_db()
    row = db.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    data = request.get_json(force=True) or {}
    allowed = {"status", "rating", "notes", "tags", "title", "cover_url", "gog_id", "folder_path", "exe_path", "case_color_override"}
    updates = {k: v for k, v in data.items() if k in allowed}

    if "folder_path" in updates:
        folder_path = (updates["folder_path"] or "").strip()
        updates["folder_path"] = folder_path or None
        if folder_path:
            size = calculate_folder_size(folder_path)
            if size is None:
                return jsonify({"error": f"folder not found: {folder_path}"}), 400
            updates["size_bytes"] = size
    elif "size_human" in data:
        parsed = parse_size_input(data["size_human"])
        if parsed is None:
            return jsonify({"error": "invalid size, use e.g. 25G, 500M, 1.5T"}), 400
        updates["size_bytes"] = parsed

    if "exe_path" in updates:
        exe_path = (updates["exe_path"] or "").strip()
        updates["exe_path"] = exe_path or None
        if exe_path and not Path(exe_path).is_file():
            return jsonify({"error": f"file not found: {exe_path}"}), 400
        if exe_path and "status" not in updates:
            updates["status"] = "playing"

    if "case_color_override" in updates:
        color = (updates["case_color_override"] or "").strip()
        if color and not re.match(r"^#[0-9a-fA-F]{6}$", color):
            return jsonify({"error": "case_color_override must be a #rrggbb hex color"}), 400
        updates["case_color_override"] = color or None

    if not updates:
        return jsonify({"error": "no valid fields"}), 400

    valid_statuses = {"backlog", "playing", "completed", "abandoned"}
    if "status" in updates and updates["status"] not in valid_statuses:
        return jsonify({"error": f"status must be one of {sorted(valid_statuses)}"}), 400
    if "rating" in updates and updates["rating"] is not None:
        try:
            r = int(updates["rating"])
        except (TypeError, ValueError):
            return jsonify({"error": "rating must be an integer 1-10"}), 400
        if not (1 <= r <= 10):
            return jsonify({"error": "rating must be between 1 and 10"}), 400
        updates["rating"] = r

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [game_id]
    db.execute(f"UPDATE games SET {set_clause}, updated_at = datetime('now') WHERE id = ?", params)
    db.commit()

    new_title = updates.get("title")
    if new_title and new_title != row["title"]:
        resolved_title = apply_title(db, game_id, new_title, row["platform"])
        if resolved_title != new_title:
            db.execute("UPDATE games SET title = ? WHERE id = ?", (resolved_title, game_id))
            db.commit()
        if row["platform"] == "gog":
            verify_gog_id(db, game_id, resolved_title)
        elif row["platform"] == "steam":
            refresh_steam_release_year(db, game_id, resolved_title)

    row = db.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    return jsonify(serialize_game(row))


@app.route("/api/games", methods=["POST"])
def create_game():
    db = get_db()
    data = request.get_json(force=True) or {}
    raw_title = (data.get("title") or "").strip()
    if not raw_title:
        return jsonify({"error": "title is required"}), 400
    platform = data.get("platform", "gog")
    if platform not in VALID_PLATFORMS:
        return jsonify(
            {"error": f"platform must be one of {sorted(VALID_PLATFORMS)}"}
        ), 400

    cur = db.execute(
        "INSERT INTO games (title, platform, size_bytes, raw_paths) VALUES (?, ?, 0, '[]')",
        (raw_title, platform),
    )
    game_id = cur.lastrowid
    db.commit()

    resolved_title = apply_title(db, game_id, raw_title, platform)
    if resolved_title != raw_title:
        db.execute("UPDATE games SET title = ? WHERE id = ?", (resolved_title, game_id))
        db.commit()
    if platform == "gog":
        verify_gog_id(db, game_id, resolved_title)
    elif platform == "steam":
        refresh_steam_release_year(db, game_id, resolved_title)

    row = db.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    return jsonify(serialize_game(row)), 201


DELETED_GAMES_LIMIT = 50
ARCHIVE_COLUMNS = [
    "gog_id", "gog_catalog_id", "steam_app_id", "platform", "title",
    "size_bytes", "folder_path", "exe_path", "raw_paths", "status", "rating",
    "notes", "tags", "cover_url", "hero_url", "logo_url", "trailer_url", "genres",
    "description", "system_requirements", "developer", "release_date",
    "case_color", "case_color_override", "added_at", "updated_at",
]


@app.route("/api/games/<int:game_id>", methods=["DELETE"])
def delete_game(game_id):
    """Soft-delete: archive the full row into deleted_games (cover/hero
    files are left on disk, not unlinked, so a restore brings back the
    original art) instead of destroying it outright. Only the oldest
    entries beyond DELETED_GAMES_LIMIT get permanently purged."""
    db = get_db()
    row = db.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    db.execute("UPDATE bonus_content SET game_id = NULL WHERE game_id = ?", (game_id,))
    columns = ["original_id"] + ARCHIVE_COLUMNS
    values = [game_id] + [row[c] for c in ARCHIVE_COLUMNS]
    placeholders = ", ".join("?" * len(columns))
    db.execute(f"INSERT INTO deleted_games ({', '.join(columns)}) VALUES ({placeholders})", values)
    db.execute("DELETE FROM games WHERE id = ?", (game_id,))
    db.commit()

    purge_ids = db.execute(
        """
        SELECT id, original_id, cover_url, hero_url, logo_url, trailer_url
        FROM deleted_games
        ORDER BY deleted_at DESC
        LIMIT -1 OFFSET ?
        """,
        (DELETED_GAMES_LIMIT,),
    ).fetchall()
    for purge_row in purge_ids:
        for url in (purge_row["cover_url"], purge_row["hero_url"], purge_row["logo_url"], purge_row["trailer_url"]):
            unlink_static_url(url)
        db.execute(
            "DELETE FROM game_screenshots WHERE game_id = ?",
            (purge_row["original_id"],),
        )
        db.execute("DELETE FROM deleted_games WHERE id = ?", (purge_row["id"],))
    db.commit()

    return "", 204


@app.route("/api/deleted_games")
def list_deleted_games():
    db = get_db()
    rows = db.execute("SELECT * FROM deleted_games ORDER BY deleted_at DESC").fetchall()
    return jsonify([serialize_game(r) for r in rows])


@app.route("/api/deleted_games/<int:trash_id>/restore", methods=["POST"])
def restore_deleted_game(trash_id):
    db = get_db()
    row = db.execute("SELECT * FROM deleted_games WHERE id = ?", (trash_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    placeholders = ", ".join("?" * len(ARCHIVE_COLUMNS))
    cur = db.execute(
        f"INSERT INTO games ({', '.join(ARCHIVE_COLUMNS)}) VALUES ({placeholders})",
        [row[c] for c in ARCHIVE_COLUMNS],
    )
    db.execute(
        "UPDATE game_screenshots SET game_id = ? WHERE game_id = ?",
        (cur.lastrowid, row["original_id"]),
    )
    db.execute("DELETE FROM deleted_games WHERE id = ?", (trash_id,))
    db.commit()

    new_row = db.execute("SELECT * FROM games WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(serialize_game(new_row)), 201


@app.route("/api/games/<int:game_id>/bonus")
def game_bonus(game_id):
    db = get_db()
    rows = db.execute("SELECT * FROM bonus_content WHERE game_id = ?", (game_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/games/<int:game_id>/screenshots")
def game_screenshots(game_id):
    """Locally-downloaded screenshots (see enrich_story.py) - served straight
    from static/screenshots/<game_id>/, nothing fetched live from the web."""
    db = get_db()
    rows = db.execute(
        "SELECT path FROM game_screenshots WHERE game_id = ? ORDER BY position", (game_id,)
    ).fetchall()
    return jsonify([r["path"] for r in rows])


@app.route("/api/games/<int:game_id>/open_folder", methods=["POST"])
def open_folder(game_id):
    db = get_db()
    row = db.execute("SELECT folder_path FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    folder_path = row["folder_path"]
    if not folder_path or not Path(folder_path).is_dir():
        return jsonify({"error": "folder not found on disk"}), 400
    system = platform.system()
    if system == "Windows":
        os.startfile(folder_path)
    elif system == "Darwin":
        subprocess.Popen(["open", folder_path])
    else:
        subprocess.Popen(["xdg-open", folder_path])
    return "", 204


@app.route("/api/games/<int:game_id>/play", methods=["POST"])
def play_game(game_id):
    db = get_db()
    row = db.execute("SELECT exe_path FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    exe_path = row["exe_path"]
    if not exe_path or not Path(exe_path).is_file():
        return jsonify({"error": "executable not found on disk"}), 400
    subprocess.Popen([exe_path], cwd=str(Path(exe_path).parent))
    return "", 204


@app.route("/api/stats")
def stats():
    db = get_db()
    platform = request.args.get("platform", "gog")
    where = "" if platform == "all" else "WHERE platform = ?"
    params = [] if platform == "all" else [platform]

    total = db.execute(f"SELECT COUNT(*) c FROM games {where}", params).fetchone()["c"]
    total_size = db.execute(f"SELECT COALESCE(SUM(size_bytes),0) s FROM games {where}", params).fetchone()["s"]
    by_status = {
        r["status"]: r["c"]
        for r in db.execute(f"SELECT status, COUNT(*) c FROM games {where} GROUP BY status", params)
    }

    catalog_join = "AND gog_catalog_id IS NOT NULL AND gog_catalog_id != ''" if where else "WHERE gog_catalog_id IS NOT NULL AND gog_catalog_id != ''"
    ids_verified = db.execute(f"SELECT COUNT(*) c FROM games {where} {catalog_join}", params).fetchone()["c"]

    folder_join = "AND folder_path IS NOT NULL AND folder_path != ''" if where else "WHERE folder_path IS NOT NULL AND folder_path != ''"
    folders_linked = db.execute(f"SELECT COUNT(*) c FROM games {where} {folder_join}", params).fetchone()["c"]

    return jsonify({
        "total_games": total,
        "total_size_human": human_size(total_size),
        "by_status": by_status,
        "ids_verified": ids_verified,
        "folders_linked": folders_linked,
        "folders_missing": total - folders_linked,
    })


@app.route("/api/build_status")
def build_status():
    """Up to date / outdated / unverified breakdown against the latest_build
    column (see check_latest_builds.py) - GOG only, since that's currently
    the only platform with a comparable build-number source.

    A game recorded with an old-style X.Y.Z.W version string instead of a
    numeric GOG build id (gog_id contains 2+ dots - see check_latest_builds.py
    and the user's own confirmation these are legitimate, just an older
    convention) can never be compared against this list's numeric build ids
    at all, so it's split out into its own "not_comparable" bucket instead
    of inflating "unverified" with games that were never checkable to
    begin with."""
    db = get_db()
    rows = db.execute(
        "SELECT id, title, gog_id, latest_build, cover_url, updated_at FROM games "
        "WHERE platform='gog' AND gog_id IS NOT NULL AND gog_id != ''"
    ).fetchall()

    up_to_date = outdated = unverified = 0
    outdated_list = []
    unverified_list = []
    not_comparable_list = []
    for r in rows:
        # a real GOG build id is always plain digits - anything else (a
        # dotted "2.1.0.17", or even space-separated like "2 1 0 4") is the
        # old X.Y.Z.W installer-version convention, never comparable here
        if not r["gog_id"].isdigit():
            not_comparable_list.append({"id": r["id"], "title": r["title"], "gog_id": r["gog_id"]})
            continue
        if not r["latest_build"]:
            unverified += 1
            unverified_list.append({
                "id": r["id"], "title": r["title"], "cover_url": r["cover_url"],
                "gog_id": r["gog_id"], "reason": "No build info available"
            })
            continue
        try:
            current = int(r["gog_id"]) if r["gog_id"].isdigit() else None
            latest = int(r["latest_build"])
        except ValueError:
            unverified += 1
            unverified_list.append({
                "id": r["id"], "title": r["title"], "cover_url": r["cover_url"],
                "gog_id": r["gog_id"], "reason": "Invalid build format"
            })
            continue
        if current is None:
            unverified += 1
            unverified_list.append({
                "id": r["id"], "title": r["title"], "cover_url": r["cover_url"],
                "gog_id": r["gog_id"], "reason": "Missing current build"
            })
            continue
        if current < latest:
            outdated += 1
            outdated_list.append({
                "id": r["id"], "title": r["title"], "cover_url": r["cover_url"],
                "updated_at": r["updated_at"], "current_build": current, "latest_build": latest,
            })
        else:
            up_to_date += 1

    outdated_list.sort(key=lambda g: g["title"].lower())
    unverified_list.sort(key=lambda g: g["title"].lower())
    not_comparable_list.sort(key=lambda g: g["title"].lower())
    return jsonify({
        "total": len(rows),
        "up_to_date": up_to_date,
        "outdated": outdated,
        "unverified": unverified,
        "not_comparable": len(not_comparable_list),
        "outdated_list": outdated_list,
        "unverified_list": unverified_list,
        "not_comparable_list": not_comparable_list,
    })


@app.route("/api/build_status/upload", methods=["POST"])
def upload_gamelist():
    """Accept an uploaded gamelist.txt (or any similarly-formatted snapshot)
    from the dashboard, run the same comparison as check_latest_builds.py,
    and save a copy next to games.db so `python check_latest_builds.py` can
    be re-run against it later without re-uploading."""
    file = request.files.get("gamelist")
    if file is None or not file.filename:
        return jsonify({"error": "no file uploaded"}), 400

    raw = file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")

    gamelist = check_latest_builds.parse_gamelist_text(text)
    if not gamelist:
        return jsonify({"error": "couldn't find any game entries in that file - check the format"}), 400

    (BASE_DIR / "gamelist.txt").write_text(text, encoding="utf-8")

    db = get_db()
    updated, skipped, total = check_latest_builds.run_check(db, gamelist)
    db.commit()

    return jsonify({
        "parsed_entries": len(gamelist),
        "updated": updated,
        "skipped": skipped,
        "total": total,
    })


@app.route("/api/export/gamelist")
def export_gamelist():
    """Plain-text export of every game in the library with its build/version
    id, one per line, in the same "<title padded> (<id>)" shape as the
    gamelist.txt files this app already reads (see check_latest_builds.py) -
    so it can also be fed back in elsewhere, not just read by a person. Only
    GOG games actually have a build id populated right now; every other
    platform gets "-" like an unbuilt entry in a real gamelist.txt."""
    db = get_db()
    rows = db.execute(
        "SELECT title, platform, gog_id FROM games ORDER BY platform, title COLLATE NOCASE"
    ).fetchall()

    lines = []
    current_platform = None
    for r in rows:
        if r["platform"] != current_platform:
            current_platform = r["platform"]
            if lines:
                lines.append("")
            lines.append(f"=== {PLATFORM_EXPORT_LABEL.get(current_platform, current_platform.upper())} ===")
            lines.append("")
        value = r["gog_id"] if r["gog_id"] else "-"
        lines.append(f"{r['title']:<62}{value}")

    body = "\n".join(lines) + "\n"
    filename = f"game_library_export_{datetime.now().strftime('%Y-%m-%d')}.txt"
    return Response(
        body,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/api/dashboard")
def dashboard_stats():
    """Cross-shelf overview: overall + per-platform totals, install/backlog
    breakdown, and a few highlight lists.

    "Folder linked" just means the raw installer/backup files are known to
    sit somewhere on disk - most of this library is GOG/Steam offline
    installers, not actually-installed games, so that count alone doesn't
    mean "installed". "Playable" (exe_path set) is the real installed
    signal for GOG/Steam, since that's only set once a game has actually
    been extracted/installed and pointed at its launch executable. PS3/PS4
    have no such concept (no launchable executable through this app), so
    folder-linked is the only meaningful metric there."""
    db = get_db()

    def platform_totals(where="", params=()):
        total = db.execute(f"SELECT COUNT(*) c FROM games {where}", params).fetchone()["c"]
        size = db.execute(f"SELECT COALESCE(SUM(size_bytes),0) s FROM games {where}", params).fetchone()["s"]
        by_status = {
            r["status"]: r["c"]
            for r in db.execute(f"SELECT status, COUNT(*) c FROM games {where} GROUP BY status", params)
        }
        connector = " AND" if where else " WHERE"
        linked = db.execute(
            f"SELECT COUNT(*) c FROM games {where}{connector} folder_path IS NOT NULL AND folder_path != ''",
            params,
        ).fetchone()["c"]
        playable = db.execute(
            f"SELECT COUNT(*) c FROM games {where}{connector} exe_path IS NOT NULL AND exe_path != ''",
            params,
        ).fetchone()["c"]
        return {
            "total": total,
            "size_bytes": size,
            "size_human": human_size(size),
            "by_status": by_status,
            "folders_linked": linked,
            "missing": total - linked,
            "playable": playable,
        }

    overall = platform_totals()
    platforms = {p: platform_totals("WHERE platform = ?", (p,)) for p in ("gog", "steam", "ps3", "ps4")}

    ids_verified = db.execute(
        "SELECT COUNT(*) c FROM games WHERE gog_catalog_id IS NOT NULL AND gog_catalog_id != ''"
    ).fetchone()["c"]
    playable = db.execute(
        "SELECT COUNT(*) c FROM games WHERE exe_path IS NOT NULL AND exe_path != ''"
    ).fetchone()["c"]
    rated = db.execute("SELECT COUNT(*) c, AVG(rating) a FROM games WHERE rating IS NOT NULL").fetchone()
    recent_count = db.execute(
        "SELECT COUNT(*) c FROM games WHERE added_at >= datetime('now', '-7 days')"
    ).fetchone()["c"]
    trash_count = db.execute("SELECT COUNT(*) c FROM deleted_games").fetchone()["c"]

    top_rated = db.execute(
        "SELECT id, title, platform, rating FROM games WHERE rating IS NOT NULL "
        "ORDER BY rating DESC, title COLLATE NOCASE ASC LIMIT 5"
    ).fetchall()
    largest = db.execute(
        "SELECT id, title, platform, size_bytes FROM games ORDER BY size_bytes DESC LIMIT 5"
    ).fetchall()
    recent = db.execute(
        "SELECT id, title, platform, added_at FROM games ORDER BY added_at DESC LIMIT 5"
    ).fetchall()

    return jsonify({
        "overall": overall,
        "platforms": platforms,
        "ids_verified": ids_verified,
        "playable": playable,
        "rated_count": rated["c"],
        "avg_rating": round(rated["a"], 1) if rated["a"] is not None else None,
        "recently_added_7d": recent_count,
        "trash_count": trash_count,
        "top_rated": [dict(r) for r in top_rated],
        "largest": [{**dict(r), "size_human": human_size(r["size_bytes"])} for r in largest],
        "recent": [dict(r) for r in recent],
    })


SIZE_BUCKETS_GB = [1, 5, 15, 30, 60, 100]


def size_bucket_label(gb, prev_gb):
    if prev_gb is None:
        return f"< {gb}G"
    if gb is None:
        return f"{prev_gb}G+"
    return f"{prev_gb}-{gb}G"


@app.route("/api/dashboard/insights")
def dashboard_insights():
    """A few more comparison views for the dashboard: how library size and
    ratings are actually distributed (not just totals/averages), and
    collecting activity over time. All cross-shelf (platform=all)."""
    db = get_db()

    all_sizes = [r["size_bytes"] or 0 for r in db.execute("SELECT size_bytes FROM games")]
    thresholds = [None] + [gb * 1024**3 for gb in SIZE_BUCKETS_GB] + [None]
    size_histogram = []
    for i in range(len(SIZE_BUCKETS_GB) + 1):
        lo = thresholds[i]
        hi = thresholds[i + 1]
        count = sum(1 for s in all_sizes if (lo is None or s >= lo) and (hi is None or s < hi))
        prev_gb = SIZE_BUCKETS_GB[i - 1] if i > 0 else None
        gb = SIZE_BUCKETS_GB[i] if i < len(SIZE_BUCKETS_GB) else None
        size_histogram.append({"label": size_bucket_label(gb, prev_gb), "count": count})

    rating_rows = db.execute(
        "SELECT rating, COUNT(*) c FROM games WHERE rating IS NOT NULL GROUP BY rating"
    ).fetchall()
    stars_count = {i: 0 for i in range(1, 6)}
    for r in rating_rows:
        star = max(1, min(5, round(r["rating"] / 2)))
        stars_count[star] += r["c"]
    rating_histogram = [{"label": f"{s}★", "count": stars_count[s]} for s in range(1, 6)]

    months = db.execute(
        "SELECT strftime('%Y-%m', added_at) m, COUNT(*) c FROM games "
        "WHERE added_at >= datetime('now', '-11 months', 'start of month') "
        "GROUP BY m ORDER BY m"
    ).fetchall()
    month_counts = {r["m"]: r["c"] for r in months}
    added_by_month = []
    today = datetime.now()
    for i in range(11, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        key = f"{year:04d}-{month:02d}"
        added_by_month.append({"label": key, "count": month_counts.get(key, 0)})

    storage_by_platform = [
        {"platform": p, "size_bytes": r["s"], "size_human": human_size(r["s"])}
        for p in ("gog", "steam", "ps3", "ps4")
        for r in [db.execute("SELECT COALESCE(SUM(size_bytes),0) s FROM games WHERE platform=?", (p,)).fetchone()]
    ]

    return jsonify({
        "size_histogram": size_histogram,
        "rating_histogram": rating_histogram,
        "added_by_month": added_by_month,
        "storage_by_platform": storage_by_platform,
    })


@app.route("/api/monitor/stats")
def monitor_stats():
    """Advanced dashboard statistics: library overview, platform breakdown,
    status distribution, storage by platform, ratings, activity."""
    db = get_db()

    # Overall stats
    total_games = db.execute("SELECT COUNT(*) c FROM games").fetchone()["c"]
    total_size = db.execute("SELECT COALESCE(SUM(size_bytes), 0) s FROM games").fetchone()["s"]

    # By status
    by_status = {}
    for status in ['backlog', 'playing', 'completed', 'abandoned']:
        count = db.execute("SELECT COUNT(*) c FROM games WHERE status = ?", (status,)).fetchone()["c"]
        by_status[status] = count

    # By platform
    by_platform = {}
    for platform in ['gog', 'steam', 'ps3', 'ps4']:
        data = db.execute("""
            SELECT COUNT(*) count, COALESCE(SUM(size_bytes), 0) size
            FROM games WHERE platform = ?
        """, (platform,)).fetchone()
        by_platform[platform] = {"count": data["count"], "size": data["size"]}

    # Top rated games
    top_rated = db.execute("""
        SELECT id, title, platform, rating
        FROM games WHERE rating IS NOT NULL
        ORDER BY rating DESC LIMIT 5
    """).fetchall()

    # Largest games
    largest = db.execute("""
        SELECT id, title, platform, size_bytes
        FROM games ORDER BY size_bytes DESC LIMIT 5
    """).fetchall()

    # Recently added
    recent = db.execute("""
        SELECT id, title, platform, added_at
        FROM games ORDER BY added_at DESC LIMIT 5
    """).fetchall()

    # Rating distribution
    rating_dist = db.execute("""
        SELECT ROUND(rating/2) stars, COUNT(*) count
        FROM games WHERE rating IS NOT NULL
        GROUP BY ROUND(rating/2)
        ORDER BY stars
    """).fetchall()

    # Games added by month (last 12)
    by_month = db.execute("""
        SELECT strftime('%Y-%m', added_at) month, COUNT(*) count
        FROM games
        WHERE added_at >= datetime('now', '-12 months')
        GROUP BY month ORDER BY month
    """).fetchall()

    # Folder status
    with_folder = db.execute("SELECT COUNT(*) c FROM games WHERE folder_path IS NOT NULL").fetchone()["c"]

    def human_size(bytes_val):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f}PB"

    return jsonify({
        "total_games": total_games,
        "total_size": total_size,
        "total_size_human": human_size(total_size),
        "by_status": by_status,
        "by_platform": by_platform,
        "folders_linked": with_folder,
        "top_rated": [dict(r) for r in top_rated],
        "largest": [{"id": r["id"], "title": r["title"], "platform": r["platform"],
                     "size": r["size_bytes"], "size_human": human_size(r["size_bytes"])} for r in largest],
        "recent": [dict(r) for r in recent],
        "rating_distribution": [dict(r) for r in rating_dist],
        "added_by_month": [dict(r) for r in by_month],
    })


@app.route("/api/scan/missing-folders")
def scan_missing_folders():
    """Scan all game folders and report which ones are missing from disk.
    Returns detailed info about games with missing installers/backups."""
    db = get_db()

    games = db.execute("""
        SELECT id, title, platform, folder_path, size_bytes, status
        FROM games
        ORDER BY title
    """).fetchall()

    missing = []
    found = []

    for game in games:
        if not game["folder_path"]:
            missing.append({
                "id": game["id"],
                "title": game["title"],
                "platform": game["platform"],
                "reason": "No folder path set",
                "size_bytes": game["size_bytes"],
                "status": game["status"],
            })
            continue

        path = Path(game["folder_path"])
        if not path.exists():
            missing.append({
                "id": game["id"],
                "title": game["title"],
                "platform": game["platform"],
                "folder_path": game["folder_path"],
                "reason": "Folder not found on disk",
                "size_bytes": game["size_bytes"],
                "status": game["status"],
            })
        else:
            found.append({
                "id": game["id"],
                "title": game["title"],
                "platform": game["platform"],
            })

    summary = {
        "total_games": len(games),
        "found_count": len(found),
        "missing_count": len(missing),
        "missing_percentage": round(100 * len(missing) / len(games), 1) if games else 0,
        "missing_games": missing,
    }

    return jsonify(summary)


@app.route("/api/dashboard/lists")
def dashboard_lists():
    """Top rated, largest installs, and recently added games."""
    db = get_db()

    # Top rated (minimum 1 rating to avoid clutter)
    top_rated = [
        {
            "title": r["title"],
            "rating": r["rating"],
            "platform": r["platform"],
        }
        for r in db.execute(
            "SELECT title, rating, platform FROM games WHERE rating IS NOT NULL "
            "ORDER BY rating DESC, title LIMIT 5"
        ).fetchall()
    ]

    # Largest installs
    largest = [
        {
            "title": r["title"],
            "size_human": human_size(r["size_bytes"]),
            "platform": r["platform"],
        }
        for r in db.execute(
            "SELECT title, size_bytes, platform FROM games WHERE size_bytes > 0 "
            "ORDER BY size_bytes DESC LIMIT 5"
        ).fetchall()
    ]

    # Recently added
    recently_added = [
        {
            "title": r["title"],
            "platform": r["platform"],
            "added_at": r["added_at"][:10] if r["added_at"] else "Unknown",
        }
        for r in db.execute(
            "SELECT title, platform, added_at FROM games "
            "ORDER BY added_at DESC LIMIT 5"
        ).fetchall()
    ]

    return jsonify({
        "top_rated": top_rated,
        "largest": largest,
        "recently_added": recently_added,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
