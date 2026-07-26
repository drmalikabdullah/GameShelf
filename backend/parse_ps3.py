#!/usr/bin/env python3
"""
Parse a raw PS3 backup folder listing into the same games.json shape
parse_gog.py produces, so it can be loaded with load_db.py --platform ps3.

PS3 folder names have their own quirks vs GOG/Steam listings:
  - real Sony title-id codes trail many names, e.g. "BLES01392", "BLUS30264",
    "BCUS98232", "NPEB01968" - stripped, not stored (they're PS3-specific,
    not useful for GOG/SteamGridDB lookups)
  - bracketed DLC/fix annotations like "[+ All DLC]", "[Fix + All DLC]"
  - underscores instead of spaces in some entries, inconsistent casing

Usage:
    python3 parse_ps3.py size.txt -o ps3_games.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from parse_gog import parse_size, human_size

TITLE_ID_RE = re.compile(r'\b[A-Z]{4}\d{5}\b')
BRACKET_NOISE_RE = re.compile(r'\[[^\]]*\]')


def clean_name(raw_name: str) -> str:
    name = raw_name.replace('_', ' ').replace('-', ' ')
    name = TITLE_ID_RE.sub('', name)
    name = BRACKET_NOISE_RE.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\(\s*', '(', name)
    name = re.sub(r'\s*\)', ')', name)
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
        if not title:
            continue
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
    ap.add_argument('-o', '--output', type=Path, default=Path('ps3_games.json'))
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
