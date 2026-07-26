# GameShelf — Your Game Library Catalogue

A local app to organize your game library: SQLite database + Flask API + web UI.
No cloud, no accounts. Everything lives in `games.db` on your machine.

## Quick Start

### 1. Install dependencies

```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the app

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## What's Inside

**Backend** (`backend/`):
- `app.py` — Flask server & REST API
- `games.db` — SQLite database (your library)
- `schema.sql` — Database schema
- `requirements.txt` — Python dependencies
- Parsers: `parse_gog.py`, `parse_steam.py`, `parse_ps3.py`
- Enrichers: `enrich.py`, `enrich_steamgriddb.py`, `enrich_story.py`, `steamgriddb.py`, `gog_catalog.py`
- Utilities: `build.py` (compile to .exe), `launcher.py`, `check_latest_builds.py`, etc.

**Frontend** (`static/`):
- `index.html`, `dashboard.html` — Web UI pages
- `app.js`, `dashboard.js` — JavaScript logic
- `style.css` — Styling
- `covers/`, `heroes/`, `screenshots/` — Game artwork

## Adding Games

Parse a game list file:

```bash
python parse_gog.py your_list.txt -o games.json
python load_db.py games.json --db games.db
```

This merges new games into your library without duplicating or losing your notes/ratings.

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
