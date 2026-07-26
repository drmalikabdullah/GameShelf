#!/usr/bin/env python3
"""
Parse a raw GOG library folder listing (as produced by `du -sh * > gog.txt`,
or similar) into clean structured JSON.

Handles:
  - size<TAB>name lines
  - UTF-16 or UTF-8 input (auto-detected)
  - three categories: game / extras / patch
  - trailing GOG numeric IDs like "-(57222)" or "-(74575)(1)"
  - noisy platform suffixes like "_windows_gog_", "_game_windows_gog_"
  - dots/underscores as word separators
  - duplicate entries (same GOG id, or same cleaned title) -> merged, keeping
    the largest size and recording all raw paths found

Usage:
    python3 parse_gog.py gog.txt [more_lists.txt ...] -o games.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

SIZE_RE = re.compile(r'^([\d.]+)\s*([KMGT]?)B?$', re.IGNORECASE)
UNIT_MULT = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}

# Trailing noise phrases to strip once separators are normalized to spaces.
# Order matters: longer/more specific phrases first.
TRAILING_NOISE = [
    'windows gog',
    'gog',
]

# Small words that should stay lowercase in title case (unless first word)
LOWER_WORDS = {'a', 'an', 'the', 'of', 'and', 'in', 'on', 'at', 'to', 'vs'}
# Words/acronyms that should always be upper/special-cased
SPECIAL_CASE = {
    'goty': 'GOTY', 'dlc': 'DLC', 'hd': 'HD', 'rtx': 'RTX', 'ii': 'II',
    'iii': 'III', 'iv': 'IV', 'vi': 'VI', 'vii': 'VII', 'viii': 'VIII',
    'ix': 'IX', 'x': 'X',
}


def parse_size(token: str) -> int:
    m = SIZE_RE.match(token.strip())
    if not m:
        return 0
    value, unit = m.groups()
    return int(float(value) * UNIT_MULT.get(unit.upper(), 1))


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ['B', 'K', 'M', 'G', 'T']:
        if size < 1024 or unit == 'T':
            return f"{size:.1f}{unit}" if unit != 'B' else f"{int(size)}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def title_case(words_str: str) -> str:
    words = words_str.split(' ')
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in SPECIAL_CASE:
            out.append(SPECIAL_CASE[lw])
        elif i > 0 and lw in LOWER_WORDS:
            out.append(lw)
        else:
            out.append(lw.capitalize() if lw else w)
    return ' '.join(out)


def clean_title(raw_name_no_prefix: str):
    """Return (title, gog_id) from a name with the category prefix already
    stripped, e.g. 'darksiders.ii.deathinitive.edition-(2.1.0.4)' or
    'lego.dc.supervillains-(57222)'."""
    name = raw_name_no_prefix
    # strip .rar extension
    name = re.sub(r'\.rar$', '', name, flags=re.IGNORECASE)

    gog_id = None
    # match a trailing "-(digits)" or "_(digits)", optionally followed by
    # a "(digits)" duplicate-download marker, e.g. "-(74575)(1)"
    m = re.search(r'[-_]\((\d+)\)(?:\(\d+\))?$', name)
    if m:
        gog_id = m.group(1)
        name = name[:m.start()]
    else:
        # sometimes parens contain a version string like (2.1.0.4) or (1.0) -
        # not a real id; just strip trailing "-(...)"/"_(...)" of that form
        m2 = re.search(r'[-_]\(([\d.]+)\)$', name)
        if m2:
            name = name[:m2.start()]

    # normalize separators to spaces
    name = name.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    name = re.sub(r'\s+', ' ', name).strip()

    # strip trailing noise phrases (whole-word match, case-insensitive), repeatedly
    words = name.split(' ')
    changed = True
    while changed:
        changed = False
        for phrase in TRAILING_NOISE:
            phrase_words = phrase.split(' ')
            n = len(phrase_words)
            if len(words) > n and [w.lower() for w in words[-n:]] == phrase_words:
                words = words[:-n]
                changed = True
                break
    name = ' '.join(words)

    title = title_case(name)
    return title, gog_id


CATEGORY_PREFIXES = [
    ('extras-', 'extras'),
    ('patch-fix-other-', 'patch'),
    ('game-', 'game'),
]


def parse_line(size_token: str, raw_name: str):
    for prefix, category in CATEGORY_PREFIXES:
        if raw_name.startswith(prefix):
            rest = raw_name[len(prefix):]
            title, gog_id = clean_title(rest)
            return {
                'category': category,
                'title': title,
                'gog_id': gog_id,
                'size_bytes': parse_size(size_token),
                'raw_name': raw_name,
            }
    # no recognized category prefix -> plain folder entries are games
    # (some listings omit the "game-" prefix for non-archived folders)
    title, gog_id = clean_title(raw_name)
    return {
        'category': 'game',
        'title': title,
        'gog_id': gog_id,
        'size_bytes': parse_size(size_token),
        'raw_name': raw_name,
    }


def read_lines(path: Path):
    raw = path.read_bytes()
    if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        text = raw.decode('utf-16')
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('utf-8', errors='replace')
    return text.splitlines()


def parse_file(path: Path):
    entries = []
    for line in read_lines(path):
        line = line.strip('\r\n')
        if not line.strip():
            continue
        parts = line.split('\t', 1)
        if len(parts) != 2:
            continue
        size_token, raw_name = parts
        raw_name = raw_name.strip()
        # skip the listing file appearing in its own listing
        if raw_name.lower().endswith('.txt'):
            continue
        entry = parse_line(size_token.strip(), raw_name)
        if entry:
            entries.append(entry)
    return entries


def merge(entries):
    """Merge duplicate entries. Two entries are the same game if they share
    a gog_id, or (lacking an id) the same category+title."""
    by_key = {}
    order = []
    for e in entries:
        key = ('id', e['category'], e['gog_id']) if e['gog_id'] else ('title', e['category'], e['title'].lower())
        if key not in by_key:
            by_key[key] = {
                **e,
                'raw_paths': [e['raw_name']],
            }
            del by_key[key]['raw_name']
            order.append(key)
        else:
            existing = by_key[key]
            existing['raw_paths'].append(e['raw_name'])
            if e['size_bytes'] > existing['size_bytes']:
                existing['size_bytes'] = e['size_bytes']
    return [by_key[k] for k in order]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+', type=Path)
    ap.add_argument('-o', '--output', type=Path, default=Path('games.json'))
    args = ap.parse_args()

    all_entries = []
    for path in args.inputs:
        all_entries.extend(parse_file(path))

    merged = merge(all_entries)
    for e in merged:
        e['size_human'] = human_size(e['size_bytes'])

    games = [e for e in merged if e['category'] == 'game']
    extras = [e for e in merged if e['category'] == 'extras']
    patches = [e for e in merged if e['category'] == 'patch']

    games.sort(key=lambda e: e['title'])

    output = {
        'games': games,
        'extras': extras,
        'patches': patches,
    }
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(f"Parsed {len(all_entries)} raw lines -> {len(merged)} unique entries", file=sys.stderr)
    print(f"  games:   {len(games)}", file=sys.stderr)
    print(f"  extras:  {len(extras)}", file=sys.stderr)
    print(f"  patches: {len(patches)}", file=sys.stderr)
    print(f"Wrote {args.output}", file=sys.stderr)


if __name__ == '__main__':
    main()
