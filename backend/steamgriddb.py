#!/usr/bin/env python3
"""
Shared SteamGridDB API client: search-matching + grid fetching, used by both
enrich_steamgriddb.py (bulk backfill script) and app.py (live edit/add-game
cover fetching).

Needs a free API key from https://www.steamgriddb.com/profile/preferences/api
Resolved from, in order: STEAMGRIDDB_API_KEY env var, or a local
steamgriddb_key.txt file next to this script (one line, just the key).
"""
import json
import html
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://www.steamgriddb.com/api/v2"
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
KEY_FILE = BASE_DIR / "steamgriddb_key.txt"

# SteamGridDB sits behind Cloudflare, which blocks requests without a
# browser-like User-Agent even when the API key is valid.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

ROMAN = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5',
         'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}

# Generic connector/filler words that add false recall without ever being
# what distinguishes one game from another (mirrors gog_catalog.py's
# STOPWORDS) - e.g. plain "Fallout Game" matching "Fallout 3: Game of the
# Year Edition" on "game" alone, when the real intended match is just
# "Fallout". "game"/"edition" are common enough in official titles that
# they carry near-zero identifying signal on their own.
STOPWORDS = {'a', 'an', 'the', 'of', 'and', 'in', 'on', 'to', 'for', 'game'}


def get_api_key():
    if os.environ.get("STEAMGRIDDB_API_KEY"):
        return os.environ["STEAMGRIDDB_API_KEY"]
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    return None


def api_get(path, api_key, retries=3):
    import time
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "User-Agent": UA,
        "Accept": "application/json",
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except urllib.error.URLError:
            return None
    return None


def word_set(title):
    # drop apostrophes entirely so "Baldur's" lines up with "Baldurs", rather
    # than turning into a stray "s" token, and fold roman numerals to digits
    # so "Darksiders II" lines up with a folder-parsed "Darksiders 2"
    title = title.lower().replace("'", "").replace("’", "").replace("‘", "")
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    return {ROMAN.get(w, w) for w in title.split() if w not in STOPWORDS}


def best_match(local_title, candidates):
    """Score candidates by word containment instead of trusting autocomplete's
    #1 result, which often favors a more "popular" spin-off or DLC (e.g. a
    Telltale tie-in, or a same-franchise sequel) over the actual base game.

    Primary signal is recall: does the candidate contain all the words in our
    (possibly noisy/typo'd) local title? Ties are broken by precision: prefer
    the candidate with the fewest *extra* words, i.e. the closest overall
    match rather than one burying our title in a longer official name.

    Requires overlap > 0 and recall >= 0.5 - without this, a search that
    doesn't return the real title among its candidates would still "match"
    whatever candidate happened to score highest against the initial
    (-1, -1) baseline, including a completely unrelated game with zero
    real word overlap.

    Note: a precision floor was tried here too (rejecting low-precision
    matches like single-word "Stranglehold" -> "Stranglehold of the
    Elite"), but it backfired - the actually-correct SteamGridDB entry for
    that game is "John Woo Presents Stranglehold", which has *worse*
    precision (1/4) than the wrong candidates (1/3) simply because its
    official title has a longer studio-name prefix. Irreducibly ambiguous
    single-word titles like this are handled via cover_overrides.json
    instead of a blanket threshold.

    Demos/soundtracks are deprioritized (not excluded) ahead of the
    precision tiebreak: "Batman - Arkham City" was matching "Batman Arkham
    City Demo" over the real "Batman: Arkham City - Game of the Year
    Edition", purely because the demo's shorter name gave it better
    precision than the GOTY suffix did."""
    JUNK_WORDS = {'demo', 'soundtrack', 'trailer'}
    local_words = word_set(local_title)
    if not local_words:
        return None
    best, best_score = None, (0.0, 0, 0.0)
    for cand in candidates:
        cand_words = word_set(cand["name"])
        if not cand_words:
            continue
        overlap = len(local_words & cand_words)
        if overlap == 0:
            continue
        recall = overlap / len(local_words)
        if recall < 0.5:
            continue
        not_junk = 0 if cand_words & JUNK_WORDS else 1
        score = (recall, not_junk, overlap / len(cand_words))
        if score > best_score:
            best_score, best = score, cand
    return best


