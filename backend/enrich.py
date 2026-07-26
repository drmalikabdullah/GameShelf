#!/usr/bin/env python3
"""
Fetch cover art + basic metadata for every game that has a gog_id but no
cover_url yet, using GOG's public (unauthenticated) product API:

    https://api.gog.com/products/{id}?expand=description

Run this on YOUR machine (it needs real internet access - it won't work
from a sandboxed environment). Safe to re-run: it only fills in games that
are still missing a cover_url, so re-running costs nothing but a bit of time.

Usage:
    python3 enrich.py --db games.db
    python3 enrich.py --db games.db --force   # re-fetch everything
"""
import argparse
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import json

API_URL = "https://api.gog.com/products/{id}?expand=description"


def fetch_product(gog_id: str):
    url = API_URL.format(id=gog_id)
    req = urllib.request.Request(url, headers={"User-Agent": "gog-catalogue/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_fields(data):
    images = data.get("images", {})
    cover = images.get("logo2x") or images.get("background") or images.get("icon")
    if cover and cover.startswith("//"):
        cover = "https:" + cover
    genres = ""
    # GOG's API doesn't always include genres in this endpoint; guard for absence
    if "genres" in data and isinstance(data["genres"], list):
        genres = ", ".join(g.get("name", "") for g in data["genres"] if isinstance(g, dict))
    description = None
    desc_obj = data.get("description")
    if isinstance(desc_obj, dict):
        description = desc_obj.get("lead") or desc_obj.get("full")
    release_date = data.get("release_date")
    return {
        "cover_url": cover,
        "genres": genres or None,
        "description": description,
        "release_date": release_date,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="games.db")
    ap.add_argument("--force", action="store_true", help="re-fetch even if cover_url already set")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds to wait between requests")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    if args.force:
        rows = conn.execute("SELECT id, gog_id, title FROM games WHERE gog_id IS NOT NULL").fetchall()
    else:
        rows = conn.execute(
            "SELECT id, gog_id, title FROM games WHERE gog_id IS NOT NULL AND cover_url IS NULL"
        ).fetchall()

    print(f"Enriching {len(rows)} games...")
    ok, failed = 0, 0
    for row in rows:
        try:
            data = fetch_product(row["gog_id"])
            fields = extract_fields(data)
            conn.execute(
                """UPDATE games SET cover_url = ?, genres = COALESCE(?, genres),
                   description = COALESCE(?, description),
                   release_date = COALESCE(?, release_date)
                   WHERE id = ?""",
                (fields["cover_url"], fields["genres"], fields["description"],
                 fields["release_date"], row["id"]),
            )
            conn.commit()
            ok += 1
            print(f"  ✓ {row['title']}")
        except urllib.error.HTTPError as e:
            failed += 1
            print(f"  ✗ {row['title']} (HTTP {e.code})", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"  ✗ {row['title']} ({e})", file=sys.stderr)
        time.sleep(args.delay)

    print(f"\nDone. {ok} enriched, {failed} failed.")


if __name__ == "__main__":
    main()
