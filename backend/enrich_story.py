#!/usr/bin/env python3
"""
Backfill story text, genre tags, developer, and screenshot images for GOG
games, straight from GOG's own catalog (gog_catalog_id must already be
verified - see verify_gog_id in app.py). Screenshots are downloaded and
resized locally into static/screenshots/<game_id>/ and the rest is stored
directly on the games row, so the app never has to hit the network to show
any of it.

Resumable and best-effort, same philosophy as enrich.py/enrich_steamgriddb.py:
the text fields (story/genres/developer) are cheap - they come from the same
single catalog request - so those are refreshed for every game each run.
Screenshots are the expensive part (up to 6 image downloads), so those are
only (re-)downloaded when a game doesn't already have any, unless --force is
passed. A game with nothing findable is just left alone (not an error).

Run:
    python3 enrich_story.py [--db games.db] [--force] [--limit N]
"""
import argparse
import io
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import gog_catalog

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

BASE_DIR = Path(__file__).parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def save_screenshot(data, dest_dir, n):
    """Store GOG's original screenshot bytes without resizing or recompression."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{n}.jpg"
    dest.write_bytes(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(BASE_DIR / "games.db"))
    ap.add_argument("--force", action="store_true", help="re-download screenshots even for games that already have them")
    ap.add_argument("--limit", type=int, default=None, help="stop after N games (for a quick test run)")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT id, title, gog_catalog_id FROM games "
        "WHERE platform='gog' AND gog_catalog_id IS NOT NULL AND gog_catalog_id != '' "
        "ORDER BY id"
    ).fetchall()
    if args.limit:
        rows = rows[:args.limit]

    total = len(rows)
    updated = nothing_found = errors = 0
    for i, row in enumerate(rows, 1):
        gid, title, cid = row["id"], row["title"], row["gog_catalog_id"]
        has_shots = db.execute(
            "SELECT COUNT(*) c FROM game_screenshots WHERE game_id=?", (gid,)
        ).fetchone()["c"]

        print(f"[{i}/{total}] {title} ...", end=" ", flush=True)
        try:
            desc, shot_urls, genres, developer = gog_catalog.fetch_story_and_screenshots(cid)
        except Exception as e:  # keep the backfill running past a single bad game
            errors += 1
            print(f"error ({e}), skipping")
            continue

        if desc:
            db.execute("UPDATE games SET description = ? WHERE id = ?", (desc, gid))
        if genres:
            db.execute("UPDATE games SET genres = ? WHERE id = ?", (genres, gid))
        if developer:
            db.execute("UPDATE games SET developer = ? WHERE id = ?", (developer, gid))

        saved = has_shots
        shots_note = f"{has_shots} screenshots (kept)"
        if shot_urls and (args.force or not has_shots):
            dest_dir = BASE_DIR / "static" / "screenshots" / str(gid)
            db.execute("DELETE FROM game_screenshots WHERE game_id = ?", (gid,))
            saved = 0
            for n, url in enumerate(shot_urls, 1):
                data = download(url)
                if data is None:
                    continue
                save_screenshot(data, dest_dir, n)
                db.execute(
                    "INSERT INTO game_screenshots (game_id, path, position) VALUES (?, ?, ?)",
                    (gid, f"/screenshots/{gid}/{n}.jpg", n),
                )
                saved += 1
            shots_note = f"{saved} screenshots (downloaded)"
        db.commit()

        if desc or genres or developer or saved:
            updated += 1
            print(f"ok (story={'y' if desc else 'n'}, genres={'y' if genres else 'n'}, dev={'y' if developer else 'n'}, {shots_note})")
        else:
            nothing_found += 1
            print("nothing found")

        time.sleep(0.3)

    print(f"\nDone. {updated} updated, {nothing_found} nothing found, {errors} errors, {total} total.")
    db.close()


if __name__ == "__main__":
    main()
