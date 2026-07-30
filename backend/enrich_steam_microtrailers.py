#!/usr/bin/env python3
"""Download Steam microtrailers for offline playback in GameShelf.

Only games with a Steam app ID are processed by default. Pass
``--resolve-missing`` to try matching titles that do not have one yet.
Downloaded videos live in ``static/trailers/<game_id>.webm`` and the database
stores only that local URL, so playback never depends on the network.

Run from ``backend``::

    python enrich_steam_microtrailers.py
    python enrich_steam_microtrailers.py --resolve-missing
    python enrich_steam_microtrailers.py --force --limit 20
"""

import argparse
import json
import sqlite3
import time
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import steamgriddb


BASE_DIR = Path(__file__).parent
TRAILERS_DIR = BASE_DIR / "static" / "trailers"
USER_AGENT = "GameShelf/1.0 (+local personal game library)"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_TRAILER_BYTES = 25 * 1024 * 1024


def request_bytes(url, timeout=30):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        data = response.read(MAX_TRAILER_BYTES + 1)
    if len(data) > MAX_TRAILER_BYTES:
        raise ValueError("microtrailer is larger than 25 MB")
    return data, content_type


def fetch_store_data(app_id):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english"
    data, _ = request_bytes(url)
    payload = json.loads(data.decode("utf-8"))
    result = payload.get(str(app_id), {})
    if not result.get("success"):
        return None
    return result.get("data") or {}


def microtrailer_candidates(movie):
    """Derive Steam's small WebM beside the public HLS trailer playlist."""
    playlist = movie.get("hls_h264") or ""
    if not playlist:
        return []
    parsed = urlsplit(playlist)
    folder = parsed.path.rsplit("/", 1)[0]
    path = f"{folder}/microtrailer.webm"
    hosts = [parsed.netloc]
    if parsed.netloc == "video.akamai.steamstatic.com":
        hosts.append("video.fastly.steamstatic.com")
    elif parsed.netloc == "video.fastly.steamstatic.com":
        hosts.append("video.akamai.steamstatic.com")
    return [urlunsplit((parsed.scheme, host, path, parsed.query, "")) for host in hosts]


def download_microtrailer(store_data):
    movies = store_data.get("movies") or []
    movies = sorted(movies, key=lambda movie: not movie.get("highlight", False))
    for movie in movies:
        for url in microtrailer_candidates(movie):
            try:
                data, content_type = request_bytes(url)
            except (HTTPError, URLError, TimeoutError, ValueError):
                continue
            if data.startswith(b"\x1aE\xdf\xa3") or "video/webm" in content_type:
                return data, movie.get("name") or "Steam microtrailer"
    return None, None


def ensure_columns(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    if "trailer_url" not in existing:
        conn.execute("ALTER TABLE games ADD COLUMN trailer_url TEXT")
        conn.commit()


def enrich_microtrailers(db_path, force=False, limit=None, resolve_missing=False, platform=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_columns(conn)

    query = """
        SELECT id, title, platform, steam_app_id, trailer_url
        FROM games
    """
    params = []
    conditions = []
    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if not force:
        conditions.append("COALESCE(trailer_url, '') = ''")
    if not resolve_missing:
        conditions.append("COALESCE(TRIM(steam_app_id), '') != ''")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY title"
    games = conn.execute(query, params).fetchall()
    if limit:
        games = games[:limit]

    TRAILERS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Processing {len(games)} games for offline Steam microtrailers...\n")

    downloaded = 0
    no_video = 0
    no_app_id = 0
    errors = 0

    for index, game in enumerate(games, 1):
        game_id = game["id"]
        title = game["title"]
        app_id = (game["steam_app_id"] or "").strip()

        if not app_id and resolve_missing:
            match = steamgriddb.find_steam_appid(title)
            if match:
                app_id = str(match["id"])
                conn.execute(
                    "UPDATE games SET steam_app_id = ? WHERE id = ?",
                    (app_id, game_id),
                )
                conn.commit()
        if not app_id:
            no_app_id += 1
            continue

        destination = TRAILERS_DIR / f"{game_id}.webm"
        local_url = f"/trailers/{game_id}.webm"
        if destination.exists() and not force:
            conn.execute(
                "UPDATE games SET trailer_url = ? WHERE id = ?",
                (local_url, game_id),
            )
            conn.commit()
            downloaded += 1
            continue

        try:
            store_data = fetch_store_data(app_id)
            if not store_data:
                no_video += 1
                print(f"[{index}/{len(games)}] {title} [NO STORE DATA]")
                continue
            video, movie_name = download_microtrailer(store_data)
            if not video:
                no_video += 1
                print(f"[{index}/{len(games)}] {title} [NO MICROTRAILER]")
                continue

            temporary = destination.with_suffix(".webm.part")
            temporary.write_bytes(video)
            temporary.replace(destination)
            conn.execute(
                "UPDATE games SET trailer_url = ?, updated_at = datetime('now') WHERE id = ?",
                (local_url, game_id),
            )
            conn.commit()
            downloaded += 1
            print(
                f"[{index}/{len(games)}] {title} "
                f"[{movie_name}, {len(video) / (1024 * 1024):.1f} MB]"
            )
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            errors += 1
            print(f"[{index}/{len(games)}] {title} [ERROR: {error}]")

        if index % 10 == 0:
            time.sleep(0.2)

    conn.close()
    print("\n" + "=" * 64)
    print(
        f"Done: {downloaded} downloaded, {no_video} without video, "
        f"{no_app_id} without app ID, {errors} errors"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="games.db", help="SQLite database path")
    parser.add_argument("--force", action="store_true", help="Re-download existing trailers")
    parser.add_argument("--limit", type=int, help="Maximum number of games to process")
    parser.add_argument(
        "--resolve-missing",
        action="store_true",
        help="Try resolving missing Steam app IDs by title",
    )
    parser.add_argument(
        "--platform",
        choices=("gog", "steam", "ps3", "ps4"),
        help="Only process games from this shelf",
    )
    arguments = parser.parse_args()
    enrich_microtrailers(
        arguments.db,
        force=arguments.force,
        limit=arguments.limit,
        resolve_missing=arguments.resolve_missing,
        platform=arguments.platform,
    )


