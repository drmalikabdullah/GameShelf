# GameShelf Architecture

## Source of truth

The only active project is `E:\Projects\GameShelf`. Runtime source and data
live under `backend\`. Flask serves `backend\static`; there is no second
frontend build or root-level static tree.

## Runtime

GameShelf is a local desktop/web application:

1. `backend/app.py` creates the Flask application and REST API.
2. In development, Flask listens on `127.0.0.1:5000`.
3. In the packaged application, `backend/launcher.py` starts Flask on an
   available private port and opens it inside a pywebview window.
4. `backend/games.db` stores the library.
5. `backend/static` contains the interface and local artwork.

The packaged executable binds only to localhost. It is not intended to be a
public or multi-user web service.

## Frontend

All shelves share:

- `backend/static/app.js` for game loading, filtering, editing, recycle-bin
  actions, screenshot galleries, and Big Picture behavior.
- `backend/static/style.css` for shelf, modal, Big Picture, and theme styles.
- `backend/static/theme.js` for appearance persistence.

Page files:

- `index.html` — GOG shelf
- `steam.html` — Steam shelf
- `ps3.html` — PS3 shelf
- `ps4.html` — PS4 shelf
- `dashboard.html` and `dashboard.js` — analytics and maintenance
- `settings.html` and `settings.js` — API key and appearance settings

Big Picture mode is part of the shared HTML/CSS/JavaScript frontend. It is not
a separate application. It displays the selected game's hero image using two
cross-fading backdrop layers and supports keyboard and gamepad navigation.

## Backend

`backend/app.py` owns:

- page routes for each shelf, dashboard, and settings;
- game list, create, update, soft-delete, and restore APIs;
- local screenshot and bonus-content APIs;
- folder opening and game launching;
- library statistics, dashboard data, and build-status comparisons;
- SteamGridDB API-key settings;
- first-run database creation and non-destructive column migrations.

Database connections are request-scoped through Flask's `g` object and are
closed at the end of each request.

## Data model

`backend/schema.sql` defines:

- `games` — primary game metadata and user-managed fields;
- `bonus_content` — extras and patches linked to games;
- `game_screenshots` — local screenshot URLs and ordering;
- `deleted_games` — the bounded recycle-bin archive.

Deleting a game archives its editable metadata. Restoring it creates a new
game row and reconnects its screenshot records. The recycle bin retains the
50 most recent entries; older entries and their asset references are purged.

## Artwork

Active artwork directories are:

- `backend/static/covers`
- `backend/static/heroes`
- `backend/static/logos`
- `backend/static/screenshots`

The database stores browser paths such as `/covers/42.jpg`. Artwork deletion
is constrained to the resolved `backend/static` directory. Shelf covers load
near the viewport through `IntersectionObserver`; hero and screenshot assets
load when their corresponding views are opened.

## Metadata integrations

- `gog_catalog.py` queries public GOG metadata.
- `steamgriddb.py` fetches covers, heroes, logos, and related artwork.
- `enrich_*.py` scripts backfill stories, screenshots, requirements, and
  artwork.
- `check_latest_builds.py` compares installed GOG build information with an
  imported list.

These network enrichments are optional. The local library remains usable
without network access or a SteamGridDB key.

## Packaging

- `launcher.py` is the packaged entry point.
- `GameShelf.spec` configures a windowed PyInstaller build.
- `build.py` copies the executable, static files, schema, configuration, and
  optional personal data into `backend/dist/GameShelf`.

The full `dist/GameShelf` directory is the portable application. The
executable must not be distributed by itself.

## Verification

Backend regression tests live under `backend/tests`. Python and JavaScript
syntax checks are documented in `EDITING_GUIDE.md`. Production builds should
also be tested on a clean Windows computer without a development environment.
