#!/usr/bin/env python3
"""
Create (if needed) games.db and load one or more parsed games.json files into it.
Safe to re-run: existing games are matched by gog_id (or title as fallback) and
only their size/raw_paths get refreshed - your status/rating/notes/tags are preserved.

Usage:
    python3 load_db.py games.json [more.json ...] --db games.db
"""
import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def upsert_game(conn, entry, platform="gog"):
    gog_id = entry.get("gog_id")
    title = entry["title"]
    size_bytes = entry["size_bytes"]
    raw_paths = json.dumps(entry.get("raw_paths", []), ensure_ascii=False)

    row = None
    if gog_id:
        row = conn.execute("SELECT id FROM games WHERE gog_id = ?", (gog_id,)).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT id FROM games WHERE gog_id IS NULL AND title = ? AND platform = ?", (title, platform)
        ).fetchone()

    if row:
        conn.execute(
            """UPDATE games SET title = ?, size_bytes = ?, raw_paths = ?,
               gog_id = COALESCE(gog_id, ?), updated_at = datetime('now')
               WHERE id = ?""",
            (title, size_bytes, raw_paths, gog_id, row["id"]),
        )
        return row["id"], False
    else:
        cur = conn.execute(
            """INSERT INTO games (gog_id, platform, title, size_bytes, raw_paths)
               VALUES (?, ?, ?, ?, ?)""",
            (gog_id, platform, title, size_bytes, raw_paths),
        )
        return cur.lastrowid, True


def upsert_bonus(conn, kind, entry):
    title = entry["title"]
    size_bytes = entry["size_bytes"]
    raw_paths = json.dumps(entry.get("raw_paths", []), ensure_ascii=False)

    row = conn.execute(
        "SELECT id FROM bonus_content WHERE kind = ? AND title = ?", (kind, title)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE bonus_content SET size_bytes = ?, raw_paths = ? WHERE id = ?",
            (size_bytes, raw_paths, row["id"]),
        )
    else:
        # best-effort link to a matching game by title
        game_row = conn.execute("SELECT id FROM games WHERE title = ?", (title,)).fetchone()
        conn.execute(
            "INSERT INTO bonus_content (kind, title, size_bytes, raw_paths, game_id) VALUES (?, ?, ?, ?, ?)",
            (kind, title, size_bytes, raw_paths, game_row["id"] if game_row else None),
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path, help="one or more games.json files from parse_gog.py")
    ap.add_argument("--db", type=Path, default=Path("games.db"))
    ap.add_argument("--platform", default="gog", help="platform tag for every game in these files (gog, steam, ...)")
    args = ap.parse_args()

    conn = get_conn(args.db)
    new_count = 0
    updated_count = 0

    for path in args.inputs:
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("games", []):
            _, is_new = upsert_game(conn, entry, platform=args.platform)
            new_count += is_new
            updated_count += not is_new
        for entry in data.get("extras", []):
            upsert_bonus(conn, "extras", entry)
        for entry in data.get("patches", []):
            upsert_bonus(conn, "patch", entry)

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    print(f"New games added: {new_count}")
    print(f"Existing games refreshed: {updated_count}")
    print(f"Total games in {args.db}: {total}")
    conn.close()


if __name__ == "__main__":
    main()
