#!/usr/bin/env python3
"""Backfill GOG minimum/recommended system requirements.

Resumable by default: only GOG games with an empty requirements field are
fetched from their public GOG store pages.

Run:
    python enrich_gog_requirements.py [--db games.db] [--force] [--limit N]
"""
import argparse
import sqlite3
import time
from pathlib import Path

import gog_catalog


BASE_DIR = Path(__file__).parent


def enrich_gog_requirements(db_path, force=False, limit=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    columns = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    if "system_requirements" not in columns:
        conn.execute("ALTER TABLE games ADD COLUMN system_requirements TEXT")
        conn.commit()

    query = """
        SELECT id, title, gog_catalog_id
        FROM games
        WHERE platform = 'gog'
          AND gog_catalog_id IS NOT NULL
          AND trim(gog_catalog_id) != ''
    """
    if not force:
        query += """
          AND (
            system_requirements IS NULL
            OR trim(system_requirements) = ''
          )
        """
    query += " ORDER BY title"
    games = conn.execute(query).fetchall()
    if limit:
        games = games[:limit]

    saved = unavailable = 0
    print(f"Processing {len(games)} GOG games...")
    for index, game in enumerate(games, 1):
        requirements = gog_catalog.fetch_system_requirements(
            game["gog_catalog_id"]
        )
        if requirements:
            conn.execute(
                """UPDATE games
                   SET system_requirements = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (requirements, game["id"]),
            )
            saved += 1
        else:
            unavailable += 1

        if index % 10 == 0:
            conn.commit()
            time.sleep(0.25)

    conn.commit()
    conn.close()
    print(f"Done: {saved} requirements saved, {unavailable} unavailable")
    return saved, unavailable


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=BASE_DIR / "games.db")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    enrich_gog_requirements(args.db, force=args.force, limit=args.limit)
