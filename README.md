# The Shelf — your GOG library catalogue

A tiny local app: SQLite database + Flask API + single-page frontend.
No cloud, no accounts, everything lives in `games.db` on your machine.

## What's here

```
parse_gog.py     -> parses a raw folder-listing .txt into clean games.json
load_db.py       -> loads games.json into games.db (safe to re-run / merge more lists)
schema.sql       -> the SQLite schema
app.py           -> Flask backend (REST API + serves the frontend)
static/index.html -> the catalogue UI (search, filters, status, rating, notes)
enrich.py        -> optional: pulls cover art + metadata from GOG's public API
games.json       -> already-parsed output from your first list
games.db         -> already-built database from your first list (116 games)
```

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install flask

python3 app.py
```

Then open **http://127.0.0.1:5000** — the catalogue loads straight from `games.db`,
which is already populated from your first list.

## Adding your second list

When you're ready to send the second list, drop the file next to these scripts and run:

```bash
python3 parse_gog.py second_list.txt -o games2.json
python3 load_db.py games2.json --db games.db
```

`load_db.py` matches by GOG id (or title, if no id was detected) so it will **not**
duplicate anything already in the database — it just adds new games and refreshes
sizes for existing ones. Your status/rating/notes/tags are never touched by a reload.

You can also parse + load both lists at once any time:

```bash
python3 parse_gog.py gog.txt second_list.txt -o games.json
python3 load_db.py games.json --db games.db
```

## Cover art (optional)

```bash
python3 enrich.py --db games.db
```

This calls GOG's public product API (`api.gog.com/products/{id}`) for every game
with a detected GOG id and fills in cover art + description where available.
I couldn't test this one end-to-end myself (no internet in my sandbox), so:
- run it once, check a handful of entries actually got a `cover_url`,
- if GOG's response shape has changed or some fields come back empty, the JSON
  structure is simple enough to tweak in `extract_fields()` in `enrich.py`.

Re-running `enrich.py` only fills games still missing a cover, so it's cheap to
re-run after fixing anything.

## A few known rough edges in the parsing

Folder-listing name-cleanup is inherently a bit fuzzy. Worth a manual glance at:
- **~6 titles** ended up with a stray trailing "Game" (e.g. "Cyberpunk 2077 Game",
  "Vampire the Masquerade Bloodlines 2 Game") — GOG's own folder names inconsistently
  include the word "game" as noise vs. as part of the real title (e.g. "Lego Ninjago
  Movie **Video Game**" needs to keep it), so I didn't try to strip it automatically.
- **"Darksiders 2 Deathinitiative Edition"** and **"Darksiders II Deathinitive Edition"**
  are the same game listed twice under slightly different spellings in your original
  file, with no GOG id on either — dedupe/delete one in the UI.
- Anything under **"no GOG id detected"** in the game's modal didn't have a clean
  numeric id in the original folder name, so `enrich.py` can't fetch a cover for it.

All of this is editable directly in the UI (click any card, edit the title inline —
you'll want to add that field if you want inline title editing beyond what's there,
or just tell me and I'll wire it up), so treat the parse as a very good first draft,
not gospel.

## Notes on the design

- `status` is one of `backlog / playing / completed / abandoned` — this catalogues
  your *playthrough* status, since everything in the list is already owned.
- Sizes, raw folder paths, and GOG ids are read-only (derived from the file listing).
  Status, rating, tags, and notes are the fields you actually edit.
- Extras (bonus content) and patches are tracked in a separate `bonus_content` table,
  best-effort linked to their parent game by title match.