GAME_URL_RE = re.compile(r"steamgriddb\.com/game/(\d+)")


def parse_game_url(text):
    """If `text` is a pasted SteamGridDB game page URL (e.g.
    https://www.steamgriddb.com/game/5209422), return its numeric id so the
    caller can fetch that exact game directly instead of fuzzy-matching a
    title - this is how a user resolves an ambiguous case like Guardians of
    the Galaxy (base game vs. the Telltale series) with certainty."""
    m = GAME_URL_RE.search(text)
    return int(m.group(1)) if m else None


def fetch_game_name(sgdb_id, api_key):
    data = api_get(f"/games/id/{sgdb_id}", api_key)
    if not data or not data.get("success"):
        return None
    return data["data"]["name"]


def fetch_cover_by_id(sgdb_id, api_key):
    """Fetch grid art for a known SteamGridDB game id directly, bypassing
    title search entirely."""
    grid_url, ext = find_grid_url(sgdb_id, api_key)
    if grid_url is None:
        return None, None
    data = download_bytes(grid_url)
    if data is None:
        return None, None
    return data, ext


def find_game_id(title, api_key):
    data = api_get(f"/search/autocomplete/{urllib.parse.quote(title)}", api_key)
    if not data or not data.get("success") or not data.get("data"):
        return None, None
    top = best_match(title, data["data"])
    if top is None:
        return None, None
    return top["id"], top["name"]


def find_grid_url(game_id, api_key):
    data = api_get(f"/grids/game/{game_id}?dimensions=600x900", api_key)
    if not data or not data.get("success") or not data.get("data"):
        # fall back to any dimension if no 600x900 grid exists
        data = api_get(f"/grids/game/{game_id}", api_key)
    if not data or not data.get("success") or not data.get("data"):
        return None, None
    grid = data["data"][0]
    return grid["url"], MIME_EXT.get(grid.get("mime"), "png")


def find_hero_url(game_id, api_key):
    data = api_get(f"/heroes/game/{game_id}", api_key)
    if not data or not data.get("success") or not data.get("data"):
        return None, None
    hero = data["data"][0]
    return hero["url"], MIME_EXT.get(hero.get("mime"), "png")


def find_logo_by_id(game_id, api_key):
    """Return (image_bytes, ext) for the official logo for a SteamGridDB game id,
    or (None, None) if not found. Downloads the logo image from CDN."""
    data = api_get(f"/logos/game/{game_id}", api_key)
    if not data or not data.get("success") or not data.get("data"):
        return None, None
    logo = data["data"][0]
    logo_url = logo["url"]
    image = download_bytes(logo_url)
    if image is None:
        return None, None
    ext = MIME_EXT.get(logo.get("mime"), "png")
    return image, ext


def fetch_logo(title, api_key):
    """Return (image_bytes, ext) for the official logo for a game title, or
    (None, None) if not found. Searches by title to find the SteamGridDB game id,
    then downloads the logo image."""
    sgdb_id, _ = find_game_id(title, api_key)
    if sgdb_id is not None:
        logo_data, ext = find_logo_by_id(sgdb_id, api_key)
        if logo_data is not None:
            return logo_data, ext
    return None, None


def download_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def _steam_search_query(title):
    """Steam's storesearch endpoint silently returns zero results when the
    query contains a standalone " - " (space-hyphen-space) - confirmed on
    real titles like "Batman - Arkham City" and "Sekiro - Shadows Die
    Twice" (both return 0 items with the hyphen, but work fine without it).
    Strip it before searching - scoring still uses the real title via
    best_match."""
    q = re.sub(r"\s+-\s+", " ", title)
    return re.sub(r"\s+", " ", q).strip()


def find_steam_appid(title):
    query = _steam_search_query(title)
    url = f"https://store.steampowered.com/api/storesearch/?{urllib.parse.urlencode({'term': query, 'l': 'english', 'cc': 'US'})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    items = data.get("items") or []
    if not items:
        return None
    # items already look like {"id": appid, "name": ...}, the shape best_match expects
    return best_match(title, items)


