#!/usr/bin/env python3
"""
Client for looking up real GOG catalog product ids - separate from gog_id,
which is the user's own build-version number from their folder naming, not
a catalog id (see schema.sql).

Uses a local mirror of GOG DB's (https://www.gogdb.org) product index
instead of GOG's own catalog search (https://catalog.gog.com), which turned
out to be unreliable: it silently returns a generic ~50-item fallback list
instead of an error for some queries (e.g. containing a colon or the word
"and"), and returns zero results for others that are plainly on GOG. GOG
DB's index is a static per-title dataset with no query-shaping to go wrong.
Per GOG DB's own FAQ (https://www.gogdb.org/moreinfo), a one-time bulk
download of the index is the intended way to use their data - not lots of
small per-title requests - so the index is cached locally and reused.
"""
import json
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

INDEX_PATH = BASE_DIR / "gogdb_index.sqlite3"
INDEX_URL = "https://www.gogdb.org/data/index.sqlite3"

ROMAN = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5',
         'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}

# Generic connector words that add false recall without ever being what
# distinguishes one game from another - e.g. "Batman a Telltale Game
# Series" losing to "Minecraft: Story Mode - A Telltale Game Series"
# because "a"/"game"/"series" overlapped while the one word that actually
# matters ("batman") did not. "game" earns its spot alongside articles and
# prepositions here: it's a frequent trailing artifact in source folder
# titles (see find_catalog_id's callers) and appears constantly in real
# GOG titles ("X: Game of the Year Edition"), so plain "Fallout Game" was
# matching "Fallout 4: Game of the Year Edition" (perfect recall) over the
# actually-correct "Fallout" (perfect precision, but recall dominates the
# comparison first).
STOPWORDS = {'a', 'an', 'the', 'of', 'and', 'in', 'on', 'to', 'for', 'game'}

_candidates = None  # cached in-process: (id, title, ...) rows from the index


def word_set(title):
    title = title.lower().replace("'", "").replace("’", "").replace("‘", "")
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    return {ROMAN.get(w, w) for w in title.split() if w not in STOPWORDS}


def best_match(local_title, candidates):
    """Word-containment scoring: recall first (does the candidate contain
    all our words), then non-DLC over DLC (a soundtrack/addon can otherwise
    out-precision the actual game it belongs to, by virtue of having a
    shorter title with fewer "extra" words), then precision (fewest extra
    words), then sale rank (lower = better seller) - GOG DB sometimes has
    multiple products with the exact same title (e.g. a legacy internal
    record alongside the actual storefront listing), so the actively-sold
    one is the more useful id to store. "pack" isn't deprioritized here
    alongside "dlc" - it's often just the actual purchasable SKU of the
    base game itself, not an add-on.

    Requires overlap > 0 and recall >= 0.5 - without this, a candidate list
    that doesn't contain the real title would still "match" whatever
    candidate scored highest against the initial baseline, including a
    completely unrelated product with zero real word overlap."""
    local_words = word_set(local_title)
    if not local_words:
        return None
    best, best_score = None, (0.0, 0, 0.0, float("-inf"))
    for cand in candidates:
        cand_words = word_set(cand["title"])
        if not cand_words:
            continue
        overlap = len(local_words & cand_words)
        if overlap == 0:
            continue
        recall = overlap / len(local_words)
        if recall < 0.5:
            continue
        sale_rank = cand.get("sale_rank")
        not_dlc = 0 if cand.get("product_type") == "dlc" else 1
        score = (recall, not_dlc, overlap / len(cand_words), -(sale_rank if sale_rank else 10**9))
        if score > best_score:
            best_score, best = score, cand
    return best


def _ensure_index():
    """Download GOG DB's product index once if we don't already have a
    local copy. Returns True if the index is available to query."""
    if INDEX_PATH.exists():
        return True
    try:
        urllib.request.urlretrieve(INDEX_URL, str(INDEX_PATH))
    except (urllib.error.URLError, OSError):
        return False
    return True


def _load_candidates():
    global _candidates
    if _candidates is not None:
        return _candidates
    if not _ensure_index():
        return []
    conn = sqlite3.connect(str(INDEX_PATH))
    try:
        rows = conn.execute("SELECT product_id, title, sale_rank, product_type FROM products").fetchall()
    finally:
        conn.close()
    _candidates = [{"id": r[0], "title": r[1], "sale_rank": r[2], "product_type": r[3]} for r in rows]
    return _candidates


def find_catalog_id(title):
    """Look up `title` in GOG DB's product index and return (id,
    official_title) as strings, or (None, None) if nothing found."""
    candidates = _load_candidates()
    if not candidates:
        return None, None
    match = best_match(title, candidates)
    if match is None:
        return None, None
    return str(match["id"]), match["title"]


def _fetch_product(catalog_id):
    """Fetch GOG DB's full per-product record for a known catalog id, or
    None on any failure. One request per game - not part of the bulk
    index, but only ever called once per game (results are cached in the
    games table after)."""
    url = f"https://www.gogdb.org/data/products/{catalog_id}/product.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return None


