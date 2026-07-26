#!/usr/bin/env python3
"""
Backfill games.case_color for games whose cover art was downloaded before
the color-tinted case tile existed (see app.py's dominant_color() /
save_cover(), which now do this automatically for every new/changed cover).

Resumable: only touches rows with cover_url set and case_color still NULL,
so re-running after an interrupted pass just picks up where it left off.

Run:
    python assign_case_colors.py [--db games.db]
"""
import argparse
import sqlite3
from pathlib import Path

from app import BASE_DIR, dominant_color


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(BASE_DIR / "games.db"))
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, cover_url FROM games WHERE cover_url IS NOT NULL AND cover_url != '' "
        "AND (case_color IS NULL OR case_color = '')"
    ).fetchall()

    updated = skipped = 0
    for r in rows:
        image_path = BASE_DIR / "static" / Path(r["cover_url"]).relative_to("/")
        if not image_path.exists():
            skipped += 1
            continue
        color = dominant_color(image_path)
        if color is None:
            skipped += 1
            continue
        db.execute("UPDATE games SET case_color = ? WHERE id = ?", (color, r["id"]))
        updated += 1

    db.commit()
    print(f"Done. {updated} games colored, {skipped} skipped (no file / unreadable), {len(rows)} total checked.")


if __name__ == "__main__":
    main()