def fetch_steam_capsule(appid):
    """Try Steam's vertical library capsule art (600x900, same shape as our
    poster grids) at its direct, hash-free CDN path. Not every game has one
    published (smaller/newer titles often don't) - falls through to the
    landscape header image when this 404s."""
    for variant in ("library_600x900_2x.jpg", "library_600x900.jpg"):
        url = f"https://shared.steamstatic.com/store_item_assets/steam/apps/{appid}/{variant}"
        image = download_bytes(url)
        if image is not None:
            return image
    return None


def fetch_steam_hero(appid):
    """Steam's wide library hero/banner art (3840x1240-ish), at the same
    direct hash-free CDN path as the capsule. Used for the big banner shown
    at the top of a game's detail modal."""
    for variant in ("library_hero_2x.jpg", "library_hero.jpg"):
        url = f"https://shared.steamstatic.com/store_item_assets/steam/apps/{appid}/{variant}"
        image = download_bytes(url)
        if image is not None:
            return image
    return None


def fetch_hero(title, api_key):
    """Return (image_bytes, ext) for a wide banner/hero image for `title`, or
    (None, None) if nothing was found. Same priority as fetch_cover: official
    Steam hero first, SteamGridDB community hero as fallback for titles with
    no Steam release."""
    match = find_steam_appid(title)
    if match is not None:
        hero = fetch_steam_hero(match["id"])
        if hero is not None:
            return hero, "jpg"

    sgdb_id, _ = find_game_id(title, api_key)
    if sgdb_id is not None:
        hero_url, ext = find_hero_url(sgdb_id, api_key)
        if hero_url is not None:
            data = download_bytes(hero_url)
            if data is not None:
                return data, ext
    return None, None


def fetch_hero_by_id(sgdb_id, api_key):
    """Fetch hero art for a known SteamGridDB game id directly, bypassing
    title search entirely - mirrors fetch_cover_by_id."""
    hero_url, ext = find_hero_url(sgdb_id, api_key)
    if hero_url is None:
        return None, None
    data = download_bytes(hero_url)
    if data is None:
        return None, None
    return data, ext


