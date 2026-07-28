# Building the standalone GameShelf app

The Shelf can run two ways:

- **Dev mode**: `python app.py`, then open `http://127.0.0.1:5000` in a browser.
- **Standalone app**: a native desktop window (via `pywebview`) built with
  PyInstaller, so it can be double-clicked without opening a terminal.

This document covers the standalone build.

## The 3D Museum view (frontend/)

The "🏛 3D Museum" page is a separate React + Three.js app (`frontend/`,
its own `package.json`) - not part of the main app's no-build-step static
files. `build.py` rebuilds it automatically (running `npm install` the
first time, then `npm run build`) into `static/museum/`, which Flask
serves at `/museum`. Node.js is only needed on the machine *building* the
app - the packaged exe never needs it, since only the compiled JS/CSS
output ships. If Node isn't installed, `build.py` just skips this step and
prints a warning; everything else still builds normally, the museum page
just won't be included.

To work on it directly: `npm --prefix frontend install`, then
`npm --prefix frontend run dev` (proxies API calls to the Flask dev server
on :5000, so run `python app.py` alongside it).

## Important: build natively on each OS

PyInstaller does not cross-compile. A build produced on Windows only runs on
Windows; a build produced on Linux only runs on Linux. To get a Linux app,
`build.py` must be run **on a Linux machine** (or WSL2, which counts as
Linux) - there is no way to produce it from this Windows machine. The steps
below are identical on every OS once the system prerequisites are in place.

## 1. Install prerequisites

### Windows / macOS

```bash
pip install -r requirements.txt
```

Windows uses the built-in Edge WebView2 runtime (pre-installed on Windows
10/11) and macOS uses the built-in Cocoa WebView - no extra system packages
needed on either.

### Linux

`pywebview` needs a native GUI toolkit for its window - it doesn't bundle
one. Install ONE of these before `pip install`:

```bash
# Option A: Qt (recommended, works on most distros)
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine

# Option B: GTK + WebKit2
sudo apt install python3-gi gir1.2-webkit2-4.1
```

(Package names above are for Debian/Ubuntu; use your distro's equivalent,
e.g. `dnf install python3-qt5` on Fedora.)

Then:

```bash
pip install -r requirements.txt
```

## 2. Build

From the project root, on the target OS:

```bash
python build.py
```

This runs PyInstaller against `GameShelf.spec` and copies the runtime data
files (`games.db`, `static/`, `cover_overrides.json`, `steamgriddb_key.txt`)
into `dist/GameShelf/` next to the built executable. That folder is the
complete portable app.

## 3. Run

Double-click `dist/GameShelf/GameShelf.exe` on Windows to launch. Copy the
entire `dist/GameShelf/` folder to distribute it - the executable alone is
not enough, since your game library data lives in `games.db` and `static/`
next to it.

## Giving a copy to someone else

`python build.py --fresh` builds the same app but leaves your personal data
out of `dist/GameShelf/`: no `games.db` (a friend gets an empty one, auto-created the
first time they launch it), no `steamgriddb_key.txt` (your API key), and no
`static/covers`, `static/heroes`, or `static/screenshots` (art tied to your
game entries). Send them the whole `dist/` folder - they double-click
`GameShelf.exe` and start from "+ Add Game" with a totally empty library of
their own, completely separate from yours.

If they want automatic cover art, they can get their own free key at
steamgriddb.com/api and save it as a `steamgriddb_key.txt` file next to
`GameShelf.exe` (one line, just the key) - optional, the app works without it.

## Notes

- Adding a new game, screenshot, or cover art writes into
  `dist/GameShelf/games.db` and `dist/GameShelf/static/` - back that folder
  up like you would any other data.
- Rebuilding overwrites `dist/GameShelf/GameShelf.exe` but `build.py` copies your
  existing `games.db`/`static/` back in every time, so rebuilds don't wipe
  your library.
