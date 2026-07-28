#!/usr/bin/env python3
"""Backfill Steam stories and PC requirements into the games table.

Resumable by default: only Steam games missing either field are fetched.

Run:
    python enrich_steam_descriptions.py [--db games.db] [--force] [--limit N]
"""
import argparse
import sqlite3
import time
from pathlib import Path

import steamgriddb


BASE_DIR = Path(__file__).parent


def enrich_steam_descriptions(db_path, force=False, limit=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    columns = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    if "system_requirements" not in columns:
        conn.execute("ALTER TABLE games ADD COLUMN system_requirements TEXT")
        conn.commit()
    query = """
        SELECT id, title, steam_app_id, description, system_requirements
        FROM games
        WHERE platform = 'steam'
    """
    if not force:
        query += """ AND (
            description IS NULL OR trim(description) = ''
            OR system_requirements IS NULL OR trim(system_requirements) = ''
        )"""
    query += " ORDER BY title"
    games = conn.execute(query).fetchall()
    if limit:
        games = games[:limit]

    descriptions_saved = requirements_saved = failed = missing_appid = 0
    print(f"Processing {len(games)} Steam games...")

    for index, game in enumerate(games, 1):
        game_id = game["id"]
        appid = game["steam_app_id"]
        if not appid:
            match = steamgriddb.find_steam_appid(game["title"])
            if match is None:
                missing_appid += 1
                continue
            appid = match["id"]
            conn.execute(
                "UPDATE games SET steam_app_id = ? WHERE id = ?",
                (appid, game_id),
            )

        description, requirements = steamgriddb.fetch_steam_description_and_requirements(appid)
        if description or requirements:
            conn.execute(
                """UPDATE games
                   SET description = COALESCE(?, description),
                       system_requirements = COALESCE(?, system_requirements),
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (description, requirements, game_id),
            )
            descriptions_saved += bool(description and not game["description"])
            requirements_saved += bool(requirements and not game["system_requirements"])
        else:
            failed += 1

        if index % 10 == 0:
            conn.commit()
            time.sleep(0.25)

    conn.commit()
    conn.close()
    print(
        f"Done: {descriptions_saved} descriptions saved, "
        f"{requirements_saved} requirements saved, "
        f"{failed} unavailable, {missing_appid} missing Steam app IDs"
    )
    return descriptions_saved, requirements_saved, failed, missing_appid


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=BASE_DIR / "games.db")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    enrich_steam_descriptions(args.db, force=args.force, limit=args.limit)
