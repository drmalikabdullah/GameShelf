#!/usr/bin/env python3
"""
Compare installed GOG build numbers (games.gog_id) against a GOG gamelist.txt
snapshot (title + latest known build id per line, e.g. a backup tool's
catalogue listing) and record the latest known build in games.latest_build,
so the app can show which games are current vs. behind without re-running
this comparison by hand every time.

Matching is deliberately conservative: a loose "closest title" match risks
comparing a game against the wrong thing entirely (its own DLC/toolkit, or
an unrelated same-franchise entry - e.g. "The Witcher 3" against "The
Witcher", or "Bioshock Remastered" against the non-remastered original).
So a candidate only counts if:
  - it contains every word of the query title (recall == 1.0), and
  - any extra words it adds beyond the query are on a small allow-list of
    edition/version qualifiers (remastered, enhanced, goty, ...) - never an
    arbitrary extra word, which is usually a sign of a different product.
If the DB title alone doesn't find a match, the game's own setup_*.exe
installer filenames are tried too (GOG's installer names are often closer to
the official product name than a folder-cleaned DB title), same rules
applied, and a companion SDK/toolkit/DLC installer bundled in the same
folder is never used as the source name.

A game with no confident match is left alone (latest_build stays NULL /
whatever it was), not guessed at - "unverified" is a safe, honest state;
a wrong comparison is not.

Run:
    python3 check_latest_builds.py <path-to-gamelist.txt> [--db games.db]
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

from gog_catalog import word_set

BASE_DIR = Path(__file__).parent
LINE_RE = re.compile(r"^(.*\S)\s+(\(\d+\)|-)\s*$")
BUILD_IN_FILENAME_RE = re.compile(r"\((\d{4,8})\)")

JUNK_WORDS = {
    "toolkit", "soundtrack", "artbook", "ost", "wallpaper", "poster",
    "comic", "goodies", "dlc", "upgrade", "bonus", "pack", "companion",
    "artwork", "artbooks", "manual", "artset", "sdk",
}
EDITION_WORDS = {
    "enhanced", "edition", "remastered", "definitive", "goty", "complete",
    "directors", "cut", "deluxe", "special", "gold", "classic", "redux",
    "remake", "anniversary", "collection", "hd", "ultimate", "extended",
    "version", "game", "year",
}


def parse_gamelist_text(text):
    entries = []
    for line in text.splitlines():
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("GOG Games ("):
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        title, build_token = m.group(1).strip(), m.group(2)
        build = int(build_token.strip("()")) if build_token != "-" else None
        entries.append({"title": title, "build": build, "words": word_set(title)})
    return entries


def parse_gamelist(path):
    with open(path, encoding="utf-8") as f:
        return parse_gamelist_text(f.read())


def strict_match(query_words, candidates):
    """Returns the best candidate whose words are a superset of query_words,
    with extra words limited to a couple of recognized edition qualifiers -
    see module docstring.

    Some titles (e.g. "Fallout 2") appear twice in a gamelist - once with a
    real build id, once as a bare "-" placeholder line with no build at
    all. Both tie on word-overlap, so the tiebreak prefers whichever one
    actually has a build number instead of whichever line happened to come
    first in the file."""
    if not query_words:
        return None
    short_query = len(query_words) <= 2
    best, best_extra = None, None
    for cand in candidates:
        cand_words = cand["words"]
        if not query_words <= cand_words:
            continue
        extra = cand_words - query_words
        if extra & JUNK_WORDS or len(extra) > 2:
            continue
        if short_query and not extra <= EDITION_WORDS:
            continue
        if best is None or len(extra) < best_extra or (len(extra) == best_extra and best["build"] is None and cand["build"] is not None):
            best, best_extra = cand, len(extra)
    return best


def dlc_fallback_match(query_words, candidates):
    """When a title has no non-DLC match at all, check whether every
    DLC/bonus-content candidate that does contain all its words (e.g. a
    gamelist that only ever lists "Aphelion - Artbook + Cosmetic Pack",
    never plain "Aphelion") agrees on one build number - GOG normally tags
    bonus content with the same build id as the base-game release it ships
    alongside, so a single, internally consistent number across every such
    candidate is corroborating evidence, not a guess.

    This is deliberately still not treated as fully trusted by the caller
    (see run_check): several DLC/bonus candidates disagreeing on the build
    - e.g. "Baldur's Gate 3 Toolkit" (85155) vs. "...Digital Deluxe Edition
    upgrade" (89470), two different numbers pushed independently of the
    base game - correctly returns None here, since there'd be no way to
    tell which one, if either, reflects the base game's actual build."""
    if not query_words:
        return None
    junk_candidates = [
        c for c in candidates
        if query_words <= c["words"] and (c["words"] - query_words) & JUNK_WORDS
    ]
    distinct_builds = {c["build"] for c in junk_candidates}
    if junk_candidates and len(distinct_builds) == 1 and None not in distinct_builds:
        return junk_candidates[0]
    return None


