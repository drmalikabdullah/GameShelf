# GameShelf Editing Guide

All work must be performed in `E:\Projects\GameShelf`. The active application
is entirely under `backend\`; the Flask server does not serve files from a
root-level `static` directory.

## Shelf and Big Picture interface

- `backend/static/app.js` — shelf rendering, game details, screenshot
  lightboxes, Big Picture behavior, keyboard and gamepad controls.
- `backend/static/style.css` — all shelf, modal, theme, and Big Picture
  styling.
- `backend/static/index.html` — GOG shelf.
- `backend/static/steam.html` — Steam shelf.
- `backend/static/ps3.html` — PS3 shelf.
- `backend/static/ps4.html` — PS4 shelf.

The four shelf pages share `app.js` and `style.css`. Make behavior changes in
those shared files unless the change truly applies to only one platform.

## Dashboard and settings

- `backend/static/dashboard.html` and `dashboard.js` — statistics, build
  status, game lists, and missing-folder checks.
- `backend/static/settings.html` and `settings.js` — SteamGridDB key and
  appearance controls.
- `backend/static/theme.js` — theme persistence and application.

## Backend and database

- `backend/app.py` — Flask routes, validation, database access, game launch,
  folder opening, recycle bin, dashboard APIs, and exports.
- `backend/schema.sql` — schema used for a new database.
- `backend/tests/` — regression tests for backend behavior.
- `backend/steamgriddb.py` and `backend/gog_catalog.py` — external metadata
  and artwork integrations.
- `backend/enrich_*.py` — one-time or maintenance enrichment scripts.

When a schema change is optional metadata, add both the new-database column to
`schema.sql` and a non-destructive migration in `app.py`.

## Desktop build

- `backend/launcher.py` — native pywebview window and local server lifecycle.
- `backend/GameShelf.spec` — PyInstaller entry point and windowed settings.
- `backend/build.py` — build orchestration and runtime-data copying.
- `BUILDING.md` — user-facing build and distribution instructions.

Do not edit generated files in `backend/build` or `backend/dist`.

## Verification

From `E:\Projects\GameShelf\backend`:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
node --check static/app.js
node --check static/dashboard.js
node --check static/settings.js
node --check static/theme.js
```

Run the development server from the same directory and verify that its
`app.static_folder` resolves to `E:\Projects\GameShelf\backend\static`.
