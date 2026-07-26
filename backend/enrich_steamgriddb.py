#!/usr/bin/env python3
"""
Bulk-fetch cover art (grids) from SteamGridDB for games in games.db.

Uses the official SteamGridDB API (https://www.steamgriddb.com/api/v2) -
requires a free API key from https://www.steamgriddb.com/profile/preferences/api
(matching logic lives in steamgriddb.py, shared with app.py's live edit/add-game
cover fetching).

Only fills games still missing a cover_url, so it's cheap to re-run after
fixing a mismatch (clear that game's cover_url in the UI/DB to force a redo).

Usage:
    python3 enrich_steamgriddb.py [--api-key YOUR_KEY] [--db games.db] [--force]
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import steamgriddb

BASE_DIR = Path(__file__).parent
COVERS_DIR = BASE_DIR / "static" / "covers"
HEROES_DIR = BASE_DIR / "static" / "heroes"
OVERRIDES_PATH = BASE_DIR / "cover_overrides.json"


def load_overrides():
    """Manually-pinned games whose title alone is ambiguous even to Steam
    search (e.g. "God of War" collides with... nothing on Steam, but games
    delisted from Steam entirely, like the Telltale Guardians of the Galaxy
    series, would otherwise silently fall through to the wrong SteamGridDB
    match on every re-run). Keyed by exact title."""
    if OVERRIDES_PATH.exists():
        return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return {}


def fetch_for(title, overrides, api_key):
    override = overrides.get(title)
    if override:
        if "steam_appid" in override:
            return steamgriddb.fetch_steam_official(override["steam_appid"])
        if "sgdb_id" in override:
            return steamgriddb.fetch_cover_by_id(override["sgdb_id"], api_key)
    return steamgriddb.fetch_cover(title, api_key)


def fetch_hero_for(title, overrides, api_key):
    override = overrides.get(title)
    if override:
        if "steam_appid" in override:
            data = steamgriddb.fetch_steam_hero(override["steam_appid"])
            return (data, "jpg") if data is not None else (None, None)
        if "sgdb_id" in override:
            return steamgriddb.fetch_hero_by_id(override["sgdb_id"], api_key)
    return steamgriddb.fetch_hero(title, api_key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=None, help="defaults to STEAMGRIDDB_API_KEY env var or steamgriddb_key.txt")
    ap.add_argument("--db", type=Path, default=BASE_DIR / "games.db")
    ap.add_argument("--force", action="store_true", help="re-fetch covers even if already set")
    args = ap.parse_args()

    api_key = args.api_key or steamgriddb.get_api_key()
    if not api_key:
        sys.exit("No API key: pass --api-key, set STEAMGRIDDB_API_KEY, or create steamgriddb_key.txt")

    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    HEROES_DIR.mkdir(parents=True, exist_ok=True)
    overrides = load_overrides()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    if args.force:
        rows = conn.execute("SELECT id, title FROM games ORDER BY title").fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title FROM games WHERE cover_url IS NULL OR cover_url = '' ORDER BY title"
        ).fetchall()

    print(f"{len(rows)} games to enrich (covers)", file=sys.stderr)

    filled = 0
    unmatched = []

    for row in rows:
        game_id, title = row["id"], row["title"]
        data, ext = fetch_for(title, overrides, api_key)
        if data is None:
            unmatched.append(title)
            time.sleep(0.2)
            continue

        old_cover = conn.execute("SELECT cover_url FROM games WHERE id = ?", (game_id,)).fetchone()[0]
        dest = COVERS_DIR / f"{game_id}.{ext}"
        dest.write_bytes(data)
        if old_cover and Path(old_cover).name != dest.name:
            (BASE_DIR / "static" / Path(old_cover).relative_to("/")).unlink(missing_ok=True)

        conn.execute(
            "UPDATE games SET cover_url = ?, updated_at = datetime('now') WHERE id = ?",
            (f"/covers/{game_id}.{ext}", game_id),
        )
        conn.commit()
        filled += 1
        time.sleep(0.25)

    print(f"\nCovers downloaded: {filled}", file=sys.stderr)
    print(f"Unmatched/failed: {len(unmatched)}", file=sys.stderr)
    if unmatched:
        print("  " + "\n  ".join(unmatched), file=sys.stderr)

    if args.force:
        hero_rows = conn.execute("SELECT id, title FROM games ORDER BY title").fetchall()
    else:
        hero_rows = conn.execute(
            "SELECT id, title FROM games WHERE hero_url IS NULL OR hero_url = '' ORDER BY title"
        ).fetchall()

    print(f"\n{len(hero_rows)} games to enrich (heroes)", file=sys.stderr)

    hero_filled = 0
    hero_unmatched = []

    for row in hero_rows:
        game_id, title = row["id"], row["title"]
        data, ext = fetch_hero_for(title, overrides, api_key)
        if data is None:
            hero_unmatched.append(title)
            time.sleep(0.2)
            continue

        old_hero = conn.execute("SELECT hero_url FROM games WHERE id = ?", (game_id,)).fetchone()[0]
        dest = HEROES_DIR / f"{game_id}.{ext}"
        dest.write_bytes(data)
        if old_hero and Path(old_hero).name != dest.name:
            (BASE_DIR / "static" / Path(old_hero).relative_to("/")).unlink(missing_ok=True)

        conn.execute(
            "UPDATE games SET hero_url = ?, updated_at = datetime('now') WHERE id = ?",
            (f"/heroes/{game_id}.{ext}", game_id),
        )
        conn.commit()
        hero_filled += 1
        time.sleep(0.25)

    conn.close()

    print(f"\nHeroes downloaded: {hero_filled}", file=sys.stderr)
    print(f"Unmatched/failed: {len(hero_unmatched)}", file=sys.stderr)
    if hero_unmatched:
        print("  " + "\n  ".join(hero_unmatched), file=sys.stderr)


if __name__ == "__main__":
    main()