def fetch_steam_header_only(appid):
    """Steam's landscape store header (460x215-ish) - every Steam game has
    one, but it crops badly when forced into our vertical poster slot, so
    this is only used as an absolute last resort."""
    req = urllib.request.Request(
        f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=US&l=english",
        headers={"User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    entry = data.get(str(appid)) or {}
    if not entry.get("success"):
        return None
    header_url = entry.get("data", {}).get("header_image")
    if not header_url:
        return None
    return download_bytes(header_url)


def fetch_steam_release_year(appid):
    """Fetch the release year for a known Steam appid via Steam's public
    appdetails API, or None if unavailable/unparseable. Steam's release_date
    field is a display string (e.g. "9 Nov, 2015", "Coming soon", "1997"),
    not a fixed format, so this just grabs the last 4-digit run in it."""
    req = urllib.request.Request(
        f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=US&l=english",
        headers={"User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    entry = data.get(str(appid)) or {}
    if not entry.get("success"):
        return None
    date_str = entry.get("data", {}).get("release_date", {}).get("date", "")
    years = re.findall(r"\d{4}", date_str)
    return years[-1] if years else None


def _fetch_steam_store_details(appid):
    req = urllib.request.Request(
        f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=US&l=english",
        headers={"User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    entry = data.get(str(appid)) or {}
    if not entry.get("success"):
        return None
    return entry.get("data", {})


def _steam_html_to_text(value):
    if not value:
        return None
    value = re.sub(r"(?i)<br\s*/?>|</(?:p|li|ul)>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", html.unescape(value))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line) or None


def fetch_steam_description_and_requirements(appid):
    """Return clean short description and PC requirements from Steam."""
    details = _fetch_steam_store_details(appid)
    if details is None:
        return None, None
    description = _steam_html_to_text(details.get("short_description"))
    requirements = details.get("pc_requirements") or {}
    minimum = _steam_html_to_text(requirements.get("minimum"))
    recommended = _steam_html_to_text(requirements.get("recommended"))
    parts = []
    if minimum:
        parts.append(f"Minimum\n{minimum}")
    if recommended:
        parts.append(f"Recommended\n{recommended}")
    return description, "\n\n".join(parts) or None


def fetch_steam_description(appid):
    """Fetch Steam's clean short store description for a known appid."""
    description, _ = fetch_steam_description_and_requirements(appid)
    return description


def fetch_steam_requirements(appid):
    """Fetch Steam's clean minimum/recommended PC requirements."""
    _, requirements = fetch_steam_description_and_requirements(appid)
    return requirements


def find_release_year(title):
    """Resolve `title` to a Steam appid and fetch its release year, or None
    if no confident appid match exists or it has no parseable release date."""
    match = find_steam_appid(title)
    if match is None:
        return None
    return fetch_steam_release_year(match["id"])


def fetch_steam_review_score(appid):
    """Fetch Steam's own review-score summary for a known appid, or None if
    unavailable/no reviews yet. Valve's review_score is already a 0-9 scale
    (0 = no reviews, 1 = Overwhelming Negative ... 9 = Overwhelmingly
    Positive), close enough to our 1-10 rating scale to use directly."""
    req = urllib.request.Request(
        f"https://store.steampowered.com/appreviews/{appid}?json=1&num_per_page=0",
        headers={"User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    score = data.get("query_summary", {}).get("review_score")
    return score if score else None


def find_release_year_and_rating(title):
    """Resolve `title` to a Steam appid once, then fetch both its release
    year and review score - used together in refresh_steam_release_year,
    no need to resolve the appid twice."""
    match = find_steam_appid(title)
    if match is None:
        return None, None
    return fetch_steam_release_year(match["id"]), fetch_steam_review_score(match["id"])


def fetch_steam_official(appid):
    """Fetch official Steam art for a known appid directly - vertical library
    capsule first, landscape store header as fallback (every Steam game has
    a header, not every game has a capsule published)."""
    capsule = fetch_steam_capsule(appid)
    if capsule is not None:
        return capsule, "jpg"
    header = fetch_steam_header_only(appid)
    if header is not None:
        return header, "jpg"
    return None, None


def fetch_cover(title, api_key):
    """Return (image_bytes, ext) for `title`, or (None, None) if nothing was
    found anywhere. Priority:
    1. Steam's official vertical library capsule (matches our poster shape
       exactly, and is the real official art, not a community re-upload).
    2. A SteamGridDB community grid - used when there's no official capsule,
       since a properly-shaped fan-made cover looks far better than an
       official image forced into the wrong aspect ratio.
    3. Steam's landscape store header as an absolute last resort (crops
       badly, but better than nothing) for titles not on SteamGridDB either.
    """
    appid = None
    match = find_steam_appid(title)
    if match is not None:
        appid = match["id"]
        capsule = fetch_steam_capsule(appid)
        if capsule is not None:
            return capsule, "jpg"

    sgdb_id, _ = find_game_id(title, api_key)
    if sgdb_id is not None:
        grid_url, ext = find_grid_url(sgdb_id, api_key)
        if grid_url is not None:
            data = download_bytes(grid_url)
            if data is not None:
                return data, ext

    if appid is not None:
        header = fetch_steam_header_only(appid)
        if header is not None:
            return header, "jpg"

    return None, None


def fetch_steam_screenshots(appid, limit=6):
    """Fetch up to `limit` screenshot URLs from Steam Store API for a known appid.
    Returns list of (data, ext) tuples ready to save to disk, or empty list."""
    url = f"https://store.steampowered.com/api/appdetails/?appids={appid}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return []

    app_data = data.get(str(appid), {}).get("data", {})
    screenshot_urls = app_data.get("screenshots", [])
    if not screenshot_urls:
        return []

    results = []
    for screenshot in screenshot_urls[:limit]:
        img_url = screenshot.get("path_thumbnail")
        if not img_url:
            continue
        img_url = img_url.replace("_96x54", "")
        img_data = download_bytes(img_url)
        if img_data is not None:
            results.append((img_data, "jpg"))
    return results