def find_release_year(catalog_id):
    """Extract the release year from GOG DB's per-product data, or None if
    unavailable. Prefers global_date (the game's original release date),
    falling back to store_date (when GOG itself first listed it) when
    global_date isn't set - several newer/smaller titles have only the
    latter."""
    data = _fetch_product(catalog_id)
    if data is None:
        return None
    date_str = data.get("global_date") or data.get("store_date")
    if not date_str:
        return None
    m = re.match(r"(\d{4})-", date_str)
    return m.group(1) if m else None


def find_user_rating(catalog_id):
    """Extract GOG's user rating for a known catalog id, converted to our
    1-10 scale, or None if unrated. GOG DB's user_rating field is 0-50
    (their 5-star display x10 for extra precision - confirmed against
    known games: The Witcher 2 = 47 -> 4.7 stars, Baldur's Gate 3 = 46 ->
    4.6 stars), so dividing by 5 lands it on our 1-10 scale."""
    data = _fetch_product(catalog_id)
    if data is None:
        return None
    raw = data.get("user_rating")
    if not raw:
        return None
    return max(1, min(10, round(raw / 5)))


def fetch_cover(title):
    """Fetch this GOG title's box art with no API key needed at all, using
    GOG DB's public catalog - the fallback cover source for platform='gog'
    games when no SteamGridDB key is configured (or SteamGridDB simply had
    nothing for the title), so a fresh install with no API key still shows
    cover art for actual GOG games. Returns (image_bytes, ext) or
    (None, None) on any failure - never raises, matching every other
    best-effort fetch in this module."""
    catalog_id, _ = find_catalog_id(title)
    if catalog_id is None:
        return None, None
    data = _fetch_product(catalog_id)
    if data is None:
        return None, None
    image_hash = data.get("image_boxart")
    if not image_hash:
        return None, None
    url = f"{GOG_IMAGE_BASE}/{image_hash}.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read(), "jpg"
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None, None


def find_release_year_and_rating(catalog_id):
    """Like find_release_year + find_user_rating, but a single request -
    used together in verify_gog_id, no need to fetch the product twice."""
    data = _fetch_product(catalog_id)
    if data is None:
        return None, None
    date_str = data.get("global_date") or data.get("store_date")
    year = None
    if date_str:
        m = re.match(r"(\d{4})-", date_str)
        year = m.group(1) if m else None
    raw = data.get("user_rating")
    rating = max(1, min(10, round(raw / 5))) if raw else None
    return year, rating


GOG_IMAGE_BASE = "https://images.gog-statics.com"
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"[ \t]+")
HTML_ENTITIES = {"&amp;": "&", "&#39;": "'", "&quot;": '"', "&nbsp;": " "}


def _strip_description_html(html):
    """GOG DB's description field is raw marketing HTML (headers, videos,
    award banners, small inline icon images) wrapped around the actual
    prose. Stripping tags to plain text is enough for most games - big AAA
    relaunches (e.g. Cyberpunk 2077's Phantom Liberty page) sometimes
    replace the prose entirely with video embeds, which is why the caller
    treats a too-short result as "no story" rather than storing
    marketing-banner leftovers.

    Every stripped inline tag (an <img> bullet icon, an empty <div>) leaves
    behind a lone space, so runs like "<br><img><br><img><br>" collapse to
    "\\n \\n \\n" - newlines separated by single spaces rather than sitting
    consecutively - which a plain \\n{3,} regex never catches, leaving dozens
    of near-blank lines in the rendered result. Splitting into lines and
    dropping any that are blank after stripping sidesteps that entirely,
    regardless of what was between the newlines."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = HTML_TAG_RE.sub(" ", text)
    for entity, char in HTML_ENTITIES.items():
        text = text.replace(entity, char)
    text = WHITESPACE_RE.sub(" ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n\n".join(lines).strip()


def fetch_story_and_screenshots(catalog_id, max_screenshots=6):
    """Fetch story text + screenshot image URLs + genre tags + developer for
    a known GOG catalog id, all from a single GOG catalog fetch (no Steam
    dependency, since every game here already has a verified catalog id -
    see verify_gog_id). Returns (description_or_None, [screenshot_url, ...],
    genres_csv_or_None, developer_or_None). Description is None if GOG's
    page has no real prose (see _strip_description_html) - a short
    leftover-banner-text result is treated the same as no data."""
    data = _fetch_product(catalog_id)
    if data is None:
        return None, [], None, None

    # A handful of catalog ids (e.g. an internal/QA product GOG DB happens to
    # mirror) carry obvious unrendered template placeholders instead of real
    # copy - "product_description_<id>", "TEST DEVELOPER" - rather than
    # empty fields. Treat those the same as no data instead of storing them.
    raw_description = data.get("description") or ""
    if re.search(r"product_description_\d+|product_feature_\d+", raw_description):
        raw_description = ""
    description = _strip_description_html(raw_description)
    if len(description) < 40:
        description = None

    hashes = data.get("screenshots") or []
    urls = [f"{GOG_IMAGE_BASE}/{h}.jpg" for h in hashes[:max_screenshots]]
    genre_names = [t["name"] for t in (data.get("tags") or []) if t.get("name")]
    genres = ", ".join(genre_names) or None
    developers = [d for d in (data.get("developers") or []) if d.strip().upper() != "TEST DEVELOPER"]
    developer = ", ".join(developers) or None
    return description, urls, genres, developer
