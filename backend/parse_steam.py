#!/usr/bin/env python3
"""
Parse a raw Steam backup folder listing (`du -sh * > steam.txt`, or similar)
into the same games.json shape parse_gog.py produces, so it can be loaded
with load_db.py --platform steam.

Unlike GOG listings, Steam folder names have no category prefix or trailing
"-(id)" - they're mostly already human-readable, so this just:
  - parses size<TAB>name lines (UTF-16 or UTF-8, auto-detected)
  - strips a trailing "-installer" suffix some folders have
  - fixes a common mojibake pattern (UTF-8 text re-encoded through the wrong
    codepage) that turns a right single quote into "ΓÇÖ"

Usage:
    python3 parse_steam.py steam.txt -o steam_games.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from parse_gog import parse_size, human_size

MOJIBAKE_FIXES = {
    "ΓÇÖ": "'",
    "ΓÇÿ": "'",
    "ΓÇ£": '"',
    "ΓÇ¥": '"',
    "ΓÇô": "-",
    "ΓÇô": "-",
}


def clean_name(raw_name: str) -> str:
    name = raw_name.strip()
    for bad, good in MOJIBAKE_FIXES.items():
        name = name.replace(bad, good)
    name = re.sub(r'-installer$', '', name, flags=re.IGNORECASE).strip()
    return name


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
        if raw_name.lower().endswith('.txt'):
            continue
        title = clean_name(raw_name)
        entries.append({
            'title': title,
            'gog_id': None,
            'size_bytes': parse_size(size_token.strip()),
            'raw_name': raw_name,
        })
    return entries


def merge(entries):
    by_title = {}
    order = []
    for e in entries:
        key = e['title'].lower()
        if key not in by_title:
            by_title[key] = {**e, 'raw_paths': [e['raw_name']]}
            del by_title[key]['raw_name']
            order.append(key)
        else:
            existing = by_title[key]
            existing['raw_paths'].append(e['raw_name'])
            if e['size_bytes'] > existing['size_bytes']:
                existing['size_bytes'] = e['size_bytes']
    return [by_title[k] for k in order]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+', type=Path)
    ap.add_argument('-o', '--output', type=Path, default=Path('steam_games.json'))
    args = ap.parse_args()

    all_entries = []
    for path in args.inputs:
        all_entries.extend(parse_file(path))

    games = merge(all_entries)
    for g in games:
        g['size_human'] = human_size(g['size_bytes'])
    games.sort(key=lambda e: e['title'])

    args.output.write_text(json.dumps({'games': games}, indent=2, ensure_ascii=False))
    print(f"Parsed {len(all_entries)} raw lines -> {len(games)} unique games", file=sys.stderr)
    print(f"Wrote {args.output}", file=sys.stderr)


if __name__ == '__main__':
    main()
