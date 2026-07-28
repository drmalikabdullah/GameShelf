# GameShelf Data Flow

## Application startup

1. `app.py` resolves `BASE_DIR`.
   - Source run: the `backend` directory.
   - Packaged run: the directory containing `GameShelf.exe`.
2. If `games.db` does not exist, `schema.sql` creates an empty library.
3. Non-destructive migrations add optional metadata columns to older
   databases.
4. Flask serves the pages and files from `BASE_DIR/static`.

The packaged launcher starts this server on a free localhost port and points a
native pywebview window at it.

## Shelf loading

1. A shelf page declares its platform in `window.APP_PLATFORM`.
2. `app.js` requests `/api/games` and `/api/stats`.
3. The backend filters and sorts SQLite rows and serializes JSON fields.
4. The page renders all matching cards.
5. Cover backgrounds are requested only as cards approach the viewport.

Search input is debounced before requesting a newly filtered game list.

## Opening and editing a game

1. Clicking a shelf card finds the corresponding game in the current
   JavaScript state.
2. The modal renders its hero, cover, metadata, editable fields, story,
   screenshots, and requirements.
3. Individual field changes send `PATCH /api/games/<id>`.
4. The backend validates status, rating, paths, and case colors before writing.
5. A title change can trigger platform-specific metadata/artwork refresh.
6. The updated row is returned and replaces the frontend's current copy.

Folder paths are checked and their size is calculated recursively. Executable
paths must identify an existing file.

## Adding a game

1. The user supplies a title from a shelf's Add Game dialog.
2. `POST /api/games` creates a minimal row.
3. Platform-specific title and metadata lookup runs when available.
4. The complete serialized row is returned.
5. The shelf refreshes.

Metadata services are best-effort; a game can exist without remote artwork.

## Artwork

Downloaded artwork is written to a game-ID-based file in:

- `/covers`
- `/heroes`
- `/logos`
- `/screenshots/<game_id>`

The matching browser URL is stored in SQLite. Cover and hero URLs include the
game's update timestamp as a cache-busting query value. File cleanup resolves
and verifies the target under `backend/static` before unlinking anything.

## Big Picture mode

1. Opening Big Picture requests the complete current platform shelf.
2. Local filters and search select the carousel's current list.
3. The focused game updates the cross-fading hero backdrop, title/logo,
   metadata, story, requirements, and screenshot strip.
4. Arrow keys, buttons, or gamepad input change the focused index.
5. Screenshot requests in flight are aborted when focus changes quickly.
6. Clicking the focused cover opens its read-only immersive detail view.
7. A configured executable can be launched with
   `POST /api/games/<id>/play`.

## Screenshot gallery

`GET /api/games/<id>/screenshots` returns local paths ordered by position.
Clicking a screenshot opens a lightbox. Left/right controls wrap through the
available images and Escape closes the lightbox.

## Soft delete and restore

### Delete

1. `DELETE /api/games/<id>` copies all editable game fields into
   `deleted_games`.
2. Bonus content is detached.
3. The active game row is removed.
4. Artwork and screenshot records remain available for restore.
5. Entries beyond the 50-item recycle-bin limit are permanently purged.

### Restore

1. `POST /api/deleted_games/<trash_id>/restore` inserts a new game row using
   the archived metadata.
2. Screenshot records are reconnected from the original ID to the new ID.
3. The archive row is removed.
4. The restored game is returned to the frontend.

## Dashboard

The dashboard requests aggregate endpoints for:

- platform and status totals;
- storage and rating distributions;
- recently added games;
- build status and imported build lists;
- missing folders;
- curated lists and insights.

Queries are local SQLite reads. Folder scanning is performed only when the
user asks for it.

## Settings and themes

The SteamGridDB key is read or written through `/api/settings/steamgriddb_key`.
Appearance selection is stored in browser local storage by `theme.js` and is
applied to shelves, dashboard/settings pages, Big Picture, and immersive
modals.

## Build flow

1. `build.py` invokes PyInstaller with `GameShelf.spec`.
2. The spec packages `launcher.py` as a windowed executable.
3. Runtime files are copied beside the executable in `dist/GameShelf`.
4. A normal build includes personal data when present.
5. A `--fresh` build excludes the database, API key, and personal artwork.
