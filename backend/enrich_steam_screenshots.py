#!/usr/bin/env python3
"""
Backfill screenshot images for Steam games from Steam Store API.
Screenshots are downloaded and resized locally into static/screenshots/<game_id>/
and stored in the game_screenshots table.

Resumable and best-effort: only downloads when a game doesn't already have
screenshots, unless --force is passed.

Run:
    python3 enrich_steam_screenshots.py [--db games.db] [--force] [--limit N]
"""
import argparse
import io
import sqlite3
import sys
import time
from pathlib import Path

import steamgriddb

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

BASE_DIR = Path(__file__).parent


def save_screenshot(data, dest_dir, n):
    """Store Steam's original screenshot bytes without resizing or recompression."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{n}.jpg"
    dest.write_bytes(data)
    return dest


def enrich_steam_screenshots(db_path, force=False, limit=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if force:
        games = cur.execute(
            "SELECT id, title, steam_app_id FROM games WHERE platform = 'steam' ORDER BY title"
        ).fetchall()
        print(f"Fetching screenshots for all {len(games)} Steam games (--force)")
    else:
        games = cur.execute(
            """SELECT g.id, g.title, g.steam_app_id FROM games g
            LEFT JOIN game_screenshots s ON g.id = s.game_id
            WHERE g.platform = 'steam' AND s.game_id IS NULL
            GROUP BY g.id ORDER BY g.title"""
        ).fetchall()
        print(f"Found {len(games)} Steam games without screenshots")

    if limit:
        games = games[:limit]

    print(f"Processing {len(games)} games...\n")

    success = 0
    failed = 0
    missing_appid = 0

    for i, game in enumerate(games, 1):
        game_id = game["id"]
        title = game["title"]
        steam_app_id = game["steam_app_id"]

        if not steam_app_id:
            match = steamgriddb.find_steam_appid(title)
            if match is None:
                missing_appid += 1
                if i % 50 == 0:
                    print(f"[{i}/{len(games)}] {title[:40]:40} [NO APP ID]")
                continue
            steam_app_id = match["id"]
            cur.execute("UPDATE games SET steam_app_id = ? WHERE id = ?", (steam_app_id, game_id))
            conn.commit()

        screenshots = steamgriddb.fetch_steam_screenshots(steam_app_id, limit=6)
        if not screenshots:
            failed += 1
            if i % 50 == 0:
                print(f"[{i}/{len(games)}] {title[:40]:40} [NO SCREENSHOTS]")
            continue

        try:
            dest_dir = BASE_DIR / "static" / "screenshots" / str(game_id)
            for idx, (data, ext) in enumerate(screenshots, 1):
                dest = save_screenshot(data, dest_dir, idx)
                path = dest.relative_to(BASE_DIR / "static").as_posix()
                cur.execute(
                    "INSERT INTO game_screenshots (game_id, path, position) VALUES (?, ?, ?)",
                    (game_id, "/" + path, idx - 1),
                )
            conn.commit()
            success += 1
            if i % 50 == 0:
                print(f"[{i}/{len(games)}] {title[:40]:40} [{len(screenshots)} screenshots]")
        except Exception as e:
            failed += 1
            print(f"ERROR saving {title}: {e}")

        if i % 10 == 0:
            time.sleep(0.1)

    conn.close()

    print(f"\n{'='*60}")
    print(f"Done! {success} games enriched, {failed} failed, {missing_appid} missing app IDs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="games.db", help="Database path")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if screenshots exist")
    parser.add_argument("--limit", type=int, help="Limit to N games")
    args = parser.parse_args()

    enrich_steam_screenshots(args.db, force=args.force, limit=args.limit)