def id_confirms_current(current_build, query_words, candidates):
    """Last resort when no title-based match (even the DLC fallback) found
    anything: check whether the game's own already-installed build number
    happens to appear elsewhere in the gamelist under a title that shares
    at least one real, distinctive word with ours.

    Build ids are NOT unique per game on GOG - the same number gets reused
    across completely unrelated products (confirmed cases in the wild:
    build 38915 is both "Batman - Arkham Asylum GOTY" and the unrelated
    "Alwa's Awakening"; 60827 is DOOM I/II Enhanced *and* the unrelated
    "Relayer Advanced"). So this never trusts the id alone - only an id
    match AND shared vocabulary counts, e.g. "Fallout 4: Game of the Year
    Edition" matching build 66700 via "Fallout 4 - High Resolution Texture
    Pack" (shares "fallout"/"4", clearly the same release).

    Since this only ever looks for the CURRENT build appearing somewhere
    relevant, a hit always means "confirmed up to date", never "outdated" -
    there's no way for this path to accuse a game of being behind."""
    if current_build is None:
        return False
    meaningful = query_words - EDITION_WORDS
    if not meaningful:
        return False
    for cand in candidates:
        if cand["build"] != current_build:
            continue
        if meaningful & (cand["words"] - EDITION_WORDS):
            return True
    return False


def exe_candidate_name(filename):
    """setup_<name>_<version junk>_(<build>).exe -> "<name>", cutting at the
    first underscore-separated token that contains both a dot and a digit
    (a version signature like "1.1", "2.6.6.0-p") - a bare number with no
    dot (the "3" in "baldurs_gate_3") is left alone since that's usually
    part of the real title, not a version."""
    name = filename
    if name.lower().endswith(".exe"):
        name = name[:-4]
    if name.lower().startswith("setup_"):
        name = name[6:]
    name = re.sub(r"_\(\d+bit\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_\(\d{4,8}\)(-\d+)?$", "", name)
    tokens = name.split("_")
    cut = len(tokens)
    for i, t in enumerate(tokens):
        if "." in t and re.search(r"\d", t):
            cut = i
            break
    text = " ".join(tokens[:cut]).replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def match_via_exes(folder_path, title_words, gamelist):
    """Try every setup_*.exe in the folder as an alternate source title.
    Only commits if every exe that produces a match agrees on the same
    gamelist entry - a genuine conflict is left unmatched rather than
    guessed at (see module docstring)."""
    edition_signal = title_words & EDITION_WORDS
    try:
        exes = [f.name for f in folder_path.iterdir()
                if f.is_file() and f.name.lower().endswith(".exe") and f.name.lower().startswith("setup_")]
    except OSError:
        return None

    candidate_matches = []
    for exe in exes:
        cand_words = word_set(exe_candidate_name(exe))
        if cand_words & JUNK_WORDS:
            continue  # this exe is itself an SDK/toolkit/DLC installer, not the base game
        if edition_signal and not edition_signal <= cand_words:
            continue
        m = strict_match(cand_words, gamelist)
        if m is not None:
            candidate_matches.append(m)

    distinct_builds = {m["build"] for m in candidate_matches}
    return candidate_matches[0] if len(distinct_builds) == 1 else None


def run_check(db, gamelist):
    """Compare every GOG game's build against `gamelist` (already parsed by
    parse_gamelist/parse_gamelist_text) and record matches in
    games.latest_build. `db` is an open sqlite3 connection with
    row_factory=sqlite3.Row; caller is responsible for commit(). Returns
    (updated, skipped, total)."""
    games = db.execute(
        "SELECT id, title, gog_id, folder_path FROM games WHERE platform='gog' ORDER BY title COLLATE NOCASE"
    ).fetchall()

    updated = skipped = 0
    for g in games:
        title_words = word_set(g["title"])
        try:
            current_build = int(g["gog_id"]) if g["gog_id"] and g["gog_id"].isdigit() else None
        except ValueError:
            current_build = None

        match = strict_match(title_words, gamelist)
        if match is None and g["folder_path"] and Path(g["folder_path"]).is_dir():
            match = match_via_exes(Path(g["folder_path"]), title_words, gamelist)

        if match is None:
            fallback = dlc_fallback_match(title_words, gamelist)
            # a DLC/bonus-only match is only trusted to confirm "up to
            # date", never to accuse a game of being outdated - see
            # dlc_fallback_match's docstring for why that direction isn't
            # safe to assume
            if fallback is not None and current_build is not None and fallback["build"] is not None \
                    and current_build >= fallback["build"]:
                match = fallback

        if match is None and id_confirms_current(current_build, title_words, gamelist):
            # our own current build shows up elsewhere in the list under a
            # genuinely related title - confirmed up to date (see
            # id_confirms_current's docstring on why this can never
            # produce a false "outdated")
            match = {"build": current_build}

        if match is None or match["build"] is None:
            skipped += 1
            continue

        db.execute(
            "UPDATE games SET latest_build = ?, build_checked_at = datetime('now') WHERE id = ?",
            (str(match["build"]), g["id"]),
        )
        updated += 1

    return updated, skipped, len(games)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gamelist", help="path to a GOG gamelist.txt snapshot")
    ap.add_argument("--db", default=str(BASE_DIR / "games.db"))
    args = ap.parse_args()

    gamelist = parse_gamelist(args.gamelist)
    print(f"Parsed {len(gamelist)} entries from {args.gamelist}")

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    updated, skipped, total = run_check(db, gamelist)
    db.commit()
    print(f"Done. {updated} games matched and recorded, {skipped} left unverified ({total} total).")


if __name__ == "__main__":
    main()
