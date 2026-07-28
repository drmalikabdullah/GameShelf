# GameShelf Dependencies

## Python

`backend/requirements.txt` is the authoritative dependency list:

- Flask — local server and REST API
- pywebview — native desktop window
- Pillow — dominant-color extraction from cover artwork
- PyInstaller — standalone executable build

SQLite, JSON, pathlib, subprocess, and the remaining backend modules are part
of Python's standard library.

Install from `E:\Projects\GameShelf\backend`:

```powershell
C:\WINDOWS\py.exe -m pip install -r requirements.txt
```

The requirements currently use unpinned versions. Before formal public
releases, test and record a known-working Python/dependency set or introduce a
lock file.

## System components

The Windows desktop build uses Microsoft Edge WebView2 through pywebview.
WebView2 is included with current Windows 10 and Windows 11 installations.

Development also uses:

- Git for version control
- Node.js only for JavaScript syntax checks; the application itself has no
  Node.js runtime or frontend build requirement

## Optional external services

### SteamGridDB

An API key enables artwork and metadata lookup. It can be configured through
the Settings page, the `STEAMGRIDDB_API_KEY` environment variable, or the
local `backend/steamgriddb_key.txt` file. Never commit an API key.

### GOG public APIs

GOG metadata lookup does not require a key. Network failures are treated as
optional enrichment failures rather than preventing local library use.

## Local data and assets

The following are runtime data, not third-party dependencies:

- `backend/games.db`
- `backend/cover_overrides.json`
- `backend/static/covers`
- `backend/static/heroes`
- `backend/static/logos`
- `backend/static/screenshots`

Back these up before large imports or manual cleanup.

## Build

Run:

```powershell
cd E:\Projects\GameShelf\backend
C:\WINDOWS\py.exe build.py
```

Use `build.py --fresh` to omit personal database/API-key/artwork data from a
copy intended for someone else. See `BUILDING.md` for distribution details.

## Dependency checks

Useful maintenance commands:

```powershell
C:\WINDOWS\py.exe -m pip check
C:\WINDOWS\py.exe -m pip list --outdated
```

Upgrade dependencies in a separate Git branch or commit, then rerun backend,
browser, and packaged-application checks before accepting the upgrade.
